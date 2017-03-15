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
from empower.core.resourcepool import TX_MCAST_DMS_H
from empower.core.tenant import T_TYPE_SHARED
from empower.datatypes.etheraddress import EtherAddress
from empower.main import RUNTIME
from empower.apps.mcast.mcastwtp import MCastWTPInfo
from empower.apps.mcast.mcastclient import MCastClientInfo

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


class DMSMcastMultigroup(EmpowerApp):


    """Mobility manager app with multicast rate adaptation support.

    Command Line Parameters:

        period: loop period in ms (optional, default 5000ms)

    Example:

        (old) ./empower-runtime.py apps.mcast.mcast:52313ecb-9d00-4b7d-b873-b55d3d9ada26
        (new) ./empower-runtime.py apps.mcast.mcastrssi --tenant_id=be3f8868-8445-4586-bc3a-3fe5d2c17339

    """

    def __init__(self, **kwargs):

        EmpowerApp.__init__(self, **kwargs)

        self.__mcast_clients = []
        self.__mcast_wtps = []

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)
        self.lvapleave(callback=self.lvap_leave_callback)
        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)
        self.wtpdown(callback=self.wtp_down_callback)

        self.incom_mcast_addr(every=500, callback=self.incom_mcast_addr_callback)

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
    def mcast_addr(self):
        """Return mcast_addr used."""
        return self.__mcast_addr

    @mcast_addr.setter
    def mcast_addr(self, mcast_addr):
        self.__mcast_addr = mcast_addr

    def incom_mcast_addr_callback(self, request):
        #self.log.info("New multicast address %s from WTP %s", request.mcast_addr, request.wtp)

        if request.wtp not in RUNTIME.tenants[self.tenant.tenant_id].wtps:
            return
        wtp = RUNTIME.tenants[self.tenant.tenant_id].wtps[request.wtp]

        for block in wtp.supports:
            if any(entry.block.hwaddr == block.hwaddr for entry in self.mcast_wtps):
                continue
            self.wtp_register(block)

        self.mcast_addr_register(None, request.mcast_addr, wtp)

    def igmp_report_callback(self, request):
        # self.log.info("IGMP report type %d for multicast address %s from %s in WTP %s", 
        #     request.igmp_type, request.mcast_addr, request.sta, request.wtp)

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

        # self.log.info("Mcast address %s packets %u bytes %u", counter.mcast,
        #               counter.tx_packets[0], counter.tx_bytes[0])

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

        self.igmp_report(every=500, callback=self.igmp_report_callback)

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

        for index, entry in enumerate(self.mcast_clients):
            if entry.addr == lvap.addr:
                del self.mcast_clients[index]
                break

        for index, entry in enumerate(self.mcast_wtps):
            if entry.block.hwaddr == default_block.hwaddr:
                entry.block.radio.connection.send_del_mcast_receiver(lvap.addr, default_block.hwaddr, default_block.channel, default_block.band)
                entry.attached_clients = entry.attached_clients - 1

    def mcast_addr_register(self, sta, mcast_addr, wtp):
        for block in wtp.supports:
            for index, entry in enumerate(self.mcast_wtps):
                if entry.block.hwaddr == block.hwaddr:
                    if mcast_addr not in entry.managed_mcast_addresses:
                        tx_policy = entry.block.tx_policies[mcast_addr]
                        tx_policy.mcast = TX_MCAST_DMS
                        tx_policy.mcs = [min(list(block.supports))]
                        entry.prob_measurement[mcast_addr] = MCAST_EWMA_PROB
                        entry.mode[mcast_addr] = TX_MCAST_DMS_H
                        entry.rate[mcast_addr] = min(entry.block.supports)
                        entry.cur_prob_rate[mcast_addr] = min(entry.block.supports)
                        entry.managed_mcast_addresses.append(mcast_addr)
                        self.txp_bin_counter(block=entry.block,
                            mcast=mcast_addr,
                            callback=self.txp_bin_counter_callback,
                            every=500)
                        break


        for index, entry in enumerate(self.mcast_clients):
            if sta is not None and entry.addr == sta and mcast_addr not in entry.multicast_services:
                entry.multicast_services.append(mcast_addr)
                break

    def mcast_addr_unregister(self, sta, mcast_addr, wtp):
        addr_in_use = False

        for index, entry in enumerate(self.mcast_clients):
            if entry.addr == sta and mcast_addr in entry.multicast_services:
                entry.multicast_services.remove(mcast_addr)
            elif entry.addr != sta and mcast_addr in entry.multicast_services:
                addr_in_use = True

        for block in wtp.supports:
            for index, entry in enumerate(self.mcast_wtps):
                # If there are not clients requesting the service and there is not any ongoing transmission using that address
                # The address can be removed. The signal must be sent to the corresponding AP
                if entry.block.hwaddr == block.hwaddr and  mcast_addr in entry.managed_mcast_addresses and addr_in_use is False and \
                entry.last_tx_bytes[mcast_addr] == 0 and entry.last_tx_pkts[mcast_addr] == 0:
                    entry.managed_mcast_addresses.remove(mcast_addr)
                    del entry.mode[mcast_addr]
                    del entry.rate[mcast_addr]
                    del entry.cur_prob_rate[mcast_addr]
                    del entry.prob_measurement[mcast_addr]
                    del entry.last_tx_bytes[mcast_addr]
                    del entry.last_txp_bin_tx_bytes_counter[mcast_addr]
                    del entry.last_tx_pkts[mcast_addr]
                    del entry.last_txp_bin_tx_pkts_counter[mcast_addr]
                    entry.block.radio.connection.send_del_mcast_addr(mcast_addr, wtp, block.hwaddr, block.channel, block.band)
                    break

    def mcast_addr_query(self, sta, mcast_addr, wtp):
        pass

    def wtp_register(self, block):
        wtp_info = MCastWTPInfo()
        wtp_info.block = block
        wtp_info.dms_max_period = 0
        wtp_info.legacy_max_period = 0
        self.mcast_wtps.append(wtp_info)

    def loop(self):
        """ Periodic job. """
        for index, entry in enumerate(self.mcast_wtps):
            if not entry.managed_mcast_addresses:
                continue

            for i, addr in enumerate(entry.managed_mcast_addresses):
                tx_policy = entry.block.tx_policies[addr]
                tx_policy.mcast = TX_MCAST_DMS
                entry.mode[addr] = TX_MCAST_DMS_H

    def to_dict(self):
        """Return JSON-serializable representation of the object."""
        out = super().to_dict()

        out['mcast_clients'] = []
        for p in self.mcast_clients:
            out['mcast_clients'].append(p.to_dict())
        out['mcast_wtps'] = []
        for p in self.mcast_wtps:
            out['mcast_wtps'].append(p.to_dict()

        return out                                

def launch(tenant_id, every=1000, mcast_clients=[], mcast_wtps=[]):
    """ Initialize the module. """

    return DMSMcastMultigroup(tenant_id=tenant_id, every=every, mcast_clients=mcast_clients, mcast_wtps=mcast_wtps)
