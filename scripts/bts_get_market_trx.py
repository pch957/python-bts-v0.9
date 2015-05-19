#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

from bts.market import BTSMarket
from bts.api import BTS
import os
import json
import time
import sys


class GetMarketTrx(object):

    def __init__(self):
        config_file = os.getenv("HOME") + "/.python-bts/bts_client.json"
        fd_config = open(config_file)
        self.config_bts = json.load(fd_config)["client_default"]
        fd_config.close()

        config_bts = self.config_bts
        self.client = BTS(config_bts["user"], config_bts["password"],
                          config_bts["host"], config_bts["port"])
        self.market = BTSMarket(self.client)
        self.height = -1

    def display_deal_trx(self, deal_trx):
        for trx in deal_trx:
            if trx["type"] == "bid":
                deal_type = "buy"
            else:
                deal_type = "sell"
            sys.stdout.write("\n%s %s %s %s %s at price %.4g %s/%s" % (
                trx["timestamp"], trx["block"], deal_type,
                trx["volume"], trx["base"], trx["price"],
                trx["quote"], trx["base"]))

    def display_place_trx(self, place_trx):
        trx_id = ""
        for trx in place_trx:
            if trx_id == trx["trx_id"]:
                sys.stdout.write(".")
                continue
            trx_id = trx["trx_id"]
            if trx["type"] == "cover":
                sys.stdout.write("\n%s %s %s %s %s %s" % (
                    trx["timestamp"], trx["block"], trx["trx_id"], trx["type"],
                    trx["amount"], trx["quote"]))
            elif trx["type"] == "add_collateral":
                sys.stdout.write("\n%s %s %s %s %s %s" % (
                    trx["timestamp"], trx["block"], trx["trx_id"], trx["type"],
                    trx["amount"], trx["base"]))
            else:
                if trx["type"] == "bid":
                    volume = trx["amount"] / trx["price"]
                else:
                    volume = trx["amount"]
                order_type = trx["type"]
                if trx["cancel"]:
                    order_type = "cancel " + trx["type"]
                if trx["price"]:
                    price_str = "%.4g" % trx["price"]
                else:
                    price_str = "unlimited"
                sys.stdout.write("\n%s %s %s %s %s %s at price %s %s/%s" % (
                    trx["timestamp"], trx["block"], trx["trx_id"], order_type,
                    volume, trx["base"], price_str,
                    trx["quote"], trx["base"]))

    def excute(self):
        client_info = self.client.get_info()
        height_now = int(client_info["blockchain_head_block_num"])
        if self.height == -1:
            self.height = height_now - 1000
        while self.height < height_now:
            self.height += 1
            trxs = self.client.get_block_transactions(self.height)
            recs = self.market.get_order_deal_rec(self.height)
            self.display_deal_trx(recs)
            recs = self.market.get_order_place_rec(trxs)
            self.display_place_trx(recs)
            self.market.update_order_owner(recs)

if __name__ == '__main__':
    get_market_trx = GetMarketTrx()
    period = float(get_market_trx .client.chain_info["block_interval"])
    while True:
        try:
            get_market_trx.excute()
        except Exception as e:
            print(e)
        time.sleep(period)
