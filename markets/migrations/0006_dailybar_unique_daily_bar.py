# Generated by Django 3.2.8 on 2022-02-28 19:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0005_auto_20220228_1408'),
    ]

    operations = [
        migrations.AddConstraint(
            model_name='dailybar',
            constraint=models.UniqueConstraint(fields=('ticker', 'd'), name='unique_daily_bar'),
        ),
    ]
