from collections import defaultdict
import copy
import logging
import datetime

logger = logging.getLogger(__name__)


def aggregate_up(lesser_dicts, aggregate_key, lesser_key=None, skip_keys=(), copy_keys=None,
                 count_inner_keys=(), sum_inner_keys=(), enumerate_keys=()):
    """ Sums values of aggregate_key in lesser dicts
    Skips top-level keys in skip_keys
    Copies top-level keys in copy_keys
    Maintains a list of values specified by enumerate_keys
        each list is specified by a tuple consisting of
            1. key to check for presence in lesser dictionary AND to be used for maintaining
               list in aggregate
            2. key in lesser dictionary providing a value to represent the presence in the
               aggregate

    If value of lesser_dict[key] is a:
        list -
            puts sum of 0th and 1st values (for [m,f] coding)
        int or float -
            adds value to total
        dict -
            copies dict to agg_dict
            if inner_key in count_inner_keys:
                counts the instances of this inner_key across all lesser_dicts
                stores value per date as inner_key if string, or N_count if inner_key is int
            if inner_key in sum_inner_keys:
                sum this inner_key across all lesser_dicts
        anything else -
            copy to agg_dict for output


    Returns new dict
    """
    logger.info('aggregating up %s' % aggregate_key)

    # a dict of dicts to hold aggregated values
    aggregate_dicts = defaultdict(lambda: defaultdict(int))
    # { 1: { '2013-12-25': 0, '2013-12-26': 1 },
    #   2: { '2013-12-25': 0, '2013-12-26': 1 }
    # }

    # holds counts across lesser_dicts
    agg_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    # { 1: {'2013-12-25': {'opened': 0, 'reported':2 },
    #        '2013-12-26': {'opened': 0, 'reported':2 }}
    # }

    agg_rollup = defaultdict(int)  # dict of ints, to hold rollup counts

    for ld in lesser_dicts:
        lesser_dict = copy.deepcopy(ld)  # copy first, so we can't modify in place
        aggregate_val = lesser_dict[aggregate_key]
        agg_rollup[aggregate_val] += 1

        agg_dict = aggregate_dicts[aggregate_val]  # the dict we'll aggregate to

        # copy only specified keys
        # by default copy all
        if not copy_keys:
            copy_keys = lesser_dict.keys()
        for key in copy_keys:
            agg_dict[key] = lesser_dict[key]
        for key_for_presence, key_for_value in enumerate_keys:
            if key_for_presence not in agg_dict:
                agg_dict[key_for_presence] = []
            if key_for_presence in ld:
                agg_dict[key_for_presence].append(lesser_dict[key_for_value])

        enumerate_key_for_presence = [i[0] for i in enumerate_keys]
        for (key, val) in lesser_dict.iteritems():
            if key not in skip_keys and key not in copy_keys and \
               key not in enumerate_key_for_presence:

                if isinstance(val, list):
                    if key not in agg_dict:
                        agg_dict[key] = list(val)
                    else:
                        # For the hacky Male/Female coding.
                        agg_dict[key] = [agg_dict[key][0] + val[0],
                                         agg_dict[key][1] + val[1]]

                elif type(val) in [int, float, long]:
                    # sum with previous values
                    agg_dict[key] += val

                elif isinstance(val, dict):
                    # copy to agg_dict first
                    agg_dict[key] = val

                    # operate on inner keys
                    for inner_key in val.keys():
                        if inner_key in count_inner_keys:
                            # increment in agg_counts
                            if isinstance(inner_key, basestring):
                                agg_counts[aggregate_val][key][inner_key] += 1
                            else:
                                agg_counts[aggregate_val][key][str(inner_key)+'_count'] += 1
                        if inner_key in sum_inner_keys:
                            # add it to agg_counts
                            agg_counts[aggregate_val][key][inner_key] += val[inner_key]

                elif isinstance(val, basestring):
                    # This code started seeing unicode when migrating reporting the code
                    # from using psycopg2-provided cursor to Django-provided cursor and
                    # running inside the Django app
                    # probably a name
                    agg_dict[key] = val

                else:
                    # default to store (what is this?)
                    agg_dict[key] = val
                    logger.warning('aggregate_up: Storing data of type %s for key %s' %
                                   (type(val), key))

    # copy agg_counts values to aggregate_dict
    for (agg_key, agg_val) in agg_counts.iteritems():
        for (date, date_val) in agg_val.iteritems():
            for (inner_key, inner_val) in date_val.iteritems():
                aggregate_dicts[agg_key][date][inner_key] = inner_val

    # copy agg_rollup to aggregate_dict
    for (agg_key, count) in agg_rollup.iteritems():
        if lesser_key:
            aggregate_dicts[agg_key][str(lesser_key)+'_count'] = count
        else:
            aggregate_dicts[agg_key]['count'] = count

    # convert nested defaultdicts back to regular dict for output
    return {k: dict(v) for (k, v) in aggregate_dicts.iteritems()}


