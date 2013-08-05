import numpy as np
import pyspec.mpfit as mpfit
from scipy.optimize import leastsq

from nexpy.api.nexus import NXdata, NXparameters, NeXusError

class Fit(object):

    def __init__(self, data=None, functions=None):
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
            if errors:
                self.e = errors.nxdata.astype(np.float64)
        else:
            raise TypeError("Must be an NXdata group")

    def get_calculation(self, x=None):
        if x is None: x = self.x
        calculation = np.zeros(x.shape,np.float64)
        for function in self.functions:
            calculation += function.module.values(x, [p.value for p in function.parameters])
        return calculation

    def residuals(self, p):
        map(lambda x,y: x.__setattr__('value', y), self.parameters, p)
        return self.y - self.get_calculation()

    def fit_data(self):
        """Run a scipy leastsq regression"""
        self.parameters = []
        for function in self.functions:
            for parameter in function.parameters:
                if not parameter.fixed:
                    self.parameters.append(parameter)
        fits, covar, info, msg, status = leastsq(self.residuals, 
                                                 [p.value for p in self.parameters], 
                                                 full_output = 1, factor = 0.1)
        self.fits = fits 
        self.stdev = np.sqrt(np.diag(covar.T))
        self.covar = covar
        self.info = info
        self.status_message = msg
        self.status_flag = status
        print self.stdev
        print self.info
        print self.status_message
        print self.status_flag
        map(lambda x,y: x.__setattr__('value', y), self.parameters, fits)


class Function(object):

    def __init__(self, name=None, module=None, parameters=[]):
        self.name = name
        self.module = module
        self.parameters = parameters
        self.index = None


class Parameter(object):

    def __init__(self, name=None, value=None, minimum=None, maximum=None, 
                 fixed=False, bound=None):
        self.name = name
        self.value = value
        self.minimum = minimum
        self.maximum = maximum
        self.fixed = fixed
        self.bound = bound
        self.index = None