#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Base class for import dialogs
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os

from nexusformat.nexus import *
from .datadialogs import BaseDialog

filetype = "Text File" #Defines the Import Menu label

class BaseImportDialog(BaseDialog):
    """Base dialog class for NeXpy import dialogs"""
 
    def __init__(self, parent=None):

        super(BaseImportDialog, self).__init__(parent)
        self.default_directory = self.mainwindow.default_directory
        self.import_file = None     # must define in subclass

    def get_data(self):
        '''
        Must define this module in each subclass.
        Must define self.import_file as file name

        :returns: :class:`NXroot` or :class:`NXentry` object
        '''
        raise NotImplementedError("must override in subclass")

    def accept(self):
        """
        Completes the data import.
        """
        self.accepted = True
        self.mainwindow.import_data()
        super(BaseImportDialog, self).accept()
 