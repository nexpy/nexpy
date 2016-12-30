# -*- coding: utf-8 -*-

'''package requirements are checked at runtime and installation time'''

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2016, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

pkg_requirements = [
    'nexusformat>=0.4.5',
    'numpy>=1.6.0',
    'scipy',
    'h5py',
    'jupyter',
    'ipython>=4.0.0',
    'matplotlib>=1.4.0',
]
extra_requirements = {
    'spec': ['spec2nexus>=2016.216.0',],
}
