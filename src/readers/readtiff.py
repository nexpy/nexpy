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

from IPython.external.qt import QtCore, QtGui

import numpy as np
from nexpy.api.nexus import *
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
        try:
            from libtiff import TIFF
            im = TIFF.open(self.get_filename())
            z = NXfield(im.read_image(), name='z')
            x = NXfield(range(z.shape[0]), name='x')
            y = NXfield(range(z.shape[1]), name='y')
        except IOError:
            import Image
            im = Image.open(self.get_filename())
            dtype = np.dtype(np.uint16)
            if im.mode == "I;32" or im.mode == "I":
                dtype=np.dtype(np.uint32)
            z = NXfield(np.array(im.getdata(),dtype=dtype).reshape(im.size[1],im.size[0]),
                        name='z')
            x = NXfield(range(im.size[0]), name='x')
            y = NXfield(range(im.size[1]), name='y')
        
        return NXentry(NXdata(z,(x,y)))
