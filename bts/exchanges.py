# -*- coding: utf-8 -*-
import requests
import json
import logging


class Exchanges():

    # ------------------------------------------------------------------------
    # Init
    # ------------------------------------------------------------------------
    def __init__(self):
        self.header = {'content-type': 'application/json',
                       'User-Agent': 'Mozilla/5.0 Gecko/20100101 Firefox/22.0'}

        self.log = logging.getLogger('bts')
        self.order_book = {}
        for exchange in ["btc38", "yunbi", "bter"]:
            self.order_book[exchange] = {"asks": [], "bids": []}
        self.true_price_in_cny_per_bts = 0
        self.true_price_in_cny_per_bts_median = 0
        self.rate_cny = {}

    # ------------------------------------------------------------------------
    # Fetch data
    # ------------------------------------------------------------------------
    #
    def fetch_from_btc38(self):
        try:
            exchange = "btc38"
            url = "http://api.btc38.com/v1/depth.php"
            params = {'c': 'bts', 'mk_type': 'cny'}
            response = requests.get(
                url=url, params=params, headers=self.header, timeout=3)
            result = json.loads(vars(response)['_content'].decode("utf-8-sig"))
            self.order_book[exchange]["asks"] = sorted(result["asks"])
            self.order_book[exchange]["bids"] = sorted(result["bids"],
                                                       reverse=True)
            return self.order_book[exchange]
        except:
            self.log.error("Error fetching results from btc38!")
            return

    def fetch_from_bter(self):
        try:
            exchange = "bter"
            url = "http://data.bter.com/api/1/depth/bts_cny"
            result = requests.get(
                url=url, headers=self.header, timeout=3).json()
            self.order_book[exchange]["asks"] = sorted(result["asks"])
            for bid_order in result["bids"]:
                self.order_book[exchange]["bids"].append(
                    [float(bid_order[0]), float(bid_order[1])])
            return self.order_book[exchange]
        except:
            self.log.error("Error fetching results from bter!")
            return

    def fetch_from_yunbi(self):
        try:
            exchange = "yunbi"
            url = "https://yunbi.com/api/v2/depth.json"
            params = {'market': 'btscny'}
            result = requests.get(
                url=url, params=params, headers=self.header, timeout=3).json()
            self.order_book[exchange]["asks"] = sorted(result["asks"])
            self.order_book[exchange]["bids"] = sorted(result["bids"],
                                                       reverse=True)
            return self.order_book[exchange]
        except:
            self.log.error("Error fetching results from yunbi!")
            return

    def get_yahoo_param(self, assets):
        params_s = ""
        for asset in assets:
            if asset == "GOLD":
                asset_yahoo = "XAU"
                params_s = params_s + asset_yahoo + "CNY=X,"
            elif asset == "SILVER":
                asset_yahoo = "XAG"
                params_s = params_s + asset_yahoo + "CNY=X,"
            elif asset == "BDR.AAPL":
                params_s = params_s + "AAPL,"
            elif asset == "OIL" or asset == "GAS" or asset == "DIESEL":
                asset_yahoo = "TODO"
            else:
                asset_yahoo = asset
                params_s = params_s + asset_yahoo + "CNY=X,"
        params = {'s': params_s, 'f': 'l1', 'e': '.csv'}
        return params

    def fetch_from_yahoo(self, assets):
        rate_cny = {}
        url = "http://download.finance.yahoo.com/d/quotes.csv"
        try:
            params = self.get_yahoo_param(assets)
            response = requests.get(
                url=url, headers=self.header, params=params, timeout=3)

            pos = posnext = 0
            for asset in assets:
                posnext = response.text.find("\n", pos)
                rate_cny[asset] = float(response.text[pos:posnext])
                pos = posnext + 1
            if "BDR.AAPL" in rate_cny:
                rate_cny["BDR.AAPL"] = rate_cny[
                    "BDR.AAPL"] * rate_cny["USD"] / 1000
            return(rate_cny)
        except:
            self.log.error("Error fetching results from yahoo!")
            return

    def fetch_from_exchange(self, exchange):
        self.order_book[exchange] = {"asks": [], "bids": []}
        if exchange == "btc38":
            self.fetch_from_btc38()
        elif exchange == "yunbi":
            self.fetch_from_yunbi()
        elif exchange == "bter":
            self.fetch_from_bter()
