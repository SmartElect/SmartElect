# Python imports
import collections
from functools import total_ordering
import json
import os
import zipfile

# 3rd party imports
from bread.bread import Bread, LabelValueReadView as BreadLabelValueReadView
from dateutil.parser import parse as dateutil_parse
import django_filters

# Django imports
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404, HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.utils.timezone import now as django_now
from django.utils.translation import ugettext as _

# Project imports
from .constants import METADATA_FILENAME, JOB_FAILURE_FILENAME
from .forms import NewJobForm
from .job import Job, INPUT_ARGUMENTS_TEMPLATE
from .models import Station
from .tasks import run_roll_generator_job
from .templatetags.rollgen_tags import center_anchor
from .utils import is_rollgen_output_dir, is_intable, generate_polling_metadata_csv
from libya_elections.constants import GENDER_MAP
from libya_elections.libya_bread import PaginatedBrowseView, StaffBreadMixin
from libya_elections.utils import get_verbose_name
from register.models import Office, RegistrationCenter
from voting.models import Election


def parse_filename(filename):
    """Given the partially qualified name of a PDF file, return office id, center_id, and filename.

    A partially qualified filename is what's contained in the JSON file. It's relative to the
    job directory. e.g. "15/34149_1_book.pdf"
    """
    office_id, filename = os.path.split(filename)
    office_id = int(office_id)
    center_id = center_id_from_filename(filename)

    return office_id, center_id, filename


def center_id_from_filename(filename):
    """Given the name of a rollgen PDF output file, return the center_id embedded in that name"""
    # Fortunately all filenames are of the format NNNNN_XXXXXX.pdf where NNNNN is the center id
    # and everything else comes after the first underscore.
    return int(filename[:filename.index('_')])


def componentize_path(path):
    """Given a path, return a list of the bits between the slashes

    e.g.  'out-2014-11-03.14-02-44-119589-caktus_philip/10/22400_1_book.pdf' ==>
         ['out-2014-11-03.14-02-44-119589-caktus_philip', '10', '22400_1_book.pdf']
    """
    components = []
    path, last = os.path.split(path)
    if last:
        components.append(last)
    while path and (path != os.path.sep):
        path, last = os.path.split(path)
        components.append(last)

    return components[::-1]


@total_ordering
class FileInfo(object):
    """A sortable container for some minimal information about a rollgen PDF output file"""
    def __init__(self, name, n_bytes, n_pages):
        self.name = name
        self.n_bytes = n_bytes
        self.n_pages = n_pages

    @property
    def center_id(self):
        """Return the int center_id implied by the filename, or None if the filename is blank"""
        if self.name:
            return center_id_from_filename(self.name)
        else:
            return None

    def __lt__(self, other):
        """__lt__() allows me to sort these objects by name with sorted()"""
        return self.name < other.name


