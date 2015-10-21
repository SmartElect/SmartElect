from django.core.urlresolvers import reverse
from django.test import TestCase

from help_desk.utils import create_help_desk_groups
from libya_site.tests.factories import DEFAULT_USER_PASSWORD

from ..factories import CaseFactory, HelpDeskUserFactory
from ...models import Case


class TestHomeView(TestCase):
    def setUp(self):
        create_help_desk_groups()
        self.operator = HelpDeskUserFactory()
        assert self.client.login(
            username=self.operator.username,
            password=DEFAULT_USER_PASSWORD)

    def test_nothing_in_progress(self):
        rsp = self.client.get(reverse('help_desk_home'))
        self.assertTemplateUsed(self, rsp, 'helpdesk/main.html')
        self.assertNotIn('in_progress', rsp.context)

    def test_case_in_progress(self):
        CaseFactory(operator=self.operator)
        rsp = self.client.get(reverse('help_desk_home'))
        self.assertTemplateUsed(self, rsp, 'helpdesk/main.html')
        in_progress = rsp.context['in_progress']
        self.assertTrue(in_progress)

    def test_start_call(self):
        self.client.get(reverse('start_case'))
        Case.objects.get(operator=self.operator)
