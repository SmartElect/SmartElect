
import logging

from django.conf import settings

from civil_registry.utils import get_citizen_by_national_id
from libya_elections import constants
from text_messages.utils import get_message

from .models import RegistrationCenter, Registration, SMS
from .utils import remaining_registrations


logger = logging.getLogger(__name__)


class Result(object):
    """
    Represent the result of processing someone's message.

    :param string phone_number: The user's phone number
    :param integer message_code: Identifies the message we're responding with
    :param dict context: Any parameters needed when we format the message
    :raise ValueError: If an invalid message code is provided.
    """
    def __init__(self, phone_number, message_code, context=None):
        self.message_code = message_code
        self.phone_number = phone_number
        context = context or {}

        message = get_message(self.message_code)

        # If we've sent the same message code to the same phone number
        # at least 3 times, after that start using an enhanced error
        # message text for that code.  (If we have one.)
        text = message.msg
        if message.enhanced and self._should_enhance():
            text = message.enhanced

        # :self.message is the formatted, final message

        # Default (if everything goes haywire below) to the message without parameters
        # filled in
        self.message = text
        try:
            self.message = text.format(**context)
        except KeyError as e:
            logger.error("Translated message appears to have a parameter that we don't have a "
                         "value for.  text = %r.  Exception = %s.", text, e)
            # Try just leaving it blank.
            try:
                key = e.args[0]
                context[key] = ''
                self.message = text.format(**context)
            except Exception as e:
                logger.error("Got second error. text = %r.  Exception = %s.", text, e)

    def _should_enhance(self):
        """
        Return True if the last 3 messages we sent to this phone number were
        this same message code.
        """
        MIN_REPEATS = 3
        messages_sent = SMS.objects.filter(to_number=self.phone_number)\
            .order_by('-creation_date')[:MIN_REPEATS]
        # If the last 3 messages all had this same error code, we need to use the enhanced message
        return messages_sent.count() == MIN_REPEATS and \
            all([msg.message_code == self.message_code for msg in messages_sent])


