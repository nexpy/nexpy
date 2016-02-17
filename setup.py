#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013-2014, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

from setuptools import setup, find_packages, Extension

import os, sys
import pkg_resources
pkg_resources.require('numpy')
import numpy
import versioneer

# pull in some definitions from the package's __init__.py file
sys.path.insert(0, os.path.join('src', ))
import nexpy
import nexpy.requires

verbose=1

setup (name =  nexpy.__package_name__,        # NeXpy
       version=versioneer.get_version(),
       cmdclass=versioneer.get_cmdclass(),
       license = nexpy.__license__,
       description = nexpy.__description__,
       long_description = nexpy.__long_description__,
       author=nexpy.__author_name__,
       author_email=nexpy.__author_email__,
       url=nexpy.__url__,
       download_url=nexpy.__download_url__,
       platforms='any',
       install_requires = nexpy.requires.pkg_requirements,
       extras_require = nexpy.requires.extra_requirements,
       package_dir = {'': 'src'},
       packages = find_packages('src'),
       include_package_data = True,
       package_data = {
                       'nexpy.gui': ['resources/icon/*.svg',
                                     'resources/icon/*.png',
                                     'resources/*.png',
                                    ],
                       'nexpy.definitions': ['base_classes/*.xml'],
                       'nexpy': [
                           'examples/*.*',
                           'examples/*/*.*',
                           'examples/*/*/*.*',
                       ],
                   },
       entry_points={
            # create & install scripts in <python>/bin
            'gui_scripts': ['nexpy = nexpy.nexpygui:main',],
       },
       classifiers= ['Development Status :: 4 - Beta',
                     'Intended Audience :: Developers',
                     'Intended Audience :: Science/Research',
                     'License :: OSI Approved :: BSD License',
                     'Programming Language :: Python',
                     'Programming Language :: Python :: 2',
                     'Programming Language :: Python :: 2.7',
                     'Programming Language :: Python :: 3',
                     'Programming Language :: Python :: 3.3',
                     'Programming Language :: Python :: 3.4',
                     'Programming Language :: Python :: 3.5',
                     'Topic :: Scientific/Engineering',
                     'Topic :: Scientific/Engineering :: Visualization'],
      )
