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
import firstfit
import logging
import math

class MigrationList_Length():
    def _reevaluate_migration_lists(self, hosts_info, possible_migration_lists):
        for evaluated_migration_list in possible_migration_lists:
            evaluated_migration_list.reward = len(evaluated_migration_list.migration_list)

class MigrationList_Variance():
    def get_reward_for_migration(self, hosts_info, vmdata, host_dst):
        # This is simply to speedup the calculations
        return 0

    def _reevaluate_migration_lists(self, hosts_info, possible_migration_lists):
        for evaluated_migration_list in possible_migration_lists:
            
            # We clone the hosts_info data structure to simmulate the list of migrations
            working_hosts_info = hosts_info.clone()
            self._make_migrations(working_hosts_info, evaluated_migration_list.migration_list)
            
            # Now we calculate the standard deviation of the resources after the migrations and set it as reward for the list,
            # instead of the sum of rewards of the migrations
            S_2 = defragger.calc_variance(working_hosts_info)

            # Less S_2 means more reward
            evaluated_migration_list.reward = -S_2
    
class Defragger_BF(firstfit.Defragger_FF):
    def _best_fit_migration(self, hosts_info, possible_migration_list, reverse = False):
        '''
        # currently we return the first migration plan (FF)
        '''
        if len(possible_migration_list) > 0:
            return possible_migration_list[0].migration_list
        
        return []

    def _reevaluate_migration_lists(self, hosts_info, possible_migration_lists):
        '''
        This function would correct the values for the cost and the reward of the vmmigration list, in case that it is needed
        e.g. will raise the cost of a migration if it implies powering on nodes or will raise the reward if the migration gets
            a node empty.
        '''
        pass

    def refilter_hosts_to_empty(self, hosts_info, current_node_id, filtered_hosts_to_empty, vm_migration_list):
        
        refiltered_hosts_to_empty = filtered_hosts_to_empty[:]
        
        if len(vm_migration_list) > 0:
            vm_movement = vm_migration_list[0]
            current_node_id = vm_movement.host_src
            refiltered_hosts_to_empty = firstfit.Defragger_FF.refilter_hosts_to_empty(self, hosts_info, current_node_id, filtered_hosts_to_empty, vm_migration_list)                
                
        return refiltered_hosts_to_empty
        

        '''        
        refiltered_hosts_to_empty = filtered_hosts_to_empty[:]
        
        if len(vm_migration_list) > 0:
            vm_movement = vm_migration_list[0]
            if vm_movement.host_src in refiltered_hosts_to_empty:
                refiltered_hosts_to_empty.remove(vm_movement.host_src)
                
        return refiltered_hosts_to_empty
        '''

        # self.__class__.__bases__[0].refilter_possible_destinations(self, hosts_info, current_node_id, filtered_hosts_to_empty, vm_migration_list)
    
    def defrag(self, _hosts_info, hosts_fixed = [], fixed_vms = []):
        # First of all we create a copy to not to modify the original structure
        hosts_info = _hosts_info.clone()
        hosts_info.normalize_resources()
        
        hosts_to_empty = [ x for x in _hosts_info.keys() if x not in hosts_fixed ]
        
        migration_plan = []
        
        # * 1 we filter the list to remove those hosts that are disabled in config, etc.
        filtered_hosts_to_empty = self.filter_hosts_to_empty(hosts_info, hosts_to_empty, fixed_vms)
        filtered_destination_candidate_hosts = self.prefilter_possible_destinations(hosts_info)

        continue_moving = True
        while continue_moving:

            possible_migration_lists = []
            
            for current_node_id in filtered_hosts_to_empty:
                
                # * 3 we re-schedule the vms from the host
                migration_list = self.schedule_vms_from_host(hosts_info.clone(), current_node_id, filtered_destination_candidate_hosts, fixed_vms, True)
    
                # We check whether the migration is acceptable because we are First-fitting just in case that we can empty the node
                migration_list = self.filter_migrations_for_host(hosts_info, current_node_id, migration_list)
                if len(migration_list) > 0:
                    possible_migration_lists.append(defragger.Evaluated_VMMigration_List(migration_list))
                
            # First we correct the costs and rewards of the possible migration lists (e.g. more reward if a migration gets a node empty or
            # more cost if it implies powering on a node)
            self._reevaluate_migration_lists(hosts_info, possible_migration_lists)
            
            # Now we "best fit" on the node to empty, according to the cost, reward or whatever
            migration_list = self._best_fit_migration(hosts_info, possible_migration_lists)
                    
            self._make_migrations(hosts_info, migration_list)
            # We store the the migration list in different rows, to enable the tracking of the different iterations of the algorithm
            migration_plan.append(migration_list)
                    
            # The current_node_id is now None, because is a migration list that "does not obbey to empty one host"
            filtered_hosts_to_empty = self.refilter_hosts_to_empty(hosts_info, None, filtered_hosts_to_empty, migration_list)
            continue_moving = (len(migration_list) > 0)

        return migration_plan
    
