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
import logging
import os
import re
import sys

from PySide import QtGui, QtCore
import pkg_resources
import numpy as np

from nexpy.api.nexus import (NeXusError, NXgroup, NXfield, NXattr,
                             NXroot, NXentry, NXdata, NXparameters)


try:
    from nexpy.api.frills.fit import Fit, Function, Parameter
except ImportError:
    pass

def wrap(text, length):
    words = text.split()
    lines = []
    line = ''
    for w in words:
        if len(w) + len(line) > length:
            lines.append(line)
            line = ''
        line = line + w + ' '
        if w is words[-1]: lines.append(line)
    return '\n'.join(lines)

def natural_sort(key):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]    


class BaseDialog(QtGui.QDialog):
    """Base dialog class for NeXpy dialogs"""
 
    def __init__(self, parent=None):


        self.accepted = False
        from nexpy.gui.consoleapp import _mainwindow
        self.mainwindow = _mainwindow
        self.treeview = self.mainwindow.treeview
        self.default_directory = _mainwindow.default_directory
        self.import_file = None     # must define in subclass
        self.nexus_filter = ';;'.join((
             "NeXus Files (*.nxs *.nx5 *.h5 *.hdf *.hdf5)",
	         "Any Files (*.* *)"))

        if parent is None:
            parent = self.mainwindow
        super(BaseDialog, self).__init__(parent)

    def buttonbox(self, save=False):
        """
        Creates a box containing the standard Cancel and OK buttons.
        """
        buttonbox = QtGui.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        if save:
            buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                         QtGui.QDialogButtonBox.Save)
        else:
            buttonbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|
                                         QtGui.QDialogButtonBox.Ok)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        return buttonbox

    def filebox(self):
        """
        Creates a text box and button for selecting a file.
        """
        self.filebutton =  QtGui.QPushButton("Choose File")
        self.filebutton.clicked.connect(self.choose_file)
        self.filename = QtGui.QLineEdit(self)
        self.filename.setMinimumWidth(300)
        filebox = QtGui.QHBoxLayout()
        filebox.addWidget(self.filebutton)
        filebox.addWidget(self.filename)
        return filebox
 
    def directorybox(self):
        """
        Creates a text box and button for selecting a directory.
        """
        self.directorybutton =  QtGui.QPushButton("Choose Directory")
        self.directorybutton.clicked.connect(self.choose_directory)
        self.directoryname = QtGui.QLineEdit(self)
        self.directoryname.setMinimumWidth(300)
        directorybox = QtGui.QHBoxLayout()
        directorybox.addWidget(self.directorybutton)
        directorybox.addWidget(self.directoryname)
        return directorybox

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.filename.text())
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open File',
            dirname)
        if os.path.exists(filename):    # avoids problems if <Cancel> was selected
            dirname = os.path.dirname(filename)
            self.filename.setText(str(filename))
            self.set_default_directory(dirname)

    def get_filename(self):
        """
        Returns the selected file.
        """
        return self.filename.text()

    def choose_directory(self):
        """
        Opens a file dialog and sets the directory text box to the chosen path.
        """
        dirname = self.get_default_directory()
        dirname = QtGui.QFileDialog.getExistingDirectory(self, 'Choose Directory',
            dir=dirname)
        if os.path.exists(dirname):    # avoids problems if <Cancel> was selected
            self.directoryname.setText(str(dirname))
            self.set_default_directory(dirname)

    def get_directory(self):
        """
        Returns the selected directory
        """
        return self.directoryname.text()
    
    def get_default_directory(self, suggestion=None):
        '''return the most recent default directory for open/save dialogs'''
        if suggestion is None or not os.path.exists(suggestion):
            suggestion = self.default_directory
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
        suggestion = os.path.abspath(suggestion)
        return suggestion
    
    def set_default_directory(self, suggestion):
        '''define the default directory to use for open/save dialogs'''
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
            self.default_directory = suggestion

    def get_filesindirectory(self, prefix='', extension='.*', directory=None):
        """
        Returns a list of files in the selected directory.
        
        The files are sorted using a natural sort algorithm that preserves the
        numeric order when a file name consists of text and index so that, e.g., 
        'data2.tif' comes before 'data10.tif'.
        """
        if directory:
            os.chdir(directory)
        else:
            os.chdir(self.get_directory())
        if not extension.startswith('.'):
            extension = '.'+extension
        from glob import glob
        filenames = glob(prefix+'*'+extension)
        return sorted(filenames,key=natural_sort)

    def parameter_grid(self, parameters):
        """
        Returns a Qt grid layout with one row for each parameter.
        
        'parameters' should be a list of parameters, each one of which is a 
        tuple containing the parameter label and its default value. If the 
        default value is a list or tuple, a QComboBox will be used instead of
        a QLineEdit to select the parameter.
        """
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.grid_row = {}
        row = 0
        for parameter in parameters:
            label, value = parameter
            self.grid_row[label].label = QtGui.QLabel(label)
            if isinstance(value, list) or isinstance(value, tuple):
                self.grid_row[label].box = QtGui.QComboBox()
                self.grid_row[label].box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
                for v in value:
                    self.grid_row[label].box.addItem(str(v))
            else:
                self.grid_row[label].box = QtGui.QLineEdit()
                if value is not None:
                    self.grid_row[label].box.setText(str(value))
            grid.addWidget(self.grid_row[label].label, row, 0)
            grid.addWidget(self.grid_row[label].box, row, 1)
            row += 1
        return grid 

    def get_parameter(self, label):
        return self.grid_row[label].box.text()
 
    def read_parameter(self, root, path):
        """
        Read the value from the NeXus path.
        
        It will return 'None' if the path is not valid.
        """
        try:
            value = root[path].nxdata
            if isinstance(value, np.ndarray) and value.size == 1:
                return np.float32(value)
            else:
                return value
        except NeXusError:
            return None 

    def accept(self):
        """
        Accepts the result.
        
        This usually needs to be subclassed in each dialog.
        """
        self.accepted = True
        QtGui.QDialog.accept(self)
        
    def reject(self):
        """
        Cancels the dialog without saving the result.
        """
        self.accepted = False
        QtGui.QDialog.reject(self)

    def update_progress(self):
        """
        Call the main QApplication.processEvents
        
        This ensures that GUI items like progress bars get updated
        """
        self.mainwindow._app.processEvents()

    def progress_layout(self, save=False):
        layout = QtGui.QHBoxLayout()
        self.progress_bar = QtGui.QProgressBar()
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        layout.addWidget(self.buttonbox(save))
        return layout

    def get_node(self):
        """
        Return the node currently selected in the treeview
        """
        return self.treeview.get_node()

    def confirm_action(self, query, information=None):
        msgBox = QtGui.QMessageBox()
        msgBox.setText(query)
        if information:
            msgBox.setInformativeText(information)
        msgBox.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
        msgBox.setDefaultButton(QtGui.QMessageBox.Ok)
        return msgBox.exec_()


