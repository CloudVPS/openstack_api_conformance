import openstack_api_conformance

import json
import requests
import unittest


class Test(unittest.TestCase):

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
        response.raise_for_status()

        token = response.json()

        cls.tokenId = token['access']['token']['id']
        object_stores = [
            service['endpoints'][0]['publicURL']
            for service in token['access']['serviceCatalog']
            if service['type'] == 'object-store'
        ]

        cls.url = object_stores[0]
        cls.headers = {'X-Auth-Token': cls.tokenId}

        requests.put(cls.url + "/foo", headers=cls.headers)\
            .raise_for_status()
        requests.put(cls.url + "/foo/a", data="abcd", headers=cls.headers)\
            .raise_for_status()

        # PUT the container again to clear caches
        requests.put(cls.url + "/foo", headers=cls.headers).raise_for_status()

    @classmethod
    def tearDownClass(cls):
        requests.delete(cls.url + "/foo/a", headers=cls.headers)
        requests.delete(cls.url + "/foo", headers=cls.headers)

    def testGet(self):
        # set the Cors header
        requests.post(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
                'X-Container-Meta-Access-Control-Allow-Origin': 'http://www.foo.com',
            }).raise_for_status()

        # check if the cors header was stored
        response = requests.get(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
            })

        response.raise_for_status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers['X-Container-Meta-access-control-allow-origin'],
            'http://www.foo.com')

        # set the Cors header
        response = requests.options(
            self.url + "/foo/a",
            headers={
                'X-Auth-Token': self.tokenId,
                'Origin': 'http://www.foo.com',
                'Access-Control-Request-Method': 'GET',
            })

        self.assertEqual(response.status_code, 200)

        # set the Cors header
        response = requests.options(
            self.url + "/foo/a",
            headers={
                'X-Auth-Token': self.tokenId,
                'Origin': 'http://www.bar.com',
                'Access-Control-Request-Method': 'GET',
            })
        self.assertEqual(response.status_code, 401)

    def testGetWildcard(self):
        # set the Cors header
        requests.post(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
                'X-Container-Meta-Access-Control-Allow-Origin': '*',
            }).raise_for_status()

        # check if the cors header was stored
        response = requests.get(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
            })

        response.raise_for_status()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers['X-Container-Meta-access-control-allow-origin'],
            '*')

        # set the Cors header
        response = requests.options(
            self.url + "/foo/a",
            headers={
                'X-Auth-Token': self.tokenId,
                'Origin': 'http://www.foo.com',
                'Access-Control-Request-Method': 'GET',
            })

        self.assertEqual(response.status_code, 200)

    def testGetMulti(self):
        # set the Cors header
        requests.post(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
                'X-Container-Meta-Access-Control-Allow-Origin': 'http://www.foo.com http://www.bar.com',
            }).raise_for_status()

        # set the Cors header
        response = requests.options(
            self.url + "/foo/a",
            headers={
                'X-Auth-Token': self.tokenId,
                'Origin': 'http://www.foo.com',
                'Access-Control-Request-Method': 'GET',
            })

        self.assertEqual(response.status_code, 200)

        # set the Cors header
        response = requests.options(
            self.url + "/foo/a",
            headers={
                'X-Auth-Token': self.tokenId,
                'Origin': 'http://www.bar.com',
                'Access-Control-Request-Method': 'GET',
            })
        self.assertEqual(response.status_code, 200)

        # set the Cors header
        response = requests.options(
            self.url + "/foo/a",
            headers={
                'X-Auth-Token': self.tokenId,
                'Origin': 'http://www.baz.com',
                'Access-Control-Request-Method': 'GET',
            })
        self.assertEqual(response.status_code, 401)
