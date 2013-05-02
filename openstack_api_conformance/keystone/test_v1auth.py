import openstack_api_conformance
import unittest2

import requests
import json
import time
import calendar

class Test(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['keystone']

    def setUp(self):
        if not self.config.v1_url:
            self.skipTest("no v1 auth support for this setup")

    def test_withTenantId(self):
        response = requests.get(
            self.config.v1_url,
            headers={
                'X-Auth-User': '%(tenantId)s:%(username)s' % self.config,
                'X-Auth-Key': self.config.password,
            }
        )

        self.assertEqual(response.status_code, 204)

        self.assertIn('X-Storage-Url', response.headers)
        self.assertIn('X-Auth-Token', response.headers)

        self.assertRegexpMatches(
            response.headers['X-Storage-url'],
            r"^https?://([a-z0-9-]+\.)+[a-z]{2,6}/")

        self.assertRegexpMatches(
            response.headers['X-Auth-Token'],
            r"^[a-f0-9]{32}$")
