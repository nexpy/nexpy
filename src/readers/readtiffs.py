#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
"""
Module to read in a folder of TIFF files and convert them to NeXus.

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
import Image

import numpy as np
from nexpy.api.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "TIFF Stack"

class ImportDialog(BaseImportDialog):
    """Dialog to import a TIFF stack"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.directorybox())
        filter_layout = QtGui.QHBoxLayout()
        prefix_label = QtGui.QLabel('File Prefix')
        self.prefix_box = QtGui.QLineEdit()
        ext_label = QtGui.QLabel('File Extension')
        self.ext_box = QtGui.QLineEdit('.tif')
        filter_layout.addWidget(prefix_label)
        filter_layout.addWidget(self.prefix_box)
        filter_layout.addWidget(ext_label)
        filter_layout.addWidget(self.ext_box)
        
        layout.addLayout(filter_layout)
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
  
        self.setWindowTitle("Import "+str(filetype))

    def get_prefix(self):
        return self.prefix_box.text().strip()
 
    def get_extension(self):
        return self.ext_box.text().strip()
 
    def get_data(self):
        filenames = self.get_filesindirectory(self.get_prefix(), 
                                              self.get_extension())
        try:
            from nexpy.readers.tifffile import tifffile as TIFF
            v0 = TIFF.imread(filenames[0])
            x = NXfield(range(v0.shape[1]), dtype=np.uint16, name='x')
            y = NXfield(range(v0.shape[0]), dtype=np.uint16, name='y')
            z = NXfield(range(1,len(filenames)+1), dtype=np.uint16, name='z')
            v = NXfield(np.zeros(shape=(len(filenames),v0.shape[0],v0.shape[1]),
                        dtype=v0.dtype), name='v')
            v[0] = v0
            for i in range(1,len(filenames)):
                v[i] = TIFF.imread(filenames[i])
        except ImportError:
            im = Image.open(filenames[0])
            dtype = np.dtype(np.uint16)
            if im.mode == "I;32" or im.mode == "I":
                dtype=np.dtype(np.uint32)
            x = NXfield(range(im.size[0]), dtype=np.uint16, name='x')
            y = NXfield(range(im.size[1]), dtype=np.uint16, name='y')
            z = NXfield(range(1,len(filenames)+1), dtype=np.uint16, name='z')
            v = NXfield(np.zeros(shape=(len(filenames),im.size[1],im.size[0]),
                        dtype=dtype), name='v')
            v[0] = np.array(im.getdata(),dtype=dtype).reshape(im.size[1],im.size[0])
            for i in range(1,len(filenames)):
                im = Image.open(filenames[i])
                v[i] = np.array(im.getdata(),dtype=dtype).reshape(im.size[1],im.size[0])
        return NXentry(NXdata(v,(z,y,x)))
        
        
        
        
        
        
        
        
        
        