class Defragger_BF_Cost(Defragger_BF):
    def _best_fit_migration(self, hosts_info, possible_migration_list, _reverse = False):
        if len(possible_migration_list) > 0:
            # Less cost first
            possible_migration_list.sort(key = lambda x: x.cost, reverse = _reverse)
            return possible_migration_list[0].migration_list
        return []

class Defragger_BFd_Cost(Defragger_BF_Cost):
    def _best_fit_migration(self, hosts_info, possible_migration_list):
        return Defragger_BF_Cost._best_fit_migration(self, hosts_info, possible_migration_list, True)

class Defragger_BF_Reward(Defragger_BF):
    def _best_fit_migration(self, hosts_info, possible_migration_list, _reverse = False):
        if len(possible_migration_list) > 0:
            # Greater reward first
            possible_migration_list.sort(key = lambda x: x.reward, reverse = not _reverse)
            return possible_migration_list[0].migration_list
        return []
    
class Defragger_BFd_Reward(Defragger_BF_Reward):
    def _best_fit_migration(self, hosts_info, possible_migration_list):
        return Defragger_BF_Reward._best_fit_migration(self, hosts_info, possible_migration_list, True)
    
class Defragger_BF_Reward_per_Cost(Defragger_BF):
    def _best_fit_migration(self, hosts_info, possible_migration_list, _reverse = False):
        if len(possible_migration_list) > 0:
            # Greater reward per cost first
            possible_migration_list.sort(key = lambda x: (x.reward/x.cost), reverse = not _reverse)
            return possible_migration_list[0].migration_list
        return []

class Defragger_BFd_Reward_per_Cost(Defragger_BF_Reward_per_Cost):
    def _best_fit_migration(self, hosts_info, possible_migration_list):
        return Defragger_BF_Reward_per_Cost._best_fit_migration(self, hosts_info, possible_migration_list, True)
    
class Defragger_BF_Cost_per_Reward(Defragger_BF):
    def _best_fit_migration(self, hosts_info, possible_migration_list, _reverse = False):
        if len(possible_migration_list) > 0:
            # Greater reward per cost first
            possible_migration_list.sort(key = lambda x: (x.cost/x.reward), reverse = not _reverse)
            return possible_migration_list[0].migration_list
        return []
    
class Defragger_BFd_Cost_per_Reward(Defragger_BF_Cost_per_Reward):
    def _best_fit_migration(self, hosts_info, possible_migration_list):
        return Defragger_BF_Cost_per_Reward._best_fit_migration(self, hosts_info, possible_migration_list, True)
    
class Defragger_Distribute(defragger.Defragger_Base):
    def _migration_enhancement(self, r_mean, hosts_info, h_id, res_amount):
        free_before = hosts_info.euclid_normalized_resources_free(h_id)
        distance_to_mean_before = math.fabs(r_mean - free_before)
        distance_to_mean_after = math.fabs(r_mean - (free_before + res_amount))
        return distance_to_mean_before - distance_to_mean_after

    def defrag(self, _hosts_info, hosts_fixed = [], fixed_vms = []):
        hosts_info = _hosts_info.clone()
        hosts_info.normalize_resources()
        hosts_to_empty = [ x for x in _hosts_info.keys() if x not in hosts_fixed ]
        
        migration_plan = []
        
        # * 1 we filter the list to remove those hosts that are disabled in config, etc.
        filtered_hosts_to_empty = self.filter_hosts_to_empty(hosts_info, hosts_to_empty, fixed_vms)
        filtered_destination_candidate_hosts = self.prefilter_possible_destinations(hosts_info)

        # Now we'll calculate the mean of free resources (we want to homogeinize the distance to the mean)
        r_total = 0.0
        n_count = float(len(hosts_info.keys()))
        for h_id in hosts_info.keys():
            r_total += float(hosts_info.euclid_normalized_resources_free(h_id))

        r_mean = r_total / n_count

        possible_migrable_vm = []
        for h_id, host in hosts_info.items():
            for vm in host.vm_list[:]:
                if vm.id not in fixed_vms:
                    vm_norm_res = hosts_info.calculate_euclid_normalized_resources(vm.memory, vm.cpu)
                    possible_migrable_vm.append((vm, vm_norm_res))
        
        possible_migrable_vm = sorted(possible_migrable_vm, key = lambda x: x[1], reverse=False)

        # For each VM, we'll try to find a new destination
        continue_moving = True
        migration_list = []
        while continue_moving:
            migration_selected = None
            while (len(possible_migrable_vm) > 0) and (migration_selected is None):
                vm, vm_norm_res = possible_migrable_vm.pop(0)

                # If moving the VM puts more distance to the mean, we'll keep the VM in the host
                if self._migration_enhancement(r_mean, hosts_info, vm.hostname, vm_norm_res) < 0:
                    continue

                # Now let's find one destination
                possible_destinations = []
                for h_id, host in hosts_info.items():
                    if (not host.has_vm(vm)) and host.vm_can_fit(vm):

                        # If moving the VM to the hosts makes that the distance to the mean is less, we'll consider the movement
                        enhancement = self._migration_enhancement(r_mean, hosts_info, h_id, -vm_norm_res)
                        if enhancement > 0:
                            possible_destinations.append((h_id, float(hosts_info.euclid_normalized_resources_free(h_id)) - enhancement))
                
                # If moving the VM to other host enhances the distribution, we'll select the first movement
                if len(possible_destinations) > 0:
                    possible_destinations = sorted(possible_destinations, key = lambda x: x[1], reverse=True)
                    (h_id, enhancement) = possible_destinations.pop(0)
                    migration_selected = defragger.VMMigration(vm.id, vm.hostname, h_id, 0, enhancement)

            if migration_selected is not None:
                fixed_vms.append(migration_selected.vmid)
                migration_list.append(migration_selected)
                self._make_migrations(hosts_info, [ migration_selected ])
            else:
                continue_moving = False

        migration_plan.append(migration_list)
        return migration_plan

