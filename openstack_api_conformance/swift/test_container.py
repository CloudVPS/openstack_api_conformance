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

        requests.put(cls.url + "/foo", headers=cls.headers).raise_for_status()
        requests.put(cls.url + "/foo/a", data="abcd", headers=cls.headers).raise_for_status()
        requests.put(cls.url + "/foo/b", data="abcdabcd", headers=cls.headers).raise_for_status()

        # PUT the container again to clear caches
        requests.put(cls.url + "/foo", headers=cls.headers).raise_for_status()

    @classmethod
    def tearDownClass(cls):
        requests.delete(cls.url + "/foo/a", headers=cls.headers).raise_for_status()
        requests.delete(cls.url + "/foo/b", headers=cls.headers).raise_for_status()
        requests.delete(cls.url + "/foo", headers=cls.headers).raise_for_status()
        requests.post(cls.url, headers=cls.headers).raise_for_status()

    def testGet(self):
        response = requests.get(
            self.url + "/foo",
            headers={'X-Auth-Token': self.tokenId})

        self.assertDictContainsSubset( {
                'content-type': 'text/plain; charset=utf-8',
                'x-container-object-count': '2',
                'x-container-bytes-used': '12',
                'content-type': 'text/plain; charset=utf-8',
            }, response.headers);

        self.assertRegexpMatches(
            response.headers['x-timestamp'],
            r"^\d+\.\d+$")

        self.assertRegexpMatches(
            response.headers['x-trans-id'],
            r"^tx[0-9a-f]{32}$")

        response_date = time.strptime(
            response.headers['date'],
            '%a, %d %b %Y %H:%M:%S GMT')

        response_time = calendar.timegm(response_date)

        self.assertAlmostEqual(time.time(), response_time, delta=2)

        self.assertEqual( response.text, 'a\nb\n')


    def testGetJson(self):
        response = requests.get(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
                'Accept': 'application/json'
            }
        )
        self.assertDictContainsSubset( {
                'content-type': 'text/plain; charset=utf-8',
                'x-container-object-count': '2',
                'x-container-bytes-used': '12',
                'content-type': 'application/json; charset=utf-8',
            }, response.headers)

        self.assertRegexpMatches(
            response.headers['x-timestamp'],
            r"^\d+\.\d+$")

        self.assertRegexpMatches(
            response.headers['x-trans-id'],
            r"^tx[0-9a-f]{32}$")

        response_date = time.strptime(
            response.headers['date'],
            '%a, %d %b %Y %H:%M:%S GMT')

        response_time = calendar.timegm(response_date)

        self.assertAlmostEqual(time.time(), response_time, delta=2)

        file_list = response.json()

        self.assertEqual(len(file_list), 2)

        self.assertDictContainsSubset({
            'bytes': 4,
            'content_type': 'application/octet-stream',
            'hash': 'e2fc714c4727ee9395f324cd2e7f331f',
            #'last_modified': '2013-04-22T10:33:29.808740',
            'name': 'a'}, file_list[0])

        modified_date = time.strptime(
            file_list[0]['last_modified'].split('.', 1)[0],
            '%Y-%m-%dT%H:%M:%S')
        modified_date = calendar.timegm(response_date)
        self.assertAlmostEqual(time.time(), modified_date, delta=2)


    def testGetXml(self):
        response = requests.get(
            self.url + "/foo",
            headers={
                'X-Auth-Token': self.tokenId,
                'Accept': 'application/xml'
            }
        )
        self.assertDictContainsSubset( {
                'content-type': 'text/plain; charset=utf-8',
                'x-container-object-count': '2',
                'x-container-bytes-used': '12',
                'content-type': 'application/xml; charset=utf-8',
            }, response.headers)

        self.assertRegexpMatches(
            response.headers['x-timestamp'],
            r"^\d+\.\d+$")

        self.assertRegexpMatches(
            response.headers['x-trans-id'],
            r"^tx[0-9a-f]{32}$")

        response_date = time.strptime(
            response.headers['date'],
            '%a, %d %b %Y %H:%M:%S GMT')

        response_time = calendar.timegm(response_date)

        self.assertAlmostEqual(time.time(), response_time, delta=2)

        # <?xml version="1.0" encoding="UTF-8"?>
        # <container name="foo">
        #   <object>
        #     <name>a</name>
        #     <hash>e2fc714c4727ee9395f324cd2e7f331f</hash>
        #     <bytes>4</bytes>
        #     <content_type>application/octet-stream</content_type>
        #     <last_modified>2013-04-22T11:15:50.500790</last_modified>
        #   </object>
        #   <object>
        #     <name>b</name>
        #     <hash>794fd8df6686e85e0d8345670d2cd4ae</hash>
        #     <bytes>8</bytes>
        #     <content_type>application/octet-stream</content_type>
        #     <last_modified>2013-04-22T11:15:50.620710</last_modified>
        #   </object>
        # </container>

        root = ET.fromstring(response.text)

        self.assertEqual(root.tag, 'container')
        self.assertEqual(root.attrib, {'name': 'foo'})

        self.assertEqual(root[0].tag, 'object')
        self.assertEqual(len(root[0]), 5)
        self.assertEqual(root[0][0].tag, 'name')
        self.assertEqual(root[0][0].text, 'a')
        self.assertEqual(root[0][1].tag, 'hash')
        self.assertEqual(root[0][1].text, 'e2fc714c4727ee9395f324cd2e7f331f')
        self.assertEqual(root[0][2].tag, 'bytes')
        self.assertEqual(root[0][2].text, '4')
        self.assertEqual(root[0][3].tag, 'content_type')
        self.assertEqual(root[0][3].text, 'application/octet-stream')
        self.assertEqual(root[0][4].tag, 'last_modified')


