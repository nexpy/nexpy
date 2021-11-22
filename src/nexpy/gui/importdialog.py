#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Base class for import dialogs
"""
import os

from nexusformat.nexus import *

from .datadialogs import NXDialog

filetype = "Text File" #Defines the Import Menu label

class NXImportDialog(NXDialog):
    """Base dialog class for NeXpy import dialogs"""
 
    def __init__(self, parent=None):

        super().__init__(parent)
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
        super().accept()
 
BaseImportDialog = NXImportDialog
