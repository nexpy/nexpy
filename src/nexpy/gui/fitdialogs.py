#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2020, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import importlib
import os
import re
import sys
from collections import OrderedDict
from inspect import getmembers, isclass

import matplotlib as mpl
import numpy as np
import pkg_resources
from lmfit import Model, Parameter, Parameters, models
from nexusformat.nexus import (NeXusError, NXattr, NXdata, NXentry, NXfield,
                               NXgroup, NXnote, NXparameters, NXprocess,
                               NXroot, nxload)

from ..api.frills.fit import Fit, Function, Parameter
from .datadialogs import NXDialog
from .plotview import NXPlotView
from .pyqt import QtCore, QtGui, QtWidgets
from .utils import report_error
from .widgets import NXCheckBox, NXComboBox, NXLabel, NXLineEdit, NXPushButton


class FitDialog(NXDialog):
    """Dialog to fit one-dimensional NeXus data"""
 
    def __init__(self, entry):

        super(FitDialog, self).__init__()
        self.setMinimumWidth(850)        
 
        self._data = self.initialize_data(entry.data)

        if 'Fit' not in self.plotviews:
            self._fitview = NXPlotView('Fit')
        self.fitview.plot(self._data, fmt='o')

        for key in [key for key in mpl.rcParams if key.startswith('keymap')]:
            for shortcut in 'lr':
                if shortcut in mpl.rcParams[key]:
                    mpl.rcParams[key].remove(shortcut)
        self.fitview.canvas.mpl_connect('key_press_event', self.on_key_press)

        self.model = None
        self.models = OrderedDict()
        self.parameters = []

        self.first_time = True
        self.fitted = False
        self.fit = None

        self.initialize_models()
 
        self.modelcombo = NXComboBox(items=sorted(self.model_list))
        add_button = NXPushButton("Add Model", self.add_model)
        model_layout = self.make_layout(self.modelcombo, add_button, left=True)
        
        self.parameter_layout = self.initialize_parameter_grid()

        remove_button = NXPushButton("Remove Model", self.remove_model)
        self.removecombo = NXComboBox()
        self.remove_layout = self.make_layout(remove_button, self.removecombo,
                                              left=True)

        self.plot_layout = QtWidgets.QHBoxLayout()
        plot_data_button = NXPushButton('Plot Data', self.plot_data)
        self.plot_model_button = NXPushButton('Plot Model', self.plot_model)
        self.plot_model_button.setVisible(False)
        self.plotcombo = NXComboBox()
        self.plotcombo.setVisible(False)
        plot_label = NXLabel('X-axis:')
        self.plot_min = self.fitview.xaxis.min
        self.plot_max = self.fitview.xaxis.max 
        self.plot_minbox = NXLineEdit(str(self.plot_min), align='right')
        plot_tolabel = NXLabel(' to ')
        self.plot_maxbox = NXLineEdit(str(self.plot_max), align='right')
        self.plot_checkbox = NXCheckBox('Use Data Points')
        self.plot_checkbox.setVisible(False)
        self.plot_layout = self.make_layout(plot_data_button, 
                                            self.plot_model_button,
                                            self.plotcombo, 
                                            self.spacer(5),
                                            plot_label,
                                            self.plot_minbox,
                                            plot_tolabel,
                                            self.plot_maxbox,
                                            self.plot_checkbox, 
                                            left=True)

        self.action_layout = QtWidgets.QHBoxLayout()
        fit_button = NXPushButton('Fit', self.fit_data)
        self.fit_label = NXLabel()
        if self._data.nxerrors:
            self.fit_checkbox = NXCheckBox('Use Errors', checked=True)
        else:
            self.fit_checkbox = NXCheckBox('Use Poisson Errors', 
                                           self.define_errors)
        self.report_button = NXPushButton("Show Fit Report", self.report_fit)
        self.save_button = NXPushButton("Save Parameters", self.save_fit)
        self.restore_button = NXPushButton("Restore Parameters", 
                                           self.restore_parameters)
        self.action_layout = self.make_layout(fit_button, self.fit_label,
                                              'stretch', self.fit_checkbox,
                                              self.spacer(5), self.save_button)

        self.bottom_layout = QtWidgets.QHBoxLayout()
        reset_button = NXPushButton('Reset Limits', self.reset_limits)
        self.bottom_layout = self.make_layout(reset_button, 'stretch',
                                              self.close_buttons())

        self.layout = self.set_layout(self.spacer(5), model_layout,
                                      self.plot_layout, self.bottom_layout)

        self.set_title("Fit NeXus Data")

        self.load_entry(entry)

    @property
    def fitview(self):
        if 'Fit' not in self.plotviews:
            self._fitview = NXPlotView('Fit')
        return self.plotviews['Fit']

    def initialize_data(self, data):
        if isinstance(data, NXdata):
            if len(data.shape) > 1:
                raise NeXusError(
                    "Fitting only possible on one-dimensional arrays")
            signal, axes = data.nxsignal, data.nxaxes[0]
            if signal.shape[0] == axes.shape[0] - 1:
                axes = axes.centers()
            fit_data = NXdata(signal, axes, title=data.nxtitle)
            if data.nxerrors:
                fit_data.errors = data.nxerrors
            return fit_data
        else:
            raise NeXusError("Must be an NXdata group")

    def initialize_models(self):
        self.model_list = [m[0] for m in getmembers(models, isclass) 
                           if m[0].endswith('Model') and m[0] != 'Model']

