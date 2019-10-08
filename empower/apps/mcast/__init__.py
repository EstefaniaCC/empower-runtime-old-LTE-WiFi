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

"""Multicast Management App."""

# the manifest
MANIFEST = {
    "name": "empower.apps.mcast.multimcast",
    "desc": "A simple Multicast manager app.",
    "params": {
        "tenant_id": {
            "desc": "The tenant on which this app must be loaded.",
            "mandatory": True,
            "type": "UUID"
        },
        "every": {
            "desc": "The control loop period (in ms).",
            "mandatory": False,
            "default": 1000,
            "type": "int"
        },
        "demo_mode": {
            "desc": "The multicast mode (dms, sdnplay)",
            "mandatory": False,
            "default": "sdnplay",
            "type": "string"
        },
        "mcast_services": {
            "desc": "Description of the multicast services",
            "mandatory": False,
            "default": {},
            "type": "dict"
        }
    }
}
