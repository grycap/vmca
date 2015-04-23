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
import copy
import math
import cpyutils.eventloop

def calculate_euclid_resources(mem, cpu):
    wm2 = (config.config_vmca.WEIGHT_MEM*mem)*(config.config_vmca.WEIGHT_MEM*mem)
    wc2 = (config.config_vmca.WEIGHT_CPU*cpu)*(config.config_vmca.WEIGHT_CPU*cpu)
    m2 = config.config_vmca.WEIGHT_MEM*config.config_vmca.WEIGHT_MEM
    c2 = config.config_vmca.WEIGHT_CPU*config.config_vmca.WEIGHT_CPU
    return math.sqrt(wm2+wc2)/math.sqrt(m2+c2)

def calc_variance(hosts_info):
    '''
    We can optimize these values, but for the sake of readingness, we are using the full calculation by now
    '''
    
    r_total = 0.0
    n_count = float(len(hosts_info.keys()))
    for h_id in hosts_info.keys():
        r_total += float(hosts_info.euclid_normalized_resources_free(h_id))

    r_mean = r_total / n_count
    
    S_sum = 0.0
    for h_id in hosts_info.keys():
        r_i = float(hosts_info.euclid_normalized_resources_free(h_id))
        S_sum += ((r_i - r_mean)*(r_i - r_mean))

    S_2 = S_sum / n_count

    return S_2
    
class HostData:
    def __init__(self, hostname, cpu, memory, keywords = {}):
        self.hostname = hostname
        self.cpu_free = cpu
        self.cpu_total = cpu
        self.memory_free = memory
        self.memory_total = memory
        self.vm_list = []
        self.maxvms = -1
        self.norm_cpu_free = 0.0
        self.norm_cpu_total = 0.0
        self.norm_memory_free = 0.0
        self.norm_memory_total = 0.0
        self.keywords = {}
        
    def norm_str(self):
        return "CPU: %.1f/%.1f; MEM: %.1f/%.1f" % (self.norm_cpu_free, self.norm_cpu_total, self.norm_memory_free, self.norm_memory_total)
        
    def add_vm(self, vmdata):
        """
        @description The function adds a vm to the host and substracts the
            resources needed to host the vm.
        
        @param vmdata the VMData structure that must be added to the node. 
            * it is not checked whether the vm has space or not
        """
        self.vm_list.append(vmdata)
        self.cpu_free -= vmdata.cpu
        self.memory_free -= vmdata.memory

    def vm_can_fit(self, vmdata):
        """
        @description Checks whether a vm would meet any of the constraints of
            the hosts, in special the amount of resources that the vm needs
        @param vmdata the VMData structure that is checked to fit the host
        @return True in case that the vm would meet any of the constraints
        """
        cpu = self.cpu_free - vmdata.cpu
        memory = self.memory_free - vmdata.memory
        fits = (cpu >= 0 and memory >= 0)
        if fits and self.maxvms >= 0:
            fits = (len(self.vm_list) < self.maxvms)
        return fits

    def remove_vm(self, vmdata):
        """
        @description Removes a VM from the host and returns the resources that
            were reserved for the VM
        @param vmdata the VMData structure that must be removed to the host
        @return True if the vm was in the host. False otherwise
        """
        for vm in self.vm_list:
            if vm.id == vmdata.id:
                self.vm_list.remove(vm)
                self.cpu_free += vmdata.cpu
                self.memory_free += vmdata.memory
                return True

        return False

    def has_vm(self, vmdata):
        """
        @description Returns whether a host is hosting a VM or not
        @param vmdata the VMData structure that must be removed to the host
        @return True if the vm was in the host. False otherwise
        """
        for vm in self.vm_list:
            if vm.id == vmdata.id:
                return True

        return False

    def get_vm_byid(self, vmid):
        """
        @description Returns the VM that has the vmid stated by vmid or None if the hosts does not host a vm with that id
        @param vmid the id of the VM that is wanted to obtain
        @return the VM if the vm was in the host. None otherwise
        """
        for vm in self.vm_list:
            if str(vm.id) == str(vmid):
                return vm

        return None
            
    def remove_any_vm(self):
        """
        @description Removes any of the VMs that are hosted by the host and
            returns the resources that were reserved to them
        """
        for vmdata in self.vm_list:
            self.cpu_free += vmdata.cpu
            self.memory_free += vmdata.memory
        self.vm_list = []
        
    def __str__(self):
        """
        @description String representation of the node
        """
        retval = "hostname: %s; cpu: %f; memory: %d" % (self.hostname, self.cpu_free, self.memory_free)
        retval = "%s; norm_cpu: %f" % (retval, self.norm_cpu_free)
        retval = "%s; norm_memory: %f" % (retval, self.norm_memory_free)
        return retval
    
    def clone(self):
        """
        @description Provides a verbatim copy of the object
        @returns A copy of the object
        """
        return copy.deepcopy(self)

