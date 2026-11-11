import accounts.models
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0025_alter_cashrecord_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="expense",
            name="account",
            field=models.ForeignKey(
                default=accounts.models.get_tbgm_account_id,
                on_delete=django.db.models.deletion.CASCADE,
                to="accounts.account",
            ),
        ),
    ]
