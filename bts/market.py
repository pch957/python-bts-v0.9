# -*- coding: utf-8 -*-
# from decimal import *
#from pprint import pprint

from bts.misc import trim_float_precision
from bts.misc import to_fixed_point


class BTSMarket():
    def __init__(self, client):
        self.client = client
        self.order_owner = [[0, 0]]

    def get_bid_ask(self, quote, base, raw_order_book):
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)

        order_book = {"bids": [], "asks": []}
        for order in raw_order_book[0]:
            _price = float(order["market_index"]["order_price"]["ratio"]) \
                * base_precision / quote_precision
            balance = float(order["state"]["balance"]) / quote_precision
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
                    #_volume = volume * feed_price / _price
                    _volume = volume  # changed since version 0.9.3
                    order_book_short.append([_price, _volume])
        if volume_at_feed_price != 0:
            _volume = volume_at_feed_price
            _price = feed_price
            order_book_short.append([_price, _volume])
        return order_book_short

    def get_cover(self, quote, base, raw_order_book, feed_price):
        timestamp = self.client.get_info()["blockchain_head_block_timestamp"]
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)

        ### maybe here is not exactly right for margin call order
        #price_margin_call = 0.9 * feed_price
        price_margin_call = feed_price
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
        return order_book_cover

    def get_order_book(self, quote, base, cover=False):
        raw_order_book = self.client.request(
            "blockchain_market_order_book", [quote, base, -1]).json()["result"]
        order_book = self.get_bid_ask(quote, base, raw_order_book)

        if self.client.is_peg_asset(quote) and base == "BTS":
            feed_price = self.client.get_feed_price(quote)
            if feed_price is not None:
                order_book["bids"].extend(
                    self.get_short(quote, base, feed_price))
                if cover is True:
                    order_book["asks"].extend(self.get_cover(
                        quote, base, raw_order_book, feed_price))

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

    def get_order_place_stage1(self, _op):
        amount_info = _op["data"]["amount"]
        if _op["type"] == "bid_op_type":
            market_index = _op["data"]["bid_index"]
            order_type = "bid"
        elif _op["type"] == "ask_op_type":
            market_index = _op["data"]["ask_index"]
            order_type = "ask"
        elif _op["type"] == "short_op_v2_type":
            market_index = _op["data"]["short_index"]
            order_type = "short"
        elif _op["type"] == "cover_op_type":
            market_index = _op["data"]["cover_index"]
            order_type = "cover"
        elif _op["type"] == "add_collateral_op_type":
            market_index = _op["data"]["cover_index"]
            order_type = "add_collateral"

        owner = market_index["owner"]
        price_info = market_index["order_price"]
        if order_type == "short":
            if "limit_price" in market_index:
                price_info = market_index["limit_price"]
            else:
                price_info["ratio"] = None
        return order_type, owner, price_info, amount_info

    def get_order_place_stage2(self, args):
        order_type, owner, price_info, amount_info = args
        quote = self.client.get_asset_symbol(price_info["quote_asset_id"])
        base = self.client.get_asset_symbol(price_info["base_asset_id"])
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)
        price = price_info["ratio"]
        if price:
            price = float(price) * base_precision / quote_precision
        if order_type == "cover" or order_type == "bid":
            amount = float(amount_info) / quote_precision
        else:
            amount = float(amount_info) / base_precision
        if amount < 0:
            amount *= -1.0
            cancel = True
        else:
            cancel = False
        return {"type": order_type, "amount": amount, "price": price,
                "quote": quote, "base": base, "owner": owner, "cancel": cancel}

    def get_order_place_rec(self, trxs):
        order_place_recs = []
        for _trx in trxs:
            _trx_id = _trx[0][:8]
            _block = _trx[1]["chain_location"]["block_num"]
            _ops = _trx[1]["trx"]["operations"]
            for _op in _ops:
                if _op["type"] == "update_feed_op_type":
                    break
                if _op["type"] == "bid_op_type" or \
                        _op["type"] == "ask_op_type" or \
                        _op["type"] == "short_op_v2_type" or \
                        _op["type"] == "cover_op_type" or \
                        _op["type"] == "add_collateral_op_type":
                    rec = self.get_order_place_stage2(
                        self.get_order_place_stage1(_op))
                else:
                    continue
                rec["trx_id"] = _trx_id
                rec["block"] = _block
                rec["timestamp"] = self.client.get_block_timestamp(_block)
                order_place_recs.append(rec)
        return order_place_recs

    def get_order_deal(self, price_info, balance_info):
            quote = self.client.get_asset_symbol(
                price_info["order_price"]["quote_asset_id"])
            base = self.client.get_asset_symbol(
                price_info["order_price"]["base_asset_id"])
            quote_precision = self.client.get_asset_precision(quote)
            base_precision = self.client.get_asset_precision(base)
            price = float(price_info["order_price"]["ratio"])\
                * base_precision/quote_precision
            volume = float(balance_info["amount"]) / base_precision
            ### there is a bug, market engine never stop, we should ignore it
            if base != "BTS" or volume > 0.00000000001:
                return {"quote": quote, "base": base, "price": price,
                        "volume": volume}

    def update_order_owner(self, place_recs):
        for rec in place_recs:
            if rec["type"] == "ask":
                order_type = "ask"
            elif rec["type"] == "bid" or rec["type"] == "short":
                order_type = "bid"
            else:
                continue
            type_owner = [order_type, rec["owner"]]
            if type_owner != self.order_owner[0]:
                self.order_owner.insert(0, type_owner)
                if len(self.order_owner) > 100:
                    self.order_owner.pop()

    def get_order_deal_rec(self, height):
        order_deal_recs = []
        trxs = self.client.request(
            "blockchain_list_market_transactions", [height]).json()["result"]
        for _trx in trxs:
            trx_type = "bid"
            bid_owner = _trx["bid_index"]["owner"]
            ask_owner = _trx["ask_index"]["owner"]
            key_balance = "%s_received" % trx_type
            key_price = "%s_index" % trx_type
            for owner in self.order_owner:
                if owner[0] == "bid" and bid_owner == owner[1]:
                    break
                elif owner[0] == "ask" and ask_owner == owner[1]:
                    trx_type = "ask"
                    key_balance = "%s_paid" % trx_type
                    key_price = "%s_index" % trx_type
                    break
            rec = self.get_order_deal(_trx[key_price], _trx[key_balance])
            if not rec:
                continue
            timestamp = self.client.get_block_timestamp(height)
            rec["timestamp"] = timestamp
            rec["type"] = trx_type
            rec["block"] = height
            order_deal_recs.append(rec)
        return order_deal_recs

    def _get_my_order_book(self, quote, base, account=""):
        return self.client.request("wallet_market_order_list",
                                   [quote, base, -1, account]).json()["result"]

    def parser_my_order_book(self, quote, base, raw_orders):
        ### todo, shorts and covers
        order_ids = []
        order_book = {"bids": [], "asks": [], "shorts": [], "covers": []}
        quote_precision = self.client.get_asset_precision(quote)
        base_precision = self.client.get_asset_precision(base)
        for item in raw_orders:
            order_ids.append(item[0])
            order = item[1]
            if order["type"] == "ask_order":
                _price = float(order["market_index"]["order_price"]["ratio"]) \
                    * base_precision / quote_precision
                _volume = float(order["state"]["balance"]) / base_precision
                order_book["asks"].append([_price, _volume])
            elif order["type"] == "bid_order":
                _price = float(order["market_index"]["order_price"]["ratio"]) \
                    * base_precision / quote_precision
                _volume = float(order["state"]["balance"]) / \
                    quote_precision / _price
                order_book["bids"].append([_price, _volume])
        order_book["asks"] = sorted(order_book["asks"])
        order_book["bids"] = sorted(order_book["bids"], reverse=True)
        return order_ids, order_book

    def get_my_order_book(self, quote, base, account=""):
        raw_orders = self._get_my_order_book(quote, base, account)
        order_ids, order_book = self.parser_my_order_book(
            quote, base, raw_orders)
        return order_book

    def get_market_status(self, quote, base):
        ## peg assest: lastfeed, cover_order_expired_time, timestamp,
        pass

    def need_update_order_book(self, market, block_info, market_status,
                               deal_trx, place_trx):
        pass
