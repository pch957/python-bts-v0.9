# -*- coding: utf-8 -*-
# from decimal import *
#import json
#import requests
#import logging

from bts.misc import trim_float_precision
from bts.misc import to_fixed_point


class BTSMarket():
    def __init__(self, client):
        self.client = client

    def get_order_book1(self, quote, base):
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)

        order_book = {"bids": [], "asks": [], "covers": []}
        order_book_json = self.client.request(
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
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)
        if not self.client.is_peg_asset(quote) or base != "BTS":
            return None

        order_book_short = []
        volume_at_feed_price = 0.0
        feed_price = self.client.get_feed_price(quote)
        order_short = self.client.request(
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

    def market_batch_update(self, canceled, new_orders):
        # v0.9 only support str
        for o in new_orders:
            asset = o[1][2]
            precision = str(int(self.client.get_asset_precision(asset)))
            o[1][1] = trim_float_precision(o[1][1], precision)
            o[1][3] = to_fixed_point(o[1][3])

        trx = self.client.request(
            "wallet_market_batch_update", [canceled, new_orders, True]).json()
        return trx
