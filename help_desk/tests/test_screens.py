# -*- coding: utf-8 -*-
"""
These are basically state machine tests. We set up one state,
pretend the operator provided certain input, then verify that
the resulting state is what we expected.
"""
from django.core.urlresolvers import reverse
from django.test import TestCase, override_settings
from django.utils.translation import override

from civil_registry.tests.factories import CitizenFactory
from help_desk.models import BUTTON_NO_CITIZEN, BUTTON_START_OVER

from libya_site.tests.factories import DEFAULT_USER_PASSWORD
from register.models import Registration
from register.tests.factories import RegistrationFactory

from ..models import BUTTON_YES, BUTTON_NO, Case, BUTTON_SUBMIT, \
    BUTTON_GO_BACK, BUTTON_HUNG_UP, BUTTON_DONE, BUTTON_NO_MATCH, \
    BUTTON_CONTINUE, BUTTON_UNABLE, BUTTON_MATCH
from ..screens import GET_STAFF_ID, GET_NID, ASK_IF_STAFF, CHECK_STAFF_NAME, CHECK_STAFF_PHONE, \
    GOOD_BYE, CHECK_NAME_AND_DOB, ASK_TO_CHANGE, HUNG_UP, \
    NOT_REGISTERED, ASK_SAME_PHONE, CHECK_FRN, HOW_TO_CHANGE, \
    CHANGE_PERIOD_STARTED, BLOCKED, FIRST_SCREEN
from ..utils import create_help_desk_groups

from .factories import CaseFactory, FieldStaffFactory


