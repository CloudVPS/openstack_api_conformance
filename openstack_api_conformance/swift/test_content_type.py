import openstack_api_conformance

import json
import requests
import unittest2
import uuid


class Test(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['swift']
        if not cls.config:
            cls.skipTest("Swift not configured")

        response = requests.post(
            cls.config.auth_url + 'v2.0/tokens',
            data=json.dumps({
                'auth': {
                    'passwordCredentials': {
                        'username': cls.config['username'],
                        'password': cls.config['password'],
                    },
                    'tenantId': cls.config['tenantId'],
                }
            }),
            headers={'content-type': 'application/json'}
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
        self.c_url = self.url + "/ct-" + uuid.uuid4().hex
        self.session.put(self.c_url)

    def tearDown(self):
        # remove the object and the container.
        r = self.session.get(
            self.c_url, headers={'accept': 'application/json'})
        for obj in r.json():
            self.session.delete(self.c_url + "/" + obj['name'])

        self.session.delete(self.c_url)

    def testAutoDetect(self):
        self.session.put(self.c_url + "/a.xml", data="foo").raise_for_status()
        r = self.session.get(self.c_url + "/a.xml")
        r.raise_for_status()
        self.assertEqual(r.headers['content-type'], 'application/xml')

    def testNonAutoDetect(self):
        self.session.put(
            self.c_url + "/a.xml",
            data="foo",
            headers={'content-type': 'application/json'}).raise_for_status()
        r = self.session.get(self.c_url + "/a.xml")
        r.raise_for_status()
        self.assertEqual(r.headers['content-type'], 'application/json')

    def testFreeForm(self):
        self.session.put(
            self.c_url + "/a.xml",
            data="foo",
            headers={'content-type': 'werkt nie; ech nie!'}).raise_for_status()
        r = self.session.get(self.c_url + "/a.xml")
        r.raise_for_status()
        self.assertEqual(r.headers['content-type'], 'werkt nie; ech nie!')

    def testContentDisposition(self):
        self.session.put(
            self.c_url + "/a1.xml",
            data="foo",
            headers={'Content-Disposition': 'Iets fouts'}).raise_for_status()
        r = self.session.get(self.c_url + "/a1.xml")
        r.raise_for_status()

        self.assertEqual(
            r.headers['content-disposition'],
            'Iets fouts')

    def testCacheControl(self):
        self.session.put(
            self.c_url + "/a.xml",
            data="foo",
            headers={'Cache-Control': 'Iets fouts'}).raise_for_status()
        r = self.session.get(self.c_url + "/a.xml")
        r.raise_for_status()

        self.assertEqual(r.headers['Cache-Control'], 'Iets fouts')

    def testMetaAscii(self):
        self.session.put(
            self.c_url + "/a.xml",
            data="foo",
            headers={'x-object-meta-foo': 'Iets fouts'}).raise_for_status()
        r = self.session.get(self.c_url + "/a.xml")
        r.raise_for_status()
        self.assertEqual(r.headers['x-object-meta-foo'], 'Iets fouts')

    def testMetaUTF(self):
        self.session.put(
            self.c_url + "/a.xml",
            data="foo",
            headers={'x-object-meta-\xDC': 'Iets fouts'}).raise_for_status()
        r = self.session.get(self.c_url + "/a.xml")
        r.raise_for_status()
        self.assertEqual(r.headers['x-object-meta-\xDC'], 'Iets fouts')
