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
        self.order_types = ["bids", "asks"]

    # ------------------------------------------------------------------------
    # Fetch data
    # ------------------------------------------------------------------------
    #
    def fetch_from_btc38(self, quote="cny", base="bts"):
        try:
            url = "http://api.btc38.com/v1/depth.php"
            params = {'c': base, 'mk_type': quote}
            response = requests.get(
                url=url, params=params, headers=self.header, timeout=3)
            result = json.loads(vars(response)['_content'].decode("utf-8-sig"))
            for order_type in self.order_types:
                for order in result[order_type]:
                    order[0] = float(order[0])
                    order[1] = float(order[1])
            order_book_ask = sorted(result["asks"])
            order_book_bid = sorted(result["bids"], reverse=True)
            return {"bids": order_book_bid, "asks": order_book_ask}
        except:
            self.log.error("Error fetching results from btc38!")
            return

    def fetch_from_bter(self, quote="cny", base="bts"):
        try:
            url = "http://data.bter.com/api/1/depth/%s_%s" % (base, quote)
            result = requests.get(
                url=url, headers=self.header, timeout=3).json()
            for order_type in self.order_types:
                for order in result[order_type]:
                    order[0] = float(order[0])
                    order[1] = float(order[1])
            order_book_ask = sorted(result["asks"])
            order_book_bid = sorted(result["bids"], reverse=True)
            for bid_order in result["bids"]:
                order_book_bid.append(
                    [float(bid_order[0]), float(bid_order[1])])
            return {"bids": order_book_bid, "asks": order_book_ask}
        except:
            self.log.error("Error fetching results from bter!")
            return

    def fetch_from_yunbi(self, quote="cny", base="bts"):
        try:
            url = "https://yunbi.com/api/v2/depth.json"
            params = {'market': base+quote}
            result = requests.get(
                url=url, params=params, headers=self.header, timeout=3).json()
            for order_type in self.order_types:
                for order in result[order_type]:
                    order[0] = float(order[0])
                    order[1] = float(order[1])
            order_book_ask = sorted(result["asks"])
            order_book_bid = sorted(result["bids"], reverse=True)
            return {"bids": order_book_bid, "asks": order_book_ask}
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
