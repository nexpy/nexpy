# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import numpy as np
from lmfit import Parameter, Parameters, __version__, fit_report, minimize
from nexusformat.nexus import NXdata, NXfield, NXnote, NXparameters, NXprocess


class Fit:
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
        return f'Fit({self.data.nxpath})'

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
            self.x = axes.centers().nxdata.astype(np.float64)
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
            Function to be included in the model. Defaults to all the
            functions.

        Returns
        -------
        model : ndarray
            values of the model at the requested x-varlues.
        """
        if x is None:
            x = self.x
        model = np.zeros(x.shape, np.float64)
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
        if __version__ > '0.8.3':
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
            group.note = NXnote(
                self.fit.result.message,
                f'Chi^2 = {self.fit.result.chisqr}\n'
                f'Reduced Chi^2 = {self.fit.result.redchi}\n'
                f'No. of Function Evaluations = {self.fit.result.nfev}\n'
                f'No. of Variables = {self.fit.result.nvarys}\n'
                f'No. of Data Points = {self.fit.result.ndata}\n'
                f'No. of Degrees of Freedom = {self.fit.result.nfree}\n'
                f'{self.fit.fit_report()}')

        return group


class Function:
    """Class defining a function to be used in the fit.

    Attributes
    ----------
    name : str
        name of the function
    module : Python module
        module containing the function code.
    function_index : int
        index of the function
    """

    def __init__(self, name=None, module=None, parameters=None,
                 function_index=0):
        self.name = name
        self.module = module
        self._parameters = parameters
        self.function_index = function_index

    def __lt__(self, other):
        return int(self.function_index) < int(other.function_index)

    def __repr__(self):
        return f'Function({self.name})'

    @property
    def parameters(self):
        """List of parameters defining the function."""
        if self._parameters is None:
            self._parameters = [Parameter(name)
                                for name in self.module.parameters]
        return self._parameters

    def guess_parameters(self, x, y):
        """Return parameters determined by the function's `guess` method."""
        [setattr(p, 'value', g) for p, g in zip(self.parameters,
                                                self.module.guess(x, y))]

    @property
    def parameter_values(self):
        """Return a list of parameter values."""
        return [p.value for p in self.parameters]

    def function_values(self, x):
        """Return the calculated values with the current parameters."""
        return self.module.values(x, self.parameter_values)
