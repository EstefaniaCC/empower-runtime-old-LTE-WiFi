#!/usr/bin/env python3
#
# Copyright (c) 2018 Roberto Riggio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the License for the
# specific language governing permissions and limitations
# under the License.

"""Wifi stats Poller App."""

from empower.core.app import EmpowerApp
from empower.core.resourcepool import BT_HT20
from empower.datatypes.etheraddress import EtherAddress
from empower.main import RUNTIME

import time
from datetime import datetime, date, time, timedelta
import os


class AggregationPoller(EmpowerApp):
    """WiFi Stats Poller Apps.

    Command Line Parameters:
        tenant_id: tenant id
        every: loop period in ms (optional, default 5000ms)

    Example:
        ./empower-runtime.py apps.pollers.wifistatspoller \
            --tenant_id=52313ecb-9d00-4b7d-b873-b55d3d9ada26
    """

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        # app parameters
        self.wifi_stats_data = {}
        self.bin_counter_data = {}
        self.lvap_stats_data = {}

        self._save_data = False
        self._scheme = None
        self._number = 0
        self._bandwidth = None
        self._pkt_size = None
        self._mcs_version = 0
        self._stations = None
        self._initial_time = None
        self.wtp_addr = None

    def wtp_up(self, wtp):
        """New WTP."""

        for block in wtp.supports:
            self.wifi_stats(block=block,
                            callback=self.wifi_callback)

        text_name = wtp.addr.to_str() + "_wifi_stats.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("scheme,", "number,", "bw,", "pkt_size,", "mcs,", "stations,", "timestamp,", "rx_utlization,", "tx_utlization", \
                      file=text_file)

        self.wtp_addr = wtp.addr.to_str()


        text_name = wtp.addr.to_str() + "_bin_counters.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("lvap,","scheme,", "number,", "bw,", "pkt_size,", "mcs,", "stations,", "timestamp,", "rx_bytes,", "tx_bytes,", "rx_pkts,", "tx_pkts,", "rx_bytes_per_second,", "tx_bytes_per_second,", "rx_pkts_per_second,", "tx_pkts_per_second", \
                    file=text_file)

        text_name = wtp.addr.to_str() + "_lvap_stats.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("lvap,","scheme,", "number,", "bw,", "pkt_size,", "mcs,", "stations,", "timestamp,", "rate,", "throughput,", "prob,", "cur_prob,", "attempts,", "success,", "cur_attempts,", "cur_success,", "hist_attempts,", "hist_success,", \
                      "attempts_bytes,", "success_bytes,", "cur_attempts_bytes,", "cur_success_bytes,", "hist_attempts_bytes,", "hist_success_bytes,", file=text_file)


    def lvap_join(self, lvap):
        """Called when a new LVAP joins the network."""

        self.bin_counter(lvap=lvap.addr,
                                every=self.every,
                                callback=self.counters_callback)

        self.lvap_stats(lvap=lvap.addr,
                        every=self.every,
                        callback=self.lvap_stats_callback)


        txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
        txp.ht_mcs = [self.mcs_version]


    def wifi_callback(self, stats):
        """ New stats available. """

        for i, j in enumerate(stats.wifi_stats["tx"]):
            if j["time"].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3] not in self.wifi_stats_data:
                self.wifi_stats_data[j["time"].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]] = {}
            self.wifi_stats_data[j["time"].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_utlization"] = stats.wifi_stats["rx"][i]["fields"]["value"]
            self.wifi_stats_data[j["time"].strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_utlization"] = j["fields"]["value"]

    def counters_callback(self, stats):
        """ New stats available. """

        lvap = RUNTIME.lvaps[stats.lvap]

        if stats.lvap.to_str() not in self.bin_counter_data:
            self.bin_counter_data[stats.lvap.to_str()] = {}

        cnt = self.bin_counter_data[stats.lvap.to_str()]

        cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]] = {}
        cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_bytes"] = stats.rx_bytes[0]
        cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_bytes"] = stats.tx_bytes[0]
        cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_pkts"] = stats.rx_packets[0]
        cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_pkts"] = stats.tx_packets[0]

        if not stats.tx_bytes_per_second or not stats.rx_bytes_per_second:
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_bytes_per_second"] = 0
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_bytes_per_second"] = 0
        else:
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_bytes_per_second"] = stats.rx_bytes_per_second[0]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_bytes_per_second"] = stats.tx_bytes_per_second[0]

        if not stats.tx_packets_per_second or not stats.rx_packets_per_second:
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_pkts_per_second"] = 0
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_pkts_per_second"] = 0
        else:
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rx_pkts_per_second"] = stats.rx_packets_per_second[0]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["tx_pkts_per_second"] = stats.tx_packets_per_second[0]

    def lvap_stats_callback(self, stats):
        """ New stats available. """

        lvap = stats.lvap

        if stats.lvap.to_str() not in self.lvap_stats_data:
            self.lvap_stats_data[stats.lvap.to_str()] = {}

        cnt = self.lvap_stats_data[stats.lvap.to_str()]
        cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]] = {}

        for mcs, value in stats.rates.items():
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["rate"] = mcs
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["throughput"] = value["throughput"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["prob"] = value["prob"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["cur_prob"] = value["cur_prob"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["attempts"] = value["attempts"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["success"] = value["success"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["cur_attempts"] = value["cur_attempts"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["cur_success"] = value["cur_success"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["hist_attempts"] = value["hist_attempts"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["hist_success"] = value["hist_success"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["attempts_bytes"] = value["attempts_bytes"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["success_bytes"] = value["success_bytes"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["cur_attempts_bytes"] = value["cur_attempts_bytes"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["cur_success_bytes"] = value["cur_success_bytes"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["hist_attempts_bytes"] = value["hist_attempts_bytes"]
            cnt[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]]["hist_success_bytes"] = value["hist_success_bytes"]

    def to_dict(self):
        """ Return a JSON-serializable."""

        out = super().to_dict()

        out['wifi_stats_data'] = self.wifi_stats_data
        out['bin_counter_data'] = self.bin_counter_data

        return out

    @property
    def save_data(self):
        """Get save_data mode."""

        return self._save_data

    @save_data.setter
    def save_data(self, save):
        """Set the save_data."""

        print("========== SAVE")

        self._save_data = save

        if save is False:
            return

        text_name = self.wtp_addr + "_wifi_stats.csv"

        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        now_parsed = datetime.strptime(now, '%Y-%m-%d %H:%M:%S.%f')
        initial_time_parsed = datetime.strptime(self.initial_time, '%Y-%m-%d %H:%M:%S.%f')

        for time, value in self.wifi_stats_data.items():
            time_parsed = datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')

            if time_parsed >= initial_time_parsed and time_parsed < now_parsed:
                with open(text_name, "a") as text_file:
                    print("%s, %d, %s, %d, %d, %d, %s, %.2f, %.2f" % \
                    (self.scheme, self.number, self.bandwidth, self.pkt_size, self.mcs_version, self.stations, time, value["rx_utlization"], value["tx_utlization"]), file=text_file)

        self.wifi_stats_data = {}

        text_name = self.wtp_addr + "_bin_counters.csv"

        for lvap, value in self.bin_counter_data.items():
            for time, stats in value.items():
                time_parsed = datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')

                if time_parsed >= initial_time_parsed and time_parsed < now_parsed:
                    print("%s, %s, %d, %s, %d, %d, %d, %s, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f" % \
                        (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.mcs_version, self.stations, time,
                            stats["rx_bytes"], stats["tx_bytes"], stats["rx_pkts"], stats["tx_pkts"], stats["rx_bytes_per_second"], stats["tx_bytes_per_second"], stats["rx_pkts_per_second"], stats["tx_pkts_per_second"]))
                    with open(text_name, "a") as text_file:
                        print("%s, %s, %d, %s, %d, %d, %d, %s, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f" % \
                        (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.mcs_version, self.stations, time,
                            stats["rx_bytes"], stats["tx_bytes"], stats["rx_pkts"], stats["tx_pkts"], stats["rx_bytes_per_second"], stats["tx_bytes_per_second"], stats["rx_pkts_per_second"], stats["tx_pkts_per_second"]), file=text_file)

        self.bin_counter_data = {}

        text_name = self.wtp_addr + "_lvap_stats.csv"

        for lvap, value in self.lvap_stats_data.items():
            for time, stats in value.items():
                time_parsed = datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')

                if time_parsed >= initial_time_parsed and time_parsed < now_parsed:
                    with open(text_name, "a") as text_file:
                        print("%s, %s, %d, %s, %d, %d, %d, %s, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f" % \
                        (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.mcs_version, self.stations, time, 
                            stats["rate"], stats["throughput"], stats["prob"], stats["cur_prob"], stats["attempts"], stats["success"], stats["cur_attempts"], stats["cur_success"], stats["hist_attempts"], stats["hist_success"], stats["attempts_bytes"], stats["success_bytes"], stats["cur_attempts_bytes"], stats["cur_success_bytes"], stats["hist_attempts_bytes"], stats["hist_success_bytes"]), file=text_file)

        self.lvap_stats_data = {}
            
    @property
    def scheme(self):
        """Get scheme mode."""

        return self._scheme

    @scheme.setter
    def scheme(self, scheme):
        """Set the scheme."""

        self._scheme = scheme

        for lvap in list(RUNTIME.lvaps.values()):
            print(lvap)
            txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
            print(txp)
            txp.max_amsdu_len = self.scheme

    @property
    def number(self):
        """Get number mode."""

        return self._number

    @number.setter
    def number(self, nb):
        """Set the number_test."""

        self._number = int(nb)

    @property
    def bandwidth(self):
        """Get bandwidth mode."""

        return self._bandwidth

    @bandwidth.setter
    def bandwidth(self, bandwidth):
        """Set the bandwidth."""

        self._bandwidth = bandwidth

    @property
    def pkt_size(self):
        """Get pkt_size mode."""

        return self._pkt_size

    @pkt_size.setter
    def pkt_size(self, pkt_size):
        """Set the pkt_size."""

        self._pkt_size = int(pkt_size)

    @property
    def mcs_version(self):
        """Get mcs_version mode."""

        return self._mcs_version

    @mcs_version.setter
    def mcs_version(self, mcs_version):
        """Set the mcs_version."""
            
        self._mcs_version = int(mcs_version)

        for lvap in list(RUNTIME.lvaps.values()):
            txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
            txp.ht_mcs = [self.mcs_version]

    @property
    def stations(self):
        """Get stations mode."""

        return self._stations

    @stations.setter
    def stations(self, stations):
        """Set the stations."""

        self._stations = int(stations)

    @property
    def initial_time(self):
        """Get initial_time mode."""

        return self._initial_time

    @initial_time.setter
    def initial_time(self, initial_time):
        """Set the initial_time."""

        if initial_time is False:
            return

        self._initial_time = datetime.utcnow()
        self._initial_time = self._initial_time + timedelta(seconds=10) 
        self._initial_time = self._initial_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]


def launch(tenant_id):
    """ Initialize the module. """

    return AggregationPoller(tenant_id=tenant_id)