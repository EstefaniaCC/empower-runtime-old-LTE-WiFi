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

from empower.apps.pollers.platform_m5p_model import PlatformM5PModel
from empower.apps.pollers.ns3_m5p_model import SimulatorM5PModel
from empower.apps.pollers.platform_rf_model import PlatformRFModel
from empower.apps.pollers.ns3_rf_model import SimulatorRFModel

import time
from datetime import datetime, date, time, timedelta
from statistics import mean
import os
from copy import copy

PHY_RATE = {0: 6500000,
            1: 13500000,
            2: 19500000,
            3: 26000000,
            4: 39000000,
            5: 52000000,
            6: 58500000,
            7: 65000000}


class AggregationPollerValidation(EmpowerApp):
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
        self.lvap_stats_data = {}
        self.dump_data = {}

        self._save_data = False
        self._scheme = "NO_AGGREGATION"
        self._number = 0
        self._bandwidth = None
        self._pkt_size = None
        self._mcs_version = 0
        self._stations = None
        self._initial_time = None
        self.wtp_addr = None
        self.last_length = {}
        self.last_mcs = {}

        self.hist_length = {}
        self.hist_mcs = {}

        self.platform_model = {}

        self.individual_results = {}
        self.individual_results_cum = {}
        self.bin_counter_data = {}

        self.previous_statistics = {}
        self.second_statistics = {}
        self.hist_counter = {}

    def wtp_up(self, wtp):
        """New WTP."""

        for block in wtp.supports:
            self.wifi_stats(block=block,
                            callback=self.wifi_callback)

        text_name = "validation_results.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("lvap,","scheme,", "number,", "bw,", "pkt_size,", "stations,", "timestamp,", "mcs,", "minstrel_throughput,", "success_ratio,", "success_ratio_per,", "last_attempts_bytes,", "last_success_bytes,",\
                      "success_tx_channel_utilization,", "hist_attempts,", "hist_success,", "hist_attempts_bytes,", "hist_success_bytes,", "hist_rtx,", "hist_rtx_bytes,", "global_channel_utilization,", "success_tx_global_channel_utilization,", file=text_file)

        text_name = "validation_individual_results.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("lvap,","scheme,", "number,", "bw,", "pkt_size,", "stations,", "hist_success_ratio_per,", "hist_attempts,", "hist_attempts_bytes,",\
                "hist_success,", "hist_success_bytes,", "hist_rtx,", "hist_rtx_bytes,", "global_channel_utilization,", file=text_file)                

        text_name = "length_distribution.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("lvap,","scheme,", "number,", "bw,", "pkt_size,", "stations,", "aggregation_size,", "times_selected", file=text_file)

        text_name = "mcs_distribution.csv"

        if not os.path.isfile(text_name):
            with open(text_name, "w") as text_file:
                print("lvap,","scheme,", "number,", "bw,", "pkt_size,", "stations,", "mcs,", "times_selected", file=text_file)

    def lvap_join(self, lvap):
        """Called when a new LVAP joins the network."""

        self.lvap_stats(lvap=lvap.addr,
                        every=self.every,
                        callback=self.lvap_stats_callback)

        self.bin_counter(lvap=lvap.addr,
                                every=self.every,
                                callback=self.counters_callback)

        if lvap.addr.to_str() not in self.hist_mcs:
            self.hist_mcs[lvap.addr.to_str()] = {}

        for key in PHY_RATE.keys():
            self.hist_mcs[lvap.addr.to_str()][key] = 0

        if lvap.addr.to_str() not in self.hist_length:
            self.hist_length[lvap.addr.to_str()] = {}

        self.hist_length[lvap.addr.to_str()][550] = 0
        self.hist_length[lvap.addr.to_str()][1024] = 0
        self.hist_length[lvap.addr.to_str()][2048] = 0
        self.hist_length[lvap.addr.to_str()][3839] = 0

        # Individual and global results are stored for the plots
        if lvap.addr.to_str() not in self.individual_results:
            self.individual_results[lvap.addr.to_str()] = {}
            self.individual_results[lvap.addr.to_str()]["hist_success_ratio_per"] = 0
            self.individual_results[lvap.addr.to_str()]["hist_attempts"] = 0
            self.individual_results[lvap.addr.to_str()]["hist_attempts_bytes"] = 0
            self.individual_results[lvap.addr.to_str()]["hist_success"] = 0
            self.individual_results[lvap.addr.to_str()]["hist_success_bytes"] = 0
            self.individual_results[lvap.addr.to_str()]["hist_rtx"] = 0
            self.individual_results[lvap.addr.to_str()]["hist_rtx_bytes"] = 0
            self.individual_results[lvap.addr.to_str()]["global_channel_utilization"] = 0

        if lvap.addr.to_str() not in self.individual_results_cum:
            self.individual_results_cum[lvap.addr.to_str()] = {}
            self.individual_results_cum[lvap.addr.to_str()]["hist_success_ratio_per"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["hist_attempts"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["hist_attempts_bytes"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["hist_success"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["hist_success_bytes"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["hist_rtx"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["hist_rtx_bytes"] = 0
            self.individual_results_cum[lvap.addr.to_str()]["global_channel_utilization"] = 0

        if self.scheme == "A-MSDU":
            txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
            print(txp)
            txp.max_amsdu_len = 3839

        # if lvap.addr.to_str() == "00:24:D7:7B:B0:7C" or lvap.addr.to_str() == "80:00:0B:6E:58:89":
        #     txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
        #     txp.ht_mcs = [0]
        # else:
        #     txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
        #     txp.ht_mcs = [4]

    def counters_callback(self, stats):
        """ New stats available. """

        lvap = RUNTIME.lvaps[stats.lvap]

        if stats.lvap.to_str() not in self.bin_counter_data:
            self.bin_counter_data[stats.lvap.to_str()] = {}

        cnt = self.bin_counter_data[stats.lvap.to_str()]

        if not stats.tx_bytes_per_second or not stats.rx_bytes_per_second:
            cnt["tx_bytes_per_second"] = 0
        else:
            cnt["tx_bytes_per_second"] = stats.tx_bytes_per_second[0]


    def wifi_callback(self, stats):
        """ New stats available. """

        current_time = datetime.min
        for i, j in enumerate(stats.wifi_stats["tx"]):
            if "global_channel_utilization" not in self.wifi_stats_data:
                self.wifi_stats_data["global_channel_utilization"] = 0
            if j["time"] > current_time:
                self.wifi_stats_data["global_channel_utilization"] = stats.wifi_stats["rx"][i]["fields"]["value"] + j["fields"]["value"]
                self.wifi_stats_data["global_channel_utilization_ed"] = stats.wifi_stats["rx"][i]["fields"]["value"] + j["fields"]["value"] + stats.wifi_stats["ed"][i]["fields"]["value"]
                current_time = j["time"]

    def lvap_stats_callback(self, stats):
        """ New stats available. """

        highest_th = 0
        best_mcs = 0
        for mcs, value in stats.rates.items():
            if value["throughput"] > highest_th:
                best_mcs = int(float(mcs))
                highest_th = value["throughput"]

        lvap = RUNTIME.lvaps[stats.lvap]

        if stats.lvap.to_str() not in self.lvap_stats_data:
            self.lvap_stats_data[stats.lvap.to_str()] = {}
        cnt = self.lvap_stats_data[stats.lvap.to_str()]

        # I should only take the mcs that is currently used by minstrel :)
        cnt["mcs"] = best_mcs%8
        cnt["minstrel_throughput"] = stats.rates[best_mcs]["throughput"]
        cnt["prob"] = stats.rates[best_mcs]["prob"]

        if stats.rates[best_mcs]["cur_attempts"] != 0:
            cnt["success_ratio"] = stats.rates[best_mcs]["cur_success"] / stats.rates[best_mcs]["cur_attempts"]
            cnt["success_ratio_per"] = (stats.rates[best_mcs]["cur_success"] / stats.rates[best_mcs]["cur_attempts"]) * 100
        else:
            cnt["success_ratio"] = 0
            cnt["success_ratio_per"] = 0

        cnt["last_attempts_bytes"] = 0
        cnt["last_success_bytes"] = 0
        cnt["success_tx_channel_utilization"] = 0

        if "hist_success_bytes" in cnt:
            cnt["previous_hist_success_bytes"] = cnt["hist_success_bytes"]
        else:
            cnt["previous_hist_success_bytes"] = 0

        if "hist_attempts_bytes" in cnt:
            cnt["previous_hist_attempts_bytes"] = cnt["hist_attempts_bytes"]
        else:
            cnt["previous_hist_attempts_bytes"] = 0

        cnt["hist_success_bytes"] = 0
        cnt["hist_attempts_bytes"] = 0
        cnt["hist_attempts"] = 0
        cnt["hist_success"] = 0
        cnt["last_hist_success"] = 0
        cnt["hist_rtx"] = 0
        cnt["hist_rtx_bytes"] = 0
        cnt["last_rtx"] = 0
        cnt["last_rtx_bytes"] = 0

        for mcs, value in stats.rates.items():

            cnt["last_attempts_bytes"] += stats.rates[mcs]["cur_attempts_bytes"]
            cnt["last_success_bytes"] += stats.rates[mcs]["cur_success_bytes"]
            cnt["success_tx_channel_utilization"] += (stats.rates[mcs]["cur_success_bytes"] / (self.every / 1000)) / PHY_RATE[mcs%8]
            cnt["hist_attempts"] += stats.rates[mcs]["hist_attempts"]
            cnt["hist_success"] += stats.rates[mcs]["hist_success"]
            cnt["hist_attempts_bytes"] += stats.rates[mcs]["hist_attempts_bytes"]
            cnt["hist_success_bytes"] += stats.rates[mcs]["hist_success_bytes"]
            cnt["hist_rtx"] += stats.rates[mcs]["hist_attempts"] - stats.rates[mcs]["hist_success"]
            cnt["hist_rtx_bytes"] += stats.rates[mcs]["hist_attempts_bytes"] - stats.rates[mcs]["hist_success_bytes"]
            cnt["last_rtx"] += stats.rates[mcs]["cur_attempts"] - stats.rates[mcs]["cur_success"]
            cnt["last_rtx_bytes"] += stats.rates[mcs]["cur_attempts_bytes"] - stats.rates[mcs]["cur_success_bytes"]

        if "previous_hist_success_bytes" not in cnt:
            cnt["previous_hist_success_bytes"] = 0
        if cnt["previous_hist_success_bytes"] == 0:
            cnt["previous_hist_success_bytes"] = cnt["hist_success_bytes"]

        if "previous_hist_attempts_bytes" not in cnt:
            cnt["previous_hist_attempts_bytes"] = 0
        if cnt["previous_hist_attempts_bytes"] == 0:
            cnt["previous_hist_attempts_bytes"] = cnt["hist_attempts_bytes"]

        if "global_channel_utilization" in self.wifi_stats_data:
            cnt["global_channel_utilization"] = self.wifi_stats_data["global_channel_utilization"]
        else:
            cnt["global_channel_utilization"] = 0

        #Add values for tx channel utilization in lvaps. It is assumed that all the lvaps are receiving traffic
        success_tx_global_channel_utilization = 0
        for key, value in self.lvap_stats_data.items():
            if "success_tx_channel_utilization" not in value:
                continue
            success_tx_global_channel_utilization += value["success_tx_channel_utilization"]

        print("total", success_tx_global_channel_utilization)
        for key, value in self.lvap_stats_data.items():
            value["success_tx_global_channel_utilization"] = success_tx_global_channel_utilization

        # To dump file for further analysis
        if stats.lvap.to_str() not in self.dump_data:
            self.dump_data[stats.lvap.to_str()] = {}

        data = self.dump_data[stats.lvap.to_str()]
        data[stats.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]] = copy(cnt)

        if stats.lvap.to_str() != "18:5E:0F:E3:B8:45" and self.scheme != "A-MSDU" and self.scheme != "NO_AGGREGATION":
            if self.bin_counter_data[stats.lvap.to_str()]["tx_bytes_per_second"] < 100:
                return

            # ML model execution. The reason to be done here is because we are sure that the statistic information is updated.
            mcs_length_combination = {}
            if stats.lvap.to_str() in self.platform_model:
                self.platform_model[stats.lvap.to_str()].mcs = best_mcs%8
                self.platform_model[stats.lvap.to_str()].last_mcs = self.last_mcs[stats.lvap.to_str()]
                self.platform_model[stats.lvap.to_str()].last_length = self.last_length[stats.lvap.to_str()]
                self.platform_model[stats.lvap.to_str()].statistics = cnt

                mcs_length_combination = self.platform_model[stats.lvap.to_str()].estimate_optimal_length()
            else:
                print("There is no model??")
                if self.scheme == "M5P_Platform":
                    self.platform_model[stats.lvap.to_str()] = PlatformM5PModel(None, None, best_mcs%8, cnt)
                elif self.scheme == "M5P_NS3":
                    self.platform_model[stats.lvap.to_str()] = SimulatorM5PModel(None, None, best_mcs%8, cnt)
                elif self.scheme == "RF_Platform":
                    self.platform_model[stats.lvap.to_str()] = PlatformRFModel(None, None, best_mcs%8, cnt)
                elif self.scheme == "RF_NS3":
                    self.platform_model[stats.lvap.to_str()] = SimulatorRFModel(None, None, best_mcs%8, cnt)

                # print("*******prev stats", self.platform_model[stats.lvap.to_str()].previous_statistics)
                mcs_length_combination = self.platform_model[stats.lvap.to_str()].estimate_optimal_length()

            # TODO: Check if lvap is here
            if stats.lvap.to_str() not in self.last_mcs:
                self.last_mcs[stats.lvap.to_str()] = 0
                self.last_length[stats.lvap.to_str()] = 0

            print("++++++ Attention ++++++")
            print("Change in lvap ", stats.lvap.to_str())
            print("New MCS", best_mcs%8)
            print("New value ", mcs_length_combination)

            if self.last_length[stats.lvap.to_str()] != mcs_length_combination["length"]:
                self.update_counters(stats.lvap.to_str())
                txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
                txp.max_amsdu_len = mcs_length_combination["length"]
                print(txp)
            
            self.last_length[stats.lvap.to_str()] = mcs_length_combination["length"]
            self.last_mcs[stats.lvap.to_str()] = best_mcs%8

            # MCS and lengths are stored for the plots
            if mcs_length_combination["length"] not in self.hist_length[stats.lvap.to_str()]:
                self.hist_length[stats.lvap.to_str()][mcs_length_combination["length"]] = 0
            self.hist_length[stats.lvap.to_str()][mcs_length_combination["length"]] += 1

        self.hist_mcs[stats.lvap.to_str()][(best_mcs%8)] += 1

        temp_counter = {}
        temp_counter["hist_success_ratio_per"] = 0
        temp_counter["hist_attempts"] = 0
        temp_counter["hist_attempts_bytes"] = 0
        temp_counter["hist_success"] = 0
        temp_counter["hist_success_bytes"] = 0
        temp_counter["hist_rtx"] = 0
        temp_counter["hist_rtx_bytes"] = 0
        temp_counter["global_channel_utilization"] = 0

        for mcs, value in stats.rates.items():
            if value["hist_attempts"] != 0:
                if temp_counter["hist_success_ratio_per"] == 0:
                    if value["hist_attempts"] != 0:
                        temp_counter["hist_success_ratio_per"] = (value["hist_success"] / value["hist_attempts"]) * 100
                else:
                    if value["hist_attempts"] != 0:
                        temp_counter["hist_success_ratio_per"] = mean([temp_counter["hist_success_ratio_per"], (value["hist_success"] / value["hist_attempts"]) * 100])

            temp_counter["hist_attempts"] += value["hist_attempts"]
            temp_counter["hist_attempts_bytes"] += value["hist_attempts_bytes"]
            temp_counter["hist_success"] += value["hist_success"]
            temp_counter["hist_success_bytes"] += value["hist_success_bytes"]
            temp_counter["hist_rtx"] += value["hist_attempts"] - value["hist_success"]
            temp_counter["hist_rtx_bytes"] += value["hist_attempts_bytes"] - value["hist_success_bytes"]

        if "global_channel_utilization" in self.wifi_stats_data and (self.wifi_stats_data["global_channel_utilization"] > 20):
            temp_counter["global_channel_utilization"] = self.wifi_stats_data["global_channel_utilization"]
            
        # This means that minstrel has been reset
        if temp_counter["hist_success"] < self.individual_results[stats.lvap.to_str()]["hist_success"]:
            self.update_counters(stats.lvap.to_str())            

        if temp_counter["hist_success"] > self.individual_results[stats.lvap.to_str()]["hist_success"]:
            if self.individual_results[stats.lvap.to_str()]["global_channel_utilization"] == 0:
                self.individual_results[stats.lvap.to_str()]["global_channel_utilization"] = temp_counter["global_channel_utilization"]
            elif temp_counter["global_channel_utilization"] != 0:
                self.individual_results[stats.lvap.to_str()]["global_channel_utilization"] = mean([self.individual_results[stats.lvap.to_str()]["global_channel_utilization"], temp_counter["global_channel_utilization"]])

            if self.individual_results[stats.lvap.to_str()]["hist_success_ratio_per"] == 0:
                self.individual_results[stats.lvap.to_str()]["hist_success_ratio_per"] = self.individual_results[stats.lvap.to_str()]["hist_success_ratio_per"]
            else:
                self.individual_results[stats.lvap.to_str()]["hist_success_ratio_per"] = mean([self.individual_results[stats.lvap.to_str()]["hist_success_ratio_per"], temp_counter["hist_success_ratio_per"]])
        else:
            self.individual_results[stats.lvap.to_str()]["hist_success_ratio_per"] = temp_counter["hist_success_ratio_per"]
            self.individual_results[stats.lvap.to_str()]["global_channel_utilization"] = temp_counter["global_channel_utilization"]
        
        # Update the current stats
        self.individual_results[stats.lvap.to_str()]["hist_attempts"] = temp_counter["hist_attempts"]
        self.individual_results[stats.lvap.to_str()]["hist_attempts_bytes"] = temp_counter["hist_attempts_bytes"]
        self.individual_results[stats.lvap.to_str()]["hist_success"] = temp_counter["hist_success"]
        self.individual_results[stats.lvap.to_str()]["hist_success_bytes"] = temp_counter["hist_success_bytes"]
        self.individual_results[stats.lvap.to_str()]["hist_rtx"] = temp_counter["hist_rtx"]
        self.individual_results[stats.lvap.to_str()]["hist_rtx_bytes"] = temp_counter["hist_rtx_bytes"]

    def update_counters(self, lvap_addr_str):
        self.individual_results_cum[lvap_addr_str]["hist_attempts"] += self.individual_results[lvap_addr_str]["hist_attempts"]
        self.individual_results_cum[lvap_addr_str]["hist_attempts_bytes"] += self.individual_results[lvap_addr_str]["hist_attempts_bytes"]
        self.individual_results_cum[lvap_addr_str]["hist_success"] += self.individual_results[lvap_addr_str]["hist_success"]
        self.individual_results_cum[lvap_addr_str]["hist_success_bytes"] += self.individual_results[lvap_addr_str]["hist_success_bytes"]
        self.individual_results_cum[lvap_addr_str]["hist_rtx"] += self.individual_results[lvap_addr_str]["hist_rtx"]
        self.individual_results_cum[lvap_addr_str]["hist_rtx_bytes"] += self.individual_results[lvap_addr_str]["hist_rtx_bytes"]
        
        if self.individual_results_cum[lvap_addr_str]["global_channel_utilization"] == 0:
            self.individual_results_cum[lvap_addr_str]["global_channel_utilization"] = self.individual_results[lvap_addr_str]["global_channel_utilization"]
        elif self.individual_results[lvap_addr_str]["global_channel_utilization"] != 0:
            self.individual_results_cum[lvap_addr_str]["global_channel_utilization"] = mean([self.individual_results_cum[lvap_addr_str]["global_channel_utilization"], self.individual_results[lvap_addr_str]["global_channel_utilization"]])

        if self.individual_results_cum[lvap_addr_str]["hist_attempts"] != 0:    
            self.individual_results_cum[lvap_addr_str]["hist_success_ratio_per"] = (self.individual_results_cum[lvap_addr_str]["hist_success"] / self.individual_results_cum[lvap_addr_str]["hist_attempts"]) * 100

        self.individual_results[lvap_addr_str]["hist_success_ratio_per"] = 0
        self.individual_results[lvap_addr_str]["hist_attempts"] = 0
        self.individual_results[lvap_addr_str]["hist_attempts_bytes"] = 0
        self.individual_results[lvap_addr_str]["hist_success"] = 0
        self.individual_results[lvap_addr_str]["hist_success_bytes"] = 0
        self.individual_results[lvap_addr_str]["hist_rtx"] = 0
        self.individual_results[lvap_addr_str]["hist_rtx_bytes"] = 0
        self.individual_results[lvap_addr_str]["global_channel_utilization"] = 0

    def to_dict(self):
        """ Return a JSON-serializable."""

        out = super().to_dict()

        out['wifi_stats_data'] = self.wifi_stats_data
        out['lvap_stats_data'] = self.lvap_stats_data
        out['hist_length'] = self.hist_length
        out['hist_mcs'] = self.hist_mcs
        out['individual_results'] = self.individual_results
        out['individual_results_cum'] = self.individual_results_cum

        return out

    @property
    def save_data(self):
        """Get save_data mode."""

        return self._save_data

    @save_data.setter
    def save_data(self, save):
        """Set the save_data."""

        self._save_data = save

        text_name = "validation_results.csv"
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        now_parsed = datetime.strptime(now, '%Y-%m-%d %H:%M:%S.%f')
        initial_time_parsed = datetime.strptime(self.initial_time, '%Y-%m-%d %H:%M:%S.%f')

        for lvap, value in self.dump_data.items():
            for time, stats in value.items():
                time_parsed = datetime.strptime(time, '%Y-%m-%d %H:%M:%S.%f')

                if time_parsed >= initial_time_parsed and time_parsed < now_parsed:
                    with open(text_name, "a") as text_file:
                        print("%s, %s, %d, %s, %d, %d, %s, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.7f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.2f, %.7f" % \
                        (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.stations, time, 
                            stats["mcs"], stats["minstrel_throughput"], stats["success_ratio"], stats["success_ratio_per"], stats["last_attempts_bytes"], stats["last_success_bytes"],
                            stats["success_tx_channel_utilization"], stats["hist_attempts"], stats["hist_success"], stats["hist_attempts_bytes"], stats["hist_success_bytes"],
                            stats["hist_rtx"], stats["hist_rtx_bytes"], stats["global_channel_utilization"], stats["success_tx_global_channel_utilization"]), file=text_file)

        text_name = "length_distribution.csv"

        for lvap, value in self.hist_length.items():
            for size, times in value.items():
                with open(text_name, "a") as text_file:
                    print("%s, %s, %d, %s, %d, %d, %d, %d" % \
                    (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.stations, size, times), file=text_file)

        text_name = "mcs_distribution.csv"

        for lvap, value in self.hist_mcs.items():
            for mcsi, times in value.items():
                with open(text_name, "a") as text_file:
                    print("%s, %s, %d, %s, %d, %d, %d, %d" % \
                    (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.stations, mcsi, times), file=text_file)

        for lvap in list(RUNTIME.lvaps.values()):
            if self.scheme == "A-MSDU" or self.scheme == "NO_AGGREGATION":
                self.update_counters(lvap.addr.to_str())

        text_name = "validation_individual_results.csv"

        for lvap, value in self.individual_results_cum.items():
            # for mcsi, times in value.items():
            with open(text_name, "a") as text_file:
                print("%s, %s, %d, %s, %d, %d, %f, %f, %f, %f, %f, %f, %f, %f" % \
                (lvap, self.scheme, self.number, self.bandwidth, self.pkt_size, self.stations, value["hist_success_ratio_per"],\
                value["hist_attempts"], value["hist_attempts_bytes"], value["hist_success"], value["hist_success_bytes"], value["hist_rtx"],\
                value["hist_rtx_bytes"], value["global_channel_utilization"]),file=text_file)
        
        # self.lvap_stats_data = {}
            
    @property
    def scheme(self):
        """Get scheme mode."""

        return self._scheme

    @scheme.setter
    def scheme(self, scheme):
        """Set the scheme."""

        self._scheme = scheme

        # Individual and global results are stored for the plots
        for lvap in list(RUNTIME.lvaps.values()):
            if lvap.addr.to_str() in self.individual_results:
                self.individual_results[lvap.addr.to_str()] = {}
                self.individual_results[lvap.addr.to_str()]["hist_success_ratio_per"] = 0
                self.individual_results[lvap.addr.to_str()]["hist_attempts"] = 0
                self.individual_results[lvap.addr.to_str()]["hist_attempts_bytes"] = 0
                self.individual_results[lvap.addr.to_str()]["hist_success"] = 0
                self.individual_results[lvap.addr.to_str()]["hist_success_bytes"] = 0
                self.individual_results[lvap.addr.to_str()]["hist_rtx"] = 0
                self.individual_results[lvap.addr.to_str()]["hist_rtx_bytes"] = 0
                self.individual_results[lvap.addr.to_str()]["global_channel_utilization"] = 0

            if lvap.addr.to_str() in self.individual_results_cum:
                self.individual_results_cum[lvap.addr.to_str()] = {}
                self.individual_results_cum[lvap.addr.to_str()]["hist_success_ratio_per"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["hist_attempts"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["hist_attempts_bytes"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["hist_success"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["hist_success_bytes"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["hist_rtx"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["hist_rtx_bytes"] = 0
                self.individual_results_cum[lvap.addr.to_str()]["global_channel_utilization"] = 0

            if lvap.addr.to_str() in self.hist_mcs:
                for key in PHY_RATE.keys():
                    self.hist_mcs[lvap.addr.to_str()][key] = 0

            if lvap.addr.to_str() in self.hist_length:
                self.hist_length[lvap.addr.to_str()][550] = 0
                self.hist_length[lvap.addr.to_str()][1024] = 0
                self.hist_length[lvap.addr.to_str()][2048] = 0
                self.hist_length[lvap.addr.to_str()][3839] = 0

        for lvap in list(RUNTIME.lvaps.values()):
            print(lvap)
            txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
            txp.max_amsdu_len = txp.max_amsdu_len

        if scheme == "A-MSDU":
            for lvap in list(RUNTIME.lvaps.values()):
                print(lvap)
                txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
                print(txp)
                txp.max_amsdu_len = 3839

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

        # for lvap in list(RUNTIME.lvaps.values()):
        #     txp = lvap.blocks[0].tx_policies[EtherAddress(lvap.addr)]
        #     txp.ht_mcs = [self.mcs_version]

        # print("--- mcs_version ", mcs_version)

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


def launch(tenant_id, every=1000):
    """ Initialize the module. """

    return AggregationPollerValidation(tenant_id=tenant_id, every=every)