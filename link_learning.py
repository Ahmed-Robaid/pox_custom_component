#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: jinpf
# @Date:   2014-05-24 17:15:37
# @Last Modified by:   jinpf
# @Last Modified time: 2014-05-24 23:07:30
# @Email: jpflcj@sina.com

"""
# @comment here:

"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow.discovery import Discovery
from pox.lib.packet.arp import arp
from pox.lib.recoco import Timer
import logging

Switch_Output={}	#Switch_Output={dpid:{mac:port}}
Swich_Connect_Info={}	#Swich_Connect_Info={dpid1:{dpid2:port1}}
Host_Info={}	#Host_Info={mac:(dpid,port)}
Switch_AntiFlood={}	#Switch_AntiFlood={dpid:[IP1,IP2,...]} , tag for prevent Broadcast radiation

def Install_Flow(event,src,dst,out_port):
	msg = of.ofp_flow_mod()
	msg.match.dl_dst = dst 
	msg.match.dl_src = src
	msg.actions.append(of.ofp_action_output(port = out_port))
	event.connection.send(msg)

def _handle_timer(message):
	for dpid in Switch_AntiFlood:
		Switch_AntiFlood[dpid]=[]


class Link_Learning(object):
	def __init__(self):
		core.openflow.addListeners(self)
		core.openflow_discovery.addListeners(self)

	def _handle_LinkEvent(self,event):
		dpid1=event.link[0]
		dpid2=event.link[2]

		if event.added is True:
			if dpid1 not in Swich_Connect_Info:
				Swich_Connect_Info[dpid1]={}
			if dpid2 not in Swich_Connect_Info:
				Swich_Connect_Info[dpid2]={}
			if Swich_Connect_Info[dpid1].get(dpid2) is None:
				Swich_Connect_Info[dpid1][dpid2]=event.link[1]
				Swich_Connect_Info[dpid2][dpid1]=event.link[3]

		if event.removed is True:
			if Swich_Connect_Info[dpid1].get(dpid2) is not None:
				del Swich_Connect_Info[dpid1][dpid2]
				del Swich_Connect_Info[dpid2][dpid1]
				#remain to do some work

		print Swich_Connect_Info

	def _handle_ConnectionUp(self,event):
		Switch_Output[event.dpid]={}
		Switch_AntiFlood[event.dpid]=[]

	def _handle_ConnectionDown(self,event):
		del Switch_Output[event.dpid]
		del Switch_AntiFlood[event.dpid]

	def _handle_PacketIn(self,event):
		packet = event.parsed
		Switch_Output[event.dpid][packet.src]=event.port

		if packet.find("arp"):
			arp_packet=packet.find("arp")
			if arp_packet.opcode==arp.REQUEST:
				if (arp_packet.protosrc,arp_packet.protodst) not in Switch_AntiFlood[event.dpid]:	#flood
					msg=of.ofp_packet_out(data=event.data)
					msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
					msg.in_port=event.port
					event.connection.send(msg)
					Switch_AntiFlood[event.dpid].append((arp_packet.protosrc,arp_packet.protodst) )


		if packet.dst in Switch_Output[event.dpid]  :
			msg=of.ofp_packet_out(data=event.ofp)
			msg.actions.append(of.ofp_action_output(port=Switch_Output[event.dpid][packet.dst]))
			msg.in_port=event.port
			event.connection.send(msg)

			Install_Flow(event,packet.src,packet.dst,Switch_Output[event.dpid][packet.dst])
			Install_Flow(event,packet.dst,packet.src,Switch_Output[event.dpid][packet.src])

		print event.dpid,'packet_in:',packet
		print 'out_put:',Switch_Output
		print 'Anti',Switch_AntiFlood
		print


def launch():
	#clear some unimportant message
	core.getLogger("packet").setLevel(logging.ERROR)
	core.registerNew(Discovery,explicit_drop=False,install_flow = False)
	core.registerNew(Link_Learning)
	Timer(30,_handle_timer,recurring=True,args=["Timer1 come! Switches,give me your stats!"])