"""
Base class for import dialogs
"""

from IPython.external.qt import QtCore, QtGui

from nexpy.api.nexus import *

filetype = "Text File"

class BaseImportDialog(QtGui.QDialog):
    """Dialog to select a text file"""
 
    def __init__(self, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.accepted = False

        self.filebutton =  QtGui.QPushButton("Choose File")
        self.filebutton.clicked.connect(self.choose_file)
        self.filename = QtGui.QLineEdit(self)
        self.filename.setMinimumWidth(300)
        self.filebox = QtGui.QHBoxLayout()
        self.filebox.addWidget(self.filebutton)
        self.filebox.addWidget(self.filename)
 
        self.buttonbox = QtGui.QDialogButtonBox(self)
        self.buttonbox.setOrientation(QtCore.Qt.Horizontal)
        self.buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        self.buttonbox.accepted.connect(self.accept)
        self.buttonbox.rejected.connect(self.reject)
 
    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path
        """
        import os
        fname, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open file',
            os.path.expanduser('~'))
        self.filename.setText(str(fname))

    def get_filename(self):
        return self.filename.text()

    def accept(self):
        self.accepted = True
        self.data = self.get_data()
        from nexpy.gui.consoleapp import _mainwindow
        _mainwindow.import_data()
        QtGui.QDialog.accept(self)
        
    def reject(self):
        self.accepted = False
        QtGui.QDialog.reject(self)