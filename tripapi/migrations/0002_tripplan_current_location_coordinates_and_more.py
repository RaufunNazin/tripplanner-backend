# Generated by Django 5.1.7 on 2025-03-16 07:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tripapi', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='tripplan',
            name='current_location_coordinates',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tripplan',
            name='dropoff_location_coordinates',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='tripplan',
            name='pickup_location_coordinates',
            field=models.JSONField(blank=True, null=True),
        ),
    ]
