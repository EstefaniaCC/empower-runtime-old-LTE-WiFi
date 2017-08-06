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

from empower.core.app import EmpowerApp
from empower.core.app import DEFAULT_PERIOD
from empower.datatypes.etheraddress import EtherAddress
from empower.core.resourcepool import ResourceBlock
from empower.main import RUNTIME
from empower.maps.ucqm import ucqm
from empower.maps.ucqm import UCQMWorker
from empower.events.wtpup import wtpup
from empower.events.lvapjoin import lvapjoin
from empower.core.resourcepool import BANDS


class NetworkColoring(EmpowerApp):

    def __init__(self, **kwargs):

        EmpowerApp.__init__(self, **kwargs)

        self.wifi_data = {}

        self.stations_channels_matrix = {}
        self.stations_aps_matrix = {}

        self.conflict_aps = {}
        self.aps_channels_matrix = {}
        self.channels_bg = []
        self.channels_an = [149, 153, 157, 161, 165]
        self.aps_clients_rel = {}

        self.channels = self.channels_bg + self.channels_an
        self.common_initial_channel = random.choice(self.channels)
        self.coloring_channels  = {149, 153, 157}

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

        return out


    def wtp_up_callback(self, wtp):
        """Called when a new WTP connects to the controller."""

        for block in wtp.supports:

            self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

            if block.addr.to_str() not in self.conflict_aps:
                self.conflict_aps[block.addr.to_str()] = []
            if block.addr.to_str() not in self.aps_clients_rel:
                self.aps_clients_rel[block.addr.to_str()] = []

            if block.addr.to_str() not in self.aps_channels_matrix:
                self.aps_channels_matrix[block.addr.to_str()] = block.channel

    def lvap_join_callback(self, lvap):
        """Called when an joins the network."""

        self.aps_clients_rel[lvap.default_block.addr.to_str()].append(lvap.addr.to_str())
        self.stations_aps_matrix[lvap.addr.to_str()] = []
        self.stations_aps_matrix[lvap.addr.to_str()].append(lvap.default_block.addr.to_str())


    def conflict_graph(self):

        initial_conflict_graph = self.conflict_aps

        for wtp_list in self.stations_aps_matrix.values():
            for wtp in wtp_list:
                for conflict_wtp in wtp_list:
                    if conflict_wtp != wtp and (conflict_wtp not in self.conflict_aps[wtp]):
                        self.conflict_aps[wtp].append(conflict_wtp)

        if initial_conflict_graph != self.conflict_aps:
            self.network_coloring()

    def delete_ucqm_worker(self, block):
        worker = RUNTIME.components[UCQMWorker.__module__]

        for module_id in list(worker.modules.keys()):
            ucqm_mod = worker.modules[module_id]
            if block == ucqm_mod.block:
                worker.remove_module(module_id)

    def update_block(self, block, channel):

        self.delete_ucqm_worker(block)
            
        block.channel = channel

        ucqm_mod = self.ucqm(block=block,
                        tenant_id=self.tenant.tenant_id,
                        every=self.every,
                        callback=self.ucqm_callback)

        if block.addr.to_str() in self.aps_clients_rel:
            for lvap in self.aps_clients_rel[block.addr.to_str()]:
                self.wifi_data[block.addr.to_str() + lvap]['channel'] = channel


    def transfer_block_data(self, src_block, dst_block, lvap):

        if lvap.addr.to_str() in self.aps_clients_rel[src_block.addr.to_str()]:
            self.aps_clients_rel[src_block.addr.to_str()].remove(lvap.addr.to_str())
        if lvap.addr.to_str() not in self.aps_clients_rel[dst_block.addr.to_str()]:
            self.aps_clients_rel[dst_block.addr.to_str()].append(lvap.addr.to_str())


    def network_coloring(self):

        network_graph = {}

        if not self.conflict_aps:
            conflict_aps["00:0D:B9:3E:05:44"] = ["00:0D:B9:3E:06:9C", "00:0D:B9:3E:D9:DC"]
            conflict_aps["00:0D:B9:3E:06:9C"] = ["00:0D:B9:3E:05:44", "00:0D:B9:3E:D9:DC"]
            conflict_aps["00:0D:B9:3E:D9:DC"] = ["00:0D:B9:3E:06:9C", "00:0D:B9:3E:05:44"]

        for ap, conflict_list in self.conflict_aps.items():
            network_graph[ap] = set(conflict_list)

        network_graph = {n:neigh for n,neigh in network_graph.items() if neigh}

        channel_assignment = self.solve_channel_assignment(network_graph, self.coloring_channels, dict(), 0)

        print("*******************")
        print("Channel assignment: ", channel_assignment)
        print("*******************")

        for ap, channel in channel_assignment.items():
            block = self.get_block_for_ap_addr(ap)
            self.switch_channel_in_block(block, channel)


    def find_best_candidate(self, graph, guesses):
        candidates_with_add_info = [
        (
        -len({guesses[neigh] for neigh in graph[n] if neigh     in guesses}), # channels that should not be assigned
        -len({neigh          for neigh in graph[n] if neigh not in guesses}), # nodes not colored yet
        n
        ) for n in graph if n not in guesses]
        candidates_with_add_info.sort()
        candidates = [n for _,_,n in candidates_with_add_info]
        if candidates:
            candidate = candidates[0]
            return candidate
        return None


    def solve_channel_assignment(self, graph, channels, guesses, depth):
        n = self.find_best_candidate(graph, guesses)
        if n is None:
            return guesses # Solution is found
        for c in channels - {guesses[neigh] for neigh in graph[n] if neigh in guesses}:
            guesses[n] = c
            indent = '  '*depth
            if self.solve_channel_assignment(graph, channels, guesses, depth+1):
                return guesses
            else:
                del guesses[n]
        return None


    def ucqm_callback(self, poller):
        """Called when a UCQM response is received from a WTP."""

        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for addr in poller.maps.values():
            # This means that this lvap is attached to a WTP in the network.
            if addr['addr'] in lvaps and lvaps[addr['addr']].wtp:

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
                                        'channel': poller.block.channel
                                    }

                # Conversion of the data structure to obtain the conflict APs
                if addr['addr'].to_str() not in self.stations_aps_matrix:
                    self.stations_aps_matrix[addr['addr'].to_str()] = []
                if poller.block.addr.to_str() not in self.stations_aps_matrix[addr['addr'].to_str()]:
                    self.stations_aps_matrix[addr['addr'].to_str()].append(poller.block.addr.to_str())

            elif poller.block.addr.to_str() + addr['addr'].to_str() in self.wifi_data:
                del self.wifi_data[poller.block.addr.to_str() + addr['addr'].to_str()]

        self.conflict_graph()

    def switch_channel_in_block(self, req_block, channel):

        if req_block.channel == channel:
            return

        wtps = RUNTIME.tenants[self.tenant.tenant_id].wtps
        lvaps = RUNTIME.tenants[self.tenant.tenant_id].lvaps

        for wtp in wtps.values():
            for block in wtp.supports:
                if block != req_block:
                    continue

                self.update_block(block, channel)

                for lvap in lvaps.values():
                    if lvap.default_block.addr != block.addr:
                        continue
                    lvap.scheduled_on = block

                if block.addr.to_str() not in self.aps_clients_rel:
                    self.aps_clients_rel[block.addr.to_str()] = []

                    for lvap in lvaps.values():
                        if lvap.default_block.addr != block.addr:
                            continue
                        self.aps_clients_rel[block.addr.to_str()].append(lvap.addr.to_str())

                for lvap in self.aps_clients_rel[block.addr.to_str()]:
                    self.wifi_data[block.addr.to_str() + lvap]['channel'] = channel

                return

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

        pass

def launch(tenant_id, period=500):
    """ Initialize the module. """

    return NetworkColoring(tenant_id=tenant_id, every=period)
