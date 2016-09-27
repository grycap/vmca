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

class VMMigration_ongoing(defragger.VMMigration):
    def __init__(self, vmmigration):
        defragger.VMMigration.__init__(self, vmmigration.vmid, vmmigration.host_src, vmmigration.host_dst, vmmigration.cost, vmmigration.reward)
        self.timestamp_start = cpyutils.eventloop.now()

def compare_hosts_info(hosts_1, hosts_2, vms_excluded):
    # This function compares two host info structures to check whether they contain the same VMs in the same hosts.
    # - it is possible to pass one parameter: vms_excluded to not to take into account the vm ids contained in that list
    hosts_1_keys = hosts_1.keys()
    hosts_2_keys = hosts_2.keys()
    for h_id, h_1 in hosts_1.items():
        # print "------------ DATOS", h_id, hosts_1.items(), hosts_2.items()
        if h_id not in hosts_2_keys:
            # LHS has at least one host more than the LRS
            return -1

        h_2 = hosts_2._hosts_info[h_id]
        for vm_1 in h_1.vm_list:
            if vm_1.id not in vms_excluded:
                has_vm = False
                for vm_2 in h_2.vm_list:
                    if vm_2.id == vm_1.id:
                        has_vm = True
                        break
                    
                if not has_vm:
                    # LHS has at least one VM in one host that is not in the same host in the RHS
                    return -2

    for h_id, h_2 in hosts_2.items():
        if h_id not in hosts_1_keys:
            # El de la derecha tiene algun host mas
            return 1

        h_1 = hosts_1._hosts_info[h_id]
        for vm_2 in h_2.vm_list:
            if vm_2.id not in vms_excluded:
                has_vm = False
                for vm_1 in h_1.vm_list:
                    if vm_1.id == vm_2.id:
                        has_vm = True
                        break
                    
                if not has_vm:
                    # El de la derecha tiene alguna maquina que no tiene el de la derecha
                    return 2
    return 0

class Monitor():
    # This class abstracts the monitor from the deployment. It caches the data obtained from the monitorization of the infrastructure
    def __init__(self, deployment):
        self._deployment = deployment
        self._lock = threading.Lock()
        self._timestamp_monitor = 0
        self._hosts_info = None

    def _set_hosts_info(self, hosts_info):
        # Sets the monitoring info along with the timestamp
        self._hosts_info = hosts_info
        self._timestamp_monitor = cpyutils.eventloop.now()

    def _monitor_hosts_info(self):
        # Monitors the infrastructure and returns the hosts info structure obtained. If the monitorization fails, we will use the monitoring info
        # - TODO: include a cache of a interval of seconds, to avoid saturation
        NOW = cpyutils.eventloop.now()
        new_hosts_info = self._deployment.get_info()
        if new_hosts_info is None:
            if (NOW - self._timestamp_monitor) > config.config_vmca.MONITORIZATION_VALIDITY:
                _LOGGER.debug("could not monitor deployment, but the current info is still valid")
                return self._hosts_info
            else:
                _LOGGER.error("could not monitor deployment")
                return None
        if self._hosts_info is None:
            self._set_hosts_info(new_hosts_info.clone())
            
        return new_hosts_info

    def monitor(self):
        # The monitoring function protected against concurrent calls
        self._lock.acquire()
        retval = self._monitor_hosts_info()
        self._lock.release()
        return retval

    def make_migration(self, vmmigration):
        # This method orders the migration in the deployment and also makes it in the local data structure in order to be able to be used as a cache
        self._lock.acquire()
        retval = self._deployment.migrate_vm(vmmigration.vmid, vmmigration.host_src, vmmigration.host_dst)
        if retval:
            self._hosts_info.make_movement(vmmigration)
        self._lock.release()
        return retval

