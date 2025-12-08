from datetime import datetime, date, timedelta, time

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
from tbgutils.dt import lbd_prior_month, our_now, prior_business_day, day_start_next_day, next_business_day
from tbgutils.str import is_near_zero, cround
from markets.tbgyahoo import yahoo_url
from markets.models import Ticker
from worth.utils import df_to_jqtable, nice_headings

from markets.utils import get_price, ticker_admin_url
from markets.models import DailyPrice
from accounts.models import Account


class MyFormView(FormView):
    title = 'No Title'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = self.title
        return context


class PnLView(LoginRequiredMixin, MyFormView):
    template_name = 'analytics/pnl.html'
    form_class = PnLForm
    success_url = '.'
    title = 'PnL'
    account = None
    days = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get
        account = getter('account')
        days = getter('days')
        active_f = bool(getter('active_f', True))

        if self.days:
            days = self.days

        if self.account:
            account = self.account

        if days is not None:
            try:
                if days.lower() == 'lbd':
                    d = prior_business_day(date.today())
                else:
                    raise AttributeError("days arg not known")

            except AttributeError:
                days = int(days)
                d = our_now() - timedelta(days=days)
                d = d.date()
        else:
            d = getter('d')

            if d is not None:
                try:
                    d = datetime.strptime(d, '%Y%m%d').date()
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

        context['d'] = d
        (context['headings1'], context['data1'], context['formats'],
         total_worth, total_today) = \
            pnl_summary(d=d, a=account, active_f=active_f)
        context['total_worth'] = total_worth
        context['total_today'] = total_today
        return context

    def form_valid(self, form):
        data = form.cleaned_data
        self.account = data['account']
        self.days = data['days']
        return self.render_to_response(self.get_context_data(form=form))


class GetIBTradesView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['headings1'], context['data1'], context['formats'] = \
            get_trades()
        context['title'] = 'IB Futures Trades'
        return context


class TickerView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/ticker.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticker_symbol = context['ticker']
        ticker = Ticker.objects.get(ticker=ticker_symbol)
        context['ticker'] = ticker_symbol
        context['tickeradmin'] = ticker_admin_url(self.request, ticker)
        context['title'] = yahoo_url(ticker)
        context['description'] = ticker.description

        pos, wap = weighted_average_price(ticker)

        if is_near_zero(pos):
            context['msg'] = 'Zero position.'
        else:
            context['pos'] = pos
            context['wap'] = wap

            try:
                cs = ticker.market.cs
                price = get_price(ticker)
                context['price'] = price
                context['capital'] = cs * pos * price
                context['realizable_pnl'] = cs * pos * (price - wap)
                context['total_pnl'] = ticker_pnl(ticker)
            except IndexError:
                context['msg'] = 'Could not get a price for this ticker.'

        return context


class ValueChartView(LoginRequiredMixin, TemplateView):
    title = 'Value Chart'
    template_name = 'analytics/value_chart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        getter = self.request.GET.get

        d = datetime.today().date()
        n_months = getter('n_months')

        if n_months is None:
            n_months = 24

        x_axis = [d, prior_business_day(d)] + \
                 [d := lbd_prior_month(d) for i in range(int(n_months))]
        x_axis.reverse()

        account = getter('a')
        # Treat missing or empty 'a' as All Accounts
        if not account:
            d_exists = PPMResult.objects.filter(d__in=x_axis). \
                values_list('d', flat=True)
            for d in set(x_axis) - set(d_exists):
                pnl_summary(d, active_f=False)
            y_axis = PPMResult.objects.filter(d__in=x_axis).order_by('d'). \
                values_list('value', flat=True)
            y_axis = [i / 1.e6 for i in y_axis]
            name = self.title
        else:
            y_axis = [pnl_summary(d, a=account,
                                  active_f=False)[-2] / 1.e6 for d in x_axis]
            name = f"{self.title} for {account}"

        x_axis = [f'{d:%Y-%m-%d}' for d in x_axis]

        fig = go.Figure(data=go.Scatter(x=x_axis, y=y_axis,
                        mode='lines', name=name,
                        opacity=0.8, marker_color='green'))
        fig.update_layout({'title_text': name, 'yaxis_title': 'Millions($)'})

        context['plot_div'] = plot({'data': fig}, output_type='div')

        # UI context
        context['title'] = self.title
        context['accounts'] = (
            Account.objects.filter(active_f=True).order_by('name'))
        context['selected_account'] = account or ''
        context['selected_n_months'] = int(n_months)

        return context


