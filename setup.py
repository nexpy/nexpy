#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

from distutils.core import setup, Extension
import numpy
import os, sys

# pull in some definitions from the package's __init__.py file
sys.path.insert(0, os.path.join('src', ))
import nexpy

verbose=1

setup (name =  nexpy.__package_name__,        # NeXpy
       version = nexpy.__version__,
       license = nexpy.__license__,
       description = nexpy.__description__,
       long_description = nexpy.__long_description__,
       author=nexpy.__author_name__,
       author_email=nexpy.__author_email__,
       url=nexpy.__url__,
       download_url=nexpy.__download_url__,
       classifiers= ['Development Status :: 4 - Beta',
                     'Intended Audience :: Developers',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 2',
                     'Programming Language :: Python :: 2.7',
                     'Topic :: Scientific/Engineering',
                     'Topic :: Scientific/Engineering :: Visualization'],
       requires = ('numpy', 'scipy', 'h5py', 'pyside', 'ipython', 'matplotlib'),
       package_dir = {'nexpy': 'src/nexpy'},
       packages = ['nexpy',
                   'nexpy.api', 'nexpy.api.nexus', 
                   'nexpy.api.frills', 'nexpy.api.frills.functions',
                   'nexpy.gui', 'nexpy.readers', 'nexpy.readers.tifffile'],
       package_data = {'nexpy': ['nexpy/gui/resources/icon/*.svg',
                                 'nexpy/gui/resources/*.png',
                                 'nexpy/examples/*.nxs']},
       ext_modules=[Extension('nexpy.readers.tifffile._tifffile', 
                              ['src/nexpy/readers/tifffile/tifffile.c'],
                   include_dirs=[numpy.get_include()])],
       scripts = ['src/nexpy.py', 'src/merge-tiffs.py']
      )
