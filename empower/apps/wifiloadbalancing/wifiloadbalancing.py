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

"""Ping-pong handover App."""
import random

from empower.core.app import EmpowerApp
from empower.core.app import DEFAULT_PERIOD
from empower.datatypes.etheraddress import EtherAddress
from empower.main import RUNTIME
from empower.maps.ucqm import ucqm
from empower.maps.ucqm import UCQMWorker
from empower.events.wtpup import wtpup
from empower.events.wtpdown import wtpdown
from empower.events.lvapjoin import lvapjoin
from empower.events.lvapleave import lvapleave
from empower.lvapp import CHANNEL_SWITCH_ANNOUNCEMENT_TO_LVAP
from empower.lvapp import PT_CHANNEL_SWITCH_ANNOUNCEMENT_TO_LVAP
from empower.lvapp import UPDATE_WTP_CHANNEL
from empower.lvapp import PT_UPDATE_WTP_CHANNEL
from empower.core.resourcepool import BANDS


GRAPH_TOP_BOTTOM_MARGIN = 40
GRAPH_LEFT_RIGHT_MARGIN = 40
GRAPH_MAX_WIDTH = 550 - GRAPH_LEFT_RIGHT_MARGIN
GRAPH_MAX_HEIGHT = 750 - GRAPH_TOP_BOTTOM_MARGIN
MIN_DISTANCE = 70
N_XY = 300

