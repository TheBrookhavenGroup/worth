# Generated by Django 3.2.8 on 2022-04-10 19:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('markets', '0010_auto_20220304_1015'),
    ]

    operations = [
        migrations.AddField(
            model_name='market',
            name='vprec',
            field=models.IntegerField(default=0),
        ),
    ]
