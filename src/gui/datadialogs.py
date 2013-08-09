# System library imports
from IPython.external.qt import QtGui,QtCore
import imp, os, re, sys
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
 
    def __init__(self, entry, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.data = entry.data

        from nexpy.gui.consoleapp import _tree
        self.tree = _tree
        
        self.functions = []
        self.parameters = []

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
        remove_button = QtGui.QPushButton("Remove Function")
        remove_button.clicked.connect(self.remove_function)
        self.removecombo = QtGui.QComboBox()
        self.removecombo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.removecombo.setMinimumWidth(100)
        self.remove_layout.addWidget(remove_button)
        self.remove_layout.addWidget(self.removecombo)
        self.remove_layout.addStretch()

        from nexpy.gui.consoleapp import _shell
        self.plot_layout = QtGui.QHBoxLayout()
        plot_data_button = QtGui.QPushButton('Plot Data')
        plot_data_button.clicked.connect(self.plot_data)
        plot_function_button = QtGui.QPushButton('Plot Function')
        plot_function_button.clicked.connect(self.plot_model)
        self.plotcombo = QtGui.QComboBox()
        self.plotcombo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.plotcombo.setMinimumWidth(100)
        plot_label = QtGui.QLabel('X-axis:')
        self.plot_minbox = QtGui.QLineEdit(str(_shell['plotview'].xtab.axis.min))
        self.plot_minbox.setAlignment(QtCore.Qt.AlignRight)
        plot_tolabel = QtGui.QLabel(' to ')
        self.plot_maxbox = QtGui.QLineEdit(str(_shell['plotview'].xtab.axis.max))
        self.plot_maxbox.setAlignment(QtCore.Qt.AlignRight)
        self.plot_checkbox = QtGui.QCheckBox('Use Data Points')
        self.plot_layout.addWidget(plot_data_button)
        self.plot_layout.addWidget(plot_function_button)
        self.plot_layout.addWidget(self.plotcombo)
        self.plot_layout.addWidget(plot_label)
        self.plot_layout.addWidget(self.plot_minbox)
        self.plot_layout.addWidget(plot_tolabel)
        self.plot_layout.addWidget(self.plot_maxbox)
        self.plot_layout.addWidget(self.plot_checkbox)
        self.plot_layout.addStretch()

        self.action_layout = QtGui.QHBoxLayout()
        fit_button = QtGui.QPushButton("Fit")
        fit_button.clicked.connect(self.fit_data)
        self.fit_label = QtGui.QLabel()
        self.report_button = QtGui.QPushButton("Show Fit Report")
        self.report_button.clicked.connect(self.report_fit)
        self.save_button = QtGui.QPushButton("Save Parameters")
        self.save_button.clicked.connect(self.save_fit)
        self.restore_button = QtGui.QPushButton("Restore Parameters")
        self.restore_button.clicked.connect(self.restore_parameters)
        self.action_layout.addWidget(fit_button)
        self.action_layout.addWidget(self.fit_label)
        self.action_layout.addStretch()
        self.action_layout.addWidget(self.save_button)

        button_box = QtGui.QDialogButtonBox(self)
        button_box.setOrientation(QtCore.Qt.Horizontal)
        button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                      QtGui.QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(function_layout)
        self.layout.addWidget(button_box)
        self.setLayout(self.layout)

        self.setWindowTitle("Fit NeXus Data")

        self.load_entry(entry)
        
        self.fitted = False

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
        headers = ['Function', 'Np', 'Name', 'Value', '', 'Min', 'Max', 'Fixed', 'Bound']
        width = [100, 50, 100, 100, 100, 100, 100, 50, 100]
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

    def compressed_name(self, name):
        return re.sub(r'([a-zA-Z]*) # (\d*)',r'\1\2', name)

    def expanded_name(self, name):
        return re.sub(r'([a-zA-Z]*)(\d*)',r'\1 # \2', name)
    
    def parse_function_name(self, name):
        match = re.match(r'([a-zA-Z]*)(\d*)',name)
        return match.group(1), match.group(2)

    def load_entry(self, entry):
        if 'fit' in entry.entries:
            for group in entry.entries:
                name, n = self.parse_function_name(group)
                if name in self.function_module:
                    module = self.function_module[name]
                    parameters = []
                    for p in module.parameters:
                        if p in entry[group].parameters.entries:
                            parameter = Parameter(p)
                            parameter.value = entry[group].parameters[p].nxdata
                            parameter.min = float(entry[group].parameters[p].attrs['min'].nxdata)
                            parameter.max = float(entry[group].parameters[p].attrs['max'].nxdata)                        
                            parameters.append(parameter)
                    f = Function(group, module, parameters)
                    self.add_function_rows(f, guess=False)
                
    def add_function(self):
        module = self.function_module[self.functioncombo.currentText()]
        name_index = [f.module.function_name for f in self.functions].count(module.function_name)
        name = '%s%s' %(module.function_name,str(name_index+1))
        parameters = [Parameter(p) for p in module.parameters]
        f = Function(name, module, parameters)
        self.add_function_rows(f)
    
    def add_function_rows(self, f, guess=True):
        self.add_parameter_rows(f)
        self.functions.append(f)
        if guess: self.guess_parameters()
        self.write_parameters()
        if self.removecombo.count() == 0:
            self.layout.insertLayout(1, self.parameter_grid)
            self.layout.insertLayout(2, self.remove_layout)
            self.layout.insertLayout(3, self.action_layout)
        self.removecombo.addItem(self.expanded_name(f.name))
        if self.plotcombo.count() == 0:
            self.layout.insertLayout(3, self.plot_layout)
            self.plotcombo.addItem('All')
            self.plotcombo.insertSeparator(1)
        self.plotcombo.addItem(self.expanded_name(f.name))

    def remove_function(self):
        name = self.compressed_name(self.removecombo.currentText())
        f=filter(lambda x: x.name==name, self.functions)[0]
        for row in f.rows:
            for column in range(9):
                item = self.parameter_grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        self.parameter_grid.removeWidget(widget)
                        widget.deleteLater()           
        self.functions.remove(f)
        self.plotcombo.removeItem(self.plotcombo.findText(expanded_name))
        self.removecombo.removeItem(self.removecombo.findText(expanded_name))
        del(f)

    def add_parameter_rows(self, f):        
        row = self.parameter_grid.rowCount()
        name = self.expanded_name(f.name)
        f.rows = []
        self.parameter_grid.addWidget(QtGui.QLabel(name), row, 0)
        for p in f.parameters:
            p.index = row
            p.value_box = QtGui.QLineEdit()
            p.value_box.setAlignment(QtCore.Qt.AlignRight)
            p.error_box = QtGui.QLabel()
            p.min_box = QtGui.QLineEdit('-inf')
            p.min_box.setAlignment(QtCore.Qt.AlignRight)
            p.max_box = QtGui.QLineEdit('inf')
            p.max_box.setAlignment(QtCore.Qt.AlignRight)
            p.fixed_box = QtGui.QCheckBox()
            p.bound_box = QtGui.QLineEdit()
            self.parameter_grid.addWidget(QtGui.QLabel(str(p.index)), row, 1,
                                          alignment = QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(QtGui.QLabel(p.name), row, 2)
            self.parameter_grid.addWidget(p.value_box, row, 3)
            self.parameter_grid.addWidget(p.error_box, row, 4)
            self.parameter_grid.addWidget(p.min_box, row, 5)
            self.parameter_grid.addWidget(p.max_box, row, 6)
            self.parameter_grid.addWidget(p.fixed_box, row, 7,
                                          alignment = QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(p.bound_box, row, 8)
            f.rows.append(row)
            row += 1

    def read_parameters(self):
        def make_float(value):
            try:
                return float(value)
            except:
                return None
        for f in self.functions:
            for p in f.parameters:
                p.value = make_float(p.value_box.text())
                p.min = make_float(p.min_box.text())
                p.max = make_float(p.max_box.text())
                p.vary = not p.fixed_box.checkState()

    def write_parameters(self):
        for f in self.functions:
            for p in f.parameters:
                if p.value:
                    p.value_box.setText('%.6g' % p.value)
                if p.vary and p.stderr:
                    p.error_box.setText('+/- %.6g' % p.stderr)
                else:
                    p.error_box.setText(' ')
                if p.min:
                    p.min_box.setText('%.6g' % p.min)
                if p.max:
                    p.max_box.setText('%.6g' % p.max)

    def guess_parameters(self):
        fit = Fit(self.data, self.functions)
        for f in self.functions:
            guess = f.module.guess(fit.x, fit.y)
            map(lambda p,g: p.__setattr__('value', g), f.parameters, guess)

    def get_model(self, f=None):
        self.read_parameters()
        fit = Fit(self.data, self.functions)
        if self.plot_checkbox.isChecked():
            x = fit.x
        else:
            x = np.linspace(float(self.plot_minbox.text()), 
                            float(self.plot_maxbox.text()), 201)
        return NXdata(NXfield(fit.get_model(x,f), name='model'),
                      NXfield(x, name=fit.data.nxaxes[0].nxname), 
                      title = 'Fit Results')
    
    def plot_data(self):
        self.data.plot()

    def plot_model(self):
        plot_function = self.plotcombo.currentText()
        if plot_function == 'All':
            self.get_model().oplot('-')
        else:
            name = self.compressed_name(plot_function)
            f=filter(lambda x: x.name==name, self.functions)[0]
            self.get_model(f).oplot('--')

    def fit_data(self):
        self.read_parameters()
        self.fit = Fit(self.data, self.functions)
        self.fit.fit_data()
        if self.fit.result.success:
            self.fit_label.setText('Fit Successful Chi^2 = %s' % self.fit.result.redchi)
        else:
            self.fit_label.setText('Fit Failed Chi^2 = %s' % self.fit.result.redchi)
        self.write_parameters()
        if not self.fitted:
            self.action_layout.addWidget(self.report_button)
            self.action_layout.addWidget(self.restore_button)
            self.save_button.setText('Save Fit')
        self.fitted = True

    def report_fit(self):
        message_box = QtGui.QMessageBox()
        message_box.setText("Fit Results")
        if self.fit.result.success:
            summary = 'Fit Successful'
        else:
            summary = 'Fit Failed'
        if self.fit.result.errorbars:
            errors = 'Uncertainties estimated'
        else:
            errors = 'Uncertainties not estimated'
        text = '%s\n' % summary +\
               '%s\n' % self.fit.result.message +\
               '%s\n' % self.fit.result.lmdif_message +\
               'scipy.optimize.leastsq error value = %s\n' % self.fit.result.ier +\
               'Chi^2 = %s\n' % self.fit.result.chisqr +\
               'Reduced Chi^2 = %s\n' % self.fit.result.redchi +\
               '%s\n' % errors +\
               'No. of Function Evaluations = %s\n' % self.fit.result.nfev +\
               'No. of Variables = %s\n' % self.fit.result.nvarys +\
               'No. of Data Points = %s\n' % self.fit.result.ndata +\
               'No. of Degrees of Freedom = %s\n' % self.fit.result.nfree +\
               '%s' % self.fit.fit_report()
        message_box.setInformativeText(text)
        message_box.setStandardButtons(QtGui.QMessageBox.Ok)
        spacer = QtGui.QSpacerItem(500, 0, 
                                   QtGui.QSizePolicy.Minimum, 
                                   QtGui.QSizePolicy.Expanding)
        layout = message_box.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        message_box.exec_()

    def save_fit(self):
        self.read_parameters()
        if 'w0' not in self.tree.keys():
            scratch_space = self.tree.add(NXroot(name='w0'))
        ind = []
        for key in self.tree['w0'].keys():
            try:
                if key.startswith('f'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if ind == []: ind = [0]
        name = 'f'+str(sorted(ind)[-1]+1)
        self.tree['w0'][name] = NXentry()
        self.tree['w0'][name].title = 'Fit Results'
        self.tree['w0'][name]['data'] = self.data
        self.tree['w0'][name]['fit'] = self.get_model()
        for f in self.functions:
            self.tree['w0'][name][f.name] = self.get_model(f)
            parameters = NXparameters()
            for p in f.parameters:
                parameters[p.name] = NXfield(p.value, error=p.stderr, 
                                             initial_value=p.init_value,
                                             min=str(p.min), max=str(p.max))
            self.tree['w0'][name][f.name].insert(parameters)
        fit = NXparameters()
        fit.nfev = self.fit.result.nfev
        fit.chisq = self.fit.result.chisqr
        fit.redchi = self.fit.result.redchi
        fit.message = self.fit.result.message
        fit.lmdif_message = self.fit.result.lmdif_message
        self.tree['w0'][name]['statistics'] = fit

    def restore_parameters(self):
        for f in self.functions:
            for p in f.parameters:
                p.value = p.init_value
                p.stderr = None
        self.fit_label.setText(' ')
        self.write_parameters()
   
    def accept(self):
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)
