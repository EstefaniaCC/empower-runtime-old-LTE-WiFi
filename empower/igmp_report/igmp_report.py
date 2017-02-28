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

from construct import UBInt8
from construct import UBInt32
from construct import Bytes
from construct import Container
from construct import Struct
from construct import Array

from empower.core.resourcepool import ResourceBlock
from empower.core.resourcepool import ResourcePool
from empower.core.app import EmpowerApp
from empower.core.module import ModuleTrigger
from empower.datatypes.etheraddress import EtherAddress
from empower.lvapp.lvappserver import ModuleLVAPPWorker
from empower.lvapp.lvappserver import ModuleLVAPPEventWorker
from empower.core.module import Module
from empower.main import RUNTIME
from empower.lvapp import PT_VERSION
from empower.lvapp import PT_IGMP_REPORT
from empower.lvapp import IGMP_REPORT

from empower.core.utils import ip_bytes_to_str
from empower.core.utils import multicast_ip_to_ether

import ipaddress


V3_MODE_IS_INCLUDE = 0x0
V3_MODE_IS_EXCLUDE = 0x1
V3_CHANGE_TO_INCLUDE_MODE = 0x2
V3_CHANGE_TO_EXCLUDE_MODE = 0x3
V3_ALLOW_NEW_SOURCES = 0x4
V3_BLOCK_OLD_SOURCES = 0x5
V2_JOIN_GROUP = 0x6
V2_LEAVE_GROUP = 0x7
V1_MEMBERSHIP_REPORT = 0x8
V1_V2_MEMBERSHIP_QUERY = 0x9

V3_MODE_IS_INCLUDE_H = 'v3 include'
V3_MODE_IS_EXCLUDE_H = 'v3 exclude'
V3_CHANGE_TO_INCLUDE_MODE_H = 'v3 change to include'
V3_CHANGE_TO_EXCLUDE_MODE_H = 'v3 change to exclude'
V3_ALLOW_NEW_SOURCES_H = 'v3 allow new sources'
V3_BLOCK_OLD_SOURCES_H = 'v3 block old sources'
V2_JOIN_GROUP_H = 'v2 join group'
V2_LEAVE_GROUP_H = 'v2 leave group'
V1_MEMBERSHIP_REPORT_H = 'v1 report'
V1_V2_MEMBERSHIP_QUERY_H = 'v1 v2 query'


IGMP_TYPES = {V3_MODE_IS_INCLUDE: V3_MODE_IS_INCLUDE_H,
            V3_MODE_IS_EXCLUDE: V3_MODE_IS_EXCLUDE_H,
            V3_CHANGE_TO_INCLUDE_MODE: V3_CHANGE_TO_INCLUDE_MODE_H,
            V3_CHANGE_TO_EXCLUDE_MODE: V3_CHANGE_TO_EXCLUDE_MODE_H,
            V3_ALLOW_NEW_SOURCES: V3_ALLOW_NEW_SOURCES_H,
            V3_BLOCK_OLD_SOURCES: V3_BLOCK_OLD_SOURCES_H,
            V2_JOIN_GROUP: V2_JOIN_GROUP_H,
            V2_LEAVE_GROUP: V2_LEAVE_GROUP_H,
            V1_MEMBERSHIP_REPORT: V1_MEMBERSHIP_REPORT_H,
            V1_V2_MEMBERSHIP_QUERY: V1_V2_MEMBERSHIP_QUERY_H}

REVERSE_IGMP_TYPES = {V3_MODE_IS_INCLUDE_H: V3_MODE_IS_INCLUDE,
            V3_MODE_IS_EXCLUDE_H: V3_MODE_IS_EXCLUDE,
            V3_CHANGE_TO_INCLUDE_MODE_H: V3_CHANGE_TO_INCLUDE_MODE,
            V3_CHANGE_TO_EXCLUDE_MODE_H: V3_CHANGE_TO_EXCLUDE_MODE,
            V3_ALLOW_NEW_SOURCES_H: V3_ALLOW_NEW_SOURCES,
            V3_BLOCK_OLD_SOURCES_H: V3_BLOCK_OLD_SOURCES,
            V2_JOIN_GROUP_H: V2_JOIN_GROUP,
            V2_LEAVE_GROUP_H: V2_LEAVE_GROUP,
            V1_MEMBERSHIP_REPORT_H: V1_MEMBERSHIP_REPORT,
            V1_V2_MEMBERSHIP_QUERY_H: V1_V2_MEMBERSHIP_QUERY}


