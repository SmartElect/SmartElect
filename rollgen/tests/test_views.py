# Python imports
from collections import OrderedDict
import os.path
import shutil
import tempfile
from unittest.mock import Mock

# Django imports
from django.contrib.auth.models import Group
from django.http import Http404
from django.test import override_settings, TestCase, RequestFactory
from django.urls import reverse
from django.utils.timezone import now as django_now

# Project imports
from .base import TestJobBase, ResponseCheckerMixin
from .factories import generate_arabic_place_name
from ..constants import ROLLGEN_FLAG_FILENAME
from ..forms import NewJobForm
from ..job import Job
from ..utils import NoVotersError, handle_job_exception
from ..views import JobOverview, is_office_dir, is_rollgen_output_dir_decorator
from libya_site.tests.factories import UserFactory
from register.tests.factories import RegistrationCenterFactory

ROLLGEN_READ_VIEW_NAMES = ('overview', 'browse_job_offices', 'browse_job_centers',
                           'browse_office_view', 'serve_pdf', 'serve_zip', 'polling_csv', )
ROLLGEN_CREATE_VIEW_NAMES = ('new', )
ROLLGEN_ALL_VIEW_NAMES = ROLLGEN_READ_VIEW_NAMES + ROLLGEN_CREATE_VIEW_NAMES


class ViewsFunctionsTestCase(TestCase):
    """Exercise functions in views.py"""
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        # Clean up.
        shutil.rmtree(cls.temp_dir)

    def test_is_office_dir(self):
        """Exercise is_office_dir()"""
        # False for non-path
        self.assertFalse(is_office_dir('/this_path_does_not_exist/skjg/dfkgnl/dfgkjerh'))

        # False for path w/basename not an int
        path = os.path.join(self.temp_dir, 'aaa')
        os.mkdir(path)
        self.assertFalse(is_office_dir(path))

        # True for path w/integer basename
        path = os.path.join(self.temp_dir, '42')
        os.mkdir(path)
        self.assertTrue(is_office_dir(path))

    def test_is_rollgen_output_dir_decorator_positive_case(self):
        """ensure is_rollgen_output_dir_decorator() works"""
        job_name = 'this_is_a_rollgen_job'
        path = os.path.join(self.temp_dir, job_name)
        os.mkdir(path)
        with open(os.path.join(path, ROLLGEN_FLAG_FILENAME), 'w') as f:
            f.write(' ')

        func = Mock()
        decorated = is_rollgen_output_dir_decorator(func)
        factory = RequestFactory()
        with override_settings(ROLLGEN_OUTPUT_DIR=self.temp_dir):
            request = factory.get(reverse('rollgen:browse_job_offices', args=(job_name, )))
            decorated(request, dirname=job_name)
        self.assertTrue(func.called)

    def test_is_rollgen_output_dir_decorator_not_a_directory(self):
        """ensure is_rollgen_output_dir_decorator() 404s on a non-existent directory"""
        job_name = 'this_path_does_not_exist'

        func = Mock()
        decorated = is_rollgen_output_dir_decorator(func)
        factory = RequestFactory()
        with override_settings(ROLLGEN_OUTPUT_DIR=self.temp_dir):
            request = factory.get(reverse('rollgen:browse_job_offices', args=(job_name, )))
            with self.assertRaises(Http404):
                decorated(request, dirname=job_name)
        self.assertFalse(func.called)

    def test_is_rollgen_output_dir_decorator_not_a_rollgen_directory(self):
        """ensure is_rollgen_output_dir_decorator() 404s on a non-rollgen directory"""
        job_name = 'this_is_not_a_rollgen_job'
        path = os.path.join(self.temp_dir, job_name)
        os.mkdir(path)

        func = Mock()
        decorated = is_rollgen_output_dir_decorator(func)
        factory = RequestFactory()
        with override_settings(ROLLGEN_OUTPUT_DIR=self.temp_dir):
            request = factory.get(reverse('rollgen:browse_job_offices', args=(job_name, )))
            with self.assertRaises(Http404):
                decorated(request, dirname=job_name)
        self.assertFalse(func.called)


