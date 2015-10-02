#! /usr/bin/env python
# coding: utf-8
#
# Virtual Machine Consolidation Agent (VMCA)
# Copyright (C) 2015 - GRyCAP - Universitat Politecnica de Valencia
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# 
import sys
import config
import xmlrpclib
import logging
from cpyutils.parameters import *

class VMCACmdLine(CmdLineParser):
    def __init__(self, proxy, executable, desc, arguments):
        CmdLineParser.__init__(self, executable, desc = desc, arguments = arguments)
        self._proxy = proxy

    def getplan(self, result, error):
        succeed, text = self._proxy.getplan()
        if succeed:
            return True, text
        else:
            return False, "Could not get the migration plan from VMCA (%s)" % text
    
    def forcerun(self, result, error):
        succeed, text = self._proxy.forcerun()
        if succeed:
            return True, text
        else:
            return False, "Could not force the run of VMCA (%s)" % text
    
    def clean(self, result, error):
        force = (result.values["-f"])
        useempty = (result.values["-e"])
	hosts = result.values["node"]

        succeed, text = self._proxy.cleanhosts(hosts, force, useempty)
        if succeed:
            return True, text
        else:
            return False, "Could not clean hosts of VMCA (%s)" % text

    def version(self, result, error):
        succeed, text = self._proxy.version()
        if succeed:
            return True, text
        else:
            return False, "Could not get version of VMCA (%s)" % text

    def info(self, result, error):
        succeed, text = self._proxy.getinfo()
        if succeed:
            return True, text
        else:
            return False, "Could not get info about VMCA (%s)" % text

def main_function():
    XMLRPC_SERVER = 'http://%s:%s/RPC2' %(config.config_vmca.XMLRPC_HOST, config.config_vmca.XMLRPC_PORT)
    proxy = xmlrpclib.ServerProxy(XMLRPC_SERVER)

    try:
        version = proxy.version()
    except:
        print "Could not connect to VMCA server %s (please, check if it is running)" % XMLRPC_SERVER, None    
        sys.exit(-1)

    p = VMCACmdLine(proxy, "vmca", desc = "The VMCA command line utility", arguments = [
            Operation("getplan", desc = "Gets the current migration plan that is being carried out in the server"),
            Operation("forcerun", desc = "Forces VMCA to analyze the platform immediately"),
            Operation("clean", desc = "Migrates all the VMs from one host", arguments = [
                Argument("node", desc = "Name of the host that is going to be cleaned", mandatory = True, count = 1),
                Flag("-f", "--force", desc = "Force cleaning even if the host has not its VMs in a stable state"),
                Flag("-e", "--use-empty", desc = "Use emtpy hosts as a possible destinations")
            ]),
            Operation("version", desc = "Gets the version of the VMCA server"),
            Operation("info", desc = "Gets the monitoring information that has the VMCA server"),
        ])
    p.self_service(True)

if __name__ == '__main__':
    main_function()
