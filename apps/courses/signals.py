from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.chat.services import ChatService
from apps.courses.models import Cohort, CohortMember, CourseDeliveryFormat


@receiver(post_save, sender=Cohort)
def create_cohort_chat(sender, instance: Cohort, **kwargs):
    ChatService.ensure_cohort_chat(instance)


@receiver(post_save, sender=CohortMember)
def sync_cohort_member_to_chat(sender, instance: CohortMember, **kwargs):
    ChatService.ensure_cohort_chat(instance.cohort)


@receiver(post_save, sender=CourseDeliveryFormat)
def create_delivery_format_chat(sender, instance: CourseDeliveryFormat, **kwargs):
    ChatService.ensure_delivery_format_chat(instance)
