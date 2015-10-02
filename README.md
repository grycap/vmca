# Virtual Machine Consolidation Agent

During the lifecycle of a private Cloud deployment, the Virtual Machines (VM) are placed in real virtualization hosts. When these VMs are no longer needed, they are destroyed and their resources are freed. The problem here is that due to these movements, we can find that the remaining VMs at a moment are spreaded among the real hosts resulting in a low density of VM per real host. The consequence is that is get a fragmentation of the resources of the virtualization hosts. Such fragmentation may have critical effects if a new VM should be started but there are not enough continous resources to be allocated, while there exist fragmented resources.

![IMAGE](https://github.com/grycap/vmca/blob/master/img/fragmented.jpg?raw=true =200x)

On the other hand, when the fragmentation of resources happens, another consequence is an inefficient usage of the virtualization resources. That means that we are probably keeping powered on some real hosts because they are running VMs. In case that these VMs were hosted in other hosts, some of the virtualization hosts may be powered off to save energy.

The Virtual Machine Consolidation Agent (VMCA) inspects your private Cloud deployment to try to defragment the available resources by migrating VMs from some real hosts to other real hosts that have enough resources to keep all the VMs running. The result is a compression of the existing free resources and an increase of the density of VMs per real host.

![IMAGE](https://github.com/grycap/vmca/blob/master/img/defragmented.jpg?raw=true =200x)

One of the main objectives of the VMCA is getting real hosts free from VMs. Using this agent in conjunction with CLUES it is possible to achieve a more efficient usage of the resources. Moreover we will save energy because those nodes that are not used by the virtualization platform will be powered off by CLUES.

## Evacuating hosts

Under some circumnstances, some hosts need to be powered off, rebooted, etc. due to maintenance. This is a problem when that host has some VMs running on it. VMCA can also be used to move the VMs from one host to the other hosts in the platform. Finally, when the host is free of VMs it can be powered off.

OpenStack has a similar function called ```host-evacuate```, but it is needed to move all the instances from one specific host to exactly one host. VMCA will try to re-place the VMs using a deffragging algorithm (e.g. packing the VMs into the less number of hosts, distributing them, etc.). 

# Installing

VMCA is currently working in conjunction with OpenNebula (it has been tested with ONE 4.8). Futher releases will integrate with OpenStack.

## Dependencies

Make sure that you have installed ```cpyutils``` package from https://github.com/grycap/cpyutils

## Installing

You have to obtain the source code in a temporary folder and execute (as root):

```
$ cd /tmp
$ git clone https://github.com/grycap/vmca
$ cd vmca
$ python setup.py install --record installed-files.txt
$ cp ./etc/vmca.cfg-example /etc/vmca.cfg
$ chmod 600 /etc/vmca.cfg
$ touch /var/log/vmca.log
```

In particular, to integrate with ONE, you will need to have one user in the ```oneadmin``` group (e.g. vmcauser).

```
$ oneuser create vmca vmcapass
```

Now you should adjust the file ```/etc/vmca.cfg``` to your settings. In particular, to work with ONE you will need to set the ```ONE_XMLRPC``` and ```ONE_AUTH``` variables.

Once ready, you can start VMCA by simply executing

```
$ vmcad start
```

## Debugging (in case that it does not start)

You can see what happens in ```/var/log/vmca.log```. In case that you cannot make vmca run, you can set ```LOG_FILE=``` in the configuration file and start vmca.py using the commandline ```vmca.py```

## Running VMCA as other user

If you want to run VMCA with other user than root, you must give the permissions to the ```/etc/vmca.cfg``` and ```/var/log/vmca.log``` files, by executing (as root):

```
$ chown vmcauser:root /etc/vmca.cfg /var/log/vmca.log
$ chmod 644 /var/log/vmca.log
$ chmod 600 /etc/vmca.cfg
```

Then you should modify the command ```vmcad``` to start the application as other user.

## Installing as source-code

You simply have to choose a folder in which VMCA is being installed (for now on it will be /usr/local/vmca) and execute (as root):

```
$ cd /usr/local
$ git clone https://github.com/grycap/vmca
$ cp vmca/etc/vmca.cfg-example /etc/vmca.cfg
$ chmod 600 /etc/vmca.cfg
$ touch /var/log/vmca.log
```

In particular, to integrate with ONE, you will need to have one user in the ```oneadmin``` group (e.g. vmcauser).

```
$ oneuser create vmca vmcapass
```

Now you should adjust the file ```/etc/vmca.cfg``` to your settings. In particular, to work with ONE you will need to set the ```ONE_XMLRPC``` and ```ONE_AUTH``` variables.

Once ready, you can start VMCA by simply executing

```
$ python /usr/local/vmca/vmca.py
```

## Running VMCA as other user

If you want to run VMCA with other user than root, you must give the permissions to the ```/etc/vmca.cfg``` and ```/var/log/vmca.log``` files, by executing (as root):

```
$ chown vmcauser:root /etc/vmca.cfg /var/log/vmca.log
$ chmod 644 /var/log/vmca.log
$ chmod 600 /etc/vmca.cfg
```

The you can su as the ```vmcauser``` user and start VMCA.

# Using VMCA

The standard distribution of VMCA incorporates the ```vmca``` CLI application, and the help of the command is very self-explanatory:

```
# vmca --help
The VMCA command line utility

Usage: vmca [-h] [getplan|forcerun|clean|version|info]

	[-h|--help] - Shows this help
	* Gets the current migration plan that is being carried out in the server
	  Usage: getplan 

	* Forces VMCA to analyze the platform immediately
	  Usage: forcerun 

	* Migrates all the VMs from one host
	  Usage: clean [-f] [-e] <node>
		[-f|--force] - Force cleaning even if the host has not its VMs in a stable state
		[-e|--use-empty] - Use emtpy hosts as a possible destinations
		<node> - Name of the host that is going to be cleaned

	* Gets the version of the VMCA server
	  Usage: version 

	* Gets the monitoring information that has the VMCA server
	  Usage: info 
```

## Evacuating a host

In case that you want to power off a host, or you need to reboot it, you can move all its VMs to other hosts using VMCA. As an example, if you want to move all the VMs from 'torito03', the commandline will be:

```
# vmca clean torito03
```

The default behaviour of VMCA is not to use the hosts that are empty (as it tries to get hosts without any VM running on them). You can modify such behaviour and enable VMCA to use the empty hosts including the flag ```-e```.

# Scenarios

## VMCA is only needed to ocasionally evacuate hosts

You can disable the periodical run of the deffragger by setting ```ENABLE_DEFRAGGER=False``` in the VMCA configuration file. Then the VMCA deffragger will never be automatically triggered, while it can be forced using the commandline.

## The deffragger used to evacuate a host has to be different than the one used automatically

In some cases you will need different defraggers for different purposes. E.g. you need an automatically defragger that packs the VMs into the hosts, but you want that when a host is evacuated, its VMs are homogenously distributed in the platform.

While it is possible to implement in VMCA, currently there is not any _configuration based_ mechanism to make it. The solution is a bit tricky, as it is needed to modify the source-code to select which defragger will be used for each purpose.

You should modify the file ```vmcad.py``` and locate the line that creates the daemon:

```
DAEMON = vmcaserver.Daemon(deployment, T(), T_clean())
```

The parameters for the Daemon class are the deployment (e.g. the ONE based), the automatic defragger (```T``` in the default implementation, and the defragger used to clean one host (```T_clean``` in the default implementation).

You can create your own class or use a combination of the available criteria, as ```T``` and ```T_clean``` are created:

```
    class T(schedule.Scheduler_Packing, firstfit.SelectHost_LessVMs_First, firstfit.Defragger_FF): pass
    class T_clean(schedule.Scheduler_Stripping, firstfit.SelectHost_LessVMs_First, firstfit.Defragger_FF): pass
```
