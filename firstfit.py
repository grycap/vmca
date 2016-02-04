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

MAX_ITERATIONS=-1

class SelectHost_FF:
    def _sort_hosts_to_move_vms(self, hosts_info, candidates, reverse = False):
        '''
        @returns a list of pairs (rank, node_id) where node_id is in candidates and fits the vm
            and the rank indicates the order in which the nodes are taken
        '''
        suitable_nodes = []
        i = 0
        for h_id in candidates:
            h = hosts_info[h_id]
            if len(h.vm_list)>0:
                value = -i
                if reverse:
                    value = -value
                suitable_nodes.append((-i, h_id))
                i += 1
        return suitable_nodes
        
    def get_host_to_move_its_vms(self, hosts_info, candidates):
        suitable_nodes = self._sort_hosts_to_move_vms(hosts_info, candidates)

        if len(suitable_nodes) > 0:                
            suitable_nodes.sort(key = lambda x: x[0], reverse = True)
            return suitable_nodes[0][1]

        return None

class SelectHost_MoreVMs_First(SelectHost_FF):
    def _sort_hosts_to_move_vms(self, hosts_info, candidates, reverse = False):
        suitable_nodes = []
        for h_id in candidates:
            h = hosts_info[h_id]
            if len(h.vm_list)>0:
                value = len(h.vm_list)
                if reverse:
                    value = -value
                suitable_nodes.append((value, h_id))
        return suitable_nodes

class SelectHost_LessVMs_First(SelectHost_MoreVMs_First):
    def _sort_hosts_to_move_vms(self, hosts_info, candidates):
        return SelectHost_MoreVMs_First._sort_hosts_to_move_vms(self, hosts_info, candidates, True)

class SelectHost_MoreUsedResources_First(SelectHost_FF):
    def _sort_hosts_to_move_vms(self, hosts_info, candidates, reverse = False):
        suitable_nodes = []
        for h_id in candidates:
            h = hosts_info[h_id]
            if len(h.vm_list)>0:
                resource_t = hosts_info.euclid_normalized_resources_total(h.hostname)
                resource_f = hosts_info.euclid_normalized_resources_free(h.hostname)
                value = ((resource_t - resource_f) / resource_t)
                if reverse:
                    value = -value
                suitable_nodes.append((value, h_id))
                
        return suitable_nodes

class SelectHost_LessUsedResources_First(SelectHost_MoreUsedResources_First):
    def _sort_hosts_to_move_vms(self, hosts_info, candidates, reverse = False):
        return SelectHost_MoreUsedResources_First._sort_hosts_to_move_vms(self, hosts_info, candidates, True)

class Defragger_FF(defragger.Defragger_Base):

    def get_host_to_move_its_vms(self, hosts_info, candidates):
        '''
        @returns the identifier of the node to deal with
            e.g. we could remove the node that is consuming more energy, the node that has less vms, etc.
            
        # the default implementation returns the first node that has VMs (or None if there is not any
          host with vms)
        '''
        
        for candidate in candidates:
            h = hosts_info[candidate]
            if len(h.vm_list) > 0:
                return candidate
        
        return None

    def defrag(self, _hosts_info, hosts_fixed = [], fixed_vms = []):
        # First of all we create a copy to not to modify the original structure
        hosts_info = _hosts_info.clone()
        hosts_info.normalize_resources()
        
        hosts_to_empty = [ x for x in _hosts_info.keys() if x not in hosts_fixed ]
        
        migration_plan = []
        
        # * 1 we filter the list to remove those hosts that are disabled in config, etc.
        filtered_hosts_to_empty = self.filter_hosts_to_empty(hosts_info, hosts_to_empty, fixed_vms)
        filtered_destination_candidate_hosts = self.prefilter_possible_destinations(hosts_info)

        iteration = 0
        continue_moving = True
        
        while continue_moving:
            # * 2 we select the node to try to move its vms
            current_node_id = self.get_host_to_move_its_vms(hosts_info, filtered_hosts_to_empty)
            
            if current_node_id is None:
                logging.debug("no node was selected to move its vms")
                return migration_plan
            
            logging.debug("trying to move vms from node %s" % current_node_id)
            
            # * 3 we re-schedule the vms from the host
            migration_list = self.schedule_vms_from_host(hosts_info.clone(), current_node_id, filtered_destination_candidate_hosts, fixed_vms, True)

            '''
            * We have an evaluated migration_list, so we can make FF or BF or FFd or BFd
                * FF implementation: take the migration list as-is and consider to make the movements
                * BF implementation: sort the migration list according to the cost or the reward, or a combination of them.
              
              Anyway it may have no sense, because all the migrations will be carried out, but some degree of importance is introduced here
            '''
            
            # Inside this function we check whether the migration is acceptable because we are First-fitting just in case that we can empty the node
            migration_list = self.filter_migrations_for_host(hosts_info, current_node_id, migration_list)
            
            self._make_migrations(hosts_info, migration_list)

            # We store the the migration list in different rows, to enable the tracking of the different iterations of the algorithm
            migration_plan.append(migration_list)
                    
            filtered_hosts_to_empty = self.refilter_hosts_to_empty(hosts_info, current_node_id, filtered_hosts_to_empty, migration_list)
            
            iteration += 1
            if MAX_ITERATIONS > 0:
                continue_moving = ((len(filtered_hosts_to_empty) != 0) and (iteration < MAX_ITERATIONS))
            else:
                continue_moving = (len(filtered_hosts_to_empty) != 0) 

        return migration_plan
    
class Defragger_Distribute(defragger.Defragger_Base):
    
    def defrag(self, _hosts_info, hosts_fixed = [], fixed_vms = []):
        # First of all we create a copy to not to modify the original structure
        hosts_info = _hosts_info.clone()
        hosts_info.normalize_resources()
        
        hosts_to_empty = [ x for x in _hosts_info.keys() if x not in hosts_fixed ]
        
        migration_plan = []
        
        # * 1 we filter the list to remove those hosts that are disabled in config, etc.
        filtered_hosts_to_empty = self.filter_hosts_to_empty(hosts_info, hosts_to_empty, fixed_vms)
        filtered_destination_candidate_hosts = self.prefilter_possible_destinations(hosts_info)

        iteration = 0
        continue_moving = True

        # TODO:
        # basicamente habria que hacer lo siguiente:
        '''
        
        1. calcular el "indice de estabilidad" para todos los nodos
        2. coger el nodo mas desfavorable
        3. coger la maquina que quitandola conseguiriamos mas estabilidad en el nodo
        4. planificarla en otro nodo
        5. ver que indice de estabilidad se consigue
        6. si seria peor, finalizamos
        
        Este algoritmo se puede refinar, evidentemente... es solo la primera aproximacion
        * variaciones:
            - probar distintas maquinas del nodo y ver cual consigue mas mejora de la situacion
                (best-fit de maquinas)
            - empezar por distintos nodos
                (best-fit de nodos)
                + este se podria combinar con el anterior
        
        '''

        return migration_plan