class MigrationPlan():
    def __init__(self, monitor):
        self._deployment = monitor
        self._ongoing_migrations = {}
        self._lock = threading.Lock()
        
        self._timestamp_start = 0
        self._timestamp_end = 0
        # self._timestamp_current = 0
        
        self._migration_plan = None
        self._migration_event = None
        
        self._timestamp_last_migration = 0
        self._last_migration = None
        self._hosts_info = None
        
        self._failed_migrations = {}
        # TODO: consider make a "_NOW" var and use it instead calling now() function all the time
        
    def __str__(self):
        self._lock.acquire()
        retval = "migration plan:\n" + "-"*80 + "\n"
        if self._migration_plan is None:
            retval = "- There is no current migration plan"
        else:
            for migration_list in self._migration_plan[:]:
                if len(migration_list) > 0:
                    for m in migration_list:
                        retval = "%s%s\n" % (retval, str(m))
            
        ongoing_str = "ongoing migrations:\n" + "-"*80 + "\n"
        for vmid, vmmovement in self._ongoing_migrations.items():
            ongoing_str = "%s%s\n" % (ongoing_str, str(vmmovement))
            
        retval = "%s\n%s\n" % (retval, ongoing_str)
            
        self._lock.release()
        return retval
        
    def get_failed_migrations(self):
        self._lock.acquire()
        failed_migrations = self._failed_migrations
        self._lock.release()
        return failed_migrations

    def is_alive(self):
        self._lock.acquire()
        if self._migration_plan is not None:
            if len(self._migration_plan) > 0:
                for migration_list in self._migration_plan[:]:
                    if len(migration_list) == 0:
                        self._migration_plan.remove(migration_list)
            if len(self._migration_plan) == 0:
                self._migration_plan = None
        retval = ((self._migration_plan is not None) or (len(self._ongoing_migrations) > 0))
        self._lock.release()
        return retval

    def _make_migration(self, vmmigration):
        if vmmigration.vmid in self._ongoing_migrations:
            _LOGGER.warning("trying to migrate %s but it is already being migrated!" % vmmigration.vmid)
            return False
        
        self._last_migration = VMMigration_ongoing(vmmigration)
        if self._deployment.make_migration(vmmigration):
            '''
            self._deployment.migrate_vm(vmmigration.vmid, vmmigration.host_src, vmmigration.host_dst)
            '''
            self._ongoing_migrations[vmmigration.vmid] = self._last_migration
            self._timestamp_last_migration = cpyutils.eventloop.now()
            self._hosts_info.make_movement(vmmigration)
            return True
        else:
            self._failed_migrations[vmmigration.vmid] = self._last_migration
            return False

    def _update_info(self):
        h_info = self._deployment.monitor()
        if h_info is None:
            return -1
        
        if self._hosts_info is None:
            self._hosts_info = h_info
        
        NOW = cpyutils.eventloop.now()
        ongoing_migrating_vms = [ vmid for vmid, migration in self._ongoing_migrations.items() if (NOW - migration.timestamp_start) < config.config_vmca.MAX_MIGRATION_TIME ]
        if compare_hosts_info(h_info, self._hosts_info, ongoing_migrating_vms) != 0:        
            if self._migration_plan is not None:
                _LOGGER.warning("things have changed, so we are cancelling the migration plan")
                self._cancel()

        self._hosts_info = h_info
        return self._purge_migrating_vms()

    def update(self):
        self._lock.acquire()
        self._update_info()
        self._lock.release()

    def _cancel(self):
        if self._migration_event is not None:
            cpyutils.eventloop.get_eventloop().cancel_event(self._migration_event.id)
            self._migration_event = None

        self._migration_plan = None
        self._timestamp_end = cpyutils.eventloop.now()
        self._timestamp_last_migration = 0

    def cancel(self):
        self._lock.acquire()
        self._cancel()
        self._lock.release()
        
    def start(self, migration_plan):
        self._lock.acquire()
        self._migration_plan = migration_plan
        self._timestamp_start = None
        self._timestamp_end = 0
        self._program_event()
        self._lock.release()
    
    def _get_next_migration(self, remove = False):
        if self._migration_plan is not None:
            if len(self._migration_plan) > 0:
                for migration_list in self._migration_plan:
                    if len(migration_list) > 0:
                        if remove:
                            return migration_list.pop(0)
                        if not remove:
                            return migration_list[0]
        return None
    
    def _pending_migrations(self):
        if self._get_next_migration(False) is not None:
            return True
        return False

    def _program_event(self, next_program = None):
        if self._pending_migrations() or (len(self._ongoing_migrations) > 0):
            if self._migration_event is None:
                if next_program is None:
                    next_program = config.config_vmca.MIGRATION_PLAN_FREQUENCY
                next_program = min(next_program, config.config_vmca.MIGRATION_PLAN_FREQUENCY)
                self._migration_event = cpyutils.eventloop.get_eventloop().add_event(cpyutils.eventloop.Event(next_program, description = "Migration plan", callback = self._execute_event, mute = False))
                
    def _migrate_next_vm(self):
        next_migration = self._get_next_migration(True)
        if next_migration is None:
            _LOGGER.debug("there is not any migration pending... let's ensure that there is not any migration plan")
            self._cancel()
            return False
        
        _LOGGER.info("will migrate %s" % next_migration)
        if not self._make_migration(next_migration):
            self._cancel()
            _LOGGER.warning("cancelling migration plan because migration %s could not be done" % next_migration)
            return False
            
        return True

    def _purge_migrating_vms(self):
        still_migrating_vms = {}
        failed_count = 0
        
        NOW = cpyutils.eventloop.now()
        for vmid, migration in self._ongoing_migrations.items():
            # Let's check if the migration has been finally carried out
            h_dst = migration.host_dst
            if h_dst in self._hosts_info.keys():
                h = self._hosts_info[h_dst]
                migration_done = False
                for vm in h.vm_list:
                    if (vm.id == migration.vmid) and (vm.state == defragger.VMData.STATE_RUNNING):
                        migration_done = True
                        _LOGGER.debug("vm %s is finally running in host %s" % (vm.id, h_dst))
                        break
                if migration_done:
                    continue
            else:
                # The host is not in the hosts info structure, so we cannot check it
                pass
            
            if (NOW - migration.timestamp_start) < config.config_vmca.MAX_MIGRATION_TIME:
                still_migrating_vms[vmid] = migration
                _LOGGER.debug("VM %s is still migrating" % migration.vmid)
            else:
                self._failed_migrations[vmid] = migration
                _LOGGER.error("Failed to migrate VM %s in %.2f seconds" % (migration.vmid, NOW - migration.timestamp_start))
                failed_count += 1
                
        self._ongoing_migrations = still_migrating_vms
        return failed_count

    def _execute_event(self):
        self._lock.acquire()
        NOW = cpyutils.eventloop.now()
        self._migration_event = None

        if (NOW - self._timestamp_last_migration) < config.config_vmca.COOLDOWN_MIGRATION:
            _LOGGER.debug("cooling down migrations")
            self._program_event(config.config_vmca.COOLDOWN_MIGRATION - NOW)
            self._lock.release()
            return

        if not config.config_vmca.ENABLE_MIGRATION:
            _LOGGER.info("we are not executing the migration plan because of ENABLE_MIGRATION is disabled... cancelling the migration plan")
            self._cancel()
            self._lock.release()
            return

        failed_migrations = self._update_info()
        if failed_migrations < 0:
            _LOGGER.error("could not monitor deployment")
            self._lock.release()
            return

        if failed_migrations > 0:
            _LOGGER.error("cancelling migration plan because there are failed migrations")
            self._cancel()
            self._lock.release()
            return
        
        if config.config_vmca.MAX_SIMULTANEOUS_MIGRATIONS > 1:
            # TODO: give support
            _LOGGER.error("there is no support for more than one migration at once, now")
            self._lock.release()
            raise Exception("there is no support for more than one migration at once, now")

        if len(self._ongoing_migrations) >= config.config_vmca.MAX_SIMULTANEOUS_MIGRATIONS:
            _LOGGER.debug("still migrating some VMs")
            self._program_event()
            self._lock.release()
            return

        #migrating_vms = self._deployment.get_migrating_vms()
        #if len(migrating_vms) >= config.config_vmca.MAX_SIMULTANEOUS_MIGRATIONS:
        #    _LOGGER.debug("skipping migration because the maximum number of simultaneous migrations has been reached")
        #    if (self._migration_plan is not None):
        #        self._continue_migration_plan()
        #    self._lock.release()
        #    return
   
        if self._pending_migrations():
            self._migrate_next_vm()

        self._program_event()        
        self._lock.release()

