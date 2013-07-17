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
        self.c_url = self.url + '/sw-' + str(uuid.uuid4())[:8]
        self.o_url = self.c_url + '/index.html'

        self.cleanup_urls = []

    def tearDown(self):
        for url in self.cleanup_urls:
            self.session.delete(url)

        self.session.delete(self.o_url)
        self.session.delete(self.c_url)

    def testWebIndex(self):
        self.session.put(
            self.c_url,
            headers={
                'X-Container-Meta-Web-Index': 'index.html',
                'X-Container-Read': '.r:*'
            }).raise_for_status()


        self.session.put(
            self.o_url,
            data="<!-- meh -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        nested_index = self.c_url + "/test/index.html"
        self.cleanup_urls.append(nested_index)
        self.session.put(
            nested_index,
            data="<!-- mah -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        response = requests.get(self.c_url + "/")
        self.assertEqual( response.text, '<!-- meh -->')
        response = requests.get(self.c_url + "/test/")
        self.assertEqual( response.text, '<!-- mah -->')



    def testRedirectPseudofolder(self):
        self.session.put(
            self.c_url,
            headers={
                'X-Container-Meta-Web-Listings': 'On',
                'X-Container-Read': '.r:*'
            }).raise_for_status()

        orig_url = self.o_url
        self.o_url = orig_url + "/foo"

        self.session.put(self.o_url, data="yeah!").raise_for_status()

        response = requests.get(self.o_url,
            headers={'Accept': 'text/html'},
        )
        self.assertEqual( response.text, 'yeah!')

        response = requests.get(orig_url,
            headers={'Accept': 'text/html'},
            allow_redirects=False
        )
        self.assertEqual( response.status_code, 302)
        self.assertEqual( response.headers['Location'],
            orig_url[len(self.url):] + '/'
        )

        response = requests.get(
            self.c_url + "/noexistement",
            headers={'Accept': 'text/html'},
            allow_redirects=False
        )
        self.assertEqual( response.status_code, 404)


    def testWebListing(self):
        self.session.put(
            self.c_url,
            headers={
                'X-Container-Meta-Web-Listings': 'On',
                'X-Container-Read': '.r:*'
            }).raise_for_status()

        self.session.put(
            self.o_url,
            data="<!-- meh -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        nested_index = self.c_url + "/test/nested.html"
        self.cleanup_urls.append(nested_index)
        self.session.put(
            nested_index,
            data="<!-- mah -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        response = requests.get(self.c_url)
        self.assertEqual(
            response.headers["content-type"],
            "text/html; charset=UTF-8")
        self.assertIn('index.html', response.text)
        self.assertNotIn('nested.html', response.text)

        response = requests.get(self.c_url + "/test/")
        self.assertEqual(
            response.headers["content-type"],
            "text/html; charset=UTF-8")
        self.assertNotIn('index.html', response.text)
        self.assertIn('nested.html', response.text)

    def testWeb404Error(self):
        self.session.put(
            self.c_url,
            headers={
                'X-Container-Meta-Web-Listings': 'On',
                'X-Container-Meta-Web-Error': 'error.html',
                'X-Container-Read': '.r:*,.rlistings'
            }).raise_for_status()

        self.o_url = self.c_url + '/404error.html'
        self.session.put(
            self.o_url,
            data="<!-- meh -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        response = requests.get(self.c_url + "/a")
        self.assertEqual('<!-- meh -->', response.text)


    def testWeb401Error(self):
        self.session.put(
            self.c_url,
            headers={
                'X-Container-Meta-Web-index': 'error.html',
                'X-Container-Meta-Web-Error': 'error.html',
            }).raise_for_status()

        self.o_url = self.c_url + '/401error.html'
        self.session.put(
            self.o_url,
            data="<!-- meh -->",
            headers={"content-type": "text/html"}
        ).raise_for_status()

        response = requests.get(self.c_url)
        self.assertEqual('<!-- meh -->', response.text)
