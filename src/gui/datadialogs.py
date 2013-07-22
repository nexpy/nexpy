# System library imports
from IPython.external.qt import QtGui,QtCore
import os
import numpy as np

# NeXpy imports
from nexpy.api.nexus import NXfield, NXgroup, NXdata

class PlotDialog(QtGui.QDialog):
    """Dialog to plot arbitrary one-dimensional NeXus data"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
        
        if isinstance(node, NXfield):
            plotlayout = QtGui.QHBoxLayout()
            self.plotbox = QtGui.QComboBox()
            for entry in self.node.nxgroup.entries.values():
                if entry is not self.node and self.check_axis(entry):
                    self.plotbox.addItem(entry.nxname)
            self.plotbox.insertSeparator(0)
            self.plotbox.insertItem(0,'NXfield index')
            plotlabel = QtGui.QLabel("Choose x-axis: ")
            plotlayout.addWidget(plotlabel)
            plotlayout.addWidget(self.plotbox)

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(plotlayout)
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Plot NeXus Field")

    def get_axis(self):
        axis = self.plotbox.currentText()
        if axis == 'NXfield index':
            return NXfield(range(1,self.node.size+1), name='index')
        else:
            return self.node.nxgroup.entries[axis]

    def check_axis(self, axis):
        try:
            node_len, axis_len = self.node.shape[0], axis.shape[0]
            if axis_len == node_len or axis_len == node_len+1:
                return True
        except:
            pass
        return False
	
    def accept(self):
        data = NXdata(self.node, [self.get_axis()])
        print data.tree
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
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                     QtGui.QDialogButtonBox.Ok)
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

    
class FitDialog(QtGui.QDialog):
    """Dialog to fit one-dimensional NeXus data"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
        
        self.initialize_functions()
 
        functionlayout = QtGui.QHBoxLayout()
        label = QtGui.QLabel("New Name: ")
        self.namebox = QtGui.QLineEdit(node.nxname)
        self.namebox.setFixedWidth(200)
        namelayout.addWidget(label)
        namelayout.addWidget(self.namebox)

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(namelayout)
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Fit NeXus Data")

    def initialize_functions(self):

        base_path = os.path.abspath(os.path.dirname(__file__))
        self.functions_path = os.path.join(os.path.abspath(os.path.dirname(base_path)), 
                                           'models')
        filenames = set()
        for file in os.listdir(self.function_path):
            name, ext = os.path.splitext(file)
            if name <> '__init__' and ext.startswith('.py'):
                filenames.add(name)
        self.importer = {}
        for name in sorted(filenames):
            fp, pathname, description = imp.find_module(name)
            try:
                function_module = imp.load_module(name, fp, pathname, description)
            finally:
                if fp:
                    fp.close()
            self.importer[import_action] = import_module
        from pyspec import fitfuncs
        funcs = [fitfuncs.constant, fitfuncs.linear, fitfuncs.power, fitfuncs.gauss,
                 fitfuncs.lor, fitfuncs.lor2, fitfuncs.pvoight]
        x = p = 0
        names=[f(x,p,'name') for f in funcs]
        params = [f(x,p,'params') for f in funcs]
        self.functions = dict(zip(names,zip(funcs,params)))

    def functionbox(self):
        layout = QtGui.QHBoxLayout()
        functionbox = QtGui.QComboBox()
        for name in self.functions.keys():
            functionbox.addItem(name)
        addbutton = QtGui.QPushButton("Add Function")
        addbutton.clicked.connect(self.addfunction)
        layout.addWidget(functionbox)
        layout.addWidget(addbutton)
        

    def accept(self):
        self.node.rename(self.get_name())
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
