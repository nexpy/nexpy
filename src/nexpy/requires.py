# -*- coding: utf-8 -*-

'''package requirements are checked at runtime and installation time'''

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2020, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

pkg_requirements = [
    'nexusformat>=0.7.1',
    'numpy',
    'scipy',
    'h5py',
    'qtpy',
    'ipykernel',
    'qtconsole',
    'ipython',
    'matplotlib',
    'lmfit>=1.0.3',
    'pylatexenc',
    'ansi2html',
    'pillow',
    'versioneer'
]
extra_requirements = {
    'spec': ['spec2nexus>=2017.901.4',],
}
