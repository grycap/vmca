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
import config
import sys
import logging

def version():
    from version import VERSION
    return True, VERSION

def forcerun():
    global DAEMON
    DAEMON.forcerun()
    return True, "run forced"

def cleanhosts(nodenames=[], override=False, canuseempty=False):
    global DAEMON
    result, text = DAEMON.clean_hosts(nodenames, override, canuseempty)
    return result, text
        
def getplan():
    global DAEMON
    return True, DAEMON.get_migration_plan()

def getmean(override_fixed_vms):
    global DAEMON
    import schedule
    import bestfit
    class T_getmean(schedule.Scheduler_Stripping, bestfit.Defragger_BF_Cost, bestfit.Defragger_Distribute): pass
    result, explain = DAEMON.defrag_using_defragger(T_getmean(), override_fixed_vms = override_fixed_vms, can_use_empty_hosts = True)
    return result, explain

def getinfo():
    global DAEMON
    return True, DAEMON.dump_data()

def vmca_server_functions():
    import cpyutils.xmlrpcutils
    cpyutils.xmlrpcutils.create_xmlrpc_server_in_thread(config.config_vmca.XMLRPC_HOST, config.config_vmca.XMLRPC_PORT, [version, forcerun, getplan, cleanhosts, getinfo, getmean])

def main_loop():
    DEBUG_MODE = True

    debug_level = logging.DEBUG
    if config.config_vmca.DEBUG_LEVEL == "info":
        debug_level = logging.INFO
    if config.config_vmca.DEBUG_LEVEL == "error":
        debug_level = logging.ERROR

    logging.basicConfig(filename=config.config_vmca.LOG_FILE, level=debug_level,
                        format='%(asctime)s: %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%Y %H:%M:%S', stream = sys.stdout)

    import schedule
    import firstfit
    import vmcaserver
    class T(schedule.Scheduler_Packing, firstfit.SelectHost_LessVMs_First, firstfit.Defragger_FF): pass
    class T_clean(schedule.Scheduler_Stripping, firstfit.SelectHost_LessVMs_First, firstfit.Defragger_FF): pass
    
    import one
    deployment = one.Deployment(config.config_one.ONE_XMLRPC, config.config_one.ONE_AUTH)
    
    vmca_server_functions()
    
    global DAEMON
    DAEMON = vmcaserver.Daemon(deployment, T(), T_clean())
    DAEMON.loop()    

if __name__ == '__main__':
    main_loop()
