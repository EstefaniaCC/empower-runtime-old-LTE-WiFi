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

"""Virtual port."""


from empower.datatypes.etheraddress import EtherAddress
from empower.core.intent import add_intent
from empower.core.intent import del_intent
from empower.core.intent import key_to_match
from empower.core.intent import match_to_key


class VirtualPort(object):
    """Virtual port."""

    def __init__(self, dpid, ovs_port_id, virtual_port_id, hwaddr, iface):

        self.dpid = dpid
        self.ovs_port_id = ovs_port_id
        self.virtual_port_id = virtual_port_id
        self.hwaddr = hwaddr
        self.iface = iface

    def to_dict(self):
        """ Return a JSON-serializable dictionary representing the Port """

        return {'dpid': self.dpid,
                'ovs_port_id': self.ovs_port_id,
                'virtual_port_id': self.virtual_port_id,
                'hwaddr': self.hwaddr,
                'iface': self.iface}

    def __hash__(self):

        return hash(self.dpid) + hash(self.ovs_port_id) + \
            hash(self.virtual_port_id)

    def __eq__(self, other):

        return (other.dpid == self.dpid and
                other.ovs_port_id == self.ovs_port_id and
                other.virtual_port_id == self.virtual_port_id)

    def __repr__(self):

        out_string = "%s ovs_port %s virtual_port %s hwaddr %s iface %s"

        out = out_string % (self.dpid, self.ovs_port_id, self.virtual_port_id,
                            self.hwaddr, self.iface)

        return out


class VirtualPortLvap(VirtualPort):
    """ Virtual port associated to an LVAP."""

    def __init__(self, dpid, ovs_port_id, virtual_port_id, hwaddr, iface):

        self.dpid = dpid
        self.ovs_port_id = ovs_port_id
        self.virtual_port_id = virtual_port_id
        self.hwaddr = hwaddr
        self.iface = iface
        self.next = VirtualPortPropLvap()


class VirtualPortLvnf(VirtualPort):
    """ Virtual port associated to an LVAP."""

    def __init__(self, dpid, ovs_port_id, virtual_port_id, hwaddr, iface):

        self.dpid = dpid
        self.ovs_port_id = ovs_port_id
        self.virtual_port_id = virtual_port_id
        self.hwaddr = hwaddr
        self.iface = iface
        self.next = VirtualPortPropLvnf()


class VirtualPortProp(dict):
    """VirtualPortProp class.

    This maps Flows to VirtualPorts. Notice that the current implementation
    only supports chaining of LVAPs with other LVNFs. Chaining of two LVNFs is
    not implemented yet.
    """

    def __init__(self):
        super(VirtualPortProp, self).__init__()
        self.__uuids__ = {}

    def __delitem__(self, key):
        """Clear virtual port configuration.

        Remove entry from dictionary and remove flows.
        """

        if not isinstance(key, dict):
            raise KeyError("Expected dict, got %s" % type(key))

        match = key_to_match(key)

        # remove virtual links
        if match in self.__uuids__:
            del_intent(self.__uuids__[match])
            del self.__uuids__[match]

        # remove old entry
        dict.__delitem__(self, match)

    @property
    def uuids(self):
        """Return list of uuids."""

        return self.__uuids__

    def __getitem__(self, key):
        """Return next virtual port.

        Accepts as an input a dictionary with the openflow match rule for
        the virtual port. Example:

        key = {"dl_src": "aa:bb:cc:dd:ee:ff"}
        """

        if not isinstance(key, dict):
            raise KeyError("Expected dict, got %s" % type(key))

        match = key_to_match(key)
        return dict.__getitem__(self, match)

    def __contains__(self, key):
        """Check if entry exists.

        Accepts as an input a dictionary with the openflow match rule for
        the virtual port. Example:

        key = {"dl_src": "aa:bb:cc:dd:ee:ff"}
        """

        if not isinstance(key, dict):
            raise KeyError("Expected dict, got %s" % type(key))

        match = key_to_match(key)

        return dict.__contains__(self, match)


