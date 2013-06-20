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
        cls.headers = {'X-Auth-Token': cls.tokenId}

    def setUp(self):
        self.session = requests.Session()
        self.session.headers.update({'X-Auth-Token': self.tokenId})
        self.to_delete = []

    def tearDown(self):
        for item in self.to_delete:
            self.session.delete(item)

    def check_name(self, name, ok=True):
        self.to_delete.append(self.url + "/" + name)

        if not ok:
            with self.assertRaises(Exception):
                self.session.put(
                    self.url + "/" + name,
                    allow_redirects=False

                ).raise_for_status()

                r =self.session.get(
                    self.url + "/" + name,
                    headers={"accept": 'application/json'})
                r.raise_for_status()
        else:
            self.session.put(
                self.url + "/" + name,
                allow_redirects=False
            ).raise_for_status()

            r =self.session.get(
                self.url + "/" + name,
                headers={"accept": 'application/json'})
            r.raise_for_status()
            self.assertEqual(r.text, '[]')

    def testContainerNameUTF8(self):
        self.check_name(u"\x2603")

    def testContainerNameLong(self):
        self.check_name('X'*256)
        self.check_name('X'*257, False)

    def testContainerControl(self):
        self.check_name('\x00')
        self.check_name('\x01')
        self.check_name('\x7f')

    def testContainerSpace(self):
        self.check_name(' ')
        self.check_name(' n')