class Defragger_Refill(defragger.Defragger_Base):
    def _migration_enhancement(self, r_mean, hosts_info, h_id, res_amount):
        free_before = hosts_info.euclid_normalized_resources_free(h_id)
        distance_to_mean_before = math.fabs(r_mean - free_before)
        distance_to_mean_after = math.fabs(r_mean - (free_before + res_amount))
        return distance_to_mean_before - distance_to_mean_after

    def defrag(self, _hosts_info, hosts_fixed = [], fixed_vms = []):
        hosts_info = _hosts_info.clone()
        hosts_info.normalize_resources()
        hosts_to_empty = [ x for x in _hosts_info.keys() if x not in hosts_fixed ]
        
        migration_plan = []
        
        # * 1 we filter the list to remove those hosts that are disabled in config, etc.
        filtered_hosts_to_empty = self.filter_hosts_to_empty(hosts_info, hosts_to_empty, fixed_vms)
        filtered_destination_candidate_hosts = self.prefilter_possible_destinations(hosts_info)

        # Now we'll calculate the mean of free resources (we want to homogeinize the distance to the mean)
        r_total = 0.0
        n_count = float(len(hosts_info.keys()))
        for h_id in hosts_info.keys():
            r_total += float(hosts_info.euclid_normalized_resources_free(h_id))

        r_mean = r_total / n_count

        possible_migrable_vm = []
        hosts_resource_info = []
        for h_id, host in hosts_info.items():
            hosts_resource_info.append((h_id, hosts_info.euclid_normalized_resources_free(h_id)))
            for vm in host.vm_list[:]:
                if vm.id not in fixed_vms:
                    vm_norm_res = hosts_info.calculate_euclid_normalized_resources(vm.memory, vm.cpu)
                    possible_migrable_vm.append((vm, vm_norm_res))
        
        migration_list = []
        # for each host we'll try to move VMs to it, to get to the mean
        while len(hosts_resource_info) > 0:
            h_id, free_resources = hosts_resource_info.pop(0)
            host = hosts_info[h_id]

            continue_moving = True
            while continue_moving:
                possible_vms = []
                for (vm, vm_norm_res) in possible_migrable_vm:
                    # If moving the VM puts more distance to the mean, we'll keep the VM in the host
                    if self._migration_enhancement(r_mean, hosts_info, vm.hostname, vm_norm_res) < 0:
                        continue

                    if (not host.has_vm(vm)) and host.vm_can_fit(vm):
                        # If moving the VM to the hosts makes that the distance to the mean is less, we'll consider the movement
                        enhancement = self._migration_enhancement(r_mean, hosts_info, h_id, -vm_norm_res)
                        if enhancement > 0:
                            possible_vms.append((vm, float(hosts_info.euclid_normalized_resources_free(h_id)) - enhancement))

                if len(possible_vms) > 0:
                    possible_vms = sorted(possible_vms, key = lambda x: x[1], reverse=True)
                    (vm, enhancement) = possible_vms.pop(0)
                    migration_selected = defragger.VMMigration(vm.id, vm.hostname, h_id, 0, enhancement)
                    migration_list.append(migration_selected)
                    self._make_migrations(hosts_info, [ migration_selected ])

                    # Need to remove the VM from the possible migrable_vms
                    still_being_migrable = [ (vm_s, vm_norm_res_s) for (vm_s, vm_norm_res_s) in possible_migrable_vm if vm_s.id != vm.id]
                    possible_migrable_vm = still_being_migrable
                else:
                    continue_moving = False

        migration_plan.append(migration_list)
        return migration_plan