class ScreenTestCase(TestCase):
    use_staff = False  # Set True to force the path through the field staff validation

    def setUp(self):
        create_help_desk_groups()
        self.case = CaseFactory()
        self.operator = self.case.operator
        self.citizen = CitizenFactory(national_id=210987654321)
        self.registration = None  # Create as needed
        assert self.client.login(
            username=self.operator.username,
            password=DEFAULT_USER_PASSWORD)
        self.staff = FieldStaffFactory()
        self.get_to_screen(self.screen_name)

    def get_to_screen(self, name):
        """Navigate through the case until we're on screen 'name', by providing
        the appropriate input on each screen.
        """
        if self.case.current_screen and self.case.current_screen.name == name:
            # We're already on the desired screen
            return
        if name == ASK_IF_STAFF:
            self.case.start_screen(ASK_IF_STAFF)
        elif name == GET_STAFF_ID:
            self.get_to_screen(ASK_IF_STAFF)
            self.operator_input(button_name=BUTTON_YES)
        elif name == CHECK_STAFF_NAME:
            self.get_to_screen(GET_STAFF_ID)
            self.operator_input(button_name=BUTTON_SUBMIT, staff_id=str(self.staff.staff_id))
        elif name == CHECK_STAFF_PHONE:
            self.get_to_screen(ASK_IF_STAFF)
            self.operator_input(button_name=BUTTON_YES, expected_screen=GET_STAFF_ID)
            self.operator_input(button_name=BUTTON_SUBMIT, staff_id=self.staff.staff_id,
                                expected_screen=CHECK_STAFF_NAME)
            # Name must have matched to get here
            self.operator_input(button_name=BUTTON_MATCH)
        elif name == GET_NID:
            if not self.case.current_screen:
                # make sure we're on some screen
                self.get_to_screen(ASK_IF_STAFF)
                self.operator_input(button_name=BUTTON_NO_CITIZEN)
            if self.use_staff or self.case.current_screen.name in (GET_STAFF_ID, CHECK_STAFF_NAME):
                # If we're on the path through field staff, go to final screen on that path
                self.get_to_screen(CHECK_STAFF_PHONE)
            if self.case.current_screen.name == CHECK_STAFF_PHONE:
                self.operator_input(button_name=BUTTON_YES)
            else:
                self.get_to_screen(ASK_IF_STAFF)
                self.operator_input(button_name=BUTTON_NO_CITIZEN)
        elif name == CHECK_NAME_AND_DOB:
            self.get_to_screen(GET_NID)
            self.operator_input(button_name=BUTTON_SUBMIT, national_id=self.citizen.national_id)
        elif name == BLOCKED:
            self.assertTrue(self.citizen.blocked,
                            msg="Cannot get to BLOCKED screen unless citizen is blocked")
            self.get_to_screen(CHECK_NAME_AND_DOB)
            self.operator_input(button_name=BUTTON_YES)
        elif name == ASK_TO_CHANGE:
            if not self.case.registration:
                self.case.registration = RegistrationFactory(citizen=self.citizen,
                                                             archive_time=None)
                self.case.save()
            self.get_to_screen(CHECK_NAME_AND_DOB)
            self.operator_input(button_name=BUTTON_YES)
        elif name == ASK_SAME_PHONE:
            self.get_to_screen(ASK_TO_CHANGE)
            self.operator_input(button_name=BUTTON_YES)
        elif name == NOT_REGISTERED:
            if self.case.registration:
                self.case.registration.delete()
                self.case.registration = None
                self.save()
            self.get_to_screen(CHECK_NAME_AND_DOB)
            self.operator_input(button_name=BUTTON_YES)
        elif name == CHECK_FRN:
            self.get_to_screen(ASK_SAME_PHONE)
            self.operator_input(button_name=BUTTON_NO)
        elif name == CHANGE_PERIOD_STARTED:
            self.get_to_screen(CHECK_FRN)
            self.operator_input(button_name=BUTTON_YES)
        elif name == HUNG_UP:
            # doesn't matter WHERE we are :-) - but we have to be somewhere
            if not self.case.current_screen:
                # make sure we're on some screen
                self.get_to_screen(ASK_IF_STAFF)
            self.operator_input(button_name=BUTTON_HUNG_UP)
        else:
            self.fail("Don't know how to get to screen %s" % name)
        self.assert_current_screen(name)

    def operator_input(self, button_name, expected_status=200,
                       expected_template='help_desk/screen.html',
                       expected_screen=None,
                       **kwargs):
        screen_name = self.case.current_screen.name
        url = reverse(screen_name, args=[self.case.pk])
        data = {
            'button_%s' % button_name: True,
        }
        data.update(**kwargs)
        # Do the redirect follow so the next screen can be established
        rsp = self.client.post(url, data=data, follow=True)

        # Get updated case record since view updated it in the database
        self.case = Case.objects.get(pk=self.case.pk)

        self.assertEqual(expected_status, rsp.status_code,
                         msg="Expected status %d but got %d on screen %s submitting %s %s" % (
                             expected_status, rsp.status_code, screen_name,
                             button_name, kwargs
                         ))
        if expected_status == 200:
            self.assertTemplateUsed(rsp, expected_template)
        self.rsp = rsp
        if expected_screen:
            self.assert_current_screen(expected_screen)

    def assert_current_screen(self, name, msg=None):
        if name != self.case.current_screen.name:
            m = "Expected to be on screen %s but on screen %s" \
                % (name, self.case.current_screen.name)
            if msg:
                m += ". " + msg
            self.fail(m)

    def assert_staff_validated(self, is_validated):
        self.assertEqual(is_validated, self.case.field_staff_validated)

    def assert_national_id_validated(self, is_validated):
        self.assertEqual(is_validated, self.case.national_id_validated)


class BasicTests(ScreenTestCase):
    screen_name = ASK_IF_STAFF

    def test_post_no_button(self):
        # Posting without any button is a 4xx
        url = reverse(ASK_IF_STAFF, args=[self.case.pk])
        rsp = self.client.post(url, data={})
        self.assertEqual(400, rsp.status_code)

    def test_wrong_screen_redirects(self):
        url = reverse(HUNG_UP, args=[self.case.pk])
        expected_url = reverse(ASK_IF_STAFF, args=[self.case.pk])
        rsp = self.client.get(url)
        self.assertRedirects(rsp, expected_url)

    def test_no_current_screen_error(self):
        self.case.current_screen = None
        self.case.save()
        url = reverse(ASK_IF_STAFF, args=[self.case.pk])
        rsp = self.client.get(url)
        self.assertEqual(500, rsp.status_code)


