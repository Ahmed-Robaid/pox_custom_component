#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: jinpf
# @Date:   2014-05-31 16:46:10
# @Last Modified by:   jinpf
# @Last Modified time: 2014-06-01 00:22:07
# @Email: jpflcj@sina.com

"""
# @comment here:

"""
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.openflow.discovery import Discovery
from pox.lib.packet.arp import arp
from pox.lib.packet.ethernet import ethernet
from pox.lib.addresses import EthAddr
from pox.lib.recoco import Timer
import logging

Swich_Connect_Info={}	#Swich_Connect_Info={dpid1:{dpid2:(port1,cost)}} , cost stands for link cost
IP_To_MAC={}	#IP_To_MAC={IP:mac}
Host_Info={}	#Host_Info={mac:(dpid,port,ip)} , record host direct connect switch


MAXINT=9999
Special_MAC=EthAddr('11:11:11:11:11:11')

###############################
##          arp proxy function          ###
###############################

#when don`t know ip->mac ,flood arp
def Arp_Flood(arp_packet):
	#construct arp request packet
	arp_request=arp()
	arp_request.hwsrc=arp_packet.hwsrc		#Special_MAC
	arp_request.hwdst=arp_packet.hwdst		#EthAddr(b"\xff\xff\xff\xff\xff\xff")
	arp_request.opcode=arp.REQUEST
	arp_request.protosrc=arp_packet.protosrc
	arp_request.protodst=arp_packet.protodst
	ether=ethernet()
	ether.type=ethernet.ARP_TYPE
	ether.dst=EthAddr(b"\xff\xff\xff\xff\xff\xff")
	ether.src=Special_MAC
	ether.payload=arp_request

	msg=of.ofp_packet_out()
	msg.data=ether.pack()
	msg.actions.append(of.ofp_action_output(port=of.OFPP_FLOOD))
	for connection in core.openflow.connections:
		connection.send(msg)

#when we know ip->mac ,reply
def Arp_Reply(event,arp_packet):
	#construct arp reply packet
	arp_reply=arp()
	arp_reply.hwsrc=IP_To_MAC[arp_packet.protodst]
	arp_reply.hwdst=arp_packet.hwsrc
	arp_reply.opcode=arp.REPLY
	arp_reply.protosrc=arp_packet.protodst
	arp_reply.protodst=arp_packet.protosrc
	ether=ethernet()
	ether.type=ethernet.ARP_TYPE
	ether.dst=arp_packet.hwsrc
	ether.src=IP_To_MAC[arp_packet.protodst]
	ether.payload=arp_reply

	# send the created arp reply back to switch
	msg=of.ofp_packet_out()
	msg.data=ether.pack()
	msg.actions.append(of.ofp_action_output(port=of.OFPP_IN_PORT))
	msg.in_port=event.port
	event.connection.send(msg)

################################
###          find path algorithm          ###
################################

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
				if dist[sw] >dist[mstart]+Swich_Connect_Info[mstart][sw][1]:
					dist[sw]=dist[mstart]+Swich_Connect_Info[mstart][sw][1]
					path[sw]=path[mstart]+[sw]

		min_sw=min(dist.items(), key=lambda x: compare_rule(x,Used_Sw)) [0]
		Used_Sw.append(min_sw)
		mstart=min_sw

	print 'path :',start,'->',end,' : ',path[end]
	return path[end]


#find all path by using information form Swich_Connect_Info , return all path
def Floyd():
	All_Path={}	#All_Path={dpid1:dpid2:[]} , record path from dpid1 to dpid2
	dist={}		#dist[start][end] stands for shortest distance from start to end node
	Switches=Swich_Connect_Info.keys()	#list of switches

	#inital
	for src_sw in Switches:
		if src_sw not in All_Path:
			All_Path[src_sw]={}
		if src_sw not in dist:
			dist[src_sw]={}
		for dst_sw in Switches:
			All_Path[src_sw][dst_sw]=[]
			if src_sw==dst_sw:
				dist[src_sw][dst_sw]=0
			else:
				dist[src_sw][dst_sw]=MAXINT

	for src_sw in Swich_Connect_Info:
		for dst_sw in Swich_Connect_Info[src_sw]:
			dist[src_sw][dst_sw]=Swich_Connect_Info[src_sw][dst_sw][1]

	for mid_sw in Switches:
		for src_sw in Switches:
			for dst_sw in Switches:
				if mid_sw != src_sw and mid_sw != dst_sw:
					if dist[src_sw][dst_sw] > dist[src_sw][mid_sw]+dist[mid_sw][dst_sw]:
						dist[src_sw][dst_sw]=dist[src_sw][mid_sw]+dist[mid_sw][dst_sw]
						All_Path[src_sw][dst_sw]=All_Path[src_sw][mid_sw]+[mid_sw]+All_Path[mid_sw][dst_sw]

	for src_sw in Switches:
		for dst_sw in Switches:
			if src_sw == dst_sw:
				All_Path[src_sw][dst_sw]=[src_sw]
			elif len(All_Path[src_sw][dst_sw]) != 0 or dist [src_sw][dst_sw] < MAXINT:
				All_Path[src_sw][dst_sw]=[src_sw]+All_Path[src_sw][dst_sw]+[dst_sw]

			print 'path :',src_sw,'->',dst_sw,' : ',All_Path[src_sw][dst_sw]

	return All_Path