class Daemon(object):
    def __init__(self, deployment, defragger_periodical, defragger_clean = None):
        self._monitor = Monitor(deployment)
        self._migration_plan = MigrationPlan(self._monitor)
        
        self._defragger_periodical = defragger_periodical
        self._defragger_clean = defragger_clean
        if self._defragger_clean is None:
            self._defragger_clean = self._defragger_periodical

        self._deployment = deployment
        
        # The migration plan
        self._lock = threading.Lock()
        # self._migration_plan = None
            
    def dump_data(self):
        self._lock.acquire()
        hosts_str = ""
        hosts_i = self._monitor.monitor()
        if hosts_i is None:
            return "None"
        
        for h_id, h in hosts_i.items():
            vm_str = ""
            for vm in h.vm_list:
                vm_str = "%s\t%s\n" % (vm_str, str(vm))
            
            h_line = "%s\n%s" % (str(h), vm_str)
            hosts_str = "%s%s\n" % (hosts_str, h_line)
        
        retval = "hostsinfo:\n" + "-"*80 + "\n%s" % (hosts_str)
        
        retval = "\n%sfailed migrations:\n%s" % (retval, "-"*80)
        for vmid, movement in self._migration_plan.get_failed_migrations().items():
            retval = "%s\n%s" % (retval, movement)
        
        self._lock.release()
        return retval
        
    def defrag(self):
        if self._migration_plan.is_alive():
            _LOGGER.debug("migration plan is still alive... we'll skip defragging")
            return

        self._lock.acquire()
        new_hosts_info = self._monitor.monitor()
        if new_hosts_info is None:
            _LOGGER.error("could not get information about the deployment... skipping defraggging")
            self._lock.release()
            return
            
        # Will lock those hosts that have more than N vms
        locked_hosts = []
        for h_id, h in new_hosts_info.items():
            if len(h.vm_list) > config.config_vmca.MAX_MIGRATIONS_PER_HOST:
                # _LOGGER.debug("locking host %s because it has too VMs hosted" % h_id)
                locked_hosts.append(h_id)
        
        failed_vms = [ vmid for vmid in self._migration_plan.get_failed_migrations().keys() ]
        
        if (config.config_vmca.SPARE_MEMORY > 0) or (config.config_vmca.SPARE_CPU > 0) or (config.config_vmca.SPARE_MEMORY_PCT > 0) or (config.config_vmca.SPARE_CPU_PCT > 0):
            # _LOGGER.debug("applying the spare threshold: CPU: %s or %s%%, MEM: %s or %s%%" % (config.config_vmca.SPARE_CPU, config.config_vmca.SPARE_CPU_PCT, config.config_vmca.SPARE_MEMORY, config.config_vmca.SPARE_MEMORY_PCT))
            new_hosts_info.reduce_capacity(config.config_vmca.SPARE_CPU, config.config_vmca.SPARE_MEMORY, config.config_vmca.SPARE_CPU_PCT, config.config_vmca.SPARE_MEMORY_PCT)
        
        new_migration_plan = self._defragger_periodical.defrag(new_hosts_info, hosts_fixed = locked_hosts, fixed_vms = failed_vms + self._deployment.get_locked_vms())
    
        if (new_migration_plan is None) or (len(new_migration_plan) == 0):
            _LOGGER.debug("nothing to migrate")
        else:
            self._migration_plan.start(new_migration_plan)
            # self._start_migration_plan(new_migration_plan)
                
        self._lock.release()


    def defrag_using_defragger(self, defragger_to_use, hosts_fixed = [], override_fixed_vms = False, can_use_empty_hosts = False):
        _LOGGER.info("defragging using defragger \"%s\"..." % str(defragger_to_use))
        self._lock.acquire()

        new_hosts_info = self._monitor.monitor()
        if new_hosts_info is None:
            _LOGGER.error("could not get information about the deployment... skipping defrag")
            self._lock.release()
            return False, "could not get information about the deployment"
        
        if override_fixed_vms:
            forcing_fixed_vms = []
        else:
            failed_vms = [ vmid for vmid in self._migration_plan.get_failed_migrations().keys() ]
            forcing_fixed_vms = failed_vms + self._deployment.get_locked_vms()

        new_hosts_info.stabilize_vms(config.config_vmca.STABLE_TIME, host_list)
        used_empty_hosts = defragger_to_use.can_use_empty_hosts_as_destination(can_use_empty_hosts)
        new_migration_plan = defragger_to_use.defrag(new_hosts_info, hosts_fixed, fixed_vms = forcing_fixed_vms)
        defragger_to_use.can_use_empty_hosts_as_destination(used_empty_hosts)

        retval = ""
        if (new_migration_plan is None) or (len(new_migration_plan) == 0):
            _LOGGER.debug("nothing to migrate")
            retval = "nothing to migrate"
        else:
            self._migration_plan.cancel()
            self._migration_plan.start(new_migration_plan)
            retval = "migration plan created\n%s" % str(self._migration_plan)

        self._lock.release()
        return True, retval

    def clean_hosts(self, host_list = [], override_fixed_vms = False, can_use_empty_hosts = False):
        _LOGGER.info("forcing cleaning hosts...")
        self._lock.acquire()

        if self._defragger_clean != self._defragger_periodical:
            _LOGGER.warning("Defragging with a different defragger from the periodical one")

        new_hosts_info = self._monitor.monitor()
        if new_hosts_info is None:
            _LOGGER.error("could not get information about the deployment... skipping cleaning hosts")
            self._lock.release()
            return False, "could not get information about the deployment"
        
        for f in host_list:
            if f not in new_hosts_info.keys():
                _LOGGER.error("tried to clean a host that is not in the deployment (%s)" % f)
                self._lock.release()
                return False, "host %s is not in the deployment" % f

        forcing_hosts_fixed = [ f for f in new_hosts_info.keys() if f not in host_list ]
        if override_fixed_vms:
            forcing_fixed_vms = []
        else:
            failed_vms = [ vmid for vmid in self._migration_plan.get_failed_migrations().keys() ]
            forcing_fixed_vms = failed_vms + self._deployment.get_locked_vms()

        new_hosts_info.stabilize_vms(config.config_vmca.STABLE_TIME, host_list)
        used_empty_hosts = self._defragger_clean.can_use_empty_hosts_as_destination(can_use_empty_hosts)
        new_migration_plan = self._defragger_clean.defrag(new_hosts_info, hosts_fixed = forcing_hosts_fixed, fixed_vms = forcing_fixed_vms)
        self._defragger_clean.can_use_empty_hosts_as_destination(used_empty_hosts)

        retval = ""
        if (new_migration_plan is None) or (len(new_migration_plan) == 0):
            _LOGGER.debug("nothing to migrate")
            retval = "nothing to migrate"
        else:
            self._migration_plan.cancel()
            self._migration_plan.start(new_migration_plan)
            retval = "migration plan created\n%s" % str(self._migration_plan)

        self._lock.release()
        return True, retval

    def forcerun(self):
        _LOGGER.info("forcing defrag...")
        self.defrag()

    def get_migration_plan(self):
        self._lock.acquire()
        retval = str(self._migration_plan)
        self._lock.release()
        return retval
        
    def loop(self):
        cpyutils.eventloop.create_eventloop(True)
        if config.config_vmca.ENABLE_DEFRAGGER:
            # cpyutils.eventloop.get_eventloop().add_periodical_event(config.config_vmca.DEFRAGGER_FREQUENCY, -config.config_vmca.DEFRAGGER_FREQUENCY, "defrag", callback = self.defrag, arguments = [], stealth = True)
            cpyutils.eventloop.get_eventloop().add_event(cpyutils.eventloop.Event_Periodical(0, config.config_vmca.DEFRAGGER_FREQUENCY, description = "defrag", callback = self.defrag, mute = True))
        else:
            _LOGGER.warning("automatic defragger is disabled. VMCA will only server to evacuate nodes")
        cpyutils.eventloop.get_eventloop().loop()