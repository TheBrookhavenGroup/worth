# Generated by Django 4.1.3 on 2023-03-06 21:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0011_remove_receivable_description_receivable_client_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='receivable',
            name='received',
            field=models.DateField(blank=True),
        ),
    ]
