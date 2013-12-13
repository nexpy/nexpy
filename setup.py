#!/usr/bin/env python
from distutils.core import setup

verbose=1

setup (name = "NeXpy", version = "0.1",
       description = "NeXpy",
       url="http://nexpy.github.io/nexpy/",
       author="NeXpy Developers",
       author_email="rosborn@anl.gov",
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
