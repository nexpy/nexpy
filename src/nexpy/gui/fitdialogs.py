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
import re
import sys
import types
from itertools import cycle

import numpy as np
import pkg_resources
from lmfit import Model, Parameters
from lmfit import __version__ as lmfit_version
from nexusformat.nexus import (NeXusError, NXdata, NXentry, NXfield, NXnote,
                               NXparameters, NXprocess, nxload)

from .datadialogs import NXDialog, NXPanel, NXTab
from .plotview import NXPlotView, linestyles
from .pyqt import QtCore, QtWidgets
from .utils import display_message, format_float, report_error
from .widgets import (NXCheckBox, NXColorBox, NXComboBox, NXLabel, NXLineEdit,
                      NXMessageBox, NXPushButton, NXrectangle, NXScrollArea)


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

    from lmfit.models import lmfit_models
    models = lmfit_models
    del models['Expression']
    del models['Gaussian-2D']

    filenames = set()

    models_path = pkg_resources.resource_filename('nexpy.api.frills', 
                                                     'models')
    sys.path.append(models_path)
    for file_ in os.listdir(models_path):
        name, ext = os.path.splitext(file_)
        if name != '__init__' and ext.startswith('.py'):
            filenames.add(name)

    private_path = os.path.join(os.path.expanduser('~'), '.nexpy', 'models')
    if os.path.isdir(private_path):
        sys.path.append(private_path)
        for file_ in os.listdir(private_path):
            name, ext = os.path.splitext(file_)
            if name != '__init__' and ext.startswith('.py'):
                filenames.add(name)

    for name in sorted(filenames):
        try:
            module = importlib.import_module(name)
            models.update(dict((n.strip('Model'), m) 
                for n, m in inspect.getmembers(module, inspect.isclass) 
                if issubclass(m, Model) and n != 'Model'))
        except ImportError:
            pass

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
        super().__init__(self.module.values, 
                         param_names=self.module.parameters,
                         independent_vars=self._get_x(), **kwargs)

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
        out = super().make_funcargs(params=params, kwargs=kwargs, strip=strip)
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
        super().__init__('Fit', title='Fit Panel', apply=True, reset=True, 
                         parent=parent)
        self.setMinimumWidth(850)        
        self.tab_class = FitTab

    def activate(self, data, plotview=None, color='C0'):
        if plotview:
            label = plotview.label + ': ' + str(plotview.num) 
        else:
            label = data.nxroot.nxname + data.nxpath
        super().activate(label, data, plotview=plotview, color=color)


