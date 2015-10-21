"""
Custom exceptions for things that can go wrong in the
execution of changesets.

These are used more for documentation than functionality
at the moment.
"""


class ChangesetException(Exception):
    pass


class NotEnoughApprovals(ChangesetException):
    pass


class NotPermittedToApprove(ChangesetException):
    pass


class NotPermittedToQueue(ChangesetException):
    pass


class NotInApprovableStatus(ChangesetException):
    pass


class NotApprovedBy(ChangesetException):
    pass


class NotAnAllowedStatus(ChangesetException):
    pass
