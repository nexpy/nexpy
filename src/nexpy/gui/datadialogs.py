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

from nexpy.gui.pyqt import QtGui, QtCore, getOpenFileName
import pkg_resources
import numpy as np
from scipy.optimize import minimize

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from nexusformat.nexus import (NeXusError, NXgroup, NXfield, NXattr,
                               NXroot, NXentry, NXdata, NXparameters)


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

    def set_layout(self, *items):
        self.layout = QtGui.QVBoxLayout()
        for item in items:
            if isinstance(item, QtGui.QLayout):
                self.layout.addLayout(item)
            elif isinstance(item, QtGui.QWidget):
                self.layout.addWidget(item)
        self.setLayout(self.layout)

    def set_title(self, title):
        self.setWindowTitle(title)

    def close_buttons(self, save=False):
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

    buttonbox = close_buttons #For backward compatibility

    def action_buttons(self, *items):
        layout = QtGui.QHBoxLayout()
        layout.addStretch()
        for label, action in items:
             button = QtGui.QPushButton(label)
             button.clicked.connect(action)
             layout.addWidget(button)
             layout.addStretch()
        return layout

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
 
    def directorybox(self, text="Choose Directory"):
        """
        Creates a text box and button for selecting a directory.
        """
        self.directorybutton =  QtGui.QPushButton(text)
        self.directorybutton.clicked.connect(self.choose_directory)
        self.directoryname = QtGui.QLineEdit(self)
        self.directoryname.setMinimumWidth(300)
        default = self.get_default_directory()
        if default:
            self.directoryname.setText(default)
        directorybox = QtGui.QHBoxLayout()
        directorybox.addWidget(self.directorybutton)
        directorybox.addWidget(self.directoryname)
        return directorybox

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.filename.text())
        filename = getOpenFileName(self, 'Open File', dirname)
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
        dirname = QtGui.QFileDialog.getExistingDirectory(self, 
                                                         'Choose Directory', 
                                                         dirname)
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

    def select_root(self, slot=None, text='Select Root :', other=False):
        layout = QtGui.QHBoxLayout()
        box = QtGui.QComboBox()
        box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        roots = []
        for root in self.treeview.tree.NXroot:
            roots.append(root.nxname)
        for root in sorted(roots):
            box.addItem(root)
        if not other:
            try:
                node = self.treeview.get_node()
                idx = box.findText(node.nxroot.nxname)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            except Exception:
                box.setCurrentIndex(0)
        if slot:
            box.currentIndexChanged.connect(slot)
        layout.addWidget(QtGui.QLabel(text))
        layout.addWidget(box)
        layout.addStretch()
        if not other:
            self.root_box = box
            self.root_layout = layout
        else:
            self.other_root_box = box
            self.other_root_layout = layout
        return layout

    @property
    def root(self):
        return self.treeview.tree[self.root_box.currentText()]

    @property
    def other_root(self):
        return self.treeview.tree[self.other_root_box.currentText()]

    def select_entry(self, slot=None, text='Select Entry :', other=False):
        layout = QtGui.QHBoxLayout()
        box = QtGui.QComboBox()
        box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        entries = []
        for root in self.treeview.tree.NXroot:
            for entry in root.NXentry:
                entries.append(root.nxname+'/'+entry.nxname)
        for entry in sorted(entries):
            box.addItem(entry)
        if not other:
            try:
                node = self.treeview.get_node()
                idx = box.findText(node.nxroot.nxname+'/'+node.nxentry.nxname)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            except Exception:
                box.setCurrentIndex(0)
        if slot:
            box.currentIndexChanged.connect(slot)
        layout.addWidget(QtGui.QLabel(text))
        layout.addWidget(box)
        layout.addStretch()
        if not other:
            self.entry_box = box
            self.entry_layout = layout
        else:
            self.other_entry_box = box
            self.other_entry_layout = layout
        return layout

    @property
    def entry(self):
        return self.treeview.tree[self.entry_box.currentText()]

    @property
    def other_entry(self):
        return self.treeview.tree[self.other_entry_box.currentText()]

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
        layout.addWidget(self.close_buttons(save))
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