class PlotDialog(BaseDialog):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""
 
    def __init__(self, node, parent=None):

        super(PlotDialog, self).__init__(parent)
 
        if isinstance(node, NXfield):
            self.group = node.nxgroup
            signal_name = node.nxname
        else:
            self.group = node
            signal_name = None

        self.signal_combo =  QtGui.QComboBox() 
        for node in self.group.values():
            if isinstance(node, NXfield):
                if node.shape != ():
                    self.signal_combo.addItem(node.nxname)
        if self.signal_combo.count() == 0:
            raise NeXusError("No plottable field in group")
        self.signal_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        if signal_name:
            idx =  self.signal_combo.findText(signal_name)
            if idx >= 0:
                self.signal_combo.setCurrentIndex(idx)
            else:
                signal_name = None
        self.signal_combo.currentIndexChanged.connect(self.choose_signal)
 
        self.grid = QtGui.QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(QtGui.QLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.choose_signal()

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.grid)
        self.layout.addWidget(self.buttonbox())
        self.setLayout(self.layout)

        self.setWindowTitle("Plot NeXus Data")

    @property
    def signal(self):
        return self.group[self.signal_combo.currentText()]

    @property
    def dims(self):
        return len(self.signal.shape)

    def choose_signal(self):
        row = 0
        self.axis_boxes = {}
        for axis in range(self.dims):
            row += 1
            self.grid.addWidget(QtGui.QLabel("Axis %s: " % axis), row, 0)
            self.axis_boxes[axis] = self.axis_box(axis)
            self.grid.addWidget(self.axis_boxes[axis], row, 1)
        while row < self.grid.rowCount() - 1:
            self.remove_axis(row)
            row += 1   

    def axis_box(self, axis):
        box = QtGui.QComboBox()
        for node in self.group.values():
            if isinstance(node, NXfield) and node is not self.signal:
                if self.check_axis(node, axis):
                    box.addItem(node.nxname)
        if box.count() > 0:
            box.insertSeparator(0)
        box.insertItem(0,'NXfield index')
        if 'axes' in self.signal.attrs:
            from nexpy.api.nexus.tree import _readaxes
            default_axis = _readaxes(self.signal.axes)[axis]
        else:
            axes = self.group.nxaxes
            if axes is not None:
                default_axis = self.group.nxaxes[axis].nxname
            else:
                default_axis = None
        if default_axis:
            idx =  box.findText(default_axis)
            if idx >= 0:
                box.setCurrentIndex(idx)
            else:
                box.setCurrentIndex(box.findText('NXfield index'))
        else:
            box.setCurrentIndex(box.findText('NXfield index'))
        return box

    def remove_axis(self, axis):
        row = axis + 1
        for column in range(2):
            item = self.grid.itemAtPosition(row, column)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(False)
                    self.grid.removeWidget(widget)
                    widget.deleteLater()           

    def check_axis(self, node, axis):
        if isinstance(node, NXgroup):
            return False
        if len(node.shape) > 1:
            return False
        try:
            node_len, axis_len = self.signal.shape[axis], node.shape[0]
            if axis_len == node_len or axis_len == node_len+1:
                return True
        except Exception:
            pass
        return False

    def get_axis(self, axis):
        axis_name = self.axis_boxes[axis].currentText()
        if axis_name == 'NXfield index':
            return NXfield(range(self.signal.shape[axis]), 
                           name='index_%s' % axis)
        else:
            return self.group[axis_name]

    def get_axes(self):
        return [self.get_axis(axis) for axis in range(self.dims)]

    def accept(self):
        data = NXdata(self.signal, self.get_axes())
        data.plot()
        super(PlotDialog, self).accept()

    