class IgmpReport(ModuleTrigger):
    """igmp_report worker."""

    MODULE_NAME = "igmp_report"
    # REQUIRED = ['module_type', 'worker', 'tenant_id', 'block']

    def __init__(self):

        ModuleTrigger.__init__(self)

        # parameters
        self._mcast_addr = None
        self._wtp = None
        # self._block = None
        #self._iface = None
        self.sta = None
        self.mcast_addr = None
        self.igmp_type = None


    def __eq__(self, other):

        return super().__eq__(other) and \
            self.mcast_addr == other.mcast_addr and \
            self.wtp == other.wtp and self.sta == other.sta and self.igmp_type == other.igmp_type
            #and self.iface == other.iface

    # @property
    # def block(self):
    #     """Return block."""

    #     return self._block

    # @block.setter
    # def block(self, value):
    #     """Set block."""

    #     if isinstance(value, ResourceBlock):

    #         self._block = value

    #     elif isinstance(value, dict):

    #         if 'hwaddr' not in value:
    #             raise ValueError("Missing field: hwaddr")

    #         if 'channel' not in value:
    #             raise ValueError("Missing field: channel")

    #         if 'band' not in value:
    #             raise ValueError("Missing field: band")

    #         if 'wtp' not in value:
    #             raise ValueError("Missing field: wtp")

    #         wtp = RUNTIME.wtps[EtherAddress(value['wtp'])]

    #         incoming = ResourcePool()
    #         block = ResourceBlock(wtp, EtherAddress(value['hwaddr']),
    #                               int(value['channel']), int(value['band']))
    #         incoming.add(block)

    #         match = wtp.supports & incoming

    #         if not match:
    #             raise ValueError("No block specified")

    #         if len(match) > 1:
    #             raise ValueError("More than one block specified")

    #         self._block = match.pop()

    @property
    def mcast_addr(self):
        """Return the mcast Address."""

        return self._mcast_addr

    @mcast_addr.setter
    def mcast_addr(self, addr):
        """Set the mcast Address."""
        ip_addr = None
        if isinstance(addr, bytes) and len(addr) == 4:
            ip_addr = ipaddress.ip_address(ip_bytes_to_str(addr))
        elif isinstance(addr, str):
            ip_addr = ipaddress.ip_address(addr)
        mac_addr = multicast_ip_to_ether(ip_addr)

        self._mcast_addr = mac_addr


    # @property
    # def iface(self):
    #     """Return the iface."""

    #     return self._iface

    # @iface.setter
    # def iface(self, value):
    #     """Set the iface."""

    #     self._iface = value

    @property
    def wtp(self):
        return self._wtp

    @wtp.setter
    def wtp(self, value):
        self._wtp = EtherAddress(value)

    @property
    def sta(self):
        return self._sta

    @sta.setter
    def sta(self, value):
        self._sta = EtherAddress(value)

    @property
    def igmp_type(self):
        """Return the igmp_type."""

        return self._igmp_type

    @igmp_type.setter
    def igmp_type(self, value):
        """Set the iface."""

        self._igmp_type = value

    def to_dict(self):
        """ Return a JSON-serializable dictionary representing the Stats """

        out = super().to_dict()

        out['wtp'] = self.wtp
        out['sta'] = self.sta
        #out['block'] = self.block
        out['mcast_addr'] = self.mcast_addr
        out['igmp_type'] = self.igmp_type
        #out['iface'] = self.iface

        return out

    def handle_response(self, request):
        """ Handle an INCOM_MCAST_REQUEST event.

        Args:
            wtp, an WTP object

        Returns:
            None
        """
        self.wtp = request.wtp
        self.sta = request.sta
        self.mcast_addr = request.mcast_addr
        self.igmp_type = request.igmp_type
        #self.iface = request.iface
        #self.block = request.block
        self.handle_callback(self)


class IgmpReportWorker(ModuleLVAPPEventWorker):
    """ Counter worker. """

    pass


def igmp_report(**kwargs):
    """Create a new module."""

    return RUNTIME.components[IgmpReportWorker.__module__].add_module(**kwargs)


def app_igmp_report(self, **kwargs):
    """Create a new module (app version)."""

    kwargs['tenant_id'] = self.tenant.tenant_id
    return igmp_report(**kwargs)


setattr(EmpowerApp, IgmpReport.MODULE_NAME, app_igmp_report)


def launch():
    """Initialize the module."""

    return IgmpReportWorker(IgmpReport, PT_IGMP_REPORT)
