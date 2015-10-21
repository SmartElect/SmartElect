from collections import OrderedDict
import logging

from django.conf.urls import url
from django.contrib import messages
from django.core.urlresolvers import reverse
from django.http.response import HttpResponseBadRequest, HttpResponseServerError, \
    HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect
from django.utils.encoding import force_text
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _, ungettext
from django.views.decorators.cache import never_cache
from django.views.generic import TemplateView, RedirectView

from .forms import GetStaffIDForm, GetNIDForm
from .models import BUTTON_YES, BUTTON_NO, BUTTON_HUNG_UP, \
    BUTTON_SUBMIT, DEFAULT_BUTTON_CLASSES, Case, BUTTON_TEXT, BUTTON_GO_BACK, \
    ScreenRecord, BUTTON_DONE, BUTTON_NO_CITIZEN, BUTTON_UNABLE, BUTTON_MATCH, \
    BUTTON_NO_MATCH, BUTTON_CONTINUE, BUTTON_START_OVER
from libya_elections.utils import LoginPermissionRequiredMixin
from register.utils import remaining_registrations


logger = logging.getLogger(__name__)


# Screen names (used internally only, do not translate):
ASK_IF_STAFF = '1_ask_if_staff'
GET_STAFF_ID = '2_get_staff_id'
CHECK_STAFF_NAME = '3_check_staff_name'
GET_NID = '4_get_nid'
CHECK_NAME_AND_DOB = '5_check_name_and_dob'
CHECK_STAFF_PHONE = '3b_check_staff_phone'
NOT_REGISTERED = '6_not_registered'
ASK_TO_CHANGE = '7_ask_to_change'
ASK_SAME_PHONE = '8_ask_same_phone'
HOW_TO_CHANGE = '9_how_to_change'
CHECK_FRN = '10_check_frn'
CHANGE_PERIOD_STARTED = '11_change_started'
BLOCKED = '12_blocked'
GOOD_BYE = '99_good_bye'
HUNG_UP = 'hung_up'
LAST_SCREEN = 'last_screen'

FIRST_SCREEN = ASK_IF_STAFF


def two_at_a_time(args):
    iterable = iter(args)
    while True:
        try:
            x = iterable.next()
            y = iterable.next()
            yield (x, y)
        except StopIteration:
            return


def make_buttons(*args):
    """
    Helper - creates an OrderedDict from its args, taking them in
    pairs as key1, value1, key2, value2, ...
    """
    d = OrderedDict()
    for k, v in two_at_a_time(args):
        d[k] = v
    return d


class StartCallView(LoginPermissionRequiredMixin,
                    RedirectView):
    permission_required = 'help_desk.add_case'
    permanent = False

    def get_redirect_url(self, **kwargs):
        case = Case.objects.create(operator=self.request.user)
        case.current_screen = ScreenRecord.objects.create(case=case, name=FIRST_SCREEN)
        case.save()
        return reverse(FIRST_SCREEN, args=[case.pk])