class LimitDialog(BaseDialog):
    """Dialog to set plot window limits
    
    This is useful when it is desired to set the limits outside the data limits. 
    """
 
    def __init__(self, parent=None):

        super(LimitDialog, self).__init__(parent)
 
        from nexpy.gui.plotview import plotview

        self.plotview = plotview
        
        layout = QtGui.QVBoxLayout()

        xmin_layout = QtGui.QHBoxLayout()
        xmin_layout.addWidget(QtGui.QLabel('xmin'))
        self.xmin_box = self.textbox()
        self.xmin_box.setValue(plotview.xaxis.min)
        xmin_layout.addWidget(self.xmin_box)
        layout.addLayout(xmin_layout)

        xmax_layout = QtGui.QHBoxLayout()
        xmax_layout.addWidget(QtGui.QLabel('xmax'))
        self.xmax_box = self.textbox()
        self.xmax_box.setValue(plotview.xaxis.max)
        xmax_layout.addWidget(self.xmax_box)
        layout.addLayout(xmax_layout)

        ymin_layout = QtGui.QHBoxLayout()
        ymin_layout.addWidget(QtGui.QLabel('ymin'))
        self.ymin_box = self.textbox()
        self.ymin_box.setValue(plotview.yaxis.min)
        ymin_layout.addWidget(self.ymin_box)
        layout.addLayout(ymin_layout)

        ymax_layout = QtGui.QHBoxLayout()
        ymax_layout.addWidget(QtGui.QLabel('ymax'))
        self.ymax_box = self.textbox()
        self.ymax_box.setValue(plotview.yaxis.max)
        ymax_layout.addWidget(self.ymax_box)
        layout.addLayout(ymax_layout)

        if plotview.ndim > 1:
            vmin_layout = QtGui.QHBoxLayout()
            vmin_layout.addWidget(QtGui.QLabel('vmin'))
            self.vmin_box = self.textbox()
            self.vmin_box.setValue(plotview.vaxis.min)
            vmin_layout.addWidget(self.vmin_box)
            layout.addLayout(vmin_layout)

            vmax_layout = QtGui.QHBoxLayout()
            vmax_layout.addWidget(QtGui.QLabel('vmax'))
            self.vmax_box = self.textbox()
            self.vmax_box.setValue(plotview.vaxis.max)
            vmax_layout.addWidget(self.vmax_box)
            layout.addLayout(vmax_layout)

        layout.addWidget(self.buttonbox()) 
        self.setLayout(layout)

        self.setWindowTitle("Limit axes")

    def textbox(self):
        from nexpy.gui.plotview import NXTextBox
        textbox = NXTextBox()
        textbox.setAlignment(QtCore.Qt.AlignRight)
        textbox.setFixedWidth(75)
        return textbox

    def accept(self):
        xmin, xmax = self.xmin_box.value(), self.xmax_box.value() 
        ymin, ymax = self.ymin_box.value(), self.ymax_box.value()
        if self.plotview.ndim > 1:
            vmin, vmax = self.vmin_box.value(), self.vmax_box.value()
            self.plotview.autoscale = False
            self.plotview.set_plot_limits(xmin, xmax, ymin, ymax, vmin, vmax)
        else:
            self.plotview.set_plot_limits(xmin, xmax, ymin, ymax)
        super(LimitDialog, self).accept()

    
