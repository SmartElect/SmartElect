import signal

from django.test import TestCase

from bulk_sms.utils import SignalManager


class SignalManagerTest(TestCase):

    def setUp(self):
        self.manager = SignalManager()

    def _test_handler1(self):
        pass

    def _test_handler2(self):
        pass

    def test_push_pop(self):
        """
        Make sure we can add and remove signal handlers, and that they get
        updated appropriately.
        """
        sig = signal.SIGHUP
        saved = signal.getsignal(sig)
        # push a new handler and make sure it gets installed
        self.manager.push(sig, self._test_handler1)
        self.assertEqual(signal.getsignal(sig), self._test_handler1)
        # pop our handler and make sure the original value gets restored
        handler = self.manager.pop(sig)
        self.assertEqual(handler, self._test_handler1)
        self.assertEqual(signal.getsignal(sig), saved)

    def test_nested(self):
        """
        Make sure nested calls to ``push`` and ``pop`` work as expected.
        """
        sig = signal.SIGHUP
        saved = signal.getsignal(sig)
        # push a new handler and make sure it gets installed
        self.manager.push(sig, self._test_handler1)
        self.assertEqual(signal.getsignal(sig), self._test_handler1)
        # push a second new handler and make sure it gets installed
        self.manager.push(sig, self._test_handler2)
        self.assertEqual(signal.getsignal(sig), self._test_handler2)
        # pop our second handler and make sure the first one we installed gets set
        handler = self.manager.pop(sig)
        self.assertEqual(handler, self._test_handler2)
        self.assertEqual(signal.getsignal(sig), self._test_handler1)
        # pop our first handler and make sure the original value gets restoredet
        handler = self.manager.pop(sig)
        self.assertEqual(handler, self._test_handler1)
        self.assertEqual(signal.getsignal(sig), saved)

    def test_saved_first(self):
        """
        Make sure ``pop`` raises a ``ValueError`` if ``push`` hasn't been called
        first for a given signum.
        """
        # fails if no handler saved
        self.assertRaises(ValueError, self.manager.pop, 1)
        # fails if handler saved but already popped
        self.manager._saved_handlers = {1: []}
        self.assertRaises(ValueError, self.manager.pop, 1)
        # fails if other handlers exist, but not one for our signum
        self.manager._saved_handlers = {2: [self._test_handler1]}
        self.assertRaises(ValueError, self.manager.pop, 1)
