# Generated by Django 4.2.2 on 2023-06-15 08:41

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domains', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='domain',
            name='user_extra_attrs',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name='domain',
            name='user_object_classes',
            field=models.CharField(blank=True, max_length=255),
        ),
    ]
