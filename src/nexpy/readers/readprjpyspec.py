#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

'''Module to read in a SPEC file and convert it to NeXus.'''

from PySide import QtCore, QtGui

import numpy as np                  #@UnusedImport
import os                           #@UnusedImport
from nexpy.api.nexus import *       #@UnusedWildImport
from nexpy.gui.importdialog import BaseImportDialog

filetype = "SPEC File (prjPySpec)"
                
class ImportDialog(BaseImportDialog):
    """Dialog to import SPEC Scans"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        raise NotImplementedError

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path
        """
        raise NotImplementedError

    def get_spectra(self):
        '''
        PySpec interface: reads specmin & specmax from dialog widgets
        '''
        raise NotImplementedError

    def get_data(self):
        raise NotImplementedError

    def parse_scan(self, scan):
        '''
        PySpec interface: interprets what type of scan
        '''
        raise NotImplementedError

    def _get_min_max(self):
        '''validate and return int(min) and int(max) from the dialog box'''
        try:
            scanmin = int(self.scanmin.text())
        except ValueError, err:
            QtGui.QMessageBox.critical(
                self, "Min must be a number", 
                str(err) + '\n Must specify a scan number in the file',
                QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
            return None, None

        try:
            scanmax = int(self.scanmax.text())
        except ValueError, err:
            QtGui.QMessageBox.critical(
                self, "Max must be a number", 
                str(err) + '\n Must specify a scan number in the file',
                QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
            return None, None
        
        if self.SPECfile.getScan(scanmin) is None:
            QtGui.QMessageBox.critical(
                self, "Minimum scan number not found!", 
                self.scanmin.text() + ' is not a scan number in this file',
                QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
            scanmin = None
        
        if self.SPECfile.getScan(scanmax) is None:
            QtGui.QMessageBox.critical(
                self, "Maximum scan number not found!", 
                self.scanmin.text() + ' is not a scan number in this file',
                QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
            scanmax = None
        
        return scanmin, scanmax
