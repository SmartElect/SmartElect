import logging


class StaticFieldFilter(logging.Filter):
    """
    Python logging filter that adds the given static contextual information
    in the ``fields`` dictionary to all logging records.
    """
    def __init__(self, fields):
        self.static_fields = fields

    def filter(self, record):
        for k, v in self.static_fields.items():
            setattr(record, k, v)
        return True


class RequestFilter(logging.Filter):
    """
    Python logging filter that removes the (non-pickable) Django ``request``
    object from the logging record.
    """
    def filter(self, record):
        if hasattr(record, 'request'):
            del record.request
        return True
