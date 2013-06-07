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
import pyspec

filetype = "SPEC File"

class ImportDialog(BaseImportDialog):
    """Dialog to import SPEC Scans"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.filebox)
        layout.addWidget(self.buttonbox)
        self.setLayout(layout)
  
        self.setWindowTitle("Import "+str(filetype))
 
    def get_data(self):
        SPECfile = pyspec.SpecDataFile(self.get_filename())
        root = NXroot()
        for i in SPECfile.findex.keys():
            try:
                scan = SPECfile.getScan(i)
                entry = 's%s' %i
                root[entry] = NXentry()
                root[entry].title = scan.header.splitlines()[0]
                root[entry].comments = scan.comments
                root[entry].data = NXdata()
                j = 0
                cols = [col.replace(' ', '_') for col in scan.cols]
                for col in cols:
                    root[entry].data[col] = NXfield(scan.data[:,j])
                    j += 1
                root[entry].data.nxsignal = root[entry].data[cols[-1]]
                root[entry].data.nxaxes = root[entry].data[cols[0]]               
                root[entry].data.errors = NXfield(np.sqrt(root[entry].data.nxsignal))
            except:
                pass
        return root
