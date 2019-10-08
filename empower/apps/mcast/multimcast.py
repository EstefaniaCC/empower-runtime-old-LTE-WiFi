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
from empower.core.transmissionpolicy import TX_MCAST_LEGACY
from empower.datatypes.etheraddress import EtherAddress
import sys

TX_MCAST_SDNPLAY = 0x3
TX_MCAST_SDNPLAY_H = "sdnplay"
SERVICES={}


class MCastManager(EmpowerApp):
    """Multicast app with rate adaptation support.

    Command Line Parameters:

        period: loop period in ms (optional, default 5000ms)

    Example:

        ./empower-runtime.py apps.mcast.multimcast \
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
        self.schedule = [TX_MCAST_DMS] * self.dms + \
            [TX_MCAST_LEGACY] * self.legacy # --> [DMS, LEGACY, LEGACY...]
        self._demo_mode = TX_MCAST_SDNPLAY_H
        self._mcast_services = {}
        self.status = {}
        self._services_registered = 0

    @property
    def mcast_services(self):
        """Get mcast_services."""
        return self._mcast_services

    @mcast_services.setter
    def mcast_services(self, service):

        if not service:
            return
    
        status = service["status"]
        serv_type = service["type"]
        addr = self.mcast_ip_to_ether(service["ip"]).to_str()
            
        if addr not in self._mcast_services:

            self._mcast_services[addr] = {
                "ip": service["ip"],
                "mcs": 6,
                "schedule": self.schedule[-self._services_registered:] + self.schedule[:-self._services_registered], 
                "receivers": service["receivers"],
                "status": status, 
                "type": serv_type
            }
            self._services_registered += 1
        else:
            self._mcast_services[addr]["receivers"] = service["receivers"]
            self._mcast_services[addr]["status"] = status
            self._mcast_services[addr]["type"] = serv_type

    def set_default_services(self):

        self._mcast_services["01:00:5e:00:c8:dc"] = \
        {
            "ip": "224.0.200.220",
            "mcs": 6,
            "schedule": self.schedule[0::] + self.schedule[:0:], 
            "receivers": ["18:5E:0F:E3:B8:68", "18:5E:0F:E3:B8:45"],
            "status": False, 
            "type": "safety"
        }

        self._mcast_services["01:00:5e:00:c8:dd"] = \
        {
            "ip": "224.0.200.221",
            "mcs": 6,
            "schedule": self.schedule[-1:] + self.schedule[:-1]  , 
            "receivers": ["00:24:D7:72:AB:BC", "00:24:D7:35:06:18", "00:24:D7:07:F3:1C"],
            "status": False, 
            "type": "safety"
        }

        self._mcast_services["01:00:5e:00:c8:de"] = \
        {
            "ip": "224.0.200.222",
            "mcs": 6,
            "schedule": self.schedule[-2:] + self.schedule[:-2], 
            "receivers": ["18:5E:0F:E3:B8:68", "00:24:D7:35:06:18", "00:24:D7:07:F3:1C"],
            "status": False, 
            "type": "flight"
        }

        self._mcast_services["01:00:5e:00:c8:df"] = \
        {
            "ip": "224.0.200.223",
            "mcs": 6,
            "schedule": self.schedule[-3:] + self.schedule[:-3], 
            "receivers": ["00:24:D7:72:AB:BC", "18:5E:0F:E3:B8:45"],
            "status": False, 
            "type": "flight"
        }

    @property
    def demo_mode(self):
        """Get demo mode."""

        return self._demo_mode

    @demo_mode.setter
    def demo_mode(self, mode):
        """Set the demo mode."""

        self._demo_mode = mode

        if not self._mcast_services:
            return

        for addr, entry in self._mcast_services.items():

            phase = self.get_next_group_phase(addr)
            self.log.info("Mcast phase %s for group %s" % (TX_MCAST[phase], EtherAddress(addr)))

            for block in self.blocks():
                # fetch txp
                txp = block.tx_policies[EtherAddress(addr)]

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
                entry['mcs'] = "None"

    def lvap_join(self, lvap):
        """Called when an LVAP joins a tenant."""

        self.receptors[lvap.addr] = \
            self.lvap_stats(lvap=lvap.addr, every=self.every)

    def lvap_leave(self, lvap):
        """Called when an LVAP leaves the network."""

        if lvap.addr in self.receptors:
            del self.receptors[lvap.addr]

        if lvap.addr in self.receptors_mcses:
            del self.receptors_mcses[lvap.addr]

        if lvap.addr in self.receptors_quality:
            del self.receptors_quality[lvap.addr]

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

    def calculate_group_mcs(self, group_receivers):

        self.compute_receptors_mcs()

        if not self.receptors_mcses:
            return 0

        if False not in self.receptors_quality.values():
            mcses = []
            for lvap, rates in self.receptors_mcses.items():
                if lvap in group_receivers:
                    mcses.append(rates)

            if mcses:
                mcs_intersection = list(set.intersection(*map(set, mcses)))
                if mcs_intersection:
                    mcs = max(mcs_intersection)
                    return mcs

        mcs = sys.maxsize
        print("*** sys max", mcs)
        for lvap, rates in self.receptors_mcses.items():
            if lvap in group_receivers:
                mcs = min(max(rates), mcs)

        if mcs == sys.maxsize:
            mcs = 0

        return mcs

    def get_next_group_phase(self, mcast_addr):
        """Get next mcast phase to be scheduled."""

        phase = self._mcast_services[mcast_addr]["schedule"][self.current % len(self.schedule)]
        self.current += 1

        return phase

    def mcast_ip_to_ether(self, ip_mcast_addr):
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

    def loop(self):
        """ Periodic job. """

        # if the demo is now in DMS it should not calculate anything
        if self.demo_mode == TX_MCAST[TX_MCAST_DMS] or \
           self.demo_mode == TX_MCAST[TX_MCAST_LEGACY]:
            return

        if not self.mcast_services:
            # self.set_default_services()
            return

        for block in self.blocks():
            for addr, entry in self._mcast_services.items():

                phase = self.get_next_group_phase(addr)
                self.log.info("Mcast phase %s for group %s" % (TX_MCAST[phase], EtherAddress(addr)))

                # fetch txp
                txp = block.tx_policies[EtherAddress(addr)]

                # If the service is disabled, DMS must be the multicast mode used.
                if entry["status"] is False:
                    txp.mcast = TX_MCAST_DMS
                    continue

                if phase == TX_MCAST_DMS:
                    txp.mcast = TX_MCAST_DMS
                else:
                    # legacy period
                    mcs_type = BT_HT20

                    # compute MCS
                    temp_mcs = self.calculate_group_mcs(entry["receivers"])
                    mcs = max(temp_mcs, min(block.supports))
                    entry['mcs'] = mcs
                    txp.mcast = TX_MCAST_LEGACY

                    if mcs_type == BT_HT20:
                        txp.ht_mcs = [mcs]
                    else:
                        txp.mcs = [mcs]

                    # assign MCS
                    self.log.info("Block %s setting mcast address %s to %s MCS %d",
                                  block, EtherAddress(addr), TX_MCAST[TX_MCAST_DMS], mcs)


    def to_dict(self):
        """ Return a JSON-serializable."""

        out = super().to_dict()

        out['Demo_mode'] = self.demo_mode
        out['SDN@Play parameters'] = \
            {str(k): v for k, v in self.status.items()}
        out['Phases_schedule'] = [TX_MCAST[x] for x in self.schedule]
        out['MCAST services'] = \
            {str(k): v for k, v in self.mcast_services.items()}

        return out

def launch(tenant_id, every=1000):

    return MCastManager(tenant_id=tenant_id, every=every)
