#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

__package_name__ = 'NeXpy'
from ._version import get_versions
__version__ = get_versions()['version']
del get_versions

__documentation_author__ = 'Ray Osborn'
__documentation_copyright__ = '2013-2020, Ray Osborn'

__license__ = 'BSD'
__author_name__ = 'NeXpy Development Team'
__author_email__ = 'nexpydev@gmail.com'
__author__ = __author_name__ + ' <' + __author_email__ + '>'

__url__          = 'http://nexpy.github.io/nexpy/'
__download_url__ = 'https://github.com/nexpy/nexpy/'

__description__ = 'NeXpy: A Python GUI to analyze NeXus data'
__long_description__ = \
u"""
NeXpy provides a high-level python interface to `NeXus data 
<http://www.nexusformat.org/>`_ contained within a simple GUI. It is 
designed to provide an intuitive interactive toolbox allowing users both 
to access existing NeXus files and to create new NeXus-conforming data 
structures without expert knowledge of the file format.

The latest development version is always available from `NeXpy's GitHub
site <https://github.com/nexpy/nexpy>`_.
"""