class FitTab(NXTab):
    """Dialog to fit one-dimensional NeXus data"""
 
    def __init__(self, label, data, plotview=None, color='C0', parent=None):

        super().__init__(label, parent=parent)
 
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
        self.model_combo = NXComboBox(items=list(self.all_models), 
                                      slot=self.choose_model)
        if 'Gaussian' in self.model_combo:
            self.model_combo.select('Gaussian')
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
                self.model_combo.setItemData(i, text(tooltip), 
                                             QtCore.Qt.ToolTipRole)
        self.form_combo = NXComboBox()
        self.compose_button = NXPushButton("Compose Models", self.compose_model)
        model_layout = self.make_layout(add_button, self.model_combo, 
                                        self.form_combo, 'stretch',
                                        self.compose_button, align='justified')
        
        self.parameter_layout = self.initialize_parameter_grid()

        self.remove_button = NXPushButton("Remove Model", self.remove_model)
        self.remove_combo = NXComboBox()
        self.restore_button = NXPushButton("Restore Parameters", 
                                           self.restore_parameters)
        self.save_parameters_button = NXPushButton("Save Parameters", 
                                                   self.save_parameters)
        self.remove_layout = self.make_layout(self.remove_button,
                                              self.remove_combo,
                                              'stretch',
                                              self.restore_button,
                                              self.save_parameters_button,
                                              align='justified')

        if self.plotview is None:
            self.fitview.plot(self._data, fmt='o', color=color)
        self.data_num = self.fitview.num
        self.data_label = self.fitview.plots[self.fitview.num]['label']
        self.cursor = self.fitview.plots[self.fitview.num]['cursor']
        if self.cursor:
            @self.cursor.connect("add")
            def add_selection(sel):
                self.mask_data()

        self.fit_button = NXPushButton('Fit', self.fit_data)
        self.fit_combo = NXComboBox(items=list(all_methods))
        for i, m in enumerate(all_methods):
            tooltip = all_methods[m]
            if tooltip:
                self.fit_combo.setItemData(i, text(tooltip), 
                                           QtCore.Qt.ToolTipRole)
        self.fit_combo.sort()
        self.fit_combo.select('leastsq') 
        if self._data.nxerrors:
            self.fit_checkbox = NXCheckBox('Use Errors', checked=True)
        else:
            self.fit_checkbox = NXCheckBox('Use Poisson Errors',
                                           self.define_errors)
        self.save_fit_button = NXPushButton("Save Fit", self.save_fit)
        self.adjust_layout = self.make_layout(self.fit_button,
                                              self.fit_combo,
                                              self.fit_checkbox,
                                              'stretch',
                                              self.save_fit_button,
                                              align='justified')

        self.fit_status = NXLabel(width=600)
        self.report_button = NXPushButton("Show Fit Report", self.report_fit)
        self.action_layout = self.make_layout(self.fit_status,
                                              'stretch',
                                              self.report_button,
                                              align='justified')

        plot_data_button = NXPushButton('Plot Data', self.plot_data)
        self.plot_model_button = NXPushButton('Plot Model', self.plot_model)
        self.plot_combo = NXComboBox()
        self.plot_checkbox = NXCheckBox('Use Data Points')
        self.mask_button = NXPushButton('Mask Data', self.mask_data)
        self.clear_mask_button = NXPushButton('Clear Masks', self.clear_masks)
        self.color_box = NXColorBox(color, label='Plot Color', width=100)
        self.plot_layout = self.make_layout(plot_data_button, 
                                            self.plot_model_button,
                                            self.plot_combo, 
                                            self.plot_checkbox,
                                            self.mask_button,
                                            self.clear_mask_button,
                                            'stretch',
                                            self.color_box,
                                            align='justified')
        self.clear_mask_button.setVisible(False)
        
        self.set_layout(model_layout, self.plot_layout)
        self.layout.setSpacing(5)
        self.set_title("Fit NeXus Data")
        self.choose_model()
        self.set_button_visibility()

        self.cid = self.fitview.canvas.mpl_connect('button_release_event', 
                                                   self.on_button_release)
        self.composite_model = ''
        self.composite_dialog = None
        self.plot_dialog = None
        self.expression_dialog = None
        self.rectangle = None
        self.mask_num = None
        self.linestyles = [linestyles[ls] for ls in linestyles 
                           if ls != 'Solid' and ls != 'None']
        self.linestyle = cycle(self.linestyles)
        self.xlo, self.xhi = self.fitview.ax.get_xlim()
        self.ylo, self.yhi = self.fitview.ax.get_ylim()

        if group:
            self.load_fit(group)

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

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_area = NXScrollArea(self.scroll_widget)
        self.scroll_layout = QtWidgets.QVBoxLayout()
        self.scroll_layout.addLayout(self.parameter_grid)
        self.scroll_layout.addStretch()
        self.scroll_widget.setLayout(self.scroll_layout)
        self.scroll_area.setMinimumHeight(200)
        self.scroll_area.setMinimumWidth(800)
        self.scroll_area.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                       QtWidgets.QSizePolicy.Expanding)
        
        grid_layout.addWidget(self.scroll_area)
        return grid_layout

    def set_button_visibility(self, fitted=False):
        if len(self.models) == 0:
            self.compose_button.setVisible(False)
            self.remove_button.setVisible(False)
            self.remove_combo.setVisible(False)
            self.restore_button.setVisible(False)
            self.save_parameters_button.setVisible(False)
            self.fit_button.setVisible(False)
            self.fit_combo.setVisible(False)
            self.fit_checkbox.setVisible(False)
            self.fit_status.setVisible(False)
            self.report_button.setVisible(False)
            self.save_fit_button.setVisible(False)
            self.plot_model_button.setVisible(False)
            self.plot_combo.setVisible(False)
            self.plot_checkbox.setVisible(False)
        else:
            if len(self.models) > 1:
                self.compose_button.setVisible(True)
            self.remove_button.setVisible(True)
            self.remove_combo.setVisible(True)
            self.save_parameters_button.setVisible(True)
            self.fit_button.setVisible(True)
            self.fit_combo.setVisible(True)
            self.fit_checkbox.setVisible(True)
            self.plot_model_button.setVisible(True)
            self.plot_combo.setVisible(True)
            self.plot_checkbox.setVisible(True)
            if fitted:
                self.restore_button.setVisible(True)
                self.fit_status.setVisible(True)
                self.report_button.setVisible(True)
                self.save_fit_button.setVisible(True)
            else:
                self.save_fit_button.setVisible(False)

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
            report_error("Fitting data", error)

    @property
    def signal(self):
        signal = self.data['signal']
        if signal.mask:
            return signal.nxdata.compressed().astype(np.float64)
        else:
            return signal.nxdata.astype(np.float64)

    @property
    def axis(self):
        data = self.data
        signal = data['signal'].nxdata
        axis = data['axis'].nxdata.astype(np.float64)
        if isinstance(signal, np.ma.MaskedArray):
            return np.ma.masked_array(axis, mask=signal.mask).compressed()
        else:
            return axis

    @property
    def errors(self):
        data = self.data
        if data.nxerrors:
            errors = data.nxerrors.nxdata.astype(np.float64)
            signal = data['signal'].nxdata
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

    def signal_mask(self):
        mask = self._data['signal'].mask
        if mask and mask.any():
            mask_data = NXfield(self._data['signal'].nxdata.data[mask==True], 
                                name='mask')
            mask_axis = NXfield(self._data['axis'].nxdata[mask==True], 
                                name='axis')
            return NXdata(mask_data, mask_axis)
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
        axis = self._data['axis']
        signal = self._data['signal']
        if self.cursor and self.cursor.selections:
            idx = self.cursor.selections[0].target.index
            if np.ma.is_masked(signal.nxvalue[idx]):
                signal[idx] = np.ma.nomask
            else:
                signal[idx] = np.ma.masked
            self.cursor.remove_selection(self.cursor.selections[0])
        elif self.rectangle:
            signal[(axis>=self.xlo) & (axis<=self.xhi)] = np.ma.masked
        else:
            display_message('Masking Data',
            "There are two methods to mask data:\n\n" +
            "1) Select data with a right-click zoom and click 'Mask Data'\n" +
            "2) Double-click points to be masked (needs 'mplcursor' package)", 
                width=350)
            return
        self.plot_mask()
        if np.ma.is_masked(signal.nxvalue):
            self.mask_button.setVisible(False)
            self.clear_mask_button.setVisible(True)
        else:
            self.mask_button.setVisible(True)
            self.clear_mask_button.setVisible(False)

    def clear_masks(self):
        self._data['signal'].mask = np.ma.nomask
        self.remove_masks()
        self.mask_button.setVisible(True)
        self.clear_mask_button.setVisible(False)

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
                    m['parameters'][p].expr = new_parameters[p].expr
                    m['parameters'][p].stderr = new_parameters[p].stderr
                    m['parameters'][p].correl = new_parameters[p].correl

    @property
    def method(self):
        return self.fit_combo.selected

    @property
    def color(self):
        return self.color_box.textbox.text()

    def compressed_name(self, name):
        return re.sub(r'([a-zA-Z_ ]*) [#] (\d*)$', r'\1_\2', 
                      name, count=1).replace(' ', '_')

    def expanded_name(self, name):
        return re.sub(r'([a-zA-Z_]*)_(\d*)$', r'\1 # \2', 
                      name, count=1).replace('_', ' ').strip()

    def parse_model_name(self, name):
        match = re.match(r'([a-zA-Z0-9_-]*)_(\d*)$', name)
        if match:
            return match.group(1).replace('_', ' '), match.group(2)
        try:
            match = re.match(r'([a-zA-Z]*)(\d*)', name)
            return match.group(1), match.group(2)
        except Exception as error:
            return None, None

    def load_fit(self, group):
        self.model = None
        self.models = []
        if 'fit' in group.entries or 'model' in group.entries:
            for name in group.entries:
                if ('parameters' in group[name] and 
                    'model' in group[name]['parameters'].attrs):
                    model_class = group[name]['parameters'].attrs['model']
                    model_name = name
                else:
                    model_class, model_index = self.parse_model_name(name)
                    model_name = model_class + '_' + model_index
                    if (model_class and model_class not in self.all_models and 
                        model_class+'Model' in self.all_models):
                        model_class = model_class + 'Model'          
                if model_class in self.all_models:
                    model = self.get_model_instance(model_class, model_name)
                    parameters = model.make_params()
                    saved_parameters = group[name]['parameters']
                    for mp in parameters:
                        p = mp.replace(model.prefix, '')
                        p = self.convert_parameter_name(p, saved_parameters)
                        if p in saved_parameters:
                            parameter = parameters[mp]
                            parameter.value = saved_parameters[p].nxvalue
                            parameter.min = float(
                                saved_parameters[p].attrs['min'])
                            parameter.max = float(
                                saved_parameters[p].attrs['max'])
                            if 'vary' in saved_parameters[p].attrs:
                                parameter.vary = saved_parameters[p].attrs['vary']
                            if 'expr' in saved_parameters[p].attrs:
                                parameter.expr = saved_parameters[p].attrs['expr']
                            else:
                                parameter.expr = None
                            if 'error' in saved_parameters[p].attrs:
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
            self.parameters = self.parameters
            def idx(model):
                return int(re.match('.*?([0-9]+)$', model['name']).group(1))
            self.models = sorted(self.models, key=idx)
            for model_index, model in enumerate(self.models):
                if model_index == 0:
                    self.model = model['model']
                    self.composite_model = model['name']
                else:
                    self.model += model['model']
                    self.composite_model += '+' + model['name']
                self.add_model_parameters(model_index)
            try:
                if 'model' in group:
                    composite_model = group['model'].nxvalue
                    self.model = self.eval_model(composite_model)
                    self.composite_model = composite_model
            except NeXusError:
                pass
            self.write_parameters()
            self.save_parameters_button.setVisible(True)
            self.save_fit_button.setVisible(False)

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

    def get_model_instance(self, model_class, model_name):
        if isinstance(self.all_models[model_class], types.ModuleType):
            return NXModel(self.all_models[model_class], prefix=model_name+'_')
        elif self.all_models[model_class].valid_forms:
            return self.all_models[model_class](prefix=model_name+'_',
                                                form=self.form_combo.selected)
        else:
            return self.all_models[model_class](prefix=model_name+'_')

    def choose_model(self):
        model_class = self.model_combo.selected
        try:
            if self.all_models[model_class].valid_forms:
                self.form_combo.setVisible(True)
                self.form_combo.clear()
                self.form_combo.add(*self.all_models[model_class].valid_forms)
            else:
                self.form_combo.setVisible(False)
        except AttributeError:
            self.form_combo.setVisible(False)
               
    def add_model(self):
        model_class = self.model_combo.selected
        model_index = len(self.models)
        model_name = (model_class.replace('Model', '').replace(' ', '_') 
                      + '_' + str(model_index+1))
        model = self.get_model_instance(model_class, model_name)
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
        if len(self.models) > 1:
            self.composite_model += '+' + model_name
        else:
            self.composite_model = model_name
        self.set_button_visibility()
 
    def add_model_parameters(self, model_index):
        self.add_model_rows(model_index)
        if self.first_time:
            self.layout.insertLayout(1, self.parameter_layout)
            self.layout.insertLayout(2, self.remove_layout)
            self.layout.insertLayout(3, self.adjust_layout)
            self.layout.insertLayout(4, self.action_layout)
            self.plot_combo.add('All')
            self.plot_combo.insertSeparator(1)
            self.plot_combo.insertSeparator(2)
            self.plot_combo.add('Composite Model')
            self.set_button_visibility()
        model_name = self.models[model_index]['name']
        self.remove_combo.add(self.expanded_name(model_name))
        self.remove_combo.select(self.expanded_name(model_name))
        self.plot_combo.insert(self.plot_combo.count()-2,
                               self.expanded_name(model_name))
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
            name = p.name.replace(model.prefix, '')
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
        expanded_name = self.remove_combo.currentText()
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
        self.plot_combo.removeItem(self.plot_combo.findText(expanded_name))
        self.remove_combo.removeItem(self.remove_combo.findText(expanded_name))
        self.model = None
        for i, m in enumerate(self.models):
            old_name = m['name']
            m['name'] = m['class'] + '_' + str(i+1)
            m['parameters'] = self.rename_parameters(m, old_name)
            m['label_box'].setText(self.expanded_name(m['name']))
            idx = self.parameter_grid.indexOf(m['label_box'])
            m['row'] = self.parameter_grid.getItemPosition(idx)[0]
            if i == 0:
                self.model = m['model']
                self.composite_model = m['name']
            else:
                self.model +=  m['model']
                self.composite_model += '+' + m['name'] 
            self.rename_model(old_name, m['name'])
        self.read_parameters()
        self.set_button_visibility()

    def rename_parameters(self, model, old_name):
        model['model'].prefix = model['name'] + '_'
        for p in model['parameters']:
            model['parameters'][p].name = model['parameters'][p].name.replace(
                old_name, model['name'])
            if model['parameters'][p].expr:
                model['parameters'][p].expr = model['parameters'][p].expr.replace(
                                                  old_name, model['name'])
            model['parameters'][p]._delay_asteval = True
        parameters = model['parameters'].copy()
        for p in parameters:
            old_p = p.replace(model['name'], old_name)
            parameters[p].box = model['parameters'][old_p].box
            parameters[p].box['error'].setText('')
        return parameters

    def rename_model(self, old_name, new_name):
        old_name, new_name = (self.expanded_name(old_name), 
                              self.expanded_name(new_name))
        plot_index = self.plot_combo.findText(old_name)
        self.plot_combo.setItemText(plot_index, new_name)
        remove_index = self.remove_combo.findText(old_name)
        self.remove_combo.setItemText(remove_index, new_name)

    def compose_model(self):
        if self.composite_dialog:
            try:
                self.composite_dialog.close()
            except Exception:
                pass
        self.composite_dialog = CompositeDialog(parent=self)
        self.composite_dialog.show()

    def eval_model(self, composite_text):
        models = {m['name']: m['model'] for m in self.models}
        text = composite_text
        for m in models:
            text = text.replace(m, f"models['{m}']")
        try:
            return eval(text)
        except Exception as error:
            raise NeXusError(str(error))

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
        try:
            if parameter.expr:
                return parameter._expr_eval(parameter.expr)
            else:
                return parameter.value
        except Exception as error:
            report_error(parameter.name, error)
                    
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
                    try:
                        p.box['value'].setText(format_float(p.value))
                    except Exception as error:
                        report_error(p.name, error)
                        return self.parameters
        return self.parameters

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
                else:
                    p.box['fixed'].setCheckState(QtCore.Qt.Checked)
                write_value(p.box['min'], p.min)
                write_value(p.box['max'], p.max)

    def get_model(self, model=None, fit=False):
        if self.plot_checkbox.isChecked():
            x = self.axis
        else:
            xmin, xmax = self.get_limits()
            x = np.linspace(xmin, xmax, 1001)
        model_axis = NXfield(x, name='axis')
        if fit and self.fit:
            parameters = self.fit.params
        else:
            parameters = self.read_parameters()
        if model is None:
            model = self.model
        y = model.eval(parameters, x=x)
        if isinstance(y, float):
            y = y * np.ones(shape=x.shape)
        if fit:
            model_data = NXfield(y, name='fit')
        else:
            model_data = NXfield(y, name='model')
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
            for label in ['label', 'legend_label']:
                self.fitview.plots[self.fitview.num][label] = self.data_label
            self.remove_plots()
        else:
            self.fitview.plots[self.data_num]['plot'].set_color(self.color)
            self.remove_plots()
        self.linestyle = cycle(self.linestyles)
        self.plot_mask()
        self.fitview.raise_()

    def plot_mask(self):
        mask_data = self.signal_mask()
        if mask_data:
            if self.mask_num in self.fitview.plots:
                self.fitview.plots[self.mask_num]['plot'].remove()
                del self.fitview.plots[self.mask_num]
            else:                
                self.mask_num = self.next_plot_num()
            self.fitview.plot(mask_data, over=True, num=self.mask_num, 
                              fmt='o', color='white', alpha=0.8)
            self.fitview.ytab.plotcombo.remove(self.mask_num)
            self.fitview.plots[self.mask_num]['legend_label'] = (
                                                    f"{self.tab_label} Mask")
            self.fitview.plots[self.mask_num]['show_legend'] = False
            if self.fitview.plots[self.mask_num]['cursor']:
                self.fitview.plots[self.mask_num]['cursor'].remove()
            self.fitview.plots[self.mask_num]['cursor'] = None
            self.fitview.update_panels()
        self.remove_rectangle()

    def plot_model(self, model=False):
        model_name = self.plot_combo.currentText()
        if model is False:
            if model_name == 'Composite Model':
                if self.plot_dialog:
                    try:
                        self.plot_dialog.close()
                    except Exception:
                        pass
                self.plot_dialog = PlotModelDialog(parent=self)
                self.plot_dialog.show()
                return
            elif model_name != 'All':
                name = self.compressed_name(model_name)
                model = [m['model'] for m in self.models if m['name'] == name][0]
        num = self.next_plot_num()
        xmin, xmax = self.plot_min, self.plot_max
        if model_name == 'All':
            if self.fitted:
                fmt = '-'
            else:
                fmt = '--'
            self.fitview.plot(self.get_model(), fmt=fmt, color=self.color,
                              xmin=self.plot_min, xmax=self.plot_max,
                              over=True, num=num)
            if self.fitted:
                self.fitview.plots[num]['legend_label'] = (
                                                    f"{self.tab_label} Fit")
            else:
                self.fitview.plots[num]['legend_label'] = (
                                                    f"{self.tab_label} Model")
        else:
            self.fitview.plot(self.get_model(model), color=self.color,
                              marker=None, linestyle=next(self.linestyle), 
                              xmin=self.plot_min, xmax=self.plot_max,
                              over=True, num=num)
            self.fitview.plots[num]['legend_label'] = (
                                            f"{self.tab_label} {model_name}")
        self.fitview.plots[num]['show_legend'] = False
        self.fitview.set_plot_limits(xmin=xmin, xmax=xmax)
        self.plot_nums.append(num)
        self.fitview.ytab.plotcombo.remove(num)
        self.fitview.ytab.plotcombo.select(self.data_num)
        self.remove_rectangle()
        self.fitview.update_panels()
        self.fitview.raise_()

    def next_plot_num(self):
        min_num = self.data_num*100 + 1
        max_num = min_num + 98
        valid_nums = [n for n in self.fitview.plots if min_num <= n <= max_num]
        if valid_nums:
            return max(valid_nums) + 1
        else:
            return min_num

    def fit_data(self):
        self.read_parameters()
        if self.fit_checkbox.isChecked():
            weights = self.weights
        else:
            weights = None
        try:
            self.fit_status.setText('Fitting...')
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
                self.fit_status.setText('Fit Successful Chi^2 = %s' 
                                       % format_float(self.fit.result.redchi))
            else:
                self.fit_status.setText('Fit Failed Chi^2 = %s' 
                                        % format_float(self.fit.result.redchi))
            self.parameters = self.fit.params
            self.write_parameters()
            self.set_button_visibility(fitted=True)
            self.fitted = True
        else:
            self.fit_status.setText('Fit failed')

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
        if self.fit is None:
            self.fit_status.setText('Fit not available for saving')
            return
        self.read_parameters()
        group = NXprocess()
        group['model'] = self.composite_model
        group['data'] = self.data
        for m in self.models:
            group[m['name']] = self.get_model(m['model'])
            parameters = NXparameters(attrs={'model':m['class']})
            for name in m['parameters']:
                p = self.fit.params[name]
                name = name.replace(m['model'].prefix, '')
                parameters[name] = NXfield(p.value, error=p.stderr, 
                                           initial_value=p.init_value,
                                           min=str(p.min), max=str(p.max),
                                           vary=p.vary, expr=p.expr)
            group[m['name']].insert(parameters)
        group['program'] = 'lmfit'
        group['program'].attrs['version'] = lmfit_version
        group['title'] = 'Fit Results'
        group['fit'] = self.get_model(fit=True)
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
        self.write_group(group)

    def save_parameters(self):
        """Saves parameters to an NXprocess group"""
        self.read_parameters()
        group = NXprocess()
        group['model'] = self.composite_model
        group['data'] = self.data
        for m in self.models:
            group[m['name']] = self.get_model(m['model'])
            parameters = NXparameters(attrs={'model':m['class']})
            for n,p in m['parameters'].items():
                n = n.replace(m['model'].prefix, '')
                parameters[n] = NXfield(p.value, error=p.stderr, 
                                        initial_value=p.init_value,
                                        min=str(p.min), max=str(p.max),
                                        vary=p.vary, expr=p.expr)
            group[m['name']].insert(parameters)
        group['title'] = 'Fit Model'
        group['model'] = self.get_model()
        self.write_group(group)

    def write_group(self, group):
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
        self.fit_status.setText(f'Parameters saved to w0/{name}')

    def restore_parameters(self):
        self.parameters = self.fit.init_params
        self.write_parameters()
        self.fit_status.setText('Waiting to fit...')

    def on_button_release(self, event):
        self.fitview.otab.release_zoom(event)
        if event.button == 1:
            self.remove_rectangle()
        elif event.button == 3 and self.fitview.zoom:
            self.xlo, self.xhi = self.fitview.zoom['x']
            self.ylo, self.yhi = self.fitview.zoom['y']
            self.draw_rectangle()
            self.clear_mask_button.setVisible(False)
            self.mask_button.setVisible(True)
        self.fitview.draw()

    def draw_rectangle(self):
        x, dx = self.xlo, self.xhi-self.xlo
        y, dy = self.ylo, self.yhi-self.ylo
        if self.rectangle:
            self.rectangle.set_bounds(x, y, dx, dy)
        else:
            self.rectangle = NXrectangle(x, y, dx, dy, plotview=self.fitview,
                                         facecolor='none', 
                                         edgecolor=self.fitview._gridcolor)
            self.rectangle.set_linestyle('dashed')
            self.rectangle.set_linewidth(2)
        self.fitview.draw()

    def remove_rectangle(self):
        if self.rectangle:
            self.rectangle.remove()
        self.rectangle = None
        self.fitview.draw()

    def remove_masks(self):
        if self.mask_num in self.fitview.plots:
            self.fitview.plots[self.mask_num]['plot'].remove()
            del self.fitview.plots[self.mask_num]
            self.fitview.ytab.plotcombo.remove(self.mask_num)
        self.remove_rectangle()

    def remove_plots(self):
        for num in [n for n in self.plot_nums if n in self.fitview.plots]:
            self.fitview.plots[num]['plot'].remove()
            del self.fitview.plots[num]
        self.plot_nums = []
        if self.data_num in self.fitview.plots:
            self.fitview.num = self.data_num
            self.fitview.ytab.plotcombo.select(self.data_num)
        self.fitview.draw()
        self.fitview.update_panels()
   
    def apply(self):
        self.remove_plots()
        if self.model is not None:
            self.fitview.plot(self.get_model(), fmt='-', color=self.color, 
                              over=True)
        
    def close(self):
        self.fitview.canvas.mpl_disconnect(self.cid)
        self.remove_masks()
        if self.plotview:
            self.remove_plots()