class RealizedGainView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/realized.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        year = self.request.GET.get('year')
        if year is None:
            messages.info(self.request, 'You can set the year.  ex: ?year=2022')
            year = date.today().year
        else:
            year = int(year)

        realized, formatter = total_realized_gains(year)

        context['h'], context['realized'], _ = (
            df_to_jqtable(df=realized, formatter=formatter))
        context["f"] = formatter
        context["realizedcsvurl"] = reverse('analytics:realizedcsv',
                                            args=[year])

        return context


class DailyPnLView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/daily_pnl.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        getter = self.request.GET.get
        account = getter('a') or None
        # Parse dates from GET; default to last 30 days
        def parse_date(s):
            try:
                return datetime.strptime(s, '%Y-%m-%d').date()
            except Exception:
                return None

        end = parse_date(getter('end'))
        start = parse_date(getter('start'))

        if end is None:
            end = date.today()
        if start is None:
            start = end - timedelta(days=30)

        # Build dataframe and present only date, account, and pnl (drop open/close values)
        df = daily_pnl(a=account, start=start, end=end)

        # Build base URL for Daily Trades and render the date as a real <a> link
        daily_trades_url = reverse('analytics:daily_trades')

        def formatter(d, a, pnl):
            d_str = f"{d:%Y-%m-%d}"
            href = f"{daily_trades_url}?d={d_str}"
            if account:
                href += f"&a={account}"
            link_html = f"<a href=\"{href}\" target=\"_blank\">{d_str}</a>"
            return link_html, a, cround(pnl)

        # Only include the desired columns in the table view
        context['h'], context['data'], context['formats'] = (
            df_to_jqtable(df=df[['d', 'a', 'pnl']], formatter=formatter))
        context['headings'] = nice_headings(context['h'])
        # Total PnL across the displayed rows
        total = float(df['pnl'].sum()) if not df.empty else 0.0
        context['total_pnl'] = cround(total)

        # UI context
        context['title'] = 'Daily PnL'
        context['accounts'] = Account.objects.filter(active_f=True).order_by('name')
        context['selected_account'] = account or ''
        context['selected_start'] = f"{start:%Y-%m-%d}"
        context['selected_end'] = f"{end:%Y-%m-%d}"
        context['daily_trades_url'] = daily_trades_url

        return context


def realized_csv_view(request, param=None):
    if param is None:
        year = date.today().year
    else:
        year = int(param)

    result, formats = total_realized_gains(year)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="realized.csv"'

    result = result.round(decimals=2)
    result.to_csv(path_or_buf=response, index=False)

    return response


class PnLIfClosedView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        losses, formatter = pnl_if_closed()

        h, context['data1'], context['formats'] = (
            df_to_jqtable(df=losses, formatter=formatter))
        context['headings1'] = nice_headings(h)
        context['title'] = 'Worth - Losers'
        context['d'] = f'PnL if closed today.'
        return context


