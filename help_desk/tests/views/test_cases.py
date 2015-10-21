# Python imports
from datetime import timedelta

# Django imports
from django.core.urlresolvers import reverse
from django.test import TestCase
from django.utils.timezone import now

# This project's imports
from ..factories import CaseFactory, HelpDeskManagerFactory, HelpDeskUserFactory
from ...models import Update, Case
from ...utils import create_help_desk_groups
from civil_registry.tests.factories import CitizenFactory
from libya_elections.tests.utils import ResponseCheckerMixin
from libya_site.tests.factories import DEFAULT_USER_PASSWORD


class TestCaseViewsUnloggedIn(ResponseCheckerMixin, TestCase):
    def setUp(self):
        create_help_desk_groups()

    def test_case_list_requires_login(self):
        url = reverse('report_cases')
        self.assertRedirectsToLogin(self.client.get(url))

    def test_case_stats_requires_login(self):
        url = reverse('report_stats')
        self.assertRedirectsToLogin(self.client.get(url))

    def test_case_detail_requires_login(self):
        case = CaseFactory()
        url = reverse('case_detail', kwargs={'pk': case.pk})
        self.assertRedirectsToLogin(self.client.get(url))

    def test_case_update_requires_login(self):
        case = CaseFactory()
        url = reverse('case_update', kwargs={'case_pk': case.pk})
        self.assertRedirectsToLogin(self.client.get(url))


