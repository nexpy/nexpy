# System library imports
from IPython.external.qt import QtGui,QtCore

# NeXpy imports
from nexpy.api.nexus import NXfield, NXgroup, NXdata

class PlotDialog(QtGui.QDialog):
    """Dialog to plot arbitrary NeXus data"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
        
        if isinstance(node, NXfield):
            plotlayout = QtGui.QHBoxLayout()
            self.plotbox = QtGui.QComboBox()
            for entry in self.node.nxgroup.entries:
                self.plotbox.addItem(node.nxgroup[entry].nxname)
            plotlabel = QtGui.QLabel("Choose x-axis: ")
            plotlayout.addWidget(plotlabel)
            plotlayout.addWidget(self.plotbox)

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(plotlayout)
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Plot NeXus Field")

    def get_axis(self):
        return self.plotbox.itemData(self.plotbox.currentIndex())
	
    def accept(self):
        data = NXdata(self.node, self.node.nxgroup[self.get_axis()])
        data.plot()
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
class RenameDialog(QtGui.QDialog):
    """Dialog to rename a NeXus node"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
 
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

    