class ButtonScreenTestMixin(object):
    """
    Test for a screen that just looks at the button that was pressed and goes
    to another screen.
    """
    #: Dictionary mapping input button name to resulting screen name
    button_to_screen = {}

    def common_button_check(self, button_name):
        if button_name in self.button_to_screen:
            expected = self.button_to_screen[button_name]
            if expected:
                self.operator_input(button_name)
                self.assert_current_screen(expected)
        else:
            self.operator_input(button_name, expected_status=400)

    def test_button_yes(self):
        self.common_button_check(BUTTON_YES)

    def test_button_no(self):
        self.common_button_check(BUTTON_NO)

    def test_button_too_many_failures(self):
        self.common_button_check(BUTTON_NO_MATCH)

    def test_button_next(self):
        self.common_button_check(BUTTON_CONTINUE)

    def test_button_go_back(self):
        if BUTTON_GO_BACK in self.button_to_screen:
            self.common_button_check(BUTTON_GO_BACK)
        # else, we have no way of knowing the expected screen.

    def test_button_start_over(self):
        self.operator_input(BUTTON_START_OVER)
        self.assert_current_screen(FIRST_SCREEN)

    def test_button_hung_up(self):
        # To the "hung up" screen.
        self.operator_input(BUTTON_HUNG_UP, expected_template='help_desk/screens/hung_up.html')
        case = Case.objects.get(pk=self.case.pk)
        # Not done yet
        self.assertIsNone(case.end_time)
        # But outcome should be set
        self.assertEqual(Case.HUNG_UP, case.call_outcome)

    def test_button_end(self):
        if BUTTON_DONE in self.button_to_screen:
            self.operator_input(BUTTON_DONE, expected_template='help_desk/main.html')
            case = Case.objects.get(pk=self.case.pk)
            # Case is done!
            self.assertIsNotNone(case.end_time)


