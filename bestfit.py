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
    