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

import os
from PySide import QtCore, QtGui

from nexpy.api.nexus import *
from nexpy.gui.datadialogs import BaseDialog

filetype = "Text File" #Defines the Import Menu label

class BaseImportDialog(BaseDialog):
    """Base dialog class for NeXpy import dialogs"""
 
    def __init__(self, parent=None):

        super(BaseImportDialog, self).__init__(parent)
        from nexpy.gui.consoleapp import _mainwindow
        self.default_directory = _mainwindow.default_directory
        self.import_file = None     # must define in subclass

    def get_data(self):
        '''
        Must define this module in each subclass.
        Must define self.import_file as file name

        :returns: :class:`NXroot` or :class:`NXentry` object
        '''
        raise NotImplementedError, "must override in subclass"
    
    def filebox(self):
        """
        Creates a text box and button for selecting a file.
        """
        self.filebutton =  QtGui.QPushButton("Choose File")
        self.filebutton.clicked.connect(self.choose_file)
        self.filename = QtGui.QLineEdit(self)
        self.filename.setMinimumWidth(300)
        filebox = QtGui.QHBoxLayout()
        filebox.addWidget(self.filebutton)
        filebox.addWidget(self.filename)
        return filebox
 
    def directorybox(self):
        """
        Creates a text box and button for selecting a directory.
        """
        self.directorybutton =  QtGui.QPushButton("Choose Directory")
        self.directorybutton.clicked.connect(self.choose_directory)
        self.directoryname = QtGui.QLineEdit(self)
        self.directoryname.setMinimumWidth(300)
        directorybox = QtGui.QHBoxLayout()
        directorybox.addWidget(self.directorybutton)
        directorybox.addWidget(self.directoryname)
        return directorybox

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.filename.text())
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open File',
            dirname)
        if os.path.exists(filename):    # avoids problems if <Cancel> was selected
            dirname = os.path.dirname(filename)
            self.filename.setText(str(filename))
            self.set_default_directory(dirname)

    def get_filename(self):
        """
        Returns the selected file.
        """
        return self.filename.text()

    def choose_directory(self):
        """
        Opens a file dialog and sets the directory text box to the chosen path.
        """
        dirname = self.get_default_directory()
        dirname = QtGui.QFileDialog.getExistingDirectory(self, 'Choose Directory',
            dir=dirname)
        if os.path.exists(dirname):    # avoids problems if <Cancel> was selected
            self.directoryname.setText(str(dirname))
            self.set_default_directory(dirname)

    def get_directory(self):
        """
        Returns the selected directory
        """
        return self.directoryname.text()
    
    def get_default_directory(self, suggestion=None):
        '''return the most recent default directory for open/save dialogs'''
        if suggestion is None or not os.path.exists(suggestion):
            suggestion = self.default_directory
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
        suggestion = os.path.abspath(suggestion)
        return suggestion
    
    def set_default_directory(self, suggestion):
        '''define the default directory to use for open/save dialogs'''
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
            self.default_directory = suggestion

    def get_filesindirectory(self, prefix='', extension='.*'):
        """
        Returns a list of files in the selected directory.
        
        The files are sorted using a natural sort algorithm that preserves the
        numeric order when a file name consists of text and index so that, e.g., 
        'data2.tif' comes before 'data10.tif'.
        """
        os.chdir(self.get_directory())
        if not extension.startswith('.'):
            extension = '.'+extension
        from glob import glob
        filenames = glob(prefix+'*'+extension)
        return sorted(filenames,key=natural_sort)

    def accept(self):
        """
        Completes the data import.
        """
        from nexpy.gui.consoleapp import _mainwindow
        _mainwindow.import_data()
        super(BaseImportDialog, self).accept()
        

def natural_sort(key):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]    
