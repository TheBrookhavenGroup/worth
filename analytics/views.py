from django.views.generic.base import TemplateView

class CheckingView(TemplateView):
    template_name = 'analytics/checking.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['account'] = 'BofA'
        return context
