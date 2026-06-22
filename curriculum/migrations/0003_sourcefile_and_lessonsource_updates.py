from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0002_add_is_default_to_project'),
    ]

    operations = [
        migrations.AddField(
            model_name='sourcefile',
            name='file',
            field=models.FileField(blank=True, null=True, upload_to='source_files/%Y/%m/'),
        ),
        migrations.AddField(
            model_name='sourcefile',
            name='file_size',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='sourcefile',
            name='page_count',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name='sourcefile',
            name='file_url',
            field=models.URLField(blank=True, max_length=1024),
        ),
        migrations.AddField(
            model_name='lessonsource',
            name='start_page',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AddField(
            model_name='lessonsource',
            name='end_page',
            field=models.PositiveIntegerField(default=1),
        ),
    ]
