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
from analytics.pnl import pnl_summary, pnl_if_closed, ticker_pnl, daily_pnl
from analytics.risk import daily_returns, sharpe, volatility, total_return, annualized_return
from analytics.utils import total_realized_gains, income, expenses
from analytics.models import PPMResult
from analytics.forms import PnLForm
from trades.ib_flex import get_trades
from trades.models import copy_trades_df
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
            total_pnl,
        ) = pnl_summary(d=d, a=account, active_f=active_f)
        context["total_worth"] = total_worth
        context["total_today"] = total_today
        context["total_pnl"] = total_pnl
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
        context["headings1"], context["data1"], context["formats1"] = get_trades()
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
                context["value"] = cs * pos * price
                context["realizable_pnl"] = cs * pos * (price - wap)
            except IndexError:
                context["msg"] = "Could not get a price for this ticker."

        try:
            context["total_pnl"] = ticker_pnl(ticker, active_f=False)
        except (IndexError, Exception):
            pass

        df = copy_trades_df(t=ticker_symbol, active_f=False)
        if not df.empty:
            df = df.sort_values("dt")
            df["pos"] = df["q"].cumsum()
            df["value"] = df["q"] * df["p"] * df["cs"]

            df = df[["dt", "a", "q", "p", "value", "pos"]]

            def trade_formatter(dt, a, q, p, v, pos):
                return [
                    dt.strftime("%Y-%m-%d %H:%M"),
                    a,
                    cround(q),
                    cround(p),
                    cround(v),
                    cround(pos),
                ]

            context["trades_headings"], context["trades_data"], context["trades_formats"] = (
                df_to_jqtable(df, formatter=trade_formatter)
            )

            context["trades_headings"] = ["Date", "Account", "Q", "P", "Value", "Pos"]

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
                "paging": False,
                "info": False,
                "dom": "t",
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
            context["formats"] = json.dumps(
                {"searching": False, "paging": False, "info": False, "dom": "t"}
            )

            # Build Prices and Opening Positions from pos_df even when there are no trades
            try:
                if pos_df is not None and not pos_df.empty:
                    pos_day = pos_df[pos_df["d"] == d]
                    if account:
                        pos_day = pos_day[pos_day["a"] == account]

                    # Prices table: include any tickers with non-zero opening or closing positions
                    pos_for_prices = pos_day[
                        (pos_day["opening_pos"].fillna(0) != 0)
                        | (pos_day["closing_pos"].fillna(0) != 0)
                    ]
                    px = (
                        pos_for_prices[["ticker", "prev_close", "close"]]
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
                        try:
                            _fmt_px = json.loads(context.get("prices_formats") or "{}")
                        except Exception:
                            _fmt_px = {}
                        _fmt_px.update(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                        context["prices_formats"] = json.dumps(_fmt_px)
                        context["prices_headings"] = nice_headings(context["prices_h"])
                    else:
                        context["prices_headings"] = nice_headings(
                            ["ticker", "prev_close", "close"]
                        )
                        context["prices_h"] = ["ticker", "prev_close", "close"]
                        context["prices_data"] = []
                        context["prices_formats"] = json.dumps(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )

                    # Opening positions table directly from pos_df opening_pos
                    op = pos_day[pos_day["opening_pos"].fillna(0) != 0][["ticker", "opening_pos"]]
                    op = (
                        op.rename(columns={"opening_pos": "open_pos"})
                        .drop_duplicates(subset=["ticker"])
                        .sort_values("ticker")
                    )

                    def pos_fmt(ticker, open_pos):
                        try:
                            return ticker, int(round(float(open_pos)))
                        except Exception:
                            return ticker, open_pos

                    if not op.empty:
                        (
                            context["openpos_h"],
                            context["openpos_data"],
                            context["openpos_formats"],
                        ) = df_to_jqtable(df=op[["ticker", "open_pos"]], formatter=pos_fmt)
                        try:
                            _fmt_op = json.loads(context.get("openpos_formats") or "{}")
                        except Exception:
                            _fmt_op = {}
                        _fmt_op.update(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                        context["openpos_formats"] = json.dumps(_fmt_op)
                        context["openpos_headings"] = nice_headings(context["openpos_h"])
                    else:
                        context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                        context["openpos_h"] = ["ticker", "open_pos"]
                        context["openpos_data"] = []
                        context["openpos_formats"] = json.dumps(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                else:
                    # No pos_df available
                    context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
                    context["prices_h"] = ["ticker", "prev_close", "close"]
                    context["prices_data"] = []
                    context["prices_formats"] = json.dumps(
                        {"searching": False, "paging": False, "info": False, "dom": "t"}
                    )
                    context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                    context["openpos_h"] = ["ticker", "open_pos"]
                    context["openpos_data"] = []
                    context["openpos_formats"] = json.dumps(
                        {"searching": False, "paging": False, "info": False, "dom": "t"}
                    )
            except Exception:
                # Fallback to empty tables on any error
                context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
                context["prices_h"] = ["ticker", "prev_close", "close"]
                context["prices_data"] = []
                context["prices_formats"] = json.dumps(
                    {"searching": False, "paging": False, "info": False, "dom": "t"}
                )
                context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                context["openpos_h"] = ["ticker", "open_pos"]
                context["openpos_data"] = []
                context["openpos_formats"] = json.dumps(
                    {"searching": False, "paging": False, "info": False, "dom": "t"}
                )

            # Add an explanatory note when PnL exists but no trades present
            try:
                if (
                    day_pnl_val
                    and abs(float(day_pnl_val)) > 0
                    and (trades_df is None or trades_df.empty)
                ):
                    context["d"] = (
                        "PnL from mark-to-market on open positions (no trades on this day)."
                    )
            except Exception:
                pass
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
                    # Include any tickers with positions regardless of whether traded that day
                    pos_for_prices = pos_day[
                        (pos_day["opening_pos"].fillna(0) != 0)
                        | (pos_day["closing_pos"].fillna(0) != 0)
                    ]
                    px = (
                        pos_for_prices[["ticker", "prev_close", "close"]]
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
                        _fmt_px.update(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                        context["prices_formats"] = json.dumps(_fmt_px)
                        context["prices_headings"] = nice_headings(context["prices_h"])
                    else:
                        context["prices_headings"] = nice_headings(
                            ["ticker", "prev_close", "close"]
                        )
                        context["prices_h"] = ["ticker", "prev_close", "close"]
                        context["prices_data"] = []
                        context["prices_formats"] = json.dumps(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                else:
                    context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
                    context["prices_h"] = ["ticker", "prev_close", "close"]
                    context["prices_data"] = []
                    context["prices_formats"] = json.dumps(
                        {"searching": False, "paging": False, "info": False, "dom": "t"}
                    )
            except Exception:
                # Fallback to empty prices table on any error
                context["prices_headings"] = nice_headings(["ticker", "prev_close", "close"])
                context["prices_h"] = ["ticker", "prev_close", "close"]
                context["prices_data"] = []
                context["prices_formats"] = json.dumps(
                    {"searching": False, "paging": False, "info": False, "dom": "t"}
                )

            # (legacy prices building removed; now sourced from pos_df above)

            # --- Opening positions at start of the selected day (from pos_df) ---
            try:
                if pos_df is not None and not pos_df.empty:
                    pos_day2 = pos_df[pos_df["d"] == d]
                    if account:
                        pos_day2 = pos_day2[pos_day2["a"] == account]
                    pos_open_df = (
                        pos_day2[pos_day2["opening_pos"].fillna(0) != 0][["ticker", "opening_pos"]]
                        .rename(columns={"opening_pos": "open_pos"})
                        .drop_duplicates(subset=["ticker"])
                        .sort_values("ticker")
                    )

                    def pos_fmt(ticker, open_pos):
                        try:
                            return ticker, int(round(float(open_pos)))
                        except Exception:
                            return ticker, open_pos

                    if not pos_open_df.empty:
                        (
                            context["openpos_h"],
                            context["openpos_data"],
                            context["openpos_formats"],
                        ) = df_to_jqtable(
                            df=pos_open_df[["ticker", "open_pos"]], formatter=pos_fmt
                        )
                        try:
                            _fmt_op = json.loads(context.get("openpos_formats") or "{}")
                        except Exception:
                            _fmt_op = {}
                        _fmt_op.update(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                        context["openpos_formats"] = json.dumps(_fmt_op)
                        context["openpos_headings"] = nice_headings(context["openpos_h"])
                    else:
                        context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                        context["openpos_h"] = ["ticker", "open_pos"]
                        context["openpos_data"] = []
                        context["openpos_formats"] = json.dumps(
                            {"searching": False, "paging": False, "info": False, "dom": "t"}
                        )
                else:
                    context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                    context["openpos_h"] = ["ticker", "open_pos"]
                    context["openpos_data"] = []
                    context["openpos_formats"] = json.dumps(
                        {"searching": False, "paging": False, "info": False, "dom": "t"}
                    )
            except Exception:
                context["openpos_headings"] = nice_headings(["ticker", "open_pos"])
                context["openpos_h"] = ["ticker", "open_pos"]
                context["openpos_data"] = []
                context["openpos_formats"] = json.dumps(
                    {"searching": False, "paging": False, "info": False, "dom": "t"}
                )

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

        total_expenses = expense_df["amt"].iloc[-1] if not expense_df.empty else 0.0
        total_income = income_df["amt"].iloc[-1] if not income_df.empty else 0.0
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
        # Default account is MarcIB; allow override via query string ?a=
        request = self.request
        account = request.GET.get("a", "MarcIB") if request else "MarcIB"

        df = daily_returns(a=account)
        # Change heading 'ret' -> 'r' for display
        if "ret" in df.columns:
            df = df.rename(columns={"ret": "r"})

        # Add cumulative return per account as 'cr'
        # Ensure proper sorting and numeric dtype for returns
        if not df.empty and "r" in df.columns:
            try:
                df = df.sort_values(["a", "d"]) if "a" in df.columns else df.sort_values(["d"])  # type: ignore[arg-type]
                r_numeric = pd.to_numeric(df["r"], errors="coerce").fillna(0.0)
                if "a" in df.columns and df["a"].nunique() > 1:
                    df["cr"] = r_numeric.groupby(df["a"]).transform(
                        lambda s: (1 + s).cumprod() - 1
                    )
                else:
                    df["cr"] = (1 + r_numeric).cumprod() - 1
            except Exception:
                # If anything goes wrong, still render table without cumulative return
                pass

        # Compute risk/performance metrics from the returns dataframe and show above table
        try:
            sh = sharpe(df)
            tr = total_return(df)
            ar = annualized_return(df)
            vol = volatility(df)

            def format_metric(val, as_pct=False):
                if pd.isna(val):
                    return "—"
                if as_pct:
                    return f"{val * 100:.2f}%"
                return f"{val:.2f}"

            def format_display(m, as_pct=False):
                if isinstance(m, pd.Series):
                    return ", ".join(
                        [f"{idx}: {format_metric(val, as_pct)}" for idx, val in m.items()]
                    )
                return format_metric(m, as_pct)

            sharpe_display = format_display(sh)
            tr_display = format_display(tr, as_pct=True)
            ar_display = format_display(ar, as_pct=True)
            vol_display = format_display(vol, as_pct=True)
        except Exception:
            sharpe_display = tr_display = ar_display = vol_display = "—"

        # Place it in the context's generic header slot shown above the table
        context["d"] = (
            f"Sharpe: {sharpe_display} | Total Return: {tr_display} | "
            f"Annualized: {ar_display} | Volatility: {vol_display}"
        )

        # Format columns:
        # - pnl: 2 decimals
        # - ts: 0 decimals
        # - r: percentage string (2 decimals)
        # - cr: cumulative return percentage string (2 decimals)
        daily_trades_url = reverse("analytics:daily_trades")

        def formatter(d, a, pnl, ts, r, cr=None):
            def fmt(val, fmt_str):
                if pd.isna(val):
                    return ""
                try:
                    return format(val, fmt_str)
                except Exception:
                    return val

            d_str = f"{d:%Y-%m-%d}"
            href = f"{daily_trades_url}?d={d_str}"
            if a and a != "(All Accounts)":
                href += f"&a={a}"
            link_html = f'<a href="{href}" target="_blank">{d_str}</a>'

            pnl_str = fmt(pnl, ",.2f")
            ts_str = fmt(ts, ",.0f")
            # Display returns as percentages
            try:
                r_str = "" if pd.isna(r) else f"{r * 100:.2f}%"
            except Exception:
                r_str = r
            # Cumulative return formatting (optional)
            try:
                cr_str = "" if cr is None or pd.isna(cr) else f"{cr * 100:.2f}%"
            except Exception:
                cr_str = cr
            # If the incoming dataframe doesn't have 'cr', formatter may be called with only 5 args
            # In that case, cr will be None and we omit it by returning 5-tuple
            if cr is None and "cr" not in df.columns:
                return link_html, a, pnl_str, ts_str, r_str
            return link_html, a, pnl_str, ts_str, r_str, cr_str

        headings, data, formats1 = df_to_jqtable(df=df, formatter=formatter)
        # Remove the search box for this table
        f1 = json.loads(formats1)
        f1["searching"] = False
        context["headings1"] = headings
        context["data1"] = data
        context["formats1"] = json.dumps(f1)

        # Add YTD returns table
        if not df.empty and "r" in df.columns:
            try:
                ytd_df = df.copy()
                ytd_df["year"] = pd.to_datetime(ytd_df["d"]).dt.year
                ytd_df["r"] = pd.to_numeric(ytd_df["r"], errors="coerce").fillna(0.0)

                if "a" in ytd_df.columns and ytd_df["a"].nunique() > 1:
                    ytd_res = (
                        ytd_df.groupby(["a", "year"])["r"]
                        .apply(lambda s: (1 + s).prod() - 1)
                        .reset_index()
                    )
                    ytd_res = ytd_res.pivot(index="year", columns="a", values="r")
                    ytd_res = ytd_res.sort_index(ascending=False)
                    ytd_headings = ["Year"] + list(ytd_res.columns)
                    ytd_data = []
                    for year, row in ytd_res.iterrows():
                        ytd_data.append(
                            [int(year)] + [f"{v * 100:.2f}%" if pd.notna(v) else "—" for v in row]
                        )
                else:
                    ytd_res = (
                        ytd_df.groupby("year")["r"]
                        .apply(lambda s: (1 + s).prod() - 1)
                        .reset_index()
                    )
                    ytd_res = ytd_res.sort_values("year", ascending=False)
                    ytd_headings = ["Year", "Return"]
                    ytd_data = [
                        [int(row["year"]), f"{row['r'] * 100:.2f}%"]
                        for _, row in ytd_res.iterrows()
                    ]

                context["headings2"] = ytd_headings
                context["data2"] = ytd_data
                context["formats2"] = json.dumps(
                    {
                        "columnDefs": [
                            {
                                "targets": [i for i in range(1, len(ytd_headings))],
                                "className": "dt-body-right",
                            }
                        ],
                        "ordering": True,
                        "searching": False,
                        "paging": False,
                        "info": False,
                    }
                )
            except Exception:
                pass

        context["title"] = f"Performance ({account})"
        return context
