# Generated by Django 3.2.8 on 2022-03-04 15:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0008_tbgdailybar'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DailyBar',
            new_name='DailyPrice',
        ),
    ]
