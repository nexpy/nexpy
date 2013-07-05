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

from IPython.external.qt import QtCore, QtGui

import numpy as np
from nexpy.api.nexus import *
from nexpy.gui.importdialog import BaseImportDialog
import Image

filetype = "TIFF Stack"

class ImportDialog(BaseImportDialog):
    """Dialog to import a TIFF stack"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.directorybox())
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
  
        self.setWindowTitle("Import "+str(filetype))
 
    def get_data(self):
        filenames = filter(lambda x: not x.startswith('.'),self.get_filesindirectory())
        im = Image.open(filenames[0])
        dtype = np.dtype(np.uint16)
        if im.mode == "I;32" or im.mode == "I":
            dtype=np.dtype(np.uint32)
        v = NXfield(np.zeros(shape=(len(filenames),im.size[1],im.size[0]),dtype=dtype),
                    name='v')
        v[0] = np.array(im.getdata(),dtype=dtype).reshape(im.size[1],im.size[0])
        for i in range(1,len(filenames)):
            im = Image.open(filenames[i])
            v[i] = np.array(im.getdata(),dtype=dtype).reshape(im.size[1],im.size[0])
        x = NXfield(range(im.size[0]), dtype=np.uint16, name='x')
        y = NXfield(range(im.size[1]), dtype=np.uint16, name='y')
        z = NXfield(range(1,len(filenames)+1), dtype=np.uint16, name='z')
        return NXentry(NXdata(v,(z,x,y)))
