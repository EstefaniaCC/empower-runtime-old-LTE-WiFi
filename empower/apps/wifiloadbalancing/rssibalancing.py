#!/usr/bin/env python3
#
# Copyright (c) 2016 Roberto Riggio
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

"""Basic mobility manager."""
import random

from empower.core.app import EmpowerApp
from empower.core.app import DEFAULT_PERIOD
from empower.main import RUNTIME
from empower.maps.ucqm import ucqm
from empower.bin_counter.bin_counter import BinCounter
from empower.events.wtpup import wtpup
from empower.events.lvapjoin import lvapjoin
from empower.core.resourcepool import BANDS
from empower.apps.survey import survey

DEFAULT_ADDRESS = "ff:ff:ff:ff:ff:ff"
DEFAULT_LIMIT = -30

class RssiLoadBalancing(EmpowerApp):
    """Basic mobility manager.

    Command Line Parameters:

        tenant_id: tenant id
        limit: handover limit in dBm (optional, default -80)
        every: loop period in ms (optional, default 5000ms)

    Example:

        ./empower-runtime.py apps.mobilitymanager.mobilitymanager \
            --tenant_id=52313ecb-9d00-4b7d-b873-b55d3d9ada26
    """

    def __init__(self, **kwargs):
        EmpowerApp.__init__(self, **kwargs)

        self.initial_setup = True
        self.warm_up_phases = 20

        self.__limit = DEFAULT_LIMIT

        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)

        # self.channels_bg = [1, 6, 11]
        # self.channels_an = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 123, 136, 140]
        self.channels_bg = []
        #self.channels_an = [56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 140]
        #self.channels_an = [149, 153, 157, 161, 165]
        self.channels_an = [149, 153, 157]
        self.channels = self.channels_bg + self.channels_an

        self.test = "test1"
        self.wifi_data = {}
        self.stations_aps_matrix = {}

    def to_dict(self):
        """Return json-serializable representation of the object."""

        out = super().to_dict()
        out['wifi_data'] = self.wifi_data
        out['stations_aps_matrix'] = self.stations_aps_matrix

        return out

    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""

        # lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps
        # new_channel = random.choice(self.channels)

        for block in wtp.supports:
        #     block.channel = new_channel

            self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

            self.summary(addr=DEFAULT_ADDRESS,
                         block=block,
                         every=self.every,
                         callback=self.summary_callback)


    def lvap_join_callback(self, lvap):
        """Called when an joins the network."""

        self.bin_counter(lvap=lvap.addr,
                 every=1000,
                 callback=self.counters_callback)

        self.rssi(lvap=lvap.addr,
                  value=self.limit,
                  relation='LT',
                  callback=self.low_rssi)

        self.stations_aps_matrix[lvap.addr.to_str()] = []
        if lvap.blocks[0].addr.to_str() not in self.stations_aps_matrix[lvap.addr.to_str()]:
            self.stations_aps_matrix[lvap.addr.to_str()].append(lvap.blocks[0].addr.to_str())

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

    def summary_callback(self, summary):
        """ New stats available. """

        self.log.info("New summary from %s addr %s frames %u", summary.block,
                      summary.addr, len(summary.frames))

        # per block log
        filename = "survey_rssibalancing_%s_%s_%u_%s.csv" % (self.test, summary.block.addr,
                                            summary.block.channel,
                                            BANDS[summary.block.band])

        for frame in summary.frames:

            line = "%u,%g,%s,%d,%u,%s,%s,%s,%s,%s\n" % \
                (frame['tsft'], frame['rate'], frame['rtype'], frame['rssi'],
                 frame['length'], frame['type'], frame['subtype'],
                 frame['ra'], frame['ta'], frame['seq'])

            with open(filename, 'a') as file_d:
                file_d.write(line)

    def counters_callback(self, stats):
        """ New stats available. """

        self.log.info("New counters received from %s" % stats.lvap)

        lvap = RUNTIME.lvaps[stats.lvap]
        block = lvap.blocks[0]

        if not stats.tx_bytes_per_second and not stats.rx_bytes_per_second:
            print("-----It's null")
            return

        if not stats.tx_bytes_per_second:
            stats.tx_bytes_per_second = []
            stats.tx_bytes_per_second.append(0)
        if not stats.rx_bytes_per_second:
            stats.rx_bytes_per_second = []
            stats.rx_bytes_per_second.append(0)

        self.counters_to_file(lvap, block, stats)

    def counters_to_file(self, lvap, block, stats):
        """ New stats available. """

        # per block log
        filename = "rssibalancing_%s_%s_%u_%s.csv" % (self.test, block.addr.to_str(),
                                            block.channel,
                                            BANDS[block.band])


        line = "%f,%s,%s,%u,%f, %f\n" % \
            (stats.last, lvap.addr.to_str(), block.addr.to_str(), block.channel, \
             stats.rx_bytes_per_second[0], stats.tx_bytes_per_second[0])

        with open(filename, 'a') as file_d:
            file_d.write(line)

    @property
    def limit(self):
        """Return loop period."""

        return self.__limit

    @limit.setter
    def limit(self, value):
        """Set limit."""

        limit = int(value)

        if limit > 0 or limit < -100:
            raise ValueError("Invalid value for limit")

        self.log.info("Setting limit %u dB" % value)
        self.__limit = limit

    def low_rssi(self, trigger):
        """ Perform handover if an LVAP's rssi is
        going below the threshold. """

        self.log.info("Received trigger from %s rssi %u dB",
                      trigger.event['block'],
                      trigger.event['current'])

        lvap = self.lvap(trigger.lvap)

        if not lvap:
            return

        self.handover(lvap)

    def handover(self, lvap):
        """ Handover the LVAP to a WTP with
        an RSSI higher that -65dB. """

        self.log.info("Running handover...")

        # pool = self.blocks()

        # if not pool:
        #     return

        # new_block = max(pool, key=lambda x: x.ucqm[lvap.addr]['mov_rssi'])

        block = lvap.blocks[0]

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
            if self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] <= (current_rssi) or \
                self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] < best_rssi or self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] == 0:
                continue

            best_rssi = self.wifi_data[wtp + lvap.addr.to_str()]['rssi']
            new_block = self.get_block_for_ap_addr(wtp)

        if not new_block:
            return

        self.log.info("LVAP %s setting new block %s" % (lvap.addr, new_block))

        lvap.blocks = new_block

    def get_block_for_ap_addr(self, addr):
        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps
        for wtp in wtps.values():
            for block in wtp.supports:
                if block.addr.to_str() != addr:
                    continue
                return block

        return None

    def loop(self):
        """ Periodic job. """

        for lvap in self.lvaps():
            self.handover(lvap)


def launch(tenant_id, every=DEFAULT_PERIOD):
    """ Initialize the module. """

    return RssiLoadBalancing(tenant_id=tenant_id, every=every)
