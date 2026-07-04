from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0006_project_ai_setup_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='lesson',
            name='order',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='lesson',
            name='section',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='lesson',
            name='unit_number',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterModelOptions(
            name='lesson',
            options={'ordering': ['unit_number', 'section', 'order']},
        ),
    ]
