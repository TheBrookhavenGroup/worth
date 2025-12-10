from datetime import datetime, date, timedelta
import json

from plotly.offline import plot
import plotly.graph_objs as go

from django.http import HttpResponse
import pandas as pd
from django.views.generic import TemplateView, FormView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from analytics.pnl import pnl_summary, pnl_if_closed, ticker_pnl, performance, daily_pnl
from analytics.utils import total_realized_gains, income, expenses
from analytics.models import PPMResult
from analytics.forms import PnLForm
from trades.ib_flex import get_trades
from trades.utils import weighted_average_price
from tbgutils.dt import lbd_prior_month, our_now, prior_business_day
from tbgutils.str import is_near_zero, cround
from markets.tbgyahoo import yahoo_url
from markets.models import Ticker
from worth.utils import df_to_jqtable, nice_headings

from markets.utils import get_price, ticker_admin_url
from markets.models import DailyPrice
from accounts.models import Account


class MyFormView(FormView):
    title = "No Title"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = self.title
        return context


class PnLView(LoginRequiredMixin, MyFormView):
    template_name = "analytics/pnl.html"
    form_class = PnLForm
    success_url = "."
    title = "PnL"
    account = None
    days = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get
        account = getter("account")
        days = getter("days")
        active_f = bool(getter("active_f", True))

        if self.days:
            days = self.days

        if self.account:
            account = self.account

        if days is not None:
            try:
                if days.lower() == "lbd":
                    d = prior_business_day(date.today())
                else:
                    raise AttributeError("days arg not known")

            except AttributeError:
                days = int(days)
                d = our_now() - timedelta(days=days)
                d = d.date()
        else:
            d = getter("d")

            if d is not None:
                try:
                    d = datetime.strptime(d, "%Y%m%d").date()
                except Exception:
                    n = 0
                    if d.isnumeric():
                        n = int(d)
                        d = our_now()
                        while n > 0:
                            d = lbd_prior_month(d)
                            n -= 1
            else:
                d = our_now().date()

        context["d"] = d
        (
            context["headings1"],
            context["data1"],
            context["formats"],
            total_worth,
            total_today,
        ) = pnl_summary(d=d, a=account, active_f=active_f)
        context["total_worth"] = total_worth
        context["total_today"] = total_today
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        self.account = data["account"]
        self.days = data["days"]
        return self.render_to_response(self.get_context_data(form=form))


class GetIBTradesView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/table.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["headings1"], context["data1"], context["formats"] = get_trades()
        context["title"] = "IB Futures Trades"
        return context


class TickerView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/ticker.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticker_symbol = context["ticker"]
        ticker = Ticker.objects.get(ticker=ticker_symbol)
        context["ticker"] = ticker_symbol
        context["tickeradmin"] = ticker_admin_url(self.request, ticker)
        context["title"] = yahoo_url(ticker)
        context["description"] = ticker.description

        pos, wap = weighted_average_price(ticker)

        if is_near_zero(pos):
            context["msg"] = "Zero position."
        else:
            context["pos"] = pos
            context["wap"] = wap

            try:
                cs = ticker.market.cs
                price = get_price(ticker)
                context["price"] = price
                context["capital"] = cs * pos * price
                context["realizable_pnl"] = cs * pos * (price - wap)
                context["total_pnl"] = ticker_pnl(ticker)
            except IndexError:
                context["msg"] = "Could not get a price for this ticker."

        return context


