from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Schedule


@receiver(post_delete, sender=Schedule)
def drop_beat_entry(sender, instance, **kwargs):
    from . import beat
    beat.remove(instance.user_id)
