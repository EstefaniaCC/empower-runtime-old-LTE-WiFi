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

class IgmpReport(ModuleTrigger):
    """igmp_report worker."""

    MODULE_NAME = "igmp_report"

    def __init__(self):

        ModuleTrigger.__init__(self)

        # parameters
        self._mcast_addr = None
        self._wtp = None
        self.sta = None
        self.mcast_addr = None
        self.igmp_type = None


    def __eq__(self, other):

        return super().__eq__(other) and \
            self.mcast_addr == other.mcast_addr and \
            self.wtp == other.wtp and self.sta == other.sta and self.igmp_type == other.igmp_type

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
        out['mcast_addr'] = self.mcast_addr
        out['igmp_type'] = self.igmp_type

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
