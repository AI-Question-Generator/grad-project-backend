from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0005_sourcefile_unique_owner_hash'),
    ]

    operations = [
        migrations.AddField(
            model_name='project',
            name='ai_setup_completed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='project',
            name='ai_setup_feedback',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='project',
            name='ai_setup_started_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='project',
            name='ai_setup_status',
            field=models.CharField(
                choices=[
                    ('PENDING', 'Pending'),
                    ('PROCESSING', 'Processing'),
                    ('COMPLETED', 'Completed'),
                    ('COMPLETED_WITH_ERRORS', 'Completed with errors'),
                    ('FAILED', 'Failed'),
                ],
                default='PENDING',
                max_length=30,
            ),
        ),
    ]