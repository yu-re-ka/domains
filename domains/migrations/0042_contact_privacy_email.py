# Generated by Django 2.2.17 on 2021-01-31 17:02

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('domains', '0041_domainregistration_deleted_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='contact',
            name='privacy_email',
            field=models.UUIDField(default=uuid.uuid4),
        ),
    ]
