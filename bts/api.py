# -*- coding: utf-8 -*-
# from decimal import *
import json
import requests
import logging
import time

from bts.misc import trim_float_precision
from bts.misc import to_fixed_point


class BTS():

    def __init__(self, user, password, host, port):
        self.asset_dict = {}
        self.asset_info = {}
        self.block_timestamp = {}
        self.url = "http://%s:%s@%s:%s/rpc" % (user, password, host, str(port))
        self.log = logging.getLogger('bts')
        self.init_chain_info()
        self.client_info = self._get_info()
        # self.log.info("Initializing with URL:  " + self.url)

    def init_chain_info(self):
        self.chain_info = self.request(
            "blockchain_get_info", []).json()["result"]

    def request(self, method, *args):
        payload = {
            "method": method,
            "params": list(*args),
            "jsonrpc": "2.0",
            "id": 0,
        }
        headers = {
            'content-type': 'application/json',
            'Authorization': "Basic YTph"
        }
        response = requests.post(self.url, data=to_fixed_point(
            json.dumps(payload)), headers=headers)
        return response

    def _get_info(self):
        client_info = self.request("get_info", []).json()["result"]
        client_info["seconds"] = time.time()
        return client_info

    def get_info(self):
        seconds = time.time()
        seconds_last = self.client_info["seconds"]
        interval = float(self.chain_info["block_interval"])
        if seconds - seconds_last >= interval*0.9:
            self.client_info = self._get_info()
        return self.client_info

    def get_asset_info(self, asset):
        asset = str(asset)
        if asset not in self.asset_info:
            result = self.request(
                "blockchain_get_asset", [asset]).json()["result"]
            self.asset_info[str(result["id"])] = \
                self.asset_info[result["symbol"]] = result
        return self.asset_info[asset]

    def get_asset_precision(self, asset):
        return self.get_asset_info(asset)["precision"]

    def get_asset_id(self, asset):
        return self.get_asset_info(asset)["id"]

    def get_asset_symbol(self, asset):
        return self.get_asset_info(asset)["symbol"]

    def is_peg_asset(self, asset):
        return int(self.get_asset_info(asset)["issuer_id"]) == -2

    def get_block_timestamp(self, block):
        if block not in self.block_timestamp:
            block_info = self.request(
                "blockchain_get_block", [block]).json()["result"]
            self.block_timestamp[block] = block_info["timestamp"]
            if len(self.block_timestamp) >= 1000:
                for _block in sorted(self.block_timestamp.keys())[:500]:
                    self.block_timestamp.pop(_block)
        return self.block_timestamp[block]

    def publish_feeds(self, delegate, feed_list):
        # v0.9 only support string
        for feed in feed_list:
            feed[1] = to_fixed_point(feed[1])
        response = self.request("wallet_publish_feeds", [delegate, feed_list])
        if response.status_code != 200:
            return False
        else:
            return True

    def transfer(self, trx):
        # v0.9 only support string
        precision = str(int(self.get_asset_precision(trx[1])))
        trx[0] = trim_float_precision(trx[0], precision)
        response = self.request("wallet_transfer", trx)
        return response.json()

    def _get_feed_price(self, quote):
        if self.get_asset_id(quote) == 0:
            return 1.0
        elif not self.is_peg_asset(quote):
            return None
        else:
            feeds = self.request(
                "blockchain_get_feeds_for_asset", [quote]).json()["result"]
            if feeds[-1]["delegate_name"] == "MARKET":
                return float(feeds[-1]["median_price"])
            else:
                return None

    def get_feed_price(self, quote, base=0):
        feed_price_base = self._get_feed_price(base)
        feed_price_quote = self._get_feed_price(quote)
        if feed_price_base and feed_price_quote:
            return feed_price_quote / feed_price_base
        else:
            return None

    def _get_balance(self, account=""):
        response = self.request("wallet_account_balance", [account])
        if len(response.json()["result"]) < 1:
            return None
        return response.json()["result"]

    def get_balance(self, account="", asset="ALL"):
        balance_list = self._get_balance(account)
        if balance_list is None:
            if asset == "ALL":
                return None
            else:
                return 0.0
        balance = {}
        for account_list in balance_list:
            _account = account_list[0]
            _balance = {}
            for item in account_list[1]:
                _asset = self.get_asset_symbol(item[0])
                _balance[_asset] = \
                    float(item[1]) / self.get_asset_precision(_asset)
            balance[_account] = _balance

        if asset == "ALL":
            return balance
        elif asset in balance:
            return balance[account][asset]
        else:
            return 0.0

    def get_account_info(self, account):
        return self.request(
            "blockchain_get_account", [account]).json()["result"]

    def delegate_withdraw_pay(self, delegate_account, pay_account, amount):
        # v0.9 only support string
        precision = str(int(self.get_asset_precision(0)))
        amount = trim_float_precision(amount, precision)
        self.request("wallet_delegate_withdraw_pay",
                     [delegate_account, pay_account, amount])

    def list_blocks(self, height, limit):
        return self.request(
            "blockchain_list_blocks", [height, limit]).json()["result"]

    def list_active_delegates(self, first=0, count=0):
        if count == 0:
            count = int(self.chain_info["delegate_num"])
        return self.request("blockchain_list_active_delegates",
                            [first, count]).json()["result"]

    def get_block_transactions(self, height):
        return self.request("blockchain_get_block_transactions",
                            [height]).json()["result"]

    def is_chain_sync(self):
        client_info = self.get_info()
        age = int(client_info["blockchain_head_block_age"])
        participation = \
            client_info["blockchain_average_delegate_participation"]
        if participation is not None:
            participation = int(participation)
        else:
            participation = 0

        if age > 15 or participation < 80:
            return None
        return client_info
