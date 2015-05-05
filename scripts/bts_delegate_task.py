#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

from bts.bts_price_after_match import BTSPriceAfterMatch
from bts.api import BTS
import time
import json
import logging
import logging.handlers
from math import fabs
import os


class DelegateTask(object):

    def __init__(self, config_file):
        self.load_config(config_file)
        self.init_bts_price()
        self.setup_log()
        self.init_task_feed_price()

    def load_config(self, config_file):
        fs_config = open(config_file)
        self.config = json.load(fs_config)
        self.config_bts = self.config["bts_client"]
        self.config = self.config["delegate_tasks"]
        self.config_price_feed = self.config["price_feed"]
        self.config_withdraw_pay = self.config["withdraw_pay"]
        fs_config.close()

    def init_bts_price(self):
        config_bts = self.config_bts
        self.client = BTS(config_bts["user"], config_bts["password"],
                          config_bts["host"], config_bts["port"])
        self.bts_price = BTSPriceAfterMatch(self.client)

    def setup_log(self):
        # Setting up Logger
        self.logger = logging.getLogger('bts')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s[%(levelname)s]: %(message)s')
        fh = logging.handlers.RotatingFileHandler("/tmp/bts_delegate_task.log")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def init_task_feed_price(self):
        peg_asset_list = ["KRW", "BTC", "SILVER", "GOLD", "TRY",
                          "SGD", "HKD", "RUB", "SEK", "NZD", "CNY",
                          "MXN", "CAD", "CHF", "AUD", "GBP", "JPY",
                          "EUR", "USD"]
        self.price_queue = {}
        for asset in peg_asset_list:
            self.price_queue[asset] = []
        self.time_publish_feed = 0
        self.last_publish_price = {}
        # Actually I think it may be beneficial to discount all feeds by 0.995
        # to give the market makers some breathing room and provide a buffer
        # against down trends.
        self.discount = 0.995

    def fetch_bts_price(self):
        # updat rate cny
        self.bts_price.get_rate_from_yahoo()

        # get all order book
        self.bts_price.get_order_book_all()

        # can add weight here
        for order_type in self.bts_price.order_types:
            for market in self.config_price_feed["market_weight"]:
                if market not in self.bts_price.order_book:
                    continue
                for _order in self.bts_price.order_book[market][order_type]:
                    _order[1] *= \
                        self.config_price_feed["market_weight"][market]

        # calculate real price
        volume, volume_sum, real_price = self.bts_price.get_real_price(
            spread=self.config_price_feed["price_limit"]["spread"])
        self.logger.info("fetch price is %.5f CNY/BTS, volume is %.3f",
                         real_price, volume)
        return real_price

    def get_median_price(self, bts_price_in_cny):
        median_price = {}
        for asset in self.price_queue:
            if asset not in self.bts_price.rate_cny:
                continue
            self.price_queue[asset].append(bts_price_in_cny
                                           / self.bts_price.rate_cny[asset])
            if len(self.price_queue[asset]) > \
                    self.config_price_feed["price_limit"]["median_length"]:
                self.price_queue[asset].pop(0)
            median_price[asset] = sorted(
                self.price_queue[asset])[int(len(self.price_queue[asset]) / 2)]
        return median_price

    def get_feed_price(self):
        current_feed_price = {}
        for asset in self.price_queue:
            current_feed_price[asset] = self.client.get_feed_price(asset)
        return current_feed_price

    def publish_rule_check(self, median_price, current_feed_price):
        # When attempting to write a market maker the slow movement of the feed
        # can be difficult.
        # I would recommend the following:
        # if  REAL_PRICE < MEDIAN and YOUR_PRICE > MEDIAN publish price
        # if  you haven't published a price in the past 20 minutes
        #   if  REAL_PRICE > MEDIAN  and  YOUR_PRICE < MEDIAN and
        # abs( YOUR_PRICE - REAL_PRICE ) / REAL_PRICE  > 0.005 publish price
        # The goal is to force the price down rapidly and allow it to creep up
        # slowly.
        # By publishing prices more often it helps market makers maintain the
        # peg and minimizes opportunity for shorts to sell USD below the peg
        # that the market makers then have to absorb.
        # If we can get updates flowing smoothly then we can gradually reduce
        # the spread in the market maker bots.
        #*note: all prices in USD per BTS
        if time.time() - self.time_publish_feed > \
                self.config_price_feed["max_update_hours"] * 60 * 60:
            return True
        for asset in median_price:
            price_change = 100.0 * (
                median_price[asset] - self.last_publish_price[asset]) \
                / self.last_publish_price[asset]

            if median_price[asset] < current_feed_price[asset] / \
                    self.discount and self.last_publish_price[asset] > \
                    current_feed_price[asset] / self.discount:
                return True
            # if  you haven't published a price in the past 20 minutes,
            # and the price change more than 0.5%
            change_min = self.config_price_feed["price_limit"]["change_min"]
            if fabs(price_change) > change_min and \
                    time.time() - self.time_publish_feed > 20 * 60:
                return True
        return False

    def check_median_price(self, median_price, current_feed_price):
        for asset in median_price:
            price_change = 100.0 * (
                median_price[asset] - current_feed_price[asset]) \
                / current_feed_price[asset]
            # don't publish price which change more than "change_max"
            if fabs(price_change) > \
                    self.config_price_feed["price_limit"]["change_max"]:
                median_price.pop(asset)

    def publish_feed_price(self, median_price):
        self.time_publish_feed = time.time()
        self.last_publish_price = median_price
        publish_feeds = []
        for asset in median_price:
            publish_feeds.append(
                [asset, "%.15f" % (median_price[asset] * self.discount)])
        self.logger.info("publish price %s", publish_feeds)
        for delegate in self.config["delegate_list"]:
            self.client.publish_feeds(delegate, publish_feeds)

    def display_price(self, median_price, current_feed_price):
        os.system("clear")
        print("================ %s ===================" %
              time.strftime("%Y%m%dT%H%M%S", time.localtime(time.time())))
        print("   ASSET  RATE(CNY)    CURRENT_FEED   LAST_PUBLISH")
        print("-----------------------------------------------------")
        for asset in sorted(median_price):
            _rate_cny = self.bts_price.rate_cny[asset]
            _current_feed_price = current_feed_price[asset]
            _last_publish_price = self.last_publish_price[asset]

            print(
                '{: >8}'.format("%s" % asset), '{: >10}'.
                format('%.3f' % _rate_cny), '{: >15}'.
                format("%.4g" % _current_feed_price), '{: >15}'.
                format('%.4g' % _last_publish_price))
        print("====================================================")

    def task_feed_price(self):
        bts_price_in_cny = self.fetch_bts_price()
        median_price = self.get_median_price(bts_price_in_cny)
        current_feed_price = self.get_feed_price()
        if self.publish_rule_check(median_price, current_feed_price):
            self.check_median_price(median_price, current_feed_price)
            self.publish_feed_price(median_price)
        self.display_price(median_price, current_feed_price)

    def withdraw_pay(self):
        for pay_list in self.config_withdraw_pay["pay_list"]:
            for delegate_account in pay_list["delegate_account"]:
                pay_balance = pay_list["pay_balance"]
                response = self.client.request("blockchain_get_account",
                                               [delegate_account])
                account_info = response.json()["result"]
                balance = float(account_info['delegate_info']['pay_balance'])/(
                    self.client.get_asset_precision("BTS"))
                if balance > pay_balance + 10:
                    for pay_account, percent in pay_list["pay_account"]:
                        print(delegate_account, pay_account,
                              pay_balance*percent)
                        #self.client.request("wallet_delegate_withdraw_pay",
                        #                    [delegate_account, pay_account,
                        #                     pay_balance*percent])

    def task_withdraw_pay(self):
        self.withdraw_pay()

    def excute(self):
        run_timer = 0
        while True:
            if self.config_price_feed["run_timer"]and \
                    run_timer % self.config_price_feed["run_timer"] == 0:
                self.task_feed_price()
            if self.config_withdraw_pay["run_timer"]and \
                    run_timer % self.config_withdraw_pay["run_timer"] == 0:
                self.task_withdraw_pay()
            run_timer += 1
            time.sleep(int(self.config["base_timer"]))

if __name__ == '__main__':
    config_file = os.getenv("HOME")+"/.python-bts.json"
    if not os.path.isfile(config_file):
        config_file = "/etc/python-bts.json"
    delegate_task = DelegateTask(config_file)
    try:
        delegate_task.excute()
    except Exception as e:
        delegate_task.logger.exception(e)
