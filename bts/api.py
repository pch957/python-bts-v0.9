# -*- coding: utf-8 -*-
# from decimal import *
import json
import requests
import logging

from bts.misc import trim_float_precision
from bts.misc import to_fixed_point


class BTS():

    def __init__(self, user, password, host, port):
        self.asset_dict = {}
        self.asset_info = {}
        self.block_timestamp = {}
        self.url = "http://%s:%s@%s:%s/rpc" % (user, password, host, str(port))
        self.log = logging.getLogger('bts')
        # self.log.info("Initializing with URL:  " + self.url)

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

    def get_info(self):
        return self.request("get_info", []).json()["result"]

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

    def get_time_stamp(self, block):
        if block not in self.block_timestamp:
            block_info = self.request(
                "blockchain_get_block", [block]).json()["result"]
            self.block_timestamp[block] = block_info["timestamp"]
            if len(self.block_timestamp) >= 1000:
                for _block in sorted(self.order_book.keys())[:500]:
                    self.order_book.pop(_block)
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

    def get_balance(self, account="", asset="ALL"):
        balance = {}
        response = self.request("wallet_account_balance", [account])
        if len(response.json()["result"]) < 1:
            if asset == "ALL":
                return None
            else:
                return 0.0
        asset_array = response.json()["result"][0][1]
        for item in asset_array:
            _asset = self.get_asset_symbol(item[0])
            balance[_asset] = float(item[1]) / self.get_asset_precision(_asset)

        if asset == "ALL":
            return balance
        elif asset in balance:
            return balance[asset]
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

    def list_active_delegates(self, first=0, count=101):
        return self.request("blockchain_list_active_delegates",
                            [first, count]).json()["result"]

    def get_block_transactions(self, height):
        return self.request("blockchain_get_block_transactions",
                            [height]).json()["result"]

    def is_chain_sync(self):
        blockchain_info = self.get_info()
        age = int(blockchain_info["blockchain_head_block_age"])
        participation = \
            blockchain_info["blockchain_average_delegate_participation"]
        if participation is not None:
            participation = int(participation)
        else:
            participation = 0

        if age > 15 or participation < 80:
            return False
        return True