class JobOverview(object):
    """Represents a summary of the rollgen job that resides in the path indicated.

    The dirname attribute is always populated. The other attributes (phase, start time, etc.) are
    populated under all but two conditions -- if the fail_message or in_progress attributes are
    populated, then the other attributes are not.
    """
    def __init__(self, path):
        self.dirname = ''
        self.fail_message = None
        self.in_progress = False
        self.raw_metadata = {}

        self.phase = ''
        self.start_time = None
        self.end_time = None

        self.n_files = 0
        self.n_pages = 0

        self.user = ''

        # self.offices maps office ids to register.models.Office instances
        self.offices = {}
        # self.files maps office ids to lists of FileInfo objects
        self.files = collections.defaultdict(lambda: [])
        # self.center_ids is a sorted list of ints
        self.center_ids = []
        # self.center_id_to_office_map maps int center ids to int office ids
        self.center_id_to_office_map = {}

        self.populate_from(path)

    @property
    def office_ids(self):
        return sorted(self.offices.keys())

    @property
    def offices_sorted(self):
        """Return office instances sorted by office id"""
        return [self.offices[key] for key in self.office_ids]

    @property
    def fq_path(self):
        return os.path.join(settings.ROLLGEN_OUTPUT_DIR, self.dirname)

    def populate_from(self, path):
        """Populate this job overview from the path indicated.

        If path doesn't start with ROLLGEN_OUTPUT_DIR, ROLLGEN_OUTPUT_DIR is prepended.
        """
        if not path.startswith(settings.ROLLGEN_OUTPUT_DIR):
            path = os.path.join(settings.ROLLGEN_OUTPUT_DIR, path)

        self.dirname = componentize_path(path)[-1]

        # See if fail info exists. If so, that trumps everything.
        filename = os.path.join(path, JOB_FAILURE_FILENAME)
        if os.path.exists(filename):
            # Uh oh.
            with open(filename, 'rb') as f:
                self.fail_message = f.read().decode('utf-8')
        else:
            filename = os.path.join(path, METADATA_FILENAME)

            if not os.path.exists(filename):
                self.in_progress = True
            else:
                with open(filename, 'rb') as f:
                    metadata = json.loads(f.read().decode('utf-8'))

                self.raw_metadata = metadata

                self.phase = metadata['input_arguments']['phase']

                self.start_time = dateutil_parse(metadata['time_information']['begin'])
                self.start_time.replace(microsecond=0)
                self.end_time = dateutil_parse(metadata['time_information']['end'])
                self.end_time.replace(microsecond=0)

                self.n_files = int(metadata['total_pdf_file_count'])
                self.n_pages = int(metadata['total_pdf_page_count'])

                self.user = metadata['user']

                for filename, file_d in metadata['files'].items():
                    office_id, center_id, filename = parse_filename(filename)

                    # Add to center==>office map
                    self.center_id_to_office_map[center_id] = office_id

                    if office_id not in self.files:
                        # This is an office id I haven't seen before
                        self.files[office_id] = []

                    # Record info about this file
                    file_info = FileInfo(filename, int(file_d['size']), int(file_d['n_pages']))
                    self.files[office_id].append(file_info)

                for office_id in self.files:
                    self.files[office_id].sort()

                # Offices are stashed in the metadata so that even if an office changes, this
                # rollgen data will represent what existed at the time the job was run.
                self.offices = {int(office['id']): Office(**office) for office in
                                metadata['offices']}

                self.center_ids = metadata['registration_centers_processed']
                self.center_ids.sort()

    def bin_center_ids(self):
        """Return a dict mapping hashed center ids to lists of tuples of info about each center.

        The hash/binning function simply uses the first 3 digits of the center id. The dict is
        ordered by (hashed) center id. The dict values are ordered lists of 2-tuples of
        (center_id, URL). See build_anchored_url() for URL details.
        """
        n_empty_centers = 0

        binned = collections.OrderedDict()
        for center_id in self.center_ids:
            hash_ = str(center_id)[:3]
            if hash_ not in binned:
                binned[hash_] = []

            if center_id in self.center_id_to_office_map:
                url = self.build_anchored_url(center_id)
            else:
                # This can happen when a center has no registrants. (This implies that
                # rollgen was run with forgive-no-voters=true.) In such case there will be no
                # PDFs produced for that center so it won't appear in any office.
                n_empty_centers += 1
                url = None

            binned[hash_].append((center_id, url))

        return binned, n_empty_centers

    def build_anchored_url(self, center_id):
        """Given an int center id, return a URL pointing to the center's docs in the office.

        The URL points to the browse office page for the appropriate office and contains an
        in-page anchor to get it to exactly the right section of the page.
        """
        # Build a URL that points to the browse page for the office related to this center.
        reverse_args = [self.dirname, self.center_id_to_office_map[center_id]]
        url = reverse('rollgen:browse_office_view', args=reverse_args)
        # Add to that URL an in-page anchor that links to the first mention of this center id.
        url += ('#' + center_anchor(center_id))

        return url


def is_office_dir(path):
    """Given a fully-qualified path, return true if it looks like an office dir, false otherwise"""
    return os.path.isdir(path) and is_intable(os.path.basename(path))


def is_rollgen_output_dir_decorator(func):
    """A view decorator that 404s if the dirname view param doesn't look like rollgen output"""
    def wrapper(*args, **kwargs):
        dirname = kwargs['dirname']
        # The regexes in urls.py should prevent any nefarious URLs from sneaking through, but as a
        # better-safe-than-sorry measure I will use basename() here to short circuit any attempt
        # to fish for ../../etc/passwd and the like.
        if dirname != os.path.basename(dirname):
            raise Http404()

        if not is_rollgen_output_dir(dirname):
            raise Http404()

        return func(*args, **kwargs)

    return wrapper


def can_view_rollgen_decorator(func):
    """A view decorator that 403s if the user isn't in the appropriate groups.

    The groups that allow access are rollgen_view_job and rollgen_create_job. (Create implies
    view permission.)

    Note that this is 403 (Permission Denied).
    """
    def wrapper(request, *args, **kwargs):
        group_names = ('rollgen_view_job', 'rollgen_create_job')
        if request.user.is_superuser or request.user.groups.filter(name__in=group_names).exists():
            return func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden(
                _("You do not have permission to view roll generator output."))

    return wrapper