class ValueChartView(LoginRequiredMixin, TemplateView):
    title = "Value Chart"
    template_name = "analytics/value_chart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        getter = self.request.GET.get

        d = datetime.today().date()
        n_months = getter("n_months")

        if n_months is None:
            n_months = 24

        x_axis = [d, prior_business_day(d)] + [
            d := lbd_prior_month(d) for i in range(int(n_months))
        ]
        x_axis.reverse()

        account = getter("a")
        # Treat missing or empty 'a' as All Accounts
        if not account:
            d_exists = PPMResult.objects.filter(d__in=x_axis).values_list("d", flat=True)
            for d in set(x_axis) - set(d_exists):
                pnl_summary(d, active_f=False)
            y_axis = (
                PPMResult.objects.filter(d__in=x_axis)
                .order_by("d")
                .values_list("value", flat=True)
            )
            y_axis = [i / 1.0e6 for i in y_axis]
            name = self.title
        else:
            y_axis = [pnl_summary(d, a=account, active_f=False)[-2] / 1.0e6 for d in x_axis]
            name = f"{self.title} for {account}"

        x_axis = [f"{d:%Y-%m-%d}" for d in x_axis]

        fig = go.Figure(
            data=go.Scatter(
                x=x_axis,
                y=y_axis,
                mode="lines",
                name=name,
                opacity=0.8,
                marker_color="green",
            )
        )
        fig.update_layout({"title_text": name, "yaxis_title": "Millions($)"})

        context["plot_div"] = plot({"data": fig}, output_type="div")

        # UI context
        context["title"] = self.title
        context["accounts"] = Account.objects.filter(active_f=True).order_by("name")
        context["selected_account"] = account or ""
        context["selected_n_months"] = int(n_months)

        return context


class RealizedGainView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/realized.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year = self.request.GET.get("year")
        if year is None:
            messages.info(self.request, "You can set the year.  ex: ?year=2022")
            year = date.today().year
        else:
            year = int(year)

        realized, formatter = total_realized_gains(year)

        # Build the table rows with the provided row formatter
        h, data, _ = df_to_jqtable(df=realized, formatter=formatter)
        context["h"] = h
        context["realized"] = data

        # Right-justify only the Realized column (index 2); left-align others
        context["f"] = json.dumps(
            {
                "columnDefs": [
                    {"targets": [0, 1], "className": "dt-body-left"},
                    {"targets": [2], "className": "dt-body-right"},
                ],
                "ordering": False,
                "pageLength": 100,
            }
        )

        context["realizedcsvurl"] = reverse("analytics:realizedcsv", args=[year])

        return context


class DailyPnLView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/daily_pnl.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        getter = self.request.GET.get
        account = getter("a") or None
        quick_range = (getter("range") or "").strip().lower()

        # Parse dates from GET; default to last 30 days
        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d").date()
            except Exception:
                return None

        end = parse_date(getter("end"))
        start = parse_date(getter("start"))

        today = date.today()
        if quick_range:
            if quick_range in ("current month", "current_month", "cm"):
                start = today.replace(day=1)
                end = today
            elif quick_range in ("last month", "last_month", "lm"):
                first_of_this_month = today.replace(day=1)
                last_month_end = first_of_this_month - timedelta(days=1)
                start = last_month_end.replace(day=1)
                end = last_month_end
            elif quick_range in ("current year", "current_year", "cy"):
                start = date(today.year, 1, 1)
                end = today

        # Fallback defaults when nothing specified
        if end is None:
            end = today
        if start is None:
            start = end - timedelta(days=30)

        # Build dataframe of daily PnL (ignore positions/trades here)
        df, _pos, _trades = daily_pnl(a=account, start=start, end=end)

        # If viewing all accounts, roll up PnL by day across accounts
        if not account:
            if not df.empty:
                grouped = df.groupby("d", as_index=False)["pnl"].sum()
                grouped["a"] = "(All Accounts)"
                df = grouped[["d", "a", "pnl"]]

        # Build base URL for Daily Trades and render the date as a real <a> link
        daily_trades_url = reverse("analytics:daily_trades")

        def formatter(d, a, pnl):
            d_str = f"{d:%Y-%m-%d}"
            href = f"{daily_trades_url}?d={d_str}"
            if account:
                href += f"&a={account}"
            link_html = f'<a href="{href}" target="_blank">{d_str}</a>'
            return link_html, a, cround(pnl)

        # Only include the desired columns in the table view
        # Base DataTables formats from utility
        context["h"], context["data"], context["formats"] = df_to_jqtable(
            df=df[["d", "a", "pnl"]], formatter=formatter
        )
        # Make the Account column more compact on this page by truncating long text
        try:
            _fmt = json.loads(context["formats"]) if context.get("formats") else {}
        except Exception:
            _fmt = {}
        # Ensure columnDefs exists and add truncate class + preferred widths
        _defs = _fmt.get("columnDefs") or []
        # Date column width (index 0)
        _defs.append({"targets": [0], "width": "110px"})
        # Account column: make compact and truncated
        _defs.append({"targets": [1], "className": "truncate", "width": "160px"})
        # PnL column: keep tight so it doesn't expand the table
        _defs.append({"targets": [2], "width": "100px"})
        _fmt["columnDefs"] = _defs
        # Remove search box and pagination controls on Daily PnL table
        _fmt["searching"] = False
        _fmt["paging"] = False
        _fmt["info"] = False
        # Only render the table (no length, filter, or pagination elements)
        _fmt["dom"] = "t"
        context["formats"] = json.dumps(_fmt)
        context["headings"] = nice_headings(context["h"])
        # Total PnL across the displayed rows
        total = float(df["pnl"].sum()) if not df.empty else 0.0
        context["total_pnl"] = cround(total)

        # UI context
        context["title"] = "Daily PnL"
        context["accounts"] = Account.objects.filter(active_f=True).order_by("name")
        context["selected_account"] = account or ""
        context["selected_start"] = f"{start:%Y-%m-%d}"
        context["selected_end"] = f"{end:%Y-%m-%d}"
        context["selected_range"] = quick_range
        context["daily_trades_url"] = daily_trades_url

        return context