class TestCaseViews(TestCase):
    def setUp(self):
        create_help_desk_groups()
        self.manager = HelpDeskManagerFactory()
        assert self.client.login(
            username=self.manager.username,
            password=DEFAULT_USER_PASSWORD)

    def test_case_list_view(self):
        # An operator with no first or last name defined
        op_noname = HelpDeskUserFactory(first_name="", last_name="", username="My_user_name")
        CaseFactory(operator=op_noname)
        # An operator with first and last name
        op_name = HelpDeskUserFactory(first_name="My_first_name", last_name="My_last_name")
        CaseFactory(operator=op_name)
        for i in range(3):
            CaseFactory()
        rsp = self.client.get(reverse('report_cases'))
        self.assertEqual(5, len(rsp.context['object_list']))
        self.assertContains(rsp, op_noname.username)
        self.assertContains(rsp, "%s %s" % (op_name.first_name, op_name.last_name))

    def test_case_list_search(self):
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        target = CaseFactory(citizen=citizen)
        for i in range(4):
            # 4 more
            CaseFactory()
        rsp = self.client.get(reverse('report_cases') + "?q=doe")
        self.assertEqual(1, len(rsp.context['object_list']))
        obj = rsp.context['object_list'][0]
        self.assertEqual(target, obj)

    def test_case_list_number(self):
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        target = CaseFactory(citizen=citizen)
        for i in range(4):
            # 4 more
            CaseFactory()
        rsp = self.client.get(reverse('report_cases') + "?q=%d" % target.citizen.national_id)
        self.assertEqual(1, len(rsp.context['object_list']))
        obj = rsp.context['object_list'][0]
        self.assertEqual(target, obj)

    def test_case_list_open(self):
        target = CaseFactory(end_time=None)
        yesterday = now() - timedelta(days=1)
        for i in range(4):
            # 4 more
            CaseFactory(end_time=yesterday)
        rsp = self.client.get(reverse('report_cases') + "?status=open")
        self.assertEqual(1, len(rsp.context['object_list']))
        obj = rsp.context['object_list'][0]
        self.assertEqual(target, obj)

    def test_case_list_marked(self):
        target = CaseFactory(review_classification=Case.FOR_REVIEW)
        for i in range(4):
            # 4 more
            CaseFactory()
        rsp = self.client.get(reverse('report_cases') + "?status=marked")
        self.assertEqual(1, len(rsp.context['object_list']))
        obj = rsp.context['object_list'][0]
        self.assertEqual(target, obj)

    def test_case_list_recommended(self):
        target = CaseFactory(review_classification=Case.RECOMMENDED)
        for i in range(4):
            # 4 more
            CaseFactory()
        rsp = self.client.get(reverse('report_cases') + "?status=recommended")
        self.assertEqual(1, len(rsp.context['object_list']))
        obj = rsp.context['object_list'][0]
        self.assertEqual(target, obj)

    def test_case_list_complete(self):
        yesterday = now() - timedelta(days=1)
        target = CaseFactory(end_time=yesterday)
        for i in range(4):
            # 4 more
            CaseFactory(end_time=None)
        rsp = self.client.get(reverse('report_cases') + "?status=complete")
        if rsp.status_code == 302:
            self.fail("Redirected to %s" % rsp['Location'])
        self.assertEqual(200, rsp.status_code)
        self.assertEqual(1, len(rsp.context['object_list']))
        obj = rsp.context['object_list'][0]
        self.assertEqual(target, obj)

    def test_case_detail_view(self):
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        case = CaseFactory(citizen=citizen)
        rsp = self.client.get(reverse('case_detail', kwargs={'pk': case.pk}), follow=False)
        if rsp.status_code == 302:
            self.fail("Redirected to %s" % rsp['Location'])
        self.assertContains(rsp, 'John')

    def test_case_update_comment(self):
        # This adds an update record to a case, it doesn't update a case
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        case = CaseFactory(citizen=citizen)
        rsp = self.client.get(reverse('case_update', kwargs={'case_pk': case.pk}))
        self.assertContains(rsp, 'John')
        data = {
            'kind': Update.COMMENT,
            'comment': 'This is a sophisticated comment',
        }
        rsp = self.client.post(reverse('case_update', kwargs={'case_pk': case.pk}), data=data)
        update = Update.objects.get()
        self.assertEqual(self.manager, update.user)
        self.assertIn('sophisticated', update.comment)
        self.assertEqual(Update.COMMENT, update.kind)
        self.assertEqual(case, update.case)

    def test_case_update_mark_for_review(self):
        # This adds an update record to a case, it doesn't update a case
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        case = CaseFactory(citizen=citizen)
        rsp = self.client.get(reverse('case_update', kwargs={'case_pk': case.pk}))
        self.assertContains(rsp, 'John')
        data = {
            'kind': Update.MARK_FOR_REVIEW,
            'comment': 'This is a sophisticated comment',
        }
        rsp = self.client.post(reverse('case_update', kwargs={'case_pk': case.pk}), data=data)
        update = Update.objects.get()
        self.assertEqual(self.manager, update.user)
        self.assertIn('sophisticated', update.comment)
        self.assertEqual(Update.MARK_FOR_REVIEW, update.kind)
        self.assertEqual(case, update.case)
        case = Case.objects.get(pk=case.pk)
        self.assertEqual(Case.FOR_REVIEW, case.review_classification)

    def test_case_update_mark_recommended(self):
        # This adds an update record to a case, it doesn't update a case
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        case = CaseFactory(citizen=citizen, reason_marked='complaint',
                           review_classification=Case.FOR_REVIEW)
        rsp = self.client.get(reverse('case_update', kwargs={'case_pk': case.pk}))
        self.assertContains(rsp, 'John')
        data = {
            'kind': Update.RECOMMEND,
            'recommended_action': 'seen',
            'comment': 'This is a sophisticated comment',
        }
        rsp = self.client.post(reverse('case_update', kwargs={'case_pk': case.pk}), data=data)
        self.assertRedirects(rsp, case.get_absolute_url() + '#updates')
        update = Update.objects.get()
        self.assertEqual(self.manager, update.user)
        self.assertIn('sophisticated', update.comment)
        self.assertEqual(Update.RECOMMEND, update.kind)
        self.assertEqual(case, update.case)
        case = Case.objects.get(pk=case.pk)
        self.assertEqual(Case.RECOMMENDED, case.review_classification)

    def test_case_update_resolve(self):
        # This adds an update record to a case, it doesn't update a case
        citizen = CitizenFactory(family_name='Doe', first_name='John')  # factory
        case = CaseFactory(citizen=citizen, reason_marked='complaint',
                           review_classification=Case.FOR_REVIEW)
        rsp = self.client.get(reverse('case_update', kwargs={'case_pk': case.pk}))
        self.assertContains(rsp, 'John')
        data = {
            'kind': Update.RESOLVE,
            'comment': 'This is a sophisticated comment',
        }
        rsp = self.client.post(reverse('case_update', kwargs={'case_pk': case.pk}), data=data)
        update = Update.objects.get()
        self.assertEqual(self.manager, update.user)
        self.assertIn('sophisticated', update.comment)
        self.assertEqual(Update.RESOLVE, update.kind)
        self.assertEqual(case, update.case)
        case = Case.objects.get(pk=case.pk)
        self.assertEqual(Case.RESOLVED, case.review_classification)
