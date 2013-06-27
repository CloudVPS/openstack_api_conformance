import json
import openstack_api_conformance
import requests
from requests.auth import HTTPBasicAuth
import unittest2
import uuid

class Test(unittest2.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = openstack_api_conformance.get_configuration()['swift']

    def setUp(self):
        if not self.config:
            self.skipTest("Swift not configured")

        response = requests.post(self.config.auth_url + 'v2.0/tokens',
            data=json.dumps({
                'auth': {
                    'passwordCredentials': {
                        'username': self.config['username'],
                        'password': self.config['password'],
                    },
                    'tenantId': self.config['tenantId'],
                }
            }),
            headers= {'content-type': 'application/json'}
        )

        token = response.json()
        self.session = requests.Session()

        self.session.headers.update({'X-Auth-Token': token['access']['token']['id']})

        object_stores = [
            service['endpoints'][0]['publicURL']
            for service in token['access']['serviceCatalog']
            if service['type'] == 'object-store'
        ]


        self.url = object_stores[0]
        self.c_url = self.url + "/"  + uuid.uuid4().hex

        # make sure container exists
        self.session.put(self.c_url).raise_for_status()

    def tearDown(self):
        # remove the object and the container.
        self.session.delete(self.c_url + "/1")
        self.session.delete(self.c_url)

    def testBasicAuth(self):
        response = requests.put(
            self.c_url+"/1",
            auth=HTTPBasicAuth(self.config['username'], self.config['password']))

        response.raise_for_status()

    def testKeystoneV1(self):
        response = requests.get(self.url,
            headers={
                'x-storage-user': self.config['username'],
                'x-storage-pass': self.config['password'],
            }
        )

        response.raise_for_status()

        url = response.headers['x-storage-url']
        token = response.headers['x-auth-token']

        requests.get(
            url,
            headers={'x-auth-token': token}
        ).raise_for_status()