class CannotNormalizeException(Exception): pass

class HostsInfo():
    def stabilize_vms(self, min_stable_time, hosts_affected = []):
        if hosts_affected is None:
            return
        
        for h_id in hosts_affected:
            if h_id in hosts_affected:
                h = self._hosts_info[h_id]
                for vm in h.vm_list:
                    vm.timestamp_state = vm.timestamp_state - min_stable_time
                    vm.state = VMData.STATE_RUNNING
    
    def normalize_resources(self):
        self._max_cpu = 0
        self._max_memory = 0

        # There is a special case for normalization that would cause problems:
        # when there is the unique host and self._max_cpu or self._max_memory is zero. So
        # we'd avoid it by assuming that when there is only 1 host, the normalized
        # values are 1.0
        if len(self._hosts_info) > 1:
            for hostname, hostdata in self._hosts_info.items():
                if hostdata.cpu_total > self._max_cpu:
                    self._max_cpu = hostdata.cpu_total
                if hostdata.memory_total > self._max_memory:
                    self._max_memory = hostdata.memory_total
                hostdata.norm_cpu_total = 0.0
                hostdata.norm_cpu_free = 0.0
                hostdata.norm_memory_total = 0.0
                hostdata.norm_memory_free = 0.0
    
            if self._max_cpu <= 0 or self._max_memory <= 0:
                raise CannotNormalizeException()
            
            for hostname, hostdata in self._hosts_info.items():
                hostdata.norm_cpu_free = (1.0 * hostdata.cpu_free) / self._max_cpu
                hostdata.norm_cpu_total = (1.0 * hostdata.cpu_total) / self._max_cpu
                hostdata.norm_memory_free = (1.0 * hostdata.memory_free) / self._max_memory
                hostdata.norm_memory_total = (1.0 * hostdata.memory_total) / self._max_memory
        else:
            for hostname, hostdata in self._hosts_info.items():
                hostdata.norm_cpu_free = 1.0
                hostdata.norm_cpu_total = 1.0
                hostdata.norm_memory_free = 1.0
                hostdata.norm_memory_total = 1.0
            
        return True

    def euclid_normalized_resources_free(self, host_id):
        host = self._hosts_info[host_id]
        return calculate_euclid_resources(host.norm_memory_free, host.norm_cpu_free)
    
    def euclid_normalized_resources_total(self, host_id):
        host = self._hosts_info[host_id]
        return calculate_euclid_resources(host.norm_memory_total, host.norm_cpu_total)

    def get_vms(self):
        vms = []
        for h_id, h in self._hosts_info.items():
            vms = vms + h.vm_list[:]
        return vms

    def get_vm_ids(self):
        vmids = []
        for h_id, h in self._hosts_info.items():
            vmids = vmids + [ vm.id for vm in h.vm_list ]
        return vmids

    def remove_vms(self, vmids = []):
        for h_id, h in self._hosts_info.items():
            for vmid in vmids:
                vm = h.get_vm_byid()
                if vm is not None:
                    h.remove_vm(vm)

    def __ne__(self, hi):
        return not self.__eq__(hi)

    def __eq__(self, hi):
        for h_id, h_mine in self._hosts_info.items():
            if h_id not in hi._hosts_info:
                return False
            
            h_other = hi._hosts_info[h_id]
            for vm in h_mine.vm_list:
                vmid_mine = vm.id
                
                has_vm = False
                for vm_other in h_other.vm_list:
                    if vm_other.id == vmid_mine:
                        has_vm = True
                        break
                    
                if not has_vm:
                    return False
                
        for h_id, h_other in hi._hosts_info.items():
            if h_id not in self._hosts_info:
                return False
            
            h_mine = self._hosts_info[h_id]
            for vm in h_other.vm_list:
                vmid_other = vm.id
                
                has_vm = False
                for vm_mine in h_mine.vm_list:
                    if vmid_other == vm_mine.id:
                        has_vm = True
                        break
                    
                if not has_vm:
                    return False
                
        return True        
    
    def clone(self):
        nhi = HostsInfo(self._hosts_info)
        nhi._max_memory = self._max_memory
        nhi._max_cpu = self._max_cpu
        return nhi
    
    def __init__(self, dictionary):
        self._hosts_info = copy.deepcopy(dictionary)
        self._max_cpu = None
        self._max_memory = None
        
    def __getitem__(self, i):
        return self._hosts_info[i]
    
    def __setitem__(self, i, itm):
        self._hosts_info[i] = itm
    
    def items(self):
        return self._hosts_info.items()
    
    def keys(self):
        return self._hosts_info.keys()
    
    def make_movement(self, vm_movement):
        h_src = vm_movement.host_src
        h_dst = vm_movement.host_dst

        vm = self._hosts_info[h_src].get_vm_byid(vm_movement.vmid)
        self._hosts_info[h_src].remove_vm(vm)
        self._hosts_info[h_dst].add_vm(vm)
        
        vm.hostname = h_dst

        if (self._max_cpu > 0) and (self._max_memory > 0):
            # We'll recalculate the normalized values
            for h in [ h_src, h_dst ]:
                hostdata = self._hosts_info[h]
                hostdata.norm_cpu_free = (1.0 * hostdata.cpu_free) / self._max_cpu
                hostdata.norm_cpu_total = (1.0 * hostdata.cpu_total) / self._max_cpu
                hostdata.norm_memory_free = (1.0 * hostdata.memory_free) / self._max_memory
                hostdata.norm_memory_total = (1.0 * hostdata.memory_total) / self._max_memory
        
    def dump_info(self):
        res = []
        count = 0
        for hostname, hostdata in self._hosts_info.items():
            res.append("--- %s" % hostdata)
            
            if len(hostdata.vm_list) == 0:
                count = count + 1
            
            for vm in hostdata.vm_list:
                res.append("%s" % vm)
            
        res.append("%d nodes can be powered off" % count)
        return "\n".join(res)
    
    def fancy_dump_info(self, max_vms = 0, pad_info = -1):
        res = []
        
        max_vmid = 0
        if max_vms == 0:
            max_vms = 0
            for h_id, h in self._hosts_info.items():
                max_vms = max(len(h.vm_list), max_vms)
                for vm in h.vm_list:
                    max_vmid = max(max_vmid, vm.id)

        if pad_info == -1:
            pad_info = len("%s" % max_vmid)
            
        fmt_str = ".%%%ds" % pad_info
        
        empty_count = 0
        for h_id, h in self._hosts_info.items():
            h_out = ""
            for vm in h.vm_list:
                h_out = h_out + fmt_str % vm.id
                
            h_out = h_out + (fmt_str % "")*(max_vms - len(h.vm_list)) + "."
            res.append(h_out)
            if len(h.vm_list) == 0:
                empty_count += 1
            
        return "|%s|%d/%d" % ("|".join(res), empty_count, len(self._hosts_info))
    
    def empty_hosts(self):
        empty_count = 0
        for h_id, h in self._hosts_info.items():
            vm_count = len(h.vm_list)
            if vm_count == 0: empty_count += 1
        return empty_count

    
