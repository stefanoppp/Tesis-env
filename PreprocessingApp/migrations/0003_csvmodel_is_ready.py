# Generated by Django 5.2 on 2025-05-29 21:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('PreprocessingApp', '0002_remove_csvmodel_is_ready_csvmodel_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='csvmodel',
            name='is_ready',
            field=models.BooleanField(default=False),
        ),
    ]