class ScreenView(LoginPermissionRequiredMixin,
                 TemplateView):
    template_name = 'help_desk/screen.html'
    permission_required = 'help_desk.add_case'
    raise_exception = True  # Raise exception, don't redirect, on missing permission

    #: Name of this screen
    name = None

    #: An OrderedDict - keys are button names, values are dictionaries with entries like
    # 'next_view' and 'outcome'.
    # Buttons are shown in order, so if there's more than one, make sure to use an
    # OrderedDict.
    buttons = None

    #: A title to be displayed on this screen.
    title = None

    #: The form class to use for the form, if any
    form_class = None

    @property
    def screen(self):
        return self.case.current_screen

    @property
    def case(self):
        if not hasattr(self, "_case"):
            self._case = get_object_or_404(Case,
                                           pk=int(self.kwargs['case']),
                                           end_time=None,
                                           operator=self.request.user)
        return self._case

    def get(self, request, *args, **kwargs):
        """
        If no form already, and we have a form class, construct one with no input.
        This can get invoked from .post() if the submitted form was not valid, so
        if there's already a form from that, don't clobber it.
        """
        if not self.request.user.has_perm('help_desk.add_case'):
            return HttpResponseForbidden("User %s does not have permission help_desk.add_case"
                                         % self.request.user)
        if self.screen:
            # make sure we're in the right view
            if self.screen.name != self.name:
                messages.info(request, _('Redirecting to current screen for this case.'))
                return redirect(reverse(self.screen.name, args=[self.case.pk]))
        else:
            return HttpResponseServerError("Case has no current screen")
        if self.form_class and not getattr(self, 'form', None):
            self.form = self.form_class()
        return super(ScreenView, self).get(request, *args, **kwargs)

    def get_button_class(self, button_name):
        # Return the CSS class to use when rendering this button.
        # Let the screen override a button's class if its semantics are different
        # from usual (e.g., "No" might be a negative thing, or might just be one
        # possible answer.)
        button = self.buttons.get(button_name, None)
        if not button:
            if button_name == BUTTON_HUNG_UP:
                button = {
                    'next_view': HUNG_UP,
                    'outcome': Case.HUNG_UP,
                }
            elif button_name == BUTTON_GO_BACK:
                button = {}
        return button.get('class', DEFAULT_BUTTON_CLASSES[button_name])

    def get_button_for_template(self, name):
        """
        Given a button name, return a 3-tuple of (name, text, class)
        """
        return (name, BUTTON_TEXT[name], self.get_button_class(name))

    def get_button_list_for_template(self):
        """
        Return a list of (button name, button label, button class).

        Adds a "GO BACK" button at the beginning if there's a previous screen.

        ALSO, always adds the hangup button, unless the caller has already hung up
        or the view has set include_hangup_button=False.
        """
        buttons = [self.get_button_for_template(name) for name in self.buttons.keys()]
        # Move Yes or Submit to the front
        for i, button in enumerate(buttons):
            if i != 0 and button[0] in ['yes', 'submit']:
                del buttons[i]
                buttons[0:0] = [button]
                break
        return buttons

    def get_context_data(self, **kwargs):
        context = super(ScreenView, self).get_context_data(**kwargs)
        context['newline'] = mark_safe('</p><p>')
        context['case'] = self.case
        context['screen'] = self.screen
        context['buttons'] = self.get_button_list_for_template()
        context['title'] = force_text(self.title)
        if hasattr(self, 'form'):
            context['form'] = self.form
        context['text_template'] = 'help_desk/screens/%s.html' % self.screen.name
        if self.case.changes_increased:
            context['pre_text'] = _("The voter had no more changes allowed from that number. "
                                    "The allowed changes have been increased.")
        context['include_hangup_button'] = (getattr(self, 'include_hangup_button', True)
                                            and self.case.call_outcome != Case.HUNG_UP)
        context['field_staff_verified'] = self.case.field_staff_validated
        return context

    def post(self, request, *args, **kwargs):
        """
        If the input is valid, this method will always:

        * End the current screen
        * Save the case and screen objects
        * Start the next screen
        * Return a redirect

        If outcome is non-None, it will set the case outcome.

        If next view is None, it will end the case and redirect to help_desk home.

        If the SUBMIT button was pressed, check the form. If valid, call form.update_case(case).
        If not valid, display the form and any errors that were found.

        Otherwise, it redirects to the next view.
        """
        if self.screen:
            # make sure we're in the right view
            if self.screen.name != self.name:
                messages.info(request, _('Redirecting to current screen for this case.'))
                return redirect(reverse(self.screen.name, args=[self.case.pk]))
        else:
            return HttpResponseServerError("Case has no current screen")
        self.button_name = None
        for name, value in request.POST.iteritems():
            if name.startswith("button_"):
                self.button_name = name[7:]
                break
        if not self.button_name:
            return HttpResponseBadRequest()
        if self.button_name == BUTTON_HUNG_UP:
            # FIXME: Here, should we just end the case right away and redirect back home?
            self.button = {
                'next_view': HUNG_UP,
                'outcome': Case.HUNG_UP,
            }
        elif self.button_name in [BUTTON_GO_BACK, BUTTON_START_OVER]:
            self.button = {}
        elif self.button_name not in self.buttons:
            return HttpResponseBadRequest()
        else:
            self.button = self.buttons[self.button_name]
        assert hasattr(self, 'button')
        if self.button_name == BUTTON_SUBMIT and self.form_class:
            self.form = self.form_class(request.POST)
            if not self.form.is_valid():
                return self.get(request, *args, **kwargs)
            self.form.update_case(self.case)
        if self.button_name == BUTTON_START_OVER:
            # Special case - reset everything
            self.case.reset()
            self.case.current_screen = ScreenRecord.objects.create(case=self.case,
                                                                   name=FIRST_SCREEN)
            self.case.save()
            return redirect(reverse(FIRST_SCREEN, args=[self.case.pk]))
        if self.button_name == BUTTON_GO_BACK:
            # Special case
            # Delete the current screen
            self.case.current_screen.delete()
            # The new "last" screen is the one we want to end up on.
            # What's its name?
            last_screen = self.case.last_screen
            if last_screen:
                screen_name = last_screen.name
            else:
                return HttpResponseBadRequest()
            # Delete previous screen too, so we can do it again from scratch
            self.case.last_screen.delete()
            self.case.start_screen(screen_name)
            # If this was a screen with a form, undo any data previously input from this form
            view = view_for_screen[screen_name]
            if view.form_class:
                view.form_class().undo(self.case)
            # Clear any outcome we might have reached
            self.case.call_outcome = None
            self.case.save()
            return redirect(screen_name, self.case.pk)

        # screen.end will save the screen and case for us
        self.screen.end(case=self.case, button=self.button_name)
        next_view = self.button['next_view']
        if callable(next_view):
            next_view = next_view(self.case)
        outcome = self.button.get('outcome', None)
        if outcome:
            self.case.call_outcome = outcome
            self.case.save()
        if next_view is None:
            assert self.case.call_outcome
            self.case.end()
            self.case.save()
            messages.info(request, _('The call has ended.'))
            return redirect('help_desk_home')
        else:
            self.case.start_screen(next_view)
            return redirect(next_view, self.case.pk)


