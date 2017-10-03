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

"""Basic mobility manager."""

from empower.core.app import EmpowerApp
from empower.core.app import DEFAULT_PERIOD
from empower.main import RUNTIME
from empower.maps.ucqm import ucqm
from empower.events.wtpup import wtpup
from empower.events.wtpdown import wtpdown
from empower.datatypes.etheraddress import EtherAddress


DEFAULT_LIMIT = -20


class LoadBalancing(EmpowerApp):
    """Basic loadbalancing manager.

    Command Line Parameters:

        tenant_id: tenant id
        limit: handover limit in dBm (optional, default -80)
        every: loop period in ms (optional, default 5000ms)

    Example:

        ./empower-runtime.py apps.mobilitymanager.mobilitymanager \
            --tenant_id=52313ecb-9d00-4b7d-b873-b55d3d9ada26
    """

    def __init__(self, **kwargs):
        self.__limit = DEFAULT_LIMIT
        EmpowerApp.__init__(self, **kwargs)

        self.wifi_data = {}
        self.bitrate_data = {}
        self.ucqm_data = {}

        self.total_tx_bytes_per_second = {}
        self.total_rx_bytes_per_second = {}
        self.nb_app = {}
        self.quality_map = {}
        self.collision_ap = {}

        self.network_tx_bytes = 0
        self.network_apps = 0
        self.active_aps = 0
        self.desiderable_average_traffic = 0

        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)
        self.wtpdown(callback=self.wtp_down_callback)

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)

    def to_dict(self):
        """Return json-serializable representation of the object."""

        out = super().to_dict()
        # out['ucqm_resp'] = self.ucqm_resp
        out['wifi_data'] = self.wifi_data

        quality_map = {str(k): v for k, v in self.quality_map.items()}
        ucqm_data = {str(k): v for k, v in self.ucqm_data.items()}


        out['quality_map'] = quality_map
        out['ucqm_data'] = ucqm_data

        return out

    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""

        for block in wtp.supports:

            self.ucqm(block=block, 
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

            # self.busyness_trigger(value=10,
            #                       relation='GT',
            #                       block=block,
            #                       callback=self.high_occupancy)

        self.active_aps += 1

        self.check_aps_same_channel()

    def wtp_down_callback(self, wtp):
        """Called when a wtp connectdiss from the controller."""

        self.active_aps -= 1
        self.check_aps_same_channel()

    def lvap_join_callback(self, lvap):
        """Called when an joins the network."""

        self.rssi(lvap=lvap.addr,
                  value=self.limit,
                  relation='LT',
                  callback=self.low_rssi)

        self.bin_counter(lvap=lvap.addr,
                 callback=self.counters_callback)

    def counters_callback(self, stats):
        """ New stats available. """

        self.log.info("New counters received from %s" % stats.lvap)

        lvap = RUNTIME.lvaps[stats.lvap]
        block = lvap.wtp.addr

        if not stats.tx_bytes_per_second or not stats.rx_bytes_per_second:
            return

        self.bitrate_data[block] = \
                            {
                            stats.lvap: 
                                    {
                                        'tx_bytes_per_second': stats.tx_bytes_per_second[0],
                                        'rx_bytes_per_second': stats.rx_bytes_per_second[0]
                                    }
                            }

        self.nb_app[block] = len(self.bitrate_data[block])
        temp_total_tx_bytes_per_second = 0
        temp_total_rx_bytes_per_second = 0

        for sta in self.bitrate_data[block].values():
            temp_total_tx_bytes_per_second += sta['tx_bytes_per_second']
            temp_total_rx_bytes_per_second += sta['rx_bytes_per_second']


        self.total_tx_bytes_per_second[block] = temp_total_tx_bytes_per_second
        self.total_rx_bytes_per_second[block] = temp_total_rx_bytes_per_second
        

    def ucqm_callback(self, poller):
        """Called when a UCQM response is received from a WTP."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        self.ucqm_resp = poller

        for addr in poller.maps.values():

            # This means that this lvap is attached to a WTP in the network. 
            if addr['addr'] in lvaps and lvaps[addr['addr']].wtp:

                self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()] = \
                                    {
                                        'rssi': addr['mov_rssi'],
                                        'wtp': poller.block.addr.to_str(),
                                        'sta': addr['addr'].to_str(),
                                    }


                self.ucqm_data[addr['addr'].to_str()] = \
                                    {
                                        poller.block.addr.to_str(): \
                                                    {
                                                        'rssi': addr['mov_rssi']
                                                    }
                                    }

            elif poller.block.addr.to_str() + addr['addr'].to_str() in self.wifi_data:
                del self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]

        print("QUALITY MAP", self.quality_map)
        print("UCQM_DATA", self.ucqm_data)
        print("WIFI DATA", self.wifi_data)
            

    def high_occupancy(self, trigger):
        """Call when channel is too busy."""

        self.log.info("Block %s busyness %f" %
                      (trigger.block, trigger.event['current']))

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

    def handover(self, lvap):
        """ Handover the LVAP to a WTP with
        an RSSI higher that -65dB. """

        self.log.info("Running handover...")

        pool = self.blocks()
        matches = pool & lvap.supported

        # print("matches", matches)

        if not matches:
            return

        if not self.wifi_data:
            return

        print("AAAA")

        valid = [block for block in matches
                 if block.ucqm[lvap.addr]['mov_rssi'] >= self.limit]

        best_rssi = -120
        best_block = None
        current_key = lvap.default_block.addr.to_str() + lvap.addr.to_str()
        current_rssi = self.wifi_data[current_key]['rssi']
        # print("LIMIT", self.limit)


        for block in matches:
            key = block.addr.to_str() + lvap.addr.to_str()
            print(key)
            print(self.wifi_data)
            if key not in self.wifi_data:
                continue
            info = self.wifi_data[key]
            if (info['rssi'] > best_rssi and (current_rssi - info['rssi'] < self.limit)):
                best_rssi = info['rssi']
                best_block = block

        if not best_block:
            return

        print("BEST RSSI", best_rssi)
        print("BEST_BLOCK", best_block)

        # print("VALID:", valid)

        # if not valid:
        #     return

        default_block = lvap.default_block

        if default_block == best_block:
            print("Not better block")
            print("Continue attached to ", default_block)
        else:
            print("Better block found")
            print("It was in ", default_block)
            print("It is now in ", best_block)
            self.log.info("LVAP %s setting new block %s" % (lvap.addr, new_block))
            lvap.scheduled_on = new_block

        # Get the AP offering the highest signal quality
        #new_block = max(valid, key=lambda x: x.ucqm[lvap.addr]['mov_rssi'])

        # if default_block != new_block:
        #     # In case  the best AP is not the same, if they operates in different channels, a channel switch must be performed. 
        #     new_channel = new_block.channel
        #     old_channel = default_block.channel

        #     if new_channel != old_channel:
        #         # Mode: 0 = no requirements on the receiving STA, 1 = no further frames until the scheduled channel switch ---> 1?
        #         # Count: 0 indicates at any time after the beacon frame. 1 indicates the switch occurs immediately before the next TBTT. --> 1??
        #         req_mode = 1
        #         req_count = 1
        #         self.log.info("Sending channel switch request...")
        #         default_block.radio.connection.send_channel_switch_request(lvap, new_channel, req_mode, req_count)

        #self.log.info("LVAP %s setting new block %s" % (lvap.addr, new_block))
        #lvap.scheduled_on = new_block

    def channel_switch(self, wtp):
        if not wtp.connection or wtp.connection.stream.closed():
            return

        if wtp in self.wtps:
            return

        self.check_aps_same_channel()

        # req = Container(version=PT_VERSION,
        #                 type=PT_ADD_BUSYNESS,
        #                 length=29,
        #                 seq=wtp.seq,
        #                 module_id=self.module_id,
        #                 wtp=wtp.addr.to_raw(),
        #                 hwaddr=self.block.hwaddr.to_raw(),
        #                 channel=self.block.channel,
        #                 band=self.block.band,
        #                 relation=RELATIONS[self.relation],
        #                 value=int(self.value * 180),
        #                 period=self.period)

        # self.log.info("Sending %s request to %s (id=%u)",
        #               self.MODULE_NAME, wtp.addr, self.module_id)

        # self.wtps.append(wtp)

        # msg = ADD_BUSYNESS_TRIGGER.build(req)
        # wtp.connection.stream.write(msg)

    def announce_channel_switch_to_bss(self, block, new_channel):

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for lvap in lvaps.values():
            if lvap.downlink.hwaddr == block.hwaddr:
                req_mode = 1
                req_count = 1
                self.log.info("Sending channel switch request to LVAP %s from channel %d to %d..." %(lvap.addr, lvap.channel, new_channel))
                default_block.radio.connection.send_channel_switch_announcement_to_lvap(lvap, new_channel, req_mode, req_count)
                

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

    def loop(self):
        """ Periodic job. """

        # Handover every active LVAP to
        # the best WTP
        for lvap in self.lvaps():
            self.handover(lvap)

    def calculate_average_traffic(self):
        self.network_apps = 0
        self.network_tx_bytes = 0
        for block, value in self.total_tx_bytes_per_second.values():
            self.network_tx_bytes += value
            self.network_apps += self.nb_app[block]

        self.desiderable_average_traffic = self.network_tx_bytes / self.active_aps

    def check_transmission_same_ap (self):

        wrong_aps = {}
        for block, value in self.bitrate_data.values():
            if len(value) <= 1:
                continue
            temp_ap_data = 0
            for lvap, data in value.values():
                # Minimum voice bitrates:
                # https://books.google.it/books?id=ExeKR1iI8RgC&pg=PA88&lpg=PA88&dq=bandwidth+consumption+per+application+voice+video+background&source=bl&ots=1zUvCgqAhZ&sig=5kkM447M4t9ezbVDde3-D3oh2ww&hl=it&sa=X&ved=0ahUKEwiRuvOJv6vUAhWPDBoKHYd5AysQ6AEIWDAG#v=onepage&q=bandwidth%20consumption%20per%20application%20voice%20video%20background&f=false
                # https://www.voip-info.org/wiki/view/Bandwidth+consumption
                # G729A codec minimum bitrate 17K
                if data['rx_bytes_per_second'] <= 17804:
                    continue
                other_wtps = False if len(self.quality_map[lvap.addr]) <= 1 else True
                wrong_aps[block] = \
                        {
                            lvap: 
                                {
                                    'data': data['rx_bytes_per_second'],
                                    'other_wtps': other_wtps
                                }

                        }
                temp_ap_data += data['rx_bytes_per_second']
            if temp_ap_data <= self.desiderable_average_traffic:
                del wrong_aps[block]

        return wrong_aps

    def check_aps_same_channel(self):

        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps
        same_channel_aps = {}

        for wtp in wtps.values():
            for block in wtp.supports:
                if block.channel not in same_channel_aps:
                    same_channel_aps[block.channel] = []
                same_channel_aps[block.channel].append(wtp.addr)

        print(same_channel_aps)
        for key, value in same_channel_aps.items():
            if len(value) <= 1:
                continue
            self.collision_ap[key] = value


    def wonderful_heuristic(self):

        # LOOP. Bandwith calculation
        # RSSI change as a triger (for detecting movements)
        # What about the signal graph?

        # Look for the wonderful idea of how the hell calculating the bitrate
        # Per AP. global


        # Average network traffic and number of ongoing transmissions
        self.calculate_average_traffic()

        # Check if there are apps in the same collision domain
        aps_in_conflict = self.check_transmission_same_ap()

        # If a two aps are in the same channel (how collision domain?)
        # there must a change in the channel of all of them, and hence, in the lvaps already connected
        # TODO. What about the vaps?????
        # TODO. Need to provide the new channel. How to identify it? Need to look for some way to detect the channels
        # in use in the network. 
        #self.announce_channel_switch_to_bss



    @property
    def aps(self):
        """Return loop period."""
        return self.__aps

    @aps.setter
    def aps(self, aps_info):
        """Updates the rate according to the aps information received"""
        print("HOLAAAAAAAAAAAAAAAAA")
        print(aps_info)

        # {'wtps': {'B4:52:FE:09:F9:8F': {'channel': 6, 'rssi': -17}, '02:CA:FE:07:F3:1C': {'channel': 6, 'rssi': -18}}, 'addr': '00:24:d7:07:f3:1c'}


        station = EtherAddress(aps_info['addr'])

        if not aps_info or station not in RUNTIME.lvaps:
            return

        lvap = RUNTIME.lvaps[station]
        #stats = self.lvap_bssid_to_hwaddr(aps_info['wtps'])
        stats = aps_info['wtps']

        print("Stats", stats)

        for wtp, value in stats.values():
            if wtp not in self.tenant.vaps:
                continue
            if self.quality_map[lvap.addr][wtp]:
                if len(self.quality_map[lvap.addr][wtp]['rssi']) >= 5:
                    del self.quality_map[lvap.addr][wtp]['rssi'][0]
                if value['channel'] != quality_map[lvap.addr][wtp]['channel']:
                    self.quality_map[lvap.addr][wtp]['channel'] = value['channel']
            else:
                self.quality_map[lvap.addr][wtp] = \
                                {
                                    'channel': value['channel'],
                                    'rssi': []
                                }
            self.quality_map[lvap.addr][wtp]['rssi'].append(value['rssi'])


        print(self.quality_map)

    # def lvap_bssid_to_hwaddr(self, aps_info):

    #     aps_hwaddr_info = dict()

    #     for key, value in aps_info.items():
    #         hwaddr = None
    #         print("key", key)
    #         print(self.tenant.vaps)
    #         print(self.tenant.lvaps)
    #         if EtherAddress(key) not in self.tenant.vaps and EtherAddress(key) not in self.tenant.lvaps:
    #             print("not here")
    #             continue

    #         if EtherAddress(key) in self.tenant.vaps:
    #             hwaddr = self.tenant.vaps[EtherAddress(key)].block.radio
    #             print("prueba",hwaddr)
    #         elif EtherAddress(key) in self.tenant.lvaps:
    #             hwaddr = self.tenant.lvaps[EtherAddress(key)].block.radio
    #             print("prueba2",hwaddr)
    #         aps_hwaddr_info[hwaddr] = value

    #     return aps_hwaddr_info

   

def launch(tenant_id, limit=DEFAULT_LIMIT, every=DEFAULT_PERIOD):
    """ Initialize the module. """

    return LoadBalancing(tenant_id=tenant_id, limit=limit, every=every)
