#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: jinpf
# @Date:   2014-05-19 09:33:07
# @Last Modified by:   jinpf
# @Last Modified time: 2014-05-24 17:11:01
# @Email: jpflcj@sina.com

"""
# @comment here:

"""
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet
import logging

IP_To_MAC={}	#Mac_To_IP={IP:mac}
Switch_Output={}	#Switch_Output={dpid:{mac:port}}
Switch_AntiFlood={}	#Switch_AntiFlood={dpid:[IP1,IP2,...]}

def Install_Flow(event,src,dst,out_port):
	msg = of.ofp_flow_mod()
	msg.match.dl_dst = dst 
	msg.match.dl_src = src
	msg.actions.append(of.ofp_action_output(port = out_port))
	event.connection.send(msg)

class Arp_proxy(object):
	def __init__(self):
		core.openflow.addListeners(self)

	def _handle_ConnectionUp(self,event):
		Switch_Output[event.dpid]={}
		Switch_AntiFlood[event.dpid]=[]

	def _handle_ConnectionDown(self,event):
		del Switch_Output[event.dpid]
		del Switch_AntiFlood[event.dpid]
		IP_To_MAC={}

	def _handle_PacketIn(self,event):
		packet = event.parsed
		Switch_Output[event.dpid][packet.src]=event.port

		if packet.find("arp"):
			arp_packet=packet.find("arp")
			IP_To_MAC[arp_packet.protosrc]=packet.src
			if arp_packet.opcode==arp.REQUEST:
				# if arp_packet.protodst in IP_To_MAC:	#reply
				# 	#construct arp reply packet
				# 	arp_reply=arp()
				# 	arp_reply.hwsrc=IP_To_MAC[arp_packet.protodst]
				# 	arp_reply.hwdst=packet.src
				# 	arp_reply.opcode=arp.REPLY
				# 	arp_reply.protosrc=arp_packet.protodst
				# 	arp_reply.protodst=arp_packet.protosrc
				# 	ether=ethernet()
				# 	ether.type=ethernet.ARP_TYPE
				# 	ether.dst=packet.src
				# 	ether.src=IP_To_MAC[arp_packet.protodst]
				# 	ether.payload=arp_reply

				# 	# send the created arp reply back to switch
				# 	msg=of.ofp_packet_out()
				# 	msg.data=ether.pack()
				# 	msg.actions.append(of.ofp_action_output(port=of.OFPP_IN_PORT))
				# 	msg.in_port=event.port
				# 	event.connection.send(msg)

				# elif (arp_reply.protosrc,arp_packet.protodst) not in Switch_AntiFlood[event.dpid]:	#flood
					msg=of.ofp_packet_out(data=event.data)
					msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
					msg.in_port=event.port
					event.connection.send(msg)
					# Switch_AntiFlood[event.dpid].append((arp_reply.protosrc,arp_packet.protodst) )


		# if packet.find('ipv4'):
		# 	ip_packet=packet.find('ipv4')
		# 	IP_To_MAC[ip_packet.dstip]=packet.dst
		# 	IP_To_MAC[ip_packet.srcip]=packet.src

		if packet.dst in Switch_Output[event.dpid]  :
			msg=of.ofp_packet_out(data=event.ofp)
			msg.actions.append(of.ofp_action_output(port=Switch_Output[event.dpid][packet.dst]))
			msg.in_port=event.port
			event.connection.send(msg)

			Install_Flow(event,packet.src,packet.dst,Switch_Output[event.dpid][packet.dst])
			Install_Flow(event,packet.dst,packet.src,Switch_Output[event.dpid][packet.src])

		print event.dpid,'packet_in:',packet
		print 'out_put:',Switch_Output
		print 'IP_MAC',IP_To_MAC
		print 'Anti',Switch_AntiFlood
		print



def launch():
	#clear some unimportant message
	core.getLogger("packet").setLevel(logging.ERROR)
	core.registerNew(Arp_proxy)