import openstack_api_conformance

import calendar
import json
import requests
import time
import unittest2


class Test(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['keystone']

    def setUp(self):
        self.base_auth = {
            'auth': {
                'passwordCredentials': {
                    'username': self.config['username'],
                    'password': self.config['password'],
                }
            }
        }

    def check_headers(self, headers):
        self.assertDictContainsSubset({
            #        'transfer-encoding': 'chunked',
            'content-type': 'application/json',
            'vary': 'X-Auth-Token',
        },
            headers)

        header_names = set(headers.keys()) - \
            set(("transfer-encoding", "content-length"))

        self.assertItemsEqual(
            header_names,
            ['date', 'content-type', 'vary'])

        if self.config.release == 'folsom':
            self.assertEqual(headers.get("transfer-encoding"), "chunked")
            self.assertNotIn('content-length', headers)
        else:
            self.assertNotIn('transfer-encoding', headers)
            self.assertRegexpMatches(headers['content-length'], r'^\d+$')

        response_date = time.strptime(
            headers['date'],
            '%a, %d %b %Y %H:%M:%S GMT')

        response_time = calendar.timegm(response_date)

        self.assertAlmostEqual(time.time(), response_time, delta=5)

    def check_token(self, token):
        # verify the minimal data set.
        self.assertIn('id', token)
        self.assertIn('expires', token)

        keys = set(token) - set(['tenant'])
        if self.config.release == 'folsom':
            self.assertItemsEqual(keys, ('id', 'expires'))
        else:
            self.assertItemsEqual(keys, ('id', 'expires', 'issued_at'))

        # Make sure the token expires 24h in the future.
        expires = time.strptime(token['expires'], '%Y-%m-%dT%H:%M:%SZ')
        expires = calendar.timegm(expires)

        # tokens are valid for 24 hours
        self.assertAlmostEqual(time.time() + 3600 * 24, expires, delta=650)

        if self.config.release == 'folsom':
            self.assertRegexpMatches(
                token['id'],
                r"^[a-f0-9]{32}$")
        else:
            self.assertRegexpMatches(
                token['id'],
                r"^[a-zA-Z0-9+-]{100,}={0,3}$")

        if 'tenant' in token:
            self.assertEqual(token['tenant']['id'], self.config.tenantId)

    def check_user(self, user):
        self.assertItemsEqual(
            user,
            (u'username', u'roles', u'roles_links', u'id', u'name')
        )

        self.assertEqual(user['roles_links'], [])
        self.assertEqual(user['username'], self.config.username)

        self.assertRegexpMatches(user['id'], r"^[a-f0-9]{32}$")

        # check the roles (if any)
        for role in user['roles']:
            self.assertIsInstance(role, dict)
            self.assertItemsEqual(role, ['name'])

    def check_catalog(self, catalog):
        if self.config.release == 'folsom' and not catalog:
            return  # folsom is inconsistent with empty catalogs.

        self.assertIsInstance(catalog, list)

        for service in catalog:
            self.assertIsInstance(service, dict)

            self.assertItemsEqual(
                service,
                [u'endpoints_links', u'endpoints', u'type', u'name']
            )
            self.assertEqual(service['endpoints_links'], [])
            self.assertIsInstance(service['endpoints'], list)
            for endpoint in service['endpoints']:
                self.assertItemsEqual(
                    endpoint,
                    [u'adminURL', u'publicURL',
                        u'internalURL', u'region', u'id']
                )

                for url in u'publicURL', u'internalURL':  # u'adminURL'
                    self.assertRegexpMatches(
                        endpoint[url],
                        r"^https?://([\d\.]+|[0-9a-z\.-]+\.[a-z\.]{2,6})(:\d+)?(/[A-Za-z0-9_\./]*)?$"
                    )

    def test_unbound(self):
        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(self.base_auth),
                                 headers={'content-type': 'application/json'}
                                 )

        self.check_headers(response.headers)

        token = response.json()

        # Check we got exactly the information one would expect from an unbound
        # token.
        self.assertItemsEqual(token, [u'access'])

        if self.config.release == 'grizzly':
            self.assertItemsEqual(
                token['access'],
                [u'token', u'user', u'serviceCatalog', u'metadata'])
        else:
            self.assertItemsEqual(
                token['access'],
                [u'token', u'user', u'serviceCatalog'])

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        # Unbound tokens should have an empty serviceCatalog
        self.assertFalse(token['access']['serviceCatalog'])

        # Unbound tokens should not have a tenant linked to the token
        self.assertNotIn('tenant', token['access']['token'])

        # Unbound tokens should not provide any roles
        self.assertEqual([], token['access']['user']['roles'])

    def test_with_tenantId(self):
        self.base_auth['auth']['tenantId'] = self.config.tenantId
        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(self.base_auth),
                                 headers={'content-type': 'application/json'}
                                 )

        self.check_headers(response.headers)

        token = response.json()

        # Check we got exactly the information one would expect from an unbound
        # token.
        self.assertItemsEqual(token, [u'access'])

        self.assertItemsEqual(
            token['access'],
            [u'token', u'user', u'serviceCatalog', u'metadata']
        )

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        self.assertEqual(
            token['access']['token']['tenant']['id'],
            self.config.tenantId)

    def test_with_tenantName(self):
        self.base_auth['auth']['tenantName'] = self.config.tenantName
        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(self.base_auth),
                                 headers={'content-type': 'application/json'}
                                 )

        self.check_headers(response.headers)

        token = response.json()

        # Check we got exactly the information one would expect from an unbound
        # token.
        self.assertItemsEqual(token, [u'access'])

        self.assertItemsEqual(
            token['access'],
            [u'token', u'user', u'serviceCatalog', u'metadata']
        )

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        self.assertEqual(
            token['access']['token']['tenant']['id'],
            self.config.tenantId)

    def test_with_unboundToken(self):
        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(self.base_auth),
                                 headers={'content-type': 'application/json'}
                                 )
        token = response.json()

        auth = {
            'auth': {
                'token': {
                    'id': token['access']['token']['id']
                }
            }
        }

        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(auth),
                                 headers={'content-type': 'application/json'}
                                 )
        token = response.json()

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        self.assertNotIn('tenant', token['access']['token'])

        auth['auth']['tenantName'] = self.config.tenantName

        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(auth),
                                 headers={'content-type': 'application/json'}
                                 )
        token = response.json()

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        self.assertEqual(
            token['access']['token']['tenant']['id'],
            self.config.tenantId)

    def test_with_boundToken(self):
        self.base_auth['auth']['tenantName'] = self.config.tenantName
        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(self.base_auth),
                                 headers={'content-type': 'application/json'}
                                 )
        token = response.json()

        auth = {
            'auth': {
                'token': {
                    'id': token['access']['token']['id']
                }
            }
        }

        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(auth),
                                 headers={'content-type': 'application/json'}
                                 )
        token = response.json()

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        self.assertNotIn('tenant', token['access']['token'])

        auth['auth']['tenantName'] = self.config.tenantName

        response = requests.post(self.config.url + 'v2.0/tokens',
                                 data=json.dumps(auth),
                                 headers={'content-type': 'application/json'}
                                 )
        token = response.json()

        self.check_token(token['access']['token'])
        self.check_user(token['access']['user'])
        self.check_catalog(token['access']['serviceCatalog'])

        self.assertEqual(
            token['access']['token']['tenant']['id'],
            self.config.tenantId)