class DailyTradesView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/daily_trades.html'

    def get_context_data(self, **kwargs):
        from trades.models import get_trades_df
        from accounts.models import CashRecord

        context = super().get_context_data(**kwargs)
        getter = self.request.GET.get
        d_str = getter('d')
        account = getter('a') or None

        try:
            d = datetime.strptime(d_str, '%Y-%m-%d').date()
        except Exception:
            d = date.today()

        # Compute Daily PnL for the selected day (and optional account)
        try:
            d_pnl_df = daily_pnl(a=account, start=d, end=d)
            if d_pnl_df.empty:
                day_pnl_val = 0.0
            else:
                if account:
                    day_pnl_val = float(d_pnl_df[d_pnl_df['a'] == account]['pnl'].sum())
                else:
                    day_pnl_val = float(d_pnl_df['pnl'].sum())
        except Exception:
            day_pnl_val = 0.0
        context['day_pnl'] = cround(day_pnl_val)

        # Load trades and filter to the specific day
        df = get_trades_df(a=account)
        if df.empty:
            headings = ['time', 'a', 't', 'q', 'p', 'commission', 'reinvest']
            context['headings'] = nice_headings(headings)
            context['h'] = headings
            context['data'] = []
            context['formats'] = '{}'
            # No trades -> no prices table either
            context['prices_headings'] = nice_headings(['ticker', 'prev_close', 'close'])
            context['prices_h'] = ['ticker', 'prev_close', 'close']
            context['prices_data'] = []
            context['prices_formats'] = '{}'
            # Opening positions (none)
            context['openpos_headings'] = nice_headings(['ticker', 'open_pos'])
            context['openpos_h'] = ['ticker', 'open_pos']
            context['openpos_data'] = []
            context['openpos_formats'] = '{}'
        else:
            # Compute per-market trading day using market t_close in America/New_York
            if not pd.api.types.is_datetime64_any_dtype(df['dt']):
                df['dt'] = pd.to_datetime(df['dt'], utc=True)
            else:
                if not pd.api.types.is_datetime64tz_dtype(df['dt']):
                    df['dt'] = pd.to_datetime(df['dt'], utc=True)

            df['_dt_eastern'] = df['dt'].dt.tz_convert('America/New_York')

            # Map tickers to market close times
            tickers = sorted(set(df['t'].dropna().tolist()))
            if tickers:
                tclose_qs = (
                    Ticker.objects
                    .filter(ticker__in=tickers)
                    .values_list('ticker', 'market__t_close')
                )
                tclose_map = {tkr: tc for tkr, tc in tclose_qs}
            else:
                tclose_map = {}

            def _trading_day_row(row):
                ts = row['_dt_eastern']
                tkr = row['t']
                d0 = ts.date()
                if ts.weekday() >= 5:
                    return next_business_day(d0)
                t_close = tclose_map.get(tkr)
                cutoff_time = t_close if t_close is not None else time(18, 0)
                cutoff_local = pd.Timestamp(datetime.combine(d0, cutoff_time), tz='America/New_York')
                return d0 if ts <= cutoff_local else next_business_day(d0)

            df['d'] = df.apply(_trading_day_row, axis=1)
            dff = df[df['d'] == d].copy()

            # Add a full date-time column for display (use Eastern to align with trading day)
            dff['time'] = dff['_dt_eastern'].dt.strftime('%Y-%m-%d %H:%M:%S')

            # Order by time
            dff.sort_values('dt', inplace=True)

            # Select and rename columns for display
            show = dff[['time', 'a', 't', 'q', 'p', 'c', 'r']]
            show.columns = ['time', 'a', 't', 'q', 'p', 'commission', 'reinvest']

            def formatter(time, a, t, q, p, commission, reinvest):
                return time, a, t, q, p, commission, ('Y' if bool(reinvest) else '')

            context['h'], context['data'], context['formats'] = df_to_jqtable(df=show, formatter=formatter)
            context['headings'] = nice_headings(context['h'])

            # --- Prices (prev close and close) for tickers traded this day ---
            tickers = sorted(set(dff['t'].dropna().tolist()))
            if tickers:
                prev_d = prior_business_day(d)
                # Fetch price rows for both dates
                price_qs = (
                    DailyPrice.objects
                    .filter(ticker__ticker__in=tickers, d__in=[prev_d, d])
                    .values_list('ticker__ticker', 'd', 'c')
                )
                prices = pd.DataFrame.from_records(list(price_qs), columns=['t', 'd', 'close']) if price_qs else pd.DataFrame(columns=['t','d','close'])

                # Handle cash tickers (no bars) using fixed_price or 1.0
                tkr_meta = Ticker.objects.filter(ticker__in=tickers).values_list('ticker', 'market__symbol', 'fixed_price')
                if tkr_meta:
                    meta_df = pd.DataFrame.from_records(list(tkr_meta), columns=['t','symbol','fixed_price'])
                    cash_tickers = meta_df[meta_df['symbol'].str.lower() == 'cash']['t'].tolist() if not meta_df.empty else []
                    if cash_tickers:
                        rows = []
                        for row in meta_df.itertuples(index=False):
                            if row.symbol and row.symbol.lower() == 'cash':
                                fp = 1.0 if pd.isna(row.fixed_price) else float(row.fixed_price)
                                rows.append([row.t, prev_d, fp])
                                rows.append([row.t, d, fp])
                        cash_df = pd.DataFrame(rows, columns=['t','d','close'])
                        prices = cash_df if prices.empty else pd.concat([prices, cash_df], ignore_index=True)

                if not prices.empty:
                    # Pivot to prev_close and close columns per ticker
                    prev_df = prices[prices['d'] == prev_d][['t','close']].rename(columns={'close':'prev_close'})
                    cur_df = prices[prices['d'] == d][['t','close']].rename(columns={'close':'close'})
                    px = pd.merge(prev_df, cur_df, on='t', how='outer').sort_values('t')

                    def px_formatter(t, prev_close, close):
                        prev_fmt = '' if pd.isna(prev_close) else cround(float(prev_close))
                        cur_fmt = '' if pd.isna(close) else cround(float(close))
                        return t, prev_fmt, cur_fmt

                    context['prices_h'], context['prices_data'], context['prices_formats'] = (
                        df_to_jqtable(df=px[['t','prev_close','close']], formatter=px_formatter)
                    )
                    context['prices_headings'] = nice_headings(context['prices_h'])
                else:
                    context['prices_headings'] = nice_headings(['ticker', 'prev_close', 'close'])
                    context['prices_h'] = ['ticker', 'prev_close', 'close']
                    context['prices_data'] = []
                    context['prices_formats'] = '{}'
            else:
                context['prices_headings'] = nice_headings(['ticker', 'prev_close', 'close'])
                context['prices_h'] = ['ticker', 'prev_close', 'close']
                context['prices_data'] = []
                context['prices_formats'] = '{}'

            # --- Opening positions at start of the selected day ---
            # Compute cumulative position for all prior trading days for tickers traded that day
            tickers_today = sorted(set(dff['t'].dropna().tolist()))
            if tickers_today:
                df_before = df[df['d'] < d]
                if not df_before.empty:
                    # Net position per ticker at day open (sum of quantities)
                    pos_open = (
                        df_before[df_before['t'].isin(tickers_today)]
                        .groupby(['a', 't'], as_index=False)['q']
                        .sum()
                    )
                    # If account filter provided, grouping still includes it; select only active account row
                    if account:
                        pos_open = pos_open[pos_open['a'] == account]
                    pos_open = pos_open[['t', 'q']].rename(columns={'t': 'ticker', 'q': 'open_pos'})

                    def pos_fmt(ticker, open_pos):
                        try:
                            return ticker, int(round(float(open_pos)))
                        except Exception:
                            return ticker, open_pos

                    context['openpos_h'], context['openpos_data'], context['openpos_formats'] = (
                        df_to_jqtable(df=pos_open[['ticker', 'open_pos']], formatter=pos_fmt)
                    )
                    context['openpos_headings'] = nice_headings(context['openpos_h'])
                else:
                    context['openpos_headings'] = nice_headings(['ticker', 'open_pos'])
                    context['openpos_h'] = ['ticker', 'open_pos']
                    context['openpos_data'] = []
                    context['openpos_formats'] = '{}'
            else:
                context['openpos_headings'] = nice_headings(['ticker', 'open_pos'])
                context['openpos_h'] = ['ticker', 'open_pos']
                context['openpos_data'] = []
                context['openpos_formats'] = '{}'

        context['title'] = 'Trades for Day'
        context['selected_account'] = account or ''
        context['selected_date'] = d.strftime('%Y-%m-%d')
        context['daily_pnl_url'] = reverse('analytics:daily_pnl')

        # --- Cash transactions for the day ---
        cash_qs = CashRecord.objects.filter(ignored=False, d=d)
        if account:
            cash_qs = cash_qs.filter(account__name=account)

        if cash_qs.exists():
            # Build rows
            rows = []
            for rec in cash_qs.select_related('account').order_by('id'):
                rows.append([
                    rec.d.strftime('%Y-%m-%d'),
                    rec.account.name,
                    getattr(rec, 'get_category_display', lambda: rec.category)(),
                    rec.description,
                    float(rec.amt),
                    'Y' if rec.cleared_f else ''
                ])

            headings = ['date', 'a', 'category', 'description', 'amt', 'cleared']

            def cash_formatter(date_s, a, category, description, amt, cleared):
                return date_s, a, category, description, cround(amt), cleared

            df_cash = pd.DataFrame(rows, columns=headings)
            context['cash_h'], context['cash_data'], context['cash_formats'] = (
                df_to_jqtable(df=df_cash, formatter=cash_formatter)
            )
            context['cash_headings'] = nice_headings(context['cash_h'])
            context['cash_total'] = cround(df_cash['amt'].sum())
        else:
            headings = ['date', 'a', 'category', 'description', 'amt', 'cleared']
            context['cash_headings'] = nice_headings(headings)
            context['cash_h'] = headings
            context['cash_data'] = []
            context['cash_formats'] = '{}'
            context['cash_total'] = cround(0.0)

        return context