def can_create_rollgen_decorator(func):
    """A view decorator that 403s if the user isn't in the rollgen_create_job group.

    Note that this is 403 (Permission Denied).
    """
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser or \
           request.user.groups.filter(name='rollgen_create_job').exists():
            return func(request, *args, **kwargs)
        else:
            return HttpResponseForbidden(_("You do not have permission to run the roll generator."))

    return wrapper


@login_required
@can_view_rollgen_decorator
def overview_view(request):
    """Generate the overview which gives options to start a new run and browse old ones."""
    dirnames = os.listdir(settings.ROLLGEN_OUTPUT_DIR)

    dirnames = [dirname for dirname in dirnames if is_rollgen_output_dir(dirname)]

    jobs = []
    for dirname in dirnames:
        job = JobOverview(os.path.join(settings.ROLLGEN_OUTPUT_DIR, dirname))
        jobs.append(job)

    if Election.objects.get_most_current_election():
        polling_csv_url = reverse('rollgen:polling_csv')
        new_url = reverse('rollgen:new')
    else:
        new_url = None
        polling_csv_url = None

    context = {'jobs': jobs,
               'polling_csv_url': polling_csv_url,
               'new_url': new_url,
               'staff_page': True,
               }

    return render(request, 'rollgen/overview.html', context)


@login_required
@can_view_rollgen_decorator
@is_rollgen_output_dir_decorator
def browse_job_offices_view(request, dirname):
    job = JobOverview(dirname)

    if job.fail_message:
        template = 'rollgen/job_failed_view.html'
        context = {'job': job, }
    elif job.in_progress:
        # When a job is in progress, the overview doesn't even offer a URL to it, but persistent
        # users can still get to the job view by pasting the job's dir name into the URL.
        template = 'rollgen/job_in_progress_view.html'
        context = {'job': job, }
    else:
        template = 'rollgen/browse_job_offices.html'

        offices = job.offices_sorted

        for office in offices:
            office.zip_file_url = request.path + '{}.zip'.format(office.id)

        context = {'job': job,
                   'offices': offices,
                   'staff_page': True,
                   }

    return render(request, template, context)


@login_required
@can_view_rollgen_decorator
@is_rollgen_output_dir_decorator
def browse_job_centers_view(request, dirname):
    job = JobOverview(dirname)

    if job.fail_message:
        template = 'rollgen/job_failed_view.html'
        context = {'job': job, }
    elif job.in_progress:
        # When a job is in progress, the overview doesn't even offer a URL to it, but persistent
        # users can still get to the job view by pasting the job's dir name into the URL.
        template = 'rollgen/job_in_progress_view.html'
        context = {'job': job, }
    else:
        template = 'rollgen/browse_job_centers.html'

        offices = job.offices_sorted

        binned, n_empty_centers = job.bin_center_ids()

        context = {'job': job,
                   'offices': offices,
                   'binned_center_ids': binned,
                   'n_empty_centers': n_empty_centers,
                   }
    context['staff_page'] = True

    return render(request, template, context)


@login_required
@can_view_rollgen_decorator
@is_rollgen_output_dir_decorator
def browse_office_view(request, dirname, office_id):
    """display the view of this office (list available PDFs)"""
    job = JobOverview(dirname)

    office_id = int(office_id)

    if office_id not in job.office_ids:
        raise Http404

    office = job.offices[office_id]

    files = job.files[office_id]

    # Each FileInfo object gets an extra attribute here called first_instance_of_this_center
    # so that the template knows which ones should get anchors.
    current_center_id = 0
    for file_ in files:
        if file_.center_id != current_center_id:
            file_.first_instance_of_this_center = True
            current_center_id = file_.center_id
        else:
            file_.first_instance_of_this_center = False

    job_url = reverse('rollgen:browse_job_offices', args=[job.dirname])

    context = {'job_url': job_url,
               'files': files,
               'office': office,
               'job': job,
               'staff_page': True,
               }

    return render(request, 'rollgen/browse_office.html', context)


