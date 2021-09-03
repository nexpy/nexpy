#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
import importlib
import inspect
import os
import pkg_resources
import re
import sys
import types
from collections import OrderedDict
from copy import deepcopy

import numpy as np

from .pyqt import QtCore, QtGui, QtWidgets

import matplotlib as mpl
from lmfit import Model, Parameter, Parameters
from lmfit import __version__ as lmfit_version
from lmfit import models

from nexusformat.nexus import (NeXusError, NXattr, NXdata, NXentry, NXfield,
                               NXgroup, NXnote, NXparameters, NXprocess,
                               NXroot, nxload)

from .datadialogs import NXDialog, NXPanel, NXTab
from .plotview import NXPlotView
from .utils import format_float, get_color, report_error
from .widgets import (NXCheckBox, NXColorBox, NXComboBox, NXLabel, NXLineEdit,
                      NXMessageBox, NXPushButton, NXScrollArea)


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

    models_path = pkg_resources.resource_filename('nexpy.api.frills', 
                                                     'models')
    sys.path.append(models_path)
    for file_ in os.listdir(models_path):
        name, ext = os.path.splitext(file_)
        if name != '__init__' and ext.startswith('.py'):
            filenames.add(name)

    models = {}
    for name in sorted(filenames):
        try:
            module = importlib.import_module(name)
            models.update(dict((n.strip('Model'), m) 
                for n, m in inspect.getmembers(module, inspect.isclass) 
                if issubclass(m, Model) and n != 'Model'))
        except ImportError:
            pass
    from lmfit.models import lmfit_models
    models.update(lmfit_models)
    del models['Expression']
    del models['Gaussian-2D']

    return models

all_models = get_models()

def get_methods():
    methods = {'leastsq': 'Levenberg-Marquardt',
               'least_squares': 'Least-Squares minimization, '
                                'using Trust Region Reflective method',
               'differential_evolution': 'differential evolution',
               'nelder': 'Nelder-Mead',
               'lbfgsb':' L-BFGS-B',
               'powell': 'Powell',
               'cg': 'Conjugate-Gradient',
               'newton': 'Newton-CG',
               'cobyla': 'Cobyla',
               'bfgs': 'BFGS',
               'tnc': 'Truncated Newton',
               'trust-ncg': 'Newton-CG trust-region',
               'trust-exact': 'nearly exact trust-region',
               'trust-krylov': 'Newton GLTR trust-region',
               'trust-constr': 'trust-region for constrained optimization',
               'dogleg': 'Dog-leg trust-region',
               'slsqp': 'Sequential Linear Squares Programming'}
    return methods

all_methods = get_methods()


class NXModel(Model):

    valid_forms = ()

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


class FitDialog(NXPanel):

    def __init__(self, parent=None):
        super(FitDialog, self).__init__('Fit', title='Fit Panel', 
                                        apply=True, reset=True, parent=parent)
        self.setMinimumWidth(850)        
        self.tab_class = FitTab

    def activate(self, data, plotview=None, color='C0'):
        if plotview:
            label = plotview.label + ': ' + str(plotview.num) 
        else:
            label = data.nxroot.nxname + data.nxpath
        super(FitDialog, self).activate(label, data, plotview=plotview, 
                                        color=color)