##################################
###         flow operation function        ###
##################################

#install flow on path switch
def Install_Path_Flow(src,dst,path=None,event=None):
	start_sw=Host_Info[src][0]
	end_sw=Host_Info[dst][0]
	if path==None:
		path=Dijkstra(start_sw,end_sw)
		print 'Install path flow -----------------------------'

	#install flow for the path
	for i in range(len(path)):
		#flow for src->dst
		msg1=of.ofp_flow_mod()
		msg1.match.dl_dst=dst
		msg1.match.dl_src=src
		if i==len(path)-1:	#last node
			msg1.actions.append(of.ofp_action_output( port=Host_Info[dst][1] ) )
		else:	
			msg1.actions.append(of.ofp_action_output( port=Swich_Connect_Info[ path[i] ][ path[i+1] ][0] ))
		core.openflow.sendToDPID(path[i],msg1)

		#flow for dst->src
		msg2=of.ofp_flow_mod()
		msg2.match.dl_dst=src
		msg2.match.dl_src=dst
		if i==0:	#first node
			msg2.actions.append(of.ofp_action_output( port=Host_Info[src][1] ) )
		else:
			msg2.actions.append(of.ofp_action_output( port=Swich_Connect_Info[ path[i] ][ path[i-1] ][0] ))
		core.openflow.sendToDPID(path[i],msg2)

	#send out this Packedin data
	if event !=None:
		i=path.index(event.dpid)
		msg=of.ofp_packet_out(data=event.data)
		if i==len(path)-1:
			msg.actions.append(of.ofp_action_output(port=Host_Info[dst][1]))
		else:
			msg.actions.append(of.ofp_action_output(port=Swich_Connect_Info[ path[i] ][ path[i+1] ][0] ))
		msg.in_port=event.port
		event.connection.send(msg)

#install all flow
def Install_All_Flow(message):
	print message
	All_Path=Floyd()
	for src_host in Host_Info.keys():
		for dst_host in Host_Info.keys():
			if src_host != dst_host:
				Install_Path_Flow(src_host,dst_host,path=All_Path[ Host_Info[src_host][0] ][ Host_Info[dst_host][0] ])

	print

#delete all flow on all switch
def Delete_All_Flow():
	msg = of.ofp_flow_mod(match = of.ofp_match(),command = of.OFPFC_DELETE)
	for connection in core.openflow.connections:
		connection.send(msg)



def Clear_All_Information(message):
	print message
	IP_To_MAC={}
	Host_Info={}
	Delete_All_Flow()
	print

################################
###      handle openflow event       ####
################################

class Link_Learning(object):
	def __init__(self):
		core.openflow.addListeners(self)
		core.openflow_discovery.addListeners(self)

	def _handle_LinkEvent(self,event):
		dpid1=event.link[0]
		dpid2=event.link[2]

		if event.added is True:
			if Swich_Connect_Info[dpid1].get(dpid2) is None:
				Swich_Connect_Info[dpid1][dpid2]=(event.link[1],1)	#cost default set 1
				Swich_Connect_Info[dpid2][dpid1]=(event.link[3],1)	#cost default set 1

		if event.removed is True:
			if Swich_Connect_Info[dpid1].get(dpid2) is not None:
				del Swich_Connect_Info[dpid1][dpid2]
				del Swich_Connect_Info[dpid2][dpid1]
				Delete_All_Flow()
				#remain to do some work

		# print Swich_Connect_Info

	def _handle_ConnectionUp(self,event):
		Swich_Connect_Info[event.dpid]={}

	def _handle_ConnectionDown(self,event):
		del Swich_Connect_Info[event.dpid]
		for host in Host_Info.keys():
			if Host_Info[host][0]==event.dpid:
				del Host_Info[host]

	def _handle_PacketIn(self,event):
		packet = event.parsed

		if packet.src!=Special_MAC:	#filt  packet send by ourself
			if packet.find("arp"):
				arp_packet=packet.find("arp")
				# print  'switch:',event.dpid,'packet_in:','arp_packet:',arp_packet
				Host_Info[packet.src]=(event.dpid,event.port,arp_packet.protosrc)
				IP_To_MAC[arp_packet.protosrc]=packet.src
				if arp_packet.opcode==arp.REQUEST:
					if arp_packet.protodst in IP_To_MAC:
						Arp_Reply(event,arp_packet)
					else:
						Arp_Flood(arp_packet)

		if packet.find('ipv4'):
			ip_packet=packet.find('ipv4')
			IP_To_MAC[ip_packet.srcip]=packet.src
			Host_Info[packet.src]=(event.dpid,event.port,ip_packet.srcip)

		if (packet.src in Host_Info) and (packet.dst in Host_Info):
			Install_Path_Flow(packet.src,packet.dst,event=event)
		
		# print 'switch:',event.dpid,'packet_in:',packet
		# print 'IP to MAC',IP_To_MAC
		# print 'Host_Info:',Host_Info
		# print

		

def launch():
	#clear some unimportant message
	core.getLogger("packet").setLevel(logging.ERROR)
	core.registerNew(Discovery,explicit_drop=False,install_flow = False)
	core.registerNew(Link_Learning)

	#update flow
	Timer(120,Install_All_Flow,recurring=True,args=["All Path------------------"])
	#clear all information to keep everything new
	# Timer(150,Clear_All_Information,recurring=True,args=["Clear All Information!"])


