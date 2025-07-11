# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import inspect
import re
import types
from itertools import cycle

import numpy as np
from lmfit import Model, Parameters
from lmfit import __version__ as lmfit_version
from nexusformat.nexus import (NeXusError, NXdata, NXentry, NXfield, NXnote,
                               NXparameters, NXprocess, nxload)

from .plotview import NXPlotView, linestyles
from .pyqt import QtCore, QtWidgets
from .utils import display_message, format_float, load_models, report_error
from .widgets import (NXCheckBox, NXColorBox, NXComboBox, NXDialog, NXLabel,
                      NXLineEdit, NXMessageBox, NXPanel, NXPushButton,
                      NXrectangle, NXScrollArea, NXTab)


def get_models():
    """
    Return a dictionary of LMFIT models.

    This function returns a dictionary of LMFIT models, including those
    defined in the LMFIT package and those defined in the
    ``nexpy.models`` package. Additional models can also be defined in
    the ``~/.nexpy/models`` directory or in another installed package,
    which declares the entry point ``nexpy.models``. The models are
    returned as a dictionary where the keys are the names of the models
    and the values are the classes defining the models.
    """
    from lmfit.models import lmfit_models
    models = lmfit_models
    if 'Expression' in models:
        del models['Expression']
    if 'Gaussian-2D' in models:
        del models['Gaussian-2D']

    nexpy_models = load_models()

    for model in nexpy_models:
        try:
            models.update(
                dict((n.strip('Model'), m)
                for n, m in inspect.getmembers(nexpy_models[model],
                                               inspect.isclass)
                if issubclass(m, Model) and n != 'Model'))
        except ImportError:
            pass

    return models


all_models = get_models()


