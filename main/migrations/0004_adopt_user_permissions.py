from django.db import migrations


def adopt_permissions(apps, schema_editor):
    """Retain old direct/group user-admin grants when the app label changes."""
    alias = schema_editor.connection.alias
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    User = apps.get_model('main', 'User')
    Group = apps.get_model('auth', 'Group')
    old_type = ContentType.objects.using(alias).filter(app_label='auth', model='user').first()
    if not old_type:
        return
    new_type, _ = ContentType.objects.using(alias).get_or_create(app_label='main', model='user')
    LogEntry = apps.get_model('admin', 'LogEntry')
    LogEntry.objects.using(alias).filter(content_type=old_type).update(content_type=new_type)
    for old_permission in Permission.objects.using(alias).filter(content_type=old_type):
        new_permission, _ = Permission.objects.using(alias).get_or_create(
            content_type=new_type, codename=old_permission.codename,
            defaults={'name': old_permission.name},
        )
        for model, owner_field in [(User.user_permissions.through, 'user_id'), (Group.permissions.through, 'group_id')]:
            owners = model.objects.using(alias).filter(permission_id=old_permission.pk).values_list(owner_field, flat=True)
            model.objects.using(alias).bulk_create(
                [model(**{owner_field: owner, 'permission_id': new_permission.pk}) for owner in owners],
                ignore_conflicts=True,
            )


class Migration(migrations.Migration):
    dependencies = [('main', '0003_auththrottle'), ('admin', '0003_logentry_add_action_flag_choices')]
    operations = [migrations.RunPython(adopt_permissions, migrations.RunPython.noop)]