class VMData:
    STATE_RUNNING = 0
    STATE_OTHER = 1
    STATE_MIGRATING = 2
    
    def __init__(self, _id, cpu, memory, original_hostname, keyw = {}):
        self.id = _id
        self.cpu = cpu
        self.memory = memory
        self.hostname = original_hostname
        self.keywords = keyw
        self.timestamp_state = 0                       # TODO: se puede quitar?
        self.state = self.STATE_RUNNING

    def clone(self):
        new_vm = VMData(self.id, self.cpu, self.memory, self.hostname, self.keywords.copy())
        new_vm.timestamp_state = self.timestamp_state
        new_vm.state = self.state
        return new_vm

    def __str__(self):
        return "id: %s; cpu: %f; memory: %.1f (hostname: %s)" % (self.id, self.cpu, self.memory, self.hostname)

class VMMigration:
    def __init__(self, vmid, host_src, host_dst, cost, reward):
        self.vmid = vmid
        self.host_src = host_src
        self.host_dst = host_dst
        self.cost = cost
        self.reward = reward
    def __str__(self):
        return "vm [%s] from [%s] to [%s] with cost [%f] and reward [%f]" % (self.vmid, self.host_src, self.host_dst, self.cost, self.reward)

class Evaluated_VMMigration_List:
    def _sum_cost_and_reward_from_list(self):
        self.cost = 0
        self.reward = 0
        for mig in self.migration_list:
            self.cost += mig.cost
            self.reward += mig.reward
    
    def __init__(self, migration_list):
        self.migration_list = migration_list[:]
        self._sum_cost_and_reward_from_list()

    def __str__(self):
        retval = "cost: %f; reward: %f; " % (self.cost, self.reward)
        return retval
        # return "vm [%s] from [%s] to [%s] with cost [%f] and reward [%f]" % (self.vmid, self.host_src, self.host_dst, self.cost, self.reward)
    
