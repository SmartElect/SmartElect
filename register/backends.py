from rapidsms.backends.vumi import VumiBackend
from rapidsms.errors import MessageSendingError

from register.models import Whitelist


class WhitelistedVumiBackend(VumiBackend):
    """
    Outgoing SMS backend for Vumi, which asserts that messages only go to
    Whitelisted phone numbers.
    """

    def send(self, id_, text, identities, context=None):
        whitelisted_numbers = Whitelist.objects.filter(
            phone_number__in=identities).values_list('phone_number', flat=True)
        if len(whitelisted_numbers) != len(set(identities)):
            # lists don't match. There must be at least 1 non-whitelisted
            # number, so we will refuse to send
            not_whitelisted = [n for n in identities if n not in whitelisted_numbers]
            msg = ('Message not sent because the following phone numbers are not '
                   'whitelisted: %s.') % not_whitelisted
            raise MessageSendingError(msg)
        super(WhitelistedVumiBackend, self).send(id_, text, identities, context)
