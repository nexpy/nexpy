#!/usr/bin/env python
from distutils.core import setup

verbose=1

setup (name = "NeXpy", version = "0.1",
       description = "NeXpy",
       url="https://github.com/nexpy/nexpy",
       author="NeXpy Developers",
       author_email="rosborn@anl.gov",
       package_dir = {'nexpy': 'src'},
       packages = ['nexpy',
                   'nexpy.api', 'nexpy.api.nexus', 
                   'nexpy.gui', 'nexpy.readers'],
       package_data = {'nexpy': ['gui/resources/icon/*.svg','examples/*.nxs']},
       scripts = ['scripts/nexpy'],
      )