class FitTab(NXTab):
    """Dialog to fit one-dimensional NeXus data"""
 
    def __init__(self, label, data, plotview=None, color='C0', parent=None):

        super(FitTab, self).__init__(label, parent=parent)
 
        if ((isinstance(data, NXentry) or isinstance(data, NXprocess))
             and 'data' in data):
            group = data
            self.initialize_data(group['data'])
        elif isinstance(data, NXdata):
            self.initialize_data(data)
            group = None
        else:
            raise NeXusError("Must be an NXdata group")

        self.plotview = plotview
        self.plot_nums = []

        self.model = None
        self.models = []
 
        self.first_time = True
        self.fitted = False
        self.fit = None

        self.initialize_models()
 
        add_button = NXPushButton("Add Model", self.add_model)
        self.modelcombo = NXComboBox(items=list(self.all_models), 
                                     slot=self.choose_model)
        if 'Gaussian' in self.modelcombo:
            self.modelcombo.select('Gaussian')
        try:
            from pylatexenc.latex2text import LatexNodes2Text
            text = LatexNodes2Text().latex_to_text
        except ImportError:
            text = str
        for i, m in enumerate(self.all_models):
            tooltip = self.all_models[m].__doc__
            if tooltip:
                tooltip = tooltip.replace('.. math::\n\n', '')
                tooltip = re.sub(r'\:[a-z]*\:', r'', tooltip)
                self.modelcombo.setItemData(i, text(tooltip), 
                                            QtCore.Qt.ToolTipRole)
        self.formcombo = NXComboBox()
        self.formcombo.setVisible(False)
        model_layout = self.make_layout(add_button, self.modelcombo, 
                                        self.formcombo, align='left')
        
        self.parameter_layout = self.initialize_parameter_grid()

        remove_button = NXPushButton("Remove Model", self.remove_model)
        self.removecombo = NXComboBox()
        self.restore_button = NXPushButton("Restore Parameters", 
                                           self.restore_parameters)
        self.restore_button.setVisible(False)
        self.remove_layout = self.make_layout(remove_button,
                                              self.removecombo,
                                              'stretch',
                                              self.restore_button,
                                              align='justified')

        if self.plotview is None:
            self.fitview.plot(self._data, fmt='o', color=color)
        self.data_num = self.fitview.num
        self.data_label = self.fitview.plots[self.fitview.num]['label']

        self.method_label = NXLabel('Method')
        self.method_label.setVisible(False)
        self.methodcombo = NXComboBox(items=list(all_methods))
        for i, m in enumerate(all_methods):
            tooltip = all_methods[m]
            if tooltip:
                self.methodcombo.setItemData(i, text(tooltip), 
                                             QtCore.Qt.ToolTipRole)
        self.methodcombo.sort()
        self.methodcombo.select('leastsq') 
        if self._data.nxerrors:
            self.fit_checkbox = NXCheckBox('Use Errors', checked=True)
        else:
            self.fit_checkbox = NXCheckBox('Use Poisson Errors',
                                           self.define_errors)
        self.mask_button = NXPushButton('Mask Data', self.mask_data)
        self.clear_mask_button = NXPushButton('Clear Mask', self.clear_mask)
        self.adjust_layout = self.make_layout(self.method_label,
                                              self.methodcombo,
                                              self.fit_checkbox,
                                              'stretch',
                                              self.mask_button,
                                              self.clear_mask_button,
                                              align='justified')
        self.clear_mask_button.setVisible(False)

        fit_button = NXPushButton('Fit', self.fit_data)
        self.fit_label = NXLabel(width=300)
        self.report_button = NXPushButton("Show Fit Report", self.report_fit)
        self.report_button.setVisible(False)
        self.save_button = NXPushButton("Save Parameters", self.save_fit)
        self.action_layout = self.make_layout(fit_button, 
                                              self.fit_label,
                                              'stretch',
                                              self.report_button,
                                              self.save_button,
                                              align='justified')

        plot_data_button = NXPushButton('Plot Data', self.plot_data)
        self.plot_model_button = NXPushButton('Plot Model', self.plot_model)
        self.plot_model_button.setVisible(False)
        self.plotcombo = NXComboBox()
        self.plotcombo.setVisible(False)
        self.plot_checkbox = NXCheckBox('Use Data Points')
        self.plot_checkbox.setVisible(False)
        self.color_box = NXColorBox(get_color(color), label='Plot Color',
                                    width=100)
        self.plot_layout = self.make_layout(plot_data_button, 
                                            self.plot_model_button,
                                            self.plotcombo, 
                                            self.plot_checkbox,
                                            'stretch',
                                            self.color_box,
                                            align='justified')

        self.set_layout(model_layout, self.plot_layout)
        self.layout.setSpacing(5)
        self.set_title("Fit NeXus Data")

        self.masks = []
        self.expression_dialog = None

        if group:
            self.load_group(group)

    def __repr__(self):
        return 'FitTab("%s")' % self.data_label

    @property
    def fitview(self):
        if self.plotview and self.plotview.label in self.plotviews:
            _fitview = self.plotview
        elif 'Fit' in self.plotviews:
            _fitview = self.plotviews['Fit']
        else:
            _fitview = NXPlotView('Fit')
        return _fitview

    def initialize_data(self, data):
        if isinstance(data, NXdata):
            if len(data.shape) > 1:
                raise NeXusError(
                    "Fitting only possible on one-dimensional arrays")
            self._data = NXdata()
            self._data['signal'] = data.nxsignal
            self._data.nxsignal = self._data['signal']
            if data.nxaxes[0].size == data.nxsignal.size + 1:
                self._data['axis'] = data.nxaxes[0].centers()
            elif data.nxaxes[0].size == data.nxsignal.size:
                self._data['axis'] = data.nxaxes[0]
            else:
                raise NeXusError("Data has invalid axes")
            self._data.nxaxes = [self._data['axis']]
            if data.nxerrors:
                self._data.nxerrors = data.nxerrors
                self.poisson_errors = False
            else:
                self.poisson_errors = True
            self._data['title'] = data.nxtitle
        else:
            raise NeXusError("Must be an NXdata group")

    def initialize_models(self):
        self.all_models = all_models
        self.all_models.update(all_functions)

    def initialize_parameter_grid(self):

        grid_layout = QtWidgets.QVBoxLayout()

        self.parameter_grid = QtWidgets.QGridLayout()
        self.parameter_grid.setSpacing(5)
        headers = ['Model', 'Name', 'Value', '', 'Min', 'Max', 'Fixed', '']
        width = [100, 100, 100, 100, 100, 100, 50, 50]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.parameter_grid.addWidget(label, 0, column)
            self.parameter_grid.setColumnMinimumWidth(column, width[column])
            column += 1

        scroll_widget = QtWidgets.QWidget()
        scroll_area = NXScrollArea(scroll_widget)
        scroll_layout = QtWidgets.QVBoxLayout()
        scroll_layout.addLayout(self.parameter_grid)
        scroll_layout.addStretch()
        scroll_widget.setLayout(scroll_layout)
        scroll_area.setMinimumHeight(200)
        scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                  QtWidgets.QSizePolicy.Expanding)
        
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
        signal = self.data['signal']
        if signal.mask:
            return signal.nxvalue.compressed().astype(np.float64)
        else:
            return signal.nxvalue.astype(np.float64)

    @property
    def axis(self):
        data = self.data
        signal = data['signal'].nxvalue
        axis = data['axis'].nxvalue.astype(np.float64)
        if isinstance(signal, np.ma.MaskedArray):
            return np.ma.masked_array(axis, mask=signal.mask).compressed()
        else:
            return axis

    @property
    def errors(self):
        data = self.data
        if data.nxerrors:
            errors = data.nxerrors.nxvalue.astype(np.float64)
            signal = data['signal'].nxvalue
            if isinstance(signal, np.ma.MaskedArray):
                return np.ma.masked_array(errors, mask=signal.mask).compressed()
            else:
                return errors
        else:
            return None

    @property
    def weights(self):
        if self.errors is not None and np.all(self.errors):
            return 1.0 / self.errors
        else:
            return None

    def define_errors(self):
        if self.poisson_errors:
            if self.fit_checkbox.isChecked():
                self._data.nxerrors = np.sqrt(np.where(self._data.nxsignal<1, 
                                                       1, self._data.nxsignal))
            else:
                del self._data[self._data.nxerrors.nxname]

    def mask_data(self):
        xlo, xhi = self.get_limits()
        axis = self._data['axis']
        self._data['signal'][(axis>=xlo) & (axis<=xhi)] = np.ma.masked
        self.clear_mask_button.setVisible(True)
        x, dx = xlo, xhi-xlo
        ylo, yhi = self.fitview.ytab.get_limits()
        y, dy = 100*(ylo-yhi), 200*(yhi-ylo) 
        self.masks.append(self.fitview.rectangle(x, y, dx, dy, 
                                                 facecolor=self.color, 
                                                 edgecolor='None', 
                                                 alpha=0.2))
        self.fitview.otab.zoom()

    def clear_mask(self):
        self._data['signal'].mask = np.ma.nomask
        self.remove_masks()

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

    @property
    def method(self):
        return self.methodcombo.selected

    @property
    def color(self):
        return self.color_box.textbox.text()

    def compressed_name(self, name):
        return re.sub(r'([a-zA-Z_ ]*) [#] (\d*) $', r'\1_\2_', 
                      name, count=1).replace(' ', '_')

    def expanded_name(self, name):
        return re.sub(r'([a-zA-Z_]*)_(\d*)_$', r'\1 # \2 ', 
                      name, count=1).replace('_', ' ')

    def parse_model_name(self, name):
        match = re.match(r'([a-zA-Z0-9_-]*)_(\d*)$', name)
        if match:
            return match.group(1).replace('_', ' '), match.group(2)
        try:
            match = re.match(r'([a-zA-Z]*)(\d*)', name)
            return match.group(1), match.group(2)
        except Exception as error:
            return None, None

    def load_group(self, group):
        self.model = None
        self.models = []
        if 'fit' in group.entries or 'model' in group.entries:
            for model_name in group.entries:
                if ('parameters' in group[model_name] and 
                    'model' in group[model_name]['parameters'].attrs):
                    model_class = group[model_name]['parameters'].attrs['model']
                else:
                    model_class, model_index = self.parse_model_name(model_name)
                    if (model_class and model_class not in self.all_models and 
                        model_class+'Model' in self.all_models):
                        model_class = model_class + 'Model'          
                if model_class in self.all_models:
                    model = self.get_model_instance(model_class, model_name)
                    parameters = model.make_params()
                    saved_parameters = group[model_name]['parameters']
                    for mp in parameters:
                        p = mp.replace(model_name, '')
                        p = self.convert_parameter_name(p, saved_parameters)
                        if p in saved_parameters:
                            parameter = parameters[mp]
                            parameter.value = saved_parameters[p].nxvalue
                            parameter.min = float(
                                saved_parameters[p].attrs['min'])
                            parameter.max = float(
                                saved_parameters[p].attrs['max'])
                            if parameter.expr:
                                parameter.vary = False
                            elif 'error' in saved_parameters[p].attrs:
                                error = saved_parameters[p].attrs['error']
                                if error:
                                    parameter.stderr = float(
                                        saved_parameters[p].attrs['error'])
                                    parameter.vary = True
                                else:
                                    parameter.vary = False
                    self.models.append({'name': model_name,
                                        'class': model_class,
                                        'model': model, 
                                        'parameters': parameters})
            def idx(model):
                return int(re.match('.*?([0-9]+)$', model['name']).group(1))
            self.models = sorted(self.models, key=idx)
            for model_index, model in enumerate(self.models):
                if model_index == 0:
                    self.model = model['model']
                else:
                    self.model += model['model']
                self.add_model_parameters(model_index)
            self.write_parameters()

    def convert_parameter_name(self, parameter, saved_parameters):
        if parameter in saved_parameters:
            return parameter
        elif parameter.capitalize() in saved_parameters:
            return parameter.capitalize()
        elif parameter == 'amplitude' and 'Integral' in saved_parameters:
            return 'Integral'
        elif parameter == 'sigma' and 'Gamma' in saved_parameters:
            return 'Gamma'
        elif parameter == 'intercept' and 'Constant' in saved_parameters:
            return 'Constant'
        else:
            return ''

    def get_model_instance(self, model_class, prefix=None):
        if isinstance(self.all_models[model_class], types.ModuleType):
            return NXModel(self.all_models[model_class], prefix=prefix)
        elif self.all_models[model_class].valid_forms:
            return self.all_models[model_class](prefix=prefix,
                                                form=self.formcombo.selected)
        else:
            return self.all_models[model_class](prefix=prefix)

    def choose_model(self):
        model_class = self.modelcombo.selected
        try:
            if self.all_models[model_class].valid_forms:
                self.formcombo.setVisible(True)
                self.formcombo.clear()
                self.formcombo.add(*self.all_models[model_class].valid_forms)
            else:
                self.formcombo.setVisible(False)
        except AttributeError:
            self.formcombo.setVisible(False)
               
    def add_model(self):
        model_class = self.modelcombo.selected
        model_index = len(self.models)
        model_name = (model_class.replace('Model', '').replace(' ', '_') 
                      + '_' + str(model_index+1) + '_')
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
        self.method_label.setVisible(True)
        self.methodcombo.setVisible(True)
 
    def add_model_parameters(self, model_index):
        self.add_model_rows(model_index)
        if self.first_time:
            self.layout.insertLayout(1, self.parameter_layout)
            self.layout.insertLayout(2, self.remove_layout)
            self.layout.insertLayout(3, self.adjust_layout)
            self.layout.insertLayout(4, self.action_layout)
            self.plot_model_button.setVisible(True)
            self.plotcombo.add('All')
            self.plotcombo.insertSeparator(1)
            self.plotcombo.setVisible(True)
            self.plot_checkbox.setVisible(True)
        model_name = self.models[model_index]['name']
        self.removecombo.add(self.expanded_name(model_name))
        self.removecombo.select(self.expanded_name(model_name))
        self.plotcombo.add(self.expanded_name(model_name))
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
            p.box['value'] = NXLineEdit(align='right', 
                                        slot=self.read_parameters)
            p.box['error'] = NXLabel()
            p.box['min'] = NXLineEdit('-inf', align='right')
            p.box['max'] = NXLineEdit('inf', align='right')
            p.box['fixed'] = NXCheckBox()
            p.box['expr'] = NXPushButton('Σ', self.edit_expression,
                                         checkable=True, width=50)
            self.parameter_grid.addWidget(NXLabel(name), row, 1)
            self.parameter_grid.addWidget(p.box['value'], row, 2)
            self.parameter_grid.addWidget(p.box['error'], row, 3)
            self.parameter_grid.addWidget(p.box['min'], row, 4)
            self.parameter_grid.addWidget(p.box['max'], row, 5)
            self.parameter_grid.addWidget(p.box['fixed'], row, 6,
                                          alignment=QtCore.Qt.AlignHCenter)
            self.parameter_grid.addWidget(p.box['expr'], row, 7)
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
            for column in range(8):
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
            m['name'] = m['class'] + '_' + str(i+1) + '_'
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

    def edit_expression(self):
        if self.expression_dialog:
            try:
                self.expression_dialog.close()
            except Exception:
                pass
        for m in self.models:
            for parameter in m['parameters']:
                p = m['parameters'][parameter]
                if p.box['expr'].isChecked():
                    self.expression_dialog = ExpressionDialog(p, parent=self)
                    self.expression_dialog.show()
                    p.box['expr'].setChecked(False)

    def eval_expression(self, parameter):
        if parameter.expr:
            return parameter._expr_eval(parameter.expr)
        else:
            return parameter.value    
                    
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
        for m in self.models:
            for parameter in m['parameters']:
                p = m['parameters'][parameter]
                if p.expr:
                    p.value = self.eval_expression(p)
                    p.box['value'].setText(format_float(p.value))

    def write_parameters(self):
        def write_value(box, value, prefix=None):
            try:
                if prefix:
                    box.setText(prefix + ' ' + format_float(value))
                else:
                    box.setText(format_float(value))
            except TypeError:
                box.setText(' ')
        for m in self.models:
            for parameter in m['parameters']:
                p = m['parameters'][parameter]
                if p.expr:
                    write_value(p.box['value'], self.eval_expression(p))
                    p.box['fixed'].setCheckState(QtCore.Qt.Checked)
                    p.box['fixed'].setEnabled(False)
                else:
                    write_value(p.box['value'], p.value)
                if p.vary:
                    write_value(p.box['error'], p.stderr, prefix='+/-')
                    p.box['fixed'].setCheckState(QtCore.Qt.Unchecked)
                write_value(p.box['min'], p.min)
                write_value(p.box['max'], p.max)

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
        return self.fitview.xtab.get_limits()

    @property
    def plot_min(self):
        return self.get_limits()[0]

    @property
    def plot_max(self):
        return self.get_limits()[1]

    def plot_data(self):
        if self.plotview is None:
            if 'Fit' not in self.plotviews:
                self.fitview.plot(self._data, fmt='o', color=self.color)
            else:
                self.fitview.plot(self._data, 
                                  xmin=self.plot_min, xmax=self.plot_max,
                                  color=self.color)
            self.fitview.set_plot_limits(*self.get_limits())
            for label in ['label', 'legend_label']:
                self.fitview.plots[self.fitview.num][label] = self.data_label
            self.remove_plots()
        else:
            self.fitview.plots[self.data_num]['plot'].set_color(self.color)
            self.fitview.set_plot_limits(*self.get_limits())
            self.remove_plots()
        self.fitview.raise_()

    def plot_model(self):
        model_name = self.plotcombo.currentText()
        if max(self.fitview.plots) < 101:
            num = 101
        else:
            num = max([p for p in self.fitview.plots if p > 100]+[100]) + 1
        xmin, xmax = self.plot_min, self.plot_max
        if model_name == 'All':
            if self.fitted:
                fmt = '-'
            else:
                fmt = '--'
            self.fitview.plot(self.get_model(), fmt=fmt, 
                              xmin=self.plot_min, xmax=self.plot_max,
                              over=True, num=num, color=self.color)
            if self.fitted:
                self.fitview.plots[num]['legend_label'] = 'Fit'
            else:
                self.fitview.plots[num]['legend_label'] = 'Model'
        else:
            name = self.compressed_name(model_name)
            self.fitview.plot(self.get_model(name), fmt='--', 
                              xmin=self.plot_min, xmax=self.plot_max,
                              over=True, num=num)
            self.fitview.plots[num]['legend_label'] = name
        self.fitview.set_plot_limits(xmin=xmin, xmax=xmax)
        self.plot_nums.append(num)
        self.fitview.ytab.plotcombo.select(self.data_num)
        self.fitview.raise_()

    def fit_data(self):
        self.read_parameters()
        if self.fit_checkbox.isChecked():
            weights = self.weights
        else:
            weights = None
        try:
            self.fit_label.setText('Fitting...')
            self.fit = self.model.fit(self.signal, 
                                      params=self.parameters,
                                      weights=weights,
                                      x=self.axis,
                                      method=self.method,
                                      nan_policy='omit')
        except Exception as error:
            report_error("Fitting Data", error)
        if self.fit:
            if self.fit.success:
                self.fit_label.setText('Fit Successful Chi^2 = %s' 
                                       % format_float(self.fit.result.redchi))
            else:
                self.fit_label.setText('Fit Failed Chi^2 = %s' 
                                        % format_float(self.fit.result.redchi))
            self.parameters = self.fit.params
            if not self.fitted:
                self.report_button.setVisible(True)
                self.restore_button.setVisible(True)
                self.save_button.setText('Save Fit')
            self.fitted = True
        else:
            self.fit_label.setText('Fit failed')

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
        """Saves fit results to an NXprocess group"""
        self.read_parameters()
        group = NXprocess()
        group['data'] = self.data
        for m in self.models:
            group[m['name']] = self.get_model(m['name'])
            parameters = NXparameters(attrs={'model':m['class']})
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

    def remove_masks(self):
        for mask in self.masks:
            mask.remove()
        self.masks = []

    def remove_plots(self):
        for num in [n for n in self.plot_nums if n in self.fitview.plots]:
            self.fitview.plots[num]['plot'].remove()
            del self.fitview.plots[num]
            self.fitview.ytab.plotcombo.remove(num)
        self.plot_nums = []
        self.fitview.num = self.data_num
        self.fitview.ytab.plotcombo.select(self.data_num)
        self.fitview.draw()
        self.fitview.update_panels()
   
    def apply(self):
        self.remove_plots()
        self.fitview.plot(self.get_model(), fmt='-', color=self.color, 
                          over=True)
        
    def close(self):
        if self.plotview:
            self.remove_masks()
            self.remove_plots()