def get_methods():
    """Return a dictionary of minimization methods in LMFIT."""
    methods = {'leastsq': 'Levenberg-Marquardt',
               'least_squares': 'Least-Squares minimization, '
                                'using Trust Region Reflective method',
               'differential_evolution': 'differential evolution',
               'nelder': 'Nelder-Mead',
               'lbfgsb': ' L-BFGS-B',
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
        """
        Initialize a Model from a module.

        Parameters
        ----------
        module : module
            A module containing a function values() and a list of
            parameters.
        **kwargs :
            Additional keyword arguments are passed to the Model
            constructor.
        """
        self.module = module
        super().__init__(self.module.values,
                         param_names=self.module.parameters,
                         independent_vars=self._get_x(), **kwargs)

    def _parse_params(self):
        """
        Initialize the parameter names and default values.

        This method is called by Model.__init__ after the parameters
        have been set. It is used to set the internal parameter names
        and default values used by the Model class. The names of the
        parameters are set to the prefix plus the parameter name, and
        the default values are set to an empty dictionary.
        """
        if self._prefix is None:
            self._prefix = ''
        self._param_names = [f"{self._prefix}{p}"
                             for p in self._param_root_names]
        self.def_vals = {}

    def _get_x(self):
        """Return a list of the names of the independent variables."""
        return [key for key in inspect.signature(self.module.values).parameters
                if key != 'p']

    def make_funcargs(self, params=None, kwargs=None, strip=True):
        """
        Return a dictionary of keyword arguments for the model function.

        Parameters
        ----------
        params : Parameters, optional
            The Parameters to use.
        kwargs : dict, optional
            Additional keyword arguments to pass to the model function.
        strip : bool, optional
            Whether to strip the prefix from the parameter names. By
            default, this is True.

        Returns
        -------
        function_out : dict
            A dictionary of keyword arguments for the model function.
        """
        self._func_allargs = ['x'] + self._param_root_names
        out = super().make_funcargs(params=params, kwargs=kwargs, strip=strip)
        function_out = {}
        function_out['p'] = [out[p]
                             for p in out if p in self._param_root_names]
        for key in out:
            if key not in self._param_root_names:
                function_out[key] = out[key]
        return function_out

    def guess(self, y, x=None, **kwargs):
        """
        Estimate initial model parameter values from data.

        Parameters
        ----------
        y : ndarray
            data to fit
        x : ndarray, optional
            x-values of the data, by default None
        **kwargs :
            Additional keyword arguments are passed to the model's guess
            method.

        Returns
        -------
        Parameters
            A Parameters object with the estimated values.
        """
        _guess = self.module.guess(x, y)
        pars = self.make_params()
        for i, p in enumerate(pars):
            pars[p].value = _guess[i]
        return pars


class FitDialog(NXPanel):

    def __init__(self, parent=None):
        """
        Initialize the Fit Panel.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the dialog. The default is None.
        """
        super().__init__('Fit', title='Fit Panel', apply=True, reset=True,
                         parent=parent)
        self.setMinimumWidth(850)
        self.tab_class = FitTab

    def activate(self, data, plotview=None, color='C0'):
        """
        Activate the Fit Panel.

        Parameters
        ----------
        data : NXdata
            data to fit
        plotview : NXPlotView, optional
            The plotview containing the data to fit. The default is None.
        color : str, optional
            The color of the fit curve. The default is 'C0'.
        """
        
        if plotview:
            label = plotview.label + ': ' + str(plotview.num)
        else:
            label = data.nxroot.nxname + data.nxpath
        super().activate(label, data, plotview=plotview, color=color)


class FitTab(NXTab):

    def __init__(self, label, data, plotview=None, color='C0', parent=None):

        """
        Initialize the Fit Tab.

        Parameters
        ----------
        label : str
            The label for the tab.
        data : NXdata
            The data to fit.
        plotview : NXPlotView, optional
            The plotview containing the data to fit. The default is None.
        color : str, optional
            The color of the fit curve. The default is 'C0'.
        parent : QWidget, optional
            The parent of the tab. The default is None.
        """
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
        self.compose_button = NXPushButton(
            "Compose Models", self.compose_model)
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
            self.plotview = NXPlotView('Fit')
            self.plotview.plot(self._data, fmt='o', color=color)
        self.data_num = self.plotview.num
        self.data_label = self.plotview.plots[self.plotview.num]['label']
        self.cursor = self.plotview.plots[self.plotview.num]['cursor']
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

        self.cid = self.plotview.canvas.mpl_connect('button_release_event',
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
        self.xlo, self.xhi = self.plotview.ax.get_xlim()
        self.ylo, self.yhi = self.plotview.ax.get_ylim()

        if group:
            self.load_fit(group)

    def __repr__(self):
        return f'FitTab("{self.data_label}")'

    @property
    def fitview(self):
        """The plotting window for the fitting data."""
        if self.plotview and self.plotview.label in self.plotviews:
            return self.plotview
        elif 'Fit' in self.plotviews:
            self.plotview = self.plotviews['Fit']
            return self.plotview
        else:
            return None

    @fitview.setter
    def fitview(self, plotview):
        self.plotview = plotview

    def initialize_data(self, data):
        """
        Initialize the data to be fitted.

        Parameters
        ----------
        data : NXdata
            The data to be fitted.

        Raises
        ------
        NeXusError
            If the data is not one-dimensional.
        """
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
        """Initialize the list of models."""
        self.all_models = all_models

    def initialize_parameter_grid(self):
        """
        Initialize the parameter grid layout.

        The parameter grid is a table of parameters for each model
        with columns for the model name, parameter name, value, min,
        max, and whether the parameter is fixed or not. The parameter
        grid is located in a scroll area with a minimum height and
        width to prevent it from being too small.

        Returns
        -------
        grid_layout : QGridLayout
            The layout of the parameter grid.
        """
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
        """
        Set the visibility of the buttons in the dialog based on whether
        there are any models defined and whether the data have been
        fitted.

        Parameters
        ----------
        fitted : bool, optional
            Set to True if the data have been fitted.
        """
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
        """The data to be fitted."""
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
        """
        The data to be fitted as a one-dimensional array.

        If the data is masked, the mask is removed before returning the
        data.
        """
        signal = self.data['signal']
        if signal.mask:
            return signal.nxdata.compressed().astype(np.float64)
        else:
            return signal.nxdata.astype(np.float64)

    @property
    def axis(self):
        """
        The x-axis values of the data to be fitted.

        If the data is masked, the mask is removed before returning the
        axis values.
        """
        data = self.data
        signal = data['signal'].nxdata
        axis = data['axis'].nxdata.astype(np.float64)
        if isinstance(signal, np.ma.MaskedArray):
            return np.ma.masked_array(axis, mask=signal.mask).compressed()
        else:
            return axis

    @property
    def errors(self):
        """
        The data errors as a one-dimensional array.

        If the data is masked, the mask is removed before returning the
        errors. If the data has no errors, returns None.
        """
        data = self.data
        if data.nxerrors:
            errors = data.nxerrors.nxdata.astype(np.float64)
            signal = data['signal'].nxdata
            if isinstance(signal, np.ma.MaskedArray):
                return np.ma.masked_array(
                    errors, mask=signal.mask).compressed()
            else:
                return errors
        else:
            return None

    @property
    def weights(self):
        """
        The data weights as a one-dimensional array.

        If the data is masked, the mask is removed before returning the
        weights. If the data has no errors, returns None.
        """
        if self.errors is not None and np.all(self.errors):
            return 1.0 / self.errors
        else:
            return None

    def signal_mask(self):
        """
        Return the masked data as a new NXdata group.

        Returns
        -------
        NXdata
            The masked data as a new NXdata group with the same name as
            the original data, but with '_mask' appended to the name. If
            no data are masked, returns None.
        """
        mask = self._data['signal'].mask
        if mask and mask.any():
            mask_data = NXfield(self._data['signal'].nxdata.data[mask == 1],
                                name='mask')
            mask_axis = NXfield(self._data['axis'].nxdata[mask == 1],
                                name='axis')
            return NXdata(mask_data, mask_axis)
        else:
            return None

    def define_errors(self):
        """
        Define the errors for the fit.

        If the 'fit' checkbox is checked, the errors are set to the square
        root of the signal, but with a minimum of 1. If the checkbox is
        not checked, the errors attribute is deleted.
        """
        if self.poisson_errors:
            if self.fit_checkbox.isChecked():
                self._data.nxerrors = np.sqrt(np.where(self._data.nxsignal < 1,
                                                       1, self._data.nxsignal))
            else:
                del self._data[self._data.nxerrors.nxname]

    def mask_data(self):
        """
        Mask the data.

        This function can be used in two ways to mask the data:

        1. Select data with right-click zoom and click 'Mask Data'
        2. Double-click points to be masked

        The function checks if any data has been selected with the zoom tool.
        If data is selected, it is masked. Otherwise, it checks if a rectangle
        has been drawn. If a rectangle has been drawn, the data within the
        rectangle is masked. If no data is selected and no rectangle has been
        drawn, a message is displayed with instructions on how to mask the
        data.
        """
        axis = self._data['axis']
        signal = self._data['signal']
        if self.cursor and self.cursor.selections:
            try:
                idx = self.cursor.selections[0].index
            except AttributeError:
                raise NeXusError("Please update the 'mplcursors' package")
            idx = self.cursor.selections[0].index
            if np.ma.is_masked(signal.nxvalue[idx]):
                signal[idx] = np.ma.nomask
            else:
                signal[idx] = np.ma.masked
            self.cursor.remove_selection(self.cursor.selections[0])
        elif self.rectangle:
            signal[(axis >= self.xlo) & (axis <= self.xhi)] = np.ma.masked
        else:
            display_message(
                "Masking Data",
                "There are two methods to mask data:\n\n"
                "1) Select data with right-click zoom and click 'Mask Data'\n"
                "2) Double-click points to be masked", width=350)
            return
        self.plot_mask()
        if np.ma.is_masked(signal.nxvalue):
            self.mask_button.setVisible(False)
            self.clear_mask_button.setVisible(True)
        else:
            self.mask_button.setVisible(True)
            self.clear_mask_button.setVisible(False)

    def clear_masks(self):
        """
        Clear all masks from the signal.

        This function removes all masks from the signal and changes the
        visibility of the 'Mask Data' and 'Clear Masks' buttons so that
        'Mask Data' is visible and 'Clear Masks' is not.
        """
        self._data['signal'].mask = np.ma.nomask
        self.remove_masks()
        self.mask_button.setVisible(True)
        self.clear_mask_button.setVisible(False)

    @property
    def parameters(self):
        """
        The LMFIT Parameters object containing all the models.

        This property is a read-only property that returns a Parameters
        object that is a composite of all the parameters from all the
        models currently in the FitTab. It is used by the FitTab to pass
        the parameters to the LMFIT minimizer.

        Returns
        -------
        Parameters
            The LMFIT Parameters object that contains all the parameters
            for all the models.
        """
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
        """The minimization method selected in the FitTab."""        
        return self.fit_combo.selected

    @property
    def color(self):
        """The current color as a string."""
        return self.color_box.textbox.text()

    def compressed_name(self, name):
        """Converts a model name to a compressed name"""
        return re.sub(r'([a-zA-Z_ ]*) [#] (\d*)$', r'\1_\2',
                      name, count=1).replace(' ', '_')

    def expanded_name(self, name):
        """Converts a compressed name to a model name"""
        return re.sub(r'([a-zA-Z_]*)_(\d*)$', r'\1 # \2',
                      name, count=1).replace('_', ' ').strip()

    def parse_model_name(self, name):
        """
        Parse a model name.

        The model name is expected to be of the form <model_name>_<number>,
        where <model_name> is the name of the model and <number> is the
        number of the model. The _ is optional. The function returns a tuple
        (name, number), where name is the name of the model and number is the
        number of the model. If the model name does not match the expected
        format, the function returns (None, None).

        Parameters
        ----------
        name : str
            The model name to be parsed.

        Returns
        -------
        name : str
            The name of the model.
        number : str
            The number of the model.
        """
        match = re.match(r'([a-zA-Z0-9_-]*)_(\d*)$', name)
        if match:
            return match.group(1).replace('_', ' '), match.group(2)
        try:
            match = re.match(r'([a-zA-Z]*)(\d*)', name)
            return match.group(1), match.group(2)
        except Exception:
            return None, None

    def load_fit(self, group):
        """
        Loads a fit from a NeXus NXprocess group.

        Parameters
        ----------
        group : NXprocess
            The NeXus NXprocess group containing the fit.
        """
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
                                parameter.vary = (
                                    saved_parameters[p].attrs['vary'])
                            if 'expr' in saved_parameters[p].attrs:
                                parameter.expr = (
                                    saved_parameters[p].attrs['expr'])
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
        """
        Convert a parameter name in the Fit Dialog to its equivalent in
        the saved parameters.

        This function is used to convert parameter names in the Fit
        Dialog to their equivalent names in the saved parameters. The
        conversion is done in the following order: 1. If the parameter
        is in the saved parameters, it is returned unchanged. 2. If the
        capitalized parameter is in the saved parameters, it is returned
           with the first letter capitalized.
        3. If the parameter is 'amplitude' and 'Integral' is in the
           saved parameters, 'Integral' is returned.
        4. If the parameter is 'sigma' and 'Gamma' is in the saved
           parameters, 'Gamma' is returned.
        5. If the parameter is 'intercept' and 'Constant' is in the
           saved parameters, 'Constant' is returned.
        6. Otherwise, an empty string is returned.

        Parameters
        ----------
        parameter : str
            The parameter name in the Fit Dialog.
        saved_parameters : dict
            The saved parameters.

        Returns
        -------
        str
            The converted parameter name.
        """
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
        """
        Returns an instance of the specified model class.

        Parameters
        ----------
        model_class : str
            The name of the model class.
        model_name : str
            The name of the model.

        Returns
        -------
        model : Model
            An instance of the specified model class.
        """
        if isinstance(self.all_models[model_class], types.ModuleType):
            return NXModel(self.all_models[model_class], prefix=model_name+'_')
        elif self.all_models[model_class].valid_forms:
            return self.all_models[model_class](prefix=model_name+'_',
                                                form=self.form_combo.selected)
        else:
            return self.all_models[model_class](prefix=model_name+'_')

    def choose_model(self):
        """
        Slot to be called when the user selects a model class from the
        model class combo box. This slot makes the form combo box
        visible and populates it with the valid forms of the selected
        model class. If the selected model class does not have valid
        forms, the form combo box is made invisible.
        """  
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
        """
        Slot to be called when the user clicks the "Add" button.

        This slot adds the selected model class to the list of models,
        creates an instance of the model class, and adds its parameters
        to the model parameters box. It guesses the initial values of
        the model parameters by calling the guess method of the model
        class. If the model class does not have a guess method, it
        creates a set of parameters with default values. It then updates
        the model by adding the new model to the list of models and by
        making the new model the active model. If the list of models
        contains more than one model, it names the active model by
        combining the names of all the models. It then makes the buttons
        for saving the fit and for plotting the models visible.
        """
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
        """
        Adds the parameters of a model to the model parameters box.

        Parameters
        ----------
        model_index : int
            The index of the model in the list of models.

        This method adds a row to the parameter grid for each parameter
        of the model, and adds a row to the remove combo box. If this is
        the first model, it adds the parameter, remove, adjust, and
        action layouts to the main layout, and adds the first model to
        the plot combo box.
        """
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
        """
        Adds a row to the parameter grid for each parameter of a model.

        Parameters
        ----------
        model_index : int
            The index of the model in the list of models.

        This method adds a row to the parameter grid for each parameter
        of the model, adds a row to the remove combo box, and adds the
        model to the plot combo box. If this is the first model, it adds
        the parameter, remove, adjust, and action layouts to the main
        layout.
        """
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
        """
        Slot to be called when the user clicks the "Remove" button.

        This slot removes the selected model from the list of models,
        removes the parameters of the model from the model parameters
        box, and updates the model by subtracting the selected model from
        the list of models. If the list of models contains more than one
        model, it renames the active model by combining the names of all
        the models. If the list of models contains only one model, it
        makes the buttons for saving the fit and for plotting the models
        invisible. It then reads the parameters and makes the buttons
        for saving the fit and for plotting the models visible.
        """
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
                self.model += m['model']
                self.composite_model += '+' + m['name']
            self.rename_model(old_name, m['name'])
        self.read_parameters()
        self.set_button_visibility()

    def rename_parameters(self, model, old_name):
        """
        Renames the parameters of a model.

        This method renames the parameters of a model by replacing the
        old name with the new name. It also updates the expressions of
        the parameters by replacing the old name with the new name. The
        _delay_asteval attribute of each parameter is set to True to
        prevent the expression from being evaluated until the model is
        evaluated. The method returns a new dictionary of parameters
        with the new names and the original parameter boxes.

        Parameters
        ----------
        model : dict
            The dictionary of the model.
        old_name : str
            The old name of the model.

        Returns
        -------
        parameters : dict
            The new dictionary of parameters with the new names and the
            original parameter boxes.
        """
        model['model'].prefix = model['name'] + '_'
        for p in model['parameters']:
            model['parameters'][p].name = model['parameters'][p].name.replace(
                old_name, model['name'])
            if model['parameters'][p].expr:
                model['parameters'][p].expr = (
                    model['parameters'][p].expr.replace(
                        old_name, model['name']))
            model['parameters'][p]._delay_asteval = True
        parameters = model['parameters'].copy()
        for p in parameters:
            old_p = p.replace(model['name'], old_name)
            parameters[p].box = model['parameters'][old_p].box
            parameters[p].box['error'].setText('')
        return parameters

    def rename_model(self, old_name, new_name):
        """
        Renames a model in the plot and remove combo boxes.

        This method takes the old name and new name of a model and
        renames the model in the plot combo box and the remove combo
        box. This method is used when the model is renamed in the
        Fit Panel.

        Parameters
        ----------
        old_name : str
            The old name of the model.
        new_name : str
            The new name of the model.
        """
        old_name, new_name = (self.expanded_name(old_name),
                              self.expanded_name(new_name))
        plot_index = self.plot_combo.findText(old_name)
        self.plot_combo.setItemText(plot_index, new_name)
        remove_index = self.remove_combo.findText(old_name)
        self.remove_combo.setItemText(remove_index, new_name)

    def compose_model(self):
        """
        Opens a dialog to allow the user to enter a composite model.

        When the method is called, it first closes any existing composite
        dialog. Then it creates a new instance of the CompositeDialog class
        and shows it. The dialog is the same as the one used to enter the
        initial model, but the window title is changed to "Composite Model".
        """
        if self.composite_dialog:
            try:
                self.composite_dialog.close()
            except Exception:
                pass
        self.composite_dialog = CompositeDialog(parent=self)
        self.composite_dialog.show()

    def eval_model(self, composite_text):
        """
        Evaluates a composite model.

        This method takes a composite model as a string and evaluates
        it. The string is a valid Python expression and can contain
        any valid Python syntax. The method first replaces all model
        names in the string with their corresponding model objects,
        and then evaluates the string using the built-in eval() function.
        If the string is invalid Python syntax, the method raises a
        NeXusError with the error message from the eval() function.

        Parameters
        ----------
        composite_text : str
            The composite model as a string.

        Returns
        -------
        model : lmfit.model.Model
            The evaluated composite model.

        Raises
        ------
        NeXusError
            If the string is invalid Python syntax.
        """
        models = {m['name']: m['model'] for m in self.models}
        text = composite_text
        for m in models:
            text = text.replace(m, f"models['{m}']")
        try:
            return eval(text)
        except Exception as error:
            raise NeXusError(str(error))

    def edit_expression(self):
        """
        Opens a dialog to edit the expression of a parameter.

        This method opens a dialog to edit the expression of a parameter
        when the 'expr' checkbox is checked. The dialog displays the
        current value of the parameter and allows the user to enter a
        mathematical expression. The expression can contain any valid
        Python syntax and can refer to any other parameter in the model
        by name. The dialog is closed when the user clicks the 'OK'
        button or presses Enter. The method then unchecks the 'expr'
        checkbox.
        """
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
        """
        Evaluate the expression of a parameter.

        If the parameter has an expression, this method evaluates it
        using the current values of all the other parameters in the
        model. If the parameter does not have an expression, the
        method simply returns the current value of the parameter.

        Parameters
        ----------
        parameter : Parameter
            The parameter to evaluate.

        Returns
        -------
        value : float
            The value of the parameter.

        Raises
        ------
        NeXusError
            If the expression is invalid Python syntax.
        """
        try:
            if parameter.expr:
                return parameter._expr_eval(parameter.expr)
            else:
                return parameter.value
        except Exception as error:
            report_error(parameter.name, error)

    def read_parameters(self):
        """
        Read the values of all parameters in the model from the GUI.

        This method is called when the user clicks the 'OK' button in the
        model dialog. It reads the values of all parameters in the model
        from the GUI and updates the `value` attribute of each parameter
        object. If a parameter has an expression, this method also evaluates
        the expression using the current values of all the other parameters
        in the model and updates the `value` attribute of the parameter
        object with the result of the evaluation. The method returns a
        list of all the parameter objects in the model.

        Returns
        -------
        parameters : list
            A list of all the parameter objects in the model.
        """
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
        """
        Write the values of all parameters in the model to the GUI.

        This method is called when the user clicks the 'Cancel' button in the
        model dialog. It writes the values of all parameters in the model
        from the parameter objects to the GUI. If a parameter has an expression,
        this method also evaluates the expression using the current values
        of all the other parameters in the model and writes the result of
        the evaluation to the GUI.
        """
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
        """
        Return a NXdata object containing the model data.

        Parameters
        ----------
        model : Model, optional
            The model to evaluate. If not given, the model in the dialog
            is used.
        fit : bool, optional
            If True and the data have been fitted, the fitted parameters
            are used to evaluate the model. If False, the current
            parameters in the dialog are used to evaluate the model. If
            the data have not been fitted, the current parameters in the
            dialog are used to evaluate the model.

        Returns
        -------
        NXdata
            A NXdata object containing the model data.
        """
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
        """
        Return the minimum and maximum values of the x-axis in the plot.

        Returns
        -------
        tuple
            A tuple of two floats, the minimum and maximum values of the
            x-axis.
        """
        return self.plotview.xtab.get_limits()

    @property
    def plot_min(self):
        """Return the minimum value of the x-axis in the plot."""
        return self.get_limits()[0]

    @property
    def plot_max(self):
        """Return the maximum value of the x-axis in the plot."""
        return self.get_limits()[1]

    def plot_data(self):
        """
        Plot the data in the current plotview.

        If the plotview is None, create a new plot of the data in the
        'Fit' plotview. Otherwise, change the color of the data in the
        current plotview to the color of the tab. Remove any other plots
        in the plotview. Set the linestyle cycle to the list of
        linestyles and plot the mask. Finally, raise the plotview to the
        top.
        """
        if self.fitview is None:
            self.fitview = NXPlotView('Fit')
            self.fitview.plot(self._data, fmt='o', color=self.color)
        elif self.fitview.label == 'Fit':
            self.fitview.plot(self._data,
                              xmin=self.plot_min, xmax=self.plot_max,
                              color=self.color)
        else:
            self.fitview.plots[self.data_num]['plot'].set_color(self.color)
        for label in ['label', 'legend_label']:
            self.fitview.plots[self.fitview.num][label] = self.data_label
        self.remove_plots()
        self.linestyle = cycle(self.linestyles)
        self.plot_mask()
        self.fitview.raise_()

    def plot_mask(self):
        """
        Plot the masked data in the current plotview.

        If there is no plotview, create a new plot of the data in the
        'Fit' plotview. Otherwise, remove any previous plots of the
        mask and plot the mask. Set the linestyle cycle to the list of
        linestyles and plot the mask. Finally, raise the plotview to the
        top.
        """
        if self.fitview is None:
            self.plot_data()
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
        """
        Plot the model in the current plotview.

        Parameters
        ----------
        model : bool or Model, optional
            If True, plot the composite model. If False, plot the model
            selected in the model combo box. If a Model object, plot the
            model. If the model is not the composite model, the model is
            plotted with a linestyle cycle of ['-', '--', '-.', ':'] and
            a color cycle of ['C0', 'C1', 'C2', ...]. If the model is the
            composite model and the data have been fitted, the model is
            plotted with a solid line. If the model is the composite model
            and the data have not been fitted, the model is plotted with a
            dashed line. The model is plotted with a legend label that
            includes the name of the tab and the name of the model.
        """
        if self.fitview is None:
            self.plot_data()
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
                model = [m['model']
                         for m in self.models if m['name'] == name][0]
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
        """
        Return the next available number for a plot.

        The next available number is defined as the first number greater
        than the data number that is not already in use as a plot number.
        The range of valid numbers is limited to 100 numbers, starting from
        1 plus 100 times the data number. If all valid numbers are in use,
        the next available number is the minimum of the valid numbers.

        Returns
        -------
        num : int
            The next available number for a plot.
        """
        min_num = self.data_num*100 + 1
        max_num = min_num + 98
        valid_nums = [n for n in self.fitview.plots if min_num <= n <= max_num]
        if valid_nums:
            return max(valid_nums) + 1
        else:
            return min_num

    def fit_data(self):
        """
        Fit the data with the current model and parameters.

        This function reads the current parameters from the GUI, creates
        a Model object, and fits the data using the Model object and the
        current parameters. If the data are weighted, the weights are
        passed to the Model object. If the fit is successful, the fit
        parameters are updated in the GUI and the fit results are
        reported in the GUI. If the fit fails, an error message is
        reported in the GUI.
        """
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
                self.fit_status.setText(
                    'Fit Successful Chi^2 = '
                    f'{format_float(self.fit.result.redchi)}')
            else:
                self.fit_status.setText(
                    'Fit Failed Chi^2 = '
                    f'{format_float(self.fit.result.redchi)}')
            self.parameters = self.fit.params
            self.write_parameters()
            self.set_button_visibility(fitted=True)
            self.fitted = True
        else:
            self.fit_status.setText('Fit failed')

    def report_fit(self):
        """
        Display the results of a fit in a message box.

        This function is used to display the results of a fit in a message box.
        The message box contains a text box that displays the fit results.
        The fit results are formatted as a multi-line string, with each line
        containing a different piece of information about the fit. The
        information includes the fit message, the chi^2 and reduced chi^2, the
        number of function evaluations, the number of variables, the number
        of data points, and the number of degrees of freedom. The fit report
        is also included.
        """
        if self.fit.result.errorbars:
            errors = 'Uncertainties estimated'
        else:
            errors = 'Uncertainties not estimated'
        text = (f'{self.fit.result.message}\n' +
                f'Chi^2 = {self.fit.result.chisqr}\n' +
                f'Reduced Chi^2 = {self.fit.result.redchi}\n' +
                f'{errors}\n' +
                f'No. of Function Evaluations = {self.fit.result.nfev}\n' +
                f'No. of Variables = {self.fit.result.nvarys}\n' +
                f'No. of Data Points = {self.fit.result.ndata}\n' +
                f'No. of Degrees of Freedom = {self.fit.result.nfree}\n' +
                f'{self.fit.fit_report()}')
        message_box = NXMessageBox('Fit Results', text, parent=self)
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        spacer = QtWidgets.QSpacerItem(500, 0,
                                       QtWidgets.QSizePolicy.Minimum,
                                       QtWidgets.QSizePolicy.Expanding)
        layout = message_box.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        message_box.exec()

    def save_fit(self):
        """
        Save the fit results in a NXprocess group.

        If the fit results have not been calculated, a message is posted
        to the status bar and the function returns without doing
        anything else.

        The NXprocess group is built from the data, model, and
        parameters. The model and data are stored in the group as
        datasets, and the parameters are stored as attributes of the
        datasets. The program name and version are stored as attributes
        of the group. The fit statistics are stored as attributes of a
        'statistics' dataset in the group. The fit report is stored as a
        note in the group.

        The group is then written to disk using the write_group method.
        """
        if self.fit is None:
            self.fit_status.setText('Fit not available for saving')
            return
        self.read_parameters()
        group = NXprocess()
        group['model'] = self.composite_model
        group['data'] = self.data
        for m in self.models:
            group[m['name']] = self.get_model(m['model'])
            parameters = NXparameters(attrs={'model': m['class']})
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
        group.note = NXnote(
            self.fit.result.message,
            f'Chi^2 = {self.fit.result.chisqr}\n'
            f'Reduced Chi^2 = {self.fit.result.redchi}\n'
            f'No. of Function Evaluations = {self.fit.result.nfev}\n'
            f'No. of Variables = {self.fit.result.nvarys}\n'
            f'No. of Data Points = {self.fit.result.ndata}\n'
            f'No. of Degrees of Freedom = {self.fit.result.nfree}\n'
            f'{self.fit.fit_report()}')
        self.write_group(group)

    def save_parameters(self):
        """
        Save the fit model in a NXprocess group.

        The group contains the model name, the data, and a 'parameters'
        dataset containing the values of all the model parameters. The
        group is then written to disk using the write_group method.
        """
        self.read_parameters()
        group = NXprocess()
        group['model'] = self.composite_model
        group['data'] = self.data
        for m in self.models:
            group[m['name']] = self.get_model(m['model'])
            parameters = NXparameters(attrs={'model': m['class']})
            for n, p in m['parameters'].items():
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
        """
        Write a group to the scratch file.

        The group is written to the first free number in the scratch file,
        starting from 'f1'. The group name is then displayed in the status
        bar.
        """
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
        """
        Restore the initial parameters of the fit model.

        This method is called when the 'Restore Initial Parameters'
        button is clicked. It resets the parameters to their initial
        values and updates the GUI.
        """
        self.parameters = self.fit.init_params
        self.write_parameters()
        self.fit_status.setText('Waiting to fit...')

    def on_button_release(self, event):
        """
        Handle a mouse button release event in the plot window.

        If the left button is released, remove any rectangle that was
        drawn. If the right button is released and a zoom is in
        progress, draw a rectangle with the zoom extent and make the
        mask button visible. In either case, the plot window is redrawn.
        """
        if self.fitview is None:
            return
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
        """
        Draw a rectangle in the plot window based on the zoom extent.

        This method is called when the right button is released in the
        plot window and a zoom is in progress. It sets the x and y
        coordinates of the rectangle to the zoom extent and makes the
        mask button visible. The plot window is then redrawn.
        """
        if self.fitview is None:
            return
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
        """
        Remove any rectangle that was drawn in the plot window.

        This method is called when the left button is released in the
        plot window. It removes any rectangle that was drawn and
        redraws the plot window.
        """
        if self.fitview is None:
            return
        if self.rectangle:
            self.rectangle.remove()
        self.rectangle = None
        self.fitview.draw()

    def remove_masks(self):
        """
        Remove the mask plot from the plot window.

        This method is called when the 'Clear Masks' button is clicked.
        It removes the mask plot from the plot window and redraws the
        plot window.
        """
        if self.fitview is None:
            return
        if self.mask_num in self.fitview.plots:
            self.fitview.plots[self.mask_num]['plot'].remove()
            del self.fitview.plots[self.mask_num]
            self.fitview.ytab.plotcombo.remove(self.mask_num)
        self.remove_rectangle()

    def remove_plots(self):
        """
        Remove any additional plots from the plot window.

        This method is called when the 'Fit Data' button is clicked.
        It removes any additional plots from the plot window and
        redraws the plot window.
        """
        if self.fitview is None:
            return
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
        """
        Remove any additional plots from the plot window and replace
        them with a line plot of the fitted model. This method is called
        when the 'Apply' button is clicked. The plot window is then
        redrawn.
        """
        if self.fitview is None:
            return
        self.remove_plots()
        if self.model is not None:
            self.fitview.plot(self.get_model(), fmt='-', color=self.color,
                              over=True)

    def close(self):
        """
        Close this dialog and disconnect any signal connections.

        This method is called when the window is closed. It disconnects any
        signal connections and removes any masks and plots from the plot window.
        """
        if self.fitview is None:
            return
        self.fitview.canvas.mpl_disconnect(self.cid)
        self.remove_masks()
        self.remove_plots()


class CompositeDialog(NXDialog):

    def __init__(self, parent=None):

        """
        Initialize the dialog to edit a composite model.

        This dialog is initialized with the given parent and the
        composite model expression in the parent. The dialog contains
        a line edit box with the expression, a button to insert a model
        name, a combo box with the names of the models, and buttons to
        close the dialog. The dialog title is "Editing Composite Model".

        Parameters
        ----------
        parent : NXDialog
            The parent of the dialog.
        """
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
        """
        Insert the selected model name into the expression box.

        This method is called when the user clicks the "Insert Model"
        button. It inserts the selected model name into the expression
        box at the current position of the text cursor.
        """
        self.expression.insert(self.model_combo.selected)

    def accept(self):
        """
        Accept the edited composite model expression.

        This method is called when the user clicks the "OK" button.
        It evaluates the expression in the expression box and
        assigns it to the model attribute of the parent. If the
        expression is invalid Python syntax, it raises a NeXusError
        with the error message from the eval() function.
        """
        try:
            self.parent.model = self.parent.eval_model(self.expression.text())
            self.parent.composite_model = self.expression.text()
            super().accept()
        except NeXusError as error:
            report_error("Editing Composite Model", error)


class PlotModelDialog(NXDialog):

    def __init__(self, parent=None):

        """
        Initialize the dialog to plot a composite model.

        Parameters
        ----------
        parent : NXDialog
            The parent of the dialog.

        The dialog contains a line edit box with the current composite
        model expression, a button to plot the model, and buttons to
        close the dialog. The dialog title is "Plotting Composite Model".
        """
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
        """
        Plot the composite model with the current expression.

        This method is called when the user clicks the "Plot Model"
        button. It evaluates the expression in the expression box and
        passes the result to the plot_model method of the parent. If the
        expression is invalid Python syntax, it raises a NeXusError
        with the error message from the eval() function.
        """
        try:
            model = self.parent.eval_model(self.expression.text())
            self.parent.plot_model(model)
            super().accept()
        except NeXusError as error:
            report_error("Plotting Composite Model", error)


class ExpressionDialog(NXDialog):

    def __init__(self, parameter, parent=None):

        """
        Initialize the dialog to edit a parameter expression.

        The dialog is initialized with the given parameter and parent.
        The dialog contains a line edit box with the expression of the
        given parameter, a button to insert a parameter, a combo box
        with the parameter names, and buttons to close the dialog.
        The dialog title is in the form "Editing 'parameter_name' Expression".

        Parameters
        ----------
        parameter : NXParameter
            The parameter to be edited.
        parent : NXDialog, optional
            The parent of the dialog. The default is None.
        """
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
        """
        Insert the selected parameter name into the expression box.

        This method is called when the user clicks the "Insert Parameter"
        button. It inserts the selected parameter name into the expression
        box at the current position of the text cursor.
        """
        self.expression.insert(self.parameter_combo.selected)

    def accept(self):
        """
        Accept the edited expression.

        This method is called when the user clicks the 'OK' button.
        It updates the parameter expression and evaluates the expression
        if it is not empty. If the expression is invalid Python syntax,
        it raises a NeXusError with the error message from the eval()
        function. The method calls the read_parameters() method of the
        parent to update the GUI and calls the accept() method of the
        parent to close the dialog.
        """
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
