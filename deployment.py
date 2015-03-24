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
import logging
import time
import defragger
import cpyutils.eventloop

class VMAssign:
    def __init__(self, vm_data):
        self._vmid = vm_data.id
        self.hostname = vm_data.hostname
        self.state = vm_data.state

        self.timestamp = cpyutils.eventloop.now()
        
        if config.config_vmca.CONSIDER_VMS_STABLE_ON_STARTUP:
            self.timestamp = self.timestamp - config.config_vmca.STABLE_TIME
        
    def update(self, vm_data):
        if vm_data.id != self._vmid:
            logging.error("an error occurred when updating the information about the assignation of a VM to a host")
        
        if (self.hostname != vm_data.hostname) or (self.state != vm_data.state):
            self.hostname = vm_data.hostname
            self.state = vm_data.state
            self.timestamp = cpyutils.eventloop.now()

class Deployment:
    def vmcount(self):
        return len(self._vms_info)
    
    def __init__(self):
        self._hosts_info = {}
        self._vms_info = {}
        self._vm2host = {}

    def get_info(self):
        """
        @description Obtains the hosts of the deployment (they include the VMs that are associated to them)
        @return hosts_info is a HostsInfo structure that contains HostData structures for each host available in the system
        """
        return defragger.HostsInfo(self._hosts_info)

    def _update_vms_to_hosts(self, hosts_info, vms_info):
        for h_id, h in hosts_info.items():
            h.remove_any_vm()

        for vm_id, vm in vms_info.items():
            h_id = vm.hostname
            vm_state = vm.state
            
            if vm_id in self._vm2host:
                self._vm2host[vm_id].update(vm)
            else:
                self._vm2host[vm_id] = VMAssign(vm)
                
            vm.timestamp_state = self._vm2host[vm_id].timestamp
            
            if h_id in hosts_info:
                hosts_info[h_id].add_vm(vm)
            else:
                logging.warning("VM %s is supposed to be located into the non existing host %s" % (vm_id, h_id))
        
    def migrate_vm(self, vmid, host_src, host_dst):
        """
        @description Migrates a VM to another host
        @param vmid the identifier (expressed in the deployment domain) of the
            VM that must be moved
        @param dest_hostname the name of the host to which the VM must be moved
        @retur True if the VM has been migrated
        """
        vm = self._vms_info[vmid]
        logging.info("moving VM %s to %s" % (vm, host_dst))
        if (host_dst in self._hosts_info and host_src in self._hosts_info):
            self._hosts_info[host_dst].add_vm(vm)
            self._hosts_info[host_src].remove_vm(vm)
            vm.hostname = host_dst
            vm.state = defragger.VMData.STATE_MIGRATING
            
            if vmid in self._vm2host:
                self._vm2host[vmid].update(vm)

            return True
        else:
            return False

    def _detect_stable_vms(self):
        now = cpyutils.eventloop.now()

        stable_vms = []
        for vm_id, vm_assign in self._vm2host.items():
            if (vm_assign.state == defragger.VMData.STATE_RUNNING) and ((now - vm_assign.timestamp) > config.STABLE_VM_TIME):
                stable_vms.append(vm_id)
            else:
                logging.debug("vm %s is not stable yet")
                
        return stable_vms

    def _detect_stable_hosts(self):
        stable_vms = self._detect_stable_vms()
        stable_hosts = []
    
        for h_id, h in self._hosts_info.items():
            host_stable = True
            for vm in h.vm_list:
                if vm.id not in stable_vms:
                    host_stable = False
                    break
            if host_stable:
                stable_hosts.append(h_id)

        return stable_hosts

    def get_candidates(self):
        """
        @description Obtains the host candidates whose VM can be moved to other
            hosts
        @return candidate_hosts A list of hostnames whose VM can be moved to
            other hosts
        """
        candidate_hosts = [ ]
        stable_hosts = self._detect_stable_hosts()

        for hostname, hostdata in self._hosts_info.items():
            if (hostname not in config.DISABLED_HOSTS) and (hostname in stable_hosts):
                remove_host = False
                
                stats = hostdata.get_stats()

                if stats.cpu_usage > (config.CPU_MIN / 100.0):
                    remove_host = True
                    
                if stats.mem_usage > (config.MEMORY_MIN / 100.0):
                    remove_host = True

                if (config.VM_MIN > -1) and (stats.vm_count > config.VM_MIN):
                    remove_host = True

                if remove_host:
                    logging.debug("excluding host (%s) because it is stable right now (%s)" % (hostname, stats))
                else:
                    candidate_hosts.append(hostname)
        
        return candidate_hosts

    def get_replaceable_vms(self):
        """
        @description Obtains the vm that can be moved to other host
        @return replaceable_vm A list of VM ids that can be moved to other hosts
        """
        candidate_hosts = self.get_candidates()
        stable_vms = self._detect_stable_vms()

        replaceable_vm = [ vmid for vmid, vmdata in self._vms_info if vmdata.id in stable_vms and vmdata.hostname in candidate_hosts ]
        return replaceable_vm

    def get_migrating_vms(self):
        '''
        @description returns a list of the vmids that are being migrated
        '''
        return None
    
    def get_locked_vms(self):
        '''
        @description returns a list of the vmids of the VMs that cannot be moved
        
        - the default implementation returns None, which is not a valid value
        '''
        None
    