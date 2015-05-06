# -*- coding: utf-8 -*-
#from pytest import raises

# The parametrize function is generated, so this doesn't work:
#
#     from pytest.mark import parametrize
#
import pytest
parametrize = pytest.mark.parametrize

from bts.api import BTS
from bts.exchanges import Exchanges
from bts.bts_price_after_match import BTSPriceAfterMatch
import json
from pprint import pprint
import os


class TestMain(object):
    logfile = open("/tmp/test-bts-api.log", 'a')
    config_file = os.getenv("HOME")+"/.python-bts/bts_client.json"
    fd_config = open(config_file)
    config_bts = json.load(fd_config)["client_default"]
    fd_config.close()
    client = BTS(config_bts["user"], config_bts["password"],
                 config_bts["host"], config_bts["port"])

    def test_info(self):
        result = self.client.request("get_info", []).json()["result"]
        pprint("======= test_info =========", self.logfile)
        pprint(result, self.logfile)
        assert result["blockchain_head_block_num"] > 1

    def test_asset_info(self):
        result = self.client.get_asset_info("BTS")
        assert result["symbol"] == "BTS"
        result = self.client.get_asset_info(0)
        assert result["id"] == 0
        pprint("======= test_asset_info =========", self.logfile)
        pprint(result, self.logfile)

    def test_is_asset_peg(self):
        assert self.client.is_peg_asset("CNY")
        assert not self.client.is_peg_asset("BTS")
        assert not self.client.is_peg_asset("BTSBOTS")

    def test_asset_precision(self):
        assert self.client.get_asset_precision("CNY") == 10**4
        assert self.client.get_asset_precision("BTS") == 10**5
        assert self.client.get_asset_precision("BTSBOTS") == 10**2

    def test_feed_price(self):
        feed_price_cny = self.client.get_feed_price("CNY")
        feed_price_usd = self.client.get_feed_price("USD")
        feed_price_usd_per_cny = self.client.get_feed_price("USD", base="CNY")
        assert feed_price_usd_per_cny == feed_price_usd / feed_price_cny
        assert not self.client.get_feed_price("BTSBOTS")

    def test_get_balance(self):
        balance = self.client.get_balance()
        pprint("======= test_get_balance =========", self.logfile)
        pprint(balance, self.logfile)

    def test_order_book(self):
        order_book = self.client.get_order_book("CNY", "BTS")
        pprint("======= test_order_book =========", self.logfile)
        pprint(order_book, self.logfile)
        assert len(order_book) > 0
    #def test_publish_feeds(self):
    #def test_transfer(self):
    #def test_market_batch_update(self):

    def test_exchanges_yahoo(self):
        exchanges = Exchanges()
        asset_list_all = ["KRW", "BTC", "SILVER", "GOLD", "TRY",
                          "SGD", "HKD", "RUB", "SEK", "NZD", "CNY",
                          "MXN", "CAD", "CHF", "AUD", "GBP", "JPY",
                          "EUR", "USD", "BDR.AAPL"]
        rate_cny = exchanges.fetch_from_yahoo(asset_list_all)
        pprint("======= test_exchanges_yahoo =========", self.logfile)
        pprint(rate_cny, self.logfile)
        assert rate_cny["USD"] > 0

    def test_exchanges_yunbi(self):
        exchanges = Exchanges()
        order_book = exchanges.fetch_from_yunbi()
        pprint("======= test_exchanges_yunbi =========", self.logfile)
        pprint(order_book, self.logfile)
        assert len(order_book["bids"]) > 0

    def test_exchanges_btc38(self):
        exchanges = Exchanges()
        order_book = exchanges.fetch_from_btc38()
        pprint("======= test_exchanges_btc38 =========", self.logfile)
        pprint(order_book, self.logfile)
        assert len(order_book["bids"]) > 0

    def test_exchanges_bter(self):
        exchanges = Exchanges()
        order_book = exchanges.fetch_from_bter()
        pprint("======= test_exchanges_bter =========", self.logfile)
        pprint(order_book, self.logfile)
        assert len(order_book["bids"]) > 0

    def test_bts_price_after_match(self):
        bts_price = BTSPriceAfterMatch(self.client)
        bts_price.get_rate_from_yahoo()

        # get all order book
        bts_price.get_order_book_all()

        # can add weight here
        for order_type in bts_price.order_types:
            for _order in bts_price.order_book["wallet_usd"][order_type]:
                _order[1] *= 0.5

        # calculate real price
        volume, volume2, real_price = bts_price.get_real_price(spread=0.01)
        pprint("======= test_bts_price_after_match =========", self.logfile)
        pprint([volume, real_price], self.logfile)
        assert volume > 0