class IncomeExpenseView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/income_expense.html'

    def get_context_data(self, **kwargs):

        def formatter(a, b, c=None):
            if c is None:
                return a, cround(b)
            else:
                return a, b, cround(c)

        messages.get_messages(self.request).used = True

        context = super().get_context_data(**kwargs)

        year = self.request.GET.get('year')
        if year is None:
            messages.info(self.request, 'You can set the year.  ex: ?year=2022')
            year = date.today().year
        else:
            year = int(year)

        expense_df, expense_fmt = expenses(year)
        income_df, income_fmt = income(year)

        total_expenses = expense_df['amt'].iloc[-1]
        total_income = income_df['amt'].iloc[-1]
        net_profit = total_income - total_expenses

        context['e_h'], context['expense'], _ = (
            df_to_jqtable(df=expense_df, formatter=formatter))
        context["e_f"] = expense_fmt

        context['i_h'], context['income'], _ = (
            df_to_jqtable(df=income_df, formatter=formatter))
        context["i_f"] = income_fmt

        # Expose totals to the template
        context['total_income'] = net_profit + total_expenses
        context['total_expenses'] = total_expenses
        context['net_profit'] = net_profit

        context['title'] = f'Income/Expense ({year})'
        context["incomecsvurl"] = reverse('analytics:incomecsv', args=[year])
        context["expensecsvurl"] = reverse('analytics:expensescsv', args=[year])
        return context


