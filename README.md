openstack_api_conformance
=========================

A test suite which verifies the stability and conformance with various OpenStack APIs.

Use: create a file named .testconfig with the following contents:

    {
        "keystone": {
            "username": "tha_username",
            "password": "teh-passwd",
            "tenantId": "abcdef0123456789",
            "tenantName": "the Tenant nam",
            "url": "http://identity.stack.cloudvps.com/"
        },
        "swift": {
            "username": "tha_username",
            "password": "teh-passwd",
            "tenantId": "abcdef0123456789",
            "auth_url": "http://identity.stack.cloudvps.com/"
        }
    }

Then, run nosetests.