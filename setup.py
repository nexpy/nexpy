#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
#!/usr/bin/env python
from distutils.core import setup

verbose=1

setup (name = "NeXpy", version = '0.1.0',
       description = "NeXpy: A Python GUI to analyze NeXus data",
       long_description = \
"""
NeXpy provides a high-level python interface to NeXus data 
<http://www.nexusformat.org/> contained within a simple GUI. It is designed to 
provide an intuitive interactive toolbox allowing users both to access existing 
NeXus files and to create new NeXus-conforming data structures without expert 
knowledge of the file format.

The latest development version is always available from NeXpy's GitHub
site <https://github.com/nexpy/nexpy>.
""",
       classifiers= ['Development Status :: 4 - Beta',
                     'Intended Audience :: Developers',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python',
                     'Topic :: Scientific/Engineering',
                     'Topic :: Scientific/Engineering :: Visualization',
                     'Operating System :: POSIX :: Linux'],
       url="http://nexpy.github.io/nexpy/",
       requires = ('numpy', 'scipy', 'h5py', 'pyside'),
       author="NeXpy Developers",
       author_email="nexpydev@gmail.com",
       package_dir = {'nexpy': 'src'},
       packages = ['nexpy',
                   'nexpy.api', 'nexpy.api.nexus', 
                   'nexpy.api.frills', 'nexpy.api.frills.functions',
                   'nexpy.gui', 'nexpy.readers'],
       package_data = {'nexpy': ['gui/resources/icon/*.svg',
                                 'gui/resources/*.png',
                                 'examples/*.nxs']},
       scripts = ['scripts/nexpy', 'scripts/merge-tiffs'],
      )