class GridParameters(OrderedDict):
    """
    A dictionary of parameters to be entered in a dialog box grid.

    All keys must be strings, and valid Python symbol names, and all values
    must be of class GridParameter.
    """
    def __init__(self, *args, **kwds):
        super(GridParameters, self).__init__(self)
        self.update(*args, **kwds)

    def __setitem__(self, key, value):
        if value is not None and not isinstance(value, GridParameter):
            raise ValueError("'%s' is not a GridParameter" % value)
        OrderedDict.__setitem__(self, key, value)
        value.name = key

    def add(self, name, value=None, label=None, vary=None, slot=None,
            field=None):
        """
        Convenience function for adding a Parameter:

        Example
        -------
        p = Parameters()
        p.add(name, value=XX, ...)

        is equivalent to:
        p[name] = Parameter(name=name, value=XX, ....
        """
        self.__setitem__(name, GridParameter(value=value, name=name, label=label,
                                             vary=vary, slot=slot))

    def grid(self, header=True, title=None):
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        header_font = QtGui.QFont()
        header_font.setBold(True)
        row = 0
        if title:
            title_label = QtGui.QLabel(title)
            title_label.setFont(header_font)
            title_label.setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(title_label, row, 0, 1, 2)
            row += 1
        if header:
            parameter_label = QtGui.QLabel('Parameter')
            parameter_label.setFont(header_font)
            parameter_label.setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(parameter_label, 0, 0)
            value_label = QtGui.QLabel('Value')
            value_label.setFont(header_font)
            value_label.setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(value_label, row, 1)
            row += 1
        vary = False
        for p in self.values():
            label, value, checkbox = p.label, p.value, p.vary
            grid.addWidget(p.label, row, 0)
            grid.addWidget(p.box, row, 1, QtCore.Qt.AlignHCenter)
            if checkbox is not None:
                grid.addWidget(p.checkbox, row, 2, QtCore.Qt.AlignHCenter)
                vary = True
            row += 1
        if vary:
            fit_label = QtGui.QLabel('Fit?')
            fit_label.setFont(header_font)
            grid.addWidget(fit_label, 0, 2, QtCore.Qt.AlignHCenter)
        return grid

    def set_parameters(self):
        self.parameters = []
        for p in self.values():
            p.init_value = p.value
            if p.vary:
                self.parameters.append({p.name:p.value})

    def get_parameters(self, p):
        i = 0
        for key in [x.keys()[0] for x in self.parameters]:
            self[key].value = p[i]
            i += 1

    def refine_parameters(self, residuals, method='nelder-mead', **opts):
        self.set_parameters()
        p0 = np.array([p.values()[0] for p in self.parameters])
        result = minimize(residuals, p0, method='nelder-mead',
                          options={'xtol': 1e-6, 'disp': True})
        self.get_parameters(result.x)

    def restore_parameters(self):
        for p in self.values():
            p.value = p.init_value

    def save(self):
        for p in self.values():
            p.save()


class GridParameter(object):
    """
    A Parameter is an object to be set in a dialog box grid.
    """
    def __init__(self, name=None, value=None, label=None, vary=None, slot=None):
        """
        Parameters
        ----------
        name : str, optional
            Name of the parameter.
        value : float, optional
            Numerical Parameter value or NXfield containing the initial value
        label : str, optional
            Label used in the dialog box.
        vary : bool or None, optional
            Whether the Parameter is fixed during a fit. 
        slot : function or None, optional
            Function to be called when the parameter is changed. 
        """
        self.name = name
        self._value = value
        if isinstance(value, list) or isinstance(value, tuple):
            self.box = QtGui.QComboBox()
            self.box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
            for v in value:
                self.box.addItem(str(v))
            if slot is not None:
                self.box.currentIndexChanged.connect(slot)
        else:
            self.box = QtGui.QLineEdit()
            self.box.setAlignment(QtCore.Qt.AlignRight)
            if value is not None:
                if isinstance(value, NXfield):
                    if value.shape == ():
                        self.field = value
                        self.value = self.field.nxdata
                    else:
                        raise NeXusError('Cannot set a grid parameter to an array')
                else:
                    self.field = None
                    self.value = value
            if slot is not None:
                self.box.editingFinished.connect(slot)
        if vary is not None:
            self.checkbox = QtGui.QCheckBox()
            self.vary = vary
            self.init_value = self.value
        else:
            self.checkbox = self.vary = self.init_value = None
        self.label = QtGui.QLabel(label)

    def set(self, value=None, vary=None):
        """
        Set or update Parameter attributes.

        Parameters
        ----------
        value : float, optional
            Numerical Parameter value.
        vary : bool, optional
            Whether the Parameter is fixed during a fit.
        """
        if value is not None:
            self._val = value
        if vary is not None:
            self.vary = vary

    def __repr__(self):
        s = []
        if self.name is not None:
            s.append("'%s'" % self.name)
        sval = repr(self.value)
        s.append(sval)
        return "<GridParameter %s>" % ', '.join(s)

    def save(self):
        if isinstance(self.field, NXfield):
            self.field.nxdata = np.array(self.value).astype(self.field.dtype)

    @property
    def value(self):
        if isinstance(self.box, QtGui.QComboBox):
            return self.box.currentText()
        else:
            _value = self.box.text()
            try:
                return np.asscalar(np.array(_value).astype(self.field.dtype))
            except AttributeError:
                try:
                    return np.float32(_value)
                except ValueError:
                    return _value

    @value.setter
    def value(self, value):
        self._value = value
        if value is not None:
            if isinstance(self.box, QtGui.QComboBox):
                idx = self.box.findText(value)
                if idx >= 0:
                    self.box.setCurrentIndex(idx)
            else:
                if isinstance(value, NXfield):
                    value = value.nxdata
                if isinstance(value, basestring):
                    self.box.setText(value)
                else:
                    self.box.setText('%.6g' % value)

    @property
    def vary(self):
        if self.checkbox is not None:
            return self.checkbox.isChecked()
        else:
            return None

    @vary.setter
    def vary(self, value):
        if self.checkbox is not None:
            if value:
                self.checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.checkbox.setCheckState(QtCore.Qt.Unchecked)


