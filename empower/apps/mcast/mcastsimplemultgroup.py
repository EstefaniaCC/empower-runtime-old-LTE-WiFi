#!/usr/bin/env python3
#
# Copyright (c) 2016, Estefanía Coronado
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

"""Multicast management app with handover support."""

import tornado.web
import tornado.httpserver
import time
import datetime
import sys
import statistics

from empower.core.app import EmpowerApp
from empower.core.resourcepool import TX_MCAST
from empower.core.resourcepool import TX_MCAST_DMS
from empower.core.resourcepool import TX_MCAST_LEGACY
from empower.core.resourcepool import TX_MCAST_DMS_H
from empower.core.resourcepool import TX_MCAST_LEGACY_H
from empower.core.tenant import T_TYPE_SHARED
from empower.datatypes.etheraddress import EtherAddress
from empower.main import RUNTIME
from empower.apps.mcast.mcastwtp import MCastWTPInfo
from empower.apps.mcast.mcastclient import MCastClientInfo
from empower.main import RUNTIME

from empower.igmp_report.igmp_report import V3_MODE_IS_INCLUDE
from empower.igmp_report.igmp_report import V3_MODE_IS_EXCLUDE
from empower.igmp_report.igmp_report import V3_CHANGE_TO_INCLUDE_MODE
from empower.igmp_report.igmp_report import V3_CHANGE_TO_EXCLUDE_MODE
from empower.igmp_report.igmp_report import V3_ALLOW_NEW_SOURCES
from empower.igmp_report.igmp_report import V3_BLOCK_OLD_SOURCES
from empower.igmp_report.igmp_report import V2_JOIN_GROUP
from empower.igmp_report.igmp_report import V2_LEAVE_GROUP
from empower.igmp_report.igmp_report import V1_MEMBERSHIP_REPORT
from empower.igmp_report.igmp_report import V1_V2_MEMBERSHIP_QUERY

import empower.logger
LOG = empower.logger.get_logger()

MCAST_EWMA_PROB = "ewma"
MCAST_CUR_PROB = "cur_prob"


