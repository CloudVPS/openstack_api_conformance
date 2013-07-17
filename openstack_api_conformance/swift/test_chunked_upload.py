import openstack_api_conformance
import unittest2

import socket
import requests
import json
import urlparse
import uuid

class Test(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['swift']

    def setUp(self):
        if not self.config:
            self.skipTest("Swift not configured")

        response = requests.post(self.config.auth_url + 'v2.0/tokens',
            data=json.dumps({
                'auth': {
                    'passwordCredentials': {
                        'username': self.config['username'],
                        'password': self.config['password'],
                    },
                    'tenantId': self.config['tenantId'],
                }
            }),
            headers= {'content-type': 'application/json'}
        )

        token = response.json()
        self.session = requests.Session()

        self.session.headers.update({'X-Auth-Token': token['access']['token']['id']})

        object_stores = [
            service['endpoints'][0]['publicURL']
            for service in token['access']['serviceCatalog']
            if service['type'] == 'object-store'
        ]


        self.url = object_stores[0]
        self.c_url = self.url + "/chup-"  + uuid.uuid4().hex

        # make sure container exists
        self.session.put(self.c_url).raise_for_status()

    def tearDown(self):
        # remove the object and the container.
        self.session.delete(self.c_url + "/1").raise_for_status()
        self.session.delete(self.c_url).raise_for_status()

    def testWithChunked(self):
        data = uuid.uuid4().hex
        def generator():
            yield data

        response = self.session.put(self.c_url + "/1", data=generator() )

        response.raise_for_status()

        response = self.session.get(self.c_url + "/1")

        self.assertEqual(data, response.text)

