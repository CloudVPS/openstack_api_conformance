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
            self.key = str(uuid.uuid4())
            self.session.post(self.url +'/',
                headers={'X-Account-Meta-Temp-URL-Key': self.key})

        self.c_url = self.url + '/tmpu-' + str(uuid.uuid4())[:8]
        self.o_url = self.c_url + '/ob'

        self.session.put(self.c_url).raise_for_status()
        self.session.put(self.o_url, data="test").raise_for_status()

    def tearDown(self):
        self.session.delete(self.o_url)
        self.session.delete(self.c_url)

    def testGetTraditional(self):
        if '/v1/AUTH_' in self.o_url:
            url = self.o_url
        else:
            url = (
                self.url.replace(self.config['tenantId']+ '.','external.') +
                "/v1/AUTH_"+self.config['tenantId']+"/" +
                self.o_url[len(self.url)+1:]
            )

        base_url, object_path = url.split('/v1/',1)
        object_path = '/v1/' + object_path
        expires = int(time() + 60)
        hmac_body = 'GET\n%i\n%s' % (expires, object_path)

        sig = hmac.new(self.key, hmac_body, sha1).hexdigest()

        requests.get(
            "%s?temp_url_sig=%s&temp_url_expires=%i" % (url, sig, expires)
        ).raise_for_status()


    def testGetSimplified(self):
        url = self.o_url
        object_path = self.o_url[len(self.url):]

        expires = int(time() + 60)
        hmac_body = 'GET\n%i\n%s' % (expires, object_path)

        sig = hmac.new(self.key, hmac_body, sha1).hexdigest()

        requests.get(
            "%s?temp_url_sig=%s&temp_url_expires=%i" % (url, sig, expires)
        ).raise_for_status()

    def testGetFarFuture(self):
        url = self.o_url
        object_path = self.o_url[len(self.url):]

        expires = int(time() + 86400*365)
        hmac_body = 'GET\n%i\n%s' % (expires, object_path)

        sig = hmac.new(self.key, hmac_body, sha1).hexdigest()

        requests.get(
            "%s?temp_url_sig=%s&temp_url_expires=%i" % (url, sig, expires)
        ).raise_for_status()


    def testBrokenHash(self):
        url = self.o_url
        object_path = self.o_url[len(self.url):] + '?'

        expires = int(time() + 60)
        hmac_body = 'GET\n%i\n%s' % (expires, object_path)

        sig = hmac.new(self.key, hmac_body, sha1).hexdigest()

        response = requests.get(
            "%s?temp_url_sig=%s&temp_url_expires=%i" % (url, sig, expires)
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Temp URL", response.text)

    def testExpired(self):
        url = self.o_url
        object_path = self.o_url[len(self.url):]

        expires = int(time() - 60)
        hmac_body = 'GET\n%i\n%s' % (expires, object_path)

        sig = hmac.new(self.key, hmac_body, sha1).hexdigest()

        response = requests.get(
            "%s?temp_url_sig=%s&temp_url_expires=%i" % (url, sig, expires)
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Temp URL", response.text)

    def testCache(self):
        url = self.o_url
        object_path = self.o_url[len(self.url):]

        expires = int(time() + 60)
        hmac_body = 'GET\n%i\n%s' % (expires, object_path)

        sig = hmac.new(self.key, hmac_body, sha1).hexdigest()

        requests.get(
            "%s?temp_url_sig=%s&temp_url_expires=%i" % (url, sig, expires)
        ).raise_for_status()

        response = requests.get(url)
        self.assertEqual(response.status_code, 401)
