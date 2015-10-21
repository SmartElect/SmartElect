from __future__ import division
import logging

from django.conf import settings
from django.utils import translation
from rapidsms.contrib.handlers import BaseHandler

from libya_elections.constants import POLLING_REPORT_INVALID, POLLING_NOT_OPEN, \
    POLLING_REPORT_RECEIVED, PHONE_NOT_ACTIVATED, POLLING_REPORT_CENTER_MISMATCH, \
    INVALID_CENTER_ID, CENTER_OPENING_NOT_AUTHORIZED, NOT_WHITELISTED_NUMBER, PHONE_ACTIVATED, \
    CENTER_OPENED, CENTER_OPEN_INDICATOR, LAST_PERIOD_NUMBER, FIRST_PERIOD_NUMBER, \
    PRELIMINARY_VOTE_COUNT_INDICATOR, PRELIMINARY_VOTES_REPORT, \
    POLLING_REPORT_RECEIVED_VERY_HIGH_TURNOUT, POLLING_REPORT_RECEIVED_NO_REGISTRANTS, \
    RESPONSE_SERVER_ERROR
from polling_reports.models import StaffPhone, CenterOpen, PollingReport, PreliminaryVoteCount
from register.handlers import LibyaHandlerMixin
from register.models import RegistrationCenter, Registration, SMS
from register.utils import polling_reports_enabled, phone_activation_enabled, center_opening_enabled
from voting.models import Election


logger = logging.getLogger(__name__)


