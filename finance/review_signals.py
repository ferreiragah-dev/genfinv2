"""Keep reconciliation reversible when a source record changes or disappears."""

from django.db.models import Q
from django.db.models.signals import post_delete, pre_save
from django.dispatch import receiver

from .models import ReviewDismissal, ReviewPair, Transaction


@receiver(post_delete, sender=ReviewPair)
def restore_pair_members(sender, instance, **kwargs):
    for pk in (instance.first_id, instance.second_id):
        pairs = ReviewPair.objects.filter(Q(first_id=pk) | Q(second_id=pk))
        role = (
            "transfer"
            if pairs.filter(kind="transfer").exists()
            else "duplicate"
            if pairs.filter(kind="duplicate", first_id=pk).exists()
            else "normal"
        )
        Transaction.objects.filter(pk=pk).update(review_role=role, reviewed_at=None)


@receiver(pre_save, sender=Transaction)
def invalidate_changed_review(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    fields = ("amount", "kind", "date", "status", "account", "bank_account_id", "description")
    previous = Transaction.objects.filter(pk=instance.pk).values(*fields).first()
    if previous and any(previous[field] != getattr(instance, field) for field in fields):
        related = Q(first_id=instance.pk) | Q(second_id=instance.pk)
        ReviewPair.objects.filter(related).delete()
        ReviewDismissal.objects.filter(related).delete()
        Transaction.objects.filter(pk=instance.pk).update(review_role="normal", reviewed_at=None)
        instance.review_role = "normal"
        instance.reviewed_at = None
