# -*- coding: utf-8 -*-

'''package requirements are checked at runtime and installation time'''

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2014, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

pkg_requirements = [
    'nexusformat>=0.1.4',
    'numpy>=1.6.0',
    'scipy',
    'h5py',
    'jupyter',
    'ipython>=4.0.0',
    'matplotlib>=1.4.0',
]
extra_requirements = {
    'spec': ['spec2nexus>=2014.1228.0',],
}