class ReportsShortCodeHandler(LibyaHandlerMixin, BaseHandler):
    # Note: this is not a PatternHandler, just a BaseHandler.

    acceptable_to_numbers = [
        settings.REPORTS_SHORT_CODE,
        settings.LIBYA_COUNTRY_CODE + settings.REPORTS_SHORT_CODE
    ]

    @classmethod
    def dispatch(cls, router, msg):
        handled = False
        try:
            handled = cls.handle(router, msg)
        except Exception:
            # LOG ANY EXCEPTION THAT BUBBLES UP HERE
            logger.exception("An unexpected exception happened in "
                             "%s.dispatch" % cls.__name__)
            if not msg.responses:
                # We did not manage to send any response.  Send SOMETHING.
                with translation.override(settings.OUTGOING_MESSAGE_LANGUAGE):
                    cls.send_response(msg, RESPONSE_SERVER_ERROR)
            msg.sms.save()
            # We handled it, return True
            return True
        else:
            # We might not have handled it, but there was no exception. Let
            # other handlers try it.
            return handled

    @classmethod
    def handle(cls, router, msg):
        if not cls.is_addressed_to_us(msg):
            return False

        with translation.override(settings.OUTGOING_MESSAGE_LANGUAGE):
            if not cls.is_whitelisted(msg):
                # Only whitelisted phones may send messages to this number
                return cls.send_response(msg, NOT_WHITELISTED_NUMBER)
            sms = msg.sms
            from_number = sms.from_number
            # We can't get here without the message being cleaned up and stripped
            # of non-numbers, so...
            if msg.text:
                numbers = [int(val) for val in msg.text.split('*')]
            else:
                numbers = []
            activation = StaffPhone.objects.filter(phone_number=sms.from_number).first()
            if not activation:
                # Phone has not already been activated
                if not phone_activation_enabled():
                    return cls.send_response(msg, POLLING_NOT_OPEN)
                elif len(numbers) != 2:
                    msg.sms.msg_type = SMS.NOT_ACTIVATED
                    return cls.send_response(msg, PHONE_NOT_ACTIVATED)
                number1, number2 = numbers
                if number1 != number2:
                    msg.sms.msg_type = SMS.POLLING_REPORT_INVALID
                    return cls.send_response(msg, POLLING_REPORT_CENTER_MISMATCH)
                try:
                    center = RegistrationCenter.objects.get(center_id=number1)
                except RegistrationCenter.DoesNotExist:
                    msg.sms.msg_type = SMS.POLLING_REPORT_INVALID
                    return cls.send_response(msg, INVALID_CENTER_ID)
                context = dict(number=from_number, code=center.center_id, centre=center.name)
                StaffPhone.objects.create(phone_number=from_number, registration_center=center)
                msg.sms.msg_type = SMS.ACTIVATE
                cls.send_response(msg, PHONE_ACTIVATED, **context)
                logger.debug("%s has been authorized for center #%s", from_number, center.center_id)
                CenterOpen.objects.create(
                    election=Election.objects.get_most_current_election(),
                    phone_number=from_number, registration_center=center
                )
                return cls.send_response(msg, CENTER_OPENED, **context)
            else:
                # phone number has been activated already
                activated_center = activation.registration_center
                activated_center_id = activated_center.center_id
                context = dict(number=from_number, code=activated_center_id,
                               centre=activated_center.name)

                if len(numbers) == 2:
                    number1, number2 = numbers
                    if number1 == CENTER_OPEN_INDICATOR:
                        # Center open message
                        if not center_opening_enabled():
                            return cls.send_response(msg, POLLING_NOT_OPEN)
                        number_in_message = number2
                        try:
                            message_center = RegistrationCenter.objects.get(
                                center_id=number_in_message)
                        except RegistrationCenter.DoesNotExist:
                            # No such center
                            msg.sms.msg_type = SMS.POLLING_REPORT_INVALID
                            return cls.send_response(msg, INVALID_CENTER_ID)
                        if message_center != activated_center:
                            context['registered_centre'] = activated_center_id
                            context['centre'] = number_in_message
                            msg.sms.msg_type = SMS.NOT_ACTIVATED
                            return cls.send_response(msg, CENTER_OPENING_NOT_AUTHORIZED, **context)
                        else:
                            CenterOpen.objects.create(
                                election=Election.objects.get_most_current_election(),
                                phone_number=from_number,
                                registration_center=activated_center
                            )
                            msg.sms.msg_type = SMS.ACTIVATE
                            return cls.send_response(msg, CENTER_OPENED, **context)
                    elif not polling_reports_enabled():
                        return cls.send_response(msg, POLLING_NOT_OPEN, **context)
                    elif not (FIRST_PERIOD_NUMBER <= number1 <= LAST_PERIOD_NUMBER):
                        msg.sms.msg_type = SMS.POLLING_REPORT_INVALID
                        return cls.send_response(msg, POLLING_REPORT_INVALID)
                    else:
                        # Looks like a polling report
                        period_number, num_voters = number1, number2
                        PollingReport.objects.create(
                            election=Election.objects.get_most_current_election(),
                            phone_number=from_number,
                            registration_center=activated_center,
                            period_number=period_number,
                            num_voters=num_voters,
                        )

                        # Construct log & SMS response messages
                        center_id = activated_center.copy_of.id if activated_center.is_copy \
                            else activated_center.id
                        qs = Registration.objects.filter(registration_center_id=center_id)
                        n_registrations = qs.count()

                        turnout = num_voters / n_registrations if n_registrations else 0

                        log_msg = "Daily report received from center {center_id}, turnout " \
                                  "is {turnout:05.01%}".format(center_id=activated_center_id,
                                                               turnout=turnout)
                        if turnout > settings.SUSPICIOUS_TURNOUT_THRESHOLD:
                            log_msg += ", SUSPICIOUS_TURNOUT_THRESHOLD exceeded"
                            response_msg = POLLING_REPORT_RECEIVED_VERY_HIGH_TURNOUT
                        elif n_registrations == 0:
                            log_msg += ", center has 0 registrants."
                            response_msg = POLLING_REPORT_RECEIVED_NO_REGISTRANTS
                        else:
                            # This is the common case.
                            response_msg = POLLING_REPORT_RECEIVED
                        logger.debug(log_msg)

                        context['code'] = activated_center_id
                        context['n_voters'] = num_voters
                        context['turnout'] = turnout

                        msg.sms.msg_type = SMS.POLLING_REPORT
                        return cls.send_response(msg, response_msg, **context)

                elif len(numbers) == 3 and numbers[0] == PRELIMINARY_VOTE_COUNT_INDICATOR:
                    election = Election.objects.\
                        get_elections_with_preliminary_vote_counts_enabled().first()
                    if not election:
                        return cls.send_response(msg, POLLING_NOT_OPEN)

                    option, num_votes = numbers[1], numbers[2]

                    # "delete" any existing reports for the same center in this election
                    # so we only count the most recent message
                    PreliminaryVoteCount.objects.filter(
                        election=election,
                        registration_center=activated_center,
                        option=option,
                    ).update(deleted=True)
                    # Create new record with the latest numbers
                    PreliminaryVoteCount.objects.create(
                        election=election,
                        phone_number=from_number,
                        registration_center=activated_center,
                        option=option,
                        num_votes=num_votes,
                    )
                    # "Centre {centre} reported {num_votes} votes for option {option}. If this
                    # is incorrect, please resubmit. Final results are based on paper results
                    # forms.  (message number 87)"
                    context['centre'] = activated_center_id
                    context['option'] = option
                    context['num_votes'] = num_votes
                    msg.sms.msg_type = SMS.POLLING_REPORT
                    return cls.send_response(msg, PRELIMINARY_VOTES_REPORT, **context)
                else:
                    msg.sms.msg_type = SMS.POLLING_REPORT_INVALID
                    return cls.send_response(msg, POLLING_REPORT_INVALID)
