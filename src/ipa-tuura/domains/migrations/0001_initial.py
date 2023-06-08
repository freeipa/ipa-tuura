# Generated by Django 4.1.5 on 2023-02-07 09:07

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Domain',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=80)),
                ('integration_domain_url', models.CharField(max_length=255)),
                ('client_id', models.CharField(max_length=20)),
                ('client_secret', models.CharField(max_length=20)),
                ('description', models.TextField(blank=True)),
                ('id_provider', models.CharField(choices=[('ipa', 'IPA Provider'), ('ad', 'LDAP Active Directory Provider'), ('ldap', 'LDAP Provider')], default='ipa', max_length=5)),
                ('user_extra_attrs', models.CharField(max_length=255)),
                ('user_object_classes', models.CharField(max_length=255)),
                ('users_dn', models.CharField(max_length=255)),
                ('ldap_tls_cacert', models.CharField(max_length=100)),
            ],
        ),
    ]
