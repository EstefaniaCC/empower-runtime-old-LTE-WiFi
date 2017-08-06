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

        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)
        self.wtpdown(callback=self.wtp_down_callback)

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)
        self.lvapleave(callback=self.lvap_leave_callback)

        # self.channels_bg = [1, 6, 11]
        # self.channels_an = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 123, 136, 140]
        self.channels_bg = []
        #self.channels_an = [56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 140]
        #self.channels_an = [149, 153, 157, 161, 165]
        self.channels_an = [149, 153, 157]
        self.channels = self.channels_bg + self.channels_an

    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps
        new_channel = random.choice(self.channels)

        for block in wtp.supports:
            block.channel = new_channel

            self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every)


    def lvap_join_callback(self, lvap):
        """Called when an joins the network."""

        self.bin_counter(lvap=lvap.addr,
                 every=500,
                 callback=self.counters_callback)

    def counters_callback(self, stats):
        """ New stats available. """

        self.log.info("New counters received from %s" % stats.lvap)

        lvap = RUNTIME.lvaps[stats.lvap]
        block = lvap.default_block

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

    def counters_to_file(self, lvap, block, summary):
        """ New stats available. """

        # per block log
        filename = "rssiloadbalancing_%s_%s_%u_%s.csv" % (self.test, block.addr.to_str(),
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

        filename = "rssiloadbalancing_%s_link_%s.csv" % (self.test, link)

        line = "%f,%d,%d\n" % \
            (summary.last, summary.rx_bytes_per_second[0], summary.tx_bytes_per_second[0])

        with open(filename, 'a') as file_d:
            file_d.write(line)

    def handover(self, lvap):
        """ Handover the LVAP to a WTP with
        an RSSI higher that -65dB. """

        self.log.info("Running handover...")

        pool = self.blocks()
        matches = pool & lvap.supported

        if not matches:
            return

        valid = [block for block in matches
                 if block.ucqm[lvap.addr]['mov_rssi'] > lvap.default_block.ucqm[lvap.addr]['mov_rssi']]

        if not valid:
            return

        new_block = max(valid, key=lambda x: x.ucqm[lvap.addr]['mov_rssi'])
        self.log.info("LVAP %s setting new block %s" % (lvap.addr, new_block))

        lvap.scheduled_on = new_block


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

    def loop(self):
        """ Periodic job. """

        # Handover every active LVAP to
        # the best WTP

        if self.warm_up_phases > 0 and self.initial_setup:
            self.warm_up_phases -= 1
        elif self.warm_up_phases == 0 and self.initial_setup:
            #Message to the APs to change the channel
            self.initial_setup = False
            #self.set_random_channels()
        else:
            for lvap in self.lvaps():
                self.handover(lvap)


def launch(tenant_id, every=DEFAULT_PERIOD):
    """ Initialize the module. """

    return RssiLoadBalancing(tenant_id=tenant_id, every=every)