def process_registration_request(center_id, national_id, sms):
    """
        Process a well formatted registration request message and returns a
        translated response message.

        Attempts to retrieve a Citizen instance
            + searches our database for match.

        Updates SMS instance
            + all incoming messages get logged.

        Registers citizen
            + Verifies that citizen has only registered once.
            + Updates registration if allowed
            + Does nothing if registering to same center twice.

        Returns a Result object.
    """
    try:
        logger.debug("Getting registration centre")
        center = RegistrationCenter.objects\
            .get(reg_open=True, copy_of=None, center_id=center_id)
    except RegistrationCenter.DoesNotExist:
        return Result(sms.from_number, constants.RESPONSE_CENTER_ID_INVALID)

    citizen = get_citizen_by_national_id(national_id)
    if not citizen:
        return Result(sms.from_number, constants.RESPONSE_NID_INVALID)

    sms.citizen = citizen

    if not citizen.is_eligible():
        logger.debug("Citizen is not eligible.")
        return Result(sms.from_number, constants.RESPONSE_NID_INVALID)

    try:
        registration = Registration.objects.get(citizen=citizen)
    except Registration.DoesNotExist:
        logger.debug("Citizen not already registered")
        registration = None

    remaining = remaining_registrations(sms.from_number)

    if registration:
        logger.debug("Citizen already registered")
        same_phone = registration.sms.from_number == sms.from_number
        unlocked = False
        if registration.unlocked:
            unlocked = True

        if same_phone or unlocked:
            # Same phone, or they've been granted an exception

            if not same_phone and remaining == 0:
                # They're trying to change to a phone that is already
                # at its maximum # of registrations.
                return Result(sms.from_number, constants.TOO_MANY_REGISTRATIONS_ON_PHONE,
                              dict(maximum=settings.MAX_REGISTRATIONS_PER_PHONE))

            # If they're out of changes, sending from same phone, they always get message 6
            if registration.change_count >= registration.max_changes:
                logger.debug("Out of changes, send message 6")
                return Result(sms.from_number, constants.MESSAGE_6,
                              dict(centre=registration.registration_center.name,
                                   code=registration.registration_center.center_id,
                                   person=str(citizen)))

            if registration.registration_center == center:
                # same location - but they could be changing their registered phone
                if not same_phone:
                    # Save the SMS object, so we can archive this registration
                    sms.save()
                    registration.sms = sms
                    logger.debug("Updating phone number")
                    registration.repeat_count = 0
                    registration.save_with_archive_version()
                else:
                    logger.debug("registration is exact repeat")
                    registration.repeat_count += 1
                    # We're just counting their calls, not changing their
                    # registration; no need to make an archive copy.
                    registration.save()
                return Result(sms.from_number, constants.MESSAGE_1,
                              dict(centre=center.name,
                                   code=center.center_id,
                                   person=str(citizen)))
            # different voting center
            logger.debug("registration changing center, count=%d" % registration.change_count)

            # We know they still have changes left because we checked above
            registration.change_count += 1
            registration.repeat_count = 1
            registration.registration_center = center
            sms.save()
            registration.sms = sms
            if unlocked:
                # they've used their exception
                registration.unlocked_until = None
            registration.save_with_archive_version()
            if not registration.remaining_changes:
                # Last time
                return Result(sms.from_number, constants.MESSAGE_5,
                              dict(centre=center.name,
                                   code=center.center_id,
                                   person=str(citizen)))
            elif registration.remaining_changes == 1:
                # one more allowed
                return Result(sms.from_number, constants.MESSAGE_4,
                              dict(centre=center.name,
                                   code=center.center_id,
                                   person=str(citizen)))
            else:
                return Result(sms.from_number, constants.RESPONSE_VALID_REGISTRATION,
                              dict(centre=center.name,
                                   code=center.center_id,
                                   person=str(citizen)))

        # Different phone
        if registration.registration_center == center:
            # same registration - don't do anything
            return Result(sms.from_number, constants.MESSAGE_7,
                          dict(centre=registration.registration_center.name,
                               number=registration.sms.from_number[-4:]))
        # Cannot change anything from a different phone
        # Sorry, this NID is already registered at {centre} with a phone
        # ending in {number}. You must use this phone to re-register. If
        # you do not have access to this phone or need help, call 1441.
        # (message number 3)'}
        return Result(sms.from_number, constants.MESSAGE_2,
                      dict(centre=registration.registration_center.name,
                           number=registration.sms.from_number[-4:]))

    logger.debug("new registration")
    kwargs = {"citizen": citizen, "registration_center": center, "sms": sms}

    if remaining == 0:
        # They're trying to create a new registration, but
        # there are the maximum (or more) registrations from
        # this phone already.
        return Result(sms.from_number, constants.TOO_MANY_REGISTRATIONS_ON_PHONE,
                      dict(maximum=settings.MAX_REGISTRATIONS_PER_PHONE))

    # We have to save the SMS before we can save the Registration that refers to it
    sms.save()
    Registration.objects.create(**kwargs)

    remaining -= 1
    if remaining == 0:
        # Send a warning message - no more regs on this phone
        msg_code = constants.AT_MAXIMUM_REGISTRATIONS_ON_PHONE
    elif remaining == 1:
        # Send a warning message - only one more reg on this phone
        msg_code = constants.ONE_MORE_REGISTRATION_ON_PHONE
    else:
        # Normal message
        msg_code = constants.RESPONSE_VALID_REGISTRATION

    return Result(sms.from_number, msg_code,
                  dict(centre=center.name,
                       code=center.center_id,
                       person=str(citizen)))


def process_registration_lookup(national_id, sms):
    """
    Given the national ID string and the sms object from a syntactically
    valid registration lookup message, check the registration of the
    citizen with the given NID and respond with a message containing the
    current registration status.
    """
    citizen = get_citizen_by_national_id(national_id)
    if not citizen:
        return Result(sms.from_number, constants.VOTER_QUERY_NOT_FOUND)

    sms.citizen = citizen
    sms.save()

    registrations = citizen.registrations.all()
    context = {'person': citizen}  # Used for formatting messages, so key='person' is okay
    if registrations:
        if registrations.count() == 1:
            # Citizen has one confirmed registration
            registration = registrations[0]
            center = registration.registration_center
            context.update({'centre': center.name, 'code': center.center_id})
            return Result(sms.from_number, constants.VOTER_QUERY_REGISTERED_AT, context)
        else:  # pragma: no cover
            # Multiple confirmed registrations - this should never happen, due to
            # database constraints
            logger.error("Voter %s has multiple confirmed registrations", national_id)
            return Result(sms.from_number, constants.VOTER_QUERY_PROBLEM_ENCOUNTERED, context)
    # Citizen has not registered.
    return Result(sms.from_number, constants.VOTER_QUERY_NOT_REGISTERED, context)
