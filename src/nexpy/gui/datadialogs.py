#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import imp
import os
import re
import sys

from PySide import QtGui, QtCore
import pkg_resources
import numpy as np

from nexpy.api.nexus import NXfield, NXgroup, NXattr, NXroot, NXentry, NXdata, NXparameters


try:
    from nexpy.api.frills.fit import Fit, Function, Parameter
except ImportError:
    pass


class PlotDialog(QtGui.QDialog):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
        self.dims = len(self.node.shape)
        
        if isinstance(node, NXfield):
            plotlayout = QtGui.QHBoxLayout()
            if self.dims == 1:
                plotlabel = [QtGui.QLabel("Choose x-axis: ")]
                self.plotbox = [self.axis_box(0)]
                plotlayout.addWidget(plotlabel[0])
                plotlayout.addWidget(self.plotbox[0])
            else:
                plotlabel = [QtGui.QLabel("Choose x-axis: "),
                             QtGui.QLabel("Choose y-axis: ")]
                self.plotbox = [self.axis_box(0), self.axis_box(1)]
                plotlayout.addWidget(plotlabel[1])
                plotlayout.addWidget(self.plotbox[1])
                plotlayout.addWidget(plotlabel[0])
                plotlayout.addWidget(self.axis_box[0])
        else:
            plotlayout = None

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        if plotlayout:
            layout.addLayout(plotlayout)
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Plot NeXus Field")

    def axis_box(self, axis):
        plotbox = QtGui.QComboBox()
        for node in self.node.nxgroup.entries.values():
            if node is not self.node and self.check_axis(node, axis):
                plotbox.addItem(node.nxname)
        plotbox.insertSeparator(0)
        plotbox.insertItem(0,'NXfield index')
        if 'axes' in self.node.attrs:
            from nexpy.api.nexus.tree import _readaxes
            default_axis = _readaxes(self.node.axes)[axis]
        elif self.node.nxgroup.nxaxes:
            default_axis = self.node.nxgroup.nxaxes[axis].nxname
        else:
            default_axis = None
        if default_axis:
            try:
                plotbox.setCurrentIndex(plotbox.findText(default_axis))
            except Exception:
                pass
        return plotbox

    def check_axis(self, node, axis):
        if len(node.shape) > 1:
            return False
        try:
            node_len, axis_len = self.node.shape[axis], node.shape[0]
            if axis_len == node_len or axis_len == node_len+1:
                return True
        except Exception:
            pass
        return False

    def get_axis(self, axis):
        axis_name = self.plotbox[axis].currentText()
        if axis_name == 'NXfield index':
            return NXfield(range(1, self.node.size+1), name='index')
        else:
            return self.node.nxgroup.entries[axis_name]

    def get_axes(self):
        if self.dims == 1:
            return [self.get_axis(0)]
        else:
            return [self.get_axis(0), self.get_axis(1)]

    def accept(self):
        data = NXdata(self.node, self.get_axes())
        data.plot()
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
class AddDialog(QtGui.QDialog):
    """Dialog to add a NeXus node"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16', 
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)

        self.node = node

        class_layout = QtGui.QHBoxLayout()
        class_button = QtGui.QPushButton("Add")
        class_button.clicked.connect(self.select_class)
        self.class_box = QtGui.QComboBox()
        if isinstance(self.node, NXgroup):
            names = ['NXgroup', 'NXfield']
        else:
            names = ['NXattr']
        for name in names:
            self.class_box.addItem(name)
        class_layout.addWidget(class_button)
        class_layout.addWidget(self.class_box)
        class_layout.addStretch()       

        if isinstance(self.node, NXfield):
            self.setWindowTitle("Add NeXus Attribute")
        else:
            self.setWindowTitle("Add NeXus Data")

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(class_layout)
        self.layout.addWidget(buttonbox) 
        self.setLayout(self.layout)

    def select_class(self):
        self.class_name = self.class_box.currentText()
        if self.class_name == "NXgroup":
            self.layout.insertLayout(1, self.define_grid("NXgroup"))
        else:
            self.layout.insertLayout(1, self.define_grid("NXfield"))

    def define_grid(self, class_name):
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)

        name_label = QtGui.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("Name:")
        self.name_box = QtGui.QLineEdit()
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        if class_name == "NXgroup":
            type_label = QtGui.QLabel()
            type_label.setAlignment(QtCore.Qt.AlignLeft)
            type_label.setText("Group Class:")
            self.type_box = QtGui.QComboBox()
            from nexpy.api.nexus.tree import nxclasses
            for name in nxclasses:
                if name != 'NXroot':
                    self.type_box.addItem(name)
            self.type_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            grid.addWidget(type_label, 0, 0)
            grid.addWidget(self.type_box, 0, 1)
            grid.addWidget(name_label, 1, 0)
            grid.addWidget(self.name_box, 1, 1)
        else:
            grid.addWidget(name_label, 0, 0)
            grid.addWidget(self.name_box, 0, 1)
            value_label = QtGui.QLabel()
            value_label.setAlignment(QtCore.Qt.AlignLeft)
            value_label.setText("Value:")
            self.value_box = QtGui.QLineEdit()
            self.value_box.setAlignment(QtCore.Qt.AlignLeft)
            grid.addWidget(value_label, 1, 0)
            grid.addWidget(self.value_box, 1, 1)
            type_label = QtGui.QLabel()
            type_label.setAlignment(QtCore.Qt.AlignLeft)
            type_label.setText("Datatype:")
            self.type_box = QtGui.QComboBox()
            for name in self.data_types:
                self.type_box.addItem(name)
            self.type_box.insertSeparator(0)
            self.type_box.insertItem(0, 'auto')
            self.type_box.setCurrentIndex(0)
            self.type_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            grid.addWidget(type_label, 2, 0)
            grid.addWidget(self.type_box, 2, 1)
        grid.setColumnMinimumWidth(1, 200)
        return grid

    def get_name(self):
        return self.name_box.text()

    def get_value(self):
        value = self.value_box.text()
        if value:
            dtype = self.get_type()
            if dtype == "char":
                return value
            else:
                from nexpy.gui.consoleapp import _shell
                try:
                    return eval(value, {"__builtins__": {}}, _shell)
                except Exception:
                    return str(value)
        else:
            return None

    def get_type(self):
        dtype = self.type_box.currentText()
        if dtype == "auto":
            return None
        else:
            return dtype 

    def accept(self):
        name = self.get_name()
        if self.class_name == "NXgroup":
            nxclass = self.get_type()
            if name:
                self.node[name] = NXgroup(nxclass=nxclass)
            else:
                self.node.insert(NXgroup(nxclass=nxclass))
        elif name:
            value = self.get_value()
            dtype = self.get_type()
            if value is not None:
                if self.class_name == "NXfield":
                    self.node[name] = NXfield(value, dtype=dtype)
                else:
                    self.node.attrs[name] = NXattr(value, dtype=dtype)
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
class InitializeDialog(QtGui.QDialog):
    """Dialog to initialize a NeXus field node"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16', 
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node

        self.setWindowTitle("Initialize NeXus Data")

        grid = QtGui.QGridLayout()
        grid.setSpacing(10)

        name_label = QtGui.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("Name:")
        self.name_box = QtGui.QLineEdit()
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        type_label = QtGui.QLabel()
        type_label.setAlignment(QtCore.Qt.AlignLeft)
        type_label.setText("Datatype:")
        self.type_box = QtGui.QComboBox()
        for name in self.data_types:
            self.type_box.addItem(name)
        self.type_box.setCurrentIndex(0)
        self.type_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        grid.addWidget(type_label, 2, 0)
        grid.addWidget(self.type_box, 2, 1)
        shape_label = QtGui.QLabel()
        shape_label.setAlignment(QtCore.Qt.AlignLeft)
        shape_label.setText("Shape:")
        self.shape_box = QtGui.QLineEdit()
        self.shape_box.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(shape_label, 3, 0)
        grid.addWidget(self.shape_box, 3, 1)
        grid.setColumnMinimumWidth(1, 200)

        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(grid)
        self.layout.addWidget(buttonbox) 
        self.setLayout(self.layout)

    def get_name(self):
        return self.name_box.text()

    def get_type(self):
        dtype = self.type_box.currentText()
        return dtype 

    def get_shape(self):
        import ast
        try:
            return ast.literal_eval(self.shape_box.text())
        except ValueError:
            return None

    def accept(self):
        name = self.get_name()
        if name:
            dtype = self.get_type()
            if dtype is None:
                dtype = np.float64
            shape = self.get_shape()
            self.node[name] = NXfield(dtype=dtype, shape=shape)
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
class RemoveDialog(QtGui.QDialog):
    """Dialog to remove a NeXus node from the tree"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
 
        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(QtGui.QLabel('Are you sure you want to remove "%s"?' 
                                      % node.nxname))
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Remove NeXus File")

    def accept(self):
        del self.node.nxgroup[self.node.nxname]
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
class DeleteDialog(QtGui.QDialog):
    """Dialog to delete a NeXus node"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
 
        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addWidget(QtGui.QLabel('Are you sure you want to delete "%s"?' 
                                      % node.nxname))
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Delete NeXus Data")

    def accept(self):
        del self.node.nxgroup[self.node.nxname]
        QtGui.QDialog.accept(self)
        
    def reject(self):
        QtGui.QDialog.reject(self)

    
