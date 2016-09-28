# coding: utf-8
#
# Virtual Machine Consolidation Agent (VMCA)
# Copyright (C) 2016 - GRyCAP - Universitat Politecnica de Valencia
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
import cpyutils
import logging
import random
import vmca.defragger
import vmca.deployment

class SimHostsInfo(vmca.defragger.HostsInfo):
    def redistribute_vms_ffd(self):
        retval = True
        vms = self._collect_vms()
        vms.sort(key = lambda x: x.cpu, reverse = True)
        for vm in vms:
            hosted = False
            for h_id, h in self._hosts_info.items():
                if h.vm_can_fit(vm):
                    h.add_vm(vm)
                    vm.hostname = h_id
                    hosted = True
                    break
            if not hosted:
                print "could not host one vm"
                retval = False
        return retval

    def redistribute_vms_random(self):
        retval = True
        vms = self._collect_vms()
        for vm in vms:
            hosted = False
            candidates = self._hosts_info.keys()
            while len(candidates) > 0:
                n = random.randint(0, len(candidates) - 1)
                h_id = candidates[n]
                candidates.remove(h_id)
                h = self._hosts_info[h_id]
                if h.vm_can_fit(vm):
                    h.add_vm(vm)
                    vm.hostname = h_id
                    hosted = True
                    break
                
            if not hosted:
                print "could not host one vm"
                retval = False
        return retval

    def _collect_vms(self):
        vms = []
        for h_id, h in self._hosts_info.items():
            for vm in h.vm_list[:]:
                h.remove_vm(vm)
                vm.hostname = None
                vms.append(vm)
        return vms
    
