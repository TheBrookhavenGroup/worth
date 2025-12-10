from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0021_alter_cashrecord_category"),
    ]

    operations = [
        migrations.CreateModel(
            name="TradeSize",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("d", models.DateField()),
                ("size", models.FloatField()),
                (
                    "a",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="accounts.account",
                    ),
                ),
            ],
            options={
                "unique_together": {("a", "d")},
            },
        ),
    ]
