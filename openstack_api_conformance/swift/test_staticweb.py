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
        self.c_url = self.url + '/' + str(uuid.uuid4())
        self.o_url = self.c_url + '/index.html'

    def tearDown(self):
        self.session.delete(self.o_url)
        self.session.delete(self.c_url)

    def testContentTypeDifferentiation(self):
        self.session.put(
            self.c_url,
            headers={
                'X-Container-Meta-Web-Index': 'index.html',
                'x-container-read': '.r:*,.rlistings'
            }).raise_for_status()

        self.session.put(
            self.o_url,
            data="<!-- meh -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        response = requests.get(self.c_url)
        self.assertEqual( response.text, '<!-- meh -->')