def realized_csv_view(request, param=None):
    if param is None:
        year = date.today().year
    else:
        year = int(param)

    result, formats = total_realized_gains(year)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="realized.csv"'

    result = result.round(decimals=2)
    result.to_csv(path_or_buf=response, index=False)

    return response


class PnLIfClosedView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/table.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        losses, formatter = pnl_if_closed()

        h, context["data1"], context["formats"] = df_to_jqtable(df=losses, formatter=formatter)
        context["headings1"] = nice_headings(h)
        context["title"] = "Worth - Losers"
        context["d"] = "PnL if closed today."
        return context


class DailyTradesView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/daily_trades.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get
        d_str = getter("d")
        account = getter("a") or None

        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except Exception:
            d = date.today()

        # Compute Daily PnL for the selected day (and optional account)
        try:
            d_pnl_df, pos_df, trades_df = daily_pnl(a=account, start=d, end=d)
            if d_pnl_df.empty:
                day_pnl_val = 0.0
            else:
                if account:
                    day_pnl_val = float(d_pnl_df[d_pnl_df["a"] == account]["pnl"].sum())
                else:
                    day_pnl_val = float(d_pnl_df["pnl"].sum())
        except Exception:
            day_pnl_val = 0.0
            trades_df = pd.DataFrame()
        context["day_pnl"] = cround(day_pnl_val)
        # Use trades returned by daily_pnl (already bucketed)
        df = trades_df
        if df.empty:
            headings = ["time", "a", "t", "q", "p", "commission", "reinvest"]
            context["headings"] = nice_headings(headings)
            context["h"] = headings
            context["data"] = []
            # Disable search/paging/info by default for empty tables too
            context["formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})
            # No trades -> no prices table either
            context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
            context["prices_h"] = ["ticker", "prev_close", "close"]
            context["prices_data"] = []
            context["prices_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})
            # Opening positions (none)
            context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
            context["openpos_h"] = ["ticker", "open_pos"]
            context["openpos_data"] = []
            context["openpos_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})
        else:
            # Filter to the selected trading day, and prepare display columns
            dff = df[df["d"] == d].copy()

            # Ensure timezone-aware New York timestamp for display
            if not pd.api.types.is_datetime64_any_dtype(dff["dt"]):
                dff["dt"] = pd.to_datetime(dff["dt"], errors="coerce")
            if pd.api.types.is_datetime64tz_dtype(dff["dt"]):
                dff["_dt_eastern"] = dff["dt"].dt.tz_convert("America/New_York")
            else:
                # Treat naive timestamps as local America/New_York wall time
                dff["_dt_eastern"] = pd.to_datetime(dff["dt"], errors="coerce").dt.tz_localize(
                    "America/New_York"
                )

            # Add a full date-time column for display
            dff["time"] = dff["_dt_eastern"].dt.strftime("%Y-%m-%d %H:%M:%S")

            # Order by time
            dff.sort_values("dt", inplace=True)

            # Select and rename columns for display
            show = dff[["time", "a", "t", "q", "p", "c", "r"]]
            show.columns = ["time", "a", "t", "q", "p", "commission", "reinvest"]

            def formatter(time, a, t, q, p, commission, reinvest):
                return (time, a, t, q, p, commission, ("Y" if bool(reinvest) else ""))

            context["h"], context["data"], context["formats"] = df_to_jqtable(
                df=show, formatter=formatter
            )
            # Disable DataTables controls for the trades table
            try:
                _fmt_trades = json.loads(context.get("formats") or "{}")
            except Exception:
                _fmt_trades = {}
            _fmt_trades.update({"searching": False, "paging": False, "info": False, "dom": "t"})
            context["formats"] = json.dumps(_fmt_trades)
            context["headings"] = nice_headings(context["h"])

            # --- Prices table using pos_df from daily_pnl ---
            try:
                if pos_df is not None and not pos_df.empty:
                    pos_day = pos_df[pos_df["d"] == d]
                    if account:
                        pos_day = pos_day[pos_day["a"] == account]
                    # Limit to tickers traded that day for a tighter view
                    tickers_today = sorted(set(dff["t"].dropna().tolist()))
                    if tickers_today:
                        pos_day = pos_day[pos_day["ticker"].isin(tickers_today)]
                    px = (
                        pos_day[["ticker", "prev_close", "close"]]
                        .drop_duplicates(subset=["ticker"])
                        .sort_values("ticker")
                        .rename(columns={"ticker": "t"})
                    )

                    def px_formatter(t, prev_close, close):
                        prev_fmt = "" if pd.isna(prev_close) else (cround(float(prev_close)))
                        cur_fmt = "" if pd.isna(close) else cround(float(close))
                        return t, prev_fmt, cur_fmt

                    if not px.empty:
                        (
                            context["prices_h"],
                            context["prices_data"],
                            context["prices_formats"],
                        ) = df_to_jqtable(
                            df=px[["t", "prev_close", "close"]], formatter=px_formatter
                        )
                        # Remove search/pagination from prices table
                        try:
                            _fmt_px = json.loads(context.get("prices_formats") or "{}")
                        except Exception:
                            _fmt_px = {}
                        _fmt_px.update({"searching": False, "paging": False, "info": False, "dom": "t"})
                        context["prices_formats"] = json.dumps(_fmt_px)
                        context["prices_headings"] = nice_headings(context["prices_h"])
                    else:
                        context["prices_headings"] = nice_headings(
                            ["ticker", "prev_close", "close"]
                        )
                        context["prices_h"] = ["ticker", "prev_close", "close"]
                        context["prices_data"] = []
                        context["prices_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})
                else:
                    context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
                    context["prices_h"] = ["ticker", "prev_close", "close"]
                    context["prices_data"] = []
                    context["prices_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})
            except Exception:
                # Fallback to empty prices table on any error
                context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
                context["prices_h"] = ["ticker", "prev_close", "close"]
                context["prices_data"] = []
                context["prices_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})

            # (legacy prices building removed; now sourced from pos_df above)

            # --- Opening positions at start of the selected day ---
            # Compute cumulative position for all prior trading days
            # for tickers traded that day
            tickers_today = sorted(set(dff["t"].dropna().tolist()))
            if tickers_today:
                df_before = df[df["d"] < d]
                if not df_before.empty:
                    # Net position per ticker at day open (sum of quantities)
                    pos_open = (
                        df_before[df_before["t"].isin(tickers_today)]
                        .groupby(["a", "t"], as_index=False)["q"]
                        .sum()
                    )
                    # If account filter provided, grouping still includes it;
                    # select only active account row
                    if account:
                        pos_open = pos_open[pos_open["a"] == account]
                    pos_open = pos_open[["t", "q"]].rename(
                        columns={"t": "ticker", "q": "open_pos"}
                    )

                    def pos_fmt(ticker, open_pos):
                        try:
                            return ticker, int(round(float(open_pos)))
                        except Exception:
                            return ticker, open_pos

                    (
                        context["openpos_h"],
                        context["openpos_data"],
                        context["openpos_formats"],
                    ) = df_to_jqtable(df=pos_open[["ticker", "open_pos"]], formatter=pos_fmt)
                    # Disable DataTables controls for the Open Positions table
                    try:
                        _fmt_op = json.loads(context.get("openpos_formats") or "{}")
                    except Exception:
                        _fmt_op = {}
                    _fmt_op.update({"searching": False, "paging": False, "info": False, "dom": "t"})
                    context["openpos_formats"] = json.dumps(_fmt_op)
                    context["openpos_headings"] = nice_headings(context["openpos_h"])
                else:
                    context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                    context["openpos_h"] = ["ticker", "open_pos"]
                    context["openpos_data"] = []
                    context["openpos_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})
            else:
                context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                context["openpos_h"] = ["ticker", "open_pos"]
                context["openpos_data"] = []
                context["openpos_formats"] = json.dumps({"searching": False, "paging": False, "info": False, "dom": "t"})

        context["title"] = "Trades for Day"
        context["selected_account"] = account or ""
        context["selected_date"] = d.strftime("%Y-%m-%d")
        context["daily_pnl_url"] = reverse("analytics:daily_pnl")

        return context


class IncomeExpenseView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/income_expense.html"

    def get_context_data(self, **kwargs):
        def formatter(a, b, c=None):
            if c is None:
                return a, cround(b)
            else:
                return a, b, cround(c)

        messages.get_messages(self.request).used = True

        context = super().get_context_data(**kwargs)

        year = self.request.GET.get("year")
        if year is None:
            messages.info(self.request, "You can set the year.  ex: ?year=2022")
            year = date.today().year
        else:
            year = int(year)

        expense_df, expense_fmt = expenses(year)
        income_df, income_fmt = income(year)

        total_expenses = expense_df["amt"].iloc[-1]
        total_income = income_df["amt"].iloc[-1]
        net_profit = total_income - total_expenses

        context["e_h"], context["expense"], _ = df_to_jqtable(df=expense_df, formatter=formatter)
        context["e_f"] = expense_fmt

        context["i_h"], context["income"], _ = df_to_jqtable(df=income_df, formatter=formatter)
        context["i_f"] = income_fmt

        # Expose totals to the template
        context["total_income"] = net_profit + total_expenses
        context["total_expenses"] = total_expenses
        context["net_profit"] = net_profit

        context["title"] = f"Income/Expense ({year})"
        context["incomecsvurl"] = reverse("analytics:incomecsv", args=[year])
        context["expensecsvurl"] = reverse("analytics:expensescsv", args=[year])
        return context


def income_csv_view(request, param=None):
    if param is None:
        year = date.today().year
    else:
        year = int(param)

    result, formats = income(year)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="income.csv"'

    result = result.round(decimals=2)
    result.to_csv(path_or_buf=response, index=False)

    return response


def expenses_csv_view(request, param=None):
    if param is None:
        year = date.today().year
    else:
        year = int(param)

    result, formats = expenses(year)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="expenses.csv"'

    result.to_csv(path_or_buf=response, index=False)

    return response


class TickerChartView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/ticker_chart.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticker_symbol = context["ticker"]
        ticker = Ticker.objects.get(ticker=ticker_symbol)

        # Get historical prices from database
        historical_prices = DailyPrice.objects.filter(ticker=ticker).order_by("d")

        # Get current price if not in database
        today = date.today()
        current_price_in_db = historical_prices.filter(d=today).exists()

        dates = [p.d for p in historical_prices]
        prices = [p.c for p in historical_prices]

        # Add current price if not already in database
        if not current_price_in_db:
            current_price = get_price(ticker)
            dates.append(today)
            prices.append(current_price)

        # Create the plot
        fig = go.Figure(
            data=go.Scatter(
                x=dates,
                y=prices,
                mode="lines+markers",
                name=f"{ticker_symbol} Price",
                opacity=0.8,
                marker_color="blue",
            )
        )

        fig.update_layout(
            {
                "title_text": f"Price History for {ticker_symbol}",
                "yaxis_title": "Price ($)",
                "xaxis_title": "Date",
            }
        )

        context["plot_div"] = plot({"data": fig}, output_type="div")
        context["ticker"] = ticker_symbol
        context["title"] = f"Price Chart for {ticker_symbol}"

        return context


class PerformanceView(LoginRequiredMixin, TemplateView):
    template_name = "analytics/table.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["headings1"], context["data1"], context["formats"] = performance()
        context["title"] = "Performance"
        return context