#        filenames = set()
#        private_path = os.path.join(os.path.expanduser('~'), '.nexpy', 
#                                    'functions')
#        if os.path.isdir(private_path):
#            sys.path.append(private_path)
#            for file_ in os.listdir(private_path):
#                name, ext = os.path.splitext(file_)
#                if name != '__init__' and ext.startswith('.py'):
#                    filenames.add(name)
#        functions_path = pkg_resources.resource_filename('nexpy.api.frills', 
#                                                         'functions')
#        sys.path.append(functions_path)

#        for file_ in os.listdir(functions_path):
#            name, ext = os.path.splitext(file_)
#            if name != '__init__' and ext.startswith('.py'):
#                filenames.add(name)
#        for name in sorted(filenames):
#            try:
#                function_module = importlib.import_module(name)
#                if hasattr(function_module, 'function_name'):
#                    self.function_module[function_module.function_name] = \
#                        function_module
#            except ImportError:
#                pass
                

    def initialize_parameter_grid(self):
        grid_layout = QtWidgets.QVBoxLayout()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()

        self.parameter_grid = QtWidgets.QGridLayout()
        self.parameter_grid.setSpacing(5)
        headers = ['Model', 'Np', 'Name', 'Value', '', 'Min', 'Max', 'Fixed']
        width = [100, 50, 100, 100, 100, 100, 100, 50, 100]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.parameter_grid.addWidget(label, 0, column)
            self.parameter_grid.setColumnMinimumWidth(column, width[column])
            column += 1

        scroll_widget.setLayout(self.parameter_grid)
        scroll_area.setWidget(scroll_widget)
        scroll_area.setMinimumHeight(200)
        
        grid_layout.addWidget(scroll_area)

        return grid_layout

    @property
    def data(self):
        try:
            xmin, xmax = self.get_limits()
            axis = self._data.nxaxes[0]
            if xmin > axis.max() or xmax < axis.min():
                raise NeXusError('Invalid data range')
            else:
                return self._data[xmin:xmax]
        except NeXusError as error:
            report_error('Fitting data', error)

    @property
    def signal(self):
        return self.data.nxsignal.nxvalue

    @property
    def axis(self):
        return self.data.nxaxes[0].nxvalue

    def compressed_name(self, name):
        name = re.sub(r'([a-zA-Z]*) # (\d*) ', r'\1\2', name, count=1)
        return name.capitalize()

    def expanded_name(self, name):
        return re.sub(r'([a-zA-Z]*)(\d*)', r'\1 # \2 ', name, count=1).title()
    
    def parse_model_name(self, name):
        match = re.match(r'([a-zA-Z]*)(\d*)', name)
        return match.group(1), match.group(2)

    def load_entry(self, entry):
        if 'fit' in entry.entries:
            for group in entry.entries:
                name, n = self.parse_model_name(group)
                if name in self.model_list:
                    parameters = []
                    for p in module.parameters:
                        if p in entry[group].parameters.entries:
                            parameter = Parameter(p)
                            parameter.value = entry[group].parameters[p].nxvalue
                            parameter.min = float(
                                entry[group].parameters[p].attrs['min'])
                            parameter.max = float(
                                entry[group].parameters[p].attrs['max'])
                            if 'error' in entry[group].parameters[p].attrs:
                                error = entry[group].parameters[p].attrs[
                                            'error']
                                if error > 0:
                                    parameter.stderr = float(
                                        entry[group].parameters[p].attrs[
                                            'error'])
                                    parameter.vary = True
                                else:
                                    parameter.vary = False
                            parameters.append(parameter)
                    m = Model(group, module, parameters, int(n))
                    self.models.append(m)
            self.models = sorted(self.models)
            for m in self.models:
                self.add_model_rows(m)
            self.write_parameters()
               
    def add_model(self):
        model_class = self.modelcombo.currentText()
        model_index = len(self.models) + 1
        model_name = model_class.replace('Model', '') + str(model_index)
        model = getattr(models, model_class)(prefix=model_name)
        try:
            parameters = model.guess(self.signal, x=self.axis)
        except NotImplementedError:
            parameters = model.make_params()
        self.models[model_name] = {'model': model, 'parameters': parameters}
        self.index_parameters()
        self.add_model_rows(model_name)
        self.write_parameters()
        if self.model is None:
            self.model = model
        else:
            self.model = self.model + model
 
    def index_parameters(self):
        np = 0
        for m in sorted(self.models):
            parameters = self.models[m]['parameters']
            for p in parameters:
                np += 1
                parameters[p].parameter_index = np
    
    def add_model_rows(self, model):
        self.add_parameter_rows(model)
        if self.first_time:
            self.layout.insertLayout(1, self.parameter_layout)
            self.layout.insertLayout(2, self.remove_layout)
            self.layout.insertLayout(4, self.action_layout)
            self.plot_model_button.setVisible(True)
            self.plotcombo.addItem('All')
            self.plotcombo.insertSeparator(1)
            self.plotcombo.setVisible(True)
            self.plot_checkbox.setVisible(True)
        self.removecombo.addItem(self.expanded_name(model))
        self.plotcombo.addItem(self.expanded_name(model))
        self.first_time = False

    def remove_model(self):
        expanded_name = self.removecombo.currentText()
        name = self.compressed_name(expanded_name)
        model = [m for m in self.models if self.models[m]['model'].prefix==name]
        for row in m.rows:
            for column in range(8):
                item = self.parameter_grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)
                        self.parameter_grid.removeWidget(widget)
                        widget.deleteLater()           
        del self.models[name]
        self.plotcombo.removeItem(self.plotcombo.findText(expanded_name))
        self.removecombo.removeItem(self.removecombo.findText(expanded_name))
        del m
        nm = 0
        np = 0
        for m in sorted(self.models):
            nm += 1
            name = '%s%s' % (m.module.model_name, str(nm))
            self.rename_model(m.name, name)
            m.name = name
            m.label_box.setText(self.expanded_name(m.name))
            for p in f.parameters:
                np += 1
                p.parameter_index = np
                p.parameter_box.setText(str(p.parameter_index))     

    def rename_model(self, old_name, new_name):
        old_name, new_name = (self.expanded_name(old_name), 
                              self.expanded_name(new_name))
        plot_index = self.plotcombo.findText(old_name)
        self.plotcombo.setItemText(plot_index, new_name)
        remove_index = self.removecombo.findText(old_name)
        self.removecombo.setItemText(remove_index, new_name)
        
    def add_parameter_rows(self, model):      
        row = self.parameter_grid.rowCount()
        name = self.expanded_name(model)
        label_box = NXLabel(name)
        self.parameter_grid.addWidget(label_box, row, 0)
        for p in self.models[model]['parameters']:
            p.parameter_index = row
            p.parameter_box = NXLabel(p.parameter_index)
            p.value_box = NXLineEdit(right=True)
            p.error_box = NXLabel()
            p.min_box = NXLineEdit('-inf', align='right')
            p.max_box = NXLineEdit('inf', align='right')
            p.fixed_box = NXCheckBox()
            self.parameter_grid.addWidget(p.parameter_box, row, 1,
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(QtWidgets.QLabel(p.name), row, 2)
            self.parameter_grid.addWidget(p.value_box, row, 3)
            self.parameter_grid.addWidget(p.error_box, row, 4)
            self.parameter_grid.addWidget(p.min_box, row, 5)
            self.parameter_grid.addWidget(p.max_box, row, 6)
            self.parameter_grid.addWidget(p.fixed_box, row, 7,
                                          alignment=QtCore.Qt.AlignHCenter)
            row += 1
        self.parameter_grid.setRowStretch(self.parameter_grid.rowCount(),10)

    def read_parameters(self):
        def make_float(value):
            try:
                return float(value)
            except Exception:
                return None
        for m in self.models:
            for p in self.models[m]['parameters']:
                p.value = make_float(p.value_box.text())
                p.min = make_float(p.min_box.text())
                p.max = make_float(p.max_box.text())
                p.vary = not p.fixed_box.checkState()

    def write_parameters(self):
        def write_value(box, value, prefix=None):
            try:
                if prefix:
                    box.setText('%s %.6g' % (prefix, value))
                else:
                    box.setText('%.6g' % value)
            except TypeError:
                box.setText(' ')
        for m in self.models:
            for p in self.models[m]['parameters']:
                write_value(p.parameter_box, p.parameter_index)
                write_value(p.value_box, p.value)
                if p.vary:
                    write_value(p.error_box, p.stderr, prefix='+/-')
                write_value(p.min_box, p.min)
                write_value(p.max_box, p.max)
                if p.vary:
                    p.fixed_box.setCheckState(QtCore.Qt.Unchecked)
                else:
                    p.fixed_box.setCheckState(QtCore.Qt.Checked)

    def guess_parameters(self, new_model):
        model = self.models['model']
        y = self.signal
        for m in self.models:
            if m is new_model:
                m.guess_parameters(fit.x, y)
            y = y - m.module.values(fit.x, f.parameter_values)

    def get_model(self, f=None):
        self.read_parameters()
        fit = Fit(self.data, self.functions)
        if self.plot_checkbox.isChecked():
            x = fit.x
        else:
            xmin, xmax = self.get_limits()
            x = np.linspace(xmin, xmax, 1001)
        return NXdata(NXfield(fit.get_model(x, f), name='model'),
                      NXfield(x, name=fit.data.nxaxes[0].nxname), 
                      title='Fit Results')

    def get_limits(self):
        return float(self.plot_minbox.text()), float(self.plot_maxbox.text())

    def reset_limits(self):
        self.plot_minbox.setText(str(self.plot_min))
        self.plot_maxbox.setText(str(self.plot_max))

    def plot_data(self):
        self.fitview.plot(self.data, fmt='o')
        self.fitview.plots['0']['legend_label'] = 'Data'
        self.fitview.raise_()

    def plot_model(self):
        plot_function = self.plotcombo.currentText()
        if plot_function == 'All':
            if self.fitted:
                fmt = '-'
            else:
                fmt = '--'
            self.fitview.plot(self.get_model(), fmt=fmtz, over=True, color='C0')
            plot_key = str(len(self.fitview.plots)-1)
            if self.fitted:
                self.fitview.plots[plot_key]['legend_label'] = 'Fit'
            else:
                self.fitview.plots[plot_key]['legend_label'] = 'Model'
        else:
            name = self.compressed_name(plot_function)
            f = list(filter(lambda x: x.name == name, self.functions))[0]
            self.fitview.plot(self.get_model(f), fmt='--', over=True)
            plot_key = str(len(self.fitview.plots)-1)
            self.fitview.plots[plot_key]['legend_label'] = name
        self.fitview.raise_()

    def define_errors(self):
        if self.fit_checkbox.isChecked():
            self.data.errors = np.sqrt(self.data.nxsignal)

    def fit_data(self):
        self.read_parameters()
        if self.fit_checkbox.isChecked():
            use_errors = True
        else:
            use_errors = False
        try:
            self.fit = Fit(self.data, self.functions, use_errors)
            self.fit.fit_data()
        except Exception as error:
            report_error("Fitting Data", error)
        if self.fit.result.success:
            self.fit_label.setText('Fit Successful Chi^2 = %s' 
                                   % self.fit.result.redchi)
        else:
            self.fit_label.setText('Fit Failed Chi^2 = %s' 
                                   % self.fit.result.redchi)
        self.write_parameters()
        if not self.fitted:
            self.action_layout.addWidget(self.report_button)
            self.action_layout.addWidget(self.restore_button)
            self.save_button.setText('Save Fit')
        self.fitted = True

    def report_fit(self):
        message_box = QtWidgets.QMessageBox()
        message_box.setText("Fit Results")
        if self.fit.result.errorbars:
            errors = 'Uncertainties estimated'
        else:
            errors = 'Uncertainties not estimated'
        text = ('%s\n' % self.fit.result.message +
                'Chi^2 = %s\n' % self.fit.result.chisqr +
                'Reduced Chi^2 = %s\n' % self.fit.result.redchi +
                '%s\n' % errors +
                'No. of Function Evaluations = %s\n' % self.fit.result.nfev +
                'No. of Variables = %s\n' % self.fit.result.nvarys +
                'No. of Data Points = %s\n' % self.fit.result.ndata +
                'No. of Degrees of Freedom = %s\n' % self.fit.result.nfree +
                '%s' % self.fit.fit_report())
        message_box.setInformativeText(text)
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        spacer = QtWidgets.QSpacerItem(500, 0, 
                                   QtWidgets.QSizePolicy.Minimum, 
                                   QtWidgets.QSizePolicy.Expanding)
        layout = message_box.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        message_box.exec_()

    def save_fit(self):
        """Saves fit results to an NXentry"""
        self.read_parameters()
        group = NXprocess()
        group['data'] = self.data
        for f in self.functions:
            group[f.name] = self.get_model(f)
            parameters = NXparameters()
            for p in f.parameters:
                parameters[p.name] = NXfield(p.value, error=p.stderr, 
                                             initial_value=p.init_value,
                                             min=str(p.min), max=str(p.max))
            group[f.name].insert(parameters)
        if self.fit is not None:
            group['program'] = 'lmfit'
            group['version'] = lmfit.__version__
            group['title'] = 'Fit Results'
            group['fit'] = self.get_model()
            fit = NXparameters()
            fit.nfev = self.fit.result.nfev
            fit.chisq = self.fit.result.chisqr
            fit.redchi = self.fit.result.redchi
            fit.message = self.fit.result.message
            group['statistics'] = fit
            group.note = NXnote(self.fit.result.message,
                ('Chi^2 = %s\n' % self.fit.result.chisqr +
                 'Reduced Chi^2 = %s\n' % self.fit.result.redchi +

                 'No. of Function Evaluations = %s\n' % self.fit.result.nfev +
                 'No. of Variables = %s\n' % self.fit.result.nvarys +
                 'No. of Data Points = %s\n' % self.fit.result.ndata +
                 'No. of Degrees of Freedom = %s\n' % self.fit.result.nfree +
                 '%s' % self.fit.fit_report()))
        else:
            group['title'] = 'Fit Model'
            group['model'] = self.get_model()
        if 'w0' not in self.tree:
            self.tree['w0'] = nxload(self.mainwindow.scratch_file, 'rw')
        ind = []
        for key in self.tree['w0']:
            try:
                if key.startswith('f'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if not ind:
            ind = [0]
        name = 'f'+str(sorted(ind)[-1]+1)
        self.tree['w0'][name] = group

    def restore_parameters(self):
        for f in self.functions:
            for p in f.parameters:
                p.value = p.init_value
                p.stderr = None
        self.fit_label.setText(' ')
        self.write_parameters()

    def on_key_press(self, event):
        if event.inaxes:
            if event.key == 'l':
                self.plot_minbox.setText('%g' % event.xdata)
            elif event.key == 'r':
                self.plot_maxbox.setText('%g' % event.xdata)
   
    def accept(self):
        if 'Fit' in self.plotviews:
            self.fitview.close()
        super(FitDialog, self).accept()
        
    def reject(self):
        if 'Fit' in self.plotviews:
            self.fitview.close()
        super(FitDialog, self).reject()

    def closeEvent(self, event):
        if 'Fit' in self.plotviews:
            self.fitview.close()
        event.accept()