class MCastMultigroup(EmpowerApp):


    """Multicast app with rate adaptation support.

    Command Line Parameters:

        period: loop period in ms (optional, default 5000ms)

    Example:

        (old) ./empower-runtime.py apps.mcast.mcast:52313ecb-9d00-4b7d-b873-b55d3d9ada26
        (new) ./empower-runtime.py apps.mcast.mcastsimplemultgroup --tenant_id=52313ecb-9d00-4b7d-b873-b55d3d9ada00

    """

    def __init__(self, **kwargs):

        EmpowerApp.__init__(self, **kwargs)
        self.__mcast_clients = list()
        self.__mcast_wtps = list()
        self.__prob_thershold = 95

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)
        self.lvapleave(callback=self.lvap_leave_callback)
        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)
        self.wtpdown(callback=self.wtp_down_callback)

        self.incom_mcast_addr(callback=self.incom_mcast_addr_callback)

        self.empower_igmp_record_type = { V3_MODE_IS_INCLUDE : self.mcast_addr_unregister,
            V3_MODE_IS_EXCLUDE : self.mcast_addr_register,
            V3_CHANGE_TO_INCLUDE_MODE : self.mcast_addr_unregister,
            V3_CHANGE_TO_EXCLUDE_MODE : self.mcast_addr_register,
            V3_ALLOW_NEW_SOURCES : self.mcast_addr_query,
            V3_BLOCK_OLD_SOURCES : self.mcast_addr_query,
            V2_JOIN_GROUP : self.mcast_addr_register,
            V2_LEAVE_GROUP : self.mcast_addr_unregister,
            V1_MEMBERSHIP_REPORT : self.mcast_addr_register,
            V1_V2_MEMBERSHIP_QUERY : self.mcast_addr_query
        }

    @property
    def mcast_clients(self):
        """Return current multicast clients."""
        return self.__mcast_clients

    @mcast_clients.setter
    def mcast_clients(self, mcast_clients_info):
        self.__mcast_clients = mcast_clients_info

    @property
    def mcast_wtps(self):
        """Return current multicast wtps."""
        return self.__mcast_wtps

    @mcast_wtps.setter
    def mcast_wtps(self, mcast_wtps_info):
        self.__mcast_wtps = mcast_wtps_info

    @property
    def prob_thershold(self):
        """Return current probability thershold."""
        return self.__prob_thershold

    @prob_thershold.setter
    def prob_thershold(self, prob_thershold):
        self.__prob_thershold = prob_thershold

    def incom_mcast_addr_callback(self, request):
        self.log.info("APP LEVEL, INCOMING MCAST ADDRESS %s from WTP %s", request.mcast_addr, request.wtp)

        if request.wtp not in RUNTIME.tenants[self.tenant.tenant_id].wtps:
            return
        
        wtp = RUNTIME.tenants[self.tenant.tenant_id].wtps[request.wtp]
        self.mcast_addr_register(None, request.mcast_addr, wtp)

    def igmp_report_callback(self, request):
        self.log.info("APP LEVEL, IGMP REPORT type %d for %s multicast address from %s station in WTP %s", 
            request.igmp_type, request.mcast_addr, request.sta, request.wtp)

        if request.wtp not in RUNTIME.tenants[self.tenant.tenant_id].wtps:
            return
        if request.sta not in RUNTIME.lvaps:
            return

        wtp = RUNTIME.tenants[self.tenant.tenant_id].wtps[request.wtp]
        lvap = RUNTIME.lvaps[request.sta]

        if request.igmp_type not in self.empower_igmp_record_type:
            return
        self.empower_igmp_record_type[request.igmp_type](lvap.addr, request.mcast_addr, wtp)

    def txp_bin_counter_callback(self, counter):
        """Counters callback."""

        self.log.info("Mcast address %s packets %u bytes %u", counter.mcast,
                      counter.tx_packets[0], counter.tx_bytes[0])

        for index, entry in enumerate(self.mcast_wtps):
            if entry.block.hwaddr == counter.block.hwaddr:
                if counter.mcast in entry.last_txp_bin_tx_pkts_counter:
                    entry.last_tx_pkts[counter.mcast] = counter.tx_packets[0] - entry.last_txp_bin_tx_pkts_counter[counter.mcast]
                else:
                    entry.last_tx_pkts[counter.mcast] = counter.tx_packets[0]
                entry.last_txp_bin_tx_pkts_counter[counter.mcast] = counter.tx_packets[0]
                if counter.mcast in entry.last_txp_bin_tx_bytes_counter:
                    entry.last_tx_bytes[counter.mcast] = counter.tx_bytes[0] - entry.last_txp_bin_tx_bytes_counter[counter.mcast]
                else:
                    entry.last_tx_bytes[counter.mcast] = counter.tx_bytes[0]
                entry.last_txp_bin_tx_bytes_counter[counter.mcast] = counter.tx_bytes[0]
                break

    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""
        for block in wtp.supports:
            if any(entry.block.hwaddr == block.hwaddr for entry in self.mcast_wtps):
                continue

            self.wtp_register(block)         

    def wtp_down_callback(self, wtp):
        """Called when a wtp connectdiss from the controller."""

        for index, entry in enumerate(self.mcast_wtps):
            for block in wtp.supports:
                if block.hwaddr == entry.block.hwaddr:
                    del self.mcast_wtps[index]
                    break

    def lvap_join_callback(self, lvap):
        """ New LVAP. """

        if any(lvap.addr == entry.addr for entry in self.mcast_clients):
            return

        lvap.lvap_stats(every=self.every, callback=self.lvap_stats_callback)
        self.igmp_report(callback=self.igmp_report_callback)

        default_block = next(iter(lvap.downlink))
        lvap_info = MCastClientInfo()

        lvap_info.addr = lvap.addr
        lvap_info.attached_hwaddr = default_block.hwaddr
        self.mcast_clients.append(lvap_info)

        for index, entry in enumerate(self.mcast_wtps):
            if entry.block.hwaddr == default_block.hwaddr:
                entry.attached_clients = entry.attached_clients + 1
                break

    def lvap_leave_callback(self, lvap):
        """Called when an LVAP disassociates from a tennant."""

        default_block = next(iter(lvap.downlink))
        mcast_addresses_in_use = list()

        for index, entry in enumerate(self.mcast_clients):
            if entry.addr == lvap.addr:
                del self.mcast_clients[index]
                mcast_addresses_in_use = entry.multicast_services
                break

        for index, entry in enumerate(self.mcast_wtps):
            if entry.block.hwaddr == default_block.hwaddr:
                entry.attached_clients = entry.attached_clients - 1
                if entry.attached_clients == 0:
                    return
                # In case that this was not the only client attached to this WTP, the rate must be recomputed. 
                if not mcast_addresses_in_use:
                    return
                for i, addr in enumerate(mcast_addresses_in_use):
                    tx_policy = entry.block.tx_policies[addr]
                    ewma_rate, cur_prob_rate = self.calculate_wtp_rate(entry, addr)
                    tx_policy.mcast = TX_MCAST_LEGACY
                    if entry.prob_measurement[addr] == MCAST_EWMA_PROB:
                        tx_policy.mcs = [int(ewma_rate)]
                    elif entry.prob_measurement[addr] == MCAST_CUR_PROB:
                        tx_policy.mcs = [int(cur_prob_rate)]
                    entry.rate[addr] = ewma_rate
                    entry.cur_prob_rate[addr] = cur_prob_rate
                    entry.mode[addr] = TX_MCAST_LEGACY_H
                    break
                break

    def lvap_stats_callback(self, counter):
        """ New stats available. """

        rates = (counter.to_dict())["rates"]
        if not rates or counter.lvap not in RUNTIME.lvaps:
            return

        highest_prob = 0
        highest_rate = 0
        highest_cur_prob = 0
        sec_highest_rate = 0
        higher_thershold_ewma_rates = []
        higher_thershold_ewma_prob = []
        higher_thershold_cur_prob_rates = []
        higher_thershold_cur_prob = []
        lowest_rate = min(int(float(key)) for key in rates.keys())

        # Looks for the rate that has the highest ewma prob. for the station.
        # If two rates have the same probability, the highest one is selected. 
        # Stores in a list the rates whose ewma prob. is higher than a certain thershold.
        for key, entry in rates.items():  #key is the rate
            if (rates[key]["prob"] > highest_prob) or \
            (rates[key]["prob"] == highest_prob and int(float(key)) > highest_rate):
                highest_rate = int(float(key))
                highest_prob = rates[key]["prob"]
            if (int(float(rates[key]["prob"]))) >= self.prob_thershold:
                higher_thershold_ewma_rates.append(int(float(key)))
                higher_thershold_ewma_prob.append(rates[key]["prob"])

        # Looks for the rate that has the highest cur prob and is lower than the one selected
        # for the ewma prob for the station.
        # Stores in a list the rates whose cur prob. is higher than thershold%.
        for key, entry in rates.items():
            if rates[key]["cur_prob"] > highest_cur_prob or \
            (rates[key]["cur_prob"] == highest_cur_prob and int(float(key)) > sec_highest_rate):
                sec_highest_rate = int(float(key))
                highest_cur_prob = rates[key]["cur_prob"] 
            if (int(float(rates[key]["cur_prob"]))) >= self.prob_thershold:
                higher_thershold_cur_prob_rates.append(int(float(key)))
                higher_thershold_cur_prob.append(rates[key]["cur_prob"])     

        if highest_cur_prob == 0 and highest_prob == 0:
            highest_rate = lowest_rate
            sec_highest_rate = lowest_rate
        elif highest_cur_prob == 0 and highest_prob != 0:
            sec_highest_rate = highest_rate

        # The information of the client is updated with the new statistics
        lvap = RUNTIME.lvaps[counter.lvap]
        for index, entry in enumerate(self.mcast_clients):
            if entry.addr == counter.lvap:
                entry.highest_rate = int(highest_rate)
                entry.rates = rates
                entry.highest_cur_prob_rate = int(sec_highest_rate)
                entry.higher_thershold_ewma_rates = higher_thershold_ewma_rates
                entry.higher_thershold_cur_prob_rates = higher_thershold_cur_prob_rates
                break

        def mcast_addr_register(self, sta, mcast_addr, wtp):
        for block in wtp.supports:
            for entry in self.mcast_wtps:
                if entry.block.hwaddr == block.hwaddr and mcast_addr not in entry.managed_mcast_addresses:
                    tx_policy = entry.block.tx_policies[mcast_addr]
                    tx_policy.mcast = TX_MCAST_LEGACY
                    tx_policy.mcs = [min(list(block.supports))]
                    entry.prob_measurement[mcast_addr] = MCAST_EWMA_PROB
                    entry.mode[mcast_addr] = TX_MCAST_LEGACY
                    entry.managed_mcast_addresses.append(mcast_addr)
                    self.txp_bin_counter(block=entry.block,
                        mcast=mcast_addr,
                        callback=self.txp_bin_counter_callback,
                        every=1000)
                    break

        for index, entry in enumerate(self.mcast_clients):
            if sta is not None and entry.addr == sta and mcast_addr not in entry.multicast_services:
                entry.multicast_services.append(mcast_addr)
                break

    def mcast_addr_unregister(self, mcast_addr, sta, wtp):
        addr_in_use = False

        for index, entry in enumerate(self.mcast_clients):
            if entry.addr == sta and mcast_addr in entry.multicast_services:
                entry.multicast_services.remove(mcast_addr)
            elif entry.addr != sta and mcast_addr in entry.multicast_services:
                addr_in_use = True

        for block in wtp.supports:
            for entry in self.mcast_wtps:
                if entry.block.hwaddr == block.hwaddr and mcast_addr in entry.managed_mcast_addresses and addr_in_use is False:
                    entry.managed_mcast_addresses.remove(mcast_addr)
                    del entry.mode[mcast_addr]
                    del entry.rate[mcast_addr]
                    del cur_prob_rate[mcast_addr]
                    del entry.prob_measurement[mcast_addr]
                    del last_tx_bytes[mcast_addr]
                    del last_txp_bin_tx_bytes_counter[mcast_addr]
                    del last_tx_pkts[mcast_addr]
                    del last_txp_bin_tx_pkts_counter[mcast_addr]
                    break

    def mcast_addr_query(self, mcast_addr, sta, wtp):
        pass

    def wtp_register(self, block):
        wtp_info = MCastWTPInfo()
        wtp_info.block = block
        self.mcast_wtps.append(wtp_info)


    def loop(self):
        """ Periodic job. """
        if not self.mcast_clients:
            return
        for index, entry in enumerate(self.mcast_wtps):
            if not entry.managed_mcast_addresses:
                continue
            for i, addr in enumerate(entry.managed_mcast_addresses):
                tx_policy = entry.block.tx_policies[addr] 
                # If there is no clients, the default mode is DMS
                # If there are many clients per AP, it combines DMS and legacy to obtain statistics. 
                # If the AP is in DMS mode and the has been an update of the RSSI, the mode is changed to legacy.
                if entry.attached_clients == 0 or \
                (entry.mode[addr] == TX_MCAST_DMS_H and (entry.current_period % (entry.dms_max_period + entry.legacy_max_period)) < 1):
                    tx_policy.mcast = TX_MCAST_DMS
                    entry.mode[addr] = TX_MCAST_DMS_H
                else:
                    ewma_rate, cur_prob_rate = self.calculate_wtp_rate(entry, addr)
                    tx_policy.mcast = TX_MCAST_LEGACY
                    if entry.prob_measurement[addr] == MCAST_EWMA_PROB:
                        tx_policy.mcs = [int(ewma_rate)]
                    elif entry.prob_measurement[addr] == MCAST_CUR_PROB:
                        tx_policy.mcs = [int(cur_prob_rate)]
                    entry.rate[addr] = ewma_rate
                    entry.cur_prob_rate[addr] = cur_prob_rate
                    entry.mode[addr] = TX_MCAST_LEGACY_H

                    if (entry.current_period % (entry.dms_max_period + entry.legacy_max_period)) == entry.legacy_max_period:
                        entry.current_period = -1

                if entry.attached_clients > 0:
                    entry.current_period += 1


    def calculate_wtp_rate(self, mcast_wtp, addr):
        min_rate = best_rate = min_highest_cur_prob_rate = best_highest_cur_prob_rate = sys.maxsize
        thershold_intersection_list = []
        thershold_highest_cur_prob_rate_intersection_list = []
        highest_thershold_valid = True
        second_thershold_valid = True

        for index, entry in enumerate(self.mcast_clients):
            if entry.attached_hwaddr == mcast_wtp.block.hwaddr and addr in entry.multicast_services:
                # It looks for the lowest rate among all the receptors just in case in there is no valid intersection
                # for the best rates of the clients (for both the ewma and cur probabilities). 
                if entry.highest_rate < min_rate:
                    min_rate = entry.highest_rate
                if entry.highest_cur_prob_rate < min_highest_cur_prob_rate:
                    min_highest_cur_prob_rate = entry.highest_cur_prob_rate

                # It checks if there is a possible intersection among the clients rates for the emwa prob.
                if highest_thershold_valid is True:
                    # If a given client does not have any rate higher than the required prob (e.g. thershold% for emwa)
                    # it is assumed that there is no possible intersection
                    if not entry.higher_thershold_ewma_rates:
                        highest_thershold_valid = False
                    elif not thershold_intersection_list:
                        thershold_intersection_list = entry.higher_thershold_ewma_rates
                    else:
                        thershold_intersection_list = list(set(thershold_intersection_list) & set(entry.higher_thershold_ewma_rates))
                        if not thershold_intersection_list:
                            highest_thershold_valid = False
                # It checks if there is a possible intersection among the clients rates for the cur prob.
                if second_thershold_valid is True:
                    # If a given client does not have any rate higher than the required prob (e.g. thershold% for cur prob)
                    # it is assumed that there is no possible intersection
                    if not entry.higher_thershold_cur_prob_rates:
                        second_thershold_valid = False
                    elif not thershold_highest_cur_prob_rate_intersection_list:
                        thershold_highest_cur_prob_rate_intersection_list = entry.higher_thershold_cur_prob_rates
                    else:
                        thershold_highest_cur_prob_rate_intersection_list = list(set(thershold_highest_cur_prob_rate_intersection_list) & set(entry.higher_thershold_cur_prob_rates))
                        if not thershold_highest_cur_prob_rate_intersection_list:
                            second_thershold_valid = False

        # If the old client was the only client in the wtp or there is not any client, lets have the basic rate
        if min_rate == sys.maxsize:
            for index, entry in enumerate(self.mcast_wtps):
                if entry.block.hwaddr == mcast_wtp.block.hwaddr:
                    min_rate = min(entry.block.supports)
                    min_highest_cur_prob_rate = min(entry.block.supports)
                    break
        
        # If some rates have been obtained as a result of the intersection, the highest one is selected as the rate. 
        if thershold_intersection_list:
            best_rate = max(thershold_intersection_list)
        # Otherwise, the rate selected is the minimum among the MRs
        else:
            best_rate = min_rate
        # The same happens for the cur prob. 
        if thershold_highest_cur_prob_rate_intersection_list:
            best_highest_cur_prob_rate = max(thershold_highest_cur_prob_rate_intersection_list)
        else:
            best_highest_cur_prob_rate = min_highest_cur_prob_rate

        return best_rate, best_highest_cur_prob_rate
    

    def to_dict(self):
        """Return JSON-serializable representation of the object."""
        out = super().to_dict()

        out['mcast_clients'] = []
        for p in self.mcast_clients:
            out['mcast_clients'].append(p.to_dict())
        out['mcast_wtps'] = []
        for p in self.mcast_wtps:
            out['mcast_wtps'].append(p.to_dict())

        return out                                  


def launch(tenant_id, every=1000, mcast_clients=[], mcast_wtps=[]):
    """ Initialize the module. """

    return MCastMultigroup(tenant_id=tenant_id, every=every, mcast_clients=mcast_clients, mcast_wtps=mcast_wtps)
