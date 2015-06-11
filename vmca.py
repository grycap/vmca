#! /usr/bin/env python
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
import sys
import config
import xmlrpclib
import logging
import cpyutils.parameters

def main_function():
    XMLRPC_SERVER = 'http://%s:%s/RPC2' %(config.config_vmca.XMLRPC_HOST, config.config_vmca.XMLRPC_PORT)
    proxy = xmlrpclib.ServerProxy(XMLRPC_SERVER)

    try:
        version = proxy.version()
    except:
        print "Could not connect to VMCA server %s (please, check if it is running)" % XMLRPC_SERVER, None    
        sys.exit(-1)

        
    p = cpyutils.parameters.ParameterHandler(['getplan', 'forcerun', 'clean', 'version', 'info'])
    p.add_flag("-h", "--help")
    p.add_op_parameter("clean", "-h", "--hosts", None)
    p.add_op_flag("clean", "-f", "--force")
    p.add_op_flag("clean", "-u", "--use-empty")

    result, parameters = p.parse(sys.argv[1:])
    if not result:
        print "* error parsing parameters\n%s" % "\n".join(parameters.errors)
        sys.exit(-1)

    if '-h' in parameters.flags:
        print "usage: "
        print "\t",p.help(sys.argv[0])
        sys.exit(0)

    if parameters.operation is None:
        print "no operation was stated"
        print "usage: "
        print "\t",p.help(sys.argv[0])
        sys.exit()
        
    if parameters.operation == 'getplan':
        succeed, text = proxy.getplan()
        if succeed:
            print text
        else:
            logging.error("Could not get the migration plan from VMCA (%s)" % text)
            sys.exit(-1)

    if parameters.operation == 'forcerun':
        succeed, text = proxy.forcerun()
        if succeed:
            print text
        else:
            logging.error("Could not force the run of VMCA (%s)" % text)
            sys.exit(-1)

    if parameters.operation == 'clean':
        hosts = cpyutils.parameters.break_parameter_into_list(parameters.op_parameters['-h'])
        if (hosts is None):
            logging.error("you must stat the hosts that you want to clean using parameter -h")
            sys.exit(-1)
            
        force = ("-f" in parameters.op_flags)
        useempty = ("-u" in parameters.op_flags)

        succeed, text = proxy.cleanhosts(hosts, force, useempty)
        if succeed:
            print text
        else:
            logging.error("Could not clean hosts of VMCA (%s)" % text)
            sys.exit(-1)

    if parameters.operation == 'version':
        succeed, text = proxy.version()
        if succeed:
            print text
        else:
            logging.error("Could not get version of VMCA (%s)" % text)
            sys.exit(-1)

    if parameters.operation == 'info':
        succeed, text = proxy.getinfo()
        if succeed:
            print text
        else:
            logging.error("Could not get info about VMCA (%s)" % text)
            sys.exit(-1)

    sys.exit()
        
    operation = (args[0].strip()).lower()
    parameters = args[1:]

    if operation not in ['getplan', 'force', 'clean', 'cleanforce', 'version']:
        logging.error("%s is not a valid operation" % operation)
        sys.exit(-1)

    if operation == 'getplan':
        if (len(parameters) > 0):
            logging.error("usage: getplan")
            sys.exit(-1)

        succeed, text = proxy.getplan()
        if succeed:
            print text
        else:
            logging.error("Could not get the migration plan from VMCA (%s)" % text)
            sys.exit(-1)

    if operation == 'force':
        if (len(parameters) > 0):
            logging.error("usage: force")
            sys.exit(-1)

        succeed, text = proxy.forcerun([])
        if succeed:
            print text
        else:
            logging.error("Could not force the run of VMCA (%s)" % text)
            sys.exit(-1)

    force = False
    if operation == 'cleanforce':
        force = True
        operation = 'clean'

    if operation == 'clean':
        if (len(parameters) == 0):
            logging.error("usage: %s <host name>" % operation)
            sys.exit(-1)

        succeed, text = proxy.forcerun(parameters, force)
        if succeed:
            print text
        else:
            logging.error("Could not clean hosts of VMCA (%s)" % text)
            sys.exit(-1)

    if operation == 'version':
        if (len(parameters) > 0):
            logging.error("usage: version")
            sys.exit(-1)

        succeed, text = proxy.version()
        if succeed:
            print text
        else:
            logging.error("Could not get version of VMCA (%s)" % text)
            sys.exit(-1)

if __name__ == '__main__':
    main_function()