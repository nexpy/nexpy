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
Module to read in a CBF file and convert it to NeXus.

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

from IPython.external.qt import QtGui

import numpy as np                  #@UnusedImport
from nexpy.api.nexus import *       #@UnusedWildImport
from nexpy.gui.importdialog import BaseImportDialog

filetype = "CBF File"

class ImportDialog(BaseImportDialog):
    """Dialog to import a CBF file"""
 
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
            import pycbf
        except ImportError:
            raise NeXusError("PyCBF library not imported")
        cbf = pycbf.cbf_handle_struct()
        cbf.read_file(str(self.import_file), pycbf.MSG_DIGEST)
        cbf.select_datablock(0)
        cbf.select_category(0)
        cbf.select_column(2)
        imsize = cbf.get_image_size(0)
        z = NXfield(np.fromstring(cbf.get_integerarray_as_string(),np.int32).reshape(imsize), name='z')
        y = NXfield(range(z.shape[0]), name='y')
        x = NXfield(range(z.shape[1]), name='x')
        
        cbf.select_column(1)
        notes = NXnote(type='text/plain', description='CBF Header', 
                       data=cbf.get_value().replace('\n','\r\n'))
        
        return NXentry(NXdata(z,(y,x)), CBF_header=notes)