class ViewsFailedJobTestCase(ResponseCheckerMixin, TestJobBase):
    """Exercise views when a job has failed"""
    @property
    def faux_output_dir(self):
        return os.path.normpath(os.path.join(self.output_path, '..'))

    def setUp(self):
        super(ViewsFailedJobTestCase, self).setUp()
        self.user = UserFactory(password='kittens!')
        self.user.is_superuser = True
        self.user.save()
        self.assertTrue(self.client.login(username=self.user.username, password='kittens!'))

        # Generate a center with no voters to force an error when the job runs.
        self.no_voters_center = RegistrationCenterFactory(name=generate_arabic_place_name())

        phase = 'in-person'

        self.input_arguments['phase'] = phase
        self.input_arguments['center_ids'] = [self.no_voters_center.center_id]

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            self.job = Job(phase, [self.no_voters_center], self.input_arguments, self.user.username,
                           self.output_path)
            try:
                self.job.generate_rolls()
            except NoVotersError as exception:
                # This is expected. (In fact, it's the whole point of the test.)
                handle_job_exception(exception, self.job.output_path)

        self.dirname = os.path.basename(self.job.output_path)

    def test_browse_job_offices_view(self):
        """Generate a job offices view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_job_offices', args=(self.dirname, )))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/job_failed_view.html')
        context = response.context
        expected_keys = ('job', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(JobOverview(self.output_path).raw_metadata, context['job'].raw_metadata)

    def test_browse_job_centers_view(self):
        """Generate a job centers view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_job_centers', args=(self.dirname, )))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/job_failed_view.html')
        context = response.context
        expected_keys = ('job', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(JobOverview(self.output_path).raw_metadata, context['job'].raw_metadata)


class ViewsInProgressJobTestCase(ResponseCheckerMixin, TestJobBase):
    """Exercise views when a job is in progress"""
    @property
    def faux_output_dir(self):
        return os.path.normpath(os.path.join(self.output_path, '..'))

    def setUp(self):
        super(ViewsInProgressJobTestCase, self).setUp()
        self.user = UserFactory(password='kittens!')
        self.user.is_superuser = True
        self.user.save()
        self.assertTrue(self.client.login(username=self.user.username, password='kittens!'))

        # I would like to create an in-progress job "organically", but that's hard to do under
        # test conditions. Instead I simulate the conditions of in-progress job.
        with open(os.path.join(self.output_path, ROLLGEN_FLAG_FILENAME), 'w') as f:
            f.write(' ')

        self.dirname = os.path.basename(self.output_path)

    def test_overview_view(self):
        """Generate a job view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:overview'))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/overview.html')

        context = response.context
        expected_keys = ('jobs', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(1, len(context['jobs']))
        self.assertTrue(context['jobs'][0].in_progress)
        # There should not be a link to the job page.
        self.assertNotContains(response, reverse('rollgen:browse_job_offices',
                               args=(self.dirname, )))

    def test_browse_job_offices_view(self):
        """Generate a job offices view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_job_offices', args=(self.dirname, )))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/job_in_progress_view.html')
        context = response.context
        expected_keys = ('job', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertTrue(context['job'].in_progress)

    def test_browse_job_centers_view(self):
        """Generate a job centers view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_job_centers', args=(self.dirname, )))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/job_in_progress_view.html')
        context = response.context
        expected_keys = ('job', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertTrue(context['job'].in_progress)


class ViewsEmptyTestCase(ResponseCheckerMixin, TestJobBase):
    """Exercise views when the data directory is empty"""
    @property
    def faux_output_dir(self):
        return os.path.normpath(os.path.join(self.output_path, '..'))

    def setUp(self):
        super(ViewsEmptyTestCase, self).setUp()
        user = UserFactory(password='kittens!')
        user.is_superuser = True
        user.save()
        self.assertTrue(self.client.login(username=user.username, password='kittens!'))

    def test_overview_view(self):
        """Generate the overview view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:overview'))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/overview.html')

        context = response.context
        expected_keys = ('jobs', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(0, len(context['jobs']))


class ViewsNonEmptyTestCase(ResponseCheckerMixin, TestJobBase):
    """Exercise views when the data directory is not empty"""
    @property
    def faux_output_dir(self):
        return os.path.normpath(os.path.join(self.output_path, '..'))

    def setUp(self):
        super(ViewsNonEmptyTestCase, self).setUp()
        user = UserFactory(password='kittens!')
        user.is_superuser = True
        user.save()
        self.assertTrue(self.client.login(username=user.username, password='kittens!'))

        phase = 'in-person'

        self.input_arguments['phase'] = phase

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            self.job = Job(phase, [self.center], self.input_arguments, self.user.username,
                           self.output_path)
            self.job.generate_rolls()

        self.dirname = os.path.basename(self.job.output_path)

    def test_overview_view(self):
        """Generate the overview view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:overview'))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/overview.html')

        context = response.context

        expected_keys = ('jobs', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(1, len(context['jobs']))
        self.assertEqual(JobOverview(self.output_path).raw_metadata,
                         context['jobs'][0].raw_metadata)

    def test_new_view(self):
        """Generate the new job view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:new'))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/new.html')

        context = response.context

        expected_keys = ('form', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertIsInstance(context['form'], NewJobForm)

    def test_new_view_no_centers(self):
        """Pass criteria that generate no centers to the new job form and test output"""
        # This is the only validation that happens at the view level. All other validation happens
        # in the form.
        no_reg_center = RegistrationCenterFactory(reg_open=False)
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.post(reverse('rollgen:new'),
                                        {'name': 'kjghdhjdhjghfkjhgdf',
                                         'center_selection_type': 'by_center_text_list',
                                         'center_text_list': [str(no_reg_center.center_id)],
                                         'phase': 'polling',
                                         'forgive_no_voters': False,
                                         'forgive_no_office': False,
                                         }
                                        )

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/new.html')

        context = response.context

        expected_keys = ('form', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertIsInstance(context['form'], NewJobForm)
        self.assertFormError(response, 'form', None,
                             "The criteria you specified didn't match any active centres.")

    def test_browse_job_offices_view(self):
        """Generate a job offices view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_job_offices', args=(self.dirname, )))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/browse_job_offices.html')

        context = response.context
        expected_keys = ('job', 'offices', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertFalse(context['job'].in_progress)

        self.assertEqual(JobOverview(self.output_path).raw_metadata, context['job'].raw_metadata)
        self.assertEqual([self.center.office], context['offices'])

    def test_browse_job_centers_view(self):
        """Generate a job centers view and test the context it passes to the template"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_job_centers', args=(self.dirname, )))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/browse_job_centers.html')

        context = response.context
        expected_keys = ('job', 'offices', 'binned_center_ids', 'n_empty_centers', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertFalse(context['job'].in_progress)

        self.assertEqual(JobOverview(self.output_path).raw_metadata, context['job'].raw_metadata)
        self.assertEqual([self.center.office], context['offices'])
        self.assertEqual(0, context['n_empty_centers'])
        binned_center_ids = OrderedDict()
        url = reverse('rollgen:browse_office_view', args=[self.dirname, self.center.office.id])
        url += ('#c' + str(self.center.center_id))
        binned_center_ids[str(self.center.center_id)[:3]] = [(self.center.center_id, url)]
        self.assertEqual(binned_center_ids, context['binned_center_ids'])

    def test_browse_office_view(self):
        """Generate a browse office view and test the context it passes to the template"""
        office_id = self.center.office.id

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_office_view',
                                               args=(self.dirname, office_id)))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/browse_office.html')

        context = response.context

        expected_keys = ('job_url', 'files', 'office', 'job', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(reverse('rollgen:browse_job_offices', args=[self.dirname]),
                         context['job_url'])
        self.assertEqual(self.center.office, context['office'])
        self.assertEqual(JobOverview(self.output_path).raw_metadata, context['job'].raw_metadata)

        # context['files'] are a bunch of view.FileInfo objects. I test their attrs here.
        actual_files = context['files']
        self.assertEqual(2, len(actual_files))

        expected_filenames = sorted(['{}_book_f.pdf'.format(self.center.center_id),
                                     '{}_book_m.pdf'.format(self.center.center_id), ])
        actual_filenames = sorted([file_info.name for file_info in actual_files])
        self.assertEqual(expected_filenames, actual_filenames)
        self.assertEqual([3, 3], [file_info.n_pages for file_info in actual_files])
        # I don't know exactly how many bytes the PDF files will be, but I want to at least verify
        # they're in a sane range.
        for file_info in actual_files:
            self.assertGreaterEqual(300000, file_info.n_bytes)
            self.assertLessEqual(100000, file_info.n_bytes)

    def test_browse_office_view_bad_office_id(self):
        """Generate a browse office view with an invalid office id and ensure the response is 404"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_office_view',
                                               args=(self.dirname, 9999)))
        self.assertResponseNotFound(response)

    def test_browse_office_view_when_office_has_no_files(self):
        """Generate a browse office view for an office that has no files associated

        Note that the office-has-no-files state can only occur during the polling phase.
        """
        center = RegistrationCenterFactory()

        input_arguments = self.input_arguments.copy()
        input_arguments['forgive_no_voters'] = True
        input_arguments['phase'] = 'polling'
        input_arguments['center_ids'] = [center.center_id]

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            job = Job(input_arguments['phase'], [center], input_arguments, self.user.username,
                      self.output_path)
            job.generate_rolls()

        dirname = os.path.basename(job.output_path)

        office_id = center.office.id

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:browse_office_view',
                                               args=(dirname, office_id)))

        self.assertResponseOK(response)
        self.assertTemplateUsed(response, 'rollgen/browse_office.html')

        context = response.context

        expected_keys = ('job_url', 'files', 'office', 'job', )
        self.assertTrue(set(expected_keys) < set(context.keys()))
        self.assertEqual(reverse('rollgen:browse_job_offices', args=[dirname]), context['job_url'])
        self.assertEqual(center.office, context['office'])
        self.assertEqual(JobOverview(self.output_path).raw_metadata, context['job'].raw_metadata)
        self.assertContains(response, "There are no files for this office.")

    def test_serve_pdf(self):
        """Generate an open-this-PDF view and test the response, including headers"""
        office_id = self.center.office.id
        pdf_filename = '{}_book_f.pdf'.format(self.center.center_id)

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:serve_pdf',
                                               args=(self.dirname, office_id, pdf_filename)))

        self.assertResponseOK(response)
        self.assertEqual('application/pdf', response['Content-Type'])
        self.assertEqual('attachment; filename="{}"'.format(pdf_filename),
                         response['Content-Disposition'])
        self.assertEqual(b'%PDF', response.content[:4])
        self.assertGreaterEqual(300000, len(response.content))
        self.assertLessEqual(100000, len(response.content))

    def test_serve_pdf_bad_office_id(self):
        """Generate an open-this-PDF view with a bad office id and ensure the response is a 404"""
        pdf_filename = '{}_book_f.pdf'.format(self.center.center_id)

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:serve_pdf',
                                               args=(self.dirname, 9999, pdf_filename)))

        self.assertResponseNotFound(response)

    def test_serve_pdf_bad_filename(self):
        """Generate an open-this-PDF view with a bad filename and ensure the response is a 404"""
        office_id = self.center.office.id
        pdf_filename = '{}_zzzz.pdf'.format(self.center.center_id)

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:serve_pdf',
                                               args=(self.dirname, office_id, pdf_filename)))

        self.assertResponseNotFound(response)

    def test_serve_zip(self):
        """Generate a download-this-zip view and test the response, including headers"""
        office_id = self.center.office.id
        zip_filename = '{}.zip'.format(office_id)

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:serve_zip', args=(self.dirname, office_id)))

        self.assertResponseOK(response)
        self.assertEqual('application/zip', response['Content-Type'])
        self.assertEqual('attachment; filename="{}"'.format(zip_filename),
                         response['Content-Disposition'])
        # OK to ignore errors since this is a zipfile so we don't expect it to be in UTF-8. We only
        # care about the first 4 characters
        self.assertEqual('PK' + chr(0o3) + chr(0o4), response.content.decode(errors='ignore')[:4])
        # I don't know exactly how many bytes the ZIP file will be, but I want to at least verify
        # that it's in a sane range.
        self.assertGreaterEqual(500000, len(response.content))
        self.assertLessEqual(250000, len(response.content))

    def test_serve_zip_bad_filename(self):
        """Generate a download-this-zip view with a bad filename and ensure the response is a 404"""
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:serve_zip', args=(self.dirname, 9999)))
        self.assertResponseNotFound(response)

    def test_serve_metadata_csv(self):
        """Generate an view for the metadata CSV and test the response, including headers"""
        response = self.client.get(reverse('rollgen:polling_csv'))
        content = response.content.decode()

        expected_filename = 'metadata_polling_{}.csv'.format(django_now().strftime('%Y_%m_%d'))

        self.assertResponseOK(response)
        self.assertEqual('text/csv', response['Content-Type'])
        self.assertEqual('attachment; filename="{}"'.format(expected_filename),
                         response['Content-Disposition'])
        self.assertEqual('Centre #,', content[:9])
        self.assertGreaterEqual(500, len(content))
        self.assertLessEqual(100, len(content))


class LoginTestCase(ResponseCheckerMixin, TestCase):
    """Test that users not logged in get bounced to the login page for all rollgen views."""
    def test_views_require_login(self):
        """test that no rollgen views are available when not logged in"""
        for view_name in ROLLGEN_ALL_VIEW_NAMES:
            if view_name in ('browse_job_offices', 'browse_job_centers', ):
                args = ['abcdefg']
            elif view_name == 'browse_office_view':
                args = ['abcdefg', '42']
            elif view_name == 'serve_pdf':
                args = ['abcdefg', '42', 'foo.pdf']
            elif view_name == 'serve_zip':
                args = ['abcdefg', '42']
            else:
                args = []

            response = self.client.get(reverse('rollgen:' + view_name, args=args))
            self.assertResponseRedirectsToLogin(response)


class GroupMembershipNegativeTestCase(ResponseCheckerMixin, TestCase):
    """Test that a user not in a rollgen-specific group can't see any pages"""
    def setUp(self):
        super(GroupMembershipNegativeTestCase, self).setUp()
        password = 'alligators'
        self.user = UserFactory(password=password)
        self.assertTrue(self.client.login(username=self.user.username, password=password))

    def test_views_require_minimal_group_membership(self):
        """test that no rollgen views are available when user is not in appropriate groups"""
        for view_name in ROLLGEN_ALL_VIEW_NAMES:
            if view_name in ('browse_job_offices', 'browse_job_centers', ):
                args = ['abcdefg']
            elif view_name == 'browse_office_view':
                args = ['abcdefg', '42']
            elif view_name == 'serve_pdf':
                args = ['abcdefg', '42', 'foo.pdf']
            elif view_name == 'serve_zip':
                args = ['abcdefg', '42']
            else:
                args = []

            response = self.client.get(reverse('rollgen:' + view_name, args=args))
            self.assertResponseForbidden(response)


class GroupMembershipPositiveTestCase(ResponseCheckerMixin, TestJobBase):
    """Test that users with appropriate permissions can see stuff"""
    @property
    def faux_output_dir(self):
        return os.path.normpath(os.path.join(self.output_path, '..'))

    def login(self, login_as_superuser=False):
        """Create a user and log in."""
        self.user.is_superuser = login_as_superuser
        self.user.save()
        self.assertTrue(self.client.login(username=self.user.username, password=self.password))

    def setUp(self):
        super(GroupMembershipPositiveTestCase, self).setUp()
        self.login()

        phase = 'in-person'

        self.input_arguments['phase'] = phase

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            self.job = Job(phase, [self.center], self.input_arguments, self.user.username,
                           self.output_path)
            self.job.generate_rolls()

        self.dirname = os.path.basename(self.job.output_path)

    def test_views_allow_superuser(self):
        """test that all rollgen views are available to superusers"""
        self.login(login_as_superuser=True)
        office_id = str(self.center.office.id)
        for view_name in ROLLGEN_ALL_VIEW_NAMES:
            if view_name in ('browse_job_offices', 'browse_job_centers', ):
                args = [self.dirname]
            elif view_name == 'browse_office_view':
                args = [self.dirname, office_id]
            elif view_name == 'serve_pdf':
                args = [self.dirname, office_id, str(self.center.center_id) + '_book_f.pdf']
            elif view_name == 'serve_zip':
                args = [self.dirname, office_id]
            else:
                args = []

            with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
                response = self.client.get(reverse('rollgen:' + view_name, args=args))
                self.assertResponseOK(response)

    def test_views_for_rollgen_view_job_group(self):
        """test that most rollgen views are available to users in rollgen_view_job"""
        self.user.groups.add(Group.objects.get(name='rollgen_view_job'))
        office_id = str(self.center.office.id)
        for view_name in ROLLGEN_READ_VIEW_NAMES:
            if view_name in ('browse_job_offices', 'browse_job_centers', ):
                args = [self.dirname]
            elif view_name == 'browse_office_view':
                args = [self.dirname, office_id]
            elif view_name == 'serve_pdf':
                args = [self.dirname, office_id, str(self.center.center_id) + '_book_f.pdf']
            elif view_name == 'serve_zip':
                args = [self.dirname, office_id]
            else:
                args = []

            with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
                response = self.client.get(reverse('rollgen:' + view_name, args=args))
                self.assertResponseOK(response)

        # New/create rollgen should not be available
        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:new'))
            self.assertResponseForbidden(response)

    def test_views_for_rollgen_create_job_group(self):
        """test that all rollgen views are available to users in rollgen_create_job"""
        self.user.groups.add(Group.objects.get(name='rollgen_create_job'))
        office_id = str(self.center.office.id)
        for view_name in ROLLGEN_ALL_VIEW_NAMES:
            if view_name in ('browse_job_offices', 'browse_job_centers', ):
                args = [self.dirname]
            elif view_name == 'browse_office_view':
                args = [self.dirname, office_id]
            elif view_name == 'serve_pdf':
                args = [self.dirname, office_id, str(self.center.center_id) + '_book_f.pdf']
            elif view_name == 'serve_zip':
                args = [self.dirname, office_id]
            else:
                args = []

        with override_settings(ROLLGEN_OUTPUT_DIR=self.faux_output_dir):
            response = self.client.get(reverse('rollgen:' + view_name, args=args))
            self.assertResponseOK(response)
