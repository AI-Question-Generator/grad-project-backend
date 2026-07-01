from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('curriculum', '0004_alter_sourcefile_options_alter_sourcefile_file_hash_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sourcefile',
            name='file_hash',
            field=models.CharField(max_length=255),
        ),
        migrations.RemoveIndex(
            model_name='sourcefile',
            name='curriculum__owner_i_61839b_idx',
        ),
        migrations.AddConstraint(
            model_name='sourcefile',
            constraint=models.UniqueConstraint(fields=('owner', 'file_hash'), name='unique_owner_file_hash'),
        ),
    ]
