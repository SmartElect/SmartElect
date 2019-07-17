# flake8: noqa
# demographic breakdowns by day per registration center
from libya_elections.constants import FIRST_PERIOD_NUMBER, LAST_PERIOD_NUMBER


DEMO_QUERY = """SELECT DATE(register_registration.creation_date) AS reg_date,
                     gender,
                     DATE_PART('YEAR', AGE(birth_date)) AS age,
                     center_id,
                     COUNT(*)
              FROM register_registration
                   JOIN civil_registry_citizen AS citizen ON (register_registration.citizen_id = citizen.civil_registry_id)
                   JOIN register_registrationcenter ON (registration_center_id = register_registrationcenter.id)
                   WHERE register_registration.archive_time IS NULL
                   /* only centers supporting registrations (no oil centers, etc) */
                   AND register_registrationcenter.reg_open = true
                   AND register_registration.deleted = false
                   AND register_registrationcenter.deleted = false
                   /* only non-deleted centers */
              GROUP BY 1, 2, 3, 4;"""

# incoming message count by day per center
MESSAGES_QUERY = """SELECT DATE(creation_date) AS message_date,
                           direction,
                           msg_type,
                           COUNT(*)
                      FROM register_sms
                     WHERE direction = 1 /* incoming only */
                       AND deleted = false
                  GROUP BY 1, 2, 3;"""

# number of phones successfully registering people with more than one distinct family records
# modified from fraud query
PHONE_MULTIPLE_FAMILY_BOOK_QUERY = """SELECT DISTINCT sms.from_number,
                COUNT(DISTINCT citizen.fbr_number) as num_count,
                ARRAY_AGG(DISTINCT citizen.fbr_number) as num_list,
                MAX(sms.creation_date) as latest
              FROM register_sms AS sms
                JOIN register_registration AS reg ON (reg.sms_id = sms.id) /* successful registrations only */
                JOIN civil_registry_citizen AS citizen ON (reg.citizen_id = citizen.civil_registry_id)
              WHERE direction = 1 /* incoming */
              AND sms.deleted = false
              AND reg.deleted = false
              AND reg.archive_time IS NULL
              GROUP BY sms.from_number
              HAVING (COUNT(DISTINCT citizen.fbr_number)) > 1;"""

# number of phones sent the "NID already registered" message
# using the rapidsms logic
DUPLICATE_REGISTRATIONS_QUERY = """SELECT DISTINCT to_number,
            s.creation_date
            FROM register_sms s
            WHERE message_code = 3
            AND direction = 2 /* outgoing */
            AND deleted = false;"""

# number of registrations per phone number, limited to phone numbers with more than 1 registration
REGISTRATIONS_BY_PHONE_QUERY = """
    SELECT DISTINCT sms.from_number,
           COUNT(DISTINCT reg.id) as reg_count
      FROM register_sms AS sms
      JOIN register_registration AS reg ON (reg.sms_id = sms.id)
     WHERE direction = 1 /* incoming */
       AND sms.deleted = false
       AND reg.deleted = false
       AND reg.archive_time IS NULL
  GROUP BY sms.from_number
 HAVING COUNT(DISTINCT reg.id) > 1;"""

# datetime of first rollcall per center each day
CENTER_OPENS = """SELECT center.center_id AS polling_center_code,
                  DATE(rollcall.creation_date) as date,
                  MIN(rollcall.creation_date::TIME) AS opened
                  FROM polling_reports_centeropen AS rollcall
                  JOIN register_registrationcenter AS center ON (rollcall.registration_center_id = center.id)
                  WHERE rollcall.election_id = %(ELECTION_ID)s
                  AND rollcall.deleted = false
                  AND center.deleted = false
                  AND NOT EXISTS
                      (SELECT * FROM polling_reports_centerclosedforelection AS election_closure
                       WHERE election_closure.election_id = %(ELECTION_ID)s
                       AND election_closure.registration_center_id = center.id
                       AND election_closure.deleted = false)
                  GROUP BY 1,2
                  ORDER BY 2,1;"""

