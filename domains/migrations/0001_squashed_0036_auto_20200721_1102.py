# Generated by Django 3.0.7 on 2020-08-09 20:05

import datetime
from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import django_countries.fields
import domains.models
import phonenumber_field.modelfields
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ContactAddress',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('description', models.CharField(max_length=255)),
                ('name', models.CharField(max_length=255, validators=[django.core.validators.MinLengthValidator(4)])),
                ('organisation', models.CharField(blank=True, max_length=255, null=True)),
                ('street_1', models.CharField(max_length=255, verbose_name='Address line 1')),
                ('street_2', models.CharField(blank=True, max_length=255, null=True, verbose_name='Address line 2')),
                ('street_3', models.CharField(blank=True, max_length=255, null=True, verbose_name='Address line 3')),
                ('city', models.CharField(max_length=255)),
                ('province', models.CharField(blank=True, max_length=255, null=True)),
                ('postal_code', models.CharField(max_length=255, null=True)),
                ('country_code', django_countries.fields.CountryField(max_length=2, verbose_name='Country')),
                ('birthday', models.DateField(blank=True, null=True)),
                ('identity_number', models.CharField(blank=True, max_length=255, null=True, verbose_name='National identity number')),
                ('disclose_address', models.BooleanField(blank=True, default=False)),
                ('disclose_name', models.BooleanField(blank=True, default=False)),
                ('disclose_organisation', models.BooleanField(blank=True, default=False)),
                ('resource_id', models.UUIDField(null=True)),
            ],
            options={
                'verbose_name_plural': 'Contact addresses',
                'ordering': ['description', 'name'],
            },
        ),
        migrations.CreateModel(
            name='Contact',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('company_number', models.CharField(blank=True, max_length=255, null=True)),
                ('created_date', models.DateTimeField(default=django.utils.timezone.now)),
                ('description', models.CharField(default='', max_length=255)),
                ('email', models.EmailField(default='', max_length=254)),
                ('entity_type', models.PositiveSmallIntegerField(choices=[(0, 'Not set'), (1, 'Unknown entity'), (2, 'UK Limited Company'), (3, 'UK Public Limited Company'), (4, 'UK Partnership'), (5, 'UK Sole Trader'), (6, 'UK Limited Liability Partnership'), (7, 'UK Industrial Provident Registered Company'), (8, 'UK Individual'), (9, 'UK School'), (10, 'UK Registered Charity'), (11, 'UK Government Body'), (12, 'UK Corporation by Royal Charter'), (13, 'UK Statutory Body'), (31, 'UK Political party'), (14, 'Other UK Entity'), (15, 'Finnish Individual'), (16, 'Finnish Company'), (17, 'Finnish Association'), (18, 'Finnish Institution'), (19, 'Finnish Political Party'), (20, 'Finnish Municipality'), (21, 'Finnish Government'), (22, 'Finnish Public Community'), (23, 'Other Individual'), (24, 'Other Company'), (25, 'Other Association'), (26, 'Other Institution'), (27, 'Other Political Party'), (28, 'Other Municipality'), (29, 'Other Government'), (30, 'Other Public Community')])),
                ('fax', phonenumber_field.modelfields.PhoneNumberField(blank=True, max_length=128, null=True, region=None)),
                ('fax_ext', models.CharField(blank=True, max_length=64, null=True, verbose_name='Fax extension')),
                ('phone', phonenumber_field.modelfields.PhoneNumberField(max_length=128, null=True, region=None)),
                ('phone_ext', models.CharField(blank=True, max_length=64, null=True, verbose_name='Phone extension')),
                ('trading_name', models.CharField(blank=True, max_length=255, null=True)),
                ('updated_date', models.DateTimeField(blank=True, null=True)),
                ('int_address', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='int_contacts', to='domains.ContactAddress', verbose_name='Internationalised address')),
                ('local_address', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='local_contacts', to='domains.ContactAddress', verbose_name='Localised address')),
                ('disclose_email', models.BooleanField(blank=True, default=False)),
                ('disclose_fax', models.BooleanField(blank=True, default=False)),
                ('disclose_phone', models.BooleanField(blank=True, default=False)),
                ('resource_id', models.UUIDField(null=True)),
            ],
            options={
                'ordering': ['description'],
            },
        ),
        migrations.CreateModel(
            name='ContactRegistry',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('registry_contact_id', models.CharField(default=domains.models.make_id, max_length=16)),
                ('registry_id', models.CharField(max_length=255)),
                ('auth_info', models.CharField(blank=True, max_length=255, null=True)),
                ('contact', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='domains.Contact')),
            ],
            options={
                'verbose_name_plural': 'Contact registries',
                'ordering': ['registry_contact_id'],
            },
        ),
        migrations.CreateModel(
            name='NameServer',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name_server', models.CharField(max_length=255)),
                ('registry_id', models.CharField(default='', max_length=255)),
                ('resource_id', models.UUIDField(null=True)),
            ],
            options={
                'ordering': ['name_server'],
            },
        ),
        migrations.CreateModel(
            name='HangoutsSpaces',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('space_id', models.CharField(max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='DomainRegistration',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain', models.CharField(max_length=255)),
                ('auth_info', models.CharField(blank=True, max_length=255, null=True)),
                ('admin_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domains_admin', to='domains.Contact')),
                ('billing_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domains_billing', to='domains.Contact')),
                ('pending', models.BooleanField(blank=True, default=False)),
                ('registrant_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domains_registrant', to='domains.Contact')),
                ('tech_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domains_tech', to='domains.Contact')),
                ('resource_id', models.UUIDField(null=True)),
                ('deleted', models.BooleanField(blank=True, default=False)),
                ('last_billed', models.DateTimeField(default=datetime.datetime(1, 1, 1, 0, 0))),
                ('last_renew_notify', models.DateTimeField(default=datetime.datetime(1, 1, 1, 0, 0))),
            ],
            options={
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='HangoutsUsers',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('user', models.CharField(max_length=255)),
                ('account', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='HangoutsUserLinkState',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('return_url', models.URLField(max_length=1000)),
                ('user', models.CharField(max_length=255)),
                ('linked', models.BooleanField(blank=True, default=False)),
                ('message_name', models.CharField(default='', max_length=255)),
            ],
        ),
        migrations.CreateModel(
            name='DomainRegistrationOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain', models.CharField(max_length=255)),
                ('period_unit', models.PositiveSmallIntegerField()),
                ('period_value', models.PositiveSmallIntegerField()),
                ('charge_state_id', models.CharField(blank=True, max_length=255, null=True)),
                ('admin_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_registration_orders_admin', to='domains.Contact')),
                ('billing_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_registration_orders_billing', to='domains.Contact')),
                ('registrant_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_registration_orders_registrant', to='domains.Contact')),
                ('tech_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_registration_orders_tech', to='domains.Contact')),
                ('domain_id', models.UUIDField(default=uuid.uuid4)),
                ('domain_obj', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='domains.DomainRegistration')),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('auth_info', models.CharField(default='', max_length=255)),
                ('last_error', models.TextField(blank=True, null=True)),
                ('redirect_uri', models.TextField(blank=True, null=True)),
                ('resource_id', models.UUIDField(null=True)),
                ('state', models.CharField(choices=[('P', 'Pending'), ('T', 'Started'), ('N', 'Needs payment'), ('S', 'Processing'), ('A', 'Pending approval'), ('C', 'Completed'), ('F', 'Failed')], default='P', max_length=1)),
            ],
            options={
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='DomainRenewOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('period_unit', models.PositiveSmallIntegerField()),
                ('period_value', models.PositiveSmallIntegerField()),
                ('charge_state_id', models.CharField(blank=True, max_length=255, null=True)),
                ('domain', models.CharField(max_length=255)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('domain_obj', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='domains.DomainRegistration')),
                ('last_error', models.TextField(blank=True, null=True)),
                ('redirect_uri', models.TextField(blank=True, null=True)),
                ('resource_id', models.UUIDField(null=True)),
                ('state', models.CharField(choices=[('P', 'Pending'), ('T', 'Started'), ('N', 'Needs payment'), ('S', 'Processing'), ('A', 'Pending approval'), ('C', 'Completed'), ('F', 'Failed')], default='P', max_length=1)),
            ],
            options={
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='DomainRestoreOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('charge_state_id', models.CharField(blank=True, max_length=255, null=True)),
                ('domain', models.CharField(max_length=255)),
                ('domain_obj', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='domains.DomainRegistration')),
                ('last_error', models.TextField(blank=True, null=True)),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('redirect_uri', models.TextField(blank=True, null=True)),
                ('resource_id', models.UUIDField(null=True)),
                ('state', models.CharField(choices=[('P', 'Pending'), ('T', 'Started'), ('N', 'Needs payment'), ('S', 'Processing'), ('A', 'Pending approval'), ('C', 'Completed'), ('F', 'Failed')], default='P', max_length=1)),
            ],
            options={
                'ordering': ['domain'],
            },
        ),
        migrations.CreateModel(
            name='DomainTransferOrder',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('domain', models.CharField(max_length=255)),
                ('domain_id', models.UUIDField(default=uuid.uuid4)),
                ('auth_code', models.CharField(max_length=255)),
                ('charge_state_id', models.CharField(blank=True, max_length=255, null=True)),
                ('admin_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_transfer_orders_admin', to='domains.Contact')),
                ('billing_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_transfer_orders_billing', to='domains.Contact')),
                ('domain_obj', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='domains.DomainRegistration')),
                ('registrant_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_transfer_orders_registrant', to='domains.Contact')),
                ('tech_contact', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='domain_transfer_orders_tech', to='domains.Contact')),
                ('price', models.DecimalField(decimal_places=2, default=0, max_digits=9)),
                ('last_error', models.TextField(blank=True, null=True)),
                ('redirect_uri', models.TextField(blank=True, null=True)),
                ('resource_id', models.UUIDField(null=True)),
                ('state', models.CharField(choices=[('P', 'Pending'), ('T', 'Started'), ('N', 'Needs payment'), ('S', 'Processing'), ('A', 'Pending approval'), ('C', 'Completed'), ('F', 'Failed')], default='P', max_length=1)),
            ],
            options={
                'ordering': ['domain'],
            },
        ),
    ]
