# Python imports
import datetime
import random

# 3rd party imports
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now
from pytz import timezone

# Project imports
from civil_registry.models import Citizen
from civil_registry.tests.factories import CitizenFactory
from libya_elections.constants import CENTER_ID_MAX_INT_VALUE, CENTER_ID_MIN_INT_VALUE, \
    MESSAGE_1, FEMALE, MALE, INCOMING, SPLIT_CENTER_SUBCONSTITUENCY_ID, FIRST_PERIOD_NUMBER, \
    LAST_PERIOD_NUMBER
from polling_reports.models import CenterClosedForElection, StaffPhone, PollingReport, \
    CenterOpen, PreliminaryVoteCount
from register.models import Constituency, Office, Person, Registration, RegistrationCenter, SMS, \
    SubConstituency, Whitelist
from register.tests.base import PAST_DAY
from register.tests.factories import OfficeFactory, ConstituencyFactory, SubConstituencyFactory, \
    BackendFactory
from reporting_api.reports import empty_report_store
from voting.models import Election
from voting.tests.factories import ElectionFactory


DEFAULT_NUM_REGISTRATIONS = 250
DEFAULT_NUM_REGISTRATION_CENTERS = 15
DEFAULT_NUM_COPY_CENTERS = -1  # trigger use of a heuristic by default
# We can mark some centers as not supporting registrations
DEFAULT_NUM_NO_REG_CENTERS = -1  # trigger use of a heuristic by default
NUM_RANDOM_SMS_MESSAGES = 200
# The vr-dashboard's weekly report displays the last 7 days, except
# during the first week when there aren't as many.
DEFAULT_NUM_REGISTRATION_DATES = 6
DEFAULT_NUM_DAILY_REPORTS = 100
# Distributing among more than one subconstituency is useful for checking
# sort order.
DEFAULT_NUM_SUBCONSTITUENCIES = 1
# We can mark some centers inactive for the elections we create.
DEFAULT_NUM_INACTIVE_PER_ELECTION = 0

# DAYS_BETWEEN_REGISTRATIONS is the interval between days that have registrations;
# making it > 1 gets days-with-registrations out of sync with calendar-days
DAYS_BETWEEN_REGISTRATIONS = 1
# Libyan cell phone: 2189xxxxxxx
# Libyan satellite phone: 88216????????
# Note: phone numbers may not contain whitespace
VOTER_PHONE_NUMBER_PATTERN = '88216%08d'
STAFF_PHONE_NUMBER_PATTERN = '2189%08d'
# destination phone numbers for various types of messages (value not critical)
REGISTRATION_PHONE_NUMBER = '12345678'
POLLING_REPORT_PHONE_NUMBER = '23456789'
ACTIVATE_PHONE_NUMBER = '34567890'
RANDOM_MESSAGE_PHONE_NUMBER = '45678901'
PRELIMINARY_VOTE_COUNT_PHONE_NUMBER = '56789012'
# Real centers don't use this id
UNUSED_CENTER_ID = CENTER_ID_MAX_INT_VALUE


def delete(delete_infra=True):
    # Registrations link to Citizens
    Registration.objects.unfiltered().delete()
    # Persons link to Citizens
    Person.objects.unfiltered().delete()
    Citizen.objects.all().delete()
    StaffPhone.objects.unfiltered().delete()
    if delete_infra:
        RegistrationCenter.objects.unfiltered().delete()
    SMS.objects.unfiltered().delete()
    CenterOpen.objects.unfiltered().delete()
    PollingReport.objects.unfiltered().delete()
    PreliminaryVoteCount.objects.unfiltered().delete()
    CenterClosedForElection.objects.unfiltered().delete()
    Election.objects.unfiltered().delete()
    Whitelist.objects.unfiltered().delete()


def ensure_staff_phone_exists(staff_phone_number, center, staff_phones, creation_date=None):
    """ Given a staff phone number and center, ensure that a corresponding StaffPhone
    exists.  White-list about half of them, and maintain a list of StaffPhones that
    have been created.
    """
    staff_phone = StaffPhone(phone_number=staff_phone_number, registration_center=center)
    try:
        staff_phone.full_clean()
    except ValidationError:
        return  # assume staff phone exists
    if creation_date:
        staff_phone.creation_date = creation_date
    staff_phone.save()

    staff_phones.append(staff_phone)

    # white-list half of them
    if random.choice((1, 2)) == 1:
        w = Whitelist(phone_number=staff_phone.phone_number)
        w.full_clean()
        w.save()


