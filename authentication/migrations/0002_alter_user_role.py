from django.db import migrations, models


def migrate_roles_forward(apps, schema_editor):
    User = apps.get_model('authentication', 'User')
    User.objects.filter(role__in=['teacher', 'student']).update(role='member')


def migrate_roles_backward(apps, schema_editor):
    User = apps.get_model('authentication', 'User')
    User.objects.filter(role='member').update(role='student')


class Migration(migrations.Migration):

    dependencies = [
        ('authentication', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='role',
            field=models.CharField(
                choices=[('admin', 'Admin'), ('member', 'Member')],
                default='member',
                max_length=20,
            ),
        ),
        migrations.RunPython(migrate_roles_forward, migrate_roles_backward),
    ]
