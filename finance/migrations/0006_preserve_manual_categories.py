from django.db import migrations
from django.utils import timezone


def preserve_manual_categories(apps, schema_editor):
    apps.get_model("finance", "Transaction").objects.filter(pluggy_id__isnull=True).update(
        category_locked=True, reviewed_at=timezone.now()
    )


class Migration(migrations.Migration):
    dependencies = [
        ("finance", "0005_transaction_category_locked_transaction_review_role_and_more")
    ]
    operations = [migrations.RunPython(preserve_manual_categories, migrations.RunPython.noop)]
