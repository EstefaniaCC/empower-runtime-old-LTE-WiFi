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

"""EmPOWER Light Virtual Access Point (LVAP) class."""

from empower.core.resourcepool import ResourcePool
from empower.core.resourcepool import ResourceBlock
from empower.core.radioport import RadioPort
from empower.core.radioport import DownlinkPort
from empower.core.radioport import UplinkPort
from empower.core.virtualport import VirtualPortLvap
from empower.core.utils import generate_bssid
from empower.core.tenant import T_TYPE_SHARED
from empower.intentserver.intentserver import IntentServer

from empower.main import RUNTIME

import empower.logger
LOG = empower.logger.get_logger()


class LVAP(object):
    """ The EmPOWER Light Virtual Access Point

    One LVAP is created for every station probing the network (unless the MAC
    was blocked or if the MAC was not in the allowed list). An LVAP can be
    hosted by multiple WTPs. More preciselly an LVAP can be scheduled on one,
    and onyl one resource block on the downlink direction and on multiple
    resource blocks on the uplink direction. The downlink resource block is
    automatically also the default uplink resource block. The default uplink
    resource block is the resource block in charge of generating WiFi acks.
    Additional uplink resource blocks do not generate acks but can
    opportunistically receive and forward traffic. An unbound LVAP, i.e. an
    LVAP not hosted by any  WTP, is not admissible. The association between
    LVAP and ResourceBlock(s) is called Port and models the parameters of the
    link between WTP and LVAP. The Port abstraction is used to specify control
    policies at the WTP level. Example are the rate control algorithm which
    cannot be managed at the controller level due to timing constraints. Due
    to implementation constraints uplink ports CAN be define but are ignored.

    Handover can be performed by setting the wtp property of an lvap object to
    another wtp, e.g.:

      lvap.wtp = new_wtp

    where lvap is an instance of LVAP object and new_wtp is an instance of wtp
    object. The controller takes care of removing the lvap from the old wtp and
    spawing a new lvap on the target wtp. Stats are cleared on handovers. The
    new_wtp must support the same channel and band of the old wtp otherwise no
    handover is performed.

    An handover can also be perfomed by assigning a valid RasourcePool to an
    LVAP block property. First build the intersection and available
    resource pools

      pool = wtp.supports & lvap.supports
      lvap.block = pool

    This results in one resource block in the pool to be configured as
    downlink resource block (and thus also as default uplink resource block)
    while the others will be configured as uplink resource blocks.

    A short cut is also provided:

      lvap.scheduled_on = block

    The operation above will assign the default port policy to the LVAP.

    To change the port configuration the downlink resource block property must
    be used:

      port = lvap.downlink[block]
      port.tx_power = 20

    Where block is the ResourceBlock previously assigned. A new port
    configuration can be assigned in a single step with:

      lvap.downlink[block] = port

    where port is an instance of the RadioPort class.

    The last line will trigger a Port update message if the entry already
    exists. If the entry does not exists and there are no other entries in
    the structure, then a new entry will be created and an add LVAP massage
    will be sent before sending the port update message. If an entry is
    already available in the structure then a ValueError is raised.

    Applications can also manually delete resource blocks (this will trigger a
    del lvap message) and create new ones (this will trigger an add lvap
    message):

      del lvap.downlink[old_block]
      lvap.downlink[new_block] = port

    Attributes:
        addr: The client's MAC Address as an EtherAddress instance.
        tx_samples: array of 2-tuples of the TX'ed packets
        rx_samples: array of 2-tuples of the RX'ed packets
        net_bssid: The LVAP's MAC Address as an EtherAddress instance. This
          address is dynamically generated by the Access Controller.
          The BSSID is supposed to be unique in the entire network.
        lvap_bssid: The LVAP's active bssid as EtherAddress instance.
        ssids: The list of SSIDs to be broadcasted for this LVAP.
        assoc_id: association id for this LVAP (this cannot change
          after the LVAP has been spawned
        authentication_state: set to True if the LVAP has already completed
          the open authentication handshake .
        association_state: set to True if the LVAP has already completed
          the association handshake.
        ssid: The currently associated SSID.
        tx_samples: the transmitted packets
        rx_samples: the received packets
        block: the resource blocks to which this LVAP is assigned.
        downlink: the resource block assigned to this LVAP on the downlink
          direction.
        uplink: the resource block assigned to this LVAP on the uplink
          direction.
        scheduled_on: union of the downlink and uplink resource blocks
    """

    def __init__(self, addr, net_bssid_addr, lvap_bssid_addr):

        # read only params
        self.addr = addr
        self.net_bssid = net_bssid_addr

        # lvap bssid, this is the bssid to which the client is currently
        # attached, it can only be updated as a result of an auth request
        # message
        self._lvap_bssid = lvap_bssid_addr

        # the following parameters are only updated upon RX of a lvap status
        # update message from an agent
        self.authentication_state = False
        self.association_state = False

        # the following parameters are only updated by the controller, which
        # will then dispatch an add lvap message in order to propagate the
        # change to the agent
        self._ssids = []
        self._encap = None

        # the following parameters can be updated by both agent and
        # controller. The controller sets them when a client successfully
        # associate. The agent sets them upon disassociation.
        self._assoc_id = 0
        self._tenant = None

        # only one block supported, default block points to this
        self._downlink = DownlinkPort()

        # multiple blocks supported, no port configuration supported
        self._uplink = UplinkPort()

        # counters
        self.tx_samples = []
        self.rx_samples = []

        # virtual ports (VNFs)
        self.ports = {}

        # downlink intent uuid
        self.poa_uuid = None

        # supported resource blocks
        self.supported = ResourcePool()

        # this is set before clearing the DL blocks, so that the del_lvap
        # message can be filled with the target block information
        self.target_block = None

    def set_ports(self):
        """Set virtual ports.
        This method is called everytime an LVAP is moved to another WTP. More
        preciselly it is called every time an assignment to the downlink
        property is made.
        """

        # Delete all outgoing virtual links
        for port_id in self.ports:
            self.ports[port_id].clear()

        # set/update intent
        intent = {'version': '1.0',
                  'dpid': self.ports[0].dpid,
                  'port': self.ports[0].ovs_port_id,
                  'hwaddr': self.addr}

        intent_server = RUNTIME.components[IntentServer.__module__]

        if self.poa_uuid:
            intent_server.update_poa(intent, self.poa_uuid)
        else:
            self.poa_uuid = intent_server.add_poa(intent)

    def refresh_lvap(self):
        """Send add lvap message on the selected port."""

        for port in self.downlink.values():
            port.block.radio.connection.send_add_lvap(port.lvap, port.block,
                                                      self.downlink.SET_MASK)

        for port in self.uplink.values():
            port.block.radio.connection.send_add_lvap(port.lvap, port.block,
                                                      self.uplink.SET_MASK)

    @property
    def encap(self):
        """Get the encap."""

        return self._encap

    @encap.setter
    def encap(self, encap):
        """ Set the encap. """

        if self._encap == encap:
            return

        self._encap = encap
        self.refresh_lvap()

    @property
    def assoc_id(self):
        """Get the assoc_id."""

        return self._assoc_id

    @assoc_id.setter
    def assoc_id(self, assoc_id):
        """Set the assoc id."""

        if self._assoc_id == assoc_id:
            return

        self._assoc_id = assoc_id
        self.refresh_lvap()

    @property
    def lvap_bssid(self):
        """Get the lvap_bssid."""

        return self._lvap_bssid

    @lvap_bssid.setter
    def lvap_bssid(self, lvap_bssid):
        """Set the assoc id."""

        if self._lvap_bssid == lvap_bssid:
            return

        self._lvap_bssid = lvap_bssid
        self.refresh_lvap()

    @property
    def ssids(self):
        """Get the ssids assigned to this LVAP."""

        return self._ssids

    @ssids.setter
    def ssids(self, ssids):
        """Set the ssids assigned to this LVAP."""

        if self._ssids == ssids:
            return

        self._ssids = ssids
        self.refresh_lvap()

    def set_ssids(self, ssids):
        """Set the ssids assigned to this LVAP without seding messages."""

        self._ssids = ssids

    @property
    def ssid(self):
        """ Get the SSID assigned to this LVAP. """

        if not self._tenant:
            return None

        return self._tenant.tenant_name

    @property
    def tenant(self):
        """ Get the tenant assigned to this LVAP. """

        return self._tenant

    @tenant.setter
    def tenant(self, tenant):
        """ Set the SSID. """

        if self._tenant == tenant:
            return

        self._tenant = tenant
        self.refresh_lvap()

    @property
    def downlink(self):
        """ Get the resource blocks assigned to this LVAP in the downlink. """

        return self._downlink

    @downlink.setter
    def downlink(self, blocks):
        """Set downlink block.

        Set the downlink block. Must receive as input a single resource block.
        """

        if isinstance(blocks, ResourcePool):
            pool = blocks
        elif isinstance(blocks, ResourceBlock):
            pool = ResourcePool()
            pool.add(blocks)
        else:
            raise TypeError("Invalid type: %s", type(blocks))

        if len(pool) > 1:
            raise ValueError("Downlink, too many blocks (%u)", len(blocks))

        current = ResourcePool(list(self._downlink.keys()))

        # Null operation, just return, but before re-send intent configuration
        if current == pool:
            self.set_ports()
            return

        # downlink block
        downlink_block = pool.pop()

        # If LVAP is associated to a shared tenant, then reset LVAP
        if self._tenant and self._tenant.bssid_type == T_TYPE_SHARED:

            # check if tenant is available at target block
            base_bssid = self._tenant.get_prefix()
            net_bssid = generate_bssid(base_bssid, downlink_block.hwaddr)

            # if not ignore request
            if net_bssid not in self._tenant.vaps:
                LOG.error("VAP %s not found on tenant %s", net_bssid,
                          self._tenant.tenant_name)
                self.set_ports()
                return

            # otherwise reset lvap
            self._tenant = None
            self.association_state = False
            self.authentication_state = False
            self._assoc_id = 0
            self._lvap_bssid = net_bssid

        # clear uplink blocks
        for block in list(self._uplink.keys()):
            del self._uplink[block]

        # save target block
        self.target_block = downlink_block

        # clear downlink block
        if self.default_block:
            del self._downlink[self.default_block]

        # reset target block
        self.target_block = None

        # assign default port policy to downlink resource block, this will
        # trigger a send_add_lvap and a set_port (radio) message
        self._downlink[downlink_block] = RadioPort(self, downlink_block)

        # set ports
        self.set_ports()

    @property
    def uplink(self):
        """ Get the resource blocks assigned to this LVAP in the uplink. """

        return self._uplink

    @uplink.setter
    def uplink(self, blocks):
        """Set downlink block.

        Set the downlink block. Must receive as input a single resource block.
        """

        if isinstance(blocks, ResourcePool):
            pool = blocks
        elif isinstance(blocks, ResourceBlock):
            pool = ResourcePool()
            pool.add(blocks)
        else:
            raise TypeError("Invalid type: %s", type(blocks))

        if len(pool) > 5:
            raise ValueError("Downlink, too many blocks (%u)", len(blocks))

        current = ResourcePool(list(self._uplink.keys()))

        # Null operation, just return
        if current == pool:
            return

        # make sure we are not overwriting a downlink block
        downlink = ResourcePool(list(self._downlink.keys()))
        pool = pool - downlink

        # make sure if specified block is not at the same wtp of the current
        # downlink block, in this case remove it
        pool = pool - self.default_block.radio.supports

        # clear uplink blocks
        for block in list(self._uplink.keys()):
            del self._uplink[block]

        # assign uplink blocks
        for block in pool:
            self._uplink[block] = RadioPort(self, block)

    @property
    def scheduled_on(self):
        """ Get the resource blocks assigned to this LVAP in the uplink. """

        return ResourcePool(list(self._downlink.keys()) +
                            list(self._uplink.keys()))

    @scheduled_on.setter
    def scheduled_on(self, blocks):
        """Assign default resource block to LVAP.

        Assign default resource block to LVAP. Accepts as input either a
        ResourcePool or a ResourceBlock. If the resource pool has more than
        one resource block then one random resource block is assigned as both
        downlink and default uplink. The remaining resource blocks are
        assigned as uplink only.

        Args:
            downlink: A ResourcePool or a ResourceBlock
        """

        if not blocks:
            return

        if isinstance(blocks, ResourcePool):
            pool = blocks
        elif isinstance(blocks, ResourceBlock):
            pool = ResourcePool()
            pool.add(blocks)
        else:
            raise TypeError("Invalid type: %s", type(blocks))

        # set downlink block
        self.downlink = pool.pop()

        # set uplink blocks
        self.uplink = pool

    @property
    def default_block(self):
        """Return the default block on which this LVAP is scheduled on."""

        if not self.downlink:
            return None

        default_block = next(iter(self.downlink.keys()))
        return default_block

    @property
    def wtp(self):
        """Return the wtp on which this LVAP is scheduled on."""

        if not self.default_block:
            return None

        return self.default_block.radio

    @wtp.setter
    def wtp(self, wtp):
        """Assigns LVAP to new wtp."""

        matching = wtp.supports & self.supported
        self.scheduled_on = matching.pop() if matching else None

    def clear_downlink(self):
        """ Clear all downlink blocks."""

        # remove downlink
        for block in list(self._downlink.keys()):
            del self._downlink[block]

        # remove intent
        if self.poa_uuid:
            intent_server = RUNTIME.components[IntentServer.__module__]
            intent_server.remove_poa(self.poa_uuid)

    def clear_uplink(self):
        """ Clear all downlink blocks."""

        for block in list(self._uplink.keys()):
            del self._uplink[block]

    def to_dict(self):
        """ Return a JSON-serializable dictionary representing the LVAP """

        return {'addr': self.addr,
                'net_bssid': self.net_bssid,
                'lvap_bssid': self.lvap_bssid,
                'ports': self.ports,
                'wtp': self.wtp,
                'scheduled_on': self.scheduled_on,
                'downlink': [k for k in self._downlink.keys()],
                'uplink': [k for k in self._uplink.keys()],
                'supported': self.supported,
                'ssids': self.ssids,
                'assoc_id': self.assoc_id,
                'ssid': self.ssid,
                'encap': self.encap,
                'tx_samples': self.tx_samples,
                'rx_samples': self.rx_samples,
                'authentication_state': self.authentication_state,
                'association_state': self.association_state}

    def __str__(self):

        accum = []
        accum.append("addr ")
        accum.append(str(self.addr))
        accum.append(" net_bssid ")
        accum.append(str(self.net_bssid))
        accum.append(" lvap_bssid ")
        accum.append(str(self.lvap_bssid))
        accum.append(" ssid ")
        accum.append(str(self.ssid))

        if self.ssids:

            accum.append(" ssids [ ")
            accum.append(str(self.ssids[0]))

            for ssid in self.ssids[1:]:
                accum.append(", ")
                accum.append(str(ssid))

            accum.append(" ]")

        accum.append(" assoc_id ")
        accum.append(str(self.assoc_id))

        if self.association_state:
            accum.append(" ASSOC")

        if self.authentication_state:
            accum.append(" AUTH")

        return ''.join(accum)

    def __hash__(self):
        return hash(self.addr)

    def __eq__(self, other):
        if isinstance(other, LVAP):
            return self.addr == other.addr
        return False

    def __ne__(self, other):
        return not self.__eq__(other)
