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
from distutils.core import setup
from version import VERSION

setup(name='VMCA',
      version=VERSION,
      description='Virtual Machine Consolidation Agent (VMCA)',
      author='Carlos de Alfonso',
      author_email='caralla@upv.es',
      url='http://www.grycap.upv.es/clues',
      # py_modules = [ 'bestfit', 'config', 'defragger', 'deployment', 'firstfit', 'one', 'schedule', 'version', 'vmcaserver' ],
      scripts = [ 'vmca', 'vmcadaemon', 'vmcad' ],
      data_files = [ ('/etc/default/', ['etc/vmca.cfg-example'] ) ],
      packages = [ 'vmca' ],
      package_dir = { 'vmca' : '.'},
      download_url = 'https://github.com/grycap/vmca',
      install_requires = [ 'cpyutils >= 0.23' ]
)
