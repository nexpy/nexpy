#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2017, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import importlib
import inspect
import numpy as np
import os
import pkg_resources
import sys

from lmfit import Model, Parameters, Parameter, minimize, fit_report

from nexusformat.nexus import *

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

    return models

all_models = get_models()


class Fit(object):
    """Class defining the data, parameters, and results of a least-squares fit.

    Attributes
    ----------
    x : ndarray
        x-values of data.
    y : ndarray
        y-values of data.
    e : ndarray, optional
        standard deviations of the y-values.
    use_errors : bool
        set to True if the errors are to be used in the fit.
    data : NXdata
        NXdata group containing the signal and axis.
    functions : list of Function objects
        Functions to be used in constructing the fit model.
    fit
        Results of the fit.
    """

    def __init__(self, data=None, functions=None, use_errors=True):
        self.x = None
        self.y = None
        self.e = None
        self.use_errors = use_errors
        self.set_data(data)
        self.functions = functions
        self.fit = None
        self.result = None

    def __repr__(self):
        return 'Fit(%s)' % self.data.nxpath

    def set_data(self, data):
        """
        Initialize the data used in the fit

        Parameters
        ----------
        data : NXdata
            NXdata group containing the signal and axis.
        """
        if isinstance(data, NXdata):
            self.data = data
            signal = data.nxsignal
            axes = data.nxaxes[0]
            errors = data.nxerrors
            if len(signal.shape) != 1:
                raise ValueError("Fit only possible on one-dimensional data")
            self.x = axes.nxdata.astype(np.float64)
            self.y = signal.nxdata.astype(np.float64)
            if errors and self.use_errors:
                self.e = errors.nxdata.astype(np.float64)
        else:
            raise TypeError("Must be an NXdata group")

    def get_model(self, x=None, f=None):
        """Returns the value of the model.

        Parameters
        ----------
        x : ndarray, optional
            x-values where the model is calculated. Defaults to `self.x`
        f : Function, optional
            Function to be included in the model. Defaults to all the functions.

        Returns
        -------
        model : ndarray
            values of the model at the requested x-varlues.
        """
        if x is None: 
            x = self.x
        model = np.zeros(x.shape,np.float64)
        if f:
            model = f.module.values(x, [p.value for p in f.parameters])
        else:
            for f in self.functions:
                model += f.module.values(x, [p.value for p in f.parameters])
        return model

    def residuals(self, parameters):
        """Returns the residuals for the specified parameters

        Parameters
        ----------
        parameters : List of Parameters
            Parameter objects containing the values to be used in the model.

        Returns
        -------
        residuals : ndarray
            Differences between the y-values and the model.
        """
        for parameter in parameters:
            self.parameters[parameter].value = parameters[parameter].value
        if self.e is not None:
             return (self.y - self.get_model()) / self.e
        else:
            return self.y - self.get_model()

    def fit_data(self):
        """Run a scipy leastsq regression."""
        self.parameters = Parameters()
        for f in self.functions:
            for p in f.parameters:
                p.original_name = p.name
                self.parameters[f.name+p.name] = p
                if p.value is None:
                    p.value = 1.0
                p.init_value = p.value
        self.result = minimize(self.residuals, self.parameters)
        if __version__ > '0.8.3':
            for parameter in self.parameters:
                self.parameters[parameter].value = \
                    self.result.params[parameter].value
                self.parameters[parameter].stderr = \
                    self.result.params[parameter].stderr
                self.parameters[parameter].correl = \
                    self.result.params[parameter].correl
        for f in self.functions:
            for p in f.parameters:
                p.name = p.original_name

    def fit_report(self):
        """Return the report created by lmfit."""
        return str(fit_report(self.parameters))

    def save(self, x=None):
        """Save the fit results in a NXprocess group.

        Parameters
        ----------
        x : ndarray, optional
            x-values at which to calculate the model. Defaults to `self.x`
        Returns
        -------
        group : NXprocess
            NXprocess group that contains the data, models and parameters.
        """
        group = NXprocess(program='lmfit', version=__version__)    
        group['data'] = self.data
        for f in self.functions:
            group[f.name] = NXdata(NXfield(self.get_model(x, f), name='model'),
                                   NXfield(x, name=self.data.nxaxes[0].nxname), 
                                   title='Fit Results')
            parameters = NXparameters()
            for p in f.parameters:
                parameters[p.name] = NXfield(p.value, error=p.stderr, 
                                             initial_value=p.init_value,
                                             min=str(p.min), max=str(p.max))
            group[f.name]['parameters'] = parameters
        group['title'] = 'Fit Results'
        group['fit'] = NXdata(NXfield(self.get_model(x), name='model'),
                              NXfield(x, name=self.data.nxaxes[0].nxname), 
                              title='Fit Results')
        if self.result is not None:
            fit = NXparameters()
            fit.nfev = self.result.nfev
            fit.chisq = self.result.chisqr
            fit.redchi = self.result.redchi
            fit.message = self.result.message
            group['statistics'] = fit
            group.note = NXnote(self.result.message,
                ('Chi^2 = %s\n' % self.result.chisqr +
                 'Reduced Chi^2 = %s\n' % self.result.redchi +
                 'No. of Function Evaluations = %s\n' % self.result.nfev +
                 'No. of Variables = %s\n' % self.result.nvarys +
                 'No. of Data Points = %s\n' % self.result.ndata +
                 'No. of Degrees of Freedom = %s\n' % self.result.nfree +
                 '%s' % self.fit_report()))

        return group


class Function(object):
    """Class defining a function to be used in the fit.

    Attributes
    ----------
    name : str
        name of the function
    module : Python module
        module containing function code
    function_index : int
        index of the function
    """

    def __init__(self, name, module=None, parameters=None, function_index=0):        
        self.name = name
        self.module = module
        self.function_index = function_index
        self._parameters = parameters
        if module:
            self.model = NXModel(module)
        elif name in all_functions:
            self.module = all_functions[name]
            self.model = NXModel(self.module)

    def __lt__(self, other):
         return int(self.function_index) < int(other.function_index)

    def __repr__(self):
        return 'Function(%s)' % self.name

    @property
    def parameters(self):
        if self._parameters is None:
            self._parameters = self.model.make_params()
        return self._parameters

    def guess_parameters(self, x, y):
        """Return a list of parameters using the function's `guess` method."""
        self._parameters = self.model.guess(y, x)

    @property
    def parameter_values(self):
        """Return a list of parameter values."""
        return [self.parameters[p].value for p in self.parameters]

    def function_values(self, x):
        """Return the calculated values with the current parameters."""
        return self.model.eval(self.parameters, x=x)


class NXModel(Model):

    def __init__(self, module, **kwargs):
        self.module = module
        super(NXModel, self).__init__(self.module.values, **kwargs)
        self._param_root_names = self.module.parameters

    def _parse_params(self):
        self._param_names = self.module.parameters
        self.def_vals = {}

    def make_funcargs(self, params=None, kwargs=None, strip=True):
        if kwargs is None:
            kwargs = {}
        out = {}
        if 'x' in kwargs:
            out['x'] = kwargs['x']
        else:
            raise NeXusError('Cannot calculate module values without x')
        out['p'] = [params[p].value for p in params]
        return out            

    def guess(self, y, x=None, **kwargs):
        _guess = self.module.guess(x, y)
        pars = self.make_params()
        for i, p in enumerate(pars):
            pars[p].value = _guess[i]
        return pars
