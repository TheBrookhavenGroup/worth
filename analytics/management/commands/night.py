from django.core.management.base import BaseCommand
from analytics.pnl import pnl
from trades.ib_flex import get_trades


# This is a zsh function to run this command.
# worth_night() {
#     echo "source $HOME/.zshrc; pyenv shell worth; python $HOME/Documents/dev/worth/manage.py night" | zsh
# }


class Command(BaseCommand):
    help = 'Run PPM and store results in database.'

    def handle(self, *args, **options):
        x = get_trades()
        for i in x[1]:
            print(i)
        df, total, total_today = pnl()
        df = df[df.Account == 'TOTAL']
        print(df.to_string())