class FAKE_Deployment(vmca.deployment.Deployment):
    def clone(self):
        import copy
        return copy.deepcopy(self)

    def get_migrating_vms(self):
        return self.migration_vms.keys()
    
    def __init__(self, vm_count = 8, host_count = 10, host_mem_size = 4096, host_proc_count = 4):
        vmca.deployment.Deployment.__init__(self)
        self.migration_vms = {}

    @staticmethod
    def create_from_filename(filename):
        if filename is not None:
            hosts_info = SimHostsInfo.createfromfile(filename)
            ndeployment = FAKE_Deployment.create_from_hosts_info(hosts_info)
            ndeployment.stabilize_vms(600)
            return ndeployment

    @staticmethod
    def create_from_random(tipo_nodos, num_nodos, tipo_instancias, tipo_instancias_prob, num_instancias, save_to_file = True):
        hosts_info = {}
        if num_nodos is None:
            # This case is when the type of nodes are the nodes themselves, so we make a copy of them
            for nodo in tipo_nodos:
                nnode = nodo.clone()
                hosts_info[nnode.hostname] = nnode
        else:
            type_count = len(tipo_nodos)
            for i in range(1, num_nodos + 1):
                n = random.randint(0, type_count - 1)
                h = tipo_nodos[n].clone()
                h.hostname = "%s%.2d" % (h.hostname, i)
                hosts_info[h.hostname] = h

        vms = []
        if num_instancias is None:
            for vm in tipo_instancias:
                vms.append(vm.clone())
        else:
            instance_type_p = []
            for i in range(0, len(tipo_instancias_prob)):
                for j in range(0, tipo_instancias_prob[i]):
                    instance_type_p.append(i)
            random.shuffle(instance_type_p)
            prob_count = len(instance_type_p)
            
            for i in range(0, num_instancias):
                n = random.randint(0, prob_count - 1)
                m = tipo_instancias[instance_type_p[n]].clone()
                m.id = i
                vms.append(m)

        for vm in vms:
            hosted = False
            candidates = hosts_info.keys()
            while len(candidates) > 0:
                n = random.randint(0, len(candidates) - 1)
                h_id = candidates[n]
                candidates.remove(h_id)
                h = hosts_info[h_id]
                if h.vm_can_fit(vm):
                    h.add_vm(vm)
                    vm.hostname = h_id
                    hosted = True
                    break
                
            if not hosted:
                print "could not host one vm"
                
        ndeployment = FAKE_Deployment.create_from_hosts_info(hosts_info)
        ndeployment.stabilize_vms(600)
        if save_to_file:
            original_hosts_info = ndeployment.get_info()
            import time
            original_hosts_info.csv("use-cases/caso-%s" % time.strftime("%Y%m%d_%H%M%S"))
        return ndeployment

    @staticmethod
    def create_from_hosts_info(hosts_info):
        nd = FAKE_Deployment(0, 0)
        nd._hosts_info = {}
        nd._vms_info = {}
        for h_id, h in hosts_info.items():
            nd._hosts_info[h_id] = h
            for vm in h.vm_list:
                nd._vms_info[vm.id] = vm
        return nd
        
    def get_info(self):
        self._update_vms_to_hosts(self._hosts_info, self._vms_info)
        return SimHostsInfo(self._hosts_info)
        # return deployment.Deployment.get_info(self)
    
    def _calculate_migration_time(self, vm, host_src, host_dst):
        import random
        base = 1.0 * random.randint(30,90)
        extra = random.random() * random.randint(30, 60)
        return base + extra

    def _start_migration(self, vmid, host_src, host_dst, now = None):
        if vmid in self.migration_vms:
            logging.error("vm %s is being already migrated" % vmid)
            raise Exception()

        if now is None:
            now = cpyutils.eventloop.now()
            
        self.migration_vms[vmid] = (host_src, host_dst, now)

        h_s = self._hosts_info[host_src]
        h_d = self._hosts_info[host_dst]
        vm = h_s.get_vm_byid(vmid)
        h_s.remove_vm(vm)
        h_d.add_vm(vm)
        vm.hostname = host_dst
        vm.timestamp_state = cpyutils.eventloop.now()
        vm.state = vmca.defragger.VMData.STATE_MIGRATING

        migration_time = self._calculate_migration_time(vm.id, host_src, host_dst)
        logging.info("(T: %.2f) migration of vm %s from %s to %s is estimated in %.2f seconds" % (cpyutils.eventloop.now(), vm.id, host_src, host_dst, migration_time))
        cpyutils.eventloop.get_eventloop().add_event(cpyutils.eventloop.Event(migration_time, description = "migration of vm %s from %s to %s" % (vmid, host_src, host_dst), callback = self._end_migration, parameters = [vmid], mute = False))
        
    def _end_migration(self, vmid):
        if vmid not in self.migration_vms:
            logging.error("vm %s is not being migrated" % vmid)
            raise Exception()

        host_src, host_dst, timestamp = self.migration_vms[vmid]
        h_s = self._hosts_info[host_src]
        h_d = self._hosts_info[host_dst]
        vm = h_d.get_vm_byid(vmid)
        vm.timestamp_state = cpyutils.eventloop.now()
        vm.state = vmca.defragger.VMData.STATE_RUNNING

        logging.info("(T: %.2f) vm %s migrated from %s to %s" % (cpyutils.eventloop.now(), vmid, host_src, host_dst))
        self._vms_info[vmid] = vm
            
        # print "-"*100
        # import defragger
        # print defragger.HostsInfo(self._hosts_info).dump_info()
        
        del self.migration_vms[vmid]

        # TODO: this is the time to ensure that the defrag method is executed in simulated time
        # cpyutils.eventloop.get_eventloop().add_control_event(10)
        
    def stabilize_vms(self, min_stable_time):
        for vm_id, vm in self._vms_info.items():
            vm.timestamp_state = vm.timestamp_state - min_stable_time
            vm.state = vmca.defragger.VMData.STATE_RUNNING

        for vmid, vmassign in self._vm2host.items():
            vmassign.timestamp -= min_stable_time

    def migrate_vm(self, vmid, host_src, host_dst):
        if vmid in self.migration_vms:
            logging.warning("tried to migrate a VM that is already being migrated")
            # raise Exception()
            return False
        
        if host_src not in self._hosts_info:
            raise Exception()
            return False
        if host_dst not in self._hosts_info:
            raise Exception()
            return False

        # print vmid, host_src, host_dst
        
        self._start_migration(vmid, host_src, host_dst)
        return True
