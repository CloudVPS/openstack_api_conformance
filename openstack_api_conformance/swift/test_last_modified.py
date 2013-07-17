import openstack_api_conformance
import unittest2

import socket
import requests
import json
import urlparse
import uuid
import time, calendar
import xml.etree.ElementTree as ET

class Test(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['swift']
        if not cls.config:
            cls.skipTest("Swift not configured")

        response = requests.post(cls.config.auth_url + 'v2.0/tokens',
            data=json.dumps({
                'auth': {
                    'passwordCredentials': {
                        'username': cls.config['username'],
                        'password': cls.config['password'],
                    },
                    'tenantId': cls.config['tenantId'],
                }
            }),
            headers= {'content-type': 'application/json'}
        )

        token = response.json()

        cls.tokenId = token['access']['token']['id']
        object_stores = [
            service['endpoints'][0]['publicURL']
            for service in token['access']['serviceCatalog']
            if service['type'] == 'object-store'
        ]

        cls.url = object_stores[0]

    def setUp(self):
        self.session = requests.Session()
        self.session.headers.update({'X-Auth-Token': self.tokenId})
        self.c_url = self.url + "/lm-" + uuid.uuid4().hex
        self.session.put(self.c_url)

    def tearDown(self):
        # remove the object and the container.
        r = self.session.get(self.c_url, headers={'accept': 'application/json'})
        for obj in r.json():
            self.session.delete(self.c_url + "/" + obj['name'])

        self.session.delete(self.c_url)

    def testAutomatic(self):
        self.session.put(self.c_url +"/a", data="foo").raise_for_status()
        ref_time = time.time()
        r = self.session.get(self.c_url +"/a")
        r.raise_for_status()
        last_modified = r.headers['last-modified']


        last_modified = time.strptime(last_modified, '%a, %d %b %Y %H:%M:%S GMT')
        last_modified = calendar.timegm(last_modified)
        self.assertAlmostEqual(ref_time, last_modified, delta=2)


    def testCustom(self):
        self.session.put(
            self.c_url +"/a",
            data="foo",
            headers={'x-timestamp': '100000000.0'}
        ).raise_for_status()
        r = self.session.get(self.c_url +"/a")
        r.raise_for_status()
        self.assertEqual(r.headers['last-modified'], "Sat, 03 Mar 1973 09:46:40 GMT")


    def testModified(self):
        self.session.put(
            self.c_url +"/a",
            data="foo",
            headers={'x-timestamp': '100000000.0'}
        ).raise_for_status()

        r = self.session.get(
            self.c_url +"/a",
            headers={"if-modified-since":  "Sat, 03 Mar 1973 09:46:41 GMT"})

        self.assertEqual(r.status_code, 304)

        r = self.session.get(
            self.c_url +"/a",
            headers={"if-modified-since":  "Sat, 03 Mar 1973 09:46:39 GMT"})

        self.assertEqual(r.status_code, 200)

    def testModifiedTZ(self):
        self.skipTest("Known to fail, swift ignores timezones in http headers")
        self.session.put(
            self.c_url +"/a",
            data="foo",
            headers={'x-timestamp': '100000000.0'}
        ).raise_for_status()

        r = self.session.get(
            self.c_url +"/a",
            headers={"if-modified-since":  "Sat, 03 Mar 1973 09:46:40 JST"})

        self.assertEqual(r.status_code, 200)
