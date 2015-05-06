# -*- coding: utf-8 -*-
# from decimal import *
import json
import requests
import logging
import re


def to_fixed_point(match):
    """Return the fixed point form of the matched number.

    Parameters:
        match is a MatchObject that matches exp_regex or similar.

    If you wish to make match using your own regex, keep the following in mind:
        group 1 should be the coefficient
        group 3 should be the sign
        group 4 should be the exponent
    """
    sign = -1 if match.group(3) == "-" else 1
    coefficient = float(match.group(1))
    exponent = sign * float(match.group(4))
    if exponent <= 0:
        format_str = "%." + "%d" % (-exponent + len(match.group(1)) - 2) + "f"
    else:
        format_str = "%.1f"
    return format_str % (coefficient * 10 ** exponent)


class BTS():

    def __init__(self, user, password, host, port):
        self.asset_dict = {}
        self.asset_info = {}
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
        exp_regex = re.compile(r"(\d+(\.\d+)?)[Ee](\+|-)(\d+)")
        response = requests.post(self.url, data=exp_regex.sub(
            to_fixed_point, json.dumps(payload)), headers=headers)
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

    def publish_feeds(self, delegate, feed_list):
        response = self.request("wallet_publish_feeds", [delegate, feed_list])
        if response.status_code != 200:
            return False
        else:
            return True

    def transfer(self, trx):
        # v0.9 only support string
        precision = str(int(self.get_asset_precision(trx[1])))
        format_str = "%." + "%d" % (len(precision) - 1) + "f"
        trx[0] = format_str % trx[0]
        response = self.request("wallet_transfer", trx)
        return response.json()

    def market_batch_update(self, canceled, new_orders):
        # v0.9 only support str
        for o in new_orders:
            asset = o[1][2]
            precision = str(int(self.get_asset_precision(asset)))
            format_str = "%." + "%d" % (len(precision) - 1) + "f"
            o[1][1] = format_str % o[1][1]

        trx = self.request(
            "wallet_market_batch_update", [canceled, new_orders, True]).json()
        return trx

    def _get_feed_price(self, quote):
        if quote == "BTS":
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

    def get_feed_price(self, quote, base="BTS"):
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
            return None
        asset_array = response.json()["result"][0][1]
        for item in asset_array:
            _asset = self.get_asset_symbol(item[0])
            balance[_asset] = float(item[1]) / self.get_asset_precision(_asset)

        if asset == "ALL":
            return balance
        elif asset in balance:
            return balance[asset]
        else:
            return None

    def get_order_book1(self, quote, base):
        quote_precision = self.get_asset_precision(quote)
        base_precision = self.get_asset_precision(base)

        order_book = {"bids": [], "asks": [], "covers": []}
        order_book_json = self.request(
            "blockchain_market_order_book", [quote, base]).json()["result"]
        for order in order_book_json[0]:
            _price = float(order["market_index"]["order_price"]["ratio"]) \
                * base_precision / quote_precision
            balance = order["state"]["balance"] / quote_precision
            _volume = float(balance) / _price
            order_book["bids"].append([_price, _volume])
        for order in order_book_json[1]:
            _price = float(order["market_index"]["order_price"]["ratio"]) \
                * base_precision / quote_precision
            if order["type"] == "ask_order":
                _volume = float(order["state"]["balance"]) / base_precision
                order_book["asks"].append([_price, _volume])
            # elif order["type"] == "cover_order":
            #  order_info["balance"] = \
            #    order["state"]["balance"] / quote_precision
            #  order_info["volume"] = order_info["balance"] / price
            #  order_cover.insert(0,order_info)
        return order_book

    def get_order_book2(self, quote, base):
        quote_precision = self.get_asset_precision(quote)
        base_precision = self.get_asset_precision(base)
        if not self.is_peg_asset(quote) or base != "BTS":
            return None

        order_book_short = []
        volume_at_feed_price = 0.0
        feed_price = self.get_feed_price(quote)
        order_short = self.request(
            "blockchain_market_list_shorts", [quote]).json()["result"]
        for order in order_short:
            volume = float(order["state"]["balance"]) / base_precision / 2
            if "limit_price" not in order["state"]:
                volume_at_feed_price += volume
            else:
                price_limit = order["state"]["limit_price"]
                if float(price_limit["ratio"]) * base_precision \
                        / quote_precision >= feed_price:
                    volume_at_feed_price += volume
                else:
                    _price = float(price_limit["ratio"])\
                        * base_precision / quote_precision
                    _volume = volume * feed_price / _price
                    order_book_short.append([_price, _volume])
        if volume_at_feed_price != 0:
            _volume = volume_at_feed_price
            _price = feed_price
            order_book_short.append([_price, _volume])
        return order_book_short

    def get_order_book(self, quote, base):
        order_book = self.get_order_book1(quote, base)
        order_book_short = self.get_order_book2(quote, base)
        order_book["bids"].extend(order_book_short)
        order_book["bids"] = sorted(order_book["bids"], reverse=True)
        return order_book
