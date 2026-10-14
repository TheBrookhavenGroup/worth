from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0023_receivable_account"),
    ]

    operations = [
        migrations.AlterField(
            model_name="cashrecord",
            name="category",
            field=models.CharField(
                choices=[
                    ("AB", "Avi Bar Mitzvah"),
                    ("AV", "Deposit to Avi account"),
                    ("BF", "Bank fee"),
                    ("BNK", "Bank Check"),
                    ("BM", "Bar Mitzvah"),
                    ("BH", "Baltimore House"),
                    ("CH", "Charity"),
                    ("CE", "College Expenses"),
                    ("DE", "Deposits"),
                    ("DV", "Dividend"),
                    ("ED", "Education/Lessons/Tutoring"),
                    ("FC", "Food & Clothing"),
                    ("GN", "General"),
                    ("HO", "House"),
                    ("HS", "Health Savings Account"),
                    ("IN", "Insurance"),
                    ("MD", "Medical"),
                    ("OL", "TBG Officers Loan"),
                    ("PR", "Professional"),
                    ("SA", "Savings"),
                    ("TR", "Transfer"),
                    ("SB", "Sailboat"),
                    ("TA", "Taxes and Accounting"),
                    ("UT", "Utilities"),
                    ("VA", "Vacation"),
                    ("WA", "Wages from tutoring"),
                    ("GB", "Gila Bat Mitzvah"),
                    ("IT", "Interest"),
                    ("GU", "Gila UTMA"),
                ],
                default="GN",
                max_length=3,
            ),
        ),
    ]
