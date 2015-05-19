#!/usr/bin/env python2
# coding=utf8 sw=1 expandtab ft=python

from __future__ import print_function
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks

from autobahn.twisted.wamp import ApplicationSession
from autobahn.wamp import auth
from autobahn.twisted.util import sleep

from twisted.internet.protocol import ReconnectingClientFactory
from autobahn.websocket.protocol import parseWsUrl
from autobahn.twisted import wamp, websocket
from autobahn.wamp import types
import time

import os
import json

from bts.market import BTSMarket
from bts.api import BTS


def get_prefix(quote, base):
    prefix = "%s_%s" % (quote, base)
    prefix = prefix.replace('.', '-')
    return prefix


class PublishMarket(object):
    def __init__(self):
        self.pusher = None
        self.order_book = {}
        self.init_market()

    def init_market(self):
        config_file = os.getenv("HOME") + "/.python-bts/bts_client.json"
        fd_config = open(config_file)
        config_bts = json.load(fd_config)["client_default"]
        fd_config.close()

        self.bts_client = BTS(config_bts["user"], config_bts["password"],
                              config_bts["host"], config_bts["port"])
        self.market = BTSMarket(self.bts_client)
        client_info = self.bts_client.get_info()
        self.height = int(client_info["blockchain_head_block_num"])

    def myPublish(self, topic, event):
        if self.pusher:
            self.pusher.publish(topic, event, c=topic)

    def publish_deal_trx(self, deal_trx):
        for trx in deal_trx:
            if trx["type"] == "bid":
                deal_type = "buy"
            else:
                deal_type = "sell"
            prefix = get_prefix(trx["quote"], trx["base"])
            format_trx = [prefix, trx["block"], trx["timestamp"],
                          deal_type, trx["price"], trx["volume"]]
            self.myPublish(
                u'bts.orderbook.%s.trx' % (format_trx[0]), format_trx[1:])
            self.myPublish(u'bts.orderbook.trx', format_trx)
            print(format_trx)

    def publish_place_trx(self, place_trx):
        trx_id = ""
        for trx in place_trx:
            if trx_id == trx["trx_id"]:
                continue
            prefix = get_prefix(trx["quote"], trx["base"])
            trx_id = trx["trx_id"]
            if trx["cancel"]:
                trx["type"] = "cancel " + trx["type"]
            format_trx = [prefix, trx["block"], trx["timestamp"],
                          trx["type"], trx["price"], trx["amount"]]
            self.myPublish(
                u'bts.orderbook.%s.order' % (format_trx[0]), format_trx[1:])
            self.myPublish(u'bts.orderbook.order', format_trx)
            print(format_trx)

    def publish_order_book(self):
        market_list = [
            ["BOTSCNY", "BTS"], ["CNY", "BTS"], ["USD", "BTS"],
            ["GOLD", "BTS"], ["BTC", "BTS"], ["BDR.AAPL", "CNY"],
            ["NOTE", "BTS"]]
        for quote, base in market_list:
            prefix = get_prefix(quote, base)
            order_book = self.market.get_order_book(
                quote, base)
            order_book["bids"] = order_book["bids"][:10]
            order_book["asks"] = order_book["asks"][:10]
            if (prefix not in self.order_book or
               self.order_book[prefix] != order_book):
                self.order_book[prefix] = order_book
                self.myPublish(
                    u'bts.orderbook.%s' % prefix, order_book)

    def execute(self):
        client_info = self.bts_client.get_info()
        height_now = int(client_info["blockchain_head_block_num"])
        if(self.height < height_now):
            time_stamp = client_info["blockchain_head_block_timestamp"]
            self.myPublish(u'bts.blockchain.info',
                           {"height": height_now, "time_stamp": time_stamp})
            self.publish_order_book()
        while self.height < height_now:
            self.height += 1
            trxs = self.bts_client.get_block_transactions(
                self.height)
            recs = self.market.get_order_deal_rec(self.height)
            self.publish_deal_trx(recs)
            recs = self.market.get_order_place_rec(trxs)
            self.publish_place_trx(recs)
            self.market.update_order_owner(recs)


class Component(ApplicationSession):
    task_token = 0
    config = {}
    publish_market = None

    @staticmethod
    def init():
        Component.publish_market = PublishMarket()
        config_file = os.getenv("HOME")+"/.python-bts/pusher.json"
        fd_config = open(config_file)
        Component.config = json.load(fd_config)
        fd_config.close()

    def onConnect(self):
        self.join(self.config.realm, [u"wampcra"], Component.config["user"])

    def onChallenge(self, challenge):
        key = Component.config["password"].encode('utf8')
        signature = auth.compute_wcs(
            key, challenge.extra['challenge'].encode('utf8'))
        return signature.decode('ascii')

    @inlineCallbacks
    def onJoin(self, details):
        Component.task_token += 1
        my_token = Component.task_token
        print("session attached")
        Component.publish_market.pusher = self
        period = float(
            Component.publish_market.bts_client.chain_info["block_interval"])

        while my_token == Component.task_token:
            try:
                Component.publish_market.execute()
            except Exception as e:
                print(e)
            now = time.time()
            nexttime = int(time.time()/period + 1)*period - now
            yield sleep(nexttime+1)

    def onLeave(self, details):
        Component.publish_market.pusher = None
        #print("onLeave: {}".format(details))
        print("onLeave()")

    def onDisconnect(self):
        print("onDisconnect()")


class MyClientFactory(websocket.WampWebSocketClientFactory,
                      ReconnectingClientFactory):
    maxDelay = 30

    def clientConnectionFailed(self, connector, reason):
        # print "reason:", reason
        ReconnectingClientFactory.clientConnectionFailed(
            self, connector, reason)

    def clientConnectionLost(self, connector, reason):
        print("Connection Lost")
        # print "reason:", reason
        ReconnectingClientFactory.clientConnectionLost(self, connector, reason)


if __name__ == '__main__':
    Component.init()

    # 1) create a WAMP application session factory
    component_config = types.ComponentConfig(realm=Component.config["realm"])
    session_factory = wamp.ApplicationSessionFactory(config=component_config)
    session_factory.session = Component

    # 2) create a WAMP-over-WebSocket transport client factory
    url = Component.config["url"]
    transport_factory = MyClientFactory(session_factory, url=url, debug=False)

    # 3) start the client from a Twisted endpoint
    isSecure, host, port, resource, path, params = parseWsUrl(url)
    transport_factory.host = host
    transport_factory.port = port
    websocket.connectWS(transport_factory)

    # 4) now enter the Twisted reactor loop
    reactor.run()
