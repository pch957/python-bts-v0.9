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

    def get_bid_ask(self, quote, base, raw_order_book):
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)

        order_book = {"bids": [], "asks": []}
        for order in raw_order_book[0]:
            _price = float(order["market_index"]["order_price"]["ratio"]) \
                * base_precision / quote_precision
            balance = order["state"]["balance"] / quote_precision
            _volume = float(balance) / _price
            order_book["bids"].append([_price, _volume])
        for order in raw_order_book[1]:
            _price = float(order["market_index"]["order_price"]["ratio"]) \
                * base_precision / quote_precision
            if order["type"] == "ask_order":
                _volume = float(order["state"]["balance"]) / base_precision
                order_book["asks"].append([_price, _volume])
        return order_book

    def get_short(self, quote, base, feed_price):
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)

        order_short = self.client.request(
            "blockchain_market_list_shorts", [quote]).json()["result"]
        order_book_short = []
        volume_at_feed_price = 0.0
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

    def get_cover(self, quote, base, raw_order_book, feed_price, timestamp):
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)

        ### maybe here is not exactly right for margin call order
        price_margin_call = 0.9 * feed_price
        #price_margin_call = feed_price
        volume_margin_call = 0.0
        volume_expired = 0.0
        for order in raw_order_book[1]:
            if order["type"] == "ask_order":
                continue
            _price = float(order["market_index"]["order_price"]["ratio"]) \
                * base_precision / quote_precision
            if _price > price_margin_call:
                _balance = order["state"]["balance"] / quote_precision
                _volume = _balance / price_margin_call
                volume_margin_call += _volume
            elif timestamp is not None and timestamp > order["expiration"]:
                _balance = order["state"]["balance"] / quote_precision
                _volume = _balance / feed_price
                volume_expired += _volume
        order_book_cover = []
        if volume_expired != 0.0:
            order_book_cover.append([feed_price, volume_expired])
        if volume_margin_call != 0.0:
            order_book_cover.append([price_margin_call, volume_margin_call])
        #print(order_book_cover)
        return order_book_cover

    def get_order_book(self, quote, base, timestamp=None):
        raw_order_book = self.client.request(
            "blockchain_market_order_book", [quote, base, -1]).json()["result"]
        order_book = self.get_bid_ask(quote, base, raw_order_book)

        if self.client.is_peg_asset(quote) and base == "BTS":
            feed_price = self.client.get_feed_price(quote)
            if feed_price is not None:
                order_book["bids"].extend(
                    self.get_short(quote, base, feed_price))
                order_book["asks"].extend(
                    self.get_cover(quote, base, raw_order_book,
                                   feed_price, timestamp))

        order_book["asks"] = sorted(order_book["asks"])
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
