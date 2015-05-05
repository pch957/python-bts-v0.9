# -*- coding: utf-8 -*-
#!/usr/bin/env python

from bts.bts_price_after_match import BTSPriceAfterMatch
from bts.api import BTS
import time
import json
import logging
import logging.handlers


class DelegateTask(object):
    def __init__(self, config_file):
        self.load_config(config_file)
        self.init_bts_price()
        self.setup_log()

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
        client = BTS(config_bts["user"], config_bts["password"],
                     config_bts["host"], config_bts["port"])
        self.bts_price = BTSPriceAfterMatch(client)

    def setup_log(self):
        ## Setting up Logger
        self.logger = logging.getLogger('bts')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s[%(levelname)s]: %(message)s')
        fh = logging.handlers.RotatingFileHandler("/tmp/autofeed.log")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def update_price(self):
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
        print(volume, real_price)

    def publish_feed_price(self):
        self.update_price()

    def withdraw_pay(self):
        print('hello')

    def excute(self):
        run_timer = 0
        while True:
            run_timer += 1
            if self.config_price_feed["run_timer"]and \
                    run_timer % self.config_price_feed["run_timer"] == 0:
                self.publish_feed_price()
            if self.config_withdraw_pay["run_timer"]and \
                    run_timer % self.config_withdraw_pay["run_timer"] == 0:
                self.withdraw_pay()
            time.sleep(int(self.config["base_timer"]))


if __name__ == '__main__':
    config_file = "config.json"
    delegate_task = DelegateTask(config_file)
    delegate_task.excute()
