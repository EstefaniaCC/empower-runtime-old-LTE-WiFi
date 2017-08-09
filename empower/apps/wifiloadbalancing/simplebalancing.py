#!/usr/bin/env python3
#
# Copyright (c) 2017 Estefania Coronado
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

import random
import sys
import time

from empower.core.app import EmpowerApp
from empower.core.app import DEFAULT_PERIOD
from empower.datatypes.etheraddress import EtherAddress
from empower.core.resourcepool import ResourceBlock
from empower.main import RUNTIME
from empower.maps.ucqm import ucqm
from empower.bin_counter.bin_counter import BinCounter
from empower.bin_counter.bin_counter import BinCounterWorker
from empower.events.wtpup import wtpup
from empower.events.wtpdown import wtpdown
from empower.events.lvapjoin import lvapjoin
from empower.events.lvapleave import lvapleave
from empower.lvap_stats.lvap_stats import lvap_stats
from empower.lvap_stats.lvap_stats import LVAPStatsWorker
from empower.core.resourcepool import BANDS


RSSI_LIMIT = 8

class WifiLoadBalancing(EmpowerApp):

    def __init__(self, **kwargs):

        EmpowerApp.__init__(self, **kwargs)

        self.test = "test1"

        self.wifi_data = {}
        self.bitrate_data_active = {}

        self.nb_app_active = {}

        self.stations_channels_matrix = {}
        self.stations_aps_matrix = {}

        self.initial_setup = True
        self.warm_up_phases = 20

        self.conflict_aps = {}
        self.aps_channels_matrix = {}
        self.aps_clients_rel = {}
        self.aps_occupancy = {}

        self.coloring_channels  = {"00:0D:B9:3E:05:44": 149, "00:0D:B9:3E:06:9C": 153, "00:0D:B9:3E:D9:DC": 157}

        self.handover_lock = {}

        self.old_aps_occupancy = {}
        self.handover_occupancies = {}
        self.unsuccessful_handovers = {}

        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)

    def to_dict(self):
        """Return json-serializable representation of the object."""

        out = super().to_dict()
        out['wifi_data'] = self.wifi_data
        out['aps_clients_rel'] = self.aps_clients_rel
        out['conflict_aps'] = self.conflict_aps
        out['stations_aps_matrix'] = self.stations_aps_matrix
        out['bitrate_data_active'] = self.bitrate_data_active
        out['aps_occupancy'] = self.aps_occupancy
        out['old_aps_occupancy'] = self.old_aps_occupancy
        out['handover_lock'] = self.handover_lock
        return out


    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for block in wtp.supports:
        
            if block.addr.to_str() in self.coloring_channels:
                block.channel = self.coloring_channels[block.addr.to_str()]

            self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

            self.conflict_aps[block.addr.to_str()] = []
            self.aps_clients_rel[block.addr.to_str()] = []
            self.aps_channels_matrix[block.addr.to_str()] = block.channel
            self.bitrate_data_active[block.addr.to_str()] = {}
            self.nb_app_active[block.addr.to_str()] = 0
            self.aps_occupancy[block.addr.to_str()] = 0


    def lvap_join_callback(self, lvap):
        """Called when an joins the network."""

        self.bin_counter(lvap=lvap.addr,
                 every=500,
                 callback=self.counters_callback)

        self.lvap_stats(lvap=lvap.addr, 
                    every=500, 
                    callback=self.lvap_stats_callback)

        if lvap.addr.to_str() not in self.aps_clients_rel[lvap.default_block.addr.to_str()]:
            self.aps_clients_rel[lvap.default_block.addr.to_str()].append(lvap.addr.to_str())

        self.stations_aps_matrix[lvap.addr.to_str()] = []
        if lvap.default_block.addr.to_str() not in self.stations_aps_matrix[lvap.addr.to_str()]:
            self.stations_aps_matrix[lvap.addr.to_str()].append(lvap.default_block.addr.to_str())

    def lvap_leave_callback(self, lvap):
        """Called when an LVAP disassociates from a tennant."""

        self.delete_bincounter_worker(lvap)
        self.delete_lvap_stats_worker(lvap)

        if lvap.addr.to_str() in self.aps_clients_rel[lvap.default_block.addr.to_str()]:
            self.aps_clients_rel[lvap.default_block.addr.to_str()].remove(lvap.addr.to_str())
        if lvap.addr.to_str() in self.bitrate_data_active[lvap.default_block.addr.to_str()]:
            del self.bitrate_data_active[lvap.default_block.addr.to_str()][lvap.addr.to_str()]
            self.nb_app_active[lvap.default_block.addr.to_str()] = len(self.bitrate_data_active[lvap.default_block.addr.to_str()])


    def lvap_stats_callback(self, counter):
        """ New stats available. """

        rates = (counter.to_dict())["rates"]
        if not rates or counter.lvap not in RUNTIME.lvaps:
            return

        lvap = RUNTIME.lvaps[counter.lvap]
        highest_rate = int(float(max(rates, key=lambda v: int(float(rates[v]['prob'])))))
        key = lvap.default_block.addr.to_str() + lvap.addr.to_str()

        if lvap.default_block.addr.to_str() not in self.old_aps_occupancy:
            self.old_aps_occupancy[lvap.default_block.addr.to_str()] = self.update_occupancy_ratio(lvap.default_block)

        if key in self.wifi_data:
            if self.wifi_data[key]['rate'] == 0:
                self.wifi_data[key]['rate'] = highest_rate
            elif highest_rate != self.wifi_data[key]['rate']:
                self.wifi_data[key]['rate_attempts'] += 1
                if self.wifi_data[key]['rate_attempts'] < 5:
                    return
        else:
            self.wifi_data[key] = \
            {
                'rssi': None,
                'wtp': lvap.default_block.addr.to_str(),
                'sta': lvap.addr.to_str(),
                'channel': lvap.default_block.channel,
                'active': 1,
                'tx_bytes_per_second': 0,
                'rx_bytes_per_second': 0,
                'reesched_attempts': 0,
                'revert_attempts': 0,
                'rate': highest_rate,
                'rate_attempts': 0
            }

        self.wifi_data[key]['rate'] = highest_rate
        self.wifi_data[key]['rate_attempts'] = 0
        
        new_occupancy = self.update_occupancy_ratio(lvap.default_block)
        average_occupancy = self.average_occupancy_surrounding_aps(lvap)

        # print("counters")
        # print("------self.bitrate_data_active[block]", self.bitrate_data_active[lvap.default_block.addr.to_str()])
        # print("------Revert attempts: ", self.wifi_data[key]['revert_attempts'])
        # print("------Reesched attempts: ", self.wifi_data[key]['reesched_attempts'])
        # print("------New occupancy: ", new_occupancy)
        # print("------self.old_aps_occupancy[block.addr.to_str()]: ", self.old_aps_occupancy[lvap.default_block.addr.to_str()])
        # print("------average_occupancy: ", average_occupancy)

        #if new_occupancy != average_occupancy:
        if new_occupancy < (average_occupancy * 0.975) or new_occupancy > (average_occupancy * 1.025) or \
        new_occupancy < (self.old_aps_occupancy[lvap.default_block.addr.to_str()] * 0.975) or \
        new_occupancy > (self.old_aps_occupancy[lvap.default_block.addr.to_str()] * 1.025):
            self.old_aps_occupancy[lvap.default_block.addr.to_str()] = new_occupancy
            if lvap not in self.handover_occupancies:
                self.evaluate_lvap_scheduling(lvap)

    def counters_callback(self, stats):
        """ New stats available. """

        self.log.info("New counters received from %s" % stats.lvap)

        lvap = RUNTIME.lvaps[stats.lvap]
        block = lvap.default_block


        # print("---------+++++++++++++++++++----------------++++++++++")
        # print("---------+++++++++++++++++++----------------++++++++++")
        # print("Counters from %s block %s" %(lvap.addr.to_str(), block.addr.to_str()))
        # print("tx %f rx %f" %(stats.tx_bytes_per_second[0], stats.rx_bytes_per_second[0]))
        # print("---------+++++++++++++++++++----------------++++++++++")
        # print("---------+++++++++++++++++++----------------++++++++++")

        if (not stats.tx_bytes_per_second and not stats.rx_bytes_per_second) and \
            (block.addr.to_str() + stats.lvap.to_str() not in self.wifi_data):
            return

        if not stats.tx_bytes_per_second:
            stats.tx_bytes_per_second = []
            stats.tx_bytes_per_second.append(0)
        if not stats.rx_bytes_per_second:
            stats.rx_bytes_per_second = []
            stats.rx_bytes_per_second.append(0)

        self.counters_to_file(lvap, block, stats)

        key = block.addr.to_str() + stats.lvap.to_str()
        if block.addr.to_str() not in self.old_aps_occupancy or self.old_aps_occupancy[block.addr.to_str()] == 0:
            self.old_aps_occupancy[block.addr.to_str()] = self.update_occupancy_ratio(block)

        if key in self.wifi_data:
            self.wifi_data[key]['tx_bytes_per_second'] = stats.tx_bytes_per_second[0]
            self.wifi_data[key]['rx_bytes_per_second'] = stats.rx_bytes_per_second[0]
        else:
            self.wifi_data[block.addr.to_str() + stats.lvap.to_str()] = \
            {
                'rssi': None,
                'wtp': block.addr.to_str(),
                'sta': stats.lvap.to_str(),
                'channel': lvap.default_block.channel,
                'active': 1,
                'tx_bytes_per_second': stats.tx_bytes_per_second[0],
                'rx_bytes_per_second': stats.rx_bytes_per_second[0],
                'reesched_attempts': 0,
                'revert_attempts': 0,
                'rate': 0,
                'rate_attempts': 0
            }
                            
        # Minimum voice bitrates:
        # https://books.google.it/books?id=ExeKR1iI8RgC&pg=PA88&lpg=PA88&dq=bandwidth+consumption+per+application+voice+video+background&source=bl&ots=1zUvCgqAhZ&sig=5kkM447M4t9ezbVDde3-D3oh2ww&hl=it&sa=X&ved=0ahUKEwiRuvOJv6vUAhWPDBoKHYd5AysQ6AEIWDAG#v=onepage&q=bandwidth%20consumption%20per%20application%20voice%20video%20background&f=false
        # https://www.voip-info.org/wiki/view/Bandwidth+consumption
        # G729A codec minimum bitrate 17K 17804
        if lvap.addr.to_str() not in self.bitrate_data_active[block.addr.to_str()]:
            self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()] = \
                                            {
                                                'tx_bytes_per_second': 0,
                                                'rx_bytes_per_second': 0
                                            }

        if stats.tx_bytes_per_second[0] >= 500:
            self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] = stats.tx_bytes_per_second[0]
        else:
            self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] = 0

        if stats.rx_bytes_per_second[0] >= 500:
            self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] = stats.rx_bytes_per_second[0]
        else:
            self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] = 0       

        if (stats.rx_bytes_per_second[0] < 500) and (stats.tx_bytes_per_second[0] < 500) and len(self.stations_aps_matrix[lvap.addr.to_str()]) > 1:
            self.wifi_data[key]['revert_attempts'] += 1

        new_occupancy = self.update_occupancy_ratio(block)
        average_occupancy = self.average_occupancy_surrounding_aps(lvap)
        print("self.old_aps_occupancy[block.addr.to_str()] ", self.old_aps_occupancy[block.addr.to_str()])

        #if new_occupancy != average_occupancy:
        if new_occupancy < (average_occupancy * 0.975) or new_occupancy > (average_occupancy * 1.025) or \
        new_occupancy < (self.old_aps_occupancy[block.addr.to_str()] * 0.975) or \
        new_occupancy > (self.old_aps_occupancy[block.addr.to_str()] * 1.025):
            if len(self.stations_aps_matrix[lvap.addr.to_str()]) > 1:
                self.wifi_data[key]['reesched_attempts'] += 1

        self.nb_app_active[block.addr.to_str()] = len(self.bitrate_data_active[block.addr.to_str()])

        # print("------self.bitrate_data_active[block]", self.bitrate_data_active[block.addr.to_str()])
        # print("------Revert attempts: ", self.wifi_data[key]['revert_attempts'])
        # print("------Reesched attempts: ", self.wifi_data[key]['reesched_attempts'])
        # print("------New occupancy: ", new_occupancy)
        # print("------self.old_aps_occupancy[block.addr.to_str()]: ", self.old_aps_occupancy[block.addr.to_str()])
        # print("------average_occupancy: ", average_occupancy)


        if self.wifi_data[key]['revert_attempts'] >= 5:
            if lvap.addr.to_str() in self.bitrate_data_active[block.addr.to_str()]:
                del self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]
                self.nb_app_active[block.addr.to_str()] = len(self.bitrate_data_active[block.addr.to_str()])
            self.wifi_data[key]['revert_attempts'] = 0
            #if lvap not in self.handover_occupancies:
            self.evaluate_lvap_revert(lvap)
        elif self.wifi_data[key]['reesched_attempts'] >= 5:
            self.wifi_data[key]['reesched_attempts'] = 0
            self.old_aps_occupancy[block.addr.to_str()] = new_occupancy
            #if self.nb_app_active[block.addr.to_str()] > 1:
            #if lvap not in self.handover_occupancies:
            self.evaluate_lvap_scheduling(lvap)

    def counters_to_file(self, lvap, block, summary):
        """ New stats available. """

        # per block log
        filename = "wifiloadbalancing_%s_%s_%u_%s.csv" % (self.test, block.addr.to_str(),
                                            block.channel,
                                            BANDS[block.band])


        line = "%f,%s,%s,%u,%d, %d,%d\n" % \
            (summary.last, lvap.addr.to_str(), block.addr.to_str(), block.channel, self.aps_occupancy[block.addr.to_str()], \
             summary.rx_bytes_per_second[0], summary.tx_bytes_per_second[0])

        with open(filename, 'a') as file_d:
            file_d.write(line)

        # per link log

        link = "%s_%s_%u_%d_%s" % (lvap.addr.to_str(), block.addr.to_str(),
                                block.channel, self.aps_occupancy[block.addr.to_str()],
                                BANDS[block.band])

        filename = "wifiloadbalancing_%s_link_%s.csv" % (self.test, link)

        line = "%f,%d,%d\n" % \
            (summary.last, summary.rx_bytes_per_second[0], summary.tx_bytes_per_second[0])

        with open(filename, 'a') as file_d:
            file_d.write(line)


    def update_occupancy_ratio(self, block):
        
        if block.addr.to_str() not in self.aps_clients_rel:
            self.aps_occupancy[block.addr.to_str()] = 0
            return 0
        if self.aps_clients_rel[block.addr.to_str()] is None:
            self.aps_occupancy[block.addr.to_str()] = 0
            return 0

        occupancy = 0
        for sta in self.aps_clients_rel[block.addr.to_str()]:
            if block.addr.to_str() + sta not in self.wifi_data:
                continue
            
            if self.wifi_data[block.addr.to_str() + sta]['tx_bytes_per_second'] == 0 and \
                self.wifi_data[block.addr.to_str() + sta]['rx_bytes_per_second'] == 0:
                continue

            if self.wifi_data[block.addr.to_str() + sta]['rate'] == 0:
                continue

            occupancy += (((self.wifi_data[block.addr.to_str() + sta]['tx_bytes_per_second'] \
                            + self.wifi_data[block.addr.to_str() + sta]['rx_bytes_per_second']) * 8 \
                            / self.wifi_data[block.addr.to_str() + sta]['rate']) / 1000000)*100

        # print("/**/*/*/*/*/*/*/* Occupancy ratio of block %s is %d" %(block.addr.to_str(), occupancy))
        self.aps_occupancy[block.addr.to_str()] = occupancy
        return occupancy

    def estimate_global_occupancy_ratio(self):

        global_occupancy = 0
        for ratio in self.aps_occupancy.values():
            global_occupancy += ratio
        
        return global_occupancy


    def evaluate_lvap_revert(self, lvap):

        block = lvap.default_block

        if block.addr.to_str() + lvap.addr.to_str() not in self.wifi_data or \
           self.wifi_data[block.addr.to_str() + lvap.addr.to_str()]['rssi'] is None:
           return

        if lvap.addr.to_str() not in self.stations_aps_matrix:
            return

        current_rssi = self.wifi_data[block.addr.to_str() + lvap.addr.to_str()]['rssi']
        best_rssi = -120
        new_block = None
        
        for wtp in self.stations_aps_matrix[lvap.addr.to_str()]:
            if wtp == block.addr.to_str():
                continue
            if self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] <= (current_rssi + RSSI_LIMIT) or \
                self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] < best_rssi:
                continue

            best_rssi = self.wifi_data[wtp + lvap.addr.to_str()]['rssi']
            new_block = self.get_block_for_ap_addr(wtp)

        if not new_block:
            return

        print("++++++++ Transfering inactive LVAP from %s to %s++++++++" %(block.addr.to_str(), new_block.addr.to_str()))
        print("current_rssi %d. Target rssi %d" % (current_rssi, best_rssi))

        if lvap.default_block == new_block:
            return 

        print("********************")
        print("best_lvap", lvap.addr.to_str())
        print("best_lvap in self.handover_lock", lvap.addr.to_str() in self.handover_lock)
        if lvap.addr.to_str() in self.handover_lock:
            print("time.time() - self.handover_lock[best_lvap]['time']", time.time() - self.handover_lock[lvap.addr.to_str()]['time'])
            print("self.handover_lock[best_lvap]['lock']", self.handover_lock[lvap.addr.to_str()]['lock'])
        print(self.handover_lock)
        print(time.time())
        print("********************")

        if lvap.addr.to_str() in self.handover_lock and \
            ((time.time() - self.handover_lock[lvap.addr.to_str()]['time'] < 3) or \
            self.handover_lock[lvap.addr.to_str()]['lock'] is True):
            return

        if lvap.addr.to_str() in self.handover_lock:
            self.handover_lock[lvap.addr.to_str()]['lock'] = True
            self.handover_lock[lvap.addr.to_str()]['time'] = time.time()
        else:
            self.handover_lock[lvap.addr.to_str()] = \
            {
                'lock': True,
                'time': time.time()
            }

        print("HANDOVER LOCK")
        print(self.handover_lock)
        print(time.time())
        
        lvap.scheduled_on = new_block

        self.transfer_block_data(block, new_block, lvap)

        self.nb_app_active[block.addr.to_str()] = len(self.bitrate_data_active[block.addr.to_str()])
        self.update_occupancy_ratio(block)

        self.nb_app_active[new_block.addr.to_str()] = len(self.bitrate_data_active[new_block.addr.to_str()])
        self.update_occupancy_ratio(new_block)

        self.handover_lock[lvap.addr.to_str()]['lock'] = False


    def evaluate_lvap_scheduling(self, lvap):

        block = lvap.default_block

        # It is not necessary to perform a change if the traffic of the ap is lower than the average or if it is holding a single lvap
        if block.addr.to_str() not in self.aps_occupancy:
            return

        average_occupancy = self.average_occupancy_surrounding_aps(lvap)
        new_block = None
        clients_candidates = {}

        print("/////////////// Evaluating lvap reescheduling %s ///////////////" % lvap.addr.to_str())
        print("average_occupancy", average_occupancy)
        print("self.aps_occupancy[block.addr.to_str()]", self.aps_occupancy[block.addr.to_str()])
        if self.aps_occupancy[block.addr.to_str()] <= average_occupancy: # or self.nb_app_active[block.addr.to_str()] < 2:
            return

        ########## Look for the lvaps from this wtp that can be reescheduled ###########
        clients_candidates = {}

        for sta in self.aps_clients_rel[block.addr.to_str()]:
            # print("Evaluating sta %s" % sta)
            # If this station has no other candidates, it is discarded
            if sta not in self.stations_aps_matrix or len(self.stations_aps_matrix[sta]) < 2:
                continue

            sta_lvap = self.get_lvap_for_sta_addr(sta)
            if sta_lvap in self.handover_occupancies:
                continue

            # Check the wtps that this lvap have in the signal graph
            # print("APs for sta %s" % sta)
            # print(self.stations_aps_matrix[sta])
            for wtp in self.stations_aps_matrix[sta]:
                #TODO. ADD THRES. WHEN THE UNITS OF THE OCCUPANCY ARE KNOWN
                if wtp == block.addr.to_str():
                    continue
                # print("Candidate %s occupancy %f" %(wtp, self.aps_occupancy[wtp]))
                if self.aps_occupancy[wtp] > self.aps_occupancy[block.addr.to_str()] \
                    or self.wifi_data[wtp + sta]['rssi'] < -85:
                    continue

                # Checks if a similar handover has been performed in an appropiate way.
                # If the conditions have changed for 5 times in a row, the wtp is taken again as a candidate
                if sta in self.unsuccessful_handovers:
                    # print("There are unsuccessful handovers", self.unsuccessful_handovers[sta])
                    if wtp in self.unsuccessful_handovers[sta]:
                        if block.addr.to_str() == self.unsuccessful_handovers[sta][wtp]['old_ap'] and \
                        self.aps_occupancy[wtp] < (self.unsuccessful_handovers[sta][wtp]['previous_occupancy'] * 0.975):
                        # self.aps_occupancy[wtp] != self.unsuccessful_handovers[sta][wtp]['previous_occupancy']:
                            self.unsuccessful_handovers[sta][wtp]['handover_retries'] += 1
                        if self.unsuccessful_handovers[sta][wtp]['handover_retries'] < 5:
                            continue
                        del self.unsuccessful_handovers[sta][wtp]

                conflict_occupancy = self.aps_occupancy[wtp]
                wtp_channel = self.aps_channels_matrix[wtp]
                if wtp in self.conflict_aps:
                    for neigh in self.conflict_aps[wtp]:
                        if self.aps_channels_matrix[neigh] != wtp_channel:
                            continue 
                        conflict_occupancy += self.aps_occupancy[neigh]

                wtp_info = \
                    {
                        'wtp': wtp,
                        'metric' : abs(self.wifi_data[wtp + sta]['rssi']) * self.aps_occupancy[wtp],
                        'conf_occupancy': conflict_occupancy,
                        'conf_metric': abs(self.wifi_data[wtp + sta]['rssi']) * conflict_occupancy
                    }
                if sta not in clients_candidates:
                    clients_candidates[sta] = []
                clients_candidates[sta].append(wtp_info)
            
            # if len(clients_candidates[sta]) == 0:
            #     del clients_candidates[sta]

        if len(clients_candidates) == 0:
            # print("Not possible reescheduling. The network is balanced")
            return

        # print("Final candidates relationship")
        print(clients_candidates)

        ########## Evaluate list of candidates lvaps-wtsp ###########
        highest_metric = sys.maxsize
        best_wtp = None
        best_lvap = None
        for sta, wtps in clients_candidates.items():
            for ap in wtps:
                # print("Current highest_metric", highest_metric)
                # print("ap['metric'] < highest_metric", ap['metric'] < highest_metric)
                # print("ap['conf_metric']", ap['conf_metric'])
                if ap['metric'] < highest_metric and ap['conf_metric'] < highest_metric:
                    highest_metric = ap['conf_metric']
                    best_wtp = ap['wtp']
                    best_lvap = sta
                # In case of finding 2 candidates lvaps whose target WTPs occupancy is the same, we will take the one
                # whose current wtp occupancy is higher. In that case it will be less crowded after the handover
                # elif ap['metric'] == highest_metric and ap['conf_metric'] == highest_metric:
                #     if self.aps_occupancy[ap['wtp']] > self.aps_occupancy[best_wtp]:
                #         best_wtp = ap['wtp']
                #         best_lvap = sta

        new_block = self.get_block_for_ap_addr(best_wtp)
        new_lvap = self.get_lvap_for_sta_addr(best_lvap)

        if new_block is None or new_lvap is None:
            # print("KDSFJLDSJFLKDSFJKLDSFJLKDSFDFJDSLKFJDKSL9999999999999999999999 NOT NEW BLOCK")
            return

        if new_lvap.default_block == new_block:
            return 

        if best_lvap in self.handover_lock and \
            ((time.time() - self.handover_lock[best_lvap]['time'] < 3) or \
            self.handover_lock[best_lvap]['lock'] is True):
            return

        print("********************")
        print("best_lvap", best_lvap)
        print("best_lvap in self.handover_lock", best_lvap in self.handover_lock)
        if best_lvap in self.handover_lock:
            print("time.time() - self.handover_lock[best_lvap]['time']", time.time() - self.handover_lock[best_lvap]['time'])
            print("self.handover_lock[best_lvap]['lock']", self.handover_lock[best_lvap]['lock'])
        print(self.handover_lock)
        print(time.time())
        print("********************")

        if best_lvap in self.handover_lock:
            self.handover_lock[best_lvap]['lock'] = True
            self.handover_lock[best_lvap]['time'] = time.time()
        else:
            self.handover_lock[best_lvap] = \
            {
                'lock': True,
                'time': time.time()
            }

        print("HANDOVER LOCK")
        print(self.handover_lock)
        print(time.time())

        print("/////////////// Performing handover for LVAP %s ///////////////" % new_lvap.addr.to_str())
        print("Handover from %s (occup. %f) to %s (occup. %f)" %(block.addr.to_str(), self.aps_occupancy[block.addr.to_str()], new_block.addr.to_str(), highest_metric))

        self.handover_occupancies[new_lvap] = \
            {
                'old_ap': block.addr.to_str(),
                'handover_ap': best_wtp,
                'previous_occupancy': self.estimate_global_occupancy_ratio(),
                'handover_time': time.time()
            }
        
        new_lvap.scheduled_on = new_block

        self.transfer_block_data(block, new_block, new_lvap)

        self.nb_app_active[block.addr.to_str()] = len(self.bitrate_data_active[block.addr.to_str()])
        self.update_occupancy_ratio(block)

        self.nb_app_active[new_block.addr.to_str()] = len(self.bitrate_data_active[new_block.addr.to_str()])
        self.update_occupancy_ratio(new_block)

        self.handover_lock[best_lvap]['lock'] = False




    def transfer_block_data(self, src_block, dst_block, lvap):

        if lvap.addr.to_str() in self.aps_clients_rel[src_block.addr.to_str()]:
            self.aps_clients_rel[src_block.addr.to_str()].remove(lvap.addr.to_str())
        if lvap.addr.to_str() not in self.aps_clients_rel[dst_block.addr.to_str()]:
            self.aps_clients_rel[dst_block.addr.to_str()].append(lvap.addr.to_str())

        self.wifi_data[dst_block.addr.to_str() + lvap.addr.to_str()]['tx_bytes_per_second'] = self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['tx_bytes_per_second']
        self.wifi_data[dst_block.addr.to_str() + lvap.addr.to_str()]['rx_bytes_per_second'] = self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['rx_bytes_per_second']

        if (src_block.addr.to_str() + lvap.addr.to_str()) in self.wifi_data:
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['tx_bytes_per_second'] = 0
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['rx_bytes_per_second'] = 0
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['reesched_attempts'] = 0
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['revert_attempts'] = 0
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['rate'] = 0
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['rate_attempts'] = 0
            self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['active'] = 0

        if src_block.addr.to_str() not in self.bitrate_data_active or \
            lvap.addr.to_str() not in self.bitrate_data_active[src_block.addr.to_str()]:
            return

        if lvap.addr.to_str() not in self.bitrate_data_active[dst_block.addr.to_str()]:
            self.bitrate_data_active[dst_block.addr.to_str()][lvap.addr.to_str()] = \
                {
                    'tx_bytes_per_second': self.bitrate_data_active[src_block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'],
                    'rx_bytes_per_second': self.bitrate_data_active[src_block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second']
                }
        else:
            self.bitrate_data_active[dst_block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] = self.bitrate_data_active[src_block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second']
            self.bitrate_data_active[dst_block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] = self.bitrate_data_active[src_block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second']

        del self.bitrate_data_active[src_block.addr.to_str()][lvap.addr.to_str()]


    def conflict_graph(self):

        initial_conflict_graph = self.conflict_aps

        for wtp_list in self.stations_aps_matrix.values():
            for wtp in wtp_list:
                for conflict_wtp in wtp_list:
                    if conflict_wtp != wtp and (conflict_wtp not in self.conflict_aps[wtp]):
                        self.conflict_aps[wtp].append(conflict_wtp)

    def ucqm_callback(self, poller):
        """Called when a UCQM response is received from a WTP."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for addr in poller.maps.values():
            # This means that this lvap is attached to a WTP in the network.
            if addr['addr'] in lvaps and lvaps[addr['addr']].wtp:
                active_flag = 1

                if (lvaps[addr['addr']].wtp.addr != poller.block.addr):
                    active_flag = 0
                elif ((lvaps[addr['addr']].wtp.addr == poller.block.addr and (lvaps[addr['addr']].association_state == False))):
                    active_flag = 0

                if poller.block.addr.to_str() + addr['addr'].to_str() in self.wifi_data:
                    self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]['rssi'] = addr['mov_rssi']
                    self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]['channel'] = poller.block.channel
                    self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]['active'] = active_flag
                else:
                    self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()] = \
                                    {
                                        'rssi': addr['mov_rssi'],
                                        'wtp': poller.block.addr.to_str(),
                                        'sta': addr['addr'].to_str(),
                                        'channel': poller.block.channel,
                                        'active': active_flag,
                                        'tx_bytes_per_second': 0,
                                        'rx_bytes_per_second': 0,
                                        'reesched_attempts': 0,
                                        'revert_attempts': 0,
                                        'rate': 0,
                                        'rate_attempts': 0
                                    }

                # Conversion of the data structure to obtain the conflict APs
                if addr['addr'].to_str() not in self.stations_aps_matrix:
                    self.stations_aps_matrix[addr['addr'].to_str()] = []
                if poller.block.addr.to_str() not in self.stations_aps_matrix[addr['addr'].to_str()]:
                    self.stations_aps_matrix[addr['addr'].to_str()].append(poller.block.addr.to_str())

            elif poller.block.addr.to_str() + addr['addr'].to_str() in self.wifi_data:
                del self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]

        self.conflict_graph()

    def average_occupancy_surrounding_aps(self, lvap):
        # average_occupancy = 0

        # for key, wtp in enumerate(self.stations_aps_matrix[lvap.addr.to_str()]):
        #     if wtp not in self.aps_occupancy:
        #         continue
        #     average_occupancy += self.aps_occupancy[wtp]

        # return (average_occupancy / len(self.stations_aps_matrix[lvap.addr.to_str()]))
        average_occupancy = 0
        block = lvap.default_block

        if block.addr.to_str() not in self.conflict_aps:
            #return self.aps_occupancy[block.addr.to_str()]
            return self.estimate_global_occupancy_ratio()
        if len(self.conflict_aps[block.addr.to_str()]) == 0:
            return self.estimate_global_occupancy_ratio()


        for wtp in self.conflict_aps[block.addr.to_str()]:
            if wtp not in self.aps_occupancy:
                continue
            average_occupancy += self.aps_occupancy[wtp]

        average_occupancy += self.aps_occupancy[block.addr.to_str()]

        return (average_occupancy / (len(self.conflict_aps[block.addr.to_str()]) + 1))


    def get_block_for_ap_addr(self, addr):
        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps
        for wtp in wtps.values():
            for block in wtp.supports:
                if block.addr.to_str() != addr:
                    continue
                return block

        return None

    def get_lvap_for_sta_addr(self, addr):
        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps
        for lvap in lvaps.values():
                if lvap.addr.to_str() != addr:
                    continue
                return lvap

        return None

    def evaluate_handover(self):

        # If a handover has been recently performed. Let's evaluate the new occupancy rate.
        checked_clients = []

        for lvap, value in self.handover_occupancies.items():

            # Wait some time to get statistics before checking if the handover was valid
            if time.time() - value['handover_time'] < 2:
                continue
            handover_occupancy_rate = self.estimate_global_occupancy_ratio()

            # If the previous occupancy rate was better, the handover must be reverted
            if value['previous_occupancy'] < handover_occupancy_rate:
                self.log.info("The handover from the AP %s to the AP %s for the client %s IS NOT efficient. The previous channel occupancy rate was %f(ms) and it is %f(ms) after the handover. It is going to be reverted" \
                    %(value['old_ap'], value['handover_ap'], lvap, value['previous_occupancy'], handover_occupancy_rate))

                print("********************")
                print("best_lvap", lvap.addr.to_str())
                print("best_lvap in self.handover_lock", lvap.addr.to_str() in self.handover_lock)
                if lvap.addr.to_str() in self.handover_lock:
                    print("time.time() - self.handover_lock[best_lvap]['time']", time.time() - self.handover_lock[lvap.addr.to_str()]['time'])
                    print("self.handover_lock[best_lvap]['lock']", self.handover_lock[lvap.addr.to_str()]['lock'])
                print(self.handover_lock)
                print(time.time())
                print("********************")

                if lvap.addr.to_str() in self.handover_lock and \
                    ((time.time() - self.handover_lock[lvap.addr.to_str()]['time'] < 3) or \
                    self.handover_lock[lvap.addr.to_str()]['lock'] is True):
                    return

                print("HANDOVER LOCK")
                print(self.handover_lock)
                print(time.time())

                if lvap.addr.to_str() in self.handover_lock:
                    self.handover_lock[lvap.addr.to_str()]['lock'] = True
                    self.handover_lock[lvap.addr.to_str()]['time'] = time.time()
                else:
                    self.handover_lock[lvap.addr.to_str()] = \
                    {
                        'lock': True,
                        'time': time.time()
                    }

                # self.revert_handover(lvap, handover_occupancy_rate)
                self.handover_lock[lvap.addr.to_str()]['lock']  = False
            else:
                self.log.info("The handover from the AP %s to the AP %s for the client %s is efficient. The previous channel occupancy rate was %f(ms) and it is %f(ms) after the handover" \
                    %(value['old_ap'], value['handover_ap'], lvap, value['previous_occupancy'], handover_occupancy_rate)) 

            checked_clients.append(lvap)

        for entry in checked_clients:
            del self.handover_occupancies[entry]


    def revert_handover(self, lvap, handover_occupancy_rate):

        handover_ap = self.get_block_for_ap_addr(self.handover_occupancies[lvap]['handover_ap'])
        old_ap = self.get_block_for_ap_addr(self.handover_occupancies[lvap]['old_ap'])

        if lvap.addr.to_str() not in self.unsuccessful_handovers:
            self.unsuccessful_handovers[lvap.addr.to_str()] = {}

        if handover_ap.addr.to_str() not in self.unsuccessful_handovers[lvap.addr.to_str()]:
            self.unsuccessful_handovers[lvap.addr.to_str()] = \
                {
                    handover_ap.addr.to_str(): {
                        'rssi': self.wifi_data[handover_ap.addr.to_str() + lvap.addr.to_str()]['rssi'],
                        'previous_occupancy': handover_occupancy_rate,
                        'handover_retries': 0,
                        'old_ap': old_ap.addr.to_str(),
                        'handover_ap': handover_ap.addr.to_str()
                    }
                }
        else:
            self.unsuccessful_handovers[lvap.addr.to_str()][handover_ap.addr.to_str()]['rssi'] = self.wifi_data[handover_ap.addr.to_str() + lvap.addr.to_str()]['rssi']
            self.unsuccessful_handovers[lvap.addr.to_str()][handover_ap.addr.to_str()]['previous_occupancy'] = handover_occupancy_rate
            self.unsuccessful_handovers[lvap.addr.to_str()][handover_ap.addr.to_str()]['handover_retries'] = 0
            self.unsuccessful_handovers[lvap.addr.to_str()][handover_ap.addr.to_str()]['old_ap'] = old_ap.addr.to_str()
            self.unsuccessful_handovers[lvap.addr.to_str()][handover_ap.addr.to_str()]['handover_ap'] = handover_ap.addr.to_str()

        if lvap.default_block == old_ap:
            return

        print("------------------------ Reverting handover from %s to %s" %(handover_ap.addr.to_str(), old_ap.addr.to_str()))
        lvap.scheduled_on = old_ap

        self.transfer_block_data(handover_ap, old_ap, lvap)

        self.nb_app_active[handover_ap.addr.to_str()] = len(self.bitrate_data_active[handover_ap.addr.to_str()])
        self.update_occupancy_ratio(handover_ap)

        self.nb_app_active[old_ap.addr.to_str()] = len(self.bitrate_data_active[old_ap.addr.to_str()])
        self.update_occupancy_ratio(old_ap)

    def loop(self):
        """ Periodic job. """

        if self.warm_up_phases > 0 and self.initial_setup:
            self.warm_up_phases -= 1
        elif self.warm_up_phases == 0 and self.initial_setup:
            #Message to the APs to change the channel
            self.initial_setup = False
        elif not self.initial_setup:
            if self.handover_occupancies:
                self.evaluate_handover()

def launch(tenant_id, period=500):
    """ Initialize the module. """

    return WifiLoadBalancing(tenant_id=tenant_id, every=period)