def aggregate_nested_key(d, d_key, nested_key):
    """ Sums values in dicts with this structure:
        {
            date_1:
                d_key: {
                    nested_key: val
                },
            date_2:
                d_key: {
                    nested_key: val
                }
        }

        Returns new dict
    """
    logger.info("aggregating nested %s for %s" % (nested_key, d_key))

    agg = defaultdict(lambda: defaultdict(int))
    for row in d.itervalues():
        row_key = row[d_key]
        for (val_key, val) in dict(row).items():
            if isinstance(val, dict):
                agg[row_key][val_key] += val[nested_key]

    return {k: dict(v) for (k, v) in agg.iteritems()}


def aggregate_dates(d, fields=None):
    """ Sums values in dicts with this structure:
        {
            date_1: { key_1: val_1, key_2: val_2, ... }
            date_2: { key_1: val_1, key_2: val_2, ... }
            date_3: { key_1: val_1, key_2: val_2, ... }
        }

        Returns new dict
    """
    # log.info("aggregating dates")

    agg = defaultdict(int)
    for row in d.itervalues():
        if isinstance(row, dict):
            if fields:
                keys = filter(lambda x: x in fields, row.keys())
            else:
                keys = row.keys()
            for key in keys:
                agg[key] += row[key]
    return dict(agg)


def join_by_date(lesser_dict, on_key, date_key, copy_keys, major_dict, date_set=set(),
                 missing=None):
    """ Emulates a SQL left join from lesser_dict to major_dict on on_key for dates in field named
          date_key
        All fields in copy_keys will be copied to new dict, and placed in major_dict[join_val][date]
        Adds all dates seen to date_set

        Converts python datetime objects to isoformat, for cross-application compatibility
        Returns new dict
    """

    logger.info("joining on %s" % on_key)

    output_dict = copy.deepcopy(major_dict)
    for row in lesser_dict:
        date = row[date_key]
        formatted_date = date.strftime('%Y-%m-%d')

        val_d = {}
        for copy_key in copy_keys:
            val = row[copy_key]

            # convert time, date or datetime to isoformat
            if isinstance(val, datetime.datetime) \
               or isinstance(val, datetime.time) \
               or isinstance(val, datetime.date):
                val_d[copy_key] = val.isoformat()
            # convert longs from db back to int
            elif isinstance(val, long):
                val_d[copy_key] = int(val)
            else:
                val_d[copy_key] = val

        join_val = row[on_key]
        if join_val in major_dict:
            if formatted_date in output_dict[join_val]:
                # date already exists, update with added keys
                output_dict[join_val][formatted_date].update(val_d)

            else:
                # create dict for this date
                output_dict[join_val][formatted_date] = val_d

        else:
            if missing is not None:
                missing[join_val].append(row)
            else:
                logger.error("join_val %s not in major_dict" % join_val)
            continue

        # add date to set
        date_set.add(formatted_date)

    return output_dict


def join_by_date_nested(lesser_dict, on_key, date_key, copy_dict_map, major_dict, date_set=set(),
                        missing=None):
    """ Emulates a SQL left join from lesser_dict to major_dict on on_key for dates in field named
          date_key
        All fields and values named in copy_dict_map will be copied to new dict, and placed in
          major_dict[join_val][date]
        Adds all dates seen to date_set

        Converts python datetime objects to isoformat, for cross-application compatibility
        Returns new dict
    """

    logger.info("joining on %s" % on_key)

    output_dict = copy.deepcopy(major_dict)
    for row in lesser_dict:
        date = row[date_key]
        formatted_date = date.strftime('%Y-%m-%d')

        val_d = {}
        for (copy_key, copy_val) in copy_dict_map.items():
            val = row[copy_val]
            key = row[copy_key]

            # convert time, date or datetime to isoformat
            if isinstance(val, datetime.datetime) \
               or isinstance(val, datetime.time) \
               or isinstance(val, datetime.date):
                val_d[key] = val.isoformat()
            # convert longs from db back to int
            elif isinstance(val, long):
                val_d[key] = int(val)
            else:
                val_d[key] = val

        join_val = row[on_key]
        if join_val in major_dict:
            if formatted_date in output_dict[join_val]:
                # date already exists, update with added keys
                output_dict[join_val][formatted_date].update(val_d)

            else:
                # create dict for this date
                output_dict[join_val][formatted_date] = val_d

        else:
            if missing is not None:
                missing[join_val].append(row)
            else:
                logger.error("join_val %s not in major_dict" % join_val)
            continue

        # add date to set
        date_set.add(formatted_date)

    return output_dict
