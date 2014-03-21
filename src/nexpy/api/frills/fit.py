#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import numpy as np
from lmfit import minimize, Parameters, Parameter, fit_report

from nexpy.api.nexus import NXentry, NXdata, NXparameters, NeXusError

class Fit(object):

    def __init__(self, data=None, functions=None, use_errors=True):
        self.x = None
        self.y = None
        self.e = None
        self.use_errors = use_errors
        self.set_data(data)
        self.functions = functions
        self.fit = None

    def set_data(self, data):
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
        if x is None: x = self.x
        model = np.zeros(x.shape,np.float64)
        if f:
            model = f.module.values(x, [p.value for p in f.parameters])
        else:
            for f in self.functions:
                model += f.module.values(x, [p.value for p in f.parameters])
        return model

    def residuals(self, parameters):
        if self.e is not None:
             return (self.y - self.get_model()) / self.e
        else:
            return self.y - self.get_model()

    def fit_data(self):
        """Run a scipy leastsq regression"""
        self.parameters = Parameters()
        for f in self.functions:
            for p in f.parameters:
                p.original_name = p.name
                self.parameters[f.name+p.name] = p
                if p.value is None:
                    p.value = 1.0
        self.result = minimize(self.residuals, self.parameters)
        for f in self.functions:
            for p in f.parameters:
                p.name = p.original_name

    def fit_report(self):
        return str(fit_report(self.parameters))

    def save_fit(self):
        """Saves fit results to an NXentry"""
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
        return entry

class Function(object):

    def __init__(self, name=None, module=None, parameters=None, function_index=0):
        self.name = name
        self.module = module
        self.parameters = parameters
        self.function_index = function_index

    def __lt__(self, other):
         return self.function_index < other.function_index