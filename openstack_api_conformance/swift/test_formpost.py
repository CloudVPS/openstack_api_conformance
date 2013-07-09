import openstack_api_conformance
import unittest2

import hmac
import json
import requests
import uuid
from hashlib import sha1
from time import time

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

        response = self.session.get(self.url + '/')
        self.key = response.headers.get('X-Account-Meta-Temp-URL-Key')
        if not self.key:
            self.key = uuid.uuid4()
            self.session.post(self.url +'/',
                headers={'X-Account-Meta-Temp-URL-Key': self.key})

        self.c_name =str(uuid.uuid4())[:8]
        self.c_url = self.url + '/' + self.c_name
        self.o_url = self.c_url + '/ob'

        self.session.put(self.c_url).raise_for_status()

    def tearDown(self):
        self.session.delete(self.o_url)
        self.session.delete(self.c_url)

    def testPost(self):
        path = "/v1/AUTH_%s/%s" % (self.config.tenantId, self.c_name)
        redirect = 'http://example.net/'
        max_file_size = 104857600
        max_file_count = 10
        expires = int(time() + 600)

        hmac_body = '%s\n%s\n%s\n%s\n%s' % (path, redirect,
            max_file_size, max_file_count, expires)
        signature = hmac.new(self.key , hmac_body, sha1).hexdigest()

        data = {
            "redirect": redirect,
            "max_file_size": str(max_file_size),
            "max_file_count": str(max_file_count),
            "expires": str(expires),
            "signature": signature,
        }

        response = requests.post(self.c_url,
            files={"file": ("test.xml", "<xml />")},
            data=data,
            allow_redirects=False)

        self.o_url = self.c_url + '/test.xml'

        self.assertEquals(response.status_code, 303)
        self.assertEquals(
            response.headers['Location'],
            redirect + "?status=201&message=")

        self.session.get(self.o_url).raise_for_status()

    def testSimplePost(self):
        path = self.c_url[len(self.url):]
        redirect = 'http://example.net/'
        max_file_size = 104857600
        max_file_count = 10
        expires = int(time() + 600)

        hmac_body = '%s\n%s\n%s\n%s\n%s' % (path, redirect,
            max_file_size, max_file_count, expires)
        signature = hmac.new(self.key , hmac_body, sha1).hexdigest()

        data = {
            "redirect": redirect,
            "max_file_size": str(max_file_size),
            "max_file_count": str(max_file_count),
            "expires": str(expires),
            "signature": signature,
        }

        response = requests.post(self.c_url,
            files={"file": ("test.xml", "<xml />")},
            data=data,
            allow_redirects=False)

        self.o_url = self.c_url + '/test.xml'

        self.assertEquals(response.status_code, 303)
        self.assertEquals(
            response.headers['Location'],
            redirect + "?status=201&message=")

        self.session.get(self.o_url).raise_for_status()

    def testExpired(self):
        path = "/v1/AUTH_%s/%s" % (self.config.tenantId, self.c_name)
        redirect = 'http://example.net/'
        max_file_size = 104857600
        max_file_count = 10
        expires = int(time() - 600)

        hmac_body = '%s\n%s\n%s\n%s\n%s' % (path, redirect,
            max_file_size, max_file_count, expires)
        signature = hmac.new(self.key , hmac_body, sha1).hexdigest()

        data = {
            "redirect": redirect,
            "max_file_size": str(max_file_size),
            "max_file_count": str(max_file_count),
            "expires": str(expires),
            "signature": signature,
        }

        response = requests.post(self.c_url,
            files={"file": ("test.xml", "<xml />")},
            data=data,
            allow_redirects=False)

        self.o_url = self.c_url + '/test.xml'

        self.assertEquals(response.status_code, 303)
        self.assertEquals(
            response.headers['Location'],
            redirect + "?status=401&message=form%20expired")


