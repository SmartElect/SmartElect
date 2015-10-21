import datetime
import logging
import os

from celery.task import task

from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.timezone import now

from libya_elections.constants import REMINDER_CHECKIN, REMINDER_REPORT, \
    REMINDER_LAST_REPORT, REMINDER_CLOSE
from libya_elections.csv_utils import UnicodeReader
from polling_reports.models import CenterOpen, PollingReport, StaffPhone
from register.models import Whitelist
from text_messages.utils import get_message

from .models import Batch, Broadcast
from .utils import Line


logger = logging.getLogger(__name__)


def read_messages_from_file(file_path):
    """
    Read uploaded bulk SMS file.
    Generate tuples: (phone_number, message, from_shortcode).
    Delete file afterward.
    :param file_path:
    :return:
    """
    # We don't currently enable customization of the from_shortcode via file upload.
    # Just use the default.
    from_shortcode = None
    with open(file_path, "rb") as f:
        reader = UnicodeReader(f)
        for row in reader:
            if any(row):
                line = Line._make(row)
                number = int(line.number)
                yield number, line.message, from_shortcode
    os.remove(file_path)


@task
def upload_bulk_sms_file(batch_id, file_path):
    """
    Upload a batch of bulk SMS messages for the given batch. Delete
    the temp file after we're done.

    Assumes the file is valid (run is_file_valid on it first!)

    :param batch_id:
    :param _file:
    :return: message_for_user
    """
    batch = Batch.objects.get(id=batch_id)
    batch.add_messages(read_messages_from_file(file_path))
    batch.status = Batch.PENDING
    batch.save()


# Break out some of the logic for sending polling report reminder messages
# for easier testing
class PollingReportReminderMessage(object):
    """
    Capture some of the common logic for polling report reminders.

    (Do not instantiate, use the subclasses.)
    """
    def __init__(self, message_number, reminder_number):
        self.message_number = message_number
        self.reminder_number = reminder_number

    def get_message_code(self):
        raise NotImplementedError

    def get_message_text(self):
        context = {'message_number': self.message_number,
                   'reminder_number': self.reminder_number}
        return get_message(self.get_message_code()).msg.format(**context)

    def get_phone_numbers_to_send_to(self):
        """
        Generator that yields (phone_number, message_text, from_shortcode) tuples
        for the phone numbers that we need to send this reminder to.
        """
        # Get the phone numbers we want to send to, excluding those that have
        # already done the thing we want to remind them of
        phone_numbers = self.PhoneModel.objects.exclude(phone_number__in=self.to_exclude())\
                                               .values_list('phone_number', flat=True)

        message_text = self.get_message_text()
        # Set from_number to REPORTS_SHORT_CODE so that recipient can
        # simply just respond to this message with their report.
        from_shortcode = settings.REPORTS_SHORT_CODE
        for phone_number in phone_numbers:
            yield phone_number, message_text, from_shortcode

    def to_exclude(self):
        raise NotImplementedError


class CheckinReminderMessage(PollingReportReminderMessage):
    """
    Message telling user to check in (activate phone, roll call)
    """
    def __init__(self, message_number, reminder_number):
        super(CheckinReminderMessage, self).__init__(message_number, reminder_number)
        self.PhoneModel = Whitelist

    def get_message_code(self):
        return REMINDER_CHECKIN

    def to_exclude(self):
        """Return list of phone numbers to exclude"""
        midnight = now().replace(hour=0, minute=0, microsecond=0)
        return CenterOpen.objects.filter(
            creation_date__gte=midnight,
        ).values_list('phone_number', flat=True)


class PollingDayReportReminderMessage(PollingReportReminderMessage):
    """
    Message telling user to send in polling day statistics report
    """
    def __init__(self, message_number, reminder_number):
        super(PollingDayReportReminderMessage, self).__init__(message_number, reminder_number)
        self.PhoneModel = StaffPhone

    def get_message_code(self):
        return {
            4: REMINDER_REPORT,
            5: REMINDER_REPORT,
            6: REMINDER_LAST_REPORT,
            7: REMINDER_CLOSE,
        }[self.message_number]

    def to_exclude(self):
        """Return list of phone numbers to exclude"""
        reporting_period = self.message_number - 3
        one_day_ago = now() - datetime.timedelta(hours=24)

        return PollingReport.objects.filter(
            period_number=reporting_period,
            creation_date__gte=one_day_ago,
        ).values_list('phone_number', flat=True)


@task
def message_reminder_task(message_number, reminder_number, audience, election):
    """
    Make a batch to send out a bunch of reminder messages to a given audience,
    iffi they haven't sent us the expected report yet.
    """
    logger.debug("Start message_reminder_task")

    if audience not in ('whitelist', 'registered'):
        raise ValueError("Unknown audience type %s - expected whitelist or registered" % audience)

    # Batches need to be owned by somebody - pick a non-random superuser
    user = get_user_model().objects.filter(is_active=True, is_superuser=True)[0]

    batch = Batch.objects.create(
        name="Reminder %d for message_number %d" % (reminder_number, message_number),
        created_by=user,
        priority=Batch.PRIORITY_TIME_CRITICAL)
    # create the corresponding broadcast object
    broadcast = Broadcast.objects.create(
        created_by=batch.created_by,
        batch=batch,
        audience=Broadcast.STAFF_ONLY,
        message=batch.name,  # this message is only temporary
    )

    try:
        if audience == 'whitelist':
            msg = CheckinReminderMessage(message_number, reminder_number)
        else:
            msg = PollingDayReportReminderMessage(message_number, reminder_number)

        batch.add_messages(msg.get_phone_numbers_to_send_to())

        batch.status = Batch.APPROVED
        batch.reviewed_by = user
        batch.save()
        # update the message for the broadcast.
        broadcast.message = msg.get_message_text()
        broadcast.save()
        logger.debug("Batch saved")
    except:
        logger.exception("Error while creating message reminder batch")
        # If anything went wrong, don't leave partial batch lying around in unknown state
        batch.delete()
        broadcast.delete()
        raise


@task
def approve_broadcast(broadcast_id):
    """Creates messages for each individual in the audience and
    changes batch status to approved."""
    broadcast = Broadcast.objects.get(pk=broadcast_id)
    messages = broadcast.get_messages()
    batch = broadcast.batch
    batch.add_messages(messages)
    batch.status = Batch.APPROVED
    batch.save()
