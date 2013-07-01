"""
Base class for import dialogs
"""
import os
from IPython.external.qt import QtCore, QtGui

from nexpy.api.nexus import *

filetype = "Text File"

class BaseImportDialog(QtGui.QDialog):
    """Dialog to select a text file"""
 
    def __init__(self, parent=None):

        QtGui.QDialog.__init__(self, parent)
        self.accepted = False 

    def filebox(self):
        self.filebutton =  QtGui.QPushButton("Choose File")
        self.filebutton.clicked.connect(self.choose_file)
        self.filename = QtGui.QLineEdit(self)
        self.filename.setMinimumWidth(300)
        filebox = QtGui.QHBoxLayout()
        filebox.addWidget(self.filebutton)
        filebox.addWidget(self.filename)
        return filebox
 
    def directorybox(self):
        self.directorybutton =  QtGui.QPushButton("Choose Directory")
        self.directorybutton.clicked.connect(self.choose_directory)
        self.directoryname = QtGui.QLineEdit(self)
        self.directoryname.setMinimumWidth(300)
        directorybox = QtGui.QHBoxLayout()
        directorybox.addWidget(self.directorybutton)
        directorybox.addWidget(self.directoryname)
        return directorybox

    def buttonbox(self):
        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                          QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        return buttonbox

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path
        """
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open file',
            os.path.expanduser('~'))
        self.filename.setText(str(filename))

    def get_filename(self):
        return self.filename.text()

    def choose_directory(self):
        """
        Opens a file dialog and returns a directory
        """
        dir = QtGui.QFileDialog.getExistingDirectory(self, 'Choose directory',
            dir=os.path.expanduser('~'))
        self.directoryname.setText(str(dir))

    def get_directory(self):
        return self.directoryname.text()

    def get_filesindirectory(self):
        os.chdir(self.get_directory())
        filenames = os.listdir(os.getcwd())
        return sorted(filenames,key=natural_sort)

    def accept(self):
        self.accepted = True
        from nexpy.gui.consoleapp import _mainwindow
        _mainwindow.import_data()
        QtGui.QDialog.accept(self)
        
    def reject(self):
        self.accepted = False
        QtGui.QDialog.reject(self)

def natural_sort(key):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]    
