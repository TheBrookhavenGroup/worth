from django.core.management.base import BaseCommand
from analytics.pnl import year_pnl
from trades.ib_flex import get_trades


class Command(BaseCommand):
    help = 'Run PPM and store results in database.'

    def handle(self, *args, **options):
        x = get_trades()
        for i in x[1]:
            print(i)
        x = year_pnl()
        print(next(i for i in x[1] if i[0] == 'ALL')[4])