class AskIfStaffView(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = ASK_IF_STAFF
    button_to_screen = {
        BUTTON_YES: GET_STAFF_ID,
        BUTTON_NO_CITIZEN: GET_NID,
    }

    def test_go_back(self):
        self.operator_input(BUTTON_GO_BACK, expected_status=400)


class GetStaffIDView(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = GET_STAFF_ID
    button_to_screen = {
        BUTTON_UNABLE: GOOD_BYE,
        BUTTON_SUBMIT: None,
    }

    def test_valid_id(self):
        self.operator_input(button_name=BUTTON_SUBMIT, staff_id=self.staff.staff_id)
        self.assertNotIn('form', self.rsp.context)
        self.assert_current_screen(CHECK_STAFF_NAME)
        self.assertEqual(self.case.field_staff, self.staff)
        self.assert_staff_validated(False)

    def test_valid_id_arabic(self):
        self.staff.staff_id = 123
        self.staff.save()
        self.operator_input(button_name=BUTTON_SUBMIT, staff_id=u'١٢٣')
        self.assertNotIn('form', self.rsp.context)
        self.assert_current_screen(CHECK_STAFF_NAME)
        self.assertEqual(self.case.field_staff, self.staff)
        self.assert_staff_validated(False)

    def test_invalid_id(self):
        self.operator_input(button_name=BUTTON_SUBMIT, staff_id='foo')
        self.assertIn('form', self.rsp.context)
        self.assert_current_screen(GET_STAFF_ID)
        self.assertIsNone(self.case.field_staff)
        self.assert_staff_validated(False)

    def test_no_such_id(self):
        self.operator_input(button_name=BUTTON_SUBMIT, staff_id=99 + self.staff.staff_id)
        self.assertIn('form', self.rsp.context)
        self.assert_current_screen(GET_STAFF_ID)
        self.assertIsNone(self.case.field_staff)
        self.assert_staff_validated(False)


class CheckStaffNameView(ButtonScreenTestMixin, ScreenTestCase):
    use_staff = True
    screen_name = CHECK_STAFF_NAME
    button_to_screen = {
        BUTTON_MATCH: CHECK_STAFF_PHONE,
        BUTTON_NO_MATCH: GOOD_BYE,
        BUTTON_GO_BACK: GET_STAFF_ID,
        BUTTON_SUBMIT: None,  # not valid on this screen
    }

    def test_go_back(self):
        # IF we go back, the staff ID form ought to undo the staff ID, if any
        self.operator_input(BUTTON_GO_BACK)
        self.assertIsNone(self.case.field_staff)
        self.assert_staff_validated(False)

    def test_match(self):
        self.operator_input(BUTTON_MATCH)
        # Should still not be marked validated since we haven't check the phone yet
        self.assert_staff_validated(False)

    def test_no_match(self):
        self.operator_input(BUTTON_NO_MATCH)
        self.assert_staff_validated(False)


class CheckStaffPhoneView(ButtonScreenTestMixin, ScreenTestCase):
    use_staff = True
    screen_name = CHECK_STAFF_PHONE
    button_to_screen = {
        BUTTON_YES: GET_NID,
        BUTTON_NO: GOOD_BYE,
        BUTTON_GO_BACK: CHECK_STAFF_NAME,
    }

    def test_valid_staff(self):
        self.operator_input(button_name=BUTTON_YES)
        # If we got here, name was valid, and now phone is valid, so field staff should be valid.
        self.assert_staff_validated(True)


class GetNIDView(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = GET_NID
    button_to_screen = {
        BUTTON_SUBMIT: None,  # skip test
        BUTTON_UNABLE: GOOD_BYE,
    }

    def test_button_submit(self):
        self.operator_input(BUTTON_SUBMIT, national_id=str(self.citizen.national_id))
        self.assert_current_screen(CHECK_NAME_AND_DOB)
        self.assert_national_id_validated(False)

    def test_button_submit_arabic(self):
        arabic_nid = u'٢١٠٩٨٧٦٥٤٣٢١'  # 210987654321, the same nid from setUp
        self.operator_input(BUTTON_SUBMIT, national_id=arabic_nid)
        self.assert_current_screen(CHECK_NAME_AND_DOB)
        self.assert_national_id_validated(False)

    def test_nonexistent_nid(self):
        self.operator_input(BUTTON_SUBMIT, national_id='123456789012')
        self.assert_current_screen(GET_NID)
        self.assert_national_id_validated(False)

    # We can get here two ways, so need to test both paths for GO_BACK
    def test_button_go_back(self):
        # Without field staff
        self.case.current_screen.end(self.case)
        self.case.start_screen(ASK_IF_STAFF)
        self.operator_input(BUTTON_NO_CITIZEN)
        self.assert_current_screen(GET_NID)
        self.operator_input(BUTTON_GO_BACK)
        self.assert_current_screen(ASK_IF_STAFF)
        self.assert_national_id_validated(False)

    def test_go_back_field_staff(self):
        # with field staff
        self.case.current_screen.end(self.case)
        self.case.start_screen(ASK_IF_STAFF)
        self.operator_input(BUTTON_YES)
        self.assert_current_screen(GET_STAFF_ID)
        staff = FieldStaffFactory()
        self.operator_input(button_name=BUTTON_SUBMIT, staff_id=staff.staff_id)
        self.assert_current_screen(CHECK_STAFF_NAME)
        self.operator_input(BUTTON_MATCH)
        self.assert_current_screen(CHECK_STAFF_PHONE)
        self.operator_input(BUTTON_YES)
        self.assert_current_screen(GET_NID)
        self.operator_input(BUTTON_GO_BACK)
        self.assert_current_screen(CHECK_STAFF_PHONE)
        self.assert_national_id_validated(False)


class CheckNameAndDOB(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = CHECK_NAME_AND_DOB
    button_to_screen = {
        BUTTON_YES: None,
        BUTTON_NO: GOOD_BYE,
    }

    def test_answer_no(self):
        self.assert_national_id_validated(False)
        self.operator_input(BUTTON_NO)
        self.assert_national_id_validated(False)

    def test_yes_if_registered(self):
        # IF registered, go to ASK_TO_CHANGE
        if not self.case.registration:
            self.case.registration = RegistrationFactory(citizen=self.citizen,
                                                         archive_time=None)
            self.case.save()
        self.operator_input(BUTTON_YES)
        self.assert_current_screen(ASK_TO_CHANGE)
        self.assert_national_id_validated(True)

    def test_yes_if_unregistered(self):
        # If not, go to NOT_REGISTERED
        if self.case.registration:
            self.case.registration.delete()
            self.case.registration = None
            self.case.save()
        self.operator_input(BUTTON_YES)
        self.assert_current_screen(NOT_REGISTERED)
        self.assert_national_id_validated(True)

    def test_yes_if_blocked(self):
        # IF blocked, go to BLOCKED
        self.case.citizen = self.citizen
        self.case.save()
        self.case.citizen.block()
        self.operator_input(BUTTON_YES)
        self.assert_current_screen(BLOCKED)
        # can complete the call and return to the main screen
        self.operator_input(BUTTON_DONE, expected_template='help_desk/main.html')
        self.assert_national_id_validated(True)

    def test_go_back(self):
        if not self.case.citizen:
            self.case.citizen = CitizenFactory()
            self.case.save()
        self.operator_input(BUTTON_GO_BACK)
        case = Case.objects.get(pk=self.case.pk)
        self.assertIsNone(case.citizen)
        self.assert_national_id_validated(False)


class AskToChange(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = ASK_TO_CHANGE
    button_to_screen = {
        BUTTON_YES: ASK_SAME_PHONE,
        BUTTON_NO: GOOD_BYE,
    }


class NotRegistered(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = NOT_REGISTERED
    button_to_screen = {
        BUTTON_CONTINUE: GOOD_BYE,
    }


class AskSamePhone(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = ASK_SAME_PHONE
    button_to_screen = {
        BUTTON_YES: HOW_TO_CHANGE,
        BUTTON_NO: CHECK_FRN,
    }

    def test_increase_changes(self):
        self.case.registration = Registration.objects.get(citizen=self.citizen)
        self.case.registration.max_changes = self.case.registration.change_count
        self.case.registration.save()
        self.case.save()
        self.operator_input(BUTTON_YES)
        self.assert_current_screen(HOW_TO_CHANGE)
        # Using assertTrue(x in y) instead of assertIn(x, y) because I don't really
        # want to see the whole darn page context if the assertion fails
        self.assertTrue('pre_text' in self.rsp.context)
        reg = Registration.objects.get(pk=self.case.registration.pk)
        self.assertTrue(reg.max_changes > reg.change_count)
        case = Case.objects.get(pk=self.case.pk)
        self.assertTrue(case.changes_increased)

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=2)
    def test_display_max_registrations_warning(self):
        PHONE_NUMBER = self.case.registration.sms.from_number
        url = reverse(self.screen_name, args=[self.case.pk])
        with override(language='en'):
            rsp = self.client.get(url)
        self.assertNotContains(rsp, "has been used for the maximum number")
        RegistrationFactory(archive_time=None, sms__from_number=PHONE_NUMBER)
        rsp = self.client.get(url)
        self.assertContains(rsp, "has been used for the maximum number")


class CheckFRN(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = CHECK_FRN
    button_to_screen = {
        BUTTON_YES: CHANGE_PERIOD_STARTED,
        BUTTON_NO: GOOD_BYE,
    }


class ChangePeriodStarted(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = CHANGE_PERIOD_STARTED
    button_to_screen = {
        BUTTON_CONTINUE: GOOD_BYE,
    }

    @override_settings(MAX_REGISTRATIONS_PER_PHONE=2)
    def test_check_number(self):
        PHONE_NUMBER = '98765'

        url = reverse(self.screen_name, args=[self.case.pk])
        data = {
            'check_number': PHONE_NUMBER,
        }
        with override(language='en'):
            # No registrations on phone
            rsp = self.client.post(url, data=data, follow=True)
            self.assertContains(rsp, "can be used for 2 more registrations.")
            self.assertRedirects(rsp, url)
            # One registration on phone
            RegistrationFactory(archive_time=None, sms__from_number=PHONE_NUMBER)
            rsp = self.client.post(url, data=data, follow=True)
            self.assertContains(rsp, "can be used for 1 more registration.")
            self.assertRedirects(rsp, url)
            # Two regs on phone
            RegistrationFactory(archive_time=None, sms__from_number=PHONE_NUMBER)
            rsp = self.client.post(url, data=data, follow=True)
            self.assertContains(rsp, "cannot be used for any more registrations.")
            self.assertRedirects(rsp, url)


class HungUp(ButtonScreenTestMixin, ScreenTestCase):
    screen_name = HUNG_UP
    button_to_screen = {
        BUTTON_DONE: None,
    }
