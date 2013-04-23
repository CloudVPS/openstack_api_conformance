import os
import json

# An javascript-like dictionary, which return None for non-existing keys, and
# exposes keys according
class AttributeDict(dict):
    def __getitem__(self, key):
        return dict.get(self,key)
    def __getattr__(self, attr):
        return self.get(attr)
    def __setattr__(self, attr, value):
        self[attr] = value

def get_configuration():
    config_filename = os.environ.get('TEST_CONFIG') or ".testconfig"

    with open(config_filename, 'r') as config_file:
        return json.load(config_file, object_hook=AttributeDict)