class AddDialog(BaseDialog):
    """Dialog to add a NeXus node"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16', 
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']
 
    def __init__(self, node, parent=None):

        super(AddDialog, self).__init__(parent)

        self.node = node

        class_layout = QtGui.QHBoxLayout()
        self.class_box = QtGui.QComboBox()
        if isinstance(self.node, NXgroup):
            names = ['NXgroup', 'NXfield']
        else:
            names = ['NXattr']
        for name in names:
            self.class_box.addItem(name)
        self.class_button = QtGui.QPushButton("Add")
        self.class_button.clicked.connect(self.select_class)
        class_layout.addWidget(self.class_box)
        class_layout.addWidget(self.class_button)
        class_layout.addStretch()       

        if isinstance(self.node, NXfield):
            self.setWindowTitle("Add NeXus Attribute")
        else:
            self.setWindowTitle("Add NeXus Data")

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(class_layout)
        self.layout.addWidget(self.buttonbox()) 
        self.setLayout(self.layout)

    def select_class(self):
        self.class_name = self.class_box.currentText()
        if self.class_name == "NXgroup":
            self.layout.insertLayout(1, self.define_grid("NXgroup"))
        elif self.class_name == "NXfield":
            self.layout.insertLayout(1, self.define_grid("NXfield"))
        else:
            self.layout.insertLayout(1, self.define_grid("NXattr"))
        self.class_button.setDisabled(True)
        self.class_box.setDisabled(True)

    def define_grid(self, class_name):
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)

        name_label = QtGui.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("Name:")
        self.name_box = QtGui.QLineEdit()
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        if class_name == "NXgroup":
            combo_label = QtGui.QLabel()
            combo_label.setAlignment(QtCore.Qt.AlignLeft)
            combo_label.setText("Group Class:")
            self.combo_box = QtGui.QComboBox()
            self.combo_box.currentIndexChanged.connect(self.select_combo)
            from nexpy.gui.consoleapp import _mainwindow
            standard_groups = sorted(list(set([g for g in 
                              _mainwindow.nxclasses[self.node.nxclass][2]])))
            for name in standard_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(_mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in _mainwindow.nxclasses if g not in
                                   standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(_mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            grid.addWidget(combo_label, 0, 0)
            grid.addWidget(self.combo_box, 0, 1)
            grid.addWidget(name_label, 1, 0)
            grid.addWidget(self.name_box, 1, 1)
        elif class_name == "NXfield":
            combo_label = QtGui.QLabel()
            combo_label.setAlignment(QtCore.Qt.AlignLeft)
            self.combo_box = QtGui.QComboBox()
            self.combo_box.currentIndexChanged.connect(self.select_combo)
            from nexpy.gui.consoleapp import _mainwindow
            fields = sorted(list(set([g for g in 
                            _mainwindow.nxclasses[self.node.nxclass][1]])))
            for name in fields:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(_mainwindow.nxclasses[self.node.nxclass][1][name][2], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            grid.addWidget(name_label, 0, 0)
            grid.addWidget(self.name_box, 0, 1)
            grid.addWidget(self.combo_box, 0, 2)
            value_label = QtGui.QLabel()
            value_label.setAlignment(QtCore.Qt.AlignLeft)
            value_label.setText("Value:")
            self.value_box = QtGui.QLineEdit()
            self.value_box.setAlignment(QtCore.Qt.AlignLeft)
            grid.addWidget(value_label, 1, 0)
            grid.addWidget(self.value_box, 1, 1)
            units_label = QtGui.QLabel()
            units_label.setAlignment(QtCore.Qt.AlignLeft)
            units_label.setText("Units:")
            self.units_box = QtGui.QLineEdit()
            self.units_box.setAlignment(QtCore.Qt.AlignLeft)
            grid.addWidget(units_label, 2, 0)
            grid.addWidget(self.units_box, 2, 1)
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
            grid.addWidget(type_label, 3, 0)
            grid.addWidget(self.type_box, 3, 1)
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

    def select_combo(self):
        self.set_name(self.combo_box.currentText())
    
    def get_name(self):
        return self.name_box.text()

    def set_name(self, name):
        if self.class_name == 'NXgroup':
            name = name[2:]
        self.name_box.setText(name)

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

    def get_units(self):
        return self.units_box.text()

    def get_type(self):
        if self.class_name == 'NXgroup':
            return self.combo_box.currentText()
        else:
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
            logging.info("'%s' added to '%s'" 
                         % (self.node[name], self.node.nxpath)) 
        elif name:
            value = self.get_value()
            dtype = self.get_type()
            if value is not None:
                if self.class_name == "NXfield":
                    self.node[name] = NXfield(value, dtype=dtype)
                    logging.info("'%s' added to '%s'" 
                                 % (name, self.node.nxpath)) 
                    units = self.get_units()
                    if units:
                        self.node[name].attrs['units'] = units
                else:
                    self.node.attrs[name] = NXattr(value, dtype=dtype)
                    logging.info("Attribute '%s' added to '%s'" 
                         % (name, self.node.nxpath)) 
        super(AddDialog, self).accept()

    
class InitializeDialog(BaseDialog):
    """Dialog to initialize a NeXus field node"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16', 
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']
 
    def __init__(self, node, parent=None):

        super(InitializeDialog, self).__init__(parent)
 
        self.node = node

        self.setWindowTitle("Initialize NeXus Data")

        grid = QtGui.QGridLayout()
        grid.setSpacing(10)

        name_label = QtGui.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("Name:")
        self.name_box = QtGui.QLineEdit()
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        self.combo_box = QtGui.QComboBox()
        self.combo_box.currentIndexChanged.connect(self.select_combo)
        from nexpy.gui.consoleapp import _mainwindow
        fields = sorted(list(set([g for g in 
                        _mainwindow.nxclasses[self.node.nxclass][1]])))
        for name in fields:
            self.combo_box.addItem(name)
            self.combo_box.setItemData(self.combo_box.count()-1, 
                wrap(_mainwindow.nxclasses[self.node.nxclass][1][name][2], 40),
                QtCore.Qt.ToolTipRole)
        self.combo_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        grid.addWidget(self.combo_box, 0, 2)
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

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(grid)
        self.layout.addWidget(self.buttonbox()) 
        self.setLayout(self.layout)

    def select_combo(self):
        self.set_name(self.combo_box.currentText())
    
    def get_name(self):
        return self.name_box.text()

    def set_name(self, name):
        self.name_box.setText(name)

    def get_type(self):
        dtype = self.type_box.currentText()
        return dtype 

    def get_shape(self):
        import ast
        try:
            shape = ast.literal_eval(self.shape_box.text())
            try:
                it = iter(shape)
                return shape
            except TypeError:
                if isinstance(shape, int):
                    return (shape,)
                else:
                    raise NeXusError('Invalid shape')
        except ValueError:
            raise NeXusError('Invalid shape')

    def accept(self):
        name = self.get_name()
        if name:
            dtype = self.get_type()
            if dtype is None:
                dtype = np.float64
            shape = self.get_shape()
            self.node[name] = NXfield(dtype=dtype, shape=shape)
            logging.info("'%s' initialized in '%s'" 
                         % (self.node[name], self.node.nxpath)) 
        super(InitializeDialog, self).accept()

    
