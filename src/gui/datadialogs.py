# System library imports
from IPython.external.qt import QtGui,QtCore
import imp, os, sys
import numpy as np

# NeXpy imports
from nexpy.api.nexus import NXfield, NXgroup, NXroot, NXentry, NXdata, NXparameters
from nexpy.api.frills.fit import Fit, Function, Parameter

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
 
    def __init__(self, data, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.data = data
        
        self.functions = []
        self.parameters = []
        self.parameter_widgets = []

        self.initialize_functions()
 
        function_layout = QtGui.QHBoxLayout()
        self.functioncombo = QtGui.QComboBox()
        for name in sorted(self.function_module.keys()):
            self.functioncombo.addItem(name)
        self.functioncombo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.functioncombo.setMinimumWidth(100)
        add_button = QtGui.QPushButton("Add Function")
        add_button.clicked.connect(self.add_function)
        function_layout.addWidget(self.functioncombo)
        function_layout.addWidget(add_button)
        function_layout.addStretch()
        
        self.header_font = QtGui.QFont()
        self.header_font.setBold(True)

        self.parameter_grid = self.initialize_parameter_grid()

        self.remove_layout = QtGui.QHBoxLayout()
        self.removecombo = QtGui.QComboBox()
        remove_button = QtGui.QPushButton("Remove Function")
        remove_button.clicked.connect(self.remove_function)
        self.removecombo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.removecombo.setMinimumWidth(100)
        self.remove_layout.addWidget(remove_button)
        self.remove_layout.addWidget(self.removecombo)
        self.remove_layout.addStretch()

        from nexpy.gui.consoleapp import _shell
        preview_layout = QtGui.QHBoxLayout()
        preview_button = QtGui.QPushButton('Plot Calculation')
        preview_button.clicked.connect(self.plot_preview)
        preview_label = QtGui.QLabel('X-axis:')
        self.preview_minbox = QtGui.QLineEdit(str(_shell['plotview'].xtab.axis.min))
        self.preview_minbox.setAlignment(QtCore.Qt.AlignRight)
        preview_tolabel = QtGui.QLabel(' to ')
        self.preview_maxbox = QtGui.QLineEdit(str(_shell['plotview'].xtab.axis.max))
        self.preview_maxbox.setAlignment(QtCore.Qt.AlignRight)
        self.preview_checkbox = QtGui.QCheckBox('Use Data Points')
        preview_layout.addWidget(preview_button)
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.preview_minbox)
        preview_layout.addWidget(preview_tolabel)
        preview_layout.addWidget(self.preview_maxbox)
        preview_layout.addWidget(self.preview_checkbox)
        preview_layout.addStretch()

        action_layout = QtGui.QHBoxLayout()
        fit_button = QtGui.QPushButton("Fit")
        fit_button.clicked.connect(self.fit_data)
        action_layout.addWidget(fit_button)
        action_layout.addStretch()

        button_box = QtGui.QDialogButtonBox(self)
        button_box.setOrientation(QtCore.Qt.Horizontal)
        button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                      QtGui.QDialogButtonBox.Save)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(function_layout)
        self.layout.addLayout(self.parameter_grid)
        self.layout.addLayout(preview_layout)
        self.layout.addLayout(action_layout)
        self.layout.addWidget(button_box)
        self.setLayout(self.layout)

        self.setWindowTitle("Fit NeXus Data")

    def initialize_functions(self):

        base_path = os.path.abspath(os.path.dirname(__file__))
        functions_path = os.path.join(os.path.abspath(os.path.dirname(base_path)), 
                                           'api', 'frills', 'functions')
        sys.path.append(functions_path)
        filenames = set()
        for file in os.listdir(functions_path):
            name, ext = os.path.splitext(file)
            if name <> '__init__' and ext.startswith('.py'):
                filenames.add(name)
        self.function_module = {}
        for name in sorted(filenames):
            fp, pathname, description = imp.find_module(name)
            try:
                function_module = imp.load_module(name, fp, pathname, description)
            finally:
                if fp:
                    fp.close()
            if hasattr(function_module, 'function_name'):
                self.function_module[function_module.function_name] = function_module

    def initialize_parameter_grid(self):
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        headers = ['Function', 'Np', 'Name', 'Value', 'Min', 'Max', 'Fixed', 'Bound']
        width = [100, 50, 100, 100, 100, 100, 50, 100]
        column = 0
        for header in headers:
            label = QtGui.QLabel()
            label.setFont(self.header_font)
            label.setAlignment(QtCore.Qt.AlignHCenter)
            label.setText(header)
            grid.addWidget(label, 0, column)
            grid.setColumnMinimumWidth(column, width[column])
            column += 1
        return grid

    def add_function(self):
        module = self.function_module[self.functioncombo.currentText()]
        name_index = [f.module.function_name for f in self.functions].count(module.function_name)
        name = '%s # %s' %(module.function_name,str(name_index+1))
        parameters = [Parameter(parameter) for parameter in module.parameters]
        function = Function(name, module, parameters)
        self.add_parameter_rows(function)
        self.functions.append(function)
        if self.removecombo.count() == 0:
            self.layout.insertLayout(2, self.remove_layout)
        self.removecombo.addItem(name)

    def remove_function(self):
        pass
       
    def add_parameter_rows(self, function):        
        row = self.parameter_grid.rowCount()
        self.parameter_grid.addWidget(QtGui.QLabel(function.name), row, 0)
        for parameter in function.parameters:
            parameter.index = row
            parameter.value_box = QtGui.QLineEdit()
            parameter.min_box = QtGui.QLineEdit()
            parameter.max_box = QtGui.QLineEdit()
            parameter.fixed_box = QtGui.QCheckBox()
            parameter.bound_box = QtGui.QLineEdit()
            self.parameter_grid.addWidget(QtGui.QLabel(str(parameter.index)), row, 1,
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(QtGui.QLabel(parameter.name), row, 2)
            self.parameter_grid.addWidget(parameter.value_box, row, 3, 
                                          alignment=QtCore.Qt.AlignRight)
            self.parameter_grid.addWidget(parameter.min_box, row, 4, 
                                          alignment=QtCore.Qt.AlignRight)
            self.parameter_grid.addWidget(parameter.max_box, row, 5, 
                                          alignment=QtCore.Qt.AlignRight)
            self.parameter_grid.addWidget(parameter.fixed_box, row, 6, 
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(parameter.bound_box, row, 7)
            row += row

    def read_parameters(self):
        def make_float(value):
            try:
                return float(value)
            except:
                return None
        for function in self.functions:
            for parameter in function.parameters:
                parameter.value = make_float(parameter.value_box.text())
                parameter.minimum = make_float(parameter.min_box.text())
                parameter.maximum = make_float(parameter.max_box.text())
                parameter.fixed = parameter.fixed_box.checkState()

    def write_parameters(self):
        for function in self.functions:
            for parameter in function.parameters:
                if parameter.value:
                    parameter.value_box.setText('%.6g' % parameter.value)
                if parameter.minimum:
                    parameter.min_box.setText('%.6g' % parameter.minimum)
                if parameter.maximum:
                    parameter.max_box.setText('%.6g' % parameter.maximum)

    def get_preview(self):
        self.read_parameters()
        fit = Fit(self.data, self.functions)
        if self.preview_checkbox.isChecked():
            x = fit.x
        else:
            x = np.linspace(float(self.preview_minbox.text()), 
                            float(self.preview_maxbox.text()), 201)
        return NXdata(NXfield(fit.get_calculation(x), name='calculation'),
                     NXfield(x, name=fit.data.nxaxes[0].nxname), 
                     title = fit.data.nxtitle)
    
    def plot_preview(self):
        self.get_preview().oplot('-')

    def fit_data(self):
        self.read_parameters()
        fit = Fit(self.data, self.functions)
        fit.fit_data()
        self.write_parameters()        

    def accept(self):
        self.read_parameters()
        fit = NXparameters()
        for function in self.functions:
            parameters = NXparameters()
            for parameter in function.parameters:
                parameters[parameter.name] = NXfield(parameter.value, 
                                                minimum=parameter.minimum,
                                                maximum=parameter.maximum)
            fit[function.name.replace(' ','_')] = parameters

        from nexpy.gui.consoleapp import _tree
        if 'w0' not in _tree.keys():
            scratch_space = _tree.add(NXroot(name='w0'))
        ind = []
        for key in _tree['w0'].keys():
            try:
                if key.startswith('f'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if ind == []: ind = [0]
        name = 'f'+str(sorted(ind)[-1]+1)
        _tree['w0'][name] = NXentry()
        _tree['w0'][name]['data'] = self.data
        _tree['w0'][name]['fit'] = self.get_preview()
        _tree['w0'][name]['parameters'] = fit

        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
