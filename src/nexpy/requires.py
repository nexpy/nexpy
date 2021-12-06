# -*- coding: utf-8 -*-

# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
"""Package requirements are checked at runtime and installation time"""

pkg_requirements = [
    'nexusformat>=0.7.1',
    'numpy',
    'scipy',
    'h5py',
    'qtpy',
    'qtconsole',
    'ipython',
    'matplotlib',
    'lmfit>=1.0.3',
    'pylatexenc',
    'ansi2html',
    'pillow'
]
extra_requirements = {
    'spec': ['spec2nexus'],
    'fabio': ['fabio'],
}