class ExpressionDialog(NXDialog):
    """Dialog to edit a fitting parameter expression."""

    def __init__(self, parameter, parent=None):

        super(ExpressionDialog, self).__init__(parent=parent)

        self.parameter = parameter
        self.parent = parent
        self.expression = NXLineEdit(parameter.expr)
        self.add_parameter_button = NXPushButton('Insert Parameter',
                                                 self.insert_parameter)
        self.parameter_combo = NXComboBox(items=self.parent.parameters)
        self.set_layout(self.expression,
                        self.make_layout(self.add_parameter_button,
                                         self.parameter_combo, 
                                         'stretch',
                                         self.close_buttons(save=True)))
        self.set_title(f"Editing '{parameter.name}' Expression")

    def insert_parameter(self):
        self.expression.insert(self.parameter_combo.selected)
        
    def accept(self):
        try:
            p = self.parent.parameters[self.parameter.name]
            p.expr = self.expression.text()
            if p.expr:
                p.value = p._expr_eval(p.expr)
                p.box['value'].setText(format_float(p.value))
                p.box['fixed'].setChecked(True)
                p.box['fixed'].setEnabled(False)
            else:
                p.box['fixed'].setChecked(False)
                p.box['fixed'].setEnabled(True)
            self.parent.read_parameters()
            super(ExpressionDialog, self).accept()    
        except NeXusError as error:
            report_error("Editing Expression", error)            

    def reject(self):
        super(ExpressionDialog, self).reject()    
