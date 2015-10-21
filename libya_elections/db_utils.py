import logging
from django.conf import settings
from django.db import connections

logger = logging.getLogger(__name__)

# How many changes to save up before doing a bulk create or a delete.
# NB: In other projects, increasing this above a few hundred didn't improve
# performance noticeably for creates.
# (http://www.caktusgroup.com/blog/2011/09/20/bulk-inserts-django/)
BATCH_SIZE = 1000


def get_cursor(db):
    return connections[db].cursor()


def delete_all(db, models, cascade=False):
    """
    Delete all records of some models.

    Note: If tables have foreign key constraints to other tables, you MUST
    truncate all the related tables in the same command, or use cascade.

    This can only be used with Postgres since it uses a non-standard
    SQL extension.

    :param db: DB identifier, e.g. 'default'
    :param models: Iterable of Django model classes to delete all data from
    :param cascade: Whether to add CASCADE to the command
    """
    if 'backends.post' not in settings.DATABASES[db]['ENGINE']:
        raise NotImplementedError("delete_all only works for Postgres")

    table_names = ', '.join(model._meta.db_table for model in models)
    cmd = "TRUNCATE %s" % table_names
    if cascade:
        cmd += " CASCADE"
    cursor = get_cursor(db)
    cursor.execute(cmd)


class BatchOperations(object):
    """
    Help do adds and deletes efficiently on a model.

    :param model: The model class we'll be adding records to and deleting records from.
    :param batch_size: How many adds or deletes to do in each batch.
    Default is BATCH_SIZE.
    """
    def __init__(self, model, batch_size=BATCH_SIZE):
        self.model = model
        self.batch_size = BATCH_SIZE
        self.to_add = []
        self.to_delete = []

    def add(self, data):
        """
        Add a record to the batch of records to add.

        If the size of the batch reaches BATCH_SIZE, go ahead and add
        all the pending records.

        :param data: dictionary with data for one record
        """
        self.to_add.append(data)
        if len(self.to_add) >= self.batch_size:
            self._flush_adds()

    def _flush_adds(self):
        """
        (Internal use only; see `flush` for the public API.)

        Add the pending records to the table.
        """
        logger.info("Creating %d %s records", len(self.to_add), self.model._meta.model_name)
        records = [self.model(**record) for record in self.to_add]
        self.model.objects.bulk_create(records)
        self.to_add = []

    def delete(self, pk):
        """
        Add a record to the batch of records to delete.

        If the size of the batch reaches BATCH_SIZE, go ahead and delete
        all the pending records.

        :param pk: primary key of the record to delete
        """
        self.to_delete.append(pk)
        if len(self.to_delete) >= self.batch_size:
            self._flush_deletes()

    def _flush_deletes(self):
        """
        (Internal use only; see `flush` for the public API.)

        Remove the pending deleted records from the table.
        """
        logger.info("Deleting %d %s records", len(self.to_delete), self.model._meta.model_name)
        self.model.objects.filter(pk__in=self.to_delete).delete()
        self.to_delete = []

    def flush(self):
        """
        Perform all pending adds and deletes.
        """
        if self.to_add:
            self._flush_adds()
        if self.to_delete:
            self._flush_deletes()

    @property
    def num_pending_adds(self):
        return len(self.to_add)

    @property
    def num_pending_deletes(self):
        return len(self.to_delete)
