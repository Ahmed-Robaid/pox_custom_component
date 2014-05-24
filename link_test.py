#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: jinpf
# @Date:   2014-04-19 09:23:32
# @Last Modified by:   jinpf
# @Last Modified time: 2014-04-20 18:37:59
# @Email: jpflcj@sina.com

"""
# @comment here:
pox moduler test, test event and data structure

"""
from pox.core import core
from pox.lib.revent import *
from pox.openflow.discovery import Discovery
from pox.lib.recoco import Timer
import pox.openflow.libopenflow_01 as of
import logging

def _handle_timer(message):
		print 
		print message
		connections = core.openflow._connections
		print 'connected switch:',
		for connection in connections:
			print connection,
			# print 'connection:',connection.dpid,connection.ports #to see what connection consists of
			connection.send(of.ofp_stats_request(body = of.ofp_flow_stats_request()))
			connection.send(of.ofp_stats_request(body = of.ofp_port_stats_request()))
			#delet all flows
			connection.send(of.ofp_flow_mod(match = of.ofp_match(),command = of.OFPFC_DELETE))
		print '\n'

class link_test(EventMixin):

	def __init__(self):
		self.listenTo(core.openflow)
		self.listenTo(core.openflow_discovery)
		

	def _handle_LinkEvent(self,event):
		print 'LinkEvent'
		if event.added is True:
			print '---link added',event.link
		if event.removed is True:
			print '---link removed',event.link
		print 

	def _handle_PacketIn(self,event):
		packet = event.parsed
		print 'PacketIn:from switch',event.dpid,':',packet,'src:',packet.src,'dst',packet.dst
		if packet.find("arp"):
			print 'PacketIn arp'
			arp_packet=packet.find("arp")
			print arp_packet
		elif packet.find("icmp"):
			print 'PacketIn icmp'
		# else:
		# 	print 'PacketIn otherpacket'
		# print 

	def _handle_FlowStatsReceived(self,event):
		print 'flowstats in switch',event.dpid,':'
		for flowstat in event.stats:
			print '  flow table_id:',flowstat.table_id,'packet_count',flowstat.packet_count,'byte_count',flowstat.byte_count
		print 

	def _handle_PortStatsReceived(self,event):
		print 'portstats in switch',event.dpid,':'
		for portstat in event.stats:
			print '  port:',portstat.port_no,'rx_packets',portstat.rx_packets,'tx_packets',portstat.tx_packets,'rx_bytes',portstat.rx_bytes,'tx_bytes',portstat.tx_bytes
		print 

	def _handle_ConnectionUp(self,event):
		print 'ConnectionUp',event.dpid
		print 

	def _handle_ConnectionDown(self,event):
		print 'ConnectionDown',event.dpid
		print 


def launch():
	#make commandline clear from unimportant things
	core.getLogger("packet").setLevel(logging.ERROR)
	core.registerNew(Discovery)
  	core.registerNew(link_test)
  	Timer(20,_handle_timer,recurring=True,args=["Timer1 come! Switches,give me your stats!"])
