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
    'nexusformat>=0.5.1',
    'numpy',
    'scipy',
    'h5py',
    'qtconsole',
    'ipython',
    'matplotlib',
    'ansi2html',
    'pillow'
]
extra_requirements = {
    'spec': ['spec2nexus>=2017.901.4',],
}