# process only those on election day
CENTER_VOTESREPORT = """SELECT r.center_id as polling_center_code,
                               p.date,
                               p.reported,
                               p.voting_period,
                               p.votes_reported
                        FROM (SELECT DISTINCT registration_center_id AS center_pk,
                                              creation_date::DATE AS date,
                                              creation_date::TIME AS reported,
                                              creation_date,
                                              row_number()
                                              OVER(PARTITION BY period_number,registration_center_id,creation_date::DATE
                                                   ORDER BY creation_date desc) as part,
                                              period_number as voting_period,
                                              num_voters AS votes_reported
                              FROM polling_reports_pollingreport
                              WHERE polling_reports_pollingreport.election_id = %(ELECTION_ID)s
                                AND period_number >= """ + str(FIRST_PERIOD_NUMBER) + """
                                AND period_number <= """ + str(LAST_PERIOD_NUMBER) + """
                                AND deleted = false
                              GROUP BY 1,2,3,4,6,7
                             ) as p
                        JOIN register_registrationcenter as r
                        ON r.id = p.center_pk
                        WHERE p.part = 1
                        AND NOT EXISTS
                            (SELECT * FROM polling_reports_centerclosedforelection AS election_closure
                            WHERE election_closure.election_id = %(ELECTION_ID)s
                            AND election_closure.registration_center_id = r.id
                            AND election_closure.deleted = false);"""

# all centers, with authorized phones
# Whitelisted phones are reported with a 'W' flag and the time the whitelist was added/modified.
# Non-whitelisted phones are reported with a 'X' flag and a dummy time.
# The time is truncated down to the second to simplify parsing.
CENTERS_AND_PHONES = """SELECT center.center_id,
                  center.name,
                  array_agg(phone_w_list.phone_number || phone_w_list.whitelist_flag || phone_w_list.whitelist_timestamp) as phones,
                  (SELECT COUNT(reg.id) FROM register_registration reg WHERE reg.registration_center_id = center.id and reg.archive_time IS NULL and reg.deleted = false) as registration_count
                  FROM register_registrationcenter AS center
                  LEFT JOIN (SELECT phone.phone_number,
                        phone.registration_center_id,
                        CASE
                            WHEN whitelist.id IS NULL THEN
                                ' X '
                            ELSE
                                ' W '
                        END AS whitelist_flag,
                        CASE
                            WHEN whitelist.id IS NULL THEN
                                DATE_TRUNC('second', TIMESTAMP WITH TIME ZONE '2000-01-01 12:00:00-00')
                            ELSE
                                DATE_TRUNC('second', whitelist.modification_date)
                        END AS whitelist_timestamp
                        FROM polling_reports_staffphone AS phone
                        LEFT JOIN register_whitelist AS whitelist ON (phone.phone_number = whitelist.phone_number AND whitelist.deleted = false)
                        WHERE phone.deleted = false
                  ) as phone_w_list ON (phone_w_list.registration_center_id = center.id)
                  WHERE center.deleted = false
                  GROUP BY center.id, center_id, name
                  ORDER BY center_id;"""

# # MESSAGE LOGS # #
LOG_PHONES = """SELECT center.center_id as center_code,
                phone.phone_number,
                phone.creation_date,
                'phonelink' as type
                FROM polling_reports_staffphone as phone
                JOIN register_registrationcenter AS center ON (phone.registration_center_id = center.id)
                WHERE phone.creation_date <= TIMESTAMP WITH TIME ZONE %(NO_LATER_THAN)s
                  AND center.deleted = false
                  AND phone.deleted = false
                ORDER BY phone.creation_date;"""

LOG_ROLLCALL = """SELECT center.center_id AS center_code,
                  rollcall.creation_date,
                  rollcall.phone_number,
                  'rollcall' as type
                  FROM polling_reports_centeropen AS rollcall
                  JOIN register_registrationcenter AS center ON (rollcall.registration_center_id = center.id)
                  WHERE rollcall.election_id = %(ELECTION_ID)s
                  AND rollcall.deleted = false
                  AND center.deleted = false
                  AND NOT EXISTS
                      (SELECT * FROM polling_reports_centerclosedforelection AS election_closure
                       WHERE election_closure.election_id = %(ELECTION_ID)s
                       AND election_closure.registration_center_id = center.id
                       AND election_closure.deleted = false)
                  ORDER BY rollcall.creation_date;"""

LOG_VOTESREPORT = """SELECT center.center_id AS center_code,
                  report.creation_date,
                  report.phone_number,
                  report.period_number || ',' || report.num_voters as data,
                  'votesreport' as type
                  FROM polling_reports_pollingreport AS report
                  JOIN register_registrationcenter AS center ON (center.id = report.registration_center_id)
                  WHERE report.election_id = %(ELECTION_ID)s
                  AND report.period_number >= """ + str(FIRST_PERIOD_NUMBER) + """
                  AND report.period_number <= """ + str(LAST_PERIOD_NUMBER) + """
                  AND report.deleted = false
                  AND NOT EXISTS
                      (SELECT * FROM polling_reports_centerclosedforelection AS election_closure
                       WHERE election_closure.election_id = %(ELECTION_ID)s
                       AND election_closure.registration_center_id = center.id
                       AND election_closure.deleted = false)
                  ORDER BY report.creation_date;"""