class Defragger_Base():
    def __init__(self):
        self._can_use_empty_hosts_as_destination=False
        
    def can_use_empty_hosts_as_destination(self, can_use):
        retval = self._can_use_empty_hosts_as_destination
        self._can_use_empty_hosts_as_destination = can_use
        return retval
    
    def _make_migrations(self, hosts_info, migration_list):
        if len(migration_list) > 0:
            for vm_movement in migration_list:
                logging.info("%s" % vm_movement)
                # str_before = "\n[%s] %s\n[%s] %s" % (vm_movement.host_src, hosts_info[vm_movement.host_src].norm_str(), vm_movement.host_dst, hosts_info[vm_movement.host_dst].norm_str())
                #logging.debug("hosts before: %s" % str_before)
                hosts_info.make_movement(vm_movement)
                # str_after = "\n[%s] %s\n[%s] %s" % (vm_movement.host_src, hosts_info[vm_movement.host_src].norm_str(), vm_movement.host_dst, hosts_info[vm_movement.host_dst].norm_str())
                # logging.debug("hosts after: %s" % str_after)
            return True
        
        return False

    def prefilter_possible_destinations(self, hosts_info):
        '''
        obtains the list of identifiers that are candidate to be destinations for the vms
        
        # currently we are returning all the hosts, but e.g. we could also remove disabled
          hosts or remove the most consuming ones, etc.
        '''
        destination_hosts = hosts_info.keys()
        return destination_hosts

    def filter_hosts_to_empty(self, hosts_info, hosts_to_empty, fixed_vms):
        '''
        @return a list of the hosts whose vms are likely to be migrated
            * e.g. we could remove some nodes that are disabled in configuration
            
        # the default implementation returns those nodes that have vms to empty
        '''
        now = cpyutils.eventloop.now()
        
        # disabled_hosts = [ x.strip() for x in config.config_vmca.DISABLED_HOSTS.split(",") ]
        disabled_hosts = config.config_vmca.DISABLED_HOSTS

        filtered_out = []
        filtered_hosts_to_empty = []
        for h_id in hosts_to_empty:
            if h_id in disabled_hosts:
                logging.debug("host %s is disabled so will not move its vms" % h_id)
                continue
            
            h = hosts_info[h_id]
            
            if len(h.vm_list) > 0:
                has_fixed_or_unstable_vms = False
                for vm in h.vm_list:
                    if vm.id in fixed_vms:
                        has_fixed_or_unstable_vms = True
                        break
                    if (vm.state == VMData.STATE_RUNNING) and ((now - vm.timestamp_state) < config.config_vmca.STABLE_TIME):
                        has_fixed_or_unstable_vms = True
                        filtered_out.append(h_id)
                        break
                    
                if not has_fixed_or_unstable_vms:
                    filtered_hosts_to_empty.append(h_id)

        if len(filtered_out) > 0:
            logging.debug("filtering out node/s %s because has/have unstable VMs" % ",".join(filtered_out))
            
        
        return filtered_hosts_to_empty
        
        # return [ h_id for h_id in hosts_to_empty if (len(hosts_info[h_id].vm_list) > 0) ]

    def refilter_hosts_to_empty(self, hosts_info, current_node_id, filtered_hosts_to_empty, vm_migration_list):
        '''
        filters the hosts to empty whenever a migration happens
        
        # currently it removes the current node (because it has been treated) and the nodes that have been the destination
        # of a migration, because these nodes will not be stable now.
        
        * in other cases it may remove the current node only if all its vms have been migrated
        
        '''
        refiltered_hosts_to_empty = filtered_hosts_to_empty[:]
        
        if (current_node_id in refiltered_hosts_to_empty) and ((len(vm_migration_list)==0) or ((len(hosts_info[current_node_id].vm_list) == 0) and (len(vm_migration_list)>0))):
            logging.debug("removing host %s from possible destinations because we have just moved its vms" % current_node_id)
            refiltered_hosts_to_empty.remove(current_node_id)
        
        for vm_movement in vm_migration_list:
            if vm_movement.host_dst in refiltered_hosts_to_empty:
                logging.debug("removing host %s from possible destinations because it is not stable (it has just received a VM)" % vm_movement.host_dst)
                refiltered_hosts_to_empty.remove(vm_movement.host_dst)
                
        return refiltered_hosts_to_empty

    def filter_migrations_for_host(self, hosts_info, host_id, migration_list):
        '''
        evaluates and sorts by priority the migration list when dealing with host hosts_info

        * currently we'll accept only those migrations that emtpy the host
        
        @return a list of migrations that are confirmed to be appropriate
        '''
        host = hosts_info[host_id]
        if len(migration_list) != len(host.vm_list):
            # logging.debug("dropping migration list for node %s because it does not empty the node (moves %d out of %d vms)" % (host_id, len(migration_list), len(host.vm_list)))
            return []
        
        # logging.debug("all the vms from %s can be migrated to other nodes" % host_id)
        return migration_list

    def schedule_vm(self, hosts_info, candidates, vmdata):
        '''
        This function makes the connection to the SCHEDULER
        @return the host which is most appropriate to host the vm stated by vmdata
        '''
        for h_id in candidates:
            h = hosts_info[h_id]
            if h.vm_can_fit(vmdata):
                return h_id
            
        return None

    def get_cost_estimation_for_migration(self, host_info, vmdata, host_dst):
        return vmdata.memory

    def get_reward_for_migration(self, host_info, vmdata, host_dst):
        return 0

    def evaluate_migration(self, host_info, vmdata, host_dst):
        '''
        @return a VMMigration object in which the migration of vm vmdata from the host in which it
            is hosted to host_dst, with the cost of the migration and the reward for migratin making
            the migration is calculated
        '''
        cost_of_migration = self.get_cost_estimation_for_migration(host_info, vmdata, host_dst)
        reward_for_migration = self.get_reward_for_migration(host_info, vmdata, host_dst)
        return VMMigration(vmdata.id, vmdata.hostname, host_dst, cost_of_migration, reward_for_migration)
    
    def filter_destinations_for_vm(self, hosts_info, possible_destinations, vmdata):
        '''
        obtains a list of identifiers of the candidates to be the host for one vm
        
        # currently we are returning the identifiers of the other nodes that are not the one
          who hosts the vm, and are hosting at least one VM

        * other defraggers may consider to include the possibility of considering that node
          in which a vm is hosted is the most appropriate for that vm.

        * other use e.g. we can get out those nodes that are offline, or include the nodes that are
          offline and are likely to host that VM
        '''
        if self._can_use_empty_hosts_as_destination:
            return [ h_id for h_id in possible_destinations if (h_id != vmdata.hostname) ]
        else:
            return [ h_id for h_id in possible_destinations if (h_id != vmdata.hostname) and (len(hosts_info[h_id].vm_list) > 0) ]

    def _sort_vms(self, vm_list):
        '''
        This method sorts the VMs prior to scheduling them. This default implementation performs a FFd on the resources of the VM
        '''
        return vm_list[:]
        vm_list_evaluated = []
        for vm in vm_list:
            vm_list_evaluated.append((calculate_euclid_resources(vm.memory, vm.cpu),vm))

        vm_list_evaluated.sort(key = lambda x: x[0], reverse = False)
        sorted_vm_list = [ vm for (_, vm) in vm_list_evaluated ]
        
        return sorted_vm_list

    def schedule_vms_from_host(self, hosts_info, node_id, filtered_destination_candidate_hosts, fixed_vms = [], make_movements = False):
        '''
        This method schedules the VMs from one host to the other hosts in the platform, whose identifiers are included in filtered_destination_candidate_hosts
        - It enables to make the movements over the hosts_info structure, to take into account the eventual changes on the allocation of the resources
            * The original workflow consists of passing a clone of the hosts_info and making movements over it, to take into account changes in the allocation of resources.
              Then the set of migrations is returned in the "order that they should be done", and the effective movements are made over the real hosts_info structure
              
            * It is used the scheduler of the underlying system (do not know which scheduler: ONE, OpenStack, etc. nor the policy), so there is no control over the
              scheduling of the VMs on the hosts.
              
        # Separating this method allows us to overload it and enable FF, BT or whatever method to redistribute the VMs
        '''
        # We'd simmulate the movements are they are called, to test whether there is enough vms or not to fit ALL the VMs
        # (the VMs would allocate CPU and Memory in their destinations, and we cannot suppose that there will be enough space
        # for all the VMs from current_node_id)
        host = hosts_info[node_id]
        migration_list = []
        
        # We'd copy the vm_list to be able to modify the host vm list as VMs are migrated (it is a swallow copy because we need that the vms are the same)
        host_vm_list = self._sort_vms(host.vm_list)

        for vm in host_vm_list:
            if vm.id not in fixed_vms:
                possible_destinations_for_vm = self.filter_destinations_for_vm(hosts_info, filtered_destination_candidate_hosts, vm)
                destination_host = self.schedule_vm(hosts_info, possible_destinations_for_vm, vm)
    
                # logging.debug("destination host for %s is %s" % (vm.id, destination_host))            
                if (destination_host is not None):
                    vm_migration = self.evaluate_migration(hosts_info, vm, destination_host)
                    if vm_migration is not None:
                        migration_list.append(vm_migration)
                        if make_movements:
                            hosts_info.make_movement(vm_migration)
                else:
                    logging.debug("could not find a new place for vm %s" % vm.id)
        
        return migration_list

    def defrag(self, _hosts_info, hosts_fixed = [], vms_fixed = []):
        """
        @description Obtains the minimum movements needed to obtain the best
            defragmentation of the resources, and the maximum amount of hosts
            that have no VM hosted (they would be candidates to be powered off)
        @param hosts_info is a dictionary that contains HostData structures for
            each host available in the system. The index is the identifier of
            the host
        @param candidate_hosts is a list that contains the identifiers of the
            hosts whose virtual machines are likely to be moved
    
        @return a migration plan that consists of an array of array of VMMigration objects
        """
        return []