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

import logging
import cpyutils.eventloop
import time
import config

_LOGGER = logging.getLogger("[VMCA]")

def preprocess_hosts_info(hosts_dic):
    for hostname, hostdata in hosts_dic.items():
        hostdata.cpu = hostdata.cpu - config.config_vmca.SPARE_CPU
        hostdata.memory = hostdata.memory - config.config_vmca.SPARE_MEMORY
        hostdata.maxvms = config.MAX_VM

def postprocess_hosts_info(hosts_dic):
    for hostname, hostdata in hosts_dic.items():
        hostdata.cpu = hostdata.cpu + config.config_vmca.SPARE_CPU
        hostdata.memory = hostdata.memory + config.config_vmca.SPARE_MEMORY

import defragger
import schedule
import threading

# TODO: it is important to refurbish the execution of the migration plan, as it is not properly done
# - currently the execution of the migration plan has to wait for the defrag to be made
# - it should be independent
# - the lock is the key: there is no problem to cancel the migration plan
# - the migration plan should check whether to continue executing or not depending on the monitorization
# - the defrag should cancel or create a new migration plan

class Daemon(object):
    def elapsed(self):
        return self._timestamp_end_migration_plan - self._timestamp_start_migration_plan
    
    def __init__(self, current_defragger, deployment):
        self._defragger = current_defragger
        self._deployment = deployment
        self._hosts_info = None
        self._hosts_info_timestamp = 0
        self._migration_plan_event_id = None
        self._timestamp_start_migration_plan = 0
        self._timestamp_end_migration_plan = 0
        
    
        # The migration plan
        self._lock = threading.Lock()
        self._migration_plan = None
            
    def _cancel_migration_plan(self):
        self._migration_plan = None
        if self._migration_plan_event_id is not None:
            cpyutils.eventloop.get_eventloop().cancel_event(self._migration_plan_event_id)
            self._migration_plan_event_id = None
        self._timestamp_end_migration_plan = cpyutils.eventloop.now()
        
    def _start_migration_plan(self, migration_plan):
        self._migration_plan = migration_plan
        self._continue_migration_plan()
        self._timestamp_start_migration_plan = None
    
    def _continue_migration_plan(self):
        if self._migration_plan is not None:
            self._migration_plan_event_id = cpyutils.eventloop.get_eventloop().add_event(config.config_vmca.MIGRATION_PLAN_FREQUENCY, "Migration plan", callback = self.execute_migration_plan, arguments = [], stealth = True)
            
    def execute_migration_plan(self):
        self._lock.acquire()

        if not config.config_vmca.ENABLE_MIGRATION:
            _LOGGER.info("we are not executing the migration plan because of ENABLE_MIGRATION is disabled")
            self._cancel_migration_plan()
            self._lock.release()
            return
    
        new_hosts_info = self._monitor_hosts_info()
        if new_hosts_info != self._hosts_info:
            if self._migration_plan is not None:
                _LOGGER.warning("things have changed, so we are cancelling the migration plan")
                self._cancel_migration_plan()
                self._lock.release()
                return
    
        # Now that we have executed the event, there is not any event programmed
        self._migration_plan_event_id = None
        
        migrating_vms = self._deployment.get_migrating_vms()
        if len(migrating_vms) >= config.config_vmca.MAX_SIMULTANEOUS_MIGRATIONS:
            # _LOGGER.debug("skipping migration because the maximum number of simultaneous migrations has been reached")
            if (self._migration_plan is not None):
                self._continue_migration_plan()
            self._lock.release()
            return
    
        if config.config_vmca.MAX_SIMULTANEOUS_MIGRATIONS > 1:
            # TODO: give support
            _LOGGER.error("there is no support for more than one migration at once, now")
            self._lock.release()
            raise Exception()
    
        _LOGGER.debug("checking whether have to execute a migration plan")
        if self._migration_plan is not None:
            
            # exit()
            # self._lock.release()
            # return 
            # Will try to execute
            if self._timestamp_start_migration_plan is None:
                self._timestamp_start_migration_plan = cpyutils.eventloop.now()
                
            if len(self._migration_plan) > 0:
                for migration_list in self._migration_plan[:]:
                    if len(migration_list) > 0:
                        movement = migration_list.pop(0)
                        logging.debug("will migrate: %s" % movement)
                        
                        _LOGGER.info("(T: %.2f) %s" % (cpyutils.eventloop.now(), self._hosts_info.fancy_dump_info()))
                        self._hosts_info.make_movement(movement)
                        self._deployment.migrate_vm(movement.vmid, movement.host_src, movement.host_dst)
                        break
                    else:
                        self._migration_plan.remove(migration_list)
    
            if len(self._migration_plan) == 0:
                self._cancel_migration_plan()
                _LOGGER.debug(self._hosts_info.fancy_dump_info())
            else:
                _LOGGER.debug("still have pending migrations... let's continue")
                self._continue_migration_plan()
                
        self._lock.release()


    def _set_hosts_info(self, hosts_info):
        self._hosts_info = hosts_info
        self._hosts_info_timestamp = cpyutils.eventloop.now()

    def _monitor_hosts_info(self):
        # If the monitoring info is valid, we will use the monitoring info
        if ((cpyutils.eventloop.now() - self._hosts_info_timestamp) < config.config_vmca.MONITORIZATION_VALIDITY) and (self._hosts_info is not None):
            return self._hosts_info
        
        new_hosts_info = self._deployment.get_info()
        if new_hosts_info is None:
            return None
    
        if self._hosts_info is None:
            self._set_hosts_info(new_hosts_info.clone())
        
        return new_hosts_info
    
    def defrag(self):
        self._lock.acquire()
    
        new_hosts_info = self._monitor_hosts_info()
        if new_hosts_info is None:
            _LOGGER.error("could not get information about the deployment... skipping defraggging")
            self._lock.release()
            return
            
        #new_hosts_info = self._deployment.get_info()
        #if new_hosts_info is None:
        #    _LOGGER.error("could not get information about the deployment... skipping defraggging")
        #    self._lock.release()
        #    return
        #
        #if self._hosts_info is None:
        #    self._hosts_info = new_hosts_info.clone()
    
        if (self._migration_plan is not None):
            if (self._hosts_info != new_hosts_info):
                # Have to cancel the migration plan
                if self._migration_plan is not None:
                    _LOGGER.warning("things have changed, so we are cancelling the migration plan")
                    self._cancel_migration_plan()
                    
        if self._migration_plan is not None:
            # we are executing a migration plan and things still in the same place, so we won't try to defrag by now
            self._continue_migration_plan()
            self._lock.release()
            return
                
        # Will update the information about the hosts
        self._set_hosts_info(new_hosts_info)
        # self._hosts_info = new_hosts_info
        
        new_migration_plan = self._defragger.defrag(self._hosts_info, fixed_vms = self._deployment.get_locked_vms())
    
        if (new_migration_plan is None) or (len(new_migration_plan) == 0):
            _LOGGER.debug("nothing to migrate")
        else:
            self._start_migration_plan(new_migration_plan)
                
        self._lock.release()

    def clean_hosts(self, host_list = [], override_fixed_vms = False):
        _LOGGER.info("forcing cleaning hosts...")
        self._lock.acquire()

        new_hosts_info = self._monitor_hosts_info()
        if new_hosts_info is None:
            _LOGGER.error("could not get information about the deployment... skipping cleaning hosts")
            self._lock.release()
            return False, "could not get information about the deployment"
        
        forcing_hosts_fixed = [ f for f in new_hosts_info.keys() if f not in host_list ]
        if override_fixed_vms:
            forcing_fixed_vms = []
        else:
            forcing_fixed_vms = self._deployment.get_locked_vms()

        new_hosts_info.stabilize_vms(config.config_vmca.STABLE_TIME, host_list)
        # new_migration_plan = []
        new_migration_plan = self._defragger.defrag(new_hosts_info, hosts_fixed = forcing_hosts_fixed, fixed_vms = forcing_fixed_vms)

        retval = ""
        if (new_migration_plan is None) or (len(new_migration_plan) == 0):
            _LOGGER.debug("nothing to migrate")
            retval = "nothing to migrate"
        else:
            self._cancel_migration_plan()
            self._set_hosts_info(new_hosts_info.clone())
            self._start_migration_plan(new_migration_plan)
            retval = "migration plan created\n%s" % self._get_migration_plan()

        self._lock.release()
        return True, retval

    def forcerun(self):
        _LOGGER.info("forcing defrag...")
        self.defrag()

    def _get_migration_plan(self):
        retval = ""
        if self._migration_plan is None:
            retval = "- There is no current migration plan"
        else:
            for migration_list in self._migration_plan[:]:
                if len(migration_list) > 0:
                    for m in migration_list:
                        retval = "%s%s\n" % (retval, str(m))
        return retval
        
    def get_migration_plan(self):
        self._lock.acquire()
        retval = self._get_migration_plan()
        self._lock.release()
        return retval
        
    def loop(self):
        cpyutils.eventloop.create_eventloop(True)
        cpyutils.eventloop.get_eventloop().add_periodical_event(config.config_vmca.DEFRAGGER_FREQUENCY, -config.config_vmca.DEFRAGGER_FREQUENCY, "defrag", callback = self.defrag, arguments = [], stealth = True)
        cpyutils.eventloop.get_eventloop().loop()