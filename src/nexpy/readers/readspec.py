#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
"""
Module to read in a SPEC file and convert it to NeXus.

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

from PySide import QtCore, QtGui

import numpy as np
import os
from nexpy.api.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "SPEC File"
motors = {'tth': 'two_theta', 'th': 'theta', 'chi': 'chi', 'phi': 'phi',
          'ts1': 'top_slit1', 'bs1': 'bot_slit1'}

#def capitalize(line):
#    return ' '.join([s[0].upper() + s[1:] for s in line.split(' ')])

def lower(text):
    """
    Return standard motors in lower case but leave others unchanged.
    
    The rationale is that some SPEC variables require capitalization,
    e.g., 'NaI'
    """
    if text.lower() in motors.values():
        return text.lower()
    else:
        return text

def reshape_data(scan_data, scan_shape):
    scan_size = np.prod(scan_shape)
    if scan_data.size == scan_size:
        data = scan_data
    else:
        data = np.empty(scan_size)
        data.fill(np.NaN)
        data[0:scan_data.size] = scan_data
    return data.reshape(scan_shape)
                
class ImportDialog(BaseImportDialog):
    """Dialog to import SPEC Scans"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.filebox())
        self.layout.addLayout(self.scanbox())
        self.layout.addWidget(self.buttonbox())
        self.setLayout(self.layout)
  
        self.setWindowTitle("Import "+str(filetype))
 
    def scanbox(self):
        scanbox = QtGui.QHBoxLayout()
        scanminlabel = QtGui.QLabel("Min. Scan")
        self.scanmin = QtGui.QLineEdit()
        self.scanmin.setFixedWidth(100)
        self.scanmin.setAlignment(QtCore.Qt.AlignRight)
        scanmaxlabel = QtGui.QLabel("Max. Scan")
        self.scanmax = QtGui.QLineEdit()
        self.scanmax.setFixedWidth(100)
        self.scanmax.setAlignment(QtCore.Qt.AlignRight)
        scanbox.addWidget(scanminlabel)
        scanbox.addWidget(self.scanmin)
        scanbox.addWidget(scanmaxlabel)
        scanbox.addWidget(self.scanmax)
        return scanbox

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path
        """
        from pyspec.spec import SpecDataFile
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open file',
            os.path.expanduser('~'))
        self.filename.setText(str(filename))
        self.SPECfile = SpecDataFile(self.get_filename())
        self.spectra = self.SPECfile.findex.keys()
        self.scanmin.setText(str(self.spectra[0]))
        self.scanmax.setText(str(self.spectra[-1]))
    
    def get_spectra(self):
        try:
            specrange = sorted([int(self.scanmin.text()), int(self.scanmax.text())])
            specmin = self.spectra.index(specrange[0])
            specmax = self.spectra.index(specrange[1]) + 1
            return specmin, specmax
        except ValueError(error_message):
                QtGui.QMessageBox.critical(
                    self, "Invalid spectra", str(error_message),
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def get_data(self):
        root = NXroot()
        self.import_file = self.get_filename()
        specmin, specmax = self.get_spectra()
        for i in self.spectra[0:specmax]:
            scan = self.SPECfile.getScan(i)
            if i < self.spectra[specmin]:
                continue
            title, entry, scan_type, cols, axis = self.parse_scan(scan)
            root[entry] = NXentry()
            root[entry].title = title
            root[entry].comments = scan.comments
            root[entry].data = NXdata()
            if isinstance(axis,list):
                scan_shape = (axis[1][1].size, axis[0][1].size)
                scan_size = np.prod(scan_shape)
                j = 0
                for col in cols:
                    root[entry].data[col] = NXfield(reshape_data(scan.data[:,j], 
                                                                 scan_shape))
                    j += 1
            else:
                j = 0
                for col in cols:
                    root[entry].data[col] = NXfield(scan.data[:,j])
                    j += 1
            root[entry].data.nxsignal = root[entry].data[cols[-1]]
            root[entry].data.errors = NXfield(np.sqrt(root[entry].data.nxsignal))
            if isinstance(axis,list):
                root[entry].data[axis[0][0]] = axis[0][1]
                root[entry].data[axis[1][0]] = axis[1][1]
                root[entry].data.nxaxes = [root[entry].data[axis[1][0]],
                                           root[entry].data[axis[0][0]]]
            else:
                root[entry].data.nxaxes = root[entry].data[axis]
        return root

    def parse_scan(self, scan):
        title = scan.header.splitlines()[0]
        words = title.split()
        scan_number = 's%s' % words[1]
        scan_type = words[2]
        cols = [lower(col.replace(' ', '_')) for col in scan.cols]
        axis = cols[0]
        try:
            if scan_type == "hscan":
                axis = 'H'
            elif scan_type == "kscan":
                axis = 'K'
            elif scan_type == "lscan":
                axis = 'L'
            elif scan_type == "hklscan":
                Hstart, Hend, Kstart, Kend, Lstart, Lend = words[3:8]
                if Hstart <> Hend:
                    axis = 'H'
                elif Kstart <> Kend:
                    axis = 'K'
                else:
                    axis = 'L'
            elif scan_type == "hklmesh":
                Q0, Q0start, Q0end, NQ0 = words[3], float(words[4]), float(words[5]), int(words[6])+1
                Q1, Q1start, Q1end, NQ1 = words[7], float(words[8]), float(words[9]), int(words[10])+1
                axis = [(Q0, np.linspace(Q0start, Q0end, NQ0)),
                        (Q1, np.linspace(Q1start, Q1end, NQ1))]                
            else:
                if words[3] in motors.keys():
                    axis = motors[words[3]]
        finally:
            return title, scan_number, scan_type, cols, axis
