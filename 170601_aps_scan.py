#!/usr/bin/env python

import subprocess
import sched, time
import argparse
import struct
import json
import sys
import string
import logging
from os.path import expanduser

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
aps_info = list()
sta_address = None
s = sched.scheduler(time.time, time.sleep)

logPath = "/home/"
fileName = "scapy_client"

formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

fh = logging.FileHandler("{0}/{1}.log".format(logPath, fileName))
fh.setLevel(logging.DEBUG)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger.addHandler(ch)


def ifaces_recovery():
	global logger
	global sta_address

	wireless_ifaces = []

	iwdev = subprocess.Popen('iw dev', shell=True, stdout=subprocess.PIPE)
	if not iwdev:
		logger.error("The was an error while interface information. Please, reconnect to the network and try again.")
		sys.exit()
		quit()

	for line in iwdev.stdout:
		if 'Interface' in line:
			fields = line.split()
			wireless_ifaces.append(fields[1])

	logger.info("Number of ifaces: %d %s", len(wireless_ifaces), wireless_ifaces)

	if (len(wireless_ifaces)) == 0:
		logger.error("No wireless interfaces have been detected")
		sys.exit()
		quit()

	iface = wireless_ifaces[0]

	sta_address = subprocess.Popen('cat /sys/class/net/%s/address' % iface, shell=True, stdout=subprocess.PIPE).stdout.read().strip()
	if not sta_address:
		logger.error("The was an error while recovering the hardware address. Please, reconnect to the network and try again.")
		sys.exit()
		quit()

	iwconfig = subprocess.Popen('iwconfig %s' % iface, shell=True, stdout=subprocess.PIPE)
	#print(iwconfig.stdout)
	ssid = None
	if not iwconfig:
		logger.error("The was an error while recovering interfaces information. Please, reconnect to the network and try again.")
		sys.exit()
		quit()
	for line in iwconfig.stdout:
		#print(line)
		fields = line.split()
		#print(fields)
		for subfield in fields:
			if 'ESSID:' in subfield:
				ssid = subfield[7:-1]
				#print(subfield[7:-1])
				return ssid

	return None

def gather_rssi_info(ssid):
	global aps_info
	global s

	scan_result = subprocess.Popen("nmcli -f BSSID,SSID,SIGNAL,CHAN dev wifi list | grep %s" % ssid, shell=True, stdout=subprocess.PIPE)
	aps_info = []

	for line in scan_result.stdout:
		fields = line.split()
		print(fields[0])
		quality = int(fields[2])
		rssi = 0
		if quality <= 0:
			rssi = -100
		elif quality >= 100:
			rssi = -50
		else:
			rssi = (quality / 2) - 100
		print(rssi)
		ap = \
			{
			'wtp': fields[0],
			'rssi': rssi,
			'channel': int(fields[3])
			}
		aps_info.append(ap)

	aps_report()
	s.enter(120, 1, gather_rssi_info (ssid), (sc,))

def aps_report():
	global sta_address
	global aps_info

	if not aps_info:
		return

	sta_information = {
		'version': 1.0,
		'params': {
			'aps': {
				'addr': sta_address,
				'wtps': aps_info
			}
		}
	}

	jsondata = json.dumps(sta_information)
	subprocess.Popen("curl -X PUT -d '%s' 'http://foo:foo@192.168.100.207:8888/api/v1/tenants/b552fedf-d846-4407-ac90-05d89d6f673c/components/empower.apps.loadbalancing.loadbalancing' " % jsondata, shell=True, stdout=subprocess.PIPE)
	logger.info(sta_information)
 
def main():
	global aps_info
	global s
	
	ssid = ifaces_recovery()

	
	s.enter(60, 1, gather_rssi_info (ssid), (s,))
	s.run()

	
	#print(ssid)

	print(aps_info)
	#hwaddr_recovery(iface)
	#aps_report()

if __name__ == '__main__':
    main()