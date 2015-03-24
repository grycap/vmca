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
import logging
import cpyutils.oneconnect
import deployment
import defragger
import config

ALREADY_MIGRATED = False

class HostONE(defragger.HostData):
    def __init__(self, oneinfo):
        defragger.HostData.__init__(self, oneinfo.NAME, oneinfo.total_slots / 100.0, oneinfo.memory_total / 1024.0, oneinfo.keywords)
        self.ID = int(oneinfo.ID)

class Deployment(deployment.Deployment):
    def __init__(self, one_xmlrpc, one_auth):
        deployment.Deployment.__init__(self)
        self._one = None
        one = cpyutils.oneconnect.ONEConnect(one_xmlrpc, one_auth)
        
        if not one.get_server_ref():
            raise Exception()
        else:
            self._one = one

        self._migrating_vms = []
        self._locked_vms = []

    def get_migrating_vms(self):
        return self._migrating_vms
            
    def get_locked_vms(self):
        return self._migrating_vms + self._locked_vms
    
    def get_info(self):
        
        # WARNING: cuando una maquina se esta migrando a veces se ha puesto en "UNKNOWN" al migrarlo y parece que se queda en el nodo origen
        
        # WARNING (2): cuando se migra una maquina, en la siguiente monitorizacion ya tiene que aparecer en el destino; si no, se considerara que ha fallado la migracion
        
        hosts = self._one.get_hosts()
        if hosts is None:
            return None

        for h in hosts:
            hi = HostONE(h)
            self._hosts_info[hi.hostname] = hi

        vms = self._one.get_vms()
        
        self._vms_info = {}
        self._migrating_vms = []
        self._locked_vms = []
        for vm in vms:
            # TODO: revisar esto de que el host sea None
            if len(vm.HISTORY_RECORDS.HISTORY) > 0:
                vm.HISTORY_RECORDS.HISTORY.sort(lambda x : x.SEQ)
                host = vm.HISTORY_RECORDS.HISTORY[0].HOSTNAME
            else:
                host = None

            vmdata = defragger.VMData(vm.ID, vm.TEMPLATE.CPU, vm.TEMPLATE.MEMORY, host)

            self._vms_info[vm.ID] = vmdata
            if (vm.STATE == cpyutils.oneconnect.VM.STATE_ACTIVE):
                if (vm.LCM_STATE == cpyutils.oneconnect.VM.LCM_RUNNING):
                    vmdata.state = defragger.VMData.STATE_RUNNING
                    if (vm.ID in config.config_one.LOCKED_VM_IDS) or (vm.UID in config.config_one.LOCKED_VM_UID) or (vm.GID in config.config_one.LOCKED_VM_GID) or (vm.TEMPLATE.TEMPLATE_ID in config.config_one.LOCKED_TEMPLATES):
                        logging.debug("locking vm %s because of configuration" % vm.ID)
                        self._locked_vms.append(vm.ID)
                        
                elif (vm.LCM_STATE in [ cpyutils.oneconnect.VM.LCM_PROLOG_MIGRATE, cpyutils.oneconnect.VM.LCM_SAVE_MIGRATE, cpyutils.oneconnect.VM.LCM_MIGRATE ]):
                    vmdata.state = defragger.VMData.STATE_MIGRATING
                    self._migrating_vms.append(vm.ID)
                else:
                    logging.debug("vm %s is locked because it is not in running state" % vm.ID)
                    vmdata.state = defragger.VMData.STATE_OTHER
                    self._locked_vms.append(vm.ID)
            else:
                logging.debug("vm %s is locked because it is not in active state" % vm.ID)
                vmdata.state = defragger.VMData.STATE_OTHER
                self._locked_vms.append(vm.ID)
        
        self._update_vms_to_hosts(self._hosts_info, self._vms_info)
        return deployment.Deployment.get_info(self)


    def migrate_vm(self, vmid, host_src, host_dst):
        """
        @description Migrates a VM to another host
        @param vmid the identifier (expressed in the deployment domain) of the
            VM that must be moved
        @param dest_hostname the name of the host to which the VM must be moved
        @retur True if the VM has been migrated
        """
        global ALREADY_MIGRATED
        vm = self._vms_info[vmid]
        logging.info("moving VM %s to %s" % (vm, host_dst))
        if (host_dst in self._hosts_info):
            
            if ALREADY_MIGRATED:
                logging.warning("we have already migrated one VM... enough for the moment")
                return False

            h_dst = self._hosts_info[host_dst]
            if self._one.migrate_vm(int(vmid), h_dst.ID, True):
                ALREADY_MIGRATED = True
                deployment.Deployment.migrate_vm(self, vmid, host_src, host_dst)
                return True
            else:
                logging.error("ONE connector could not migrate vm %s from %s to %s" % (vmid, host_src, host_dst))
                return False
        else:
            return False