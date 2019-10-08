#!/usr/bin/env python3
#
# Copyright (c) 2017, Estefanía Coronado
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the CREATE-NET nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY CREATE-NET ''AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL CREATE-NET BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

"""Simple multicast management app."""

from empower.core.app import EmpowerApp
from empower.core.resourcepool import BT_HT20
from empower.core.transmissionpolicy import TX_MCAST
from empower.core.transmissionpolicy import TX_MCAST_DMS
from empower.core.transmissionpolicy import TX_MCAST_DMS_H
from empower.core.transmissionpolicy import TX_MCAST_LEGACY
from empower.datatypes.etheraddress import EtherAddress
from empower.main import RUNTIME
import struct
import sys
import math

TX_MCAST_SDNPLAY = 0x3
TX_MCAST_SDNPLAY_H = "sdnplay"


class MCastTub(EmpowerApp):
    """Multicast app with rate adaptation support.

    Command Line Parameters:

        period: loop period in ms (optional, default 5000ms)

    Example:

        ./empower-runtime.py apps.mcast.mcast \
            --tenant_id=52313ecb-9d00-4b7d-b873-b55d3d9ada00

    """

    def __init__(self, **kwargs):

        super().__init__(**kwargs)

        # app parameters
        self.receptors = {}
        self.receptors_mcses = {}
        self.receptors_quality = {}
        self.prob_threshold = 90.0
        self.mcast_addr = EtherAddress("01:00:5e:00:c8:dd")
        self.current = 0
        self.dms = 1
        self.legacy = 9
        self.scheduler = [TX_MCAST_DMS] * self.dms + \
            [TX_MCAST_LEGACY] * self.legacy
        self._demo_mode = TX_MCAST_DMS_H
        self.status = {}

        self.aps_counters = {}
        self._snr = {}
        self.ucqm_data = {}
        self.file = None
        #["cd", "snr", "air"]
        self._scheme = "cd"
        self.aps_clients_matrix = {}

    @property
    def snr(self):
        """Return SNR info."""
        return self._snr
 
    @snr.setter
    def snr(self, snr_info):
        """Updates the SNR"""

        
 
        if not snr_info:
            return

        lvap_addr = snr_info['lvap']

        for freq, val in snr_info['info'].items():
            if val['pwr'] != -127:
                if lvap_addr not in self._snr:
                    self._snr[lvap_addr] = {
                        1:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        2:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        3:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        4:{'pwr':-127, 'noise':-127, 'rssi':-127}, 
                        5:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        6:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        7:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        8:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        9:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        10:{'pwr':-127, 'noise':-127, 'rssi':-127},
                        11:{'pwr':-127, 'noise':-127, 'rssi':-127}
                    }

                self._snr[lvap_addr][val['c']]['pwr'] = val['pwr']
                self._snr[lvap_addr][val['c']]['noise'] = val['noise']
                self._snr[lvap_addr][val['c']]['rssi'] = val['rssi']

    #     station = EtherAddress(aps_info['addr'])
    #     if station not in RUNTIME.lvaps:
    #         return
        
    #     lvap = RUNTIME.lvaps[station]
    #     stats = self.lvap_bssid_to_hwaddr(aps_info['wtps'])

    #     disable_old_wtp = False
    #     enable_handover_search = False
    #     max_rate = None

    #     attached_hwaddr = lvap.blocks[0].hwaddr

    #     if self.occupancy_rate == 0:
    #         self.occupancy_rate = self.overall_occupancy_rate_calculation(lvap.ssid)

    #     for index, entry in enumerate(self.mcast_wtps):
    #         if entry.block.hwaddr not in stats:
    #             continue
    #         if entry.prob_measurement[self.mcast_addr] == MCAST_EWMA_PROB:
    #             if self.mcast_addr in entry.rate:
    #                 stats[entry.block.hwaddr]['rate'] = entry.rate[self.mcast_addr]
    #             else:
    #                 stats[entry.block.hwaddr]['rate'] = 0
    #         elif entry.prob_measurement[self.mcast_addr] == MCAST_CUR_PROB:
    #             if self.mcast_addr in entry.cur_prob_rate:
    #                 stats[entry.block.hwaddr]['rate'] = entry.cur_prob_rate[self.mcast_addr]
    #             else:
    #                 stats[entry.block.hwaddr]['rate'] = 0

    #     for index, entry in enumerate(self.mcast_clients):
    #         if entry.addr == station:
    #             for key, value in stats.items():
    #                 if key not in entry.wtps or (key in entry.wtps and entry.wtps[key] != value):
    #                     enable_handover_search = True
    #                 entry.wtps[key] = value
    #             if entry.last_handover_time is not None and time.time() - entry.last_handover_time <= 3:
    #                 enable_handover_search = False
    #             # Remove the APs that are not already in the coverage area of this client
    #             useless_wtps = []
    #             for key, value in entry.wtps.items():
    #                 if key not in stats:
    #                     useless_wtps.append(key)
    #             for i, wtp in enumerate(useless_wtps):
    #                 del entry.wtps[wtp]

    #             entry.rssi = entry.wtps[attached_hwaddr]['rssi']
    #             self.__aps[station] = stats
    #             max_rate = max(int(float(key)) for key in entry.rates.keys())
    #             break

    #     # Check if the transmission will be turned off in the current WTP (0 clients)
    #     for index, entry in enumerate(self.mcast_wtps):
    #         if entry.block.hwaddr == attached_hwaddr:
    #             entry.attached_clients_rssi[station] = stats[attached_hwaddr]['rssi']
    #             entry.attached_clients = len(entry.attached_clients_rssi)
    #             rssi_values = list(entry.attached_clients_rssi.values())
    #             if len(list(filter((0).__ne__, rssi_values))) > 0:
    #                 entry.avg_perceived_rssi =  statistics.mean(list(filter((0).__ne__, rssi_values)))
    #             if entry.attached_clients > 1 and len(list(filter((0).__ne__, rssi_values))) > 1:
    #                 entry.dev_perceived_rssi = statistics.stdev(list(filter((0).__ne__, rssi_values)))
    #             else:
    #                 entry.dev_perceived_rssi = 0

    #             entry.last_rssi_change = time.time()
    #             entry.prob_measurement[self.mcast_addr] = MCAST_CUR_PROB
    #             if entry.attached_clients == 1:
    #                 disable_old_wtp = True
    #             elif entry.attached_clients == 1 and entry.cur_prob_rate[self.mcast_addr] == max_rate and stats[attached_hwaddr]['rssi'] >= self.rssi_thershold:
    #                 enable_handover_search = False
    #             break

    #     for key, value in self.handover_occupancies.items():
    #         if value['handover_client'] == station:
    #             enable_handover_search = False
    #             break

    #     # If there is only one AP is not worthy to do the process
    #     if len(stats) <= 1 or enable_handover_search is False:
    #         return

    #     self.handover_search(station, stats, disable_old_wtp)

    # def lvap_bssid_to_hwaddr(self, aps_info):
    #     """ holi """

    #     blocks_rssi = dict()

    #     for key, value in aps_info.items():

    #         for vap in self.tenant.vaps.values():
    #             if EtherAddress(key) == vap.bssid:
    #                 blocks_rssi []


    #     aps_hwaddr_info = dict()
    #     shared_tenants = [x for x in RUNTIME.tenants.values()
    #                           if x.bssid_type == T_TYPE_SHARED]

    #     for key, value in aps_info.items():
    #         for tenant in shared_tenants:
    #             if EtherAddress(key) in tenant.vaps and tenant.vaps[EtherAddress(key)].block.hwaddr not in aps_hwaddr_info:
    #                 hwaddr = tenant.vaps[EtherAddress(key)].block.hwaddr
    #                 value['lvap_bssid'] = EtherAddress(key)
    #                 aps_hwaddr_info[hwaddr] = value

    #     return aps_hwaddr_info

    @property
    def scheme(self):
        """Get scheme."""

        return self._scheme

    @scheme.setter
    def scheme(self, scheme):
        """Set the demo mode."""

        self._scheme = scheme

    @property
    def demo_mode(self):
        """Get demo mode."""

        return self._demo_mode

    @demo_mode.setter
    def demo_mode(self, mode):
        """Set the demo mode."""

        self._demo_mode = mode

        # if the demo is not SDN@Play, the tx policy should be ignored
        for block in self.blocks():
            # fetch txp
            txp = block.tx_policies[self.mcast_addr]
            if mode == TX_MCAST[TX_MCAST_DMS]:
                txp.mcast = TX_MCAST_DMS
            elif mode == TX_MCAST[TX_MCAST_LEGACY]:
                txp.mcast = TX_MCAST_LEGACY
                mcs_type = BT_HT20
                if mcs_type == BT_HT20:
                    txp.ht_mcs = [min(block.ht_supports)]
                else:
                    txp.mcs = [min(block.supports)]

        if mode != TX_MCAST_SDNPLAY_H:
            self.status['MCS'] = "None"
            self.status['Phase'] = "None"

    def counters_callback(self, stats):
        """ New stats available. """

        lvap = RUNTIME.lvaps[stats.lvap]

        if lvap.addr not in self.aps_counters[lvap.blocks[0].addr]:
            self.aps_counters[lvap.blocks[0].addr][lvap.addr] = \
            {
                'tx_bytes_per_second': [],
                'tx_packets_per_second': [],
                'tx_bytes': [],
                'tx_packets': [],
                'tx_bytes_c': 0,
                'tx_packets_c': 0
            }

        if lvap.blocks[0].addr.to_str() + lvap.addr.to_str() not in self.ucqm_data:
            self.ucqm_data[lvap.blocks[0].addr.to_str() + lvap.addr.to_str()] = \
                {
                    'rssi': None,
                    'wtp': lvap.blocks[0],
                    'lvap': lvap,
                    'active': 1,
                    'capacity': 0,
                    'power':-127,
                    'rssi_driver': -127,
                    'snr': 1
                }

        cnt = self.aps_counters[lvap.blocks[0].addr][lvap.addr]

        if not stats.tx_bytes_per_second or stats.tx_bytes_per_second[0] == 0:
            return

        cnt['tx_bytes_per_second'].append(stats.tx_bytes_per_second[0])
        cnt['tx_packets_per_second'].append(stats.tx_packets_per_second[0])
        cnt['tx_bytes'].append(stats.tx_bytes[0])
        cnt['tx_packets'].append(stats.tx_packets[0])
        cnt['tx_bytes_c'] += stats.tx_bytes[0]
        cnt['tx_packets_c'] += stats.tx_packets[0]

        text_name = lvap.addr.to_str() + lvap.blocks[0].addr.to_str()
        text_name = text_name+".txt"
        with open(text_name, "a") as text_file:
            print("%.2f,%.2f,%.2f,%.2f,%.2f,%.2f" % \
                (stats.tx_bytes_per_second[0], stats.tx_packets_per_second[0], \
                    stats.tx_bytes[0], stats.tx_packets[0], cnt['tx_bytes_c'], cnt['tx_packets_c']), file=text_file)

    def lvap_join(self, lvap):
        """Called when an LVAP joins a tenant."""

        self.receptors[lvap.addr] = \
            self.lvap_stats(lvap=lvap.addr, every=self.every)

        self.ucqm_data[lvap.blocks[0].addr.to_str() + lvap.addr.to_str()] = \
            {
                'rssi': None,
                'wtp': lvap.blocks[0],
                'lvap': lvap,
                'active': 1,
                'capacity': 0,
                'power':-127,
                'rssi_driver': -127,
                'snr': 1
            }

        self._snr[lvap.addr] = {
            1:{'pwr':-127, 'noise':-127, 'rssi':-127},
            2:{'pwr':-127, 'noise':-127, 'rssi':-127},
            3:{'pwr':-127, 'noise':-127, 'rssi':-127},
            4:{'pwr':-127, 'noise':-127, 'rssi':-127}, 
            5:{'pwr':-127, 'noise':-127, 'rssi':-127},
            6:{'pwr':-127, 'noise':-127, 'rssi':-127},
            7:{'pwr':-127, 'noise':-127, 'rssi':-127},
            8:{'pwr':-127, 'noise':-127, 'rssi':-127},
            9:{'pwr':-127, 'noise':-127, 'rssi':-127},
            10:{'pwr':-127, 'noise':-127, 'rssi':-127},
            11:{'pwr':-127, 'noise':-127, 'rssi':-127}
        }

        if lvap.addr not in self.aps_clients_matrix[lvap.blocks[0].addr]:
            self.aps_clients_matrix[lvap.blocks[0].addr].append(lvap.addr)

        for block in self.blocks():
            if block.addr != lvap.blocks[0].addr:
                 if lvap.addr in self.aps_clients_matrix[block.addr]:
                    del self.aps_clients_matrix[lvap.blocks[0].addr][lvap.addr]

        text_name = lvap.addr.to_str() + lvap.blocks[0].addr.to_str()
        text_name = text_name+".txt"
        with open(text_name, "w") as text_file:
            print("tx_bytes_per_second, tx_packets_per_second, tx_bytes, tx_packets, tx_bytes_c, tx_packets_c", \
                file=text_file)

        hofile = "HO_"+lvap.addr.to_str()+".txt"
        with open(text_name, "w") as text_file:
            print("source, destination, mode", \
                file=text_file)

    def lvap_leave(self, lvap):
        """Called when an LVAP leaves the network."""

        if lvap.addr in self.receptors:
            del self.receptors[lvap.addr]

        if lvap.addr in self.receptors_mcses:
            del self.receptors_mcses[lvap.addr]

        if lvap.addr in self.receptors_quality:
            del self.receptors_quality[lvap.addr]

    def wtp_up(self, wtp):
        """Called when a new WTP connects to the controller."""

        for block in wtp.supports:

            self.ucqm(block=block,
                      every=self.every,
                      callback=self.ucqm_callback)

            self.aps_counters[block.addr] = {}
            self.aps_clients_matrix[block.addr] = list()

    def ucqm_callback (self, poller):
        """Called when a UCQM response is received from a WTP."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for lvap in poller.maps.values():
            key = poller.block.addr.to_str() + lvap['addr'].to_str()
            if lvap['addr'] in lvaps and lvaps[lvap['addr']].wtp:
                active_flag = 1
                if (lvaps[lvap['addr']].wtp.addr != poller.block.addr):
                    active_flag = 0
                elif ((lvaps[lvap['addr']].wtp.addr == poller.block.addr and (lvaps[lvap['addr']].association_state == False))):
                    active_flag = 0
                if key not in self.ucqm_data:
                    self.ucqm_data[key] = \
                    {
                        'rssi': lvap['mov_rssi'],
                        'wtp': poller.block,
                        'lvap': lvaps[lvap['addr']],
                        'active':active_flag,
                        'snr':1,
                        'capacity': self.compute_shannon_capacity(lvap['mov_rssi'], poller.block, lvap['addr']),
                        'power': self.snr[lvap['addr']][poller.block.channel]['pwr'],
                        'rssi_driver': self.snr[lvap['addr']][poller.block.channel]['rssi']
                    }
                else:
                    self.ucqm_data[key]['rssi'] = lvap['mov_rssi']
                    self.ucqm_data[key]['active'] = active_flag
                    self.ucqm_data[key]['capacity'] = self.compute_shannon_capacity(lvap['mov_rssi'], poller.block, lvap['addr'])
                    self.ucqm_data[key]['power'] = self.snr[lvap['addr']][poller.block.channel]['pwr']
                    self.ucqm_data[key]['rssi_driver'] = self.snr[lvap['addr']][poller.block.channel]['rssi']
            elif key in self.ucqm_data:
                del self.ucqm_data[key]

    def compute_shannon_capacity(self, rssi, block, lvap_addr):

        # noise_power = -95
        # # if (self.snr[lvap_addr][channel]['pwr'] != -127):
        # #     noise_power = self.snr[lvap_addr][channel]['pwr']

        # # sig_relation = 1 + (rssi/noise_power)
        # sig_relation = 1
        # key = lvap_addr.to_str() + block.addr.to_str()
        # if self.snr[lvap_addr][block.channel]['rssi'] != -127:
        #     sig_relation = self.snr[lvap_addr][block.channel]['rssi']
        # elif key in self.ucqm_data:
        #     sig_relation = 1 + (self.ucqm_data[key]['rssi']/noise_power)

        # print("********SIG RELATION", sig_relation)
        # capacity = 20000000 * math.log(sig_relation,2)/1000000
        # print("********CAPACITY", capacity)

        noise_power = -95
        sig_relation = 1
        key = block.addr.to_str() + lvap_addr.to_str()

        if key in self.ucqm_data:

            sig_relation = self.ucqm_data[key]['rssi']- noise_power
            if sig_relation < 0:
                sig_relation = 1
            self.ucqm_data[key]['snr'] = sig_relation

        capacity = 0.332* 20000000 * math.log(sig_relation,2)/1000000

        return capacity

    def compute_receptors_mcs(self):
        """ New stats available. """

        for value in self.receptors.values():
            highest_prob = 0
            information = value.to_dict()

            if not information["rates"]:
                continue

            lvap = information["lvap"]
            keys = [float(i) for i in information["rates"].keys()]
            best_mcs = min(list(map(int, keys)))

            if lvap in self.receptors_mcses:
                del self.receptors_mcses[lvap]

            self.receptors_mcses[lvap] = []

            for mcs, stats in information["rates"].items():
                if stats["prob"] >= self.prob_threshold:
                    self.receptors_mcses[lvap].append(int(float(mcs)))
                elif stats["prob"] > highest_prob:
                    best_mcs = int(float(mcs))
                    highest_prob = stats["prob"]

            if not self.receptors_mcses[lvap]:
                self.receptors_quality[lvap] = False
                self.receptors_mcses[lvap].append(best_mcs)
            else:
                self.receptors_quality[lvap] = True

    def calculate_mcs(self):

        self.compute_receptors_mcs()
        if not self.receptors_mcses:
            return 0

        if False not in self.receptors_quality.values():
            mcses = []
            for rates in self.receptors_mcses.values():
                mcses.append(rates)

            mcs_intersection = list(set.intersection(*map(set, mcses)))
            if mcs_intersection:
                mcs = max(mcs_intersection)
                return mcs

        mcs = sys.maxsize
        for rates in self.receptors_mcses.values():
            mcs = min(max(rates), mcs)

        return mcs

    def get_next_phase(self):
        """Get next mcast phase to be scheduled."""

        phase = self.scheduler[self.current % len(self.scheduler)]
        self.current += 1

        return phase

    def multicast_ip_to_ether(self, ip_mcast_addr):
        """Transform an IP multicast address into an Ethernet one."""

        if ip_mcast_addr is None:
            return '\x00' * 6

        # The first 24 bits are fixed according to class D IP
        # and IP multicast address convenctions
        mcast_base = '01:00:5e'

        # The 23 low order bits are mapped.
        ip_addr_bytes = str(ip_mcast_addr).split('.')

        # The first IP byte is not use,
        # and only the last 7 bits of the second byte are used.
        second_byte = int(ip_addr_bytes[1]) & 127
        third_byte = int(ip_addr_bytes[2])
        fourth_byte = int(ip_addr_bytes[3])

        mcast_upper = format(second_byte, '02x') + ':' + \
                      format(third_byte, '02x') + ':' + \
                      format(fourth_byte, '02x')

        return EtherAddress(mcast_base + ':' + mcast_upper)

    def verify_mcast_addr(self, ip_mcast_addr):
        """Verify if it is a valid IP multicast address."""

        ip_addr_b = str(ip_mcast_addr).split('.')

        if len(ip_addr_b) != 4:
            return False

        # class D IP range 224.0.0.0 – 239.255.255.255
        # is reserved for multicast IP addresses
        if int(ip_addr_b[0]) < 224 or int(ip_addr_b[0]) > 239:
            return False

        for byte in range(1, 4):
            if int(ip_addr_b[byte]) < 0 or int(ip_addr_b[byte]) > 255:
                return False

        return True

    def sort_by_snr(self, lvap):
        """Return list sorted by rssi for the specific address."""

        print(self.blocks())
        candidate_block = None
        highest_capacity = 0

        for block in self.blocks():
            
            key = block.addr.to_str() + lvap.addr.to_str()

            if key in self.ucqm_data:
                print(self.ucqm_data[key])
                print("key %s, value %d. current %d" % (key, self.ucqm_data[key]['snr'], highest_capacity))
                if self.ucqm_data[key]['snr'] > highest_capacity:
                    highest_capacity = self.ucqm_data[key]['snr']
                    candidate_block = block

        if not candidate_block or candidate_block == lvap.blocks[0]:
            return

        hofile = "HO_"+lvap.addr.to_str()+".txt"
        with open(hofile, "a") as text_file:
            print("%s, %s, %s" % (lvap.blocks[0].addr.to_str(), candidate_block.addr.to_str(), "snr"), \
                file=text_file)
        if lvap.addr in self.aps_clients_matrix[lvap.blocks[0].addr]:
            self.aps_clients_matrix[lvap.blocks[0].addr].remove(lvap.addr)
        self.aps_clients_matrix[candidate_block.addr].append(lvap.addr)
        
        lvap.blocks = candidate_block

    def sort_by_air(self, lvap):
        """Return list sorted by rssi for the specific address."""

        candidate_block = None
        highest_capacity = 0

        for block in self.blocks():
            key = block.addr.to_str() + lvap.addr.to_str()

            if key in self.ucqm_data:
                length = 1
                if block == lvap.blocks[0]:
                    length = len(self.aps_clients_matrix[block.addr])
                else:
                    length = 1 + len(self.aps_clients_matrix[block.addr])

                if self.ucqm_data[key]['capacity']/length > highest_capacity:
                    highest_capacity = self.ucqm_data[key]['capacity']/length
                    candidate_block = block

        if not candidate_block or candidate_block == lvap.blocks[0]:
            return

        hofile = "HO_"+lvap.addr.to_str()+".txt"
        with open(hofile, "a") as text_file:
            print("%s, %s, %s" % (lvap.blocks[0].addr.to_str(), candidate_block.addr.to_str(), "air"), \
                file=text_file)
        if lvap.addr in self.aps_clients_matrix[lvap.blocks[0].addr]:
            self.aps_clients_matrix[lvap.blocks[0].addr].remove(lvap.addr)
        self.aps_clients_matrix[candidate_block.addr].append(lvap.addr)
        
        lvap.blocks = candidate_block

    def loop(self):
        """ Periodic job. """

        # if the demo is now in DMS it should not calculate anything
        if self.demo_mode == TX_MCAST[TX_MCAST_DMS] or \
           self.demo_mode == TX_MCAST[TX_MCAST_LEGACY]:
        
            if self.scheme == "cd":
                # for lvap in self.lvaps():
                #     candidate_block = self.blocks().sort_by_rssi(lvap.addr).first()
                #     if not candidate_block:
                #         return
                #     if candidate_block[0] != lvap.blocks[0]:
                #         if lvap.addr in self.aps_clients_matrix[lvap.blocks[0].addr]:
                #             self.aps_clients_matrix[lvap.blocks[0].addr].remove(lvap.addr)
                #         self.aps_clients_matrix[candidate_block.addr].append(lvap.addr)
                #     lvap.blocks = candidate_block

                pass

            elif self.scheme == "snr":
                for lvap in self.lvaps():
                    self.sort_by_snr(lvap)
            elif self.scheme == "air":
                for lvap in self.lvaps():
                    self.sort_by_air(lvap)
        else:

            if self.scheme == "mc":
                for lvap in self.lvaps():
                    if lvap.addr.to_str() == "18:5E:0F:E3:B8:68" or lvap.addr.to_str() == "18:5E:0F:E3:B8:45":
                        if lvap.blocks[0] != self.blocks()[0]:
                            if lvap.addr in self.aps_clients_matrix[lvap.blocks[0].addr]:
                                self.aps_clients_matrix[lvap.blocks[0].addr].remove(lvap.addr)
                            self.aps_clients_matrix[self.blocks()[0].addr].append(lvap.addr)
                            lvap.blocks = self.blocks()[0]
                    elif lvap.addr.to_str() == "00:24:D7:35:06:18" or lvap.addr.to_str() == "00:24:D7:07:F3:1C"  or lvap.addr.to_str() == "00:24:D7:72:AB:BC":
                        if lvap.blocks[0] != self.blocks()[1]:
                            if lvap.addr in self.aps_clients_matrix[lvap.blocks[0].addr]:
                                self.aps_clients_matrix[lvap.blocks[0].addr].remove(lvap.addr)
                            self.aps_clients_matrix[self.blocks()[1].addr].append(lvap.addr)
                            lvap.blocks = self.blocks()[1]

                for block in self.blocks():
                    phase = self.get_next_phase()
                    self.log.info("Mcast phase %s", TX_MCAST[phase])

                    txp = block.tx_policies[self.mcast_addr]

                    if phase == TX_MCAST_DMS:
                        txp.mcast = TX_MCAST_DMS
                    else:
                        # legacy period
                        mcs_type = BT_HT20

                        # compute MCS
                        mcs = max(self.calculate_mcs(), min(block.supports))
                        self.status['MCS'] = mcs
                        txp.mcast = TX_MCAST_LEGACY

                        if mcs_type == BT_HT20:
                            txp.ht_mcs = [mcs]
                        else:
                            txp.mcs = [mcs]

                        # assign MCS
                        self.log.info("Block %s setting mcast address %s to %s MCS %d",
                                      block, self.mcast_addr, TX_MCAST[TX_MCAST_DMS], mcs)

                        self.status['Phase'] = TX_MCAST[phase]

    def to_dict(self):
        """ Return a JSON-serializable."""

        out = super().to_dict()

        out['Demo_mode'] = self.demo_mode
        out['scheme'] = self.scheme
        out['SDN@Play parameters'] = \
            {str(k): v for k, v in self.status.items()}
        out['Receptors'] = \
            {str(k): v for k, v in self.receptors.items()}
        out['Status'] = \
            {str(k): v for k, v in self.status.items()}
        # out['SNR'] = \
        #      {str(k): v for k, v in self.snr.items()}
        out['ucqm_data'] = \
            {str(k): {'wtp':v['wtp'].addr, 'lvap':v['lvap'].addr, 'rssi':v['rssi'], \
                     'active':v['active'], 'capacity':v['capacity'], 'power':v['power'], \
                     'rssi_driver':v['rssi_driver'], 'snr':v['snr']} \
                        for k, v in self.ucqm_data.items()}
        out['aps_clients_matrix'] = \
             {str(k): str(v) for k, v in self.aps_clients_matrix.items()}

        return out


def launch(tenant_id, every=1000, snr={}, scheme=""):
    """ Initialize the module. """

    return MCastTub(tenant_id=tenant_id, every=every, snr=snr, scheme=scheme)