class CompositeDialog(NXDialog):
    """Dialog to define a composite model."""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.parent = parent
        self.expression = NXLineEdit(self.parent.composite_model)
        self.add_model_button = NXPushButton('Insert Model', self.insert_model)
        self.model_combo = NXComboBox(items=[m['name'] 
                                             for m in self.parent.models])
        self.set_layout(self.expression,
                        self.make_layout(self.add_model_button,
                                         self.model_combo, 
                                         'stretch',
                                         self.close_buttons(save=True)))
        self.set_title("Editing Composite Model")

    def insert_model(self):
        self.expression.insert(self.model_combo.selected)

    def accept(self):
        try:
            self.parent.model = self.parent.eval_model(self.expression.text())
            self.parent.composite_model = self.expression.text()
            super().accept()    
        except NeXusError as error:
            report_error("Editing Composite Model", error)            


class PlotModelDialog(NXDialog):
    """Dialog to plot a composite model."""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.parent = parent
        self.expression = NXLineEdit(self.parent.composite_model)
        self.plot_model_button = NXPushButton('Plot Model', self.plot_model)
        self.set_layout(self.expression,
                        self.make_layout(self.plot_model_button,
                                         'stretch',
                                         self.close_buttons(close=True)))
        self.set_title("Plotting Composite Model")
        self.setMinimumWidth(400)

    def plot_model(self):
        try:
            model = self.parent.eval_model(self.expression.text())
            self.parent.plot_model(model)
            super().accept()
        except NeXusError as error:
            report_error("Plotting Composite Model", error)            


class ExpressionDialog(NXDialog):
    """Dialog to edit a fitting parameter expression."""

    def __init__(self, parameter, parent=None):

        super().__init__(parent=parent)

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
            super().accept()    
        except NeXusError as error:
            report_error("Editing Expression", error)            
