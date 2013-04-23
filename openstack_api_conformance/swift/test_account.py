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
        session = requests.Session()
        session.headers.update({'X-Auth-Token': cls.tokenId})

        session.put(cls.url + "/foo").raise_for_status()
        session.put(cls.url + "/foo/a", data="abcd").raise_for_status()
        session.put(cls.url + "/foo/b", data="abcdabcd").raise_for_status()

        # PUT the container again to clear caches
        session.put(cls.url + "/foo").raise_for_status()

        # Add metadata to container
        session.post(
            cls.url,
            headers={'X-Account-Meta-foo': 'bar'}).raise_for_status()

    @classmethod
    def tearDownClass(cls):
        session = requests.Session()
        session.headers.update({'X-Auth-Token': cls.tokenId})

        session.delete(cls.url + "/foo/a").raise_for_status()
        session.delete(cls.url + "/foo/b").raise_for_status()
        session.delete(cls.url + "/foo").raise_for_status()

    def setUp(self):
        self.session = requests.Session()
        self.session.headers.update({'X-Auth-Token': self.tokenId})

    def testGet(self):
        response = self.session.get(self.url)

        self.assertDictContainsSubset( {
                'accept-ranges': 'bytes, bytes',
                'age': '0',
                'connection': 'keep-alive',
                'content-type': 'text/plain; charset=utf-8',
                'x-account-bytes-used': '12',
                'x-account-container-count': '1',
                'x-account-object-count': '2',
                'X-Account-Meta-foo': 'bar',
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

        self.assertRegexpMatches(
            response.text,
            r"^foo$")


    def testGetJson(self):
        response = self.session.get(
            self.url,
            headers={'accept': 'application/json'})

        self.assertDictContainsSubset( {
                'accept-ranges': 'bytes, bytes',
                'age': '0',
                'connection': 'keep-alive',
                'content-type': 'application/json; charset=utf-8',
            }, response.headers);


        self.assertRegexpMatches(
            response.headers['x-account-bytes-used'],
            r"^\d+$")


        self.assertRegexpMatches(
            response.headers['x-account-container-count'],
            r"^\d+$")

        self.assertRegexpMatches(
            response.headers['x-account-object-count'],
            r"^\d+$")

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

        act_bytes = int(response.headers['x-account-bytes-used'])
        act_containers = int(response.headers['x-account-container-count'])
        act_objects = int(response.headers['x-account-object-count'])
        for container in response.json():
            self.assertItemsEqual(container.keys(), ['name', 'count', 'bytes'])
            act_bytes -= container['bytes']
            act_containers -= 1
            act_objects -= container['count']

        self.assertEqual(act_bytes, 0)
        self.assertEqual(act_containers, 0)
        self.assertEqual(act_objects, 0)


    def testGetXML(self):
        response = self.session.get(
            self.url,
            headers={'accept': 'application/xml'})

        self.assertDictContainsSubset( {
                'accept-ranges': 'bytes, bytes',
                'age': '0',
                'connection': 'keep-alive',
                'content-type': 'application/xml; charset=utf-8',
            }, response.headers);

        root = ET.fromstring(response.text)

        self.assertEqual(root.tag, 'account')
        self.assertEqual(root.attrib, {'name': 'AUTH_' + self.config.tenantId})

        for child in root:
            self.assertEqual(child.tag, 'container')
            self.assertItemsEqual(
                [x.tag for x in child],
                ['bytes', 'count', 'name'])
            self.assertEqual(child.attrib, {})
            self.assertTrue(all(x.attrib == {} for x in child))