class AskIfStaffView(ScreenView):
    name = ASK_IF_STAFF
    title = _('Welcome')
    buttons = make_buttons(
        BUTTON_YES, {
            'next_view': GET_STAFF_ID
        },
        BUTTON_NO_CITIZEN, {
            'next_view': GET_NID,
        }
    )


class GetStaffIDView(ScreenView):
    name = GET_STAFF_ID
    title = _('Ask Staff ID')
    form_class = GetStaffIDForm
    buttons = make_buttons(
        BUTTON_SUBMIT, {
            'next_view': CHECK_STAFF_NAME
        },
        BUTTON_UNABLE, {
            'next_view': GOOD_BYE,
            'outcome': Case.INVALID_STAFF_ID,
        }
    )


class CheckStaffNameView(ScreenView):
    name = CHECK_STAFF_NAME
    title = _('Verify Staff Name')
    buttons = make_buttons(
        BUTTON_MATCH, {
            'next_view': CHECK_STAFF_PHONE
        },
        BUTTON_NO_MATCH, {
            'next_view': GOOD_BYE,
            'outcome': Case.INVALID_STAFF_NAME,
        }
    )


class CheckStaffPhoneView(ScreenView):
    name = CHECK_STAFF_PHONE
    title = _('Verify Staff Phone')
    buttons = make_buttons(
        BUTTON_YES, {
            'next_view': GET_NID
        },
        BUTTON_NO, {
            'next_view': GOOD_BYE,
            'outcome': Case.INVALID_STAFF_PHONE,
        }
    )


class GetNIDView(ScreenView):
    name = GET_NID
    title = _('Get National ID')
    form_class = GetNIDForm
    buttons = make_buttons(
        BUTTON_SUBMIT, {
            'next_view': CHECK_NAME_AND_DOB
        },
        BUTTON_UNABLE, {
            'next_view': GOOD_BYE,
            'outcome': Case.INVALID_NID,
        },
    )


def figure_out_next_on_yes_after_check_name_and_dob(case):
    """
    Use this to figure out what the next screen should be for the given
    case after the help desk staffer has said they gave us the
    correct name and DOB to authenticated themselves.
    """
    if case.blocked:
        return BLOCKED
    elif case.registration:
        return ASK_TO_CHANGE
    else:
        return NOT_REGISTERED


class CheckNameAndDOBView(ScreenView):
    name = CHECK_NAME_AND_DOB
    title = _('Verify Name and Birth Year')

    buttons = make_buttons(
        BUTTON_YES, {
            'next_view': figure_out_next_on_yes_after_check_name_and_dob,
        },
        BUTTON_NO, {
            'next_view': GOOD_BYE,
            'outcome': Case.INVALID_NAME_DOB,
        }
    )


class NotRegisteredView(ScreenView):
    name = NOT_REGISTERED
    title = _('Citizen is not registered')
    buttons = make_buttons(
        BUTTON_CONTINUE, {
            'next_view': GOOD_BYE,
            'outcome': Case.UNREGISTERED,
        }
    )


