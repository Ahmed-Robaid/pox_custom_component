#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: jinpf
# @Date:   2014-05-24 17:15:37
# @Last Modified by:   jinpf
# @Last Modified time: 2014-05-25 22:33:22
# @Email: jpflcj@sina.com

"""
# @comment here:

"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow.discovery import Discovery
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet
from pox.lib.recoco import Timer
import logging

Swich_Connect_Info={}	#Swich_Connect_Info={dpid1:{dpid2:port1}}
IP_To_MAC={}	#Mac_To_IP={IP:mac}
Host_Info={}	#Host_Info={mac:(dpid,port)} , record host direct connect switch
Switch_AntiFlood={}	#Switch_AntiFlood={dpid:[IP1,IP2,...]} , tag for prevent Broadcast radiation

MAXINT=9999

#compare rule,put in min(),data as tumple,data[1] stands for compare data,if data[0] in list L,data[1] won`t be counted when compare
def compare_rule(data,L):
	if data[0] in L:
		return MAXINT
	else:
		return data[1]

#return start -> end path in list
def Dijkstra(start,end):
	path={}	#all shortest path from start
	dist={}		#dist[i] stands for shortest distance from start to i node

	Switches=Swich_Connect_Info.keys()	#list of switches
	Used_Sw=[start]	#already used switches in algorithm

	#inital
	for sw in Switches:
		path[sw]=[]
		dist[sw]=MAXINT

	mstart=start		#mstart stands for start node in each loop 
	path[start]=[start]
	dist[start]=0
	while(len(Used_Sw)<len(Switches)):
		for sw in Swich_Connect_Info[mstart]:
			if sw not in Used_Sw:
				if dist[sw] >dist[mstart]+1:
					dist[sw]=dist[mstart]+1
					path[sw]=path[mstart]+[sw]

		min_sw=min(dist.items(), key=lambda x: compare_rule(x,Used_Sw)) [0]
		Used_Sw.append(min_sw)
		mstart=min_sw

	print path[end]
	return path[end]

#install flow on path switch
def Install_Path_Flow(src,dst,event=None):
	print 'Install path flow -----------------------------'
	start_sw=Host_Info[src][0]
	end_sw=Host_Info[dst][0]
	path=Dijkstra(start_sw,end_sw)

	#install flow for the path
	for i in range(len(path)):
		#flow for src->dst
		msg1=of.ofp_flow_mod()
		msg1.match.dl_dst=dst
		msg1.match.dl_src=src
		if i==len(path)-1:	#last node
			msg1.actions.append(of.ofp_action_output( port=Host_Info[dst][1] ) )
		else:	
			msg1.actions.append(of.ofp_action_output( port=Swich_Connect_Info[ path[i] ][ path[i+1] ] ))
		core.openflow.sendToDPID(path[i],msg1)

		#flow for dst->src
		msg2=of.ofp_flow_mod()
		msg2.match.dl_dst=src
		msg2.match.dl_src=dst
		if i==0:	#first node
			msg2.actions.append(of.ofp_action_output( port=Host_Info[src][1] ) )
		else:
			msg2.actions.append(of.ofp_action_output( port=Swich_Connect_Info[ path[i] ][ path[i-1] ] ))
		core.openflow.sendToDPID(path[i],msg2)

	#send out this Packedin data
	if event !=None:
		i=path.index(event.dpid)
		msg=of.ofp_packet_out(data=event.data)
		if i==len(path)-1:
			msg.actions.append(of.ofp_action_output(port=Host_Info[dst][1]))
		else:
			msg.actions.append(of.ofp_action_output(port=Swich_Connect_Info[ path[i] ][ path[i+1] ] ))
		msg.in_port=event.port
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
		Switch_AntiFlood[event.dpid]=[]

	def _handle_ConnectionDown(self,event):
		del Switch_AntiFlood[event.dpid]
		del Swich_Connect_Info[event.dpid]

	def _handle_PacketIn(self,event):
		packet = event.parsed
		if packet.src not in Host_Info:
			Host_Info[packet.src]=(event.dpid,event.port)

		if packet.find("arp"):
			arp_packet=packet.find("arp")
			IP_To_MAC[arp_packet.protosrc]=packet.src
			if arp_packet.opcode==arp.REQUEST:
				if arp_packet.protodst in IP_To_MAC:	#reply
					#construct arp reply packet
					arp_reply=arp()
					arp_reply.hwsrc=IP_To_MAC[arp_packet.protodst]
					arp_reply.hwdst=packet.src
					arp_reply.opcode=arp.REPLY
					arp_reply.protosrc=arp_packet.protodst
					arp_reply.protodst=arp_packet.protosrc
					ether=ethernet()
					ether.type=ethernet.ARP_TYPE
					ether.dst=packet.src
					ether.src=IP_To_MAC[arp_packet.protodst]
					ether.payload=arp_reply

					# send the created arp reply back to switch
					msg=of.ofp_packet_out()
					msg.data=ether.pack()
					msg.actions.append(of.ofp_action_output(port=of.OFPP_IN_PORT))
					msg.in_port=event.port
					event.connection.send(msg)

				elif (arp_packet.protosrc,arp_packet.protodst) not in Switch_AntiFlood[event.dpid]:	#flood
					msg=of.ofp_packet_out(data=event.data)
					msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
					msg.in_port=event.port
					event.connection.send(msg)
					Switch_AntiFlood[event.dpid].append((arp_packet.protosrc,arp_packet.protodst) )

		if (packet.src in Host_Info) and (packet.dst in Host_Info):
			Install_Path_Flow(packet.src,packet.dst)

		
		print event.dpid,'packet_in:',packet
		print 'IP to MAC',IP_To_MAC
		# print 'Anti',Switch_AntiFlood
		print 'Host_Info:',Host_Info
		print


def launch():
	#clear some unimportant message
	core.getLogger("packet").setLevel(logging.ERROR)
	core.registerNew(Discovery,explicit_drop=False,install_flow = False)
	core.registerNew(Link_Learning)
	Timer(30,_handle_timer,recurring=True,args=["Timer1 come! Switches,give me your stats!"])