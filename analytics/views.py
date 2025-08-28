from datetime import datetime, date, timedelta

from plotly.offline import plot
import plotly.graph_objs as go

from django.http import HttpResponse
from django.views.generic import TemplateView, FormView
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from analytics.cash import cash_sums
from analytics.pnl import pnl_summary, pnl_if_closed, ticker_pnl
from analytics.utils import total_realized_gains, income, expenses
from analytics.models import PPMResult
from analytics.forms import PnLForm, CheckingForm
from trades.ib_flex import get_trades
from trades.utils import weighted_average_price
from tbgutils.dt import lbd_prior_month, our_now, prior_business_day
from tbgutils.str import is_near_zero, cround
from accounts.models import Account
from markets.tbgyahoo import yahoo_url
from markets.models import Ticker
from worth.utils import df_to_jqtable, nice_headings

from markets.utils import get_price, ticker_admin_url
from markets.models import DailyPrice


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
        if account is None:
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

        context['e_h'], context['expense'], _ = (
            df_to_jqtable(df=expense_df, formatter=formatter))
        context["e_f"] = expense_fmt

        context['i_h'], context['income'], _ = (
            df_to_jqtable(df=income_df, formatter=formatter))
        context["i_f"] = income_fmt

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
