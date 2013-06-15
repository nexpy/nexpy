# System library imports
from IPython.external.qt import QtGui,QtCore

"""
Dialog for renaming a NeXus node
"""
class RenameDialog(QtGui.QDialog):
    """Dialog to select a text file"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
        self.view = parent
 
        namelayout = QtGui.QHBoxLayout()
        label = QtGui.QLabel("New Name: ")
        self.namebox = QtGui.QLineEdit(node.nxname)
        self.namebox.setFixedWidth(200)
        namelayout.addWidget(label)
        namelayout.addWidget(self.namebox)

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(namelayout)
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Rename NeXus Object")

    def get_name(self):
        return self.namebox.text()

    def accept(self):
        self.node.rename(self.get_name())
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