class SignalDialog(QtGui.QDialog):
    """Dialog to set the signal of NXdata"""
 
    def __init__(self, node, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.node = node
        self.dims = len(self.node.shape)
        
        signal_layout = QtGui.QHBoxLayout()
        signal_label = QtGui.QLabel("Signal Attribute")
        self.signal_box = QtGui.QLineEdit("1")
        signal_layout.addWidget(signal_label)
        signal_layout.addWidget(self.signal_box)

        axis_layout = [QtGui.QHBoxLayout()]
        axis_label = [QtGui.QLabel("Choose Axis 0: ")]
        self.axis_boxes = [self.axis_box(0)]
        axis_layout[0].addWidget(axis_label[0])
        axis_layout[0].addWidget(self.axis_boxes[0])
        for axis in range(1, self.dims):
            axis_layout.append(QtGui.QHBoxLayout())
            axis_label.append(QtGui.QLabel("Choose Axis %s: " % axis))
            self.axis_boxes.append(self.axis_box(axis))
            axis_layout[axis].addWidget(axis_label[axis])
            axis_layout[axis].addWidget(self.axis_boxes[axis])
 
        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                     QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)

        layout = QtGui.QVBoxLayout()
        layout.addLayout(signal_layout)
        for axis in range(self.dims):
            layout.addLayout(axis_layout[axis])
        layout.addWidget(buttonbox) 
        self.setLayout(layout)

        self.setWindowTitle("Set %s as Signal" % self.node.nxname)

    def axis_box(self, axis=0):
        axisbox = QtGui.QComboBox()
        for node in self.node.nxgroup.entries.values():
            if node is not self.node and self.check_axis(node, axis):
                axisbox.addItem(node.nxname)
        if 'axes' in self.node.attrs:
            from nexpy.api.nexus.tree import _readaxes
            default_axis = _readaxes(self.node.axes)[axis]
        elif self.node.nxgroup.nxaxes:
            default_axis = self.node.nxgroup.nxaxes[axis].nxname
        else:
            default_axis = None
        if default_axis:
            try:
                axisbox.setCurrentIndex(axisbox.findText(default_axis))
            except Exception:
                pass
        return axisbox

    def check_axis(self, node, axis):
        if len(node.shape) > 1:
            return False
        try:
            node_len, axis_len = self.node.shape[axis], node.shape[0]
            if axis_len == node_len or axis_len == node_len+1:
                return True
        except Exception:
            pass
        return False

    def get_axes(self):
        return [str(self.axis_boxes[axis].currentText()) 
                for axis in range(self.dims)]

    def accept(self):
        signal = int(self.signal_box.text())
        if signal == 1:
            self.node.nxgroup.nxsignal = self.node
        else:
            self.node.attrs["signal"] = signal
        self.node.axes = ":".join(self.get_axes())
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

        from nexpy.gui.plotview import change_plotview
        self.plotview = change_plotview("Fit")
        self.plotview.setMinimumSize(700, 300)
        self.plotview.setMaximumSize(1200, 500)
        
        self.data.plot()
        
        self.functions = []
        self.parameters = []

        self.first_time = True
        self.fitted = False
        self.fit = None

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

        self.plot_layout = QtGui.QHBoxLayout()
        plot_data_button = QtGui.QPushButton('Plot Data')
        plot_data_button.clicked.connect(self.plot_data)
        plot_function_button = QtGui.QPushButton('Plot Function')
        plot_function_button.clicked.connect(self.plot_model)
        self.plotcombo = QtGui.QComboBox()
        self.plotcombo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.plotcombo.setMinimumWidth(100)
        plot_label = QtGui.QLabel('X-axis:')
        self.plot_minbox = QtGui.QLineEdit(str(self.plotview.xtab.axis.min))
        self.plot_minbox.setAlignment(QtCore.Qt.AlignRight)
        plot_tolabel = QtGui.QLabel(' to ')
        self.plot_maxbox = QtGui.QLineEdit(str(self.plotview.xtab.axis.max))
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
        self.fit_checkbox = QtGui.QCheckBox('Use Errors')
        if self.data.nxerrors:
            self.fit_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.fit_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.fit_checkbox.setVisible(False)
        self.report_button = QtGui.QPushButton("Show Fit Report")
        self.report_button.clicked.connect(self.report_fit)
        self.save_button = QtGui.QPushButton("Save Parameters")
        self.save_button.clicked.connect(self.save_fit)
        self.restore_button = QtGui.QPushButton("Restore Parameters")
        self.restore_button.clicked.connect(self.restore_parameters)
        self.action_layout.addWidget(fit_button)
        self.action_layout.addWidget(self.fit_checkbox)
        self.action_layout.addWidget(self.fit_label)
        self.action_layout.addStretch()
        self.action_layout.addWidget(self.save_button)

        button_box = QtGui.QDialogButtonBox(self)
        button_box.setOrientation(QtCore.Qt.Horizontal)
        button_box.setStandardButtons(QtGui.QDialogButtonBox.Cancel |
                                      QtGui.QDialogButtonBox.Ok)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        scroll_area = QtGui.QScrollArea()
        scroll_area.setWidgetResizable(True)
        self.scroll_widget = QtGui.QWidget()
        self.scroll_widget.setMinimumWidth(800)
        self.scroll_widget.setMaximumHeight(800)
        self.scroll_widget.setSizePolicy(QtGui.QSizePolicy.Expanding, 
                                         QtGui.QSizePolicy.Expanding)
        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(function_layout)
        self.layout.addWidget(button_box)
        self.scroll_widget.setLayout(self.layout)
        scroll_area.setWidget(self.scroll_widget)
        layout = QtGui.QVBoxLayout()
        layout.addWidget(self.plotview)
        layout.addWidget(scroll_area)
        self.setLayout(layout)

        self.setWindowTitle("Fit NeXus Data")

        self.load_entry(entry)

    def initialize_functions(self):

        filenames = set()
        private_path = os.path.join(os.path.expanduser('~'), '.nexpy', 
                                    'functions')
        if os.path.isdir(private_path):
            sys.path.append(private_path)
            for file_ in os.listdir(private_path):
                name, ext = os.path.splitext(file_)
                if name != '__init__' and ext.startswith('.py'):
                    filenames.add(name)
        functions_path = pkg_resources.resource_filename('nexpy.api.frills', 'functions')
        sys.path.append(functions_path)
        for file_ in os.listdir(functions_path):
            name, ext = os.path.splitext(file_)
            if name != '__init__' and ext.startswith('.py'):
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
        return re.sub(r'([a-zA-Z]*) # (\d*)', r'\1\2', name)

    def expanded_name(self, name):
        return re.sub(r'([a-zA-Z]*)(\d*)', r'\1 # \2', name)
    
    def parse_function_name(self, name):
        match = re.match(r'([a-zA-Z]*)(\d*)', name)
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
                    f = Function(group, module, parameters, n)
                    self.functions.append(f)
            self.functions = sorted(self.functions)
            for f in self.functions:
                self.add_function_rows(f)
            self.write_parameters()
               
    def add_function(self):
        module = self.function_module[self.functioncombo.currentText()]
        function_index = len(self.functions) + 1
        name = '%s%s' % (module.function_name, str(function_index))
        parameters = [Parameter(p) for p in module.parameters]
        f = Function(name, module, parameters, function_index)
        self.functions.append(f)
        self.index_parameters()
        self.guess_parameters()
        self.add_function_rows(f)
        self.write_parameters()
        self.scroll_widget.adjustSize()
 
    def index_parameters(self):
        np = 0
        for f in sorted(self.functions):
            for p in f.parameters:
                np += 1
                p.parameter_index = np
    
    def add_function_rows(self, f):
        self.add_parameter_rows(f)
        if self.first_time:
            self.layout.insertLayout(1, self.parameter_grid)
            self.layout.insertLayout(2, self.remove_layout)
            self.layout.insertLayout(3, self.plot_layout)
            self.layout.insertLayout(4, self.action_layout)
            self.plotcombo.addItem('All')
            self.plotcombo.insertSeparator(1)
        self.removecombo.addItem(self.expanded_name(f.name))
        self.plotcombo.addItem(self.expanded_name(f.name))
        self.first_time = False

    def remove_function(self):
        expanded_name = self.removecombo.currentText()
        name = self.compressed_name(expanded_name)
        f = filter(lambda x: x.name == name, self.functions)[0]
        for row in f.rows:
            for column in range(9):
                item = self.parameter_grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)
                        self.parameter_grid.removeWidget(widget)
                        widget.deleteLater()           
        self.functions.remove(f)
        self.plotcombo.removeItem(self.plotcombo.findText(expanded_name))
        self.removecombo.removeItem(self.removecombo.findText(expanded_name))
        del f
        nf = 0
        np = 0
        for f in sorted(self.functions):
            nf += 1
            name = '%s%s' % (f.module.function_name, str(nf))
            self.rename_function(f.name, name)
            f.name = name
            f.label_box.setText(self.expanded_name(f.name))
            for p in f.parameters:
                np += 1
                p.parameter_index = np
                p.parameter_box.setText(str(p.parameter_index))     

    def rename_function(self, old_name, new_name):
        old_name, new_name = self.expanded_name(old_name), self.expanded_name(new_name)
        plot_index = self.plotcombo.findText(old_name)
        self.plotcombo.setItemText(plot_index, new_name)
        remove_index = self.removecombo.findText(old_name)
        self.removecombo.setItemText(remove_index, new_name)
        
    def add_parameter_rows(self, f):        
        row = self.parameter_grid.rowCount()
        name = self.expanded_name(f.name)
        f.rows = []
        f.label_box = QtGui.QLabel(name)
        self.parameter_grid.addWidget(f.label_box, row, 0)
        for p in f.parameters:
            p.parameter_index = row
            p.parameter_box = QtGui.QLabel(str(p.parameter_index))
            p.value_box = QtGui.QLineEdit()
            p.value_box.setAlignment(QtCore.Qt.AlignRight)
            p.error_box = QtGui.QLabel()
            p.min_box = QtGui.QLineEdit('-inf')
            p.min_box.setAlignment(QtCore.Qt.AlignRight)
            p.max_box = QtGui.QLineEdit('inf')
            p.max_box.setAlignment(QtCore.Qt.AlignRight)
            p.fixed_box = QtGui.QCheckBox()
            p.bound_box = QtGui.QLineEdit()
            self.parameter_grid.addWidget(p.parameter_box, row, 1,
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(QtGui.QLabel(p.name), row, 2)
            self.parameter_grid.addWidget(p.value_box, row, 3)
            self.parameter_grid.addWidget(p.error_box, row, 4)
            self.parameter_grid.addWidget(p.min_box, row, 5)
            self.parameter_grid.addWidget(p.max_box, row, 6)
            self.parameter_grid.addWidget(p.fixed_box, row, 7,
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(p.bound_box, row, 8)
            f.rows.append(row)
            row += 1

    def read_parameters(self):
        def make_float(value):
            try:
                return float(value)
            except Exception:
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
                if p.parameter_index:
                    p.parameter_box.setText(str(p.parameter_index))
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
        y = np.array(fit.y)
        for f in self.functions:
            guess = f.module.guess(fit.x, y)
            map(lambda p, g: p.__setattr__('value', g), f.parameters, guess)
            y = y - f.module.values(fit.x, guess)

    def get_model(self, f=None):
        self.read_parameters()
        fit = Fit(self.data, self.functions)
        if self.plot_checkbox.isChecked():
            x = fit.x
        else:
            x = np.linspace(float(self.plot_minbox.text()), 
                            float(self.plot_maxbox.text()), 1001)
        return NXdata(NXfield(fit.get_model(x, f), name='model'),
                      NXfield(x, name=fit.data.nxaxes[0].nxname), 
                      title='Fit Results')
    
    def plot_data(self):
        self.data.plot()

    def plot_model(self):
        plot_function = self.plotcombo.currentText()
        if plot_function == 'All':
            self.get_model().oplot('-')
        else:
            name = self.compressed_name(plot_function)
            f = filter(lambda x: x.name == name, self.functions)[0]
            self.get_model(f).oplot('--')

    def fit_data(self):
        self.read_parameters()
        if self.fit_checkbox.isChecked():
            use_errors = True
        else:
            use_errors = False
        from nexpy.gui.mainwindow import report_error
        try:
            self.fit = Fit(self.data, self.functions, use_errors)
            self.fit.fit_data()
        except Exception as error:
            report_error("Fitting Data", error)
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
        """Saves fit results to an NXentry"""
        self.read_parameters()
        entry = NXentry()
        entry['title'] = 'Fit Results'
        entry['data'] = self.data
        entry['fit'] = self.get_model()
        for f in self.functions:
            entry[f.name] = self.get_model(f)
            parameters = NXparameters()
            for p in f.parameters:
                parameters[p.name] = NXfield(p.value, error=p.stderr, 
                                             initial_value=p.init_value,
                                             min=str(p.min), max=str(p.max))
            entry[f.name].insert(parameters)
        fit = NXparameters()
        fit.nfev = self.fit.result.nfev
        fit.ier = self.fit.result.ier 
        fit.chisq = self.fit.result.chisqr
        fit.redchi = self.fit.result.redchi
        fit.message = self.fit.result.message
        fit.lmdif_message = self.fit.result.lmdif_message
        entry['statistics'] = fit
        if 'w0' not in self.tree.keys():
            self.tree.add(NXroot(name='w0'))
        ind = []
        for key in self.tree['w0'].keys():
            try:
                if key.startswith('f'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if not ind:
            ind = [0]
        name = 'f'+str(sorted(ind)[-1]+1)
        self.tree['w0'][name] = entry

    def restore_parameters(self):
        for f in self.functions:
            for p in f.parameters:
                p.value = p.init_value
                p.stderr = None
        self.fit_label.setText(' ')
        self.write_parameters()
   
    def accept(self):
        self.plotview.close_view()
        QtGui.QDialog.accept(self)
        
    def reject(self):
        self.plotview.close_view()
        QtGui.QDialog.reject(self)

    def closeEvent(self, event):
        self.plotview.close_view()
        event.accept()
