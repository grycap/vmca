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

import sys
import logging
import time
import vmca.vmcaserver
import daemon
import deployment
import cpyutils.parameters

if __name__ == "__main__":
    logging.basicConfig(filename=None, level=logging.CRITICAL,
                        format='%(asctime)s: %(levelname)-8s %(message)s',
                        datefmt='%m-%d-%Y %H:%M:%S')
                        # , stream = sys.stdout)
    
    p = cpyutils.parameters.CmdLineParser("vmca-simulation", desc = "The VMCA simulation utility", arguments = [
            cpyutils.parameters.Parameter("-f", "--file", desc = "CSV file to load"),
            cpyutils.parameters.Flag("--pi", "--print-initial", desc = "prints the initial configuration"),
            cpyutils.parameters.Flag("--si", "--summary-initial", desc = "prints the summary of the initial configuration"),
            cpyutils.parameters.Flag("--pf", "--print-final", desc = "prints the final configuration"),
            cpyutils.parameters.Flag("--sf", "--summary-final", desc = "prints the summary of the final configuration"),
            cpyutils.parameters.Parameter("-d", "--defragger", desc = "Defragger to use. Possible values: 0 = Defragger_Refill"),
        ])
    
    parsed, result, info = p.parse(sys.argv[1:])
    if not parsed:
        if (result is None):
            print "Error:", info
            sys.exit(-1)
        else:
            print info
            sys.exit(0)
    
    csv_file = None
    try:
        csv_file = result.values['-f'][0]
        hostsinfo = vmca.defragger.HostsInfo.createfromfile(csv_file)
    except:
        if csv_file is None:
            print "you must provide a file name to load using parameter -f (currently we have not any random feature implemented)"
        else:
            print "file %s is not valid as a input file " % csv_file
        exit(-1)

    deployment = deployment.FAKE_Deployment.create_from_hosts_info(hostsinfo)
    deployment_info = deployment.get_info()

    pi = ""
    if result.values['--pi']:
        pi = deployment_info.csv()

    si = ""
    if result.values['--si']:
        si = deployment_info.fancy_dump_info()

    classname = result.values['-d'][0]

    if classname is None:
        print "you must provide the name of the class that you want to use as a defragger (using parameter --defragger)"
        exit(-1)

    classparts = classname.split(".")
    modulename = ".".join(classparts[:-1])
    if modulename == "":
        modulename = __name__
    classname = classparts[-1]

    if modulename not in sys.modules:
        try:
            __import__(modulename)
        except:
            print "could not import module %s" % modulename
            exit(-1)

    try:
        defragger_class = getattr(sys.modules[modulename], "Defragger_Refill")
        defragger = defragger_class()
    except:
        print "could not use class %s" % defragger
        exit(-1)

    monitor = vmca.vmcaserver.Monitor(deployment)
    monitor.monitor()
    new_migration_plan = defragger.defrag(deployment.get_info(), fixed_vms = [])
    plan = vmca.vmcaserver.MigrationPlan(monitor)
    plan.start(new_migration_plan)
    plan.update()
    while plan._migrate_next_vm(): pass

    pf = ""
    if result.values['--pf']:
        pf = deployment_info.csv()

    sf = ""
    if result.values['--sf']:
        sf = deployment_info.fancy_dump_info()

    if pi != "": print pi
    if pf != "": print pf
    if si != "": print si
    if sf != "": print sf