class AskToChangeView(ScreenView):
    name = ASK_TO_CHANGE
    title = _('Citizen is registered')
    buttons = make_buttons(
        BUTTON_YES, {
            'next_view': ASK_SAME_PHONE
        },
        BUTTON_NO, {
            'next_view': GOOD_BYE,
            'outcome': Case.REGISTRATION_OKAY,
        }
    )


class AskSamePhoneView(ScreenView):
    name = ASK_SAME_PHONE
    title = _('Ask if can change from same phone')
    buttons = make_buttons(
        BUTTON_YES, {
            'next_view': HOW_TO_CHANGE,
            'outcome': Case.SAME_PHONE,
        },
        BUTTON_NO, {
            'next_view': CHECK_FRN,
        }
    )


class CheckFRNView(ScreenView):
    name = CHECK_FRN
    title = _('Verify Family Book Record Number or Mother\'s Name')
    buttons = make_buttons(
        BUTTON_YES, {
            'next_view': CHANGE_PERIOD_STARTED,
            'outcome': Case.UNLOCKED,
            },
        BUTTON_NO, {
            'next_view': GOOD_BYE,
            'outcome': Case.INVALID_FRN,
            }
    )

    def post(self, request, *args, **kwargs):
        if 'button_' + BUTTON_YES in request.POST:
            self.case.unlock_registration()
            self.case.increase_changes_if_needed()
            self.case.save()
        return super(CheckFRNView, self).post(request, *args, **kwargs)


class HowToChangeView(ScreenView):
    name = HOW_TO_CHANGE
    title = _('How To Change Registration')
    buttons = make_buttons(
        BUTTON_CONTINUE, {
            'next_view': GOOD_BYE,
        }
    )

    def get(self, request, *args, **kwargs):
        # .increase_changes_if_needed will set the outcome to INCREASED_CHANGES if
        # it increases the changes; otherwise leaves it alone.
        self.case.increase_changes_if_needed()
        self.case.save()
        return super(HowToChangeView, self).get(request, *args, **kwargs)


class ChangePeriodStartedView(ScreenView):
    name = CHANGE_PERIOD_STARTED
    title = _('Period to Change Registration from another phone has started')
    buttons = make_buttons(
        BUTTON_CONTINUE, {
            'next_view': GOOD_BYE,
            'outcome': Case.UNLOCKED,
        },
    )

    def post(self, request, *args, **kwargs):
        if 'check_number' in request.POST:
            # See how many registrations are left for the phone number
            phone_number = request.POST['check_number']
            remaining = remaining_registrations(phone_number)
            if remaining <= 0:
                msg = _("The phone number {phone_number} cannot be used for any more "
                        "registrations.").format(phone_number=phone_number)
            else:
                msg = ungettext(
                    "The phone number {phone_number} can be used for {number} more registration.",
                    "The phone number {phone_number} can be used for {number} more registrations.",
                    remaining
                ).format(phone_number=phone_number, number=remaining)
            messages.info(request, msg)
            return redirect(request.path)
        return super(ChangePeriodStartedView, self).post(request, *args, **kwargs)


# Final screens:
class HungUpView(ScreenView):
    name = HUNG_UP
    title = _('Caller hung up')
    buttons = make_buttons(
        BUTTON_DONE, {
            'next_view': None,
            'outcome': Case.HUNG_UP,
        }
    )


class BlockedView(ScreenView):
    name = BLOCKED
    title = _('Citizen is blocked from voting')
    buttons = make_buttons(
        BUTTON_DONE, {
            'next_view': None,  # call ended
            'outcome': Case.INVALID_NID,
        },
    )


class GoodByeView(ScreenView):
    name = GOOD_BYE
    title = _('Good Bye')
    include_hangup_button = False
    buttons = make_buttons(
        BUTTON_DONE, {
            'next_view': None  # call ended
        },
    )


screen_views = [
    AskIfStaffView,
    GetStaffIDView,
    CheckStaffNameView,
    CheckStaffPhoneView,
    GetNIDView,
    CheckNameAndDOBView,
    NotRegisteredView,
    AskToChangeView,
    AskSamePhoneView,
    CheckFRNView,
    HowToChangeView,
    ChangePeriodStartedView,
    HungUpView,
    BlockedView,
    GoodByeView,
]

view_for_screen = {}
for v in screen_views:
    view_for_screen[v.name] = v

urlpatterns = [
    url(r'%s/(?P<case>\d+)/$' % View.name,
        never_cache(View.as_view()),
        name=View.name
        )
    for View in screen_views
]
