#!/usr/bin/env python
# -*- coding: utf-8 -*-
# @Author: jinpf
# @Date:   2014-05-17 08:56:12
# @Last Modified by:   jinpf
# @Last Modified time: 2014-05-17 10:42:01
# @Email: jpflcj@sina.com

"""
# @comment here:

"""
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.recoco import Timer
import logging


def _handle_timer(message):
	print message
	#msg1:in_port=1 => drop
	msg1=of.ofp_flow_mod(command=of.OFPFC_MODIFY)
	msg1.match.in_port=1
	#msg2:in_port=2 => drop
	msg2=of.ofp_flow_mod(command=of.OFPFC_MODIFY)
	msg2.match.in_port=2
	_connections = core.openflow._connections
	for connection in _connections.values():
		connection.send(msg1)
		connection.send(msg2)

class Sp_network(object):
	"""docstring for Sp_network"""
	def __init__(self):
		core.openflow.addListeners(self)

	def _handle_ConnectionUp (self, event):
		#msg1:in_port=1 => out_port=2
		msg1=of.ofp_flow_mod()
		msg1.match.in_port=1
		msg1.actions.append(of.ofp_action_output(port=2))
		#msg2:in_port=2 => out_port=1
		msg2=of.ofp_flow_mod()
		msg2.match.in_port=2
		msg2.actions.append(of.ofp_action_output(port=1))
		event.connection.send(msg1)
		event.connection.send(msg2)
		print '1 ping 2 is ok'


def launch():
	#clear some unimportant message
	core.getLogger("packet").setLevel(logging.ERROR)
	core.registerNew(Sp_network)
	Timer(25,_handle_timer,recurring=False,args=["Now 1 ping 2 is not ok!"])