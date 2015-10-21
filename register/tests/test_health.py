"""Test health check"""
from django.test import TestCase


class HealthCheckTest(TestCase):
    def test_health_check(self):
        # Not using ``reverse``, this has to be at "/health/" or it
        # won't work
        rsp = self.client.get('/health/')
        self.assertEqual(200, rsp.status_code)
