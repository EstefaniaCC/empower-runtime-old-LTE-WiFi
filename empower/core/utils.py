#!/usr/bin/env python3
#
# Copyright (c) 2016 Roberto Riggio, Estefania Coronado
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

"""EmPOWER utils."""

from empower.datatypes.etheraddress import EtherAddress


def hex_to_ether(in_hex):
    """Convert Int to EtherAddress."""

    str_hex_value = format(in_hex, 'x')
    padding = '0' * (12 - len(str_hex_value))
    mac_string = padding + str_hex_value
    mac_string_array = \
        [mac_string[i:i+2] for i in range(0, len(mac_string), 2)]

    return EtherAddress(":".join(mac_string_array))


def ether_to_hex(ether):
    """Convert EtherAddress to Int."""

    return int.from_bytes(ether.to_raw(), byteorder='big')


def generate_bssid(base_mac, sta_mac):
    """ Generate a new BSSID address. """

    base = str(base_mac).split(":")[0:3]
    unicast_addr_mask = int(base[0], 16) & 0xFE
    base[0] = str(format(unicast_addr_mask, 'X'))
    sta = str(sta_mac).split(":")[3:6]
    return EtherAddress(":".join(base + sta))

def multicast_ip_to_ether(ip_mcast_addr):
    if ip_mcast_addr is None:
       return '\x00' * 6
    # The first 25 bits are fixed according to class D IP and IP multicast address convenctions
    mcast_base = '01:00:5e'
    # The 23 low order bits are mapped.  
    ip_addr_bytes = str(ip_mcast_addr).split('.')
    # The first IP byte is not use, and only the last 7 bits of the second byte are used.
    ip_addr_second_byte = int(ip_addr_bytes[1]) & 127
    ip_addr_third_byte = int(ip_addr_bytes[2])
    ip_addr_fourth_byte = int(ip_addr_bytes[3])

    mcast_upper = format(ip_addr_second_byte, '02x') + ':' + format(ip_addr_third_byte, '02x') + ':' + format(ip_addr_fourth_byte, '02x')
    mcast_addr = mcast_base + ':' + mcast_upper
    return EtherAddress(mcast_addr)

def verify_multicast_address (ip_mcast_addr):
    ip_addr_bytes = str(ip_mcast_addr).split('.')

    if len(ip_addr_bytes) != 4:
        return False
    # class D IP range 224.0.0.0 – 239.255.255.255 is reserved for multicast IP addresses
    if int(ip_addr_bytes[0]) < 224 or int(ip_addr_bytes[0]) > 239:
        return False
    for byte in range (1, 4):
        if int(ip_addr_bytes[byte]) < 0 or int(ip_addr_bytes[byte]) > 255:
            return False

    return True

def ip_bytes_to_str(addr):
    if isinstance(addr, bytes) and len(addr) == 4:
        ip_string_array = [str(int.from_bytes(addr[i:(i+1)], byteorder='big')) for i in range(0, 4)]
        ip_string = (".".join(ip_string_array))
        return ip_string

    return None
