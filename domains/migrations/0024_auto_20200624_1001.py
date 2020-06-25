# Generated by Django 3.0.7 on 2020-06-24 10:01

from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('domains', '0023_auto_20200607_1111'),
    ]

    operations = [
        migrations.CreateModel(
            name='HangoutsSpaces',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('space_id', models.CharField(max_length=255)),
            ],
        ),
        migrations.AddField(
            model_name='domainregistration',
            name='deleted',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]