class WifiLoadBalancing(EmpowerApp):
    """Ping-pong handover App.

    Command Line Parameters:

        tenant_id: tenant id
        lvap: the lvap address (optinal, default 00:18:DE:CC:D3:40)
        wtps: comma separated list (optional, default 00:0D:B9:2F:56:58,
            00:0D:B9:2F:56:5C, 00:0D:B9:2F:56:64)
        every: loop period in ms (optional, default 5000ms)

    Example:

        ./empower-runtime.py apps.pingpong.pingpong \
            --tenant_id=52313ecb-9d00-4b7d-b873-b55d3d9ada26D
    """

    def __init__(self, **kwargs):

        EmpowerApp.__init__(self, **kwargs)
        self.idx = 0

        # Generating inital coordinates for the graph nodes
        self.coord = self.get_coordinates()

        self.wifi_data = {}
        self.bitrate_data = {}
        self.bitrate_data_active = {}
        
        self.graphData = {}

        self.total_tx_bytes_per_second = {}
        self.total_rx_bytes_per_second = {}
        self.nb_app = {}
        self.nb_app_active = {}

        self.network_tx_bytes = 0
        self.network_apps = 0
        self.active_aps = 0
        self.desiderable_average_traffic = 0

        self.stations_channels_matrix = {}
        self.stations_aps_matrix = {}

        self.distribution_needed = False
        self.initial_setup = True
        self.warm_up_phases = 10
        self.new_distribution = {}

        self.conflict_aps = {}
        self.aps_channels_matrix = {}
        self.channels_bg = [1, 6, 11]
        self.channels_an = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 123, 136, 140]
        self.aps_clients_rel = {}
        self.aps_occupation = {}

        self.links = {}
        self.addr = "ff:ff:ff:ff:ff:ff" 

        # Register an wtp up event
        self.wtpup(callback=self.wtp_up_callback)
        self.wtpdown(callback=self.wtp_down_callback)

        # Register an lvap join event
        self.lvapjoin(callback=self.lvap_join_callback)
        self.lvapleave(callback=self.lvap_leave_callback)

    def get_coordinates(self):

        rangeX = (GRAPH_LEFT_RIGHT_MARGIN, GRAPH_MAX_WIDTH)
        rangeY = (GRAPH_TOP_BOTTOM_MARGIN, GRAPH_MAX_HEIGHT)

        deltas = set()
        for x in range(-MIN_DISTANCE, MIN_DISTANCE + 1):
            for y in range(-MIN_DISTANCE, MIN_DISTANCE + 1):
                if (x * x) + (y * y) >= MIN_DISTANCE * MIN_DISTANCE:
                    deltas.add((x,y))

        randPoints = []
        excluded = set()
        count = 0
        while count < N_XY:
            x = random.randrange(*rangeX)
            y = random.randrange(*rangeY)

            if (x, y) in excluded:
                continue

            randPoints.append((x, y))
            count += 1

            excluded.update((x + dx, y + dy) for (dx, dy) in deltas)

        return randPoints

    def to_dict(self):
        """Return json-serializable representation of the object."""

        out = super().to_dict()
        # out['ucqm_resp'] = self.ucqm_resp
        out['wifi_data'] = self.wifi_data

        stations_aps_matrix = {str(k): v for k, v in self.stations_aps_matrix.items()}
        total_rx_bytes_per_second = {str(k): v for k, v in self.total_rx_bytes_per_second.items()}
        total_tx_bytes_per_second = {str(k): v for k, v in self.total_tx_bytes_per_second.items()}
        stations_channels_matrix = {str(k): v for k, v in self.stations_channels_matrix.items()}
        conflict_aps = {str(k): v for k, v in self.conflict_aps.items()}


        # out['stations_aps_matrix'] = stations_aps_matrix
        out['total_rx_bytes_per_second'] = total_rx_bytes_per_second
        out['total_tx_bytes_per_second'] = total_tx_bytes_per_second
        out['aps_clients_rel'] = self.aps_clients_rel
        out['graphData'] = self.graphData
        out['conflict_aps'] = self.conflict_aps
        out['stations_aps_matrix'] = self.stations_aps_matrix
        out['bitrate_data_active'] = self.bitrate_data_active
        out['links'] = self.links

        return out


    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""

        for block in wtp.supports:

            self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

            self.summary(addr=self.addr,
                         block=block,
                         period=1000,
                         callback=self.summary_callback)

            if block.addr.to_str() not in self.conflict_aps:
                self.conflict_aps[block.addr.to_str()] = []
            if block.addr.to_str() not in self.aps_clients_rel:
                self.aps_clients_rel[block.addr.to_str()] = []

            if block.addr.to_str() not in self.aps_channels_matrix:
                self.aps_channels_matrix[block.addr.to_str()] = block.channel

            if block.addr.to_str() not in self.bitrate_data_active:
                self.bitrate_data_active[block.addr.to_str()] = {}
            if block.addr.to_str() not in self.bitrate_data:
                self.bitrate_data[block.addr.to_str()] = {}

            if block.addr.to_str() not in self.total_tx_bytes_per_second:
                self.total_tx_bytes_per_second[block.addr.to_str()] = 0
            if block.addr.to_str() not in self.total_rx_bytes_per_second:
                self.total_rx_bytes_per_second[block.addr.to_str()] = 0

            if block.addr.to_str() not in self.nb_app:
                self.nb_app[block.addr.to_str()] = 0
            if block.addr.to_str() not in self.nb_app_active:
                self.nb_app_active[block.addr.to_str()] = 0

            if block.addr.to_str() not in self.aps_channels_matrix:
                self.aps_channels_matrix[block.addr.to_str()] = block.channel

        self.active_aps += 1

        

    def wtp_down_callback(self, wtp):
        """Called when a wtp connectdiss from the controller."""

        worker = RUNTIME.components[UCQMWorker.__module__]
        self.active_aps -= 1

        for block in wtp.supports:
            for module_id in list(worker.modules.keys()):
                ucqm_mod = worker.modules[module_id]
                if block != ucqm_mod.block:
                    continue
                worker.remove_module(module_id)

            if block.addr.to_str() in self.conflict_aps:
                del self.conflict_aps[block.addr.to_str()]

            for key, values in self.conflict_aps.items():
                if block.addr.to_str() in values:
                    values.remove(block.addr.to_str())
                    break

            if block.addr.to_str() in self.aps_channels_matrix:
                del self.aps_channels_matrix[block.addr.to_str()]

            if block.addr.to_str() in self.bitrate_data:
                del self.bitrate_data[block.addr.to_str()]
            if block.addr.to_str() in self.bitrate_data_active:
                del self.bitrate_data_active[block.addr.to_str()] 

            if block.addr.to_str() in self.total_tx_bytes_per_second:
                del self.total_tx_bytes_per_second[block.addr.to_str()]
            if block.addr.to_str() in self.total_rx_bytes_per_second:
                del self.total_rx_bytes_per_second[block.addr.to_str()]

            if block.addr.to_str() in self.nb_app:
                del self.nb_app[block.addr.to_str()]
            if block.addr.to_str() in self.nb_app_active:
                del self.nb_app_active[block.addr.to_str()]

            if block.addr.to_str() in self.aps_channels_matrix:
                del self.aps_channels_matrix[block.addr.to_str()]


    def lvap_join_callback(self, lvap):
        """Called when an joins the network."""

        self.bin_counter(lvap=lvap.addr,
                 every=500,
                 callback=self.counters_callback)

        lvap.lvap_stats(every=500, callback=self.lvap_stats_callback)

        self.aps_clients_rel[lvap.default_block.addr.to_str()].append(lvap.addr.to_str())

    def lvap_leave_callback(self, lvap):
        """Called when an LVAP disassociates from a tennant."""
        self.aps_clients_rel[lvap.default_block.addr.to_str()].remove(lvap.addr.to_str())

        #TODO. DELANTE THE COUNTERS FROM THE BITRATE DATA AND SIMILAR

        del self.bitrate_data[lvap.default_block.addr.to_str()][lvap.addr.to_str()]
        del self.bitrate_data_active[lvap.default_block.addr.to_str()][lvap.addr.to_str()]

    def lvap_stats_callback(self, counter):
        """ New stats available. """

        rates = (counter.to_dict())["rates"]
        if not rates or counter.lvap not in RUNTIME.lvaps:
            return

        highest_prob = 0
        highest_rate = 0
        lvap = RUNTIME.lvaps[counter.lvap]
        
        for key, entry in rates.items():  #key is the rate
            if (rates[key]["prob"] > highest_prob) or \
            (rates[key]["prob"] == highest_prob and int(float(key)) > highest_rate):
                highest_rate = int(float(key))
                highest_prob = rates[key]["prob"]

        self.wifi_data[lvap.default_block.addr.to_str() + lvap.addr.to_str()]['prob'] = highest_prob
        self.wifi_data[lvap.default_block.addr.to_str() + lvap.addr.to_str()]['rate'] = highest_rate

    def summary_callback(self, summary):
        """ New stats available. """

        self.log.info("New summary from %s addr %s frames %u", summary.block,
                      summary.addr, len(summary.frames))

        # per block log
        filename = "survey_%s_%u_%s.csv" % (summary.block.addr,
                                            summary.block.channel,
                                            BANDS[summary.block.band])

        for frame in summary.frames:

            line = "%u,%g,%s,%d,%u,%s,%s,%s,%s,%s\n" % \
                (frame['tsft'], frame['rate'], frame['rtype'], frame['rssi'],
                 frame['length'], frame['type'], frame['subtype'],
                 frame['ra'], frame['ta'], frame['seq'])

            with open(filename, 'a') as file_d:
                file_d.write(line)

        # per link log
        for frame in summary.frames:

            link = "%s_%s_%u_%s" % (frame['ta'], summary.block.addr,
                                    summary.block.channel,
                                    BANDS[summary.block.band])

            filename = "link_%s.csv" % link

            if link not in self.links:
                self.links[link] = {}

            if frame['rssi'] not in self.links[link]:
                self.links[link][frame['rssi']] = 0

            self.links[link][frame['rssi']] += 1

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
        block = lvap.default_block

        if (not stats.tx_bytes_per_second and not stats.rx_bytes_per_second) and \
            (block.addr.to_str() + stats.lvap.to_str() not in self.wifi_data):
            print("-----It's null")
            return

        if not stats.tx_bytes_per_second:
            stats.tx_bytes_per_second = []
            stats.tx_bytes_per_second.append(0)
        if not stats.rx_bytes_per_second:
            stats.rx_bytes_per_second = []
            stats.rx_bytes_per_second.append(0)

        if block.addr.to_str() + stats.lvap.to_str() in self.wifi_data:
            self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['tx_bytes_per_second'] = stats.tx_bytes_per_second[0]
            self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['rx_bytes_per_second'] = stats.rx_bytes_per_second[0]
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
                            'reesched_tries': 0,
                            'revert_tries': 0,
                            'prob': 0,
                            'rate': 0
                        }

        self.bitrate_data[block.addr.to_str()][stats.lvap.to_str()] = \
                                    {
                                        'tx_bytes_per_second': stats.tx_bytes_per_second[0],
                                        'rx_bytes_per_second': stats.rx_bytes_per_second[0]
                                    }
                            

        possible_revert_lvap = False
        possible_resched_lvap = False
        # Minimum voice bitrates:
        # https://books.google.it/books?id=ExeKR1iI8RgC&pg=PA88&lpg=PA88&dq=bandwidth+consumption+per+application+voice+video+background&source=bl&ots=1zUvCgqAhZ&sig=5kkM447M4t9ezbVDde3-D3oh2ww&hl=it&sa=X&ved=0ahUKEwiRuvOJv6vUAhWPDBoKHYd5AysQ6AEIWDAG#v=onepage&q=bandwidth%20consumption%20per%20application%20voice%20video%20background&f=false
        # https://www.voip-info.org/wiki/view/Bandwidth+consumption
        # G729A codec minimum bitrate 17K 17804
        if lvap.addr.to_str() in self.bitrate_data_active[block.addr.to_str()]:
            if stats.tx_bytes_per_second[0] >= 500:
                # This means the app was already active or it was not there
                self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] = stats.tx_bytes_per_second[0]
            else:
                # if self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] >= 500:
                self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] = 0

            if stats.rx_bytes_per_second[0] >= 500:
                # This means the app was already active or it was not there
                self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] = stats.rx_bytes_per_second[0]
            else:
                # if self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] >= 500:
                self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] = 0

            if (self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] >= 500) or \
                (self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] >= 500):
                self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['reesched_tries'] += 1

            if (self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] < 500) and \
                (self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] < 500):
                self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['reesched_tries'] = 0
                self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['revert_tries'] += 1
                
        else:
            if stats.tx_bytes_per_second[0] >= 500:
                self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()] = \
                                            {
                                                'tx_bytes_per_second': stats.tx_bytes_per_second[0],
                                                'rx_bytes_per_second': 0
                                            }
                self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['reesched_tries'] += 1
                                    
            if stats.rx_bytes_per_second[0] >= 500:
                self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()] = \
                                            {
                                                'tx_bytes_per_second': 0,
                                                'rx_bytes_per_second': stats.rx_bytes_per_second[0]
                                            }
                self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['reesched_tries'] += 1


            if (stats.rx_bytes_per_second[0] < 500) and (stats.tx_bytes_per_second[0] < 500):
                self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['revert_tries'] += 1


        print("------self.bitrate_data_active[block]", self.bitrate_data_active[block.addr.to_str()])

        if self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['revert_tries'] >= 5:
            if lvap.addr.to_str() in self.bitrate_data_active[block.addr.to_str()]:
                del self.bitrate_data_active[block.addr.to_str()][lvap.addr.to_str()]
            possible_revert_lvap = True
        elif self.wifi_data[block.addr.to_str() + stats.lvap.to_str()]['reesched_tries'] >= 5:
            possible_resched_lvap = True

        self.update_transmission_traffic(block)

        if not possible_revert_lvap and not possible_resched_lvap:
            print("NO SCHEDULING")
            return

        if self.nb_app_active[block.addr.to_str()] < 2 and possible_resched_lvap:
            print("NOT ENOUGH APPS")
            return

        self.evalute_lvap_scheduling(stats, possible_revert_lvap, possible_resched_lvap)


    def update_transmission_traffic(self, block):

        self.nb_app[block.addr.to_str()] = len(self.bitrate_data[block.addr.to_str()])
        self.nb_app_active[block.addr.to_str()] = len(self.bitrate_data_active[block.addr.to_str()])
        temp_total_tx_bytes_per_second = 0
        temp_total_rx_bytes_per_second = 0

        for sta in self.bitrate_data_active[block.addr.to_str()].values():
            temp_total_tx_bytes_per_second += sta['tx_bytes_per_second']
            temp_total_rx_bytes_per_second += sta['rx_bytes_per_second']


        self.total_tx_bytes_per_second[block.addr.to_str()] = temp_total_tx_bytes_per_second
        self.total_rx_bytes_per_second[block.addr.to_str()] = temp_total_rx_bytes_per_second


    def evalute_lvap_scheduling(self, stats, possible_revert_lvap, possible_resched_lvap):

        lvap = RUNTIME.lvaps[stats.lvap]
        block = lvap.default_block
        new_block = None
        self.calculate_average_traffic()

        print("------possible_revert_lvap", possible_revert_lvap)
        print("------possible_resched_lvap", possible_resched_lvap)
        print("------self.average_traffic_surrounding_aps(lvap)", self.average_traffic_surrounding_aps(lvap))
        print("------self.total_tx_bytes_per_second[block.addr.to_str()] ", self.total_tx_bytes_per_second[block.addr.to_str()] )
        print("------self.total_rx_bytes_per_second[block.addr.to_str()]", self.total_rx_bytes_per_second[block.addr.to_str()])
        print("------self.nb_app_active[block]", self.nb_app_active[block.addr.to_str()])

        ###### Transmission finished ######
        if possible_revert_lvap:
            print("++++++++COME BACK++++++++")
            current_rssi = self.wifi_data[block.addr.to_str() + lvap.addr.to_str()]['rssi']
            print("------current_rssi", current_rssi)

            self.wifi_data[block.addr.to_str() + lvap.addr.to_str()]['revert_tries'] = 0
            
            for wtp in self.stations_aps_matrix[lvap.addr.to_str()]:
                if wtp == block.addr.to_str():
                    continue
                print("rssi of %s: %d" %(wtp, self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] ))
                if self.wifi_data[wtp + lvap.addr.to_str()]['rssi'] <= current_rssi:
                    continue
                current_rssi = self.wifi_data[wtp + lvap.addr.to_str()]['rssi']
                new_block = self.get_block_for_ap_addr(wtp)

            if not new_block:
                return

            self.transfer_block_data(block, new_block, lvap)
            self.update_transmission_traffic(block)
            self.update_transmission_traffic(new_block)
            

            lvap.scheduled_on = new_block
            return


        ###### New Transmission or in case that the bitrate of the transmission increased ######
        if possible_resched_lvap:
            self.wifi_data[block.addr.to_str() + lvap.addr.to_str()]['reesched_tries'] = 0
            # It is not necessary to perform a change if the traffic of the ap is lower than the average or if it is holding a single lvap
            if block.addr.to_str() not in self.total_rx_bytes_per_second and block.addr.to_str() not in self.total_tx_bytes_per_second:
                print("NOTHING HERE")
                return

            average_traffic = self.average_traffic_surrounding_aps(lvap)
            if (self.total_tx_bytes_per_second[block.addr.to_str()] + self.total_rx_bytes_per_second[block.addr.to_str()]) <= average_traffic \
                or self.nb_app_active[block.addr.to_str()] < 2:
                print("NOT ENOUGH TRAFFIC")
                print("average traffic", average_traffic)
                print("self.total_tx_bytes_per_second[block.addr.to_str()] + self.total_rx_bytes_per_second[block.addr.to_str()]", (self.total_tx_bytes_per_second[block.addr.to_str()] + self.total_rx_bytes_per_second[block.addr.to_str()]))
                return

            # There are not other APs in the coverage area of this station
            if lvap.addr.to_str() not in self.stations_aps_matrix:
                return
            if len(self.stations_aps_matrix[lvap.addr.to_str()]) < 2: 
                return

            ########## Estimation of the channel occupancy of the candidate APs ###########
            less_busy_ap = block.addr.to_str()
            less_occupation = sys.maxsize
            for entry in self.stations_aps_matrix[lvap.addr.to_str()]:
                occupation = 0

                for sta in self.aps_clients_rel[entry]:
                    occupation += ((self.wifi_data[entry + sta]['tx_bytes_per_second'] \
                                    + self.wifi_data[entry + sta]['rx_bytes_per_second']) * 8 \
                                    / self.wifi_data[entry + sta]['rate']) / 1000000

                if occupation < less_occupation:
                    less_busy_ap = entry
                    less_occupation = occupation

                self.aps_occupation[entry] = occupation


            for entry in self.stations_aps_matrix[lvap.addr.to_str()]:
                if entry == block.addr.to_str():
                    continue

                if (self.total_tx_bytes_per_second[entry] + self.total_rx_bytes_per_second[entry]) > average_traffic:
                    print("TOO MUCH TRAFFIC IN THE CANDIDATE AP")
                    continue

                if lvap.addr.to_str() not in self.new_distribution:
                    self.new_distribution[lvap.addr.to_str()] = {
                        'source_wtp': block,
                        'dst_wtp': entry, 
                        'rssi':  self.wifi_data[entry + stats.lvap.to_str()]['rssi'],
                        'traffic': self.total_tx_bytes_per_second[entry] + self.total_rx_bytes_per_second[entry]
                    }
                elif (self.total_tx_bytes_per_second[entry] + self.total_rx_bytes_per_second[entry]) < self.new_distribution[lvap.addr.to_str()]['traffic']:
                    self.new_distribution[lvap.addr.to_str()] = {
                        'source_wtp': block,
                        'dst_wtp': entry, 
                        'rssi':  self.wifi_data[entry + stats.lvap.to_str()]['rssi'],
                        'traffic': self.total_tx_bytes_per_second[entry] + self.total_rx_bytes_per_second[entry]
                    }

            if lvap.addr.to_str() not in self.new_distribution:
                print("NO BETTER WTP")
                return

            print("PERFORMING HANDOVER")
            new_block = self.get_block_for_ap_addr(self.new_distribution[lvap.addr.to_str()]['dst_wtp'])
            del self.new_distribution[lvap.addr.to_str()]
        
            # Check if there are APs in the same channel
            channel_switch = False
            unavailable_channels = []
            self.conflict_graph()
            for ap in self.conflict_aps[new_block.addr.to_str()]:
                    if self.aps_channels_matrix[new_block.addr.to_str()] != self.aps_channels_matrix[ap] and \
                        self.nb_app_active[ap] >= 1:
                        unavailable_channels.append(self.aps_channels_matrix[ap])
                    else:
                        channel_switch = True

            print("---- current channel ", self.aps_channels_matrix[new_block.addr.to_str()])
            print("---- channel needed", channel_switch)
            
            # Calculate if it is needed a new channel change. 
            if channel_switch:

                new_channel = None
                first_band_list = None
                second_band_list = None
                # First it tries to mantain the same frequency band
                if new_block.channel in self.channels_bg:
                    first_band_list = self.channels_bg
                    second_band_list = self.channels_an
                else:
                    first_band_list = self.channels_an
                    second_band_list = self.channels_bg

                # First frequency band
                for entry in first_band_list:
                    if new_block.channel == entry:
                        continue
                    if entry in unavailable_channels:
                        continue
                    new_channel = entry
                    break

                print ("---- 1 try. new channel", new_channel)

                # If any available channel in the same frequency band, it checks the second one
                if not new_channel:
                    for entry in second_band_list:
                        if self.aps_channels_matrix[new_block.addr.to_str()] == entry:
                            continue
                        if entry in unavailable_channels:
                            continue
                        new_channel = entry
                        break
                    print ("---- 2 try. new channel", new_channel)

                # If all the channels are busy, it picks the one holding the lowest number of APs
                if not new_channel:
                    new_channel = min(self.stations_channels_matrix[lvap.addr.to_str()].keys(), key=(lambda k: stations_channels_matrix[lvap.addr.to_str()][k]))
                    print ("---- worst try. new channel", new_channel)

                self.switch_channel_in_block(new_block, new_channel)
            
                new_block.channel = new_channel

            self.transfer_block_data(block, new_block, lvap)
            self.update_transmission_traffic(block)
            self.update_transmission_traffic(new_block)

            print("++++++++ new block", new_block.addr.to_str())
            print("++++++++ new block info bitrate active", self.bitrate_data_active[new_block.addr.to_str()][lvap.addr.to_str()])
            print("++++++++ old block", block.addr.to_str())
            print("++++++++++++ self.nb_app[block.addr.to_str()]", self.nb_app[block.addr.to_str()])
            print("++++++++++++ self.nb_app[new_block.addr.to_str()]", self.nb_app[new_block.addr.to_str()])


            lvap.scheduled_on = new_block

            return

    def update_block(self, block, channel):

        worker = RUNTIME.components[UCQMWorker.__module__]

        for module_id in list(worker.modules.keys()):
            ucqm_mod = worker.modules[module_id]
            print("****************************************")
            print(ucqm_mod)
            if block == ucqm_mod.block:
                worker.remove_module(module_id)
            
        old_block_status = block
        block.channel = channel

        ucqm_mod = self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

        if old_block_status.addr.to_str() in self.aps_clients_rel:
            for lvap in self.aps_clients_rel[old_block_status.addr.to_str()]:
                self.wifi_data[block.addr.to_str() + lvap]['channel'] = channel

        self.aps_channels_matrix[block.addr.to_str()] = channel


    def transfer_block_data(self, src_block, dst_block, lvap):

        if lvap.addr.to_str() in self.aps_clients_rel[src_block.addr.to_str()]:
            self.aps_clients_rel[src_block.addr.to_str()].remove(lvap.addr.to_str())
        if lvap.addr.to_str() not in self.aps_clients_rel[dst_block.addr.to_str()]:
            self.aps_clients_rel[dst_block.addr.to_str()].append(lvap.addr.to_str())

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
        self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['tx_bytes_per_second'] = 0
        self.wifi_data[src_block.addr.to_str() + lvap.addr.to_str()]['rx_bytes_per_second'] = 0
        self.bitrate_data[src_block.addr.to_str()][lvap.addr.to_str()]['tx_bytes_per_second'] = 0
        self.bitrate_data[src_block.addr.to_str()][lvap.addr.to_str()]['rx_bytes_per_second'] = 0 


    def conflict_graph(self):

        for wtp_list in self.stations_aps_matrix.values():
            for wtp in wtp_list:
                for conflict_wtp in wtp_list:
                    if conflict_wtp != wtp and (conflict_wtp not in self.conflict_aps[wtp]):
                        self.conflict_aps[wtp].append(conflict_wtp)

        for wtp_list in self.stations_aps_matrix.values():
            for wtp in wtp_list:
                for conflict_wtp in wtp_list:
                    if conflict_wtp != wtp and (conflict_wtp not in self.conflict_aps[wtp]):
                        self.conflict_aps[wtp].append(conflict_wtp)


    def ucqm_callback(self, poller):
        """Called when a UCQM response is received from a WTP."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps
        self.ucqm_resp = poller

        for addr in poller.maps.values():

            # This means that this lvap is attached to a WTP in the network.
            if addr['addr'] in lvaps and lvaps[addr['addr']].wtp:
                active_flag = 1

                if (lvaps[addr['addr']].wtp.addr != poller.block.addr):
                    active_flag = 0
                elif ((lvaps[addr['addr']].wtp.addr == poller.block.addr  \
                    and (lvaps[addr['addr']].association_state == False))):
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
                                        'tx_bytes_per_second': None,
                                        'rx_bytes_per_second': None,
                                        'reesched_tries': 0,
                                        'revert_tries': 0,
                                        'prob': 0,
                                        'rate': 0
                                    }

                # Conversion of the data structure to obtain the conflict APs
                if addr['addr'].to_str() not in self.stations_aps_matrix:
                    self.stations_aps_matrix[addr['addr'].to_str()] = []
                if poller.block.addr.to_str() not in self.stations_aps_matrix[addr['addr'].to_str()]:
                    self.stations_aps_matrix[addr['addr'].to_str()].append(poller.block.addr.to_str())


                self.stations_channels_matrix[addr['addr'].to_str()] = {}

                if poller.block.channel not in self.stations_channels_matrix[addr['addr'].to_str()]:
                    self.stations_channels_matrix[addr['addr'].to_str()][poller.block.channel] = 1
                else:
                    number = self.stations_channels_matrix[addr['addr'].to_str()][poller.block.channel]
                    self.stations_channels_matrix[addr['addr'].to_str()][poller.block.channel] = number + 1


            elif poller.block.addr.to_str() + addr['addr'].to_str() in self.wifi_data:
                del self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]


    @property
    def wtp_addrs(self):
        """Return wtp_addrs."""

        return self.__wtp_addrs

    @wtp_addrs.setter
    def wtp_addrs(self, value):
        """Set wtp_addrs."""

        self.__wtp_addrs = [EtherAddress(x) for x in value.split(",")]

    @property
    def lvap_addr(self):
        """Return lvap_addr."""

        return self.__lvap_addr

    @lvap_addr.setter
    def lvap_addr(self, value):
        """Set lvap_addr."""
        self.__lvap_addr = EtherAddress(value)


    def revert_lvaps(self):
        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        initial_block = None
        for lvap in lvaps.values():
            if not initial_block:
                initial_block = lvap.default_block

            if lvap.default_block == initial_block:
                continue

            lvap.scheduled_on = initial_block

    def revert_channels(self):

        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps
        initial_channel = None
        for wtp in wtps.values():
            for block in wtp.supports:
                if not initial_channel:
                    initial_channel = block.channel
                    break

        if not initial_channel:
            return

        for wtp in wtps.values():
            for block in wtp.supports:
                if block.channel == initial_channel:
                    continue
                # If it holds any lvap... 
                self.announce_channel_switch_to_bss(block, initial_channel)
                block.radio.connection.send_channel_switch_request(initial_channel, block.hwaddr, block.channel, block.band)

                self.update_block(block, initial_channel)

                for lvap in self.aps_clients_rel[block.addr.to_str()]:
                    self.wifi_data[block.addr.to_str() + lvap]['channel'] = initial_channel


    def setup_channels(self):

        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps

        initial_channel = 40

        for wtp in wtps.values():
            for block in wtp.supports:
                if block.channel == initial_channel:
                    continue
                # If it holds any lvap... 
                self.announce_channel_switch_to_bss(block, initial_channel)
                block.radio.connection.send_channel_switch_request(initial_channel, block.hwaddr, block.channel, block.band)

                self.update_block(block, initial_channel)

                for lvap in self.aps_clients_rel[block.addr.to_str()]:
                    self.wifi_data[block.addr.to_str() + lvap]['channel'] = initial_channel


    def switch_channel_in_block(self, req_block, channel):

        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps

        for wtp in wtps.values():
            for block in wtp.supports:
                if block != req_block:
                    continue

                # If it holds any lvap... 
                self.announce_channel_switch_to_bss(block, channel)
                block.radio.connection.send_channel_switch_request(channel, block.hwaddr, block.channel, block.band)

                self.update_block(block, channel)

                for lvap in self.aps_clients_rel[block.addr.to_str()]:
                    self.wifi_data[block.addr.to_str() + lvap]['channel'] = channel

                return

    def announce_channel_switch_to_bss(self, block, new_channel):

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps
        holding_lvaps = False

        for lvap in lvaps.values():
            if lvap.default_block.hwaddr != block.hwaddr:
                continue
            req_mode = 1
            req_count = 10
            self.log.info("Sending channel switch request to LVAP %s from channel %d to %d..." %(lvap.addr, lvap.default_block.channel, new_channel))
            holding_lvaps = True
            lvap.default_block.radio.connection.send_channel_switch_announcement_to_lvap(lvap, new_channel, req_mode, req_count)

        return holding_lvaps

    def calculate_average_traffic(self):
        self.network_bytes = 0
        for block, value in self.total_tx_bytes_per_second.items():
            self.network_bytes += value

        for block, value in self.total_rx_bytes_per_second.items():
            self.network_bytes += value

        self.desiderable_average_traffic = self.network_bytes / self.active_aps

    def average_traffic_surrounding_aps(self, lvap):
        average_traffic_ps = 0

        for key, wtp in enumerate(self.stations_aps_matrix[lvap.addr.to_str()]):
            if wtp not in self.total_tx_bytes_per_second:
                continue
            average_traffic_ps += self.total_tx_bytes_per_second[wtp]
            print("TRAFFIC IN AVERAGE", self.total_tx_bytes_per_second[wtp])

        for key, wtp in enumerate(self.stations_aps_matrix[lvap.addr.to_str()]):
            if wtp not in self.total_rx_bytes_per_second:
                continue
            average_traffic_ps += self.total_rx_bytes_per_second[wtp]
            print("TRAFFIC IN AVERAGE", self.total_rx_bytes_per_second[wtp])
        print(len(self.stations_aps_matrix[lvap.addr.to_str()]))
        return (average_traffic_ps / len(self.stations_aps_matrix[lvap.addr.to_str()]))

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

        node_id = 0
        # Contains all links between cells and UEs
        graph_links = []
        # Contains all nodes in the graph
        graph_nodes = {}

        tenant = RUNTIME.tenants[self.tenant.tenant_id]

        # Populate existing WTPs and trigger UCQM for existing WTPs
        for wtp in self.tenant.wtps.values():
            if not wtp.connection:
                continue

            # Append the WTP's info
            graph_nodes['wtp' + wtp.addr.to_str()] =  \
                                            {
                                                'id': node_id,
                                                'node_id': wtp.addr.to_str(),
                                                'entity': 'wtp',
                                                'tooltip': 'MAC',
                                                'x': self.coord[node_id][0],
                                                'y': self.coord[node_id][1]
                                            }
            node_id += 1

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for sta in lvaps.values():
            # Append the LVAP's info
            graph_nodes['sta' + sta.addr.to_str()] =  \
                                        {
                                            'id': node_id,
                                            'node_id': sta.addr.to_str(),
                                            'entity': 'sta',
                                            'tooltip': 'MAC',
                                            'x': self.coord[node_id][0],
                                            'y': self.coord[node_id][1]
                                        }

            for k, v in self.wifi_data.items():
                # Check for links pertaining to each WIFI station
                if k.endswith(sta.addr.to_str()):

                    color = 'black'
                    width = 4

                    if v['active'] == 1:
                        width = 6
                        color = 'lightgreen'

                    # Add each link for a measured WTP
                    graph_links.append({
                                        'src': graph_nodes['wtp' + v['wtp']]['id'],
                                        'dst': node_id,
                                        'rssi': v['rssi'],
                                        'entity': 'wifi',
                                        'color': color,
                                        'width': width,
                                        'channel': v['channel'],
                                        'tx_bps': v['tx_bytes_per_second'],
                                        'rx_bps': v['rx_bytes_per_second']
                                       })

            node_id += 1

        self.graphData = {
                            'nodes': graph_nodes.values(),
                            'links': graph_links
                          }

        if self.warm_up_phases > 0 and self.initial_setup:
            self.warm_up_phases -= 1
        elif self.warm_up_phases == 0 and self.initial_setup:
            #Message to the APs to change the channel
            self.initial_setup = False
            self.revert_channels()
        # elif not self.initial_setup:
            
        #     print("TRAFFIC", self.desiderable_average_traffic)
        #     print("APPS", self.network_apps)
            # self.conflict_graph()


def launch(tenant_id, period=500):
    """ Initialize the module. """

    return WifiLoadBalancing(tenant_id=tenant_id, every=period)
