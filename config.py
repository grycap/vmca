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
import cpyutils.config 

cpyutils.config.set_paths([ './etc/', '/etc/vmca/', '/etc/' ])
cpyutils.config.set_main_config_file("vmca.cfg")

class ONEConfig(cpyutils.config.Configuration):
    @staticmethod
    def str2intlist(str_list):
        ar_list = [ x.strip() for x in str_list.split(",") ]
        result = []
        for v in ar_list:
            try:
                v = int(v)
            except:
                v = None
            if v is not None:
                result.append(v)
        return result

    def parse(self):
        self.LOCKED_TEMPLATES = ONEConfig.str2intlist(self.LOCKED_TEMPLATES)
        self.LOCKED_VM_UID = ONEConfig.str2intlist(self.LOCKED_VM_UID)
        self.LOCKED_VM_GID = ONEConfig.str2intlist(self.LOCKED_VM_GID)
        self.LOCKED_VM_IDS = ONEConfig.str2intlist(self.LOCKED_VM_IDS)

config_one = ONEConfig(
    "ONE",
    {
        "ONE_XMLRPC": "http://localhost:2633/RPC2",
        "ONE_AUTH": "vmca:vmcapass",
        "LOCKED_TEMPLATES": "",
        "LOCKED_VM_UID": "",
        "LOCKED_VM_GID": "",
        "LOCKED_VM_IDS": "",
    },
    callback = ONEConfig.parse
)

class VMCAConfig(cpyutils.config.Configuration):
    def parse(self):
        self.DISABLED_HOSTS = [ x.strip() for x in self.DISABLED_HOSTS.split(",") ]
        dlevel = str(self.DEBUG_LEVEL).lower()
        if dlevel not in ["error", "debug", "info" ]:
            self.DEBUG_LEVEL = "debug"

config_vmca = VMCAConfig(
    "GENERAL",
    {
        "DEBUG_LEVEL": "error",
        "LOG_FILE": None,
        "SPARE_CPU": 0,
        "SPARE_MEMORY": 0,
        "MAX_SIMULTANEOUS_MIGRATIONS": 1,
        "MIGRATION_PLAN_FREQUENCY": 10,
        "DEFRAGGER_FREQUENCY": 10,
        "DISABLED_HOSTS": "",
        "STABLE_TIME": 600,
        "WEIGHT_MEM": 1,
        "WEIGHT_CPU": 1,
        "ENABLE_MIGRATION": False,
        "CONSIDER_VMS_STABLE_ON_STARTUP": False,
        "XMLRPC_PORT": 9999,
        "XMLRPC_HOST": "localhost",
        "MONITORIZATION_VALIDITY": 10,
        "COOLDOWN_MIGRATION": 10,
        "MAX_MIGRATIONS_PER_HOST": 2,
    },
    callback = VMCAConfig.parse
)
