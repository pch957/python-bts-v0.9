# -*- coding: utf-8 -*-
#!/usr/bin/python

#from pytest import raises

# The parametrize function is generated, so this doesn't work:
#
#     from pytest.mark import parametrize
#
from bts.api import BTS
import json
import os


config_file_name = os.getenv("HOME")+"/.python-bts.json"
if not os.path.isfile(config_file_name):
    config_file_name = "/etc/python-bts.json"
config_file = open(config_file_name)
config = json.load(config_file)
config_bts = config["bts_client"]
config_file.close()
client = BTS(config_bts["user"], config_bts["password"],
             config_bts["host"], config_bts["port"])

print(client.get_asset_precision("CNY"))
print(client.get_asset_precision("BTS"))
print(client.get_asset_precision("BTS"))
print(client.get_asset_precision(0))
