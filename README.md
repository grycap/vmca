# Virtual Machine Consolidation Agent

During the lifecycle of a private Cloud deployment, the Virtual Machines (VM) are placed in real virtualization hosts. When these VMs are no longer needed, they are destroyed and their resources are freed. The problem here is that due to these movements, we can find that the remaining VMs at a moment are spreaded among the real hosts resulting in a low density of VM per real host. The consequence is that is get a fragmentation of the resources of the virtualization hosts. Such fragmentation may have critical effects if a new VM should be started but there are not enough continous resources to be allocated, while there exist fragmented resources.

![IMAGE](https://github.com/grycap/vmca/blob/master/img/fragmented.jpg?raw=true =200x)

On the other hand, when the fragmentation of resources happens, another consequence is an inefficient usage of the virtualization resources. That means that we are probably keeping powered on some real hosts because they are running VMs. In case that these VMs were hosted in other hosts, some of the virtualization hosts may be powered off to save energy.

The Virtual Machine Consolidation Agent (VMCA) inspects your private Cloud deployment to try to defragment the available resources by migrating VMs from some real hosts to other real hosts that have enough resources to keep all the VMs running. The result is a compression of the existing free resources and an increase of the density of VMs per real host.

![IMAGE](https://github.com/grycap/vmca/blob/master/img/defragmented.jpg?raw=true =200x)

One of the main objectives of the VMCA is getting real hosts free from VMs. Using this agent in conjunction with CLUES it is possible to achieve a more efficient usage of the resources. Moreover we will save energy because those nodes that are not used by the virtualization platform will be powered off by CLUES.

# Installing

VMCA is currently working in conjunction with OpenNebula (it has been tested with ONE 4.8). Futher releases will integrate with OpenStack.

## Prerrequisites

Make sure that you have installed ```cpyutils``` package from https://github.com/grycap/cpyutils

## Installing

The current installation is source-code based. So you simply have to choose a folder in which VMCA is being installed (for now on it will be /usr/local/vmca) and execute (as root):

```
$ cd /usr/local
$ git clone https://github.com/grycap/vmca
$ cp vmca/etc/vmca.cfg-example /etc/vmca.cfg
$ chmod 600 /etc/vmca.cfg
$ touch /var/log/vmca.log
```

In particular, to integrate with ONE, you will need to have one user in the ```oneadmin``` group (e.g. vmcauser).

```
$ oneuser create vmca vmcapass --sha1
```

Now you should adjust the file ```/etc/vmca.cfg``` to your settings. In particular, to work with ONE you will need to set the ```ONE_XMLRPC``` and ```ONE_AUTH``` variables.

Once ready, you can start VMCA by simply executing

```
$ python /usr/local/vmca/vmca.py
```

## Running VMCA with other user

If you want to run VMCA with other user than root, you must give the permissions to the ```/etc/vmca.cfg``` and ```/var/log/vmca.log``` files, by executing (as root):

```
$ chown vmcauser:root /etc/vmca.cfg /var/log/vmca.log
$ chmod 644 /var/log/vmca.log
$ chmod 600 /etc/vmca.cfg
```

The you can su as the ```vmcauser``` user and start VMCA.
