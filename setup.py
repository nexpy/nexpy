#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
#!/usr/bin/env python
from distutils.core import setup, Extension
import numpy

verbose=1

setup (name = 'NeXpy', version = '0.1.2',
       description = 'NeXpy: A Python GUI to analyze NeXus data',
       long_description = \
"""
NeXpy provides a high-level python interface to `NeXus data 
<http://www.nexusformat.org/>`_ contained within a simple GUI. It is designed to 
provide an intuitive interactive toolbox allowing users both to access existing 
NeXus files and to create new NeXus-conforming data structures without expert 
knowledge of the file format.

The latest development version is always available from `NeXpy's GitHub
site <https://github.com/nexpy/nexpy>`_.
""",
       classifiers= ['Development Status :: 4 - Beta',
                     'Intended Audience :: Developers',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 2',
                     'Programming Language :: Python :: 2.7',
                     'Topic :: Scientific/Engineering',
                     'Topic :: Scientific/Engineering :: Visualization'],
       url='http://nexpy.github.io/nexpy/',
       download_url='https://github.com/nexpy/nexpy/',
       requires = ('numpy', 'scipy', 'h5py', 'pyside', 'ipython', 'matplotlib'),
       author='NeXpy Developers',
       author_email='nexpydev@gmail.com',
       package_dir = {'nexpy': 'src'},
       packages = ['nexpy',
                   'nexpy.api', 'nexpy.api.nexus', 
                   'nexpy.api.frills', 'nexpy.api.frills.functions',
                   'nexpy.gui', 'nexpy.readers', 'nexpy.readers.tifffile'],
       package_data = {'nexpy': ['gui/resources/icon/*.svg',
                                 'gui/resources/*.png',
                                 'examples/*.nxs']},
       ext_modules=[Extension('tifffile._tifffile', 
                              ['src/readers/tifffile/tifffile.c'],
                   include_dirs=[numpy.get_include()])],
       scripts = ['scripts/nexpy', 'scripts/merge-tiffs']
      )
