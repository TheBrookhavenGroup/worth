from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.shortcuts import get_object_or_404

from .models import Ticker


@require_GET
def api_t_close(request):
    """Return Market.t_close for a given ticker.

    Accepts either ?ticker_id=<pk> or ?ticker=<symbol>
    Response: {"t_close": "HH:MM"}
    """
    ticker_id = request.GET.get('ticker_id')
    ticker_symbol = request.GET.get('ticker')

    if ticker_id:
        ticker = get_object_or_404(Ticker, pk=ticker_id)
    elif ticker_symbol:
        ticker = get_object_or_404(Ticker, ticker=ticker_symbol)
    else:
        return JsonResponse({"error": "Missing ticker_id or ticker"}, status=400)

    t = ticker.market.t_close
    hhmm = t.strftime('%H:%M') if hasattr(t, 'strftime') else str(t)
    return JsonResponse({"t_close": hhmm})
