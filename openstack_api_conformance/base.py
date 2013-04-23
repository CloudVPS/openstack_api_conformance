import unittest2
import sys
import json

class TestCase(unittest2.TestCase):
	def __init__(self, *a, **b):
		self.config = get_configuration()
		super(TestCase, self).__init__(*a, **b)


def get_configuration():
	config_filename = sys.environ.get('TEST_CONFIG') or ".testconfig"

	with open(config_filename, 'r') as config_file:
		return json.load(config_file)
