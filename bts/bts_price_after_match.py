# -*- coding: utf-8 -*-
#!/usr/bin/python

from bts.exchanges import Exchanges
import time
#from pprint import pprint


class BTSPriceAfterMatch(object):

    def __init__(self, client, exchanges=None):
        self.client = client
        if exchanges:
            self.exchanges = exchanges
        else:
            self.exchanges = Exchanges()
        self.order_book = {}
        self.timeout = 300  # order book can't use after 300 seconds
        self.timestamp_rate_cny = 0
        self.timestamp = 0
        self.rate_cny = []
        self.order_types = ["bids", "asks"]

    def get_rate_from_yahoo(self):
        asset_list_all = ["KRW", "BTC", "SILVER", "GOLD", "TRY",
                          "SGD", "HKD", "RUB", "SEK", "NZD", "CNY",
                          "MXN", "CAD", "CHF", "AUD", "GBP", "JPY",
                          "EUR", "USD", "BDR.AAPL"]
        _rate_cny = self.exchanges.fetch_from_yahoo(asset_list_all)
        if _rate_cny:
            self.timestamp_rate_cny = self.timestamp
            self.rate_cny = _rate_cny

    def change_order_to_cny(self, _order_book, asset):
        if asset not in self.rate_cny:
            return False
        for order_type in self.order_types:
            for order in _order_book[order_type]:
                order[0] = order[0] * self.rate_cny[asset]
        return True

    def get_order_book_from_wallet(self):
        _order_book = self.client.get_order_book("CNY", "BTS")
        if _order_book:
            self.order_book["wallet_cny"] = _order_book
            self.order_book["wallet_cny"]["timestamp"] = self.timestamp
        _order_book = self.client.get_order_book("USD", "BTS")
        if _order_book:
            self.change_order_to_cny(_order_book, "USD")
            self.order_book["wallet_usd"] = _order_book
            self.order_book["wallet_usd"]["timestamp"] = self.timestamp

    def get_order_book_from_exchanges(self):
        _order_book = self.exchanges.fetch_from_btc38()
        if _order_book:
            self.order_book["btc38_cny"] = _order_book
            self.order_book["btc38_cny"]["timestamp"] = self.timestamp
        _order_book = self.exchanges.fetch_from_btc38("btc", "bts")
        if _order_book:
            self.change_order_to_cny(_order_book, "BTC")
            self.order_book["btc38_btc"] = _order_book
            self.order_book["btc38_btc"]["timestamp"] = self.timestamp

        _order_book = self.exchanges.fetch_from_yunbi()
        if _order_book:
            self.order_book["yunbi_cny"] = _order_book
            self.order_book["yunbi_cny"]["timestamp"] = self.timestamp
        _order_book = self.exchanges.fetch_from_bter()
        if _order_book:
            self.order_book["bter_cny"] = _order_book
            self.order_book["bter_cny"]["timestamp"] = self.timestamp

    def get_order_book_all(self):
        self.timestamp = time.time()
        self.order_book_all = {"bids": [], "asks": []}
        if self.timestamp_rate_cny == 0:
            self.get_rate_from_yahoo()
        self.get_order_book_from_exchanges()
        self.get_order_book_from_wallet()
        for market in self.order_book:
            if self.timestamp - self.order_book[market]["timestamp"] \
                    >= self.timeout:
                continue
            for order_type in self.order_types:
                self.order_book_all[order_type].extend(
                    self.order_book[market][order_type])
        self.order_book_all["bids"] = sorted(
            self.order_book_all["bids"], reverse=True)
        self.order_book_all["asks"] = sorted(self.order_book_all["asks"])

    def get_median(self, prices):
        lenth = len(prices)
        _index = int(lenth / 2)
        if lenth % 2 == 0:
            median_price = (prices[_index - 1] + prices[_index]) / 2
        else:
            median_price = prices[_index]
        return median_price

    def get_spread_order_book(self, spread=0.0):
        order_bids = []
        order_asks = []
        for order in self.order_book_all["bids"]:
            order_bids.append([order[0]*(1 + spread), order[1]])
        for order in self.order_book_all["asks"]:
            order_asks.append([order[0]*(1 - spread), order[1]])
        return order_bids, order_asks

    def get_price_list(self, order_bids, order_asks):
        price_list = []
        for order in order_bids:
            if order[0] < order_asks[0][0]:
                break
            if len(price_list) == 0 or order[0] != price_list[-1]:
                price_list.append(order[0])
        for order in order_asks:
            if order[0] < order_bids[0][0]:
                break
            if len(price_list) == 0 or order[0] != price_list[-1]:
                price_list.append(order[0])
        price_list = sorted(price_list)
        return price_list

    def get_match_result(self, order_bids, order_asks, price_list):
        bid_volume = ask_volume = 0
        median_price = self.get_median(price_list)
        for order in order_bids:
            if order[0] < median_price:
                break
            bid_volume += order[1]
        for order in order_asks:
            if order[0] > median_price:
                break
            ask_volume += order[1]
        return ([bid_volume, ask_volume, median_price])

    def get_real_price(self, spread=0.0):
        order_bids, order_asks = self.get_spread_order_book(spread)
        price_list = self.get_price_list(order_bids, order_asks)
        if len(price_list) < 1:
            return [0.0, (order_bids[0][0] + order_asks[0][0]) / 2]
        match_result = []
        while True:
            bid_volume, ask_volume, median_price = self.get_match_result(
                order_bids, order_asks, price_list)
            #### we need to find a price, which can match the max volume
            match_result.append([min(bid_volume, ask_volume),
                                 -(bid_volume+ask_volume), median_price])
            if len(price_list) <= 1:
                break
            if(bid_volume <= ask_volume):
                price_list = price_list[:int(len(price_list) / 2)]
            else:
                price_list = price_list[int(len(price_list) / 2):]

        match_result = sorted(match_result, reverse=True)
        #pprint(match_result)
        return match_result[0]
