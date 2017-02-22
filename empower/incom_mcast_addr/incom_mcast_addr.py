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
from empower.lvapp import PT_INCOM_MCAST_REQUEST
from empower.lvapp import INCOM_MCAST_REQUEST
from empower.lvapp import PT_INCOM_MCAST_RESPONSE
from empower.lvapp import INCOM_MCAST_RESPONSE



class IncomMcastAddr(ModuleTrigger):
    """incom_mcast_addr worker."""

    MODULE_NAME = "incom_mcast_addr"
    # REQUIRED = ['module_type', 'worker', 'tenant_id', 'block']

    def __init__(self):

        ModuleTrigger.__init__(self)

        # parameters
        self._mcast_addr = None
        self._wtp = None
        # self._block = None
        self._iface = None

    def __eq__(self, other):

        return super().__eq__(other) and \
            self.mcast_addr == other.mcast_addr and \
            self.wtp == other.wtp and self.iface == other.iface

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
    def mcast_addr(self, value):
        """Set the mcast Address."""

        self._mcast_addr = EtherAddress(value)

    @property
    def iface(self):
        """Return the iface."""

        return self._iface

    @iface.setter
    def iface(self, value):
        """Set the iface."""

        self._iface = value

    @property
    def wtp(self):
        return self._wtp

    @wtp.setter
    def wtp(self, value):
        self._wtp = EtherAddress(value)

    def to_dict(self):
        """ Return a JSON-serializable dictionary representing the Stats """

        out = super().to_dict()

        out['wtp'] = self.wtp
        #out['block'] = self.block
        out['mcast_addr'] = self.mcast_addr
        out['iface'] = self.iface

        return out

    def handle_response(self, request):
        """ Handle an INCOM_MCAST_REQUEST event.

        Args:
            wtp, an WTP object

        Returns:
            None
        """
        self.wtp = request.wtp
        self.mcast_addr = request.mcast_addr
        self.iface = request.iface
        #self.block = request.block
        self.handle_callback(self)


class IncomMcastAddrWorker(ModuleLVAPPEventWorker):
    """ Counter worker. """

    pass


def incom_mcast_addr(**kwargs):
    """Create a new module."""

    return RUNTIME.components[IncomMcastAddrWorker.__module__].add_module(**kwargs)


def app_incom_mcast_addr(self, **kwargs):
    """Create a new module (app version)."""

    kwargs['tenant_id'] = self.tenant.tenant_id
    return incom_mcast_addr(**kwargs)


setattr(EmpowerApp, IncomMcastAddr.MODULE_NAME, app_incom_mcast_addr)


def launch():
    """Initialize the module."""

    return IncomMcastAddrWorker(IncomMcastAddr, PT_INCOM_MCAST_REQUEST, PT_INCOM_MCAST_RESPONSE)