def create(center_without_office=False,
           num_copy_centers=DEFAULT_NUM_COPY_CENTERS,
           num_registrations=DEFAULT_NUM_REGISTRATIONS,
           num_registration_dates=DEFAULT_NUM_REGISTRATION_DATES,
           num_daily_reports=DEFAULT_NUM_DAILY_REPORTS,
           num_registration_centers=DEFAULT_NUM_REGISTRATION_CENTERS,
           num_subconstituencies=DEFAULT_NUM_SUBCONSTITUENCIES,
           use_existing_infra=False,
           num_inactive_centers_per_election=DEFAULT_NUM_INACTIVE_PER_ELECTION,
           num_no_reg_centers=DEFAULT_NUM_NO_REG_CENTERS,
           election_dates=()):

    assert settings.ENVIRONMENT not in ('production', 'testing')

    delete(delete_infra=not use_existing_infra)
    empty_report_store()  # Remove any old data from Redis

    # Figure out ~10% of "normal" centers...
    fraction_of_normal_centers = \
        max(1, int(0.1 * num_registration_centers)) if num_registration_centers else 0

    # If numbers of some weird center types weren't specified, use a small
    # fraction of normal centers.
    if num_copy_centers == DEFAULT_NUM_COPY_CENTERS:
        num_copy_centers = fraction_of_normal_centers
    if num_no_reg_centers == DEFAULT_NUM_NO_REG_CENTERS:
        num_no_reg_centers = fraction_of_normal_centers

    carrier = BackendFactory()

    if election_dates:
        elections = [
            ElectionFactory(
                polling_start_time=election_date.replace(hour=8),
                polling_end_time=election_date.replace(hour=20)
            )
            for election_date in election_dates
        ]
    else:
        election_date = PAST_DAY.replace(hour=8, microsecond=123456)
        election = ElectionFactory(
            polling_start_time=election_date,
            polling_end_time=election_date.replace(hour=20)
        )
        elections = (election,)

    if not use_existing_infra:
        OfficeFactory()
        ConstituencyFactory(name_english='first')
        SubConstituencyFactory(name_english='Benghazi')

    offices = Office.objects.all()
    copy_centers = []
    no_reg_centers = []
    staff_phones = []

    if use_existing_infra:
        # Pick centers that support registrations at random.
        ordinary_centers = RegistrationCenter.objects.filter(reg_open=True)\
            .exclude(center_type=RegistrationCenter.Types.COPY)\
            .order_by('?')[:num_registration_centers]
        if num_copy_centers:  # user wants some, but there might not be any
            copy_centers = RegistrationCenter.objects.\
                filter(reg_open=True, center_type=RegistrationCenter.Types.COPY)\
                .order_by('?')[:num_copy_centers]
        if num_no_reg_centers:  # user wants some, but there might not be any
            no_reg_centers = RegistrationCenter.objects.\
                filter(reg_open=False).order_by('?')[:num_no_reg_centers]
        # why like this? sliced queries and/or list
        all_kinds_of_centers = \
            list(ordinary_centers) + list(copy_centers) + list(no_reg_centers)
    else:
        subconstituencies = SubConstituency.objects.exclude(pk=SPLIT_CENTER_SUBCONSTITUENCY_ID)
        subconstituencies = subconstituencies[:num_subconstituencies]

        constituencies = Constituency.objects.all()

        ordinary_centers = []
        for i in range(num_registration_centers):
            constituency = random.choice(constituencies)
            subconstituency = random.choice(subconstituencies)

            rc = RegistrationCenter(name='polling-center-%d' % i,
                                    center_id=CENTER_ID_MIN_INT_VALUE + i,
                                    constituency=constituency,
                                    subconstituency=subconstituency,
                                    office=random.choice(offices))
            rc.full_clean()
            rc.save()
            ordinary_centers.append(rc)

        for i in range(num_copy_centers):
            original = random.choice(ordinary_centers)
            # XXX This doesn't handle accidentally making too many copies of the same
            #     center, so make sure --num-centers is "big enough" w.r.t. --num-copy-centers.
            new_center_id = CENTER_ID_MIN_INT_VALUE + num_registration_centers + i
            copy = RegistrationCenter(name='Copy of %s' % original.name,
                                      center_id=new_center_id,
                                      constituency=original.constituency,
                                      subconstituency=original.subconstituency,
                                      office=original.office,
                                      center_type=RegistrationCenter.Types.COPY,
                                      copy_of=original)
            copy.full_clean()
            copy.save()
            copy_centers.append(copy)

        for i in range(num_no_reg_centers):
            constituency = random.choice(constituencies)
            subconstituency = random.choice(subconstituencies)
            center_id = CENTER_ID_MIN_INT_VALUE + num_registration_centers + num_copy_centers + i
            rc = RegistrationCenter(name='no-reg-polling-center-%d' % i,
                                    center_id=center_id,
                                    constituency=constituency,
                                    subconstituency=subconstituency,
                                    office=random.choice(offices),
                                    reg_open=False)
            rc.full_clean()
            rc.save()
            no_reg_centers.append(rc)

        all_kinds_of_centers = \
            ordinary_centers + copy_centers + no_reg_centers

    if center_without_office:
        try:
            # by not specifying office and other infra, it will be "standalone"
            rc = RegistrationCenter(name='dummy-registration-center',
                                    center_id=UNUSED_CENTER_ID)
            rc.full_clean()
            rc.save()
        except ValidationError:
            pass  # assume that it already exists

    for election in elections:
        num_daily_reports_on_election_day = int(round(0.9 * num_daily_reports))
        centers_reported = set()
        for i in range(num_daily_reports_on_election_day):
            staff_phone_number = STAFF_PHONE_NUMBER_PATTERN % i
            from_center = random.choice(all_kinds_of_centers)
            ensure_staff_phone_exists(staff_phone_number, from_center, staff_phones,
                                      election.work_start_time + datetime.timedelta(minutes=5))

            # split votes between two options
            number_of_votes = (random.randint(1, 100), random.randint(1, 100))
            random_period_number = random.randint(FIRST_PERIOD_NUMBER, LAST_PERIOD_NUMBER)
            pr = PollingReport(election=election,
                               phone_number=staff_phone_number,
                               registration_center=from_center,
                               period_number=random_period_number,
                               num_voters=sum(number_of_votes),
                               creation_date=election.polling_start_time)
            pr.full_clean()
            pr.save()
            s = SMS(from_number=staff_phone_number, to_number=POLLING_REPORT_PHONE_NUMBER,
                    direction=INCOMING, message='my message', msg_type=SMS.POLLING_REPORT,
                    message_code=MESSAGE_1, carrier=carrier,
                    creation_date=election.polling_start_time)
            s.full_clean()
            s.save()

            if from_center in centers_reported:
                continue  # can't send but one PreliminaryVoteCount from a center

            # send a corresponding vote count
            for option, votes_for_option in enumerate(number_of_votes, start=1):
                pvc = PreliminaryVoteCount(election=election,
                                           phone_number=staff_phone_number,
                                           registration_center=from_center,
                                           option=option,
                                           num_votes=votes_for_option,
                                           creation_date=election.polling_start_time)
                pvc.full_clean()
                pvc.save()
                s = SMS(from_number=staff_phone_number,
                        to_number=PRELIMINARY_VOTE_COUNT_PHONE_NUMBER,
                        # XXX no specific message type for PreliminaryVoteCount
                        direction=INCOMING, message='my message', msg_type=SMS.POLLING_REPORT,
                        message_code=MESSAGE_1, carrier=carrier,
                        creation_date=election.polling_start_time)
                s.full_clean()
                s.save()

            centers_reported.add(from_center)

        # some daily reports on the day after
        for i in range(num_daily_reports - num_daily_reports_on_election_day):
            staff_phone_number = STAFF_PHONE_NUMBER_PATTERN % i
            rc = random.choice(all_kinds_of_centers)
            ensure_staff_phone_exists(staff_phone_number, rc, staff_phones,
                                      election.work_start_time + datetime.timedelta(minutes=5))
            report_creation_date = election.polling_start_time + datetime.timedelta(days=1)
            pr = PollingReport(election=election,
                               phone_number=staff_phone_number,
                               registration_center=rc,
                               period_number=LAST_PERIOD_NUMBER,  # day after counts as last period
                               num_voters=random.randint(1, 50),
                               creation_date=report_creation_date)
            pr.full_clean()
            pr.save()
            s = SMS(from_number=staff_phone_number, to_number=POLLING_REPORT_PHONE_NUMBER,
                    direction=INCOMING, message='my message', msg_type=SMS.POLLING_REPORT,
                    message_code=MESSAGE_1, carrier=carrier,
                    creation_date=election.polling_start_time)
            s.full_clean()
            s.save()

        # Tag some centers as inactive for the election.  We may or may not pick some that
        # sent messages as being inactive.
        num_inactive_centers_per_election = \
            min(num_inactive_centers_per_election, len(all_kinds_of_centers))
        if num_inactive_centers_per_election:
            reordered = all_kinds_of_centers
            random.shuffle(reordered)
            for i in range(num_inactive_centers_per_election):
                inactive_on_election = CenterClosedForElection(
                    registration_center=reordered[i], election=election
                )
                inactive_on_election.full_clean()
                inactive_on_election.save()

    tz = timezone(settings.TIME_ZONE)
    # construct a datetime that will change based on timezone discrepancies
    # 0-2am in Libya has a different date than the same time in UDT or EDT
    today_fragile = now().astimezone(tz).replace(hour=0, minute=59)

    # tz.normalize fixes up the date arithmetic when crossing DST boundaries
    creation_dates = \
        [tz.normalize((today_fragile
                       - datetime.timedelta(days=DAYS_BETWEEN_REGISTRATIONS * i)).astimezone(tz))
         for i in range(num_registration_dates)]

    citizens = []
    existing_civil_registry_ids = []
    for i in range(num_registrations):
        # about 60% of registrations are for males, just as with actual data
        gender = MALE if random.randint(1, 100) <= 60 else FEMALE
        nat_id = '%d%011d' % (gender, i)

        creation_date = random.choice(creation_dates)
        modification_date = creation_date

        # Select voter ages from 18 years on up.
        voter_age = random.randint(18, 99)
        # If they were a certain age at any time yesterday, they are certainly that age at any time
        # today.
        yesterday = datetime.datetime.now().replace(tzinfo=tz) - datetime.timedelta(days=1)
        birth_date = datetime.date(yesterday.year - voter_age, yesterday.month, yesterday.day)
        civil_registry_id = random.randint(1, 99999999)
        # make sure we don't generate a duplicate key error
        while civil_registry_id in existing_civil_registry_ids:
            civil_registry_id = random.randint(1, 99999999)
        citizen = CitizenFactory(civil_registry_id=civil_registry_id, national_id=nat_id,
                                 gender=gender, birth_date=birth_date)
        citizens.append(citizen)
        s = SMS(from_number=VOTER_PHONE_NUMBER_PATTERN % i, to_number=REGISTRATION_PHONE_NUMBER,
                citizen=citizen, direction=INCOMING,
                message='my reg message', msg_type=SMS.REGISTRATION, message_code=MESSAGE_1,
                carrier=carrier, creation_date=creation_date)
        s.full_clean()
        s.save()

        rc = random.choice(list(ordinary_centers))

        confirmed = random.randint(1, 100) <= 80  # most are confirmed
        if confirmed:
            archive_time = None
        else:
            archive_time = random.choice(creation_dates)
        r = Registration(citizen=citizen, registration_center=rc, sms=s,
                         archive_time=archive_time,
                         creation_date=creation_date, modification_date=modification_date)
        r.full_clean()
        r.save()

    if num_registrations:  # if any data being generated
        # generate a variety of sms messages
        for i in range(NUM_RANDOM_SMS_MESSAGES):
            sms_type = random.choice(SMS.MESSAGE_TYPES)[0]
            staff_phone = random.choice(staff_phones)
            s = SMS(from_number=staff_phone.phone_number, to_number=RANDOM_MESSAGE_PHONE_NUMBER,
                    citizen=random.choice(citizens), direction=INCOMING,
                    message='my long random message',
                    msg_type=sms_type, message_code=MESSAGE_1, carrier=carrier,
                    creation_date=random.choice(creation_dates))
            s.full_clean()
            s.save()

        for election in elections:
            for rc in ordinary_centers:
                i = random.randint(8888, 9999)
                staff_phone_number = STAFF_PHONE_NUMBER_PATTERN % i
                ensure_staff_phone_exists(staff_phone_number, rc, staff_phones,
                                          election.work_start_time + datetime.timedelta(minutes=5))
                center_open = CenterOpen(
                    election=election,
                    phone_number=staff_phone_number, registration_center=rc,
                    creation_date=election.polling_start_time.replace(hour=random.randint(0, 10),
                                                                      minute=23))
                center_open.full_clean()
                center_open.save()
                s = SMS(from_number=staff_phone_number, to_number=ACTIVATE_PHONE_NUMBER,
                        direction=INCOMING, message='my message', msg_type=SMS.ACTIVATE,
                        message_code=MESSAGE_1, carrier=carrier,
                        creation_date=election.polling_start_time)
                s.full_clean()
                s.save()
