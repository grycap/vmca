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
import defragger
import logging

class Scheduler_FF:
    def _sort_hosts_to_schedule(self, hosts_info, candidates, vmdata):
        '''
        @returns a list of pairs (rank, node_id) where node_id is in candidates and fits the vm
            and the rank indicates the order in which the nodes are taken
        '''
        suitable_nodes = []
        i = 0
        for h_id in candidates:
            h = hosts_info[h_id]
            if h.vm_can_fit(vmdata):
                suitable_nodes.append((-i, h_id))
                i += 1
        return suitable_nodes
        
    def schedule_vm(self, hosts_info, candidates, vmdata):
        '''
        @return the host which is most appropriate to host the vm stated by vmdata
        '''

        suitable_nodes = self._sort_hosts_to_schedule(hosts_info, candidates, vmdata)

        if len(suitable_nodes) > 0:                
            suitable_nodes.sort(key = lambda x: x[0], reverse = True)
            return suitable_nodes[0][1]
        
        return None

class Scheduler_Packing(Scheduler_FF):
    def _sort_hosts_to_schedule(self, hosts_info, candidates, vmdata):
        '''
        @returns a list of pairs (rank, node_id) where node_id is in candidates and fits the vm
        '''
        suitable_nodes = []
        for h_id in candidates:
            h = hosts_info[h_id]
            if h.vm_can_fit(vmdata):
                suitable_nodes.append((len(h.vm_list), h_id))
        return suitable_nodes

class Scheduler_Stripping(Scheduler_FF):
    def _sort_hosts_to_schedule(self, hosts_info, candidates, vmdata):
        '''
        @returns a list of pairs (rank, node_id) where node_id is in candidates and fits the vm
        '''
        suitable_nodes = []
        for h_id in candidates:
            h = hosts_info[h_id]
            if h.vm_can_fit(vmdata):
                suitable_nodes.append((-len(h.vm_list), h_id))
        return suitable_nodes

class Scheduler_Load(Scheduler_FF):
    def _sort_hosts_to_schedule(self, hosts_info, candidates, vmdata):
        '''
        @returns a list of pairs (rank, node_id) where node_id is in candidates and fits the vm
        '''
        suitable_nodes = []
        for h_id in candidates:
            h = hosts_info[h_id]
            if h.vm_can_fit(vmdata):
                f_cpu = 0.0
                if 'FREE_CPU' in h.keywords:
                    try:
                        f_cpu = float(h.keywords['FREE_CPU'])
                    except:
                        f_cpu = 0.0
                    suitable_nodes.append((f_cpu, h_id))
                else:
                    logging.warning("trying to use FREE_CPU as rank, but the host does not have such keyword. Setting FREE_CPU as zero")
                    
                suitable_nodes.append((f_cpu, h_id))
        return suitable_nodes

'''
class Reward_VMCount():
    def get_reward_for_migration(self, host_info, vmdata, host_dst):
        h_dst = host_info[host_dst]
        return len(h_dst.vm_list)+1

class Reward_Efficiently_used_resources():
    def get_reward_for_migration(self, hosts_info, vmdata, host_dst):
        host_src = vmdata.hostname
        
        # Move VM to the destination host and check
        hosts_info.make_movement(VMMigration(vmdata, host_src, host_dst, 0, 0))
        
        resource_t = hosts_info.euclid_normalized_resources_total(host_dst)
        resource_f = hosts_info.euclid_normalized_resources_free(host_dst)
        value = ((resource_t - resource_f) / resource_t)

        # Move back the VM to where it was
        hosts_info.make_movement(VMMigration(vmdata, host_dst, host_src, 0, 0))
        
        return value

class Reward_used_resources_per_vm():
    def get_reward_for_migration(self, hosts_info, vmdata, host_dst):
        host_src = vmdata.hostname

        # Move VM to the destination host and check
        hosts_info.make_movement(VMMigration(vmdata, host_src, host_dst, 0, 0))

        resource_t = hosts_info.euclid_normalized_resources_total(host_dst)
        resource_f = hosts_info.euclid_normalized_resources_free(host_dst)
        value = ((resource_t - resource_f) / float(len(hosts_info.vm_list)))
        
        # Move back the VM to where it was
        hosts_info.make_movement(VMMigration(vmdata, host_dst, host_src, 0, 0))

        return value
'''