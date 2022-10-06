# Generated by Django 4.0.2 on 2022-10-06 21:04

from django.db import migrations, models
import ipatuura.models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='User',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('password', models.CharField(max_length=128, verbose_name='password')),
                ('last_login', models.DateTimeField(blank=True, null=True, verbose_name='last login')),
                ('scim_id', models.CharField(blank=True, default=None, help_text='A unique identifier for a SCIM resource as defined by the service provider.', max_length=254, null=True, unique=True, verbose_name='SCIM ID')),
                ('scim_external_id', models.CharField(blank=True, db_index=True, default=None, help_text='A string that is an identifier for the resource as defined by the provisioning client.', max_length=254, null=True, verbose_name='SCIM External ID')),
                ('scim_username', models.CharField(blank=True, default=None, help_text="A service provider's unique identifier for the user", max_length=254, null=True, unique=True, verbose_name='SCIM Username')),
                ('first_name', models.CharField(max_length=100, verbose_name='First Name')),
                ('last_name', models.CharField(max_length=100, verbose_name='Last Name')),
                ('email', models.EmailField(max_length=254, verbose_name='Email')),
                ('is_staff', models.BooleanField(default=False, help_text='Whether the user can log into this admin site', verbose_name='staff status')),
            ],
            options={
                'abstract': False,
            },
            managers=[
                ('objects', ipatuura.models.CustomUserManager()),
            ],
        ),
        migrations.CreateModel(
            name='Group',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scim_id', models.CharField(blank=True, default=None, help_text='A unique identifier for a SCIM resource as defined by the service provider.', max_length=254, null=True, unique=True, verbose_name='SCIM ID')),
                ('scim_external_id', models.CharField(blank=True, db_index=True, default=None, help_text='A string that is an identifier for the resource as defined by the provisioning client.', max_length=254, null=True, verbose_name='SCIM External ID')),
                ('scim_display_name', models.CharField(blank=True, db_index=True, default=None, help_text='A human-readable name for the Group.', max_length=254, null=True, verbose_name='SCIM Display Name')),
            ],
            options={
                'abstract': False,
            },
            managers=[
                ('objects', ipatuura.models.CustomGroupManager()),
            ],
        ),
    ]
