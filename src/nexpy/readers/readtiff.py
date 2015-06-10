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
Module to read in a TIFF file and convert it to NeXus.

Each importer needs to layout the GUI buttons necessary for defining the imported file 
and its attributes and a single module, get_data, which returns an NXroot or NXentry
object. This will be added to the NeXpy tree.

Two GUI elements are provided for convenience:

    ImportDialog.filebox: Contains a "Choose File" button and a text box. Both can be 
                          used to set the path to the imported file. This can be 
                          retrieved as a string using self.get_filename().
    ImportDialog.buttonbox: Contains a "Cancel" and "OK" button to close the dialog. 
                            This should be placed at the bottom of all import dialogs.
"""

from nexpy.gui.pyqt import QtGui

import numpy as np
from nexusformat.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "TIFF Image"

class ImportDialog(BaseImportDialog):
    """Dialog to import a TIFF image"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.filebox())
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
  
        self.setWindowTitle("Import "+str(filetype))
 
    def get_data(self):
        self.import_file = self.get_filename()
        try:
            from nexpy.readers.tifffile import tifffile as TIFF
            im = TIFF.imread(self.import_file)
            z = NXfield(im, name='z')
            y = NXfield(range(z.shape[0]), name='y')
            x = NXfield(range(z.shape[1]), name='x')
        except ImportError:
            import Image
            im = Image.open(self.import_file)
            dtype = np.dtype(np.uint16)
            if im.mode == "I;32" or im.mode == "I":
                dtype=np.dtype(np.uint32)
            z = NXfield(np.array(im.getdata(),dtype=dtype),
                        name='z')
            y = NXfield(range(im.size[1]), name='y')
            x = NXfield(range(im.size[0]), name='x')
        
        return NXentry(NXdata(z,(y,x)))