def income_csv_view(request, param=None):
    if param is None:
        year = date.today().year
    else:
        year = int(param)

    result, formats = income(year)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="income.csv"'

    result = result.round(decimals=2)
    result.to_csv(path_or_buf=response, index=False)

    return response


def expenses_csv_view(request, param=None):
    if param is None:
        year = date.today().year
    else:
        year = int(param)

    result, formats = expenses(year)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expenses.csv"'

    result.to_csv(path_or_buf=response, index=False)

    return response


class TickerChartView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/ticker_chart.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticker_symbol = context['ticker']
        ticker = Ticker.objects.get(ticker=ticker_symbol)

        # Get historical prices from database
        historical_prices = DailyPrice.objects.filter(
            ticker=ticker).order_by('d')

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
        fig = go.Figure(data=go.Scatter(
            x=dates,
            y=prices,
            mode='lines+markers',
            name=f'{ticker_symbol} Price',
            opacity=0.8,
            marker_color='blue'
        ))

        fig.update_layout({
            'title_text': f'Price History for {ticker_symbol}',
            'yaxis_title': 'Price ($)',
            'xaxis_title': 'Date'
        })

        context['plot_div'] = plot({'data': fig}, output_type='div')
        context['ticker'] = ticker_symbol
        context['title'] = f'Price Chart for {ticker_symbol}'

        return context


class PerformanceView(LoginRequiredMixin, TemplateView):
    template_name = 'analytics/table.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['headings1'], context['data1'], context['formats'] = \
            performance()
        context['title'] = 'Performance'
        return context
