# 3rd party imports
from django.db import connection

# Project imports
from register.models import Office, SubConstituency
from .utils import dictfetchall


def _get_registration_centers(must_allow_registrations=True):
    """This returns a dict populated by data from the table register_registrationcenter. The
    dict is keyed by center_id; values are 4-tuples:
    (office_id, center_type, subconstituency_id, center id of copied center (or None))
    e.g. -- 11001: (2, 1, 48, None)

    The returned dict represents non-deleted centers, possibly filtered by whether or not
    they support registrations.  A copy center will be reported even if its original center
    doesn't support registrations or is deleted.

    must_allow_registrations: Whether or not the centers allow registrations
    """

    # In the query, "center" refers to any active, non-deleted center, which may or may
    # not be a copy center; when "center" is a copy center, "original" refers to the
    # center which it is a copy of.  (original.center_id will be null if center is not
    # a copy center.)
    inserted_clause = ' center.reg_open = true AND ' if must_allow_registrations else ''
    sql = """SELECT
                 center.center_id, center.center_type, center.office_id,
                 center.subconstituency_id, original.center_id as original_center_id
             FROM
                 (SELECT * FROM register_registrationcenter c) AS center
             LEFT JOIN
                 (SELECT id, center_id FROM register_registrationcenter o) AS original
             ON center.copy_of_id = original.id
             WHERE %s center.deleted = false""" % inserted_clause
    cursor = connection.cursor()
    cursor.execute(sql)
    rows = dictfetchall(cursor, date_time_columns=())
    d = {
        row['center_id']: (
            row['office_id'],
            row['center_type'],
            row['subconstituency_id'],
            row['original_center_id']
        )
        for row in rows
    }

    return d


def get_active_registration_locations():
    """Return all centers which are valid for registration (i.e., marked active).
    See _get_registration_centers() above for further details.)"""
    return _get_registration_centers(must_allow_registrations=True)


def get_all_polling_locations():
    """Return all centers, whether or not polling is planned at the center for
    a particular election.
    See _get_registration_centers() above for further details.)"""
    return _get_registration_centers(must_allow_registrations=False)


def get_offices():
    return [{'arabic_name': o.name_arabic,
             'english_name': o.name_english,
             'code': o.id} for o in Office.objects.all()]


def get_subconstituencies():
    return [{'arabic_name': s.name_arabic,
             'english_name': s.name_english,
             'code': s.id}
            for s in SubConstituency.objects.all()]