class VirtualPortPropLvap(VirtualPortProp):
    """VirtualPortProp class for LVAPs."""

    def __init__(self):
        super(VirtualPortPropLvap, self).__init__()
        self.lvap = None

    def __setitem__(self, key, value):
        """Set virtual port configuration.

        Accepts as an input a dictionary with the openflow match rule for
        the virtual port specified as value. Notice value could also be None
        in case the chain consists just in an LVAP. Example:

        key = {"dl_src": "aa:bb:cc:dd:ee:ff"}
        """

        if not isinstance(key, dict):
            raise KeyError("Expected dict, got %s" % type(key))

        if value and not isinstance(value, VirtualPort):
            raise KeyError("Expected VirtualPort, got %s" % type(key))

        # if this is a virtual link definition then clear all the virtual
        # port. this is because in this case there could be the default
        # virtual port inserted by the handover procedure.
        if value:
            for match in list(self.keys()):
                key = match_to_key(match)
                self.__delitem__(key)

        # if encap is set, then all outgoing traffic must go to THE SAME
        # LVNF. This is because the outgoing traffic will be LWAPP
        # encapsulated and as such cannot be handled anyway by OF
        # switches. Ignore totally the specified key and silently use as
        # key the LWAPP src and dst addresses. Notice that this will send
        # as many intents as the number of blocks.
        if self.lvap.encap != EtherAddress("00:00:00:00:00:00"):

            # Set downlink and uplink virtual link(s)

            # r_port is a RadioPort object
            for r_port in self.lvap.downlink.values():

                # n_port is a NetworkPort object
                for n_port in r_port.block.radio.ports.values():

                    if n_port.iface != "empower0":
                        continue

                    # ignore input key
                    key = {}
                    key['dpid'] = n_port.dpid
                    key['port_id'] = n_port.port_id

                    if value:
                        key['dl_src'] = self.lvap.addr
                        key['dl_dst'] = value.hwaddr

                    match = key_to_match(key)

                    intent = {'version': '1.0',
                              'src_dpid': n_port.dpid,
                              'src_port': n_port.port_id,
                              'hwaddr': self.lvap.addr,
                              'match': match}

                    if value:
                        intent['dst_dpid'] = value.dpid
                        intent['dst_port'] = value.ovs_port_id

                    # remove virtual link
                    if self.__contains__(key):
                        self.__delitem__(key)

                    # add new virtual link
                    uuid = add_intent(intent)
                    self.__uuids__[match] = uuid

                    dict.__setitem__(self, match, value)

                    break

            # if this is not a new virtual link definition then ignore uplink
            # port. This is because the old configuration is anyway deleted by
            # the corresponding LVAP object.
            if not value:
                return

            for r_port in self.lvap.uplink.values():

                # n_port is a NetworkPort object
                for n_port in r_port.block.radio.ports.values():

                    if n_port.iface != "empower0":
                        continue

                    # ignore input key
                    key = {}
                    key['dpid'] = n_port.dpid
                    key['port_id'] = n_port.port_id
                    key['dl_src'] = self.lvap.addr
                    key['dl_dst'] = value.hwaddr

                    match = key_to_match(key)

                    intent = {'version': '1.0',
                              'src_dpid': n_port.dpid,
                              'src_port': n_port.port_id,
                              'match': match}

                    intent['dst_dpid'] = value.dpid
                    intent['dst_port'] = value.ovs_port_id

                    # remove virtual link
                    if self.__contains__(key):
                        self.__delitem__(key)

                    # add new virtual link
                    uuid = add_intent(intent)
                    self.__uuids__[match] = uuid

                    dict.__setitem__(self, match, value)

                    break

        # encap is not set, then all outgoing traffic can go to different
        # LVNFs as specified by key. Remove the key only if it already exists.
        else:

            # Set downlink and uplink virtual link(s)

            # r_port is a RadioPort object
            for r_port in self.lvap.downlink.values():

                # n_port is a NetworkPort object
                for n_port in r_port.block.radio.ports.values():

                    if n_port.iface != "empower0":
                        continue

                    # add dummy fields
                    key['dpid'] = n_port.dpid
                    key['port_id'] = n_port.port_id

                    # make sure that dl_src is specified, but only if I am
                    # defining a new virtual link. In case of handover the
                    # dl_src match shall not be specified
                    if value:
                        key['dl_src'] = self.lvap.addr

                    match = key_to_match(key)

                    intent = {'version': '1.0',
                              'src_dpid': n_port.dpid,
                              'src_port': n_port.port_id,
                              'hwaddr': self.lvap.addr,
                              'match': match}

                    if value:
                        intent['dst_dpid'] = value.dpid
                        intent['dst_port'] = value.ovs_port_id

                    # remove virtual link
                    if self.__contains__(key):
                        self.__delitem__(key)

                    # add new virtual link
                    uuid = add_intent(intent)
                    self.__uuids__[match] = uuid

                    dict.__setitem__(self, match, value)

                    break

            # if this is not a new virtual link definition then ignore uplink
            # port. This is because the old configuration is anyway deleted by
            # the corresponding LVAP object.
            if not value:
                return

            # r_port is a RadioPort object
            for r_port in self.lvap.uplink.values():

                # n_port is a NetworkPort object
                for n_port in r_port.block.radio.ports.values():

                    if n_port.iface != "empower0":
                        continue

                    # add dummy fields
                    key['dpid'] = n_port.dpid
                    key['port_id'] = n_port.port_id

                    # make sure that dl_src is specified, but only if I am
                    # defining a new virtual link. In case of handover the
                    # dl_src match shall not be specified
                    key['dl_src'] = self.lvap.addr

                    match = key_to_match(key)

                    intent = {'version': '1.0',
                              'src_dpid': n_port.dpid,
                              'src_port': n_port.port_id,
                              'hwaddr': self.lvap.addr,
                              'match': match}

                    intent['dst_dpid'] = value.dpid
                    intent['dst_port'] = value.ovs_port_id

                    # remove virtual link
                    if self.__contains__(key):
                        self.__delitem__(key)

                    # add new virtual link
                    uuid = add_intent(intent)
                    self.__uuids__[match] = uuid

                    dict.__setitem__(self, match, value)

                    break


class VirtualPortPropLvnf(VirtualPortProp):
    """VirtualPortProp class for LVAPs."""

    def __init__(self):
        super().__init__()
        self.lvnf = None
