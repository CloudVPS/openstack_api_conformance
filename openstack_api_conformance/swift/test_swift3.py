import openstack_api_conformance
import unittest2

import base64
import email.utils
import json
import hmac
import requests
import sha
import time
import urllib
import uuid


def canonical_string(method, path, headers, expires=None):
    """
    Generates the aws canonical string for the given parameters
    """
    interesting_headers = {}
    for key in headers:
        lk = key.lower()
        if headers[key] != None and (lk in ['content-md5', 'content-type', 'date'] or
                                     lk.startswith('x-amz-')):
            interesting_headers[lk] = str(headers[key]).strip()

    # these keys get empty strings if they don't exist
    if 'content-type' not in interesting_headers:
        interesting_headers['content-type'] = ''
    if 'content-md5' not in interesting_headers:
        interesting_headers['content-md5'] = ''

    # if you're using expires for query string auth, then it trumps date
    # (and provider.date_header)
    if expires:
        interesting_headers['date'] = str(expires)

    sorted_header_keys = sorted(interesting_headers.keys())

    buf = "%s\n" % method
    for key in sorted_header_keys:
        val = interesting_headers[key]
        if key.startswith('x-amz-'):
            buf += "%s:%s\n" % (key, val)
        else:
            buf += "%s\n" % val

    # don't include anything after the first ? in the resource...
    # unless it is one of the QSA of interest, defined above
    t = path.split('?')
    buf += t[0]

    return buf


def sign_headers(method, path, headers, expires=None):

    if 'Date' not in headers and not expires:
        headers['date'] = email.utils.formatdate(time.time())

    string_to_sign = canonical_string(method, path, headers, expires)

    config = openstack_api_conformance.get_configuration()['swift']

    signature = base64.b64encode(hmac.new(
        str(config['s3_secret']),
        str(string_to_sign), sha).digest())

    headers['Authorization'] = 'AWS %s:%s' % (config['s3_access'], signature)


class Test(unittest2.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['swift']
        if not cls.config:
            cls.skipTest("Swift not configured")

        cls.url = cls.config['s3_base']

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

        object_stores = [
            service['endpoints'][0]['publicURL']
            for service in token['access']['serviceCatalog']
            if service['type'] == 'object-store'
        ]

        cls.swift_url = object_stores[0]
        cls.tokenId = token['access']['token']['id']

    def setUp(self):
        if not self.config:
            self.skipTest("Swift not configured")

        if not self.config['s3_access'] and not self.config['s3_secret']:
            self.skipTest("S3 not configured")

        self.container_name = 'sw3-' + str(uuid.uuid4())[:8]
        self.obj_name = 'ob-' + str(uuid.uuid4())[:8]
        self.container = '/%s' % self.container_name
        self.obj = '/%s/%s' % (self.container_name, self.obj_name)

    def tearDown(self):
        headers = {}
        url = self.url + self.obj

        sign_headers('DELETE', '/' + url.split('/', 3)[-1], headers)
        requests.delete(url, headers=headers)

        headers = {}
        url = self.url + self.container
        sign_headers('DELETE', '/' + url.split('/', 3)[-1], headers)
        requests.delete(url, headers=headers)

    def testPut(self):
        headers = {}
        url = self.url + self.container
        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers)
        requests.put(url, headers=headers).raise_for_status()

        headers = {
            'Cache-Control': 'foo',
            'Content-Disposition': 'bar',
            'Content-Type': "baz"
        }
        url = self.url + self.obj
        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers)
        requests.put(url, headers=headers).raise_for_status()

        result = requests.get(self.swift_url + self.obj,
                              headers={'x-auth-token': self.tokenId})
        result.raise_for_status()
        self.assertEqual(result.headers['Content-Type'], 'baz')
        self.assertEqual(result.headers['Cache-Control'], 'foo')
        self.assertEqual(result.headers['Content-Disposition'], 'bar')

    def testPutCopy(self):
        headers = {}
        url = self.url + self.container
        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers)
        requests.put(url, headers=headers).raise_for_status()

        headers = {}
        url = self.url + self.obj
        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers)
        requests.put(url, headers=headers).raise_for_status()

        headers = {'X-AMZ-COPY-SOURCe': self.obj}
        url = self.url + self.obj + "-1"
        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers)
        response = requests.put(url, headers=headers)
        response.raise_for_status()

        self.assertIn('<CopyObjectResult>', response.content)

        result = requests.get(self.swift_url + self.obj + "-1",
                              headers={'x-auth-token': self.tokenId})
        result.raise_for_status()

    def testPutSigned(self):
        headers = {}
        expires = int(time.time() + 60)
        url = self.url + self.container

        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers, expires)

        key, sign = headers['Authorization'].split(" ")[-1].split(':', 1)
        requests.put(
            url + "?AWSAccessKeyId=%s&Expires=%s&Signature=%s" % (
                key, expires, urllib.quote(sign)
            ),
            headers=headers).raise_for_status()

    def testPutSignedFarFuture(self):
        headers = {}
        expires = int(time.time() + 3600)
        url = self.url + self.container

        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers, expires)

        key, sign = headers['Authorization'].split(" ")[-1].split(':', 1)
        requests.put(
            url + "?AWSAccessKeyId=%s&Expires=%s&Signature=%s" % (
                key, expires, urllib.quote(sign)
            ),
            headers=headers).raise_for_status()

    def testPutSignedPast(self):
        headers = {}
        expires = int(time.time() - 3600)
        url = self.url + self.container

        sign_headers('PUT', '/' + url.split('/', 3)[-1], headers, expires)

        key, sign = headers['Authorization'].split(" ")[-1].split(':', 1)
        result = requests.put(
            url + "?AWSAccessKeyId=%s&Expires=%s&Signature=%s" % (
                key, expires, urllib.quote(sign)
            ),
            headers=headers)

        self.assertEqual(result.status_code, 403)