@login_required
@can_view_rollgen_decorator
@is_rollgen_output_dir_decorator
def serve_pdf(request, dirname, office_id, filename):
    """Deliver the PDF described by filename"""
    job = JobOverview(dirname)

    zipname = os.path.join(job.fq_path, office_id + '.zip')

    if not os.path.exists(zipname):
        raise Http404

    with zipfile.ZipFile(zipname, 'r') as z:
        try:
            with z.open(filename, 'r') as f:
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)
                response.write(f.read())
                return response
        except KeyError:
            # The named file doesn't exist in the PDF.
            raise Http404


@login_required
@can_view_rollgen_decorator
@is_rollgen_output_dir_decorator
def serve_zip(request, dirname, office_id):
    """Deliver the ZIP file for this office"""
    job = JobOverview(dirname)

    zipname = os.path.join(job.fq_path, office_id + '.zip')

    if not os.path.exists(zipname):
        raise Http404

    with open(zipname, 'rb') as f:
        response = HttpResponse(content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="{}.zip"'.format(office_id)
        response.write(f.read())
        return response


@login_required
@can_create_rollgen_decorator
def new_view(request):
    """Render the view that allows users to start a new rollgen"""
    if request.method == 'POST':
        form = NewJobForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['center_selection_type'] == 'all':
                centers = RegistrationCenter.objects.all()
            elif form.cleaned_data['center_selection_type'] == 'by_constituency':
                constituencies = form.cleaned_data['constituencies']
                centers = RegistrationCenter.objects.filter(constituency__in=constituencies)
            elif form.cleaned_data['center_selection_type'] == 'by_office':
                centers = RegistrationCenter.objects.filter(office__in=form.cleaned_data['offices'])
            elif form.cleaned_data['center_selection_type'] == 'by_center_select_list':
                centers = form.cleaned_data['center_select_list']
            elif form.cleaned_data['center_selection_type'] == 'by_center_text_list':
                center_ids = form.cleaned_data['center_text_list']
                centers = RegistrationCenter.objects.filter(center_id__in=center_ids)

            centers = centers.filter(reg_open=True).all()

            if not centers:
                msg = _("The criteria you specified didn't match any active centres.")
                form.add_error(None, msg)
            else:
                input_arguments = INPUT_ARGUMENTS_TEMPLATE.copy()
                input_arguments['phase'] = form.cleaned_data['phase']
                input_arguments['forgive_no_voters'] = form.cleaned_data['forgive_no_voters']
                input_arguments['forgive_no_office'] = form.cleaned_data['forgive_no_office']
                input_arguments['office_ids'] = [office.id for office in
                                                 form.cleaned_data['offices']]
                input_arguments['center_ids'] = [center.center_id for center in centers]

                job = Job(form.cleaned_data['phase'], centers, input_arguments,
                          request.user.username, os.path.join(settings.ROLLGEN_OUTPUT_DIR,
                          form.cleaned_data['name']))
                run_roll_generator_job.delay(job)
                return redirect('rollgen:overview')
    else:
        form = NewJobForm()

    context = {'form': form,
               'staff_page': True}

    return render(request, 'rollgen/new.html', context)


@login_required
@can_view_rollgen_decorator
def polling_csv_view(request):
    """Deliver the polling CSV file for the current election"""
    csv = generate_polling_metadata_csv()

    client_filename = 'metadata_polling_{}.csv'.format(django_now().strftime('%Y_%m_%d'))

    # Proper MIME type is text/csv. ref: http://tools.ietf.org/html/rfc4180
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(client_filename)
    response.write(csv)
    return response


class StationFilterSet(django_filters.FilterSet):
    class Meta:
        model = Station
        fields = ['election', 'center']


class StationBrowse(PaginatedBrowseView):
    filterset = StationFilterSet


class StationRead(BreadLabelValueReadView):
    fields = ((get_verbose_name(Station, 'election'), 'election_as_html'),
              (get_verbose_name(Station, 'center'), 'registration_center_as_html'),
              (None, 'number'),
              (get_verbose_name(Station, 'gender'),
               lambda context: GENDER_MAP[context['object'].gender]),
              (None, 'n_registrants'),
              (None, 'first_voter_name'),
              (None, 'first_voter_number'),
              (None, 'last_voter_name'),
              (None, 'last_voter_number'),
              (get_verbose_name(Station, 'creation_date'), 'formatted_creation_date'),
              (get_verbose_name(Station, 'modification_date'), 'formatted_modification_date'),
              )


class StationBread(StaffBreadMixin, Bread):
    browse_view = StationBrowse
    read_view = StationRead
    model = Station
    views = 'BRD'