class RenameDialog(BaseDialog):
    """Dialog to rename a NeXus node"""

    def __init__(self, node, parent=None):

        super(RenameDialog, self).__init__(parent)

        self.node = node

        self.setWindowTitle("Rename NeXus data")

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.define_grid())
        self.layout.addWidget(self.buttonbox()) 
        self.setLayout(self.layout)

    def define_grid(self):
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        name_label = QtGui.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("New Name:")
        self.name_box = QtGui.QLineEdit(self.node.nxname)
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        self.combo_box = None
        if isinstance(self.node, NXgroup) and self.node.nxclass != 'NXroot':
            combo_label = QtGui.QLabel()
            combo_label.setAlignment(QtCore.Qt.AlignLeft)
            combo_label.setText("New Class:")
            self.combo_box = QtGui.QComboBox()
            from nexpy.gui.consoleapp import _mainwindow
            parent_class = self.node.nxgroup.nxclass
            standard_groups = sorted(list(set([g for g in 
                          _mainwindow.nxclasses[parent_class][2]])))
            for name in standard_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(_mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in _mainwindow.nxclasses 
                                   if g not in standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(_mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            self.combo_box.addItem('NXgroup')
            self.combo_box.setCurrentIndex(self.combo_box.findText(self.node.nxclass))
            self.combo_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            grid.addWidget(combo_label, 1, 0)
            grid.addWidget(self.combo_box, 1, 1)
        else:
            parent_class = self.node.nxgroup.nxclass
            if parent_class != 'NXroot' and parent_class != 'NXtree':
                combo_label = QtGui.QLabel()
                combo_label.setAlignment(QtCore.Qt.AlignLeft)
                combo_label.setText("Valid Fields:")
                self.combo_box = QtGui.QComboBox()
                self.combo_box.currentIndexChanged.connect(self.set_name)
                from nexpy.gui.consoleapp import _mainwindow
                fields = sorted(list(set([g for g in 
                            _mainwindow.nxclasses[parent_class][1]])))
                for name in fields:
                    self.combo_box.addItem(name)
                    self.combo_box.setItemData(self.combo_box.count()-1, 
                        wrap(_mainwindow.nxclasses[parent_class][1][name][2], 40),
                        QtCore.Qt.ToolTipRole)
                if self.node.nxname in fields:
                    self.combo_box.setCurrentIndex(self.combo_box.findText(self.node.nxname))
                else:
                    self.name_box.setText(self.node.nxname)
                self.combo_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
                grid.addWidget(self.combo_box, 0, 2)
        grid.setColumnMinimumWidth(1, 200)
        return grid

    def get_name(self):
        return self.name_box.text()

    def set_name(self):
        self.name_box.setText(self.combo_box.currentText())

    def get_class(self):
        return self.combo_box.currentText()

    def accept(self):
        name = self.get_name()
        if name:
            self.node.rename(name)
        if isinstance(self.node, NXgroup):
            if self.combo_box:
                self.node.nxclass = self.get_class()
        super(RenameDialog, self).accept()

    
class RemoveDialog(BaseDialog):
    """Dialog to remove a NeXus node from the tree"""
 
    def __init__(self, node, parent=None):

        super(RemoveDialog, self).__init__(parent)
 
        self.node = node
 
        layout = QtGui.QVBoxLayout()
        layout.addWidget(QtGui.QLabel('Are you sure you want to remove "%s"?' 
                                      % node.nxname))
        layout.addWidget(self.buttonbox()) 
        self.setLayout(layout)

        self.setWindowTitle("Remove NeXus File")

    def accept(self):
        del self.node.nxgroup[self.node.nxname]
        super(RemoveDialog, self).accept()

    
class DeleteDialog(BaseDialog):
    """Dialog to delete a NeXus node"""
 
    def __init__(self, node, parent=None):

        super(DeleteDialog, self).__init__(parent)
 
        self.node = node
 
        layout = QtGui.QVBoxLayout()
        layout.addWidget(QtGui.QLabel('Are you sure you want to delete "%s"?' 
                                      % node.nxname))
        layout.addWidget(self.buttonbox()) 
        self.setLayout(layout)

        self.setWindowTitle("Delete NeXus Data")

    def accept(self):
        del self.node.nxgroup[self.node.nxname]
        super(DeleteDialog, self).accept()

    
class SignalDialog(BaseDialog):
    """Dialog to set the signal of NXdata"""
 
    def __init__(self, node, parent=None):

        super(SignalDialog, self).__init__(parent)
 
        if isinstance(node, NXfield):
            self.group = node.nxgroup
            signal_name = node.nxname
        else:
            self.group = node
            if self.group.nxsignal:
                signal_name = self.group.nxsignal.nxname
            else:
                signal_name = None

        self.signal_combo =  QtGui.QComboBox() 
        for node in self.group.values():
            if isinstance(node, NXfield) and node.shape != ():
                self.signal_combo.addItem(node.nxname)
        if self.signal_combo.count() == 0:
            raise NeXusError("No plottable field in group")
        self.signal_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        if signal_name:
            idx =  self.signal_combo.findText(signal_name)
            if idx >= 0:
                self.signal_combo.setCurrentIndex(idx)
            else:
                self.signal_combo.setCurrentIndex(0)
        else:
            self.signal_combo.setCurrentIndex(0)
        self.signal_combo.currentIndexChanged.connect(self.choose_signal)
        self.signal_box = QtGui.QLineEdit("1")

        self.grid = QtGui.QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(QtGui.QLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.grid.addWidget(QtGui.QLabel('Signal Attribute:'), 1, 0)
        self.grid.addWidget(self.signal_box, 1, 1)
        self.choose_signal()

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.grid)
        self.layout.addWidget(self.buttonbox())
        self.setLayout(self.layout)

        self.setWindowTitle("Set signal for %s" % self.group.nxname)

    @property
    def signal(self):
        return self.group[self.signal_combo.currentText()]

    @property
    def dims(self):
        return len(self.signal.shape)

    def choose_signal(self):
        row = 1
        self.axis_boxes = {}
        for axis in range(self.dims):
            self.axis_boxes[axis] = self.axis_box(axis)
            if self.axis_boxes[axis] is not None:
                row += 1
                self.grid.addWidget(QtGui.QLabel("Axis %s: " % axis), row, 0)
                self.grid.addWidget(self.axis_boxes[axis], row, 1)
        while row < self.grid.rowCount() - 1:
            self.remove_axis(row)
            row += 1   

    def axis_box(self, axis=0):
        box = QtGui.QComboBox()
        for node in self.group.values():
            if node is not self.signal and self.check_axis(node, axis):
                box.addItem(node.nxname)
        if box.count() == 0:
            return None
        if 'axes' in self.signal.attrs:
            from nexpy.api.nexus.tree import _readaxes
            default_axis = _readaxes(self.signal.axes)[axis]
        else:
            axes = self.group.nxaxes
            if axes is not None:
                default_axis = self.group.nxaxes[axis].nxname
            else:
                default_axis = None
        if default_axis:
            try:
                box.setCurrentIndex(box.findText(default_axis))
            except Exception:
                pass
        else:
            box.setCurrentIndex(0)
        return box

    def remove_axis(self, axis):
        row = axis + 1
        for column in range(2):
            item = self.grid.itemAtPosition(row, column)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(False)
                    self.grid.removeWidget(widget)
                    widget.deleteLater()           

    def check_axis(self, node, axis):
        if len(node.shape) > 1:
            return False
        try:
            node_len, axis_len = self.signal.shape[axis], node.shape[0]
            if axis_len == node_len or axis_len == node_len+1:
                return True
        except Exception:
            pass
        return False

    def get_axis(self, axis):
        try:
            return self.group[self.axis_boxes[axis].currentText()]
        except Exception:
            return None

    def get_axes(self):
        return [self.get_axis(axis) for axis in range(self.dims)]

    def accept(self):
        signal = int(self.signal_box.text())
        try:
            axes = self.get_axes()
            if None in axes:
                raise NeXusError("Unable to set axes")
            if len(set(axes)) < len(axes):
                raise NeXusError("Cannot have duplicate axes")
            if signal == 1:
                self.group.nxsignal = self.signal
                self.group.nxaxes = axes
            else:
                self.signal.attrs["signal"] = signal
                self.signal.attrs["axes"] = ":".join([axis.nxname for axis in axes])
            super(SignalDialog, self).accept()
        except NeXusError as error:
            from nexpy.gui.mainwindow import report_error 
            report_error("Setting signal", error)

    
class FitDialog(BaseDialog):
    """Dialog to fit one-dimensional NeXus data"""
 
    def __init__(self, entry, parent=None):

        super(FitDialog, self).__init__(parent)
        self.setMinimumWidth(850)        
 
        self.data = self.initialize_data(entry.data)

        from nexpy.gui.consoleapp import _tree
        self.tree = _tree

        from nexpy.gui.plotview import plotview
        self.plotview = plotview
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

        self.parameter_layout = self.initialize_parameter_grid()

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
        if self.data.nxerrors:
            self.fit_checkbox = QtGui.QCheckBox('Use Errors')
            self.fit_checkbox.setCheckState(QtCore.Qt.Checked)
        else:
            self.fit_checkbox = QtGui.QCheckBox('Use Poisson Errors')
            self.fit_checkbox.setCheckState(QtCore.Qt.Unchecked)
            self.fit_checkbox.stateChanged.connect(self.define_errors)
        self.report_button = QtGui.QPushButton("Show Fit Report")
        self.report_button.clicked.connect(self.report_fit)
        self.save_button = QtGui.QPushButton("Save Parameters")
        self.save_button.clicked.connect(self.save_fit)
        self.restore_button = QtGui.QPushButton("Restore Parameters")
        self.restore_button.clicked.connect(self.restore_parameters)
        self.action_layout.addWidget(fit_button)
        self.action_layout.addWidget(self.fit_label)
        self.action_layout.addStretch()
        self.action_layout.addWidget(self.fit_checkbox)
        self.action_layout.addWidget(self.save_button)

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(function_layout)
        self.layout.addWidget(self.buttonbox())

        self.setLayout(self.layout)

        self.setWindowTitle("Fit NeXus Data")

        self.load_entry(entry)

    def initialize_data(self, data):
        if isinstance(data, NXdata):
            if len(data.nxsignal.shape) > 1:
                raise NeXusError("Fitting only possible on one-dimensional arrays")
            fit_data = NXdata(data.nxsignal, data.nxaxes, title=data.nxtitle)
            if data.nxerrors:
                fit_data.errors = data.nxerrors
            return fit_data
        else:
            raise NeXusError("Must be an NXdata group")

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
        grid_layout = QtGui.QVBoxLayout()
        scroll_area = QtGui.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QtGui.QWidget()

        self.parameter_grid = QtGui.QGridLayout()
        self.parameter_grid.setSpacing(10)
        headers = ['Function', 'Np', 'Name', 'Value', '', 'Min', 'Max', 'Fixed']
        width = [100, 50, 100, 100, 100, 100, 100, 50, 100]
        column = 0
        for header in headers:
            label = QtGui.QLabel()
            label.setFont(self.header_font)
            label.setAlignment(QtCore.Qt.AlignHCenter)
            label.setText(header)
            self.parameter_grid.addWidget(label, 0, column)
            self.parameter_grid.setColumnMinimumWidth(column, width[column])
            column += 1

        scroll_widget.setLayout(self.parameter_grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setMinimumHeight(200)
        
        grid_layout.addWidget(scroll_area)

        return grid_layout

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
 
    def index_parameters(self):
        np = 0
        for f in sorted(self.functions):
            for p in f.parameters:
                np += 1
                p.parameter_index = np
    
    def add_function_rows(self, f):
        self.add_parameter_rows(f)
        if self.first_time:
            self.layout.insertLayout(1, self.parameter_layout)
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
            for column in range(8):
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
#            p.bound_box = QtGui.QLineEdit()
            self.parameter_grid.addWidget(p.parameter_box, row, 1,
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(QtGui.QLabel(p.name), row, 2)
            self.parameter_grid.addWidget(p.value_box, row, 3)
            self.parameter_grid.addWidget(p.error_box, row, 4)
            self.parameter_grid.addWidget(p.min_box, row, 5)
            self.parameter_grid.addWidget(p.max_box, row, 6)
            self.parameter_grid.addWidget(p.fixed_box, row, 7,
                                          alignment=QtCore.Qt.AlignHCenter)
#            self.parameter_grid.addWidget(p.bound_box, row, 8)
            f.rows.append(row)
            row += 1
        self.parameter_grid.setRowStretch(self.parameter_grid.rowCount(),10)

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

    def define_errors(self):
        if self.fit_checkbox.isChecked():
            self.data.errors = np.sqrt(self.data.nxsignal)

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
        entry['data'] = self.data
        for f in self.functions:
            entry[f.name] = self.get_model(f)
            parameters = NXparameters()
            for p in f.parameters:
                parameters[p.name] = NXfield(p.value, error=p.stderr, 
                                             initial_value=p.init_value,
                                             min=str(p.min), max=str(p.max))
            entry[f.name].insert(parameters)
        if self.fit is not None:
            entry['title'] = 'Fit Results'
            entry['fit'] = self.get_model()
            fit = NXparameters()
            fit.nfev = self.fit.result.nfev
            fit.ier = self.fit.result.ier 
            fit.chisq = self.fit.result.chisqr
            fit.redchi = self.fit.result.redchi
            fit.message = self.fit.result.message
            fit.lmdif_message = self.fit.result.lmdif_message
            entry['statistics'] = fit
        else:
            entry['title'] = 'Fit Model'
            entry['model'] = self.get_model()
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
        super(FitDialog, self).accept()
        
    def reject(self):
        super(FitDialog, self).reject()

    def closeEvent(self, event):
        event.accept()


class LogDialog(BaseDialog):
    """Dialog to display a NeXpy log filt"""
 
    def __init__(self, parent=None):

        super(LogDialog, self).__init__(parent)
 
        from consoleapp import _nexpy_dir
        self.log_directory = _nexpy_dir

        self.ansi_re = re.compile('\x1b' + r'\[([\dA-Fa-f;]*?)m')
 
        layout = QtGui.QVBoxLayout()
        self.text_box = QtGui.QPlainTextEdit()
        self.text_box.setMinimumWidth(700)
        self.text_box.setMinimumHeight(600)
        layout.addWidget(self.text_box)
        footer_layout = QtGui.QHBoxLayout()
        self.file_combo = QtGui.QComboBox()
        for file_name in self.get_filesindirectory('nexpy', extension='.log*',
                                                   directory=self.log_directory):
            self.file_combo.addItem(file_name)
        self.file_combo.setCurrentIndex(self.file_combo.findText('nexpy.log'))
        self.file_combo.currentIndexChanged.connect(self.show_log)
        close_box = QtGui.QDialogButtonBox(QtGui.QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        footer_layout.addStretch()
        footer_layout.addWidget(self.file_combo)
        footer_layout.addWidget(close_box)
        layout.addLayout(footer_layout)
        self.setLayout(layout)

        self.show_log()

    @property
    def file_name(self):
        return os.path.join(self.log_directory, self.file_combo.currentText())

    def show_log(self):
        f = open(self.file_name, 'r')
        try:
            from ansi2html import Ansi2HTMLConverter
            conv = Ansi2HTMLConverter(dark_bg=False, inline=True)
            text = conv.convert(''.join(f.readlines()))
            self.text_box.appendHtml(text)
        except ImportError:
            self.text_box.setPlainText(self.ansi_re.sub('', f.read()))
        f.close()
        self.text_box.verticalScrollBar().setValue(
            self.text_box.verticalScrollBar().maximum())
        self.setWindowTitle("Log File: %s" % self.file_name)


class RemoteDialog(BaseDialog):
    """Dialog to open a remote file.
    """ 
    def __init__(self, parent=None):

        super(RemoteDialog, self).__init__(parent)
 
        from globusonline.catalog.client.examples.catalog_wrapper import CatalogWrapper
        token_file = os.path.join(os.path.expanduser('~'),'.nexpy',
                                  'globusonline', 'gotoken.txt')
        self.wrap = CatalogWrapper(token='file', token_file=token_file)
        _,self.catalogs = self.wrap.catalogClient.get_catalogs()
        catalog_layout = QtGui.QHBoxLayout()
        self.catalog_box = QtGui.QComboBox()
        for catalog in self.catalogs:
            try:
                self.catalog_box.addItem(catalog['config']['name'])
            except:
                pass
        self.catalog_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        catalog_button = QtGui.QPushButton("Choose Catalog")
        catalog_button.clicked.connect(self.get_catalog)
        catalog_layout.addWidget(self.catalog_box)
        catalog_layout.addStretch()
        catalog_layout.addWidget(catalog_button)
        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(catalog_layout)
        self.layout.addWidget(self.buttonbox(save=True))
        self.setLayout(self.layout)
        self.dataset_box = None
        self.member_box = None
        self.uri_box = None
  
        self.setWindowTitle("Open Remote File")

    def get_catalog(self):
        self.catalog_id = self.get_catalog_id(self.catalog_box.currentText())
        _,self.datasets = self.wrap.catalogClient.get_datasets(self.catalog_id)
        if self.dataset_box is None:
            dataset_layout = QtGui.QHBoxLayout()
            self.dataset_box = QtGui.QComboBox()
            self.dataset_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            dataset_button = QtGui.QPushButton("Choose Dataset")
            dataset_button.clicked.connect(self.get_dataset)
            dataset_layout.addWidget(self.dataset_box)
            dataset_layout.addStretch()
            dataset_layout.addWidget(dataset_button)
            self.layout.insertLayout(1, dataset_layout)       
        else:
            self.dataset_box.clear()
            self.member_box.clear()
        for dataset in self.datasets:
            try:
                self.dataset_box.addItem(dataset['name'])
            except:
                pass

    def get_catalog_id(self, name):
        for catalog in self.catalogs:
            if catalog['config']['name']==name:
                return catalog['id']
 
    def get_dataset(self):
        self.dataset_id = self.get_dataset_id(self.dataset_box.currentText())
        _,self.members = self.wrap.catalogClient.get_members(self.catalog_id,
                                                             self.dataset_id)
        if self.member_box is None:
            member_layout = QtGui.QHBoxLayout()
            self.member_box = QtGui.QComboBox()
            self.member_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            member_button = QtGui.QPushButton("Choose Member")
            member_button.clicked.connect(self.get_member)
            member_layout.addWidget(self.member_box)
            member_layout.addWidget(member_button)            
            self.layout.insertLayout(2, member_layout) 
        else:
            self.member_box.clear()           
        for member in self.members:
            try:
                self.member_box.addItem(member['data_uri'])
            except:
                pass

    def get_dataset_id(self, name):
        for dataset in self.datasets:
            if dataset['name']==name:
                return dataset['id']

    def get_member(self):
        self.member_uri = self.member_box.currentText()
        if self.uri_box is None:
            uri_layout = QtGui.QHBoxLayout()
            uri_label = QtGui.QLabel('URI')
            self.uri_box = QtGui.QLineEdit('PYRO:rosborn@localhost:8801')
            self.uri_box.setMinimumWidth(200)        
            uri_layout.addStretch()
            uri_layout.addWidget(uri_label)
            uri_layout.addWidget(self.uri_box)
            uri_layout.addStretch()
            self.layout.insertLayout(3, uri_layout)

    def accept(self):
        if self.uri_box is not None and len(self.member_uri) > 0:
            uri = self.uri_box.text()
            file_name = self.member_uri
            try:
                from nexpy.gui.consoleapp import _mainwindow, _shell
                from nexpyro.pyro.nxfileremote import nxloadremote
                name = _mainwindow.treeview.tree.get_name(file_name)
                _mainwindow.treeview.tree[name] = _shell[name] = nxloadremote(file_name, uri)
                logging.info("Remote NeXus file '%s' on '%s' opened  as workspace '%s'" 
                             % (file_name, uri, name))
                super(RemoteDialog, self).accept()
            except NeXusError:
                super(RemoteDialog, self).reject()
        else:        
            super(RemoteDialog, self).reject()

