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
import inspect
import os
import pkg_resources
import re
import sys
import types
from collections import OrderedDict

import matplotlib as mpl
import numpy as np
from lmfit import Model, Parameter, Parameters, models
from lmfit import __version__ as lmfit_version
from nexusformat.nexus import (NeXusError, NXattr, NXdata, NXentry, NXfield,
                               NXgroup, NXnote, NXparameters, NXprocess,
                               NXroot, nxload)

from .datadialogs import NXDialog
from .plotview import NXPlotView
from .pyqt import QtCore, QtGui, QtWidgets
from .utils import report_error, format_float
from .widgets import (NXCheckBox, NXComboBox, NXLabel, NXLineEdit, 
                      NXMessageBox, NXPushButton)


def get_functions():
    """Return a list of available functions and models."""

    filenames = set()
    private_path = os.path.join(os.path.expanduser('~'), '.nexpy', 'functions')
    if os.path.isdir(private_path):
        sys.path.append(private_path)
        for file_ in os.listdir(private_path):
            name, ext = os.path.splitext(file_)
            if name != '__init__' and ext.startswith('.py'):
                filenames.add(name)

    functions_path = pkg_resources.resource_filename('nexpy.api.frills', 
                                                     'functions')
    sys.path.append(functions_path)
    for file_ in os.listdir(functions_path):
        name, ext = os.path.splitext(file_)
        if name != '__init__' and ext.startswith('.py'):
            filenames.add(name)

    functions = {}
    for name in sorted(filenames):
        try:
            module = importlib.import_module(name)
            if hasattr(module, 'function_name'):
                functions[module.function_name] = module
        except ImportError:
            pass

    return functions

all_functions = get_functions()

def get_models():
    """Return a list of available models."""

    filenames = set()
    private_path = os.path.join(os.path.expanduser('~'), '.nexpy', 'models')
    if os.path.isdir(private_path):
        sys.path.append(private_path)
        for file_ in os.listdir(private_path):
            name, ext = os.path.splitext(file_)
            if name != '__init__' and ext.startswith('.py'):
                filenames.add(name)

    functions_path = pkg_resources.resource_filename('nexpy.api.frills', 
                                                     'models')
    sys.path.append(functions_path)
    for file_ in os.listdir(functions_path):
        name, ext = os.path.splitext(file_)
        if name != '__init__' and ext.startswith('.py'):
            filenames.add(name)

    models = {}
    for name in sorted(filenames):
        try:
            module = importlib.import_module(name)
            models.update(dict((n, m) 
                for n, m in inspect.getmembers(module, inspect.isclass) 
                if issubclass(m, Model)))
        except ImportError:
            pass
    from lmfit import models as lmfit_models
    models.update(dict((n, m) 
                  for n, m in inspect.getmembers(lmfit_models, inspect.isclass) 
                  if issubclass(m, Model) and n != 'Model'))

    for model in ['DonaichModel', 'ExpressionModel']:
        if model in models:
            del models[model]

    return models

all_models = get_models()


