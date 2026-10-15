from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0024_alter_cashrecord_category"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashrecord",
            name="category",
            field=models.CharField(
                choices=[
                    ("BF", "Bank fee"),
                    ("BNK", "Bank Check"),
                    ("BH", "Baltimore House"),
                    ("CH", "Charity"),
                    ("DE", "Deposits"),
                    ("DV", "Dividend"),
                    ("ED", "Education/Lessons/Tutoring"),
                    ("FC", "Food & Clothing"),
                    ("GN", "General"),
                    ("HO", "House"),
                    ("IN", "Insurance"),
                    ("OL", "TBG Officers Loan"),
                    ("SA", "Savings"),
                    ("TR", "Transfer"),
                    ("TA", "Taxes and Accounting"),
                    ("UT", "Utilities"),
                    ("VA", "Vacation"),
                    ("IT", "Interest"),
                ],
                default="GN",
                max_length=3,
            ),
        ),
    ]
