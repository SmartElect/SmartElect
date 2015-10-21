import logging

from django.conf import settings
from django.core.mail import send_mass_mail
from django.template.loader import render_to_string

from .models import Subscription

logger = logging.getLogger(__name__)


def send_notifications(subscription_type, **kwargs):
    logger.debug("sending notification for {0}".format(subscription_type))
    context = kwargs or {}
    context.update({
        'domain': settings.SITE_DOMAIN,
        'env': settings.ENVIRONMENT
    })
    subscribers = Subscription.objects.filter(subscription_type=subscription_type)
    subject = render_to_string('subscriptions/email_subject.txt', context).strip()
    body = render_to_string('subscriptions/email_body.txt', context).strip()
    messages = [(subject, body, settings.DEFAULT_FROM_EMAIL,
                 [subscriber.user.email]) for subscriber in subscribers]
    send_mass_mail(messages, fail_silently=True)
