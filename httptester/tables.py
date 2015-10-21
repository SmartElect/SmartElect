import django_tables2 as tables

from rapidsms.backends.database.models import BackendMessage


class MessageTable(tables.Table):

    class Meta:
        model = BackendMessage
        sequence = ('date', 'identity', 'direction', 'text')
        exclude = ('id', 'name', 'message_id', 'external_id')
        order_by = ('-date', )
        attrs = {
            'id': 'log',
            'class': 'page-width'
        }