class PlotDialog(BaseDialog):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""
 
    def __init__(self, node, parent=None, fmt='o'):

        super(PlotDialog, self).__init__(parent)
 
        if isinstance(node, NXfield):
            self.group = node.nxgroup
            signal_name = node.nxname
        else:
            self.group = node
            signal_name = None

        self.fmt = fmt

        self.signal_combo =  QtGui.QComboBox() 
        for node in self.group.values():
            if isinstance(node, NXfield) and node.is_plottable():
                self.signal_combo.addItem(node.nxname)
        if self.signal_combo.count() == 0:
            raise NeXusError("No plottable field in group")
        self.signal_combo.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        if signal_name:
            idx = self.signal_combo.findText(signal_name)
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
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

        self.setWindowTitle("Plot NeXus Data")

    @property
    def signal(self):
        return self.group[self.signal_combo.currentText()]

    @property
    def ndim(self):
        return self.signal.ndim

    def choose_signal(self):
        row = 0
        self.axis_boxes = {}
        for axis in range(self.ndim):
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
        if isinstance(node, NXgroup) or node.ndim > 1:
            return False
        axis_len = self.signal.shape[axis]
        if node.ndim == 0:
            node_len = 1
        else:
            node_len = node.shape[0]
        if node_len == axis_len or node_len == axis_len+1:
            return True
        else:
            return False

    def get_axis(self, axis):
        axis_name = self.axis_boxes[axis].currentText()
        if axis_name == 'NXfield index':
            return NXfield(range(self.signal.shape[axis]), 
                           name='index_%s' % axis)
        else:
            return self.group[axis_name]

    def get_axes(self):
        return [self.get_axis(axis) for axis in range(self.ndim)]

    def accept(self):
        data = NXdata(self.signal, self.get_axes(), title=self.signal.nxtitle)
        data.plot(fmt=self.fmt)
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

        layout.addWidget(self.close_buttons()) 
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
        self.layout.addWidget(self.close_buttons()) 
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
        self.layout.addWidget(self.close_buttons()) 
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
        self.layout.addWidget(self.close_buttons()) 
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
            if self.combo_box is not None:
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
        layout.addWidget(self.close_buttons()) 
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
        layout.addWidget(self.close_buttons()) 
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
            if self.group.nxsignal is not None:
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

        self.grid = QtGui.QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(QtGui.QLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.choose_signal()

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.grid)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

        self.setWindowTitle("Set signal for %s" % self.group.nxname)

    @property
    def signal(self):
        return self.group[self.signal_combo.currentText()]

    @property
    def ndim(self):
        return len(self.signal.shape)

    def choose_signal(self):
        row = 1
        self.axis_boxes = {}
        for axis in range(self.ndim):
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
            from nexusformat.nexus.tree import _readaxes
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
        return [self.get_axis(axis) for axis in range(self.ndim)]

    def accept(self):
        try:
            axes = self.get_axes()
            if None in axes:
                raise NeXusError("Unable to set axes")
            if len(set(axes)) < len(axes):
                raise NeXusError("Cannot have duplicate axes")
            self.group.nxsignal = self.signal
            self.group.nxaxes = axes
            super(SignalDialog, self).accept()
        except NeXusError as error:
            from nexpy.gui.mainwindow import report_error 
            report_error("Setting signal", error)

    
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


