#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

from bts.api import BTS
import json
import logging
import logging.handlers
import os
import time
import smtplib


class DelegateWatch(object):

    def __init__(self):
        self.load_config()
        self.init_bts()
        self.setup_log()
        self.init_watch()
        self.init_contact()

    def load_config(self):
        config_file = os.getenv("HOME")+"/.python-bts/delegate_watch.json"
        fd_config = open(config_file)
        self.config = json.load(fd_config)["delegate_watch"]
        fd_config.close()
        config_file = os.getenv("HOME")+"/.python-bts/bts_client.json"
        fd_config = open(config_file)
        self.config_bts = json.load(fd_config)[self.config["bts_client"]]
        fd_config.close()

    def init_bts(self):
        config_bts = self.config_bts
        self.bts_client = BTS(config_bts["user"], config_bts["password"],
                              config_bts["host"], config_bts["port"])
        self.delegate_num = int(self.bts_client.chain_info["delegate_num"])
        self.period = float(self.bts_client.chain_info["block_interval"])

    def setup_log(self):
        # Setting up Logger
        self.logger = logging.getLogger('bts')
        self.logger.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s[%(levelname)s]: %(message)s')
        fh = logging.handlers.RotatingFileHandler(
            "/tmp/bts_delegate_watch.log")
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

    def init_watch(self):
        client_info = self.bts_client.get_info()
        self.height = int(client_info["blockchain_head_block_num"])
        self.round_left = int(client_info["blockchain_blocks_left_in_round"])
        self.active_delegates = self.bts_client.list_active_delegates()
        self.active_offset = self.height
        for delegate in self.active_delegates:
            last_block_num = int(
                delegate["delegate_info"]["last_block_num_produced"])
            if last_block_num == self.height:
                break
            self.active_offset -= 1

    def init_contact(self):
        self.contact = {}
        mail_list = self.config["contact"]
        for mail in mail_list:
            if mail_list[mail]["enable"] == 0:
                continue
            for delegate in mail_list[mail]["delegates"]:
                if delegate not in self.contact:
                    self.contact[delegate] = [mail]
                else:
                    self.contact[delegate].append(mail)

    def process_missed_block(self, height):
        index = (height-self.active_offset) % self.delegate_num
        account = self.active_delegates[index]["name"]
        print("missed", height, account)
        self.logger.info("missed %s", account)
        self.active_offset -= 1
        self.notify(account, height)
        return account

    def get_block_delegate(self, height):
        index = (height-self.active_offset) % self.delegate_num
        account = self.active_delegates[index]["name"]
        print("......", height, account)
        self.logger.info("%d %s", height, account)
        return account

    def check_missed_block(self, height):
        limit = height - self.height + 1
        list_blocks = self.bts_client.list_blocks(height, limit)
        last_timestamp = -1
        for block in reversed(list_blocks):
            timestamp = int(block["timestamp"][-2:])
            block_num = int(block["block_num"])
            if last_timestamp != -1:
                period = (timestamp - last_timestamp + 60) % 60
                while period != self.period:
                    period -= self.period
                    self.process_missed_block(block_num)
                self.get_block_delegate(block_num)
            last_timestamp = timestamp

    def notify(self, account, height):
        if account not in self.contact:
            print("no contact")
            return
        print ("sent notify mail")
        sender = self.config["sender"]
        msg_from = "From: %s <%s>\n" % (self.config["name"], sender)
        msg_to = ""
        for receiver in self.contact[account]:
            msg_to = msg_to+"To: <%s>\n" % receiver

        msg_subject = "Subject: missed block attention for %s\n" % account
        msg_content = "you have missed block %d\n" % height
        message = msg_from+msg_to+msg_subject+msg_content
        print(message)
        smtpObj = smtplib.SMTP('localhost')
        smtpObj.sendmail(sender, self.contact[account], message)

    def execute(self):
        while True:
            try:
                client_info = self.bts_client.get_info()
                height = int(client_info["blockchain_head_block_num"])
                if height != self.height:
                    round_left = int(
                        client_info["blockchain_blocks_left_in_round"])
                    if round_left > self.round_left:
                        if self.round_left != 1:
                            round_left = 1
                            height = self.height+self.round_left-1
                        else:
                            self.active_delegates = \
                                self.bts_client.list_active_delegates()
                    self.check_missed_block(height)
                    self.height = height
                    self.round_left = round_left
            except Exception as e:
                self.logger.exception(e)
            now = time.time()
            nexttime = int(now/self.period+1)*self.period - now
            time.sleep(nexttime+1)

if __name__ == '__main__':
    delegate_watch = DelegateWatch()
    delegate_watch.execute()
