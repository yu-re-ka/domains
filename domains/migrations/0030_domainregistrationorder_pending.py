# Generated by Django 3.0.7 on 2020-07-10 18:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domains', '0029_auto_20200710_1825'),
    ]

    operations = [
        migrations.AddField(
            model_name='domainregistrationorder',
            name='pending',
            field=models.BooleanField(blank=True, default=True),
        ),
    ]