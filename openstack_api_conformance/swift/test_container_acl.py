import openstack_api_conformance
import unittest2

import requests
import json
import uuid

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
        self.o_url = self.c_url + '/a'

    def tearDown(self):
        self.session.delete(self.o_url)
        self.session.delete(self.c_url)

    def testNonPublic(self):
        self.session.put(self.c_url).raise_for_status()
        self.session.put(self.o_url, data="test").raise_for_status()

        # use self.session is authenticated, bare requests isn't
        response = requests.get(self.o_url)
        self.assertEqual(response.status_code, 401)

        # use self.session is authenticated, bare requests isn't
        response = requests.get(self.c_url)
        self.assertEqual(response.status_code, 401)

        response = requests.put(self.c_url + 'a', data='bar')
        self.assertEqual(response.status_code, 401)

        response = requests.put(self.c_url)
        self.assertEqual(response.status_code, 401)

    def testPublic(self):
        self.session.put(self.c_url, headers={
            'x-container-read': '.r:*'
        }).raise_for_status()
        self.session.put(self.o_url, data="test").raise_for_status()

        # use self.session is authenticated, bare requests isn't
        response = requests.get(self.o_url)
        self.assertEqual(response.status_code, 200)

        # use self.session is authenticated, bare requests isn't
        response = requests.get(self.c_url)
        self.assertEqual(response.status_code, 401)

        response = requests.put(self.o_url, data='bar')
        self.assertEqual(response.status_code, 401)

        response = requests.put(self.c_url)
        self.assertEqual(response.status_code, 401)


    def testPublicList(self):
        self.session.put(self.c_url, headers={
            'x-container-read': '.r:*,.rlistings'
        }).raise_for_status()
        self.session.put(self.o_url, data="test").raise_for_status()

        # use self.session is authenticated, bare requests isn't
        response = requests.get(self.o_url)
        self.assertEqual(response.status_code, 200)

        response = requests.get(self.c_url)
        self.assertEqual(response.status_code, 200)

        response = requests.put(self.o_url, data='bar')
        self.assertEqual(response.status_code, 401)

        response = requests.put(self.c_url)
        self.assertEqual(response.status_code, 401)

    def testPublicList_content_type(self):
        self.session.put(self.c_url, headers={
            'x-container-read': '.r:*,.rlistings'
        }).raise_for_status()
        self.session.put(self.o_url, data="test").raise_for_status()

        response = requests.get(self.c_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text, "a\n")
        self.assertEqual(response.headers['content-type'], "text/plain; charset=utf-8")

        response = requests.get(self.c_url, headers={
            'accept': 'application/json'
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.text[0], "[")
        self.assertEqual(response.headers['content-type'], "application/json; charset=utf-8")
