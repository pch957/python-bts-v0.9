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

config_file = os.getenv("HOME")+"/.python-bts/bts_client.json"
fd_config = open(config_file)
config_bts = json.load(fd_config)["client_default"]
fd_config.close()

client = BTS(config_bts["user"], config_bts["password"],
             config_bts["host"], config_bts["port"])

print(client.get_asset_precision("CNY"))
print(client.get_asset_precision("BTS"))
print(client.get_asset_precision("BTS"))
print(client.get_asset_precision(0))