class NXModel(Model):

    def __init__(self, module, **kwargs):
        self.module = module
        super(NXModel, self).__init__(self.module.values,
                                      param_names=self.module.parameters,
                                      independent_vars=self._get_x(),
                                      **kwargs)

    def _parse_params(self):
        if self._prefix is None:
            self._prefix = ''
        self._param_names = ["%s%s" % (self._prefix, p) 
                             for p in self._param_root_names]
        self.def_vals = {}

    def _get_x(self):
        return [key for key in inspect.signature(self.module.values).parameters 
                if key != 'p']

    def make_funcargs(self, params=None, kwargs=None, strip=True):
        self._func_allargs = ['x'] + self._param_root_names
        out = super(NXModel, self).make_funcargs(params=params, kwargs=kwargs, 
                                                 strip=strip)
        function_out = {}
        function_out['p'] = [out[p] for p in out if p in self._param_root_names]
        for key in out:
            if key not in self._param_root_names:
                function_out[key] = out[key]
        return function_out            

    def guess(self, y, x=None, **kwargs):
        _guess = self.module.guess(x, y)
        pars = self.make_params()
        for i, p in enumerate(pars):
            pars[p].value = _guess[i]
        return pars


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
        self.models = []
 
        self.first_time = True
        self.fitted = False
        self.fit = None

        self.initialize_models()
 
        self.modelcombo = NXComboBox(items=list(self.all_models))
        add_button = NXPushButton("Add Model", self.add_model)
        model_layout = self.make_layout(self.modelcombo, add_button, 
                                        align='left')
        
        self.parameter_layout = self.initialize_parameter_grid()

        remove_button = NXPushButton("Remove Model", self.remove_model)
        self.removecombo = NXComboBox()
        self.remove_layout = self.make_layout(remove_button, self.removecombo,
                                              align='left')

        self.plot_layout = QtWidgets.QHBoxLayout()
        plot_data_button = NXPushButton('Plot Data', self.plot_data)
        self.plot_model_button = NXPushButton('Plot Model', self.plot_model)
        self.plot_model_button.setVisible(False)
        self.plotcombo = NXComboBox()
        self.plotcombo.setVisible(False)
        plot_label = NXLabel('X:')
        self.plot_min = self.fitview.xaxis.min
        self.plot_max = self.fitview.xaxis.max 
        self.plot_minbox = NXLineEdit(format_float(self.plot_min), 
                                      align='right', width=100)
        plot_tolabel = NXLabel(' to ')
        self.plot_maxbox = NXLineEdit(format_float(self.plot_max), 
                                      align='right', width=100)
        self.plot_checkbox = NXCheckBox('Use Data Points')
        self.plot_checkbox.setVisible(False)
        self.plot_layout = self.make_layout(plot_data_button, 
                                            self.plot_model_button,
                                            self.plotcombo, 
                                            self.plot_checkbox,
                                            'stretch',
                                            plot_label,
                                            self.plot_minbox,
                                            plot_tolabel,
                                            self.plot_maxbox,
                                            align='justified')

        fit_button = NXPushButton('Fit', self.fit_data)
        self.fit_label = NXLabel(width=300)
        if self._data.nxerrors:
            self.fit_checkbox = NXCheckBox('Use Errors', checked=True)
        else:
            self.fit_checkbox = NXCheckBox('Use Poisson Errors', 
                                           self.define_errors)
        self.report_button = NXPushButton("Show Fit Report", self.report_fit)
        self.report_button.setVisible(False)
        self.save_button = NXPushButton("Save Parameters", self.save_fit)
        self.restore_button = NXPushButton("Restore Parameters", 
                                           self.restore_parameters)
        self.restore_button.setVisible(False)
        reset_button = NXPushButton('Reset Limits', self.reset_limits)
        self.action_layout = self.make_layout(fit_button, 
                                              self.fit_checkbox,
                                              self.fit_label,
                                              'stretch',
                                              self.report_button,
                                              self.save_button,
                                              align='justified')

        self.bottom_layout = QtWidgets.QHBoxLayout()
        self.bottom_layout = self.make_layout(reset_button, 
                                              self.restore_button,
                                              'stretch',
                                              self.close_buttons(),
                                              align='justified')

        self.set_layout(model_layout, self.plot_layout, self.bottom_layout)
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
        self.all_models = all_functions
        self.all_models.update(all_models)

    def initialize_parameter_grid(self):
        grid_layout = QtWidgets.QVBoxLayout()
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QtWidgets.QWidget()

        self.parameter_grid = QtWidgets.QGridLayout()
        self.parameter_grid.setSpacing(5)
        headers = ['Model', 'Name', 'Value', '', 'Min', 'Max', 'Fixed']
        width = [100, 100, 100, 100, 100, 100, 50, 100]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.parameter_grid.addWidget(label, 0, column)
            self.parameter_grid.setColumnMinimumWidth(column, width[column])
            column += 1

        scroll_layout = QtWidgets.QVBoxLayout()
        scroll_layout.addLayout(self.parameter_grid)
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
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
        return self.data.nxsignal.nxvalue.astype(np.float64)

    @property
    def errors(self):
        if self.data.nxerrors:
            return self.data.nxerrors.nxvalue.astype(np.float64)
        else:
            return None

    @property
    def weights(self):
        if self.errors and np.all(self.errors):
            return 1.0 / self.errors
        else:
            return None

    @property
    def axis(self):
        return self.data.nxaxes[0].nxvalue.astype(np.float64)

    @property
    def parameters(self):
        _parameters = Parameters()
        for m in self.models:
            _parameters += m['parameters']
        return _parameters

    @parameters.setter
    def parameters(self, new_parameters):
        for m in self.models:
            for p in m['parameters']:
                if p in new_parameters:
                    m['parameters'][p].value = new_parameters[p].value
                    m['parameters'][p].min = new_parameters[p].min
                    m['parameters'][p].max = new_parameters[p].max
                    m['parameters'][p].vary = new_parameters[p].vary
                    m['parameters'][p].stderr = new_parameters[p].stderr
                    m['parameters'][p].correl = new_parameters[p].correl
        self.write_parameters()

    def compressed_name(self, name):
        return re.sub(r'([a-zA-Z]*) # (\d*) ', r'\1\2', name, count=1)

    def expanded_name(self, name):
        return re.sub(r'([a-zA-Z]*)(\d*)', r'\1 # \2 ', name, count=1)
    
    def parse_model_name(self, name):
        match = re.match(r'([a-zA-Z]*)(\d*)', name)
        return match.group(1), match.group(2)

    def load_entry(self, entry):
        if 'fit' in entry.entries:
            for group in entry.entries:
                name, n = self.parse_model_name(group)
                if name in list(self.all_models):
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
                self.add_model_parameters(m)
            self.write_parameters()

    def get_model_instance(self, model_class, prefix=None):
        if isinstance(self.all_models[model_class], types.ModuleType):
            return NXModel(self.all_models[model_class], prefix=prefix)
        else:
            if model_class == 'PolynomialModel':
                return self.all_models[model_class](7, prefix=prefix)
            else:
                return self.all_models[model_class](prefix=prefix)
               
    def add_model(self):
        model_class = self.modelcombo.currentText()
        model_index = len(self.models)
        model_name = model_class.replace('Model', '') + str(model_index+1)
        model = self.get_model_instance(model_class, prefix=model_name)
        try:
            if self.model:
                y = self.signal - self.model.eval(self.parameters, x=self.axis)
            else:
                y = self.signal
            parameters = model.guess(y, x=self.axis)
        except NotImplementedError:
            parameters = model.make_params()
        self.models.append({'name': model_name,
                            'class': model_class,
                            'model': model, 
                            'parameters': parameters})
        self.add_model_parameters(model_index)
        self.write_parameters()
        if self.model is None:
            self.model = model
        else:
            self.model = self.model + model
 
    def add_model_parameters(self, model_index):
        self.add_model_rows(model_index)
        if self.first_time:
            self.layout.insertLayout(1, self.parameter_layout)
            self.layout.insertLayout(2, self.remove_layout)
            self.layout.insertLayout(4, self.action_layout)
            self.plot_model_button.setVisible(True)
            self.plotcombo.addItem('All')
            self.plotcombo.insertSeparator(1)
            self.plotcombo.setVisible(True)
            self.plot_checkbox.setVisible(True)
        model_name = self.models[model_index]['name']
        self.removecombo.addItem(self.expanded_name(model_name))
        self.plotcombo.addItem(self.expanded_name(model_name))
        self.first_time = False

    def add_model_rows(self, model_index): 
        model = self.models[model_index]['model']     
        model_name = self.models[model_index]['name']
        parameters = self.models[model_index]['parameters']
        first_row = row = self.parameter_grid.rowCount()
        name = self.expanded_name(model_name)
        label_box = NXLabel(name)
        self.parameter_grid.addWidget(label_box, row, 0)
        for parameter in parameters:
            p = parameters[parameter]
            name = p.name.replace(model_name, '')
            if name == 'Fwhm':
                name = 'FWHM'
            p.box = {}
            p.box['value'] = NXLineEdit(align='right')
            p.box['error'] = NXLabel()
            p.box['min'] = NXLineEdit('-inf', align='right')
            p.box['max'] = NXLineEdit('inf', align='right')
            p.box['fixed'] = NXCheckBox()
            self.parameter_grid.addWidget(NXLabel(name), row, 1)
            self.parameter_grid.addWidget(p.box['value'], row, 2)
            self.parameter_grid.addWidget(p.box['error'], row, 3)
            self.parameter_grid.addWidget(p.box['min'], row, 4)
            self.parameter_grid.addWidget(p.box['max'], row, 5)
            self.parameter_grid.addWidget(p.box['fixed'], row, 6,
                                          alignment=QtCore.Qt.AlignHCenter)
            row += 1
        self.models[model_index]['row'] = first_row
        self.models[model_index]['label_box'] = label_box

    def remove_model(self):
        expanded_name = self.removecombo.currentText()
        model_name = self.compressed_name(expanded_name)
        model_index = [self.models.index(m) for m in self.models 
                       if m['name'] == model_name][0]
        parameters = self.models[model_index]['parameters']
        row = self.models[model_index]['row']
        for row in range(row, row+len(parameters)):
            for column in range(7):
                item = self.parameter_grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)
                        self.parameter_grid.removeWidget(widget)
                        widget.deleteLater()
        self.models.pop(model_index)
        self.plotcombo.removeItem(self.plotcombo.findText(expanded_name))
        self.removecombo.removeItem(self.removecombo.findText(expanded_name))
        self.model = None
        for i, m in enumerate(self.models):
            old_name = m['name']
            m['name'] = m['class'].replace('Model', '') + str(i+1)
            m['model'].prefix = m['name']
            m['parameters'] = self.rename_parameters(m, old_name)
            m['label_box'].setText(self.expanded_name(m['name']))
            idx = self.parameter_grid.indexOf(m['label_box'])
            m['row'] = self.parameter_grid.getItemPosition(idx)[0]
            if i == 0:
                self.model = m['model']
            else:
                self.model +=  m['model']
            self.rename_model(old_name, m['name'])

    def rename_parameters(self, model, old_name):
        for p in model['parameters']:
            model['parameters'][p].name = model['parameters'][p].name.replace(
                old_name, model['name'])
        _parameters = model['parameters'].copy()
        for p in _parameters:
            old_p = p.replace(model['name'], old_name)
            _parameters[p].box = model['parameters'][old_p].box
            _parameters[p].box['error'].setText('')
        return _parameters

    def rename_model(self, old_name, new_name):
        old_name, new_name = (self.expanded_name(old_name), 
                              self.expanded_name(new_name))
        plot_index = self.plotcombo.findText(old_name)
        self.plotcombo.setItemText(plot_index, new_name)
        remove_index = self.removecombo.findText(old_name)
        self.removecombo.setItemText(remove_index, new_name)
        
    def read_parameters(self):
        def make_float(value):
            try:
                return float(value)
            except Exception:
                return None
        for m in self.models:
            for parameter in m['parameters']:
                p = m['parameters'][parameter]
                p.value = make_float(p.box['value'].text())
                p.min = make_float(p.box['min'].text())
                p.max = make_float(p.box['max'].text())
                p.vary = not p.box['fixed'].checkState()

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
            for parameter in m['parameters']:
                p = m['parameters'][parameter]
                write_value(p.box['value'], p.value)
                if p.vary:
                    write_value(p.box['error'], p.stderr, prefix='+/-')
                write_value(p.box['min'], p.min)
                write_value(p.box['max'], p.max)
                if p.vary:
                    p.box['fixed'].setCheckState(QtCore.Qt.Unchecked)
                else:
                    p.box['fixed'].setCheckState(QtCore.Qt.Checked)
                    if p.expr:
                        p.box['fixed'].setEnabled(False)

    def get_model(self, name=None):
        if self.plot_checkbox.isChecked():
            x = self.axis
        else:
            xmin, xmax = self.get_limits()
            x = np.linspace(xmin, xmax, 1001)
        model_axis = NXfield(x, name=self.data.nxaxes[0].nxname)
        self.read_parameters()
        if name:
            ys = self.model.eval_components(params=self.parameters, x=x)
            model_data = NXfield(ys[name], name=name)
        else:
            y = self.model.eval(self.parameters, x=x)
            model_data = NXfield(y, name='Model')
        return NXdata(model_data, model_axis, title=self.data.nxtitle)

    def get_limits(self):
        return float(self.plot_minbox.text()), float(self.plot_maxbox.text())

    def reset_limits(self):
        self.plot_minbox.setText(format_float(self.plot_min))
        self.plot_maxbox.setText(format_float(self.plot_max))

    def plot_data(self):
        self.fitview.plot(self.data, fmt='o')
        self.fitview.plots['0']['legend_label'] = 'Data'
        self.fitview.raise_()

    def plot_model(self):
        model_name = self.plotcombo.currentText()
        if model_name == 'All':
            if self.fitted:
                fmt = '-'
            else:
                fmt = '--'
            self.fitview.plot(self.get_model(), fmt=fmt, over=True, color='C0')
            plot_key = str(len(self.fitview.plots)-1)
            if self.fitted:
                self.fitview.plots[plot_key]['legend_label'] = 'Fit'
            else:
                self.fitview.plots[plot_key]['legend_label'] = 'Model'
        else:
            name = self.compressed_name(model_name)
            self.fitview.plot(self.get_model(name), fmt='--', over=True)
            plot_key = str(len(self.fitview.plots)-1)
            self.fitview.plots[plot_key]['legend_label'] = name
        self.fitview.raise_()

    def define_errors(self):
        if self.fit_checkbox.isChecked():
            self.data.nxerrors = np.sqrt(self.data.nxsignal)

    def fit_data(self):
        self.read_parameters()
        if self.fit_checkbox.isChecked():
            weights = self.weights
        else:
            weights = None
        try:
            self.fit = self.model.fit(self.signal, 
                                      params=self.parameters,
                                      weights=weights,
                                      x=self.axis)
        except Exception as error:
            report_error("Fitting Data", error)
        if self.fit and self.fit.success:
            self.fit_label.setText('Fit Successful Chi^2 = %s' 
                                   % self.fit.result.redchi)
        else:
            self.fit_label.setText('Fit Failed Chi^2 = %s' 
                                   % self.fit.result.redchi)
        self.parameters = self.fit.params
        if not self.fitted:
            self.report_button.setVisible(True)
            self.restore_button.setVisible(True)
            self.save_button.setText('Save Fit')
        self.fitted = True

    def report_fit(self):
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
        message_box = NXMessageBox('Fit Results', text, parent=self)
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
        for m in self.models:
            group[m['name']] = self.get_model(m['name'])
            parameters = NXparameters()
            for n,p in m['parameters'].items():
                n = n.replace(m['name'], '')
                parameters[n] = NXfield(p.value, error=p.stderr, 
                                        initial_value=p.init_value,
                                        min=str(p.min), max=str(p.max))
            group[m['name']].insert(parameters)
        if self.fit is not None:
            group['program'] = 'lmfit'
            group['version'] = lmfit_version
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
        self.parameters = self.fit.init_params
        self.fit_label.setText(' ')

    def on_key_press(self, event):
        if event.inaxes:
            if event.key == 'l':
                self.plot_minbox.setText(format_float(event.xdata))
            elif event.key == 'r':
                self.plot_maxbox.setText(format_float(event.xdata))
   
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
