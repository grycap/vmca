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
import vmca.vmcaserver
import cpyutils.eventloop

def isempty_migration_plan(migration_plan):
    for ml in migration_plan[:]:
        if len(ml) > 0:
            return False
    return True

class Daemon(vmca.vmcaserver.Daemon):
    def migration_plan_step(self):
        if self._migration_plan.is_alive():
            self._migration_plan._execute_event()
            # Ahora tendriamos que programar el siguiente evento, despues del tiempo de estabilizacion
            cpyutils.eventloop.get_eventloop().add_event(cpyutils.eventloop.Event(self._stabilization_time, callback = self.migration_plan_step, description = "Next migration plan step"))

    def start_simulation(self, stabilization_time, fname):
        vmca.config.config_vmca.ENABLE_MIGRATION=True
        vmca.config.config_vmca.CONSIDER_VMS_STABLE_ON_STARTUP=True
        vmca.config.config_vmca.ENABLE_MIGRATION=True
        vmca.config.config_vmca.COOLDOWN_MIGRATION=0

        self._migration_plan.cancel()
        self._deployment.stabilize_vms(stabilization_time)

        hosts_info = self._deployment.get_info()
        start_empty_hosts = hosts_info.empty_hosts()
        if hosts_info is None:
            raise Exception()

        self._hosts_info = hosts_info
        self._stabilization_time = stabilization_time

        new_migration_plan = self._defragger_periodical.defrag(self._hosts_info, fixed_vms = self._deployment.migration_vms.keys())
        if not isempty_migration_plan(new_migration_plan):
            self._migration_plan.start(new_migration_plan)
            eventloop = cpyutils.eventloop.get_eventloop()
            eventloop.add_event(cpyutils.eventloop.Event(0, callback = self.migration_plan_step, description = "Next migration plan step"))
            eventloop.limit_walltime(1000)
            eventloop.loop()

        end_empty_hosts = hosts_info.empty_hosts()
        return end_empty_hosts, self._deployment.get_info().fancy_dump_info()