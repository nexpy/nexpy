# -*- coding: utf-8 -*-
"""
Plotting modules.

This module contains the NXPlotView class, which defines plotting
windows and their associated tabs for modifying the axis limits and 
plotting options. 

Attributes
----------
plotview: NXPlotView
    The currently active NXPlotView window
plotviews: dictionary
    A dictionary containing all the existing NXPlotView windows. The
    keys are defined by the 
    
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

from .pyqt import QtCore, QtGui, QtWidgets, QtVersion

import numbers
import numpy as np
import os
import pkg_resources

import matplotlib as mpl
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import FigureManagerBase
if QtVersion == 'Qt5Agg':
    from matplotlib.backends.backend_qt5 import FigureManagerQT as FigureManager
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
else:
    from matplotlib.backends.backend_qt4 import FigureManagerQT as FigureManager
    from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backends.qt_editor.formlayout import ColorButton, to_qcolor
from matplotlib.figure import Figure
from matplotlib.image import NonUniformImage
from matplotlib.colors import LogNorm, Normalize, SymLogNorm
from matplotlib.colors import colorConverter, rgb2hex
from matplotlib.cm import cmap_d, get_cmap
from matplotlib.lines import Line2D
from matplotlib import markers
from matplotlib.patches import Circle, Ellipse, Rectangle, Polygon
from matplotlib.ticker import AutoLocator, LogLocator, ScalarFormatter
try:
    from matplotlib.ticker import LogFormatterSciNotation as LogFormatter
except ImportError:
    from matplotlib.ticker import LogFormatter
from matplotlib.transforms import nonsingular
from mpl_toolkits.axisartist.grid_helper_curvelinear import GridHelperCurveLinear
from mpl_toolkits.axisartist import Subplot
from mpl_toolkits.axisartist.grid_finder import MaxNLocator

from nexusformat.nexus import NXfield, NXdata, NXroot, NeXusError, nxload

from .. import __version__
from .datadialogs import BaseDialog, GridParameters
from .utils import report_error, find_nearest

plotview = None
plotviews = {}
colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']
cmaps = ['viridis', 'inferno', 'magma', 'plasma', #perceptually uniform
         'spring', 'summer', 'autumn', 'winter', 'cool', 'hot', #sequential
         'bone', 'copper', 'gray', 'pink', 
         'jet', 'spectral', 'rainbow', 'hsv', #miscellaneous
         'seismic', 'coolwarm', 'RdBu', 'RdYlBu', 'RdYlGn'] #diverging
cmaps = [cm for cm in cmaps if cm in cmap_d]
if 'viridis' in cmaps:
    default_cmap = 'viridis'
else:
    default_cmap = 'jet'
interpolations = ['nearest', 'bilinear', 'bicubic', 'spline16', 'spline36',
                  'hanning', 'hamming', 'hermite', 'kaiser', 'quadric',
                  'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos']
try:
    from astropy.convolution import convolve, Gaussian2DKernel
    interpolations.insert(1, 'convolve')
except ImportError:
    pass
linestyles = {'-': 'Solid', '--': 'Dashed', '-.': 'DashDot', ':': 'Dotted',
              'None': 'None'}
markers = markers.MarkerStyle.markers
logo = mpl.image.imread(pkg_resources.resource_filename(
           'nexpy.gui', 'resources/icon/NeXpy.png'))[180:880,50:1010]


def new_figure_manager(label=None, *args, **kwargs):
    """Create a new figure manager instance.

    A new figure number is generated. with numbers > 100 preserved for 
    the Projection and Fit windows.

    Parameters
    ----------
    label: str
        The label used to define 
    """
    import matplotlib.pyplot as plt
    if label is None:
        label = ''
    if label == 'Projection' or label == 'Fit':
        nums = [num for num in plt.get_fignums() if num > 100]
        if nums:
            num = max(nums) + 1
        else:
            num = 101
    else:
        nums = [num for num in plt.get_fignums() if num < 100]
        if nums:
            missing_nums = sorted(set(range(nums[0], nums[-1]+1)).difference(nums))
            if missing_nums:
                num = missing_nums[0]
            else:
                num = max(nums) + 1
        else:
            num = 1
    thisFig = Figure(*args, **kwargs)
    canvas = NXCanvas(thisFig)
    manager = NXFigureManager(canvas, num)
    return manager


def change_plotview(label):
    """Change the current active plotting window.
    
    Parameters
    ----------
    label: str
        The label of the plotting window to be activatd.
    """
    global plotview, plotviews
    if label in plotviews:
        if plotviews[label].number < 101:
            plotviews[label].make_active()
            plotview = plotviews[label]
    else:
        plotview = NXPlotView(label)
    return plotview


def get_plotview():
    """Return the currently active plotting window."""
    global plotview
    return plotview


class NXCanvas(FigureCanvas):
    """Subclass of Matplotlib's FigureCanvas."""
    def __init__(self, figure):

        FigureCanvas.__init__(self, figure)

        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                           QtWidgets.QSizePolicy.MinimumExpanding)


class NXFigureManager(FigureManager):
    """Subclass of Matplotlib's FigureManager."""
    def __init__(self, canvas, num):
        FigureManagerBase.__init__(self, canvas, num)
        self._status_and_tool_height = 0
        def notify_axes_change(fig):
            # This will be called whenever the current axes is changed
            if self.canvas.toolbar is not None:
                self.canvas.toolbar.update()
        self.canvas.figure.add_axobserver(notify_axes_change)
    
    def resize(self, width, height):
        extra_width = self.window.width() - self.canvas.width()
        extra_height = self.window.height() - self.canvas.height()
        self.window.resize(width+extra_width, height+extra_height)


class NXPlotView(QtWidgets.QDialog):
    """QT widget containing a NeXpy plot.

    The widget consists of a QVBoxLayout containing a matplotlib canvas 
    over a tab widget, which contains NXPlotTab objects for adjusting 
    plot axes.

    Parameters
    ----------
    label: str
        The label used to identify this NXPlotView instance. It can be
        used as the key to select an instance in the 'plotviews' 
        dictionary.
    parent: QWidget
        The parent widget of this window. This needs to be set to 
        the applications QMainWindow if the window is to inherit the 
        application's main menu. If the parameter is not given, it is
        set to the main window defined in the 'consoleapp' module.

    Attributes
    ----------
    label: str
        The label used to identify this NXPlotView instance. It can be
        used as the key to select an instance in the 'plotviews' 
        dictionary.
    number: int
        The number used by Matplotlib to identify the plot. Numbers 
        greater than 100 are reserved for the Projection and Fit plots.
    data: NXdata
        Original NXdata group to be plotted.
    plotdata: NXdata
        Plotted data. If 'data' has more than two dimensions, this 
        contains the 2D slice that is currently plotted.
    signal: NXfield
        Array containing the plotted signal values.
    axes: list
        List of NXfields containing the plotted axes.
    image:
        Matplotlib image instance. Set to None for 1D plots.
    colorbar:
        Matplotlib color bar.
    rgb_image: bool
        True if the image contains RGB layers.
    vtab: NXPlotTab
        Signal (color) axis for 2D plots.
    xtab: NXPlotTab
        x-axis (horizontal) tab.
    ytab: NXPlotTab
        y-axis (vertical) tab; this is the intensity axis for 1D plots.
    ztab: NXPlotTab
        Tab to define plotting limits for non-plotted dimensions in 
        three- or higher dimensional plots.
    ptab: NXPlotTab
        Tab for defining projections.
    otab: NXPlotTab
        Matplotlib buttons for adjusting plot markers and labels, 
        zooming, and saving plots in files.
    vaxis: NXPlotAxis
        Signal (color) axis values and limits.
    xaxis: NXPlotAxis
        x-axis values and limits.
    yaxis: NXPlotAxis
        y-axis values and limits.
    zaxis: NXPlotAxis
        Currently selected zaxis. For higher-dimensional data, this is
        the dimension selected in the ztab.
    axis: dictionary
        A dictionary of NXPlotAxis instances. The keys are 'signal' or
        an integer: 0 for the currently selected z-axis, 1 for the 
        y-axis, and 2 for the x-axis.
    """
    def __init__(self, label=None, parent=None):

        if parent is not None:
            self.mainwindow = parent
        else:
            from .consoleapp import _mainwindow
            self.mainwindow = _mainwindow
            parent = self.mainwindow

        super(NXPlotView, self).__init__(parent)

        self.setMinimumSize(724, 550)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                           QtWidgets.QSizePolicy.MinimumExpanding)

        global plotview, plotviews
        if label in plotviews:
            plotviews[label].close()

        self.figuremanager = new_figure_manager(label)
        self.number = self.figuremanager.num
        self.canvas = self.figuremanager.canvas
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)

        Gcf.set_active(self.figuremanager)
        def make_active(event):
            if self.number < 101:
                self.make_active()
            self.xdata, self.ydata = self.inverse_transform(event.xdata,
                                                            event.ydata)
            if event.button == 3:
                try:
                    self.otab.home(autoscale=False)
                except Exception:
                    pass
        cid = self.canvas.mpl_connect('button_press_event', make_active)
        self.canvas.figure.show = lambda *args: self.show()
        self.figuremanager._cidgcf = cid
        self.figuremanager.window = self
        self._destroying = False
        self.figure = self.canvas.figure
        if label:
            self.label = label
            self.figure.set_label(self.label)
        else:
            self.label = "Figure %d" % self.number

        self.canvas.setMinimumWidth(700)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setFixedHeight(80)
        self.tab_widget.setMinimumWidth(700)

        self.vtab = NXPlotTab('v', axis=False, image=True, plotview=self)
        self.xtab = NXPlotTab('x', plotview=self)
        self.ytab = NXPlotTab('y', plotview=self)
        self.ztab = NXPlotTab('z', log=False, zaxis=True, plotview=self)
        self.ptab = NXProjectionTab(plotview=self)
        self.otab = NXNavigationToolbar(self.canvas, self.tab_widget)
        self.figuremanager.toolbar = self.otab
        self.tab_widget.addTab(self.xtab, 'x')
        self.tab_widget.addTab(self.ytab, 'y')
        self.tab_widget.addTab(self.otab, 'options')
        self.currentTab = self.otab
        self.tab_widget.setCurrentWidget(self.currentTab)

        self.vbox = QtWidgets.QVBoxLayout()
        self.vbox.setContentsMargins(12, 12, 12, 12)
        self.vbox.addWidget(self.canvas)
        self.vbox.addWidget(self.tab_widget)
        self.setLayout(self.vbox)

        self.setWindowTitle(self.label)
        
        self.resize(734, 550)

        self.num = 0
        self.axis = {}
        self.xaxis = self.yaxis = self.zaxis = None
        self.xmin = self.xmax = self.ymin = self.ymax = self.vmin = self.vmax = None

        self.image = None
        self.colorbar = None
        self.zoom = None
        self.rgb_image = False
        self._aspect = 'auto'
        self._skew_angle = None
        self._grid = False
        self._gridcolor = mpl.rcParams['grid.color']
        self._gridstyle = mpl.rcParams['grid.linestyle']
        self._linthresh = None
        self._linscale = None
        self._stddev = 2.0

        if self.number < 101:
            plotview = self
        plotviews[self.label] = self
        self.plotviews = plotviews

        self.projection_panel = None
        self.customize_panel = None

        if self.label != "Main":
            self.add_menu_action()
            self.show()

        self.display_logo()

    def __repr__(self):
        return 'NXPlotView("%s")' % self.label

    def display_logo(self):
        self.plot(NXdata(logo, title='NeXpy'), image=True)
        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
        self.ax.title.set_visible(False)
        self.draw()

    def make_active(self):
        """Make this window active for plotting."""
        global plotview
        if self.number < 101:
            plotview = self
            self.mainwindow.user_ns['plotview'] = self
        Gcf.set_active(self.figuremanager)
        self.show()
        if self.label == 'Main':
            self.mainwindow.raise_()
        else:
            self.raise_()
        self.update_active()

    def update_active(self):
        """Update the active window in 'Window' menu.""" 
        if self.number < 101:
            self.mainwindow.update_active(self.number)

    def add_menu_action(self):
        """Add this window to the 'Window' menu."""
        if self.label not in self.mainwindow.active_action:
            self.mainwindow.make_active_action(self.number, self.label)
        self.mainwindow.update_active(self.number)

    def remove_menu_action(self):
        """Remove this window from the 'Window' menu."""
        if self.number in self.mainwindow.active_action:
            self.mainwindow.window_menu.removeAction(
                self.mainwindow.active_action[self.number])
            del self.mainwindow.active_action[self.number]
        if self.number == self.mainwindow.previous_active:
            self.mainwindow.previous_active = 1
        self.mainwindow.make_active(self.mainwindow.previous_active)

    def save_plot(self):
        """Open a dialog box for saving the plot as a PNG file"""
        file_choices = "PNG (*.png)|*.png"
        path = six.text_type(QtWidgets.QFileDialog.getSaveFileName(self,
                             'Save file', '', file_choices))
        if path:
            self.canvas.print_figure(path, dpi=self.dpi)
            self.statusBar().showMessage('Saved to %s' % path, 2000)

    def plot(self, data, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             vmin=None, vmax=None, **opts):
        """Plot an NXdata group with optional limits.

        Parameters
        ----------
        data : NXdata
            This is the NXdata object that contains the signal and 
            associated axes.
        fmt : string
            The format argument is used to set the color and type of the 
            markers or lines for 1D plots, using the standard matplotlib 
            syntax. The default is set to blue circles. All keyword 
            arguments accepted by matplotlib.pyplot.plot can be used to 
            customize the plot.
        xmin, xmax, ymin, ymax, vmin, vmax : float
            Axis and signal limits. These parameters are optional 
            keyword arguments in the NXgroup plot method; if not 
            specified, they are set to None.
        opts : dict
            This dictionary can contain any valid matplotlib options as
            well as other keyword arguments specified below.
        over: bool
            If True, 1D data is plotted over the existing plot.
        image: bool
            If True, the data are plotted as an RGB image.
        log: bool
            If True, the signal is plotted on a log scale.
        logx: bool
            If True, the x-axis is plotted on a log scale.
        logy: bool
            If True, the y-axis is plotted on a log scale. This is 
            equivalent to 'log=True' for one-dimenional data.
        skew:
            The value of the skew angle between the x and y axes for 2D 
            plots.
        """
        mpl.interactive(False)

        over = opts.pop("over", False)
        image = opts.pop("image", False)
        log = opts.pop("log", False)
        logx = opts.pop("logx", False)
        logy = opts.pop("logy", False)
        cmap = opts.pop("cmap", None)
        self._aspect = opts.pop("aspect", "auto")
        self._skew_angle = opts.pop("skew", None)

        self.data = data
        if not over:
            self.title = data.nxtitle

        if self.data.nxsignal is None:
            raise NeXusError('No plotting signal defined')

        if image:
            self.rgb_image = True
        else:
            self.rgb_image = False

        self.plotdata = self.get_plotdata(over)

        #One-dimensional Plot
        if self.ndim == 1:
            if over:
                self.num = self.num + 1
            else:
                self.num = 0
                if xmin:
                    self.xaxis.lo = xmin
                if xmax:
                    self.xaxis.hi = xmax
                if ymin:
                    self.yaxis.lo = ymin
                if ymax:
                    self.yaxis.hi = ymax
                if logx:
                    self.xtab.logbox.setChecked(True)
                else:
                    self.xtab.logbox.setChecked(False)
                if log or logy:
                    self.ytab.logbox.setChecked(True)
                else:
                    self.ytab.logbox.setChecked(False)
            if fmt == '':
                fmt = colors[self.num%len(colors)] + 'o'

            self.x, self.y, self.e = self.get_points()
            self.plot_points(fmt, over, **opts)

        #Higher-dimensional plot
        else:
            if xmin:
                self.xaxis.lo = xmin
            else:
                self.xaxis.lo = self.xaxis.min
            if xmax:
                self.xaxis.hi = xmax
            else:
                self.xaxis.hi = self.xaxis.max
            if ymin:
                self.yaxis.lo = ymin
            else:
                self.yaxis.lo = self.yaxis.min
            if ymax:
                self.yaxis.hi = ymax
            else:
                self.yaxis.hi = self.yaxis.max
            if vmin:
                self.vaxis.lo = vmin
            if vmax:
                self.vaxis.hi = vmax
            if log:
                self.vtab.logbox.setChecked(True)
            else:
                self.vtab.logbox.setChecked(False)

            self.x, self.y, self.v = self.get_image()
            self.plot_image(over, **opts)

        self.limits = (self.xaxis.min, self.xaxis.max,
                       self.yaxis.min, self.yaxis.max)

        if over:
            self.update_tabs()
        else:
            self.init_tabs()

        if self.rgb_image:
            self.ytab.flipped = True
            self.replot_axes(draw=False)
            if self.aspect == 'auto':
                self.aspect = 'equal'
        elif self.xaxis.reversed or self.yaxis.reversed:
            self.replot_axes(draw=False)

        self.offsets = False
        self.aspect = self._aspect

        self.draw()
        self.otab.push_current()
        mpl.interactive(True)

    def get_plotdata(self, over=False):
        """Return an NXdata group containing the plottable data.

        This function removes size 1 arrays, creates axes if none are 
        specified and initializes the NXPlotAxis instances.
        
        Parameters
        ----------
        over: bool
            If True, the signal and axes values are updated without
            creating a new NXPlotAxis instance.
        """
        if self.data.plot_axes is not None:
            axes = self.data.plot_axes
        else:
            axes = [NXfield(np.arange(self.shape[i]), name='Axis%s'%i)
                            for i in range(self.ndim)]

        self.axes = [NXfield(axes[i].nxdata, name=axes[i].nxname,
                     attrs=axes[i].safe_attrs) for i in range(self.ndim)]

        if self.ndim > 2:
            idx=[np.s_[0] if s==1 else np.s_[:] for s in self.data.nxsignal.shape]
            for i in range(len(idx)):
                if idx.count(slice(None,None,None)) > 2:
                    try:
                        idx[i] = self.axes[i].index(0.0)
                    except Exception:
                        idx[i] = 0
            self.signal = self.data.nxsignal[tuple(idx)][()]
        elif self.rgb_image:
            self.signal = self.data.nxsignal[()]
        else:
            self.signal = self.data.nxsignal[()].reshape(self.shape)

        if over:
            self.axis['signal'].set_data(self.signal)
        else:
            self.axis = {}
            self.axis['signal'] = NXPlotAxis(self.signal)

        for i in range(self.ndim):
            if over:
                self.axis[i].set_data(self.axes[i], self.shape[i])
            else:
                self.axis[i] = NXPlotAxis(self.axes[i], i, self.shape[i])

        if self.ndim == 1:
            self.xaxis = self.axis[0]
            self.yaxis = self.axis['signal']
            if self.data.nxerrors and self.data.nxerrors != self.data.nxsignal:
                self.errors = self.data.nxerrors
            else:
                self.errors = None
            plotdata = NXdata(self.signal, self.axes[0], self.errors)
        else:
            self.xaxis = self.axis[self.ndim-1]
            self.yaxis = self.axis[self.ndim-2]
            if self.ndim > 2:
                for i in range(self.ndim-2):
                    self.axis[i].lo = self.axis[i].hi \
                        = np.float(self.axis[i].data[idx[i]])
                self.zaxis = self.axis[self.ndim - 3]
                self.zaxis.lo = self.zaxis.hi = self.axis[self.ndim - 3].lo
            else:
                self.zaxis = None
            self.vaxis = self.axis['signal']
            plotdata = NXdata(self.signal, [self.axes[i] for i in [-2,-1]])

        plotdata['title'] = self.data.nxtitle

        return plotdata

    def get_points(self):
        """Initialize the x, y, and e values for plotting 1D data.

        Returns
        -------
        x: ndarray
            Plotted x-values. For 1D data stored in histograms, these 
            are defined by the histogram centers.
        y: ndarray
            Plotted y-values, i.e., the signal array.
        e: ndarray
            Plotted error bars if 'plotdata' contains an error array.
        """
        x = self.xaxis.centers
        y = self.yaxis.data
        if self.errors:
            e = self.errors.nxdata
        else:
            e = None
        return x, y, e

    def plot_points(self, fmt, over=False, **opts):
        """Plot one-dimensional data.
        
        Parameters
        ----------
        fmt: str
            The format argument is used to set the color and type of the 
            markers or lines for 1D plots, using the standard matplotlib 
            syntax. The default is set to blue circles. All keyword 
            arguments accepted by matplotlib.pyplot.plot can be used to 
            customize the plot.
        over: bool
            If True, the figure is not cleared and the axes are not
            adjusted. However, the extremal axis values are changed, 
            and the entire range covering all the overplotted data is
            shown by, e.g., by clicking on the 'Home' button or 
            right-clicking on the plot.
        opts: dictionary
            A dictionary containing Matplotlib options.
        """
        if not over:
            self.figure.clf()
        ax = self.figure.gca()

        if self.e is not None:
            ax.errorbar(self.x, self.y, self.e, fmt=fmt, **opts)
        else:
            ax.plot(self.x, self.y, fmt,  **opts)

        path = self.data.nxsignal.nxpath
        if self.data.nxroot.nxclass == "NXroot":
            path = self.data.nxroot.nxname + path
        ax.lines[-1].set_label(path)

        if over:
            self.xaxis.min = min(self.xaxis.lo, self.x.min())
            self.xaxis.max = max(self.xaxis.hi, self.x.max())
            _range = self.xaxis.max - self.xaxis.min
            if self.xaxis.min < self.xaxis.lo:
                self.xaxis.min = self.xaxis.min - 0.05*_range
            if self.xaxis.max > self.xaxis.hi:
                self.xaxis.max = self.xaxis.max + 0.05*_range
            ax.set_xlim(self.xaxis.lo, self.xaxis.hi)
            self.yaxis.min = min(self.yaxis.lo, self.y.min())
            self.yaxis.max = max(self.yaxis.hi, self.y.max())
        else:
            xlo, xhi = ax.set_xlim(auto=True)
            ylo, yhi = ax.set_ylim(auto=True)

            if self.xaxis.lo:
                ax.set_xlim(xmin=self.xaxis.lo)
            else:
                self.xaxis.lo = xlo
            if self.xaxis.hi:
                ax.set_xlim(xmax=self.xaxis.hi)
            else:
                self.xaxis.hi = xhi
            if self.yaxis.lo:
                ax.set_ylim(ymin=self.yaxis.lo)
            else:
                self.yaxis.lo = ylo
            if self.yaxis.hi:
                ax.set_ylim(ymax=self.yaxis.hi)
            else:
                self.yaxis.hi = yhi
            if self.xtab.logbox.isChecked():
                ax.set_xscale('log')
            if self.ytab.logbox.isChecked():
                ax.set_yscale('log')
            ax.set_xlabel(self.xaxis.label)
            ax.set_ylabel(self.yaxis.label)
            ax.set_title(self.title)

            self.xaxis.min, self.xaxis.max = ax.get_xlim()
            self.yaxis.min, self.yaxis.max = ax.get_ylim()
            self.xaxis.lo, self.xaxis.hi = self.xaxis.min, self.xaxis.max
            self.yaxis.lo, self.yaxis.hi = self.yaxis.min, self.yaxis.max

        self.image = None
        self.colorbar = None

    def get_image(self):
        """Initialize the plot's signal and axis values.

        Returns
        -------
        x: ndarray
            Plotted x-values. These are defined by the bin boundaries.
        y: ndarray
            Plotted y-values. These are defined by the bin boundaries.
        v: ndarray
            Plotted signal array. If 'interpolation' is set to 
            'convolve', the array is convolved with a Gaussian whose 
            pixel width is defined by the 'smooth' property (default 2).
        """
        x = self.xaxis.boundaries
        y = self.yaxis.boundaries
        v = self.plotdata.nxsignal.nxdata
        if self.interpolation == 'convolve':
            return x, y, convolve(v, Gaussian2DKernel(self.smooth))
        else:
            return x, y, v

    def plot_image(self, over=False, **opts):
        """Plot a two-dimensional plot.

        Parameters
        ----------
        over: bool
            Not currently used.
        opts: dictionary
            A dictionary containing Matplotlib options.
        """
        self.set_data_limits()
        self.set_data_norm()

        self.figure.clf()
        if self.skew:
            ax = self.figure.add_subplot(Subplot(self.figure, 1, 1, 1, 
                                         grid_helper=self.grid_helper()))
        else:
            ax = self.figure.add_subplot(1, 1, 1)
        ax.autoscale(enable=True)

        if self.xaxis.reversed:
            left, right = self.xaxis.max_data, self.xaxis.min_data
        else:
            left, right = self.xaxis.min_data, self.xaxis.max_data
        if self.yaxis.reversed:
            bottom, top = self.yaxis.max_data, self.yaxis.min_data
        else:
            bottom, top = self.yaxis.min_data, self.yaxis.max_data
        extent = (left, right, bottom, top)

        if self.regular_grid:
            if self.interpolation == 'convolve':
                opts['interpolation'] = 'bicubic'
            else:
                opts['interpolation'] = self.interpolation

        if self.rgb_image or self.regular_grid:
            opts['origin'] = 'lower'
            self.image = ax.imshow(self.v, extent=extent, cmap=self.cmap,
                                   norm=self.norm, **opts)
        else:
            if self.skew is not None:
                xx, yy = np.meshgrid(self.x, self.y)
                x, y = self.transform(xx, yy)
            else:
                x, y = self.x, self.y
            self.image = ax.pcolormesh(x, y, self.v, cmap=self.cmap, **opts)
            self.image.set_norm(self.norm)
        self.image.get_cmap().set_bad('k', 1.0)
        ax.set_aspect(self.aspect)

        if not self.rgb_image:
            self.colorbar = self.figure.colorbar(self.image, ax=ax,
                                                 norm=plotview.norm)
            self.colorbar.locator = self.locator
            self.colorbar.formatter = self.formatter
            self.colorbar.update_normal(self.image)

        xlo, ylo = self.transform(self.xaxis.lo, self.yaxis.lo)
        xhi, yhi = self.transform(self.xaxis.hi, self.yaxis.hi)

        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)

        if self._grid:
            ax.grid(self._grid, color=self._gridcolor, linestyle=self._gridstyle)

        ax.set_xlabel(self.xaxis.label)
        ax.set_ylabel(self.yaxis.label)
        ax.set_title(self.title)

        vmin, vmax = self.image.get_clim()
        if self.vaxis.min > vmin:
            self.vaxis.min = vmin
        if self.vaxis.max < vmax:
            self.vaxis.max = vmax

        self.vtab.set_axis(self.vaxis)

    @property
    def shape(self):
        """Shape of the original NXdata signal array.
        
        This removes any dimension of size 1. Also, a dimension is 
        removed if the data contain RGB layers.
        
        Returns
        -------
        shape: tuple
            Tuple of dimension sizes.
        """
        _shape = list(self.data.nxsignal.shape)
        while 1 in _shape:
            _shape.remove(1)
        if self.rgb_image:
            _shape = _shape[:-1]
        return tuple(_shape)

    @property
    def ndim(self):
        """Number of dimensions of the original NXdata signal."""
        return len(self.shape)

    @property
    def finite_v(self):
        """Plotted signal array excluding NaNs and infinities."""
        return self.v[np.isfinite(self.v)]

    def set_data_limits(self):
        """Set the vaxis data and limits for 2D plots."""
        self.vaxis.data = self.v
        if self.vaxis.hi is None or self.autoscale:
            try:
                self.vaxis.hi = self.vaxis.max = np.max(self.finite_v)
            except:
                self.vaxis.hi = self.vaxis.max = 0.1
        if self.vtab.symmetric:
            self.vaxis.lo = -self.vaxis.hi
            self.vaxis.min = -self.vaxis.max
        elif self.vaxis.lo is None or self.autoscale:
            try:
                self.vaxis.lo = self.vaxis.min = np.min(self.finite_v)
            except:
                self.vaxis.lo = self.vaxis.min = 0.0
        if self.vtab.logbox.isChecked() and not self.vtab.symmetric:
            try:
                self.vaxis.lo = max(self.vaxis.lo, 
                                    self.finite_v[self.finite_v>0.0].min())
            except ValueError:
                self.vaxis.lo, self.vaxis.hi = (0.01, 0.1)
        self.vtab.set_axis(self.vaxis)

    def set_data_norm(self):
        """Set the normalization for 2D plots."""
        if self.vtab.logbox.isChecked():
            if self.vtab.symmetric:
                if self._linthresh:
                    linthresh = self._linthresh
                else:
                    linthresh = self.vaxis.hi / 10.0
                if self._linscale:
                    linscale = self._linscale
                else:
                    linscale = 0.1
                self.norm = NXSymLogNorm(linthresh, linscale=linscale,
                                         vmin=self.vaxis.lo, 
                                         vmax=self.vaxis.hi)
                self.locator = AutoLocator()
                self.formatter = ScalarFormatter()
            else:
                self.norm = LogNorm(self.vaxis.lo, self.vaxis.hi)
                self.locator = LogLocator()
                self.formatter = LogFormatter()
        else:
            self.norm = Normalize(self.vaxis.lo, self.vaxis.hi)
            self.locator = AutoLocator()
            self.formatter = ScalarFormatter()

    def replot_data(self, newaxis=False):
        """Replot the data with new axes if necessary.
        
        This is required when new axes are selected in tabs, z-axis 
        values are changed, the skew angle is changed, or signal values 
        are changed, e.g., by adding masks.

        Parameters
        ----------
        newaxis: bool
            If True, a new set of axes is drawn by calling plot_image.
        """
        axes = [self.yaxis.dim, self.xaxis.dim]
        limits = []
        xmin, xmax, ymin, ymax = [np.float(value) for value in self.limits]
        for i in range(self.ndim):
            if i in axes:
                if i == self.xaxis.dim:
                    limits.append((xmin, xmax))
                else:
                    limits.append((ymin, ymax))
            else:
                limits.append((np.float(self.axis[i].lo), 
                               np.float(self.axis[i].hi)))
        if self.data.nxsignal.shape != self.data.plot_shape:
            axes, limits = fix_projection(self.data.nxsignal.shape, axes, limits)
        self.plotdata = self.data.project(axes, limits, summed=self.summed)
        self.plotdata.title = self.title
        self.x, self.y, self.v = self.get_image()
        if newaxis:
            self.plot_image()
            self.draw()
        elif self.regular_grid:
            self.image.set_data(self.v)
            if self.xaxis.reversed:
                xmin, xmax = xmax, xmin
            if self.yaxis.reversed:
                ymin, ymax = ymax, ymin
            self.image.set_extent((xmin, xmax, ymin, ymax))
            self.replot_image()
        else:
            self.image.set_array(self.v.ravel())
            self.replot_image()
        self.grid(display=self._grid)

    def replot_image(self):
        """Replot the image with new signal limits."""
        try:
            self.set_data_limits()
            self.set_data_norm()
            self.colorbar.locator = self.locator
            self.colorbar.formatter = self.formatter
            self.colorbar.set_norm(self.norm)
            self.image.set_norm(self.norm)
            self.colorbar.update_normal(self.image)
            self.image.set_clim(self.vaxis.lo, self.vaxis.hi)
            if self.regular_grid:
                if self.interpolation == 'convolve':
                    self.image.set_interpolation('bicubic')
                else:
                    self.image.set_interpolation(self.interpolation)
            self.replot_axes()
        except Exception as error:
            pass

    def replot_axes(self, draw=True):
        """Adjust the x and y axis limits in the plot."""
        ax = self.figure.gca()
        xmin, xmax = self.xaxis.get_limits()
        ymin, ymax = self.yaxis.get_limits()
        xmin, ymin = self.transform(xmin, ymin)
        xmax, ymax = self.transform(xmax, ymax)
        if ((self.xaxis.reversed and not self.xtab.flipped) or
            (not self.xaxis.reversed and self.xtab.flipped)):
            ax.set_xlim(xmax, xmin)
        else:
            ax.set_xlim(xmin, xmax)
        if ((self.yaxis.reversed and not self.ytab.flipped) or
            (not self.yaxis.reversed and self.ytab.flipped)):
            ax.set_ylim(ymax, ymin)
        else:
            ax.set_ylim(ymin, ymax)
        ax.set_xlabel(self.xaxis.label)
        ax.set_ylabel(self.yaxis.label)
        self.otab.push_current()
        if draw:
            self.draw()

    def grid_helper(self):
        """Define the locator used in skew transforms."""
        locator = MaxNLocator(nbins=9, steps=[1, 2, 5, 10])
        return GridHelperCurveLinear((self.transform, self.inverse_transform),
                                     grid_locator1=locator,
                                     grid_locator2=locator)

    def transform(self, x, y):
        """Return the x and y values transformed by the skew angle."""
        if x is None or y is None or self.skew is None:
            return x, y
        else:
            x, y = np.asarray(x), np.asarray(y)
            angle = np.radians(self.skew)
            return 1.*x+np.cos(angle)*y,  np.sin(angle)*y

    def inverse_transform(self, x, y):
        """Return the inverse transform of the x and y values."""
        if x is None or y is None or self.skew is None:
            return x, y
        else:
            x, y = np.asarray(x), np.asarray(y)
            angle = np.radians(self.skew)
            return 1.*x-y/np.tan(angle),  y/np.sin(angle)

    def set_log_axis(self):
        """Set x and y axis scales when the log option is on or off."""
        ax = self.figure.gca()
        if self.xtab.logbox.isChecked():
            ax.set_xscale('log')
        else:
            ax.set_xscale('linear')
        if self.ytab.logbox.isChecked():
            ax.set_yscale('log')
        else:
            ax.set_yscale('linear')
        self.draw()

    def symlog(self, linthresh=None, linscale=None, vmax=None):
        """Use symmetric log normalization in the current plot.

           This implements SymLogNorm, which requires the definition of 
           a region close to zero where a linear interpolation is 
           utilized. The current data is replotted with the new 
           normalization.

        Parameters
        ----------
        linthresh: float)
            Threshold value below which linear interpolation is used.
        linscale: float
            Parameter that stretches the region over which the linear 
            interpolation is used.
        vmax: float
            The maximum value for the plot. This is applied 
            symmetrically, i.e., vmin = -vmax.
        """
        self._linthresh = linthresh
        self._linscale = linscale
        
        if self.image is not None:
            if vmax is None:
                vmax = max(abs(self.vaxis.min), abs(self.vaxis.max))
            if linthresh:
                linthresh = self._linthresh
            else:
                linthresh = vmax / 10.0
            if linscale:
                linscale = self._linscale
            else:
                linscale = 0.1
            self.vaxis.min = self.vaxis.lo = -vmax
            self.vaxis.max = self.vaxis.hi = vmax
            self.colorbar.locator = AutoLocator()
            self.colorbar.formatter = ScalarFormatter()
            self.colorbar.set_norm(NXSymLogNorm(linthresh, linscale=linscale,
                                                vmin=-vmax, vmax=vmax))
            self.image.set_norm(NXSymLogNorm(linthresh, linscale=linscale,
                                             vmin=-vmax, vmax=vmax))
            self.colorbar.update_normal(self.image)
            self.image.set_clim(self.vaxis.lo, self.vaxis.hi)
            self.draw()
            self.vtab.set_axis(self.vaxis)

    def set_plot_limits(self, xmin=None, xmax=None, ymin=None, ymax=None, 
                        vmin=None, vmax=None):
        """Set the minimum and maximum values of the plot."""
        if xmin is not None:
            self.xaxis.min = xmin
        if xmax is not None:
            self.xaxis.max = xmax
        if ymin is not None:
            self.yaxis.min = ymin
        if ymax is not None:
            self.yaxis.max = ymax
        if vmin is not None:
            self.vaxis.min = vmin
        if vmax is not None:
            self.vaxis.max = vmax
        self.update_tabs()

    def reset_plot_limits(self, autoscale=True):
        """Restore the plot limits to the original values."""
        xmin, xmax, ymin, ymax = self.limits
        self.xaxis.min = self.xaxis.lo = self.xtab.minbox.old_value = xmin
        self.xaxis.max = self.xaxis.hi = self.xtab.maxbox.old_value = xmax
        self.yaxis.min = self.yaxis.lo = self.ytab.minbox.old_value = ymin
        self.yaxis.max = self.yaxis.hi = self.ytab.maxbox.old_value = ymax
        if self.ndim == 1:
            self.replot_axes()
        else:
            if autoscale:
                try:
                    self.vaxis.min = self.vaxis.lo = np.min(self.finite_v)
                    self.vaxis.max = self.vaxis.hi = np.max(self.finite_v)
                except:
                    self.vaxis.min = self.vaxis.lo = 0.0
                    self.vaxis.max = self.vaxis.hi = 0.1
                self.vtab.set_axis(self.vaxis)
            self.replot_image()
        self.update_tabs()

    def _aspect(self):
        """Return the currently set aspect ratio value."""
        return self._aspect

    def _set_aspect(self, aspect):
        """Set the aspect ratio of the x and y axes.
        
        If set to a numerical value, this is the ratio of the y-axis 
        unit length to the x-axis unit length. This parameter is 
        immediately passed to Matplotlib to adjust current and future 
        plots.
        
        Note
        ----
        When the axes represent lattice vectors of different unit 
        length, e.g., a and c, with the x-axis parallel to a and the 
        y-axis parallel to c, the numerical value is c/a. 
        
        Parameters
        ----------
        aspect: float or str
            The value of the aspect ratio. This is either 'auto', to let
            Matplotlib choose the ratio, 'equal', to have the aspect 
            ratio set by their values assuming their unit lengthss are 
            the same, or a floating point value representing the ratio.
            A value of 1 is equivalent to 'equal'.
        """
        try:
            self._aspect = float(aspect)
            if self._aspect > 0.0:
                self.otab._actions['set_aspect'].setChecked(True)
            else:
                return
        except (ValueError, TypeError):
            if aspect == 'auto':
                self._aspect = 'auto'
                self.otab._actions['set_aspect'].setChecked(False)
            elif aspect == 'equal':
                self._aspect = 'equal'
                self.otab._actions['set_aspect'].setChecked(True)
            else:
                self._aspect = 'auto'
        try:
            plotview.ax.set_aspect(self._aspect)
            self.canvas.draw()
        except:
            pass
        self.update_customize_panel()

    aspect = property(_aspect, _set_aspect, "Property: Aspect ratio value")

    def _skew(self):
        """Return the skew angle for a 2D plot."""
        return self._skew_angle

    def _set_skew(self, skew_angle):
        """Set the skew angle for a 2D plot.

        This defines the transformation values stored in 'grid_helper'.
        The data are replotted and the Customize Panel is updated.
        
        Note
        ----
        The skew angle is only meaningful if the ratio of the unit 
        lengths of the x and y axes is known. If they are different, 
        the 'aspect' parameter should be adjusted accordingly. 
        Otherwise, it is assumed they are the same, i.e., when 'aspect'
        is set to 'auto', it is automatically changed to 'equal'. 

        Parameters
        ----------
        skew_angle: float
            The angle between the x and y axes for a 2D plot.
        """
        try:
            _skew_angle = float(skew_angle)
            if self.skew is not None and np.isclose(self.skew, _skew_angle):
                return
            if np.isclose(_skew_angle, 0.0) or np.isclose(_skew_angle, 90.0):
                _skew_angle = None
        except (ValueError, TypeError):
            if (skew_angle is None or six.text_type(skew_angle) == '' or 
                six.text_type(skew_angle) == 'None' or 
                six.text_type(skew_angle) == 'none'):
                _skew_angle = None
            else:
                return
        if self.skew is None and _skew_angle is None:
            return
        else:
            self._skew_angle = _skew_angle
        if self.skew is not None and self._aspect == 'auto':
            self._aspect = 'equal'
            self.otab._actions['set_aspect'].setChecked(True)
            plotview.ax.set_aspect(self._aspect)
        if self.image is not None:
            self.replot_data(newaxis=True)
            self.update_customize_panel()

    skew = property(_skew, _set_skew, "Property: Axis skew angle")

    def _autoscale(self):
        """Return True if the ztab autoscale checkbox is selected."""
        if self.ndim > 2 and self.ztab.scalebox.isChecked():
            return True
        else:
            return False

    def _set_autoscale(self, value=True):
        """Set the ztab autoscale checkbox to True or False"""
        self.ztab.scalebox.setChecked(value)

    autoscale = property(_autoscale, _set_autoscale, "Property: Autoscale boolean")

    @property
    def summed(self):
        """Return True if the projection tab is set to sum the data."""
        if self.ptab.summed:
            return True
        else:
            return False

    def _cmap(self):
        """Return the color map set in the vtab."""
        return self.vtab.cmap

    def _set_cmap(self, cmap):
        """Set the color map.
        
        Parameters
        ----------
        cmap: str or Matplotlib cmap
            Value of required color map. If the cmap is not available
            but not in the NeXpy default set, it is added.
        
        Raises
        ------
        NeXusError
            If the requested color map is not available.
        """
        try:
            new_cmap = get_cmap(cmap)
        except ValueError as error:
            raise NeXusError(six.text_type(error))
        self.vtab.set_cmap(new_cmap.name)
        self.vtab.change_cmap()

    cmap = property(_cmap, _set_cmap, "Property: color map")

    @property
    def interpolations(self):
        """Return valid interpolations for the current plot.
        
        If the axes are not all equally spaced, then 2D plots use
        pcolormesh, which cannot use any Matplotlib interpolation 
        methods. It is possible to use Gaussian smoothing, with the
        'convolve' option.
        """
        if self.regular_grid:
            return interpolations
        elif "convolve" in interpolations:
            return interpolations[:2]
        else:
            return interpolations[:1]

    def _interpolation(self):
        """Return the currently selected interpolation method."""
        return self.vtab.interpolation

    def _set_interpolation(self, interpolation):
        """Set the interpolation method and replot the data."""
        try:
            self.vtab.set_interpolation(interpolation)
            self.interpolate()
        except ValueError as error:
            raise NeXusError(six.text_type(error))

    interpolation = property(_interpolation, _set_interpolation,
                             "Property: interpolation method")

    def interpolate(self):
        """Replot the data with the current interpolation method."""
        if self.image:
            self.x, self.y, self.v = self.get_image()
            if self.interpolation == 'convolve':
                self.plot_image()
            elif self.regular_grid:
                self.image.set_data(self.plotdata.nxsignal.nxdata)
                self.image.set_interpolation(self.interpolation)
            self.draw()

    def _smooth(self):
        """Return standard deviation in pixels of Gaussian smoothing."""
        return self._stddev

    def _set_smooth(self, value):
        """Set standard deviation in pixels of Gaussian smoothing."""
        self._stddev = value
        self.interpolate()

    smooth = property(_smooth, _set_smooth, 
                      "Property: No. of pixels in Gaussian convolution")

    def _offsets(self):
        """Return the axis offset used in tick labels."""
        return self._axis_offsets

    def _set_offsets(self, value):
        """Set the axis offset used in tick labels and redraw plot."""
        self._axis_offsets = value
        self.ax.ticklabel_format(useOffset=self._axis_offsets)
        self.draw()

    offsets = property(_offsets, _set_offsets, "Property: Axis offsets property")

    @property
    def regular_grid(self):
        """Return whether it is possible to use 'imshow'.
        
        If both the x and y axes are equally spaced and there is no skew
        angle, the Matplotlib imshow function is used for 2D plots. 
        Otherwise, pcolormesh is used.
        """
        try:
            return (self.xaxis.equally_spaced and 
                    self.yaxis.equally_spaced
                    and self.skew is None)
        except Exception:
            return False

    @property
    def ax(self):
        """The current Matplotlib axes instance."""
        return self.figure.gca()

    def draw(self):
        """Redraw the current plot."""
        self.canvas.draw_idle()

    def grid(self, display=None, **opts):
        """Set grid display.
        
        Parameters
        ----------
        display: bool or None
            If True, the grid is displayed. If None, grid display is 
            toggled on or off.
        opts: dictionary
            Valid options for displaying grids. If not set, the default
            Matplotlib styles are used.
        """
        if display is True or display is False:
            self._grid = display
        elif opts:
            self._grid = True
        else:
            self._grid = not self._grid
        if 'linestyle' in opts:
            self._gridstyle = opts['linestyle']
        else:
            opts['linestyle'] = self._gridstyle
        if 'color' in opts:
            self._gridcolor = opts['color']
        else:
            opts['color'] = self._gridcolor
        if not self._grid:
            opts = {}
        self.ax.grid(self._grid, **opts)
        self.draw()
        self.update_customize_panel()

    def vlines(self, x, ymin=None, ymax=None, y=None, **opts):
        """Plot vertical lines at x-value(s).
        
        Parameters
        ----------
        x: float or ndarray
            x-values of vertical line(s)
        y: float
            y-value at which the x-value is determined. This is only 
            required if the plot is skewed.
        ymin: float
            Minimum y-value of vertical line. Defaults to plot minimum.
        ymax: float
            Maximum y-value of vertical line. Defaults to plot maximum.
        opts: dictionary
            Valid options for displaying lines.

        Returns
        -------
        lines: Matplotlib LineCollection
            Collection of vertical lines.
        """
        if ymin is None:
            ymin = plotview.ax.get_ylim()[0]
        if ymax is None:
            ymax = plotview.ax.get_ylim()[1]
        if self.skew is not None and y is not None:
            x, _ = self.transform(x, y)
        lines = plotview.ax.vlines(x, ymin, ymax, **opts)
        self.canvas.draw()
        return lines

    vline = vlines

    def hlines(self, y, xmin=None, xmax=None, x=None, **opts):
        """Plot horizontal line at y-value(s).
        
        Parameters
        ----------
        y: float or ndarray
            y-values of horizontal line(s)
        x: float
            x-value at which the y-value is determined. This is only 
            required if the plot is skewed.
        xmin: float
            Minimum x-value of horizontal line. Defaults to plot 
            minimum.
        xmax: float
            Maximum x-value of horizontal line. Defaults to plot 
            maximum.
        opts: dictionary
            Valid options for displaying lines.

        Returns
        -------
        lines: Matplotlib LineCollection
            Collection of horizontal lines.
        """
        if xmin is None:
            xmin = plotview.ax.get_xlim()[0]
        if xmax is None:
            xmax = plotview.ax.get_xlim()[1]
        if self.skew is not None and x is not None:
            _, y = self.transform(x, y)
        lines = plotview.ax.hlines(y, xmin, xmax, **opts)
        self.canvas.draw()
        return lines

    hline = hlines

    def crosshairs(self, x, y, **opts):
        """Plot crosshairs centered at (x,y).
        
        Parameters
        ----------
        x: float
            x-value of vertical line
        y: float
            y-value of horizontal line
        opts: dictionary
            Valid options for displaying lines.

        Returns
        -------
        lines: list
            List containing line collections of vertical and horizontal 
            lines.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        crosshairs = []
        crosshairs.append(self.vline(float(x), **opts))
        crosshairs.append(self.hline(float(y), **opts))
        return crosshairs

    def xline(self, x, **opts):
        """Plot line at constant x-value.
        
        This is similar to vlines, but the line will be skewed if the 
        plot is skewed.
        
        Parameters
        ----------
        x: float
            x-value of vertical line
        opts: dictionary
            Valid options for displaying lines.

        Returns
        -------
        line: Line2D
            Matplotlib line object.
        """
        ymin, ymax = self.yaxis.get_limits()
        if self.skew is None:
            return self.vline(x, ymin, ymax, **opts)
        else:
            x0, _ = self.transform(float(x), ymin)
            x1, _ = self.transform(float(x), ymax)
            y0, y1 = plotview.ax.get_ylim()
            line = Line2D([x0,x1], [y0,y1], **opts)
            plotview.ax.add_line(line)
            self.canvas.draw()
            return line

    def yline(self, y, **opts):
        """Plot line at constant y-value.
        
        This is similar to hlines, but the line will be skewed if the 
        plot is skewed.
        
        Parameters
        ----------
        y: float
            y-value of vertical line
        opts: dictionary
            Valid options for displaying lines.

        Returns
        -------
        line: Line2D
            Matplotlib line object.
        """
        xmin, xmax = self.xaxis.get_limits()
        if self.skew is None:
            return self.hline(y, xmin, xmax, **opts)
        else:
            _, y0 = self.transform(xmin, float(y))
            _, y1 = self.transform(xmax, float(y))
            x0, x1 = plotview.ax.get_xlim()
            line = Line2D([x0, x1], [y0, y1], **opts)
            plotview.ax.add_line(line)
            self.canvas.draw()
            return line

    def rectangle(self, x, y, dx, dy, **opts):
        """Plot rectangle.
        
        Note
        ----
        The rectangle will be skewed if the plot is skewed.
        
        Parameters
        ----------
        x, y: float
            x and y values of lower left corner
        dx, dy: float
            x and y widths of rectangle
        opts: dictionary
            Valid options for displaying shapes.

        Returns
        -------
        rectangle: Polygon
            Matplotlib polygon object.
        """
        if self.skew is None:
            rectangle = plotview.ax.add_patch(Rectangle((float(x),float(y)),
                                              float(dx), float(dy), **opts))
        else:
            xc, yc = [x, x, x+dx, x+dx], [y, y+dy, y+dy, y]
            xy = [self.transform(_x, _y) for _x,_y in zip(xc,yc)]
            rectangle = plotview.ax.add_patch(Polygon(xy, True, **opts))
        if 'linewidth' not in opts:
            rectangle.set_linewidth(1.0)
        if 'facecolor' not in opts:
            rectangle.set_facecolor('none')
        self.canvas.draw()
        return rectangle

    def polygon(self, xy, closed=True, **opts):
        """Plot closed polygon.
        
        Note
        ----
        The polygon will be skewed if the plot is skewed.
        
        Parameters
        ----------
        xy: tuple
            x and y coordinates as a tuple of paired floats
        closed: bool
            True if the polygon is closed
        opts: dictionary
            Valid options for displaying shapes.

        Returns
        -------
        rectangle: Polygon
            Matplotlib polygon object.
        """
        if self.skew is not None:
            xy = [self.transform(_x, _y) for _x,_y in xy]
        polygon = plotview.ax.add_patch(Polygon(xy, closed, **opts))
        if 'linewidth' not in opts:
            polygon.set_linewidth(1.0)
        if 'facecolor' not in opts:
            polygon.set_facecolor('none')
        self.canvas.draw()
        return polygon

    def ellipse(self, x, y, dx, dy, **opts):
        """Plot ellipse.
        
        Note
        ----
        The ellipse will be skewed if the plot is skewed.
        
        Parameters
        ----------
        x, y: float
            x and y values of ellipse center
        dx, dy: float
            x and y widths of ellipse
        opts: dictionary
            Valid options for displaying shapes.

        Returns
        -------
        ellipse: Ellipse
            Matplotlib ellipse object.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        ellipse = plotview.ax.add_patch(Ellipse((float(x),float(y)),
                                                float(dx), float(dy), 
                                                **opts))
        if 'linewidth' not in opts:
            ellipse.set_linewidth(1.0)
        if 'facecolor' not in opts:
            ellipse.set_facecolor('none')
        self.canvas.draw()
        return ellipse

    def circle(self, x, y, radius, **opts):
        """Plot circle.
        
        Note
        ----
        This assumes that the unit lengths of the x and y axes are the 
        same. The circle will be skewed if the plot is skewed.
        
        Parameters
        ----------
        x, y: float
            x and y values of center of circle.
        radius: float
            radius of circle.
        opts: dictionary
            Valid options for displaying shapes.

        Returns
        -------
        circle: Circle
            Matplotlib circle object.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        circle = plotview.ax.add_patch(Circle((float(x),float(y)), radius,
                                              **opts))
        if 'linewidth' not in opts:
            circle.set_linewidth(1.0)
        if 'facecolor' not in opts:
            circle.set_facecolor('none')
        self.canvas.draw()
        return circle

    def init_tabs(self):
        """Initialize tabs for a new plot."""
        self.xtab.set_axis(self.xaxis)
        self.ytab.set_axis(self.yaxis)
        if self.ndim == 1:
            self.xtab.logbox.setVisible(True)
            self.xtab.axiscombo.setVisible(False)
            self.ytab.logbox.setVisible(True)
            self.ytab.axiscombo.setVisible(False)
            self.ytab.flipbox.setVisible(False)
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.vtab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ptab))
        elif self.ndim >= 2:
            self.vtab.set_axis(self.vaxis)
            if self.tab_widget.indexOf(self.vtab) == -1:
                self.tab_widget.insertTab(0,self.vtab,'signal')
            if self.number < 101:
                if self.tab_widget.indexOf(self.ptab) == -1:
                    self.tab_widget.insertTab(self.tab_widget.indexOf(self.otab),
                                              self.ptab,'projections')
                self.ptab.set_axes()
                self.zoom = None
            if self.ndim > 2:
                self.ztab.set_axis(self.zaxis)
                self.ztab.locked = True
                self.ztab.pause()
                self.ztab.scalebox.setChecked(True)
                if self.tab_widget.indexOf(self.ztab) == -1:
                    self.tab_widget.insertTab(self.tab_widget.indexOf(self.ptab),
                                              self.ztab,'z')
            else:
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.xtab.logbox.setVisible(False)
            self.xtab.axiscombo.setVisible(True)
            self.xtab.flipbox.setVisible(True)
            self.ytab.logbox.setVisible(False)
            self.ytab.axiscombo.setVisible(True)
            self.ytab.flipbox.setVisible(True)
            if self.rgb_image:
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.vtab))
            else:
                self.vtab.flipbox.setVisible(False)
        if self.projection_panel:
            self.projection_panel.close()
        if self.customize_panel:
            self.customize_panel.close()

    def update_tabs(self):
        """Update tabs when limits have changed."""
        self.xtab.set_range()
        self.xtab.set_limits(self.xaxis.lo, self.xaxis.hi)
        self.xtab.set_sliders(self.xaxis.lo, self.xaxis.hi)
        self.ytab.set_range()
        self.ytab.set_limits(self.yaxis.lo, self.yaxis.hi)
        self.ytab.set_sliders(self.yaxis.lo, self.yaxis.hi)
        if self.ndim > 1:
            self.vtab.set_range()
            self.vtab.set_limits(self.vaxis.lo, self.vaxis.hi)
            self.vtab.set_sliders(self.vaxis.lo, self.vaxis.hi)
        self.update_customize_panel()

    def change_axis(self, tab, axis):
        """Replace the axis in a plot tab."""
        xmin, xmax, ymin, ymax = self.limits
        if tab == self.xtab and axis == self.yaxis:
            self.yaxis = self.ytab.axis = self.xtab.axis
            self.xaxis = self.xtab.axis = axis
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
            self.limits = (ymin, ymax, xmin, xmax)
            if isinstance(self.aspect, numbers.Real):
                self.aspect = 1.0 / self.aspect
            self.replot_data(newaxis=True)
        elif tab == self.ytab and axis == self.xaxis:
            self.xaxis = self.xtab.axis = self.ytab.axis
            self.yaxis = self.ytab.axis = axis
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
            self.limits = (ymin, ymax, xmin, xmax)
            if isinstance(self.aspect, numbers.Real):
                self.aspect = 1.0 / self.aspect
            self.replot_data(newaxis=True)
        elif tab == self.ztab:
            self.zaxis = self.ztab.axis = axis
            self.ztab.set_axis(self.zaxis)
            self.zaxis.locked = self.ztab.locked
        else:
            if tab == self.xtab:
                self.zaxis = self.ztab.axis = self.xaxis
                self.xaxis = self.xtab.axis = axis
                self.xaxis.set_limits(self.xaxis.min, self.xaxis.max)
                self.xaxis.locked = False
                self.limits = (self.xaxis.min, self.xaxis.max, ymin, ymax)
            elif tab == self.ytab:
                self.zaxis = self.ztab.axis = self.yaxis
                self.yaxis = self.ytab.axis = axis
                self.yaxis.set_limits(self.yaxis.min, self.yaxis.max)
                self.yaxis.locked = False
                self.limits = (xmin, xmax, self.yaxis.min, self.yaxis.max)
            z = find_nearest(self.zaxis.data, 0.0)
            self.zaxis.set_limits(z, z)
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.ztab.set_axis(self.zaxis)
            self.vtab.set_axis(self.vaxis)
            self.ztab.locked = True
            self.aspect = 'auto'
            self.skew = None
            self.replot_data(newaxis=True)
            if self.projection_panel:
                self.projection_panel.update_limits()
        self.update_customize_panel()
        self.otab.update()

    def update_customize_panel(self):
        """Update the customize panel."""
        if self.customize_panel:
            self.customize_panel.update()

    def format_coord(self, x, y):
        """Return the x, y, and signal values for the selected pixel."""
        try:
            if plotview.ndim == 1:
                return 'x={:.4g} y={:.4g}'.format(x, y)
            else:
                x, y = plotview.inverse_transform(x, y)
                if plotview.xaxis.reversed:
                    col = np.searchsorted(x-plotview.xaxis.boundaries, 0.0) - 1
                else:
                    col = np.searchsorted(plotview.xaxis.boundaries-x, 0.0) - 1
                if plotview.yaxis.reversed:
                    row = np.searchsorted(y-plotview.yaxis.boundaries, 0.0) - 1
                else:
                    row = np.searchsorted(plotview.yaxis.boundaries-y, 0.0) - 1
                z = self.v[row,col]
                return 'x={:.4g} y={:.4g}\nv={:.4g}'.format(x, y, z)
        except Exception:
            return ''

    def close_view(self):
        """Remove this window from menus and close associated panels."""
        self.remove_menu_action()
        Gcf.destroy(self.number)
        if self.label in plotviews:
            del plotviews[self.label]
        if self.projection_panel:
            self.projection_panel.close()
        if self.customize_panel:
            self.customize_panel.close()
        if self.mainwindow.panels.tabs.count() == 0:
            self.mainwindow.panels.setVisible(False)

    def closeEvent(self, event):
        """Close this widget and mark it for deletion."""
        self.close_view()
        self.deleteLater()
        event.accept()


class NXPlotAxis(object):
    """Class containing plotted axis values and limits.

    Parameters
    ----------
    axis: NXfield
        Field containing the axis values and metadata.
    name: str
        The axis field name.
    data: ndarray
        The axis values.
    dim: int
        Dimension value
    dimlen: int
        Length of equivalent dimension in the signal array. This is used 
        to determine if the axis values are bin centers or boundaries.

    Attributes
    ----------
    name: str
        Axis name.
    data: ndarray
        Array of axis values.
    dim: int
        No. of the axis dimensions (not currently used).
    reversed: bool
        True if the axis values fall with increasing array index.
    equally_spaced: bool
        True if the axis values are regularly spaced.
    """
    def __init__(self, axis, dim=None, dimlen=None):
        self.name = axis.nxname
        self.data = axis.nxdata
        self.dim = dim
        self.reversed = False
        self.equally_spaced = True
        if self.data is not None:
            if dimlen is None:
                self.centers = None
                self.boundaries = None
                try:
                    self.min = np.min(self.data[np.isfinite(self.data)])
                    self.max = np.max(self.data[np.isfinite(self.data)])
                except Exception:
                    self.min = 0.0
                    self.max = 0.1
            else:
                if self.data[0] > self.data[-1]:
                    self.reversed = True
                _spacing = self.data[1:] - self.data[:-1]
                _range = self.data.max() - self.data.min()
                if max(_spacing) - min(_spacing) > _range/1000:
                    self.equally_spaced = False
                self.centers = centers(self.data, dimlen)
                self.boundaries = boundaries(self.data, dimlen)
                try:
                    self.min = np.min(self.boundaries[np.isfinite(self.boundaries)])
                    self.max = np.max(self.boundaries[np.isfinite(self.boundaries)])
                except:
                    self.min = 0.0
                    self.max = 0.1
        else:
            self.centers = None
            self.boundaries = None
            self.min = None
            self.max = None
        self.min_data = self.min
        self.max_data = self.max
        self.lo = None
        self.hi = None
        self.diff = 0.0
        self.locked = True
        if hasattr(axis, 'long_name'):
            self.label = axis.long_name
        elif hasattr(axis, 'units'):
            self.label = "%s (%s)" % (axis.nxname, axis.units)
        else:
            self.label = axis.nxname

    def __repr__(self):
        return 'NXPlotAxis("%s")' % self.name

    def set_data(self, axis, dimlen=None):
        """Initialize the axis data values.
        
        This also determines if the values are all equally spaced, 
        which is used to determine the Matplotlib image function, and 
        stores the bin centers and boundaries of the axis values, 
        whether stored as histograms or not.
        """
        self.data = axis.nxdata
        self.reversed = False
        if dimlen is not None:
            if self.data[0] > self.data[-1]:
                self.reversed = True
            _spacing = self.data[1:] - self.data[:-1]
            _range = self.data.max() - self.data.min()
            _spacing = self.data[1:] - self.data[:-1]
            if max(_spacing) - min(_spacing) > _range/1000:
                self.equally_spaced = False
            self.centers = centers(self.data, dimlen)
            self.boundaries = boundaries(self.data, dimlen)

    def set_limits(self, lo, hi):
        """Set the low and high values for the axis."""
        if lo > hi:
            lo, hi = hi, lo
        self.lo, self.hi = lo, hi
        self.diff = hi - lo

    def get_limits(self):
        """Return the low and high values for the axis."""
        return float(self.lo), float(self.hi)

    @property
    def min_range(self):
        return self.max_range*1e-6

    @property
    def max_range(self):
        return self.max - self.min


class NXReplotSignal(QtCore.QObject):
    """QObject to receive replot signals."""
    replot = QtCore.Signal()


class NXPlotTab(QtWidgets.QWidget):
    """Tab widget for setting axis limits and options.
    
    Parameters
    ----------
    name: str
        Name of the axis.
    axis: bool
        If True, this tab represents a plotted axis.
    log: bool
        If True, a log checkbox should be included.
    zaxis: bool
        If True, this is a tab for selecting the z-axis.
    image: bool
        If True, this is a tab for defining signal options, such as the
        color map or interpolation method.
    plotview: NXPlotView
        Parent window containing this tab.

    Attributes
    ----------
    name: str
        Name of the axis
    plotview: NXPlotView
        Parent window.
    minbox, maxbox: NXSpinBox, NXDoubleSpinBox
        Text boxes for defining the minimum and maximum plot values.
    minslider, maxslider: QSlider
        Sliders for adjusting minimum and maximum plot values.
    """
    def __init__(self, name=None, axis=True, log=True, zaxis=False, image=False,
                 plotview=None):

        super(NXPlotTab, self).__init__()

        self.name = name
        self.plotview = plotview

        self.setMinimumHeight(51)
        hbox = QtWidgets.QHBoxLayout()
        widgets = []

        if axis:
            self.axiscombo = self.combobox(self.change_axis)
            widgets.append(self.axiscombo)
        else:
            self.axiscombo = None
        if zaxis:
            self.zaxis = True
            self.minbox = self.spinbox(self.read_minbox)
            self.maxbox = self.spinbox(self.read_maxbox)
            self.lockbox = self.checkbox("Lock", self.change_lock)
            self.lockbox.setChecked(True)
            self.scalebox = self.checkbox("Autoscale", 
                                          self.plotview.replot_image)
            self.scalebox.setChecked(True)
            self.init_toolbar()
            widgets.append(self.minbox)
            widgets.append(self.maxbox)
            widgets.append(self.lockbox)
            widgets.append(self.scalebox)
            widgets.append(self.toolbar)
            self.minslider = self.maxslider = self.flipbox = self.logbox = None
        else:
            self.zaxis = False
            self.minbox = self.doublespinbox(self.read_minbox)
            self.minslider = self.slider(self.read_minslider)
            self.maxslider = self.slider(self.read_maxslider)
            self.maxbox = self.doublespinbox(self.read_maxbox)
            if log:
                self.logbox = self.checkbox("Log", self.set_log)
                self.logbox.setChecked(False)
            else:
                self.logbox = None
            self.flipbox = self.checkbox("Flip", self.flip_axis)
            widgets.append(self.minbox)
            widgets.extend([self.minslider, self.maxslider])
            widgets.append(self.maxbox)
            if log:
                widgets.append(self.logbox)
            widgets.append(self.flipbox)
            self.lockbox = self.scalebox = None
        if image:
            self.cmapcombo = self.combobox(self.change_cmap)
            self.cmapcombo.addItems(cmaps)
            if cmaps.index('spring') > 0:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('spring'))
            if cmaps.index('seismic') > 0:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('seismic'))
            self.cmapcombo.setCurrentIndex(
                self.cmapcombo.findText(default_cmap))
            widgets.append(self.cmapcombo)
            self.interpcombo = self.combobox(self.change_interpolation)
            self.interpcombo.addItems(interpolations)
            self.set_interpolation('nearest')
            self._cached_interpolation = 'nearest'
            widgets.append(self.interpcombo)
        else:
            self.cmapcombo = None
            self.interpcombo = None

        if zaxis:
            hbox.addStretch()
        for w in widgets:
            hbox.addWidget(w)
            hbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        if zaxis:
            hbox.addStretch()

        self.setLayout(hbox)

        self.replotSignal = NXReplotSignal()
        self.replotSignal.replot.connect(self.plotview.replot_data)

    def __repr__(self):
        return 'NXPlotTab("%s")' % self.name

    def set_axis(self, axis):
        """Set the axis values and limits for the tab.
        
        This sets the minimum and maximum values of the tab spin boxes
        and sliders. If this is a signal axis (name = 'v'), then 
        the interpolations combobox is reset with options valid for the
        new axis.
        
        Parameters
        ----------
        axis: NXPlotAxis
            Axis values to be applied to this tab.
        """
        self.block_signals(True)
        self.axis = axis
        if self.zaxis:
            self.minbox.data = self.maxbox.data = self.axis.centers
            self.minbox.setRange(0, len(self.axis.data)-1)
            self.maxbox.setRange(0, len(self.axis.data)-1)
            self.minbox.setValue(axis.lo)
            self.maxbox.setValue(axis.hi)
            self.minbox.diff = self.maxbox.diff = axis.hi - axis.lo
            self.pause()
        else:
            self.set_range()
            self.set_limits(axis.lo, axis.hi)
        self.minbox.old_value = axis.lo
        self.maxbox.old_value = axis.hi
        if not self.zaxis:
            self.axis.locked = False
            self.flipbox.setChecked(False)
            self.set_sliders(axis.lo, axis.hi)
        if self.axiscombo is not None:
            self.axiscombo.clear()
            if self.plotview.rgb_image:
                self.axiscombo.addItem(axis.name)
            else:
                self.axiscombo.addItems(self.get_axes())
            self.axiscombo.setCurrentIndex(self.axiscombo.findText(axis.name))
        if self.name == 'v':
            self.interpcombo.clear()
            self.interpcombo.addItems(self.plotview.interpolations)
            self.set_interpolation(self._cached_interpolation)
        self.block_signals(False)

    def combobox(self, slot):
        """Return a QComboBox with a signal slot."""
        combobox = QtWidgets.QComboBox()
        combobox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        combobox.setMinimumWidth(100)
        combobox.activated.connect(slot)
        return combobox

    def spinbox(self, slot):
        """Return a NXSpinBox with a signal slot."""
        spinbox = NXSpinBox()
        spinbox.setAlignment(QtCore.Qt.AlignRight)
        spinbox.setFixedWidth(100)
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(False)
        spinbox.valueChanged[six.text_type].connect(slot)
        return spinbox

    def doublespinbox(self, slot):
        """Return a NXDoubleSpinBox with a signal slot."""
        doublespinbox = NXDoubleSpinBox()
        doublespinbox.setAlignment(QtCore.Qt.AlignRight)
        doublespinbox.setFixedWidth(100)
        doublespinbox.setKeyboardTracking(False)
        doublespinbox.editingFinished.connect(slot)
        return doublespinbox

    def slider(self, slot):
        """Return a QSlider with a signal slot."""
        slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        slider.setMinimumWidth(100)
        slider.setRange(0, 1000)
        slider.setSingleStep(5)
        slider.setValue(0)
        slider.setTracking(True)
        slider.sliderReleased.connect(slot)
        if self.name != 'v':
            slider.sliderMoved.connect(slot)
        return slider

    def checkbox(self, label, slot):
        """Return a QCheckbox with the specified label and slot."""
        checkbox = QtWidgets.QCheckBox(label)
        checkbox.setChecked(False)
        checkbox.clicked.connect(slot)
        return checkbox

    def pushbutton(self, label, slot):
        """Return a QPushButton with the specified label and slot."""
        button = QtWidgets.QPushButton(label)
        button.clicked.connect(slot)
        return button

    @QtCore.Slot()
    def read_maxbox(self):
        """Update plot based on the maxbox value."""
        hi = self.maxbox.value()
        if np.isclose(hi, self.maxbox.old_value):
            return
        if self.name == 'x' or self.name == 'y' or self.name == 'v':
            if self.name == 'v' and self.symmetric:
                self.axis.hi = hi
                self.axis.lo = -self.axis.hi
                self.minbox.setValue(-hi)
            elif hi > self.axis.lo:
                self.axis.hi = hi
            else:
                self.maxbox.setValue(self.maxbox.old_value)
                return
            self.axis.max = self.axis.hi
            self.axis.min = self.axis.lo
            self.set_range()
            self.set_sliders(self.axis.lo, self.axis.hi)
            if self.name == 'v':
                self.plotview.autoscale = False
                self.plotview.replot_image()
            else:
                self.plotview.replot_axes()
        else:
            if self.axis.locked:
                self.axis.hi = hi
                self.axis.lo = self.axis.hi - self.axis.diff
                if not np.isclose(self.axis.lo, self.minbox.old_value):
                    self.minbox.setValue(self.axis.lo)
                    self.minbox.old_value = self.axis.lo
                self.replotSignal.replot.emit()
            else:
                if hi >= self.axis.lo:
                    self.axis.hi = hi
                else:
                    self.maxbox.setValue(self.maxbox.old_value)
                    return
        self.maxbox.old_value = self.axis.hi

    @QtCore.Slot()
    def read_minbox(self):
        lo = self.minbox.value()
        if not self.minbox.isEnabled() or self.axis.locked or \
            np.isclose(lo, self.minbox.old_value):
            return
        if self.name == 'x' or self.name == 'y' or self.name == 'v':
            if lo < self.axis.hi:
                self.axis.lo = lo
            else:
                self.minbox.setValue(self.minbox.old_value)
                return
            self.axis.min = self.axis.lo
            self.set_range()
            self.set_sliders(self.axis.lo, self.axis.hi)
            if self.name == 'v':
                self.plotview.autoscale = False
                self.plotview.replot_image()
            else:
                self.plotview.replot_axes()
        else:
            if lo <= self.axis.hi:
                self.axis.lo = lo
            else:
                self.minbox.setValue(self.minbox.old_value)
                return
        self.minbox.old_value = self.axis.lo

    def read_maxslider(self):
        self.block_signals(True)
        if self.name == 'v' and self.symmetric:
            _range = max(self.axis.max, self.axis.min_range)
            self.axis.hi = max((self.maxslider.value()*_range/1000), 
                                self.axis.min_range)
            self.axis.lo = -self.axis.hi
            self.maxbox.setValue(self.axis.hi)
            self.minbox.setValue(self.axis.lo)
            self.minslider.setValue(1000 - self.maxslider.value())
        else:
            self.axis.lo = self.minbox.value()
            _range = max(self.axis.max - self.axis.lo, self.axis.min_range)
            self.axis.hi = self.axis.lo + max((self.maxslider.value()*_range/1000), 
                                               self.axis.min_range)
            self.maxbox.setValue(self.axis.hi)
            _range = max(self.axis.hi - self.axis.min, self.axis.min_range)
            try:
                self.minslider.setValue(1000*(self.axis.lo - self.axis.min)/_range)
            except (ZeroDivisionError, OverflowError, RuntimeWarning):
                self.minslider.setValue(1000)
        if self.name == 'x' or self.name == 'y':
            self.plotview.replot_axes()
        else:
            self.plotview.autoscale = False
            self.plotview.replot_image()
        self.block_signals(False)

    def read_minslider(self):
        self.block_signals(True)
        self.axis.hi = self.maxbox.value()
        _range = max(self.axis.hi - self.axis.min, self.axis.min_range)
        self.axis.lo = self.axis.min + (self.minslider.value()*_range/1000)
        self.minbox.setValue(self.axis.lo)
        _range = max(self.axis.max-self.axis.lo, self.axis.min_range)
        try:
            self.maxslider.setValue(1000*(self.axis.hi-self.axis.lo)/_range)
        except (ZeroDivisionError, OverflowError, RuntimeWarning):
            self.maxslider.setValue(0)
        if self.name == 'x' or self.name == 'y':
            self.plotview.replot_axes()
        else:
            self.plotview.autoscale = False
            self.plotview.replot_image()
        self.block_signals(False)

    def set_sliders(self, lo, hi):
        self.block_signals(True)
        _range = max(hi-self.axis.min, self.axis.min_range)
        try:
            self.minslider.setValue(1000*(lo - self.axis.min)/_range)
        except (ZeroDivisionError, OverflowError, RuntimeWarning):
            self.minslider.setValue(1000)
        _range = max(self.axis.max - lo, self.axis.min_range)
        try:
            self.maxslider.setValue(1000*(hi-lo)/_range)
        except (ZeroDivisionError, OverflowError, RuntimeWarning):
            self.maxslider.setValue(0)
        self.block_signals(False)

    def block_signals(self, block=True):
        self.minbox.blockSignals(block)
        self.maxbox.blockSignals(block)
        if self.minslider: self.minslider.blockSignals(block)
        if self.maxslider: self.maxslider.blockSignals(block)

    @property
    def log(self):
        if self.logbox is not None:
            return self.logbox.isChecked()

    def set_log(self):
        try:
            if self.name == 'v' and self.plotview.image:
                self.plotview.replot_image()
            else:
                self.plotview.set_log_axis()
        except:
            pass

    def _locked(self):
        try:
            return self.lockbox.isChecked()
        except:
            return False

    def _set_locked(self, value):
        try:
            self.axis.locked = value
            if value:
                lo, hi = self.get_limits()
                self.axis.diff = self.maxbox.diff = self.minbox.diff = max(hi - lo, 0.0)
                self.minbox.setDisabled(True)
            else:
                self.axis.locked = False
                self.axis.diff = self.maxbox.diff = self.minbox.diff = 0.0
                self.minbox.setDisabled(False)
            self.lockbox.setChecked(value)
        except:
            pass

    locked = property(_locked, _set_locked, "Property: Tab lock")

    def change_lock(self):
        self._set_locked(self.locked)

    def _flipped(self):
        try:
            return self.flipbox.isChecked()
        except:
            return False

    def _set_flipped(self, value):
        try:
            self.flipbox.setChecked(value)
        except:
            pass

    flipped = property(_flipped, _set_flipped, "Property: Axis flip")

    def flip_axis(self):
        try:
            self.plotview.replot_axes()
        except:
            pass

    @QtCore.Slot()
    def reset(self):
        self.set_range()
        self.set_limits(self.axis.min, self.axis.max)

    def set_range(self):
        """Set the range and step sizes for the minbox and maxbox."""
        if np.isclose(self.axis.min, self.axis.max):
            self.axis.min, self.axis.max = nonsingular(self.axis.min, self.axis.max)
        self.minbox.setRange(self.axis.min, self.axis.max)
        self.maxbox.setRange(self.axis.min, self.axis.max)
        range = self.axis.max - self.axis.min
        decimals = int(max(0, 2-np.rint(np.log10(range)))) + 1
        self.minbox.setSingleStep((range)/100)
        self.maxbox.setSingleStep((range)/100)
        self.minbox.setDecimals(decimals)
        self.maxbox.setDecimals(decimals)

    def get_limits(self):
        """Return the minbox and maxbox values."""
        return self.minbox.value(), self.maxbox.value()

    def set_limits(self, lo, hi):
        """Set the minbox and maxbox limits and sliders."""
        if lo > hi:
            lo, hi = hi, lo
        self.axis.set_limits(lo, hi)
        self.minbox.setValue(lo)
        self.maxbox.setValue(hi)
        if not self.zaxis:
            self.set_sliders(lo, hi)

    def change_axis(self):
        """Change the axis for the current tab."""
        names = [self.plotview.axis[i].name for i in range(self.plotview.ndim)]
        idx = names.index(self.axiscombo.currentText())
        self.plotview.change_axis(self, self.plotview.axis[idx])

    def get_axes(self):
        """Return a list of the currently plotted axes."""
        if self.zaxis:
            plot_axes = [self.plotview.xaxis.name, self.plotview.yaxis.name]
            return  [axis.nxname for axis in self.plotview.axes
                     if axis.nxname not in plot_axes]
        else:
            return [axis.nxname for axis in self.plotview.axes]

    def change_cmap(self):
        """Change the color map of the current plot."""
        try:
            cm = get_cmap(self.cmap)
            cm.set_bad('k', 1)
            self.plotview.image.set_cmap(cm)
            if self.symmetric:
                self.symmetrize()
                self.plotview.x, self.plotview.y, self.plotview.v = self.plotview.get_image()
                self.plotview.replot_image()
            else:
                self.minbox.setDisabled(False)
                self.minslider.setDisabled(False)
            self.plotview.draw()
        except Exception:
            pass

    def set_cmap(self, cmap):
        """Set the color map.
        
        If the color map is available but was not included in the 
        default list when NeXpy was launched, it is added to the list.
        """
        idx = self.cmapcombo.findText(cmap)
        if idx < 0 and cmap in cmap_d:
            self.cmapcombo.insertItem(4, cmap)
            self.cmapcombo.setCurrentIndex(self.cmapcombo.findText(cmap))

    @property
    def cmap(self):
        """Return the currently selected color map."""
        return self.cmapcombo.currentText()

    @property
    def symmetric(self):
        """Return True if a divergent color map has been selected."""
        if (self.cmapcombo is not None and
            self.cmapcombo.currentIndex() >= self.cmapcombo.findText('seismic')):
                return True
        return False

    def symmetrize(self):
        """Symmetrize the minimum and maximum boxes and sliders."""
        self.axis.lo = -self.axis.hi
        self.axis.min = -self.axis.max
        self.maxbox.setMinimum(0.0)
        self.minbox.setMinimum(-self.maxbox.maximum())
        self.minbox.setMaximum(0.0)
        self.minbox.setValue(-self.maxbox.value())
        self.minbox.setDisabled(True)
        self.minslider.setValue(1000-self.maxslider.value())
        self.minslider.setDisabled(True)

    def change_interpolation(self):
        self._cached_interpolation = self.interpolation
        self.plotview.interpolate()

    def set_interpolation(self, interpolation):
        idx = self.interpcombo.findText(interpolation)
        if idx >= 0:
            self.interpcombo.setCurrentIndex(idx)
            self._cached_interpolation = interpolation
        else:
            self.interpcombo.setCurrentIndex(0)

    @property
    def interpolation(self):
        return self.interpcombo.currentText()

    def init_toolbar(self):
        _backward_icon = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui',
                                            'resources/backward-icon.png'))
        _pause_icon = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui',
                                            'resources/pause-icon.png'))
        _forward_icon = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui',
                                            'resources/forward-icon.png'))
        _refresh_icon = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui',
                                            'resources/refresh-icon.png'))
        self.toolbar = QtWidgets.QToolBar(parent=self)
        self.toolbar.setIconSize(QtCore.QSize(16,16))
        self.add_action(_refresh_icon, self.plotview.replot_data, "Replot",
                        checkable=False)
        self.toolbar.addSeparator()
        self.playback_action = self.add_action(_backward_icon,
                                               self.playback,
                                               "Play Back")
        self.add_action(_pause_icon, self.pause, "Pause", checkable=False)
        self.playforward_action = self.add_action(_forward_icon,
                                                  self.playforward,
                                                  "Play Forward")
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.slideshow)
        self.playsteps = 0

    def add_action(self, icon, slot, tooltip, checkable=True):
        action = self.toolbar.addAction(icon, '', slot)
        action.setToolTip(tooltip)
        if checkable:
            action.setCheckable(True)
            action.setChecked(False)
        return action

    def slideshow(self):
        self.maxbox.stepBy(self.playsteps)
        if self.maxbox.pause:
            self.pause()

    def playback(self):
        self.locked = True
        if self.playsteps == -1:
            self.interval = self.timer.interval() / 2
        else:
            self.playsteps = -1
            self.interval = 1000
        self.timer.setInterval(self.interval)
        self.timer.start(self.interval)
        self.playback_action.setChecked(True)
        self.playforward_action.setChecked(False)

    def pause(self):
        self.playsteps = 0
        self.timer.stop()
        self.playback_action.setChecked(False)
        self.playforward_action.setChecked(False)

    def playforward(self):
        self.locked = True
        if self.playsteps == 1:
            self.interval = self.timer.interval() / 2
        else:
            self.playsteps = 1
            self.interval = 1000
        self.timer.setInterval(self.interval)
        self.timer.start(self.interval)
        self.playforward_action.setChecked(True)
        self.playback_action.setChecked(False)


class NXTextBox(QtWidgets.QLineEdit):
    """Subclass of QLineEdit with floating values."""
    def value(self):
        return float(six.text_type(self.text()))

    def setValue(self, value):
        self.setText(six.text_type(float('%.4g' % value)))


class NXSpinBox(QtWidgets.QSpinBox):
    """Subclass of QSpinBox with floating values.

    Parameters
    ----------
    data: ndarray
        Values of data to be adjusted by the spin box.

    Attributes
    ----------
    data: array
        Data values.
    validator: QDoubleValidator
        Function to ensure only floating point values are entered.
    old_value: float
        Previously stored value.
    diff: float
        Difference between maximum and minimum values when the box is
        locked.
    pause: bool
        Used when playing a movie with changing z-values.
    """
    def __init__(self, data=None):
        super(NXSpinBox, self).__init__()
        self.data = data
        self.validator = QtGui.QDoubleValidator()
        self.old_value = None
        self.diff = None
        self.pause = False

    def value(self):
        if self.data is not None:
            return float(self.centers[self.index])
        else:
            return 0.0

    @property
    def centers(self):
        if self.data is None:
            return None
        elif self.reversed:
            return self.data[::-1]
        else:
            return self.data

    @property
    def boundaries(self):
        if self.data is None:
            return None
        else:
            return boundaries(self.centers, self.data.shape[0])

    @property
    def index(self):
        return super(NXSpinBox, self).value()

    @property
    def reversed(self):
        if self.data[-1] < self.data[0]:
            return True
        else:
            return False

    def setValue(self, value):
        super(NXSpinBox, self).setValue(self.valueFromText(value))

    def valueFromText(self, text):
        return self.indexFromValue(float(six.text_type(text)))

    def textFromValue(self, value):
        try:
            return six.text_type(float('%.4g' % self.centers[value]))
        except:
            return ''

    def valueFromIndex(self, idx):
        if idx < 0:
            return self.centers[0]
        elif idx > self.maximum():
            return self.centers[-1]
        else:
            return self.centers[idx]

    def indexFromValue(self, value):
        return (np.abs(self.centers - value)).argmin()

    def minBoundaryValue(self, idx):
        if idx <= 0:
            return self.boundaries[0]
        elif idx >= len(self.centers) - 1:
            return self.boundaries[-2]
        else:
            return self.boundaries[idx]

    def maxBoundaryValue(self, idx):
        if idx <= 0:
            return self.boundaries[1]
        elif idx >= len(self.centers) - 1:
            return self.boundaries[-1]
        else:
            return self.boundaries[idx+1]

    def validate(self, input_value, pos):
        return self.validator.validate(input_value, pos)

    @property
    def tolerance(self):
        return self.diff / 100.0

    def stepBy(self, steps):
        self.pause = False
        if self.diff:
            value = self.value() + steps * self.diff
            if (value <= self.centers[-1] + self.tolerance) and \
               (value - self.diff >= self.centers[0] - self.tolerance):
                self.setValue(value)
            else:
                self.pause = True
        else:
            if self.index + steps <= self.maximum() and \
               self.index + steps >= 0:
                super(NXSpinBox, self).stepBy(steps)
            else:
                self.pause = True
        self.valueChanged.emit(1)


class NXDoubleSpinBox(QtWidgets.QDoubleSpinBox):

    def __init__(self, data=None):
        super(NXDoubleSpinBox, self).__init__()
        self.validator = QtGui.QDoubleValidator()
        self.validator.setRange(-np.inf, np.inf)
        self.validator.setDecimals(1000)
        self.old_value = None
        self.diff = None

    def validate(self, input_value, pos):
        return self.validator.validate(input_value, pos)

    def stepBy(self, steps):
        if self.diff:
            self.setValue(self.value() + steps * self.diff)
        else:
            super(NXDoubleSpinBox, self).stepBy(steps)
        self.editingFinished.emit()

    def valueFromText(self, text):
        value = np.float32(text)
        if value > self.maximum():
            self.setMaximum(value)
        elif value < self.minimum():
            self.setMinimum(value)
        return value

    def setValue(self, value):
        if value > self.maximum():
            self.setMaximum(value)
        elif value < self.minimum():
            self.setMinimum(value)
        super(NXDoubleSpinBox, self).setValue(value)


class NXProjectionTab(QtWidgets.QWidget):

    def __init__(self, plotview=None):

        super(NXProjectionTab, self).__init__()

        self.plotview = plotview

        hbox = QtWidgets.QHBoxLayout()
        widgets = []

        self.xbox = QtWidgets.QComboBox()
        self.xbox.currentIndexChanged.connect(self.set_xaxis)
        self.xbox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        widgets.append(QtWidgets.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = QtWidgets.QComboBox()
        self.ybox.currentIndexChanged.connect(self.set_yaxis)
        self.ybox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.ylabel = QtWidgets.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)

        self.save_button = QtWidgets.QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_projection)
        widgets.append(self.save_button)

        self.plot_button = QtWidgets.QPushButton("Plot", self)
        self.plot_button.clicked.connect(self.plot_projection)
        widgets.append(self.plot_button)

        self.sumbox = QtWidgets.QCheckBox("Sum")
        self.sumbox.setChecked(False)
        self.sumbox.clicked.connect(self.plotview.replot_data)
        widgets.append(self.sumbox)

        self.overplot_box = QtWidgets.QCheckBox("Over")
        self.overplot_box.setChecked(False)
        if 'Projection' not in plotviews:
            self.overplot_box.setVisible(False)
        widgets.append(self.overplot_box)

        self.panel_button = QtWidgets.QPushButton("Open Panel", self)
        self.panel_button.clicked.connect(self.open_panel)
        widgets.append(self.panel_button)

        hbox.addStretch()
        for w in widgets:
            hbox.addWidget(w)
            hbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        hbox.addStretch()

        self.setLayout(hbox)

    def __repr__(self):
        return 'NXProjectionTab("%s")' % self.plotview.label

    def get_axes(self):
        return  [self.plotview.axis[axis].name
                 for axis in range(self.plotview.ndim)]

    def set_axes(self):
        axes = self.get_axes()
        self.xbox.clear()
        self.xbox.addItems(axes)
        self.xbox.setCurrentIndex(self.xbox.findText(self.plotview.xaxis.name))
        if self.plotview.ndim <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0,'None')
            self.ybox.addItems(axes)
            self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.yaxis.name))

    @property
    def xaxis(self):
        return self.xbox.currentText()

    def set_xaxis(self):
        if self.xaxis == self.yaxis:
            self.ybox.setCurrentIndex(self.ybox.findText('None'))

    @property
    def yaxis(self):
        if self.plotview.ndim <= 2:
            return 'None'
        else:
            return self.ybox.currentText()

    def set_yaxis(self):
        if self.yaxis == self.xaxis:
            for idx in range(self.xbox.count()):
                if self.xbox.itemText(idx) != self.yaxis:
                    self.xbox.setCurrentIndex(idx)
                    break

    @property
    def summed(self):
        try:
            return self.sumbox.isChecked()
        except:
            return False

    def get_projection(self):
        x = self.get_axes().index(self.xaxis)
        if self.yaxis == 'None':
            axes = [x]
        else:
            y = self.get_axes().index(self.yaxis)
            axes = [y, x]
        limits = [(self.plotview.axis[axis].lo,
                   self.plotview.axis[axis].hi)
                   for axis in range(self.plotview.ndim)]
        if self.plotview.zoom:
            xdim, xlo, xhi = self.plotview.zoom['x']
            ydim, ylo, yhi = self.plotview.zoom['y']
        else:
            xaxis = self.plotview.xaxis
            xdim, xlo, xhi = xaxis.dim, xaxis.lo, xaxis.hi
            yaxis = self.plotview.yaxis
            ydim, ylo, yhi = yaxis.dim, yaxis.lo, yaxis.hi

        limits[xdim] = (xlo, xhi)
        limits[ydim] = (ylo, yhi)
        for axis in axes:
            if axis not in [ydim, xdim]:
                limits[axis] = (None, None)
        shape = self.plotview.data.nxsignal.shape
        if len(shape)-len(limits) > 0 and len(shape)-len(limits) == shape.count(1):
            axes, limits = fix_projection(shape, axes, limits)
        if self.plotview.rgb_image:
            limits.append((None, None))
        return axes, limits

    def save_projection(self):
        axes, limits = self.get_projection()
        keep_data(self.plotview.data.project(axes, limits, summed=self.summed))

    def plot_projection(self):
        if 'Projection' not in plotviews:
            self.overplot_box.setChecked(False)
        axes, limits = self.get_projection()
        if 'Projection' in plotviews:
            projection = plotviews['Projection']
        else:
            projection = NXPlotView('Projection')
        if len(axes) == 1 and self.overplot_box.isChecked():
            over = True
        else:
            over = False
        projection.plot(self.plotview.data.project(axes, limits, 
                                                   summed=self.summed), 
                        over=over)
        if len(axes) == 1:
            self.overplot_box.setVisible(True)
        else:
            self.overplot_box.setVisible(False)
            self.overplot_box.setChecked(False)
        self.plotview.make_active()
        plotviews[projection.label].raise_()
        self.plotview.mainwindow.panels.update()

    def open_panel(self):
        if not self.plotview.projection_panel:
            self.plotview.projection_panel = NXProjectionPanel(
                                                 plotview=self.plotview)
        self.plotview.projection_panel.panels.setVisible(True)
        self.plotview.projection_panel.panels.tabs.setCurrentWidget(
                                                 self.plotview.projection_panel)
        self.plotview.projection_panel.panels.update()
        self.plotview.projection_panel.panels.raise_()


class NXProjectionPanels(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super(NXProjectionPanels, self).__init__(parent)
        layout = QtWidgets.QVBoxLayout()
        self.tabs = QtWidgets.QTabWidget(self)
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.setWindowTitle('Projection Panel')
        self.tabs.currentChanged.connect(self.update)

    def __repr__(self):
        return 'NXProjectionPanels()'

    def __getitem__(self, key):
        try:
            return [panel for panel in self.panels if panel.label == key][0]
        except Exception as error:
            return None

    def __contains__(self, key):
        """Implements 'k in d' test"""
        return key in [panel for panel in self.panels if panel.label == key]

    @property
    def panels(self):
        return [self.tabs.widget(idx) for idx in range(self.tabs.count())]

    @property
    def labels(self):
        return [panel.plotview.label for panel in self.panels]

    def update(self):
        for panel in self.panels:
            panel.adjustSize()
            if 'Projection' in plotviews and plotviews['Projection'].ndim == 1:
                panel.overplot_box.setVisible(True)
            else:
                panel.overplot_box.setVisible(False)
            panel.update_panels()
        if self.tabs.count() == 0:
            self.setVisible(False)

    def closeEvent(self, event):
        self.close()
        event.accept()

    def close(self):
        for panel in self.panels:
            panel.close()
        self.setVisible(False)


class NXProjectionPanel(QtWidgets.QWidget):

    def __init__(self, plotview=None):

        self.plotview = plotview
        self.ndim = self.plotview.ndim
        self.label = self.plotview.label
        self.panels = self.plotview.mainwindow.panels

        QtWidgets.QWidget.__init__(self, parent=self.panels.tabs)

        layout = QtWidgets.QVBoxLayout()

        axisbox = QtWidgets.QHBoxLayout()
        widgets = []

        self.xbox = QtWidgets.QComboBox()
        self.xbox.currentIndexChanged.connect(self.set_xaxis)
        self.xbox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        widgets.append(QtWidgets.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = QtWidgets.QComboBox()
        self.ybox.currentIndexChanged.connect(self.set_yaxis)
        self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.yaxis.name))
        self.ybox.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.ylabel = QtWidgets.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)

        self.set_axes()

        axisbox.addStretch()
        for w in widgets:
            axisbox.addWidget(w)
            axisbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        axisbox.addStretch()

        layout.addLayout(axisbox)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        headers = ['Axis', 'Minimum', 'Maximum', 'Lock']
        width = [50, 100, 100, 25]
        column = 0
        header_font = QtGui.QFont()
        header_font.setBold(True)
        for header in headers:
            label = QtWidgets.QLabel()
            label.setAlignment(QtCore.Qt.AlignHCenter)
            label.setText(header)
            label.setFont(header_font)
            grid.addWidget(label, 0, column)
            grid.setColumnMinimumWidth(column, width[column])
            column += 1

        row = 0
        self.minbox = {}
        self.maxbox = {}
        self.lockbox = {}
        for axis in range(self.ndim):
            row += 1
            self.minbox[axis] = self.spinbox()
            self.maxbox[axis] = self.spinbox()
            self.lockbox[axis] = QtWidgets.QCheckBox()
            self.lockbox[axis].stateChanged.connect(self.set_lock)
            self.lockbox[axis].setChecked(False)
            grid.addWidget(QtWidgets.QLabel(self.plotview.axis[axis].name), row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)
            grid.addWidget(self.lockbox[axis], row, 3,
                           alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.save_button = QtWidgets.QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_projection)
        self.save_button.setDefault(False)
        self.save_button.setAutoDefault(False)
        grid.addWidget(self.save_button, row, 1)
        self.plot_button = QtWidgets.QPushButton("Plot", self)
        self.plot_button.clicked.connect(self.plot_projection)
        self.plot_button.setDefault(False)
        self.plot_button.setAutoDefault(False)
        grid.addWidget(self.plot_button, row, 2)
        self.overplot_box = QtWidgets.QCheckBox()
        self.overplot_box.setChecked(False)
        if 'Projection' not in plotviews:
            self.overplot_box.setVisible(False)
        grid.addWidget(self.overplot_box, row, 3,
                       alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.mask_button = QtWidgets.QPushButton("Mask", self)
        self.mask_button.clicked.connect(self.mask_data)
        self.mask_button.setDefault(False)
        self.mask_button.setAutoDefault(False)
        grid.addWidget(self.mask_button, row, 1)
        self.unmask_button = QtWidgets.QPushButton("Unmask", self)
        self.unmask_button.clicked.connect(self.unmask_data)
        self.unmask_button.setDefault(False)
        self.unmask_button.setAutoDefault(False)
        grid.addWidget(self.unmask_button, row, 2)

        row += 1
        self.sumbox = QtWidgets.QCheckBox("Sum Projections")
        self.sumbox.setChecked(False)
        grid.addWidget(self.sumbox, row, 1, 1, 2, 
                       alignment=QtCore.Qt.AlignHCenter)

        layout.addLayout(grid)

        self.copy_row = QtWidgets.QWidget()
        copy_layout = QtWidgets.QHBoxLayout()
        self.copy_box = QtWidgets.QComboBox()
        self.copy_button = QtWidgets.QPushButton("Copy Limits", self)
        self.copy_button.clicked.connect(self.copy_limits)
        self.copy_button.setDefault(False)
        self.copy_button.setAutoDefault(False)
        copy_layout.addStretch()
        copy_layout.addWidget(self.copy_box)
        copy_layout.addWidget(self.copy_button)
        copy_layout.addStretch()
        self.copy_row.setLayout(copy_layout)
        layout.addWidget(self.copy_row)

        button_layout = QtWidgets.QHBoxLayout()
        self.reset_button = QtWidgets.QPushButton("Reset Limits", self)
        self.reset_button.clicked.connect(self.reset_limits)
        self.reset_button.setDefault(False)
        self.reset_button.setAutoDefault(False)
        self.rectangle_button = QtWidgets.QPushButton("Hide Limits", self)
        self.rectangle_button.clicked.connect(self.toggle_rectangle)
        self.rectangle_button.setDefault(False)
        self.rectangle_button.setAutoDefault(False)
        self.close_button = QtWidgets.QPushButton("Close Panel", self)
        self.close_button.clicked.connect(self.close)
        self.close_button.setDefault(False)
        self.close_button.setAutoDefault(False)
        button_layout.addStretch()
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.rectangle_button)
        button_layout.addWidget(self.close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()

        self.setLayout(layout)
        self.panels.tabs.insertTab(self.plotview.number-1, self,
                                   self.plotview.label)
        self.panels.tabs.adjustSize()
        self.panels.tabs.setCurrentWidget(self)

        for axis in range(self.ndim):
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.axis[axis].centers
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.minbox[axis].diff = self.maxbox[axis].diff = None
            self.block_signals(True)
            self.minbox[axis].setValue(self.minbox[axis].data.min())
            self.maxbox[axis].setValue(self.maxbox[axis].data.max())
            self.block_signals(False)

        self._rectangle = None

        self.update_limits()
        self.update_panels()

    def __repr__(self):
        return 'NXProjectionPanel("%s")' % self.plotview.label

    def get_axes(self):
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        axes = self.get_axes()
        self.xbox.clear()
        self.xbox.addItems(axes)
        self.xbox.setCurrentIndex(self.xbox.findText(self.plotview.xaxis.name))
        if self.ndim <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0,'None')
            self.ybox.addItems(axes)
            self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.yaxis.name))

    @property
    def xaxis(self):
        return self.xbox.currentText()

    def set_xaxis(self):
        if self.xaxis == self.yaxis:
            self.ybox.setCurrentIndex(self.ybox.findText('None'))

    @property
    def yaxis(self):
        if self.ndim <= 2:
            return 'None'
        else:
            return self.ybox.currentText()

    def set_yaxis(self):
        if self.yaxis == self.xaxis:
            for idx in range(self.xbox.count()):
                if self.xbox.itemText(idx) != self.yaxis:
                    self.xbox.setCurrentIndex(idx)
                    break

    def set_limits(self):
        self.block_signals(True)
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                min_value = self.maxbox[axis].value() - self.maxbox[axis].diff
                self.minbox[axis].setValue(min_value)
            elif self.minbox[axis].value() > self.maxbox[axis].value():
                self.minbox[axis].setValue(self.maxbox[axis].value())
        self.block_signals(False)
        self.draw_rectangle()

    def get_limits(self, axis=None):
        def get_indices(minbox, maxbox):
            start, stop = minbox.index, maxbox.index+1
            if minbox.reversed:
                start, stop = len(maxbox.data)-stop, len(minbox.data)-start
            return start, stop
        if axis:
            return get_indices(self.minbox[axis], self.maxbox[axis])
        else:
            return [get_indices(self.minbox[axis], self.maxbox[axis]) 
                    for axis in range(self.ndim)]

    def reset_limits(self):
        self.block_signals(True)
        for axis in range(self.ndim):
            self.minbox[axis].setValue(self.minbox[axis].data.min())
            self.maxbox[axis].setValue(self.maxbox[axis].data.max())
        self.block_signals(False)
        self.update_limits()

    def update_limits(self):
        self.block_signals(True)
        for axis in range(self.ndim):
            lo, hi = self.plotview.axis[axis].get_limits()
            minbox, maxbox = self.minbox[axis], self.maxbox[axis]
            ilo, ihi = minbox.indexFromValue(lo), maxbox.indexFromValue(hi)
            if (self.plotview.axis[axis] is self.plotview.xaxis or 
                   self.plotview.axis[axis] is self.plotview.yaxis):
                ilo = ilo + 1
                ihi = max(ilo, ihi-1)
                if lo > minbox.value():
                    minbox.setValue(minbox.valueFromIndex(ilo))
                if  hi < maxbox.value():
                    maxbox.setValue(maxbox.valueFromIndex(ihi))
            else:
                minbox.setValue(minbox.valueFromIndex(ilo))
                maxbox.setValue(maxbox.valueFromIndex(ihi))
        self.block_signals(False)
        self.draw_rectangle()

    def update_panels(self):
        self.copy_row.setVisible(False)
        self.copy_box.clear()
        for panel in self.panels.panels:
            if panel is not self and panel.ndim == self.ndim:
                self.copy_row.setVisible(True)
                self.copy_box.addItem(panel.label)

    def copy_limits(self):
        self.block_signals(True)
        panel = self.panels[self.copy_box.currentText()]
        for axis in range(self.ndim):
            self.minbox[axis].setValue(panel.minbox[axis].value())
            self.maxbox[axis].setValue(panel.maxbox[axis].value())
            self.lockbox[axis].setCheckState(panel.lockbox[axis].checkState())
        self.xbox.setCurrentIndex(panel.xbox.currentIndex())
        if self.ndim > 1:
            self.ybox.setCurrentIndex(panel.ybox.currentIndex())
        self.block_signals(False)
        self.draw_rectangle()              

    def set_lock(self):
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                lo, hi = self.minbox[axis].value(), self.maxbox[axis].value()
                self.minbox[axis].diff = self.maxbox[axis].diff = max(hi - lo, 0.0)
                self.minbox[axis].setDisabled(True)
            else:
                self.minbox[axis].diff = self.maxbox[axis].diff = None
                self.minbox[axis].setDisabled(False)

    @property
    def summed(self):
        try:
            return self.sumbox.isChecked()
        except:
            return False

    def get_projection(self):
        x = self.get_axes().index(self.xaxis)
        if self.yaxis == 'None':
            axes = [x]
        else:
            y = self.get_axes().index(self.yaxis)
            axes = [y,x]
        limits = self.get_limits()
        shape = self.plotview.data.nxsignal.shape
        if len(shape)-len(limits) > 0 and len(shape)-len(limits) == shape.count(1):
            axes, limits = fix_projection(shape, axes, limits)
        if self.plotview.rgb_image:
            limits.append((None, None))
        return axes, limits

    def save_projection(self):
        try:
            axes, limits = self.get_projection()
            keep_data(self.plotview.data.project(axes, limits, summed=self.summed))
        except NeXusError as error:
            report_error("Saving Projection", error)

    def plot_projection(self):
        try:
            if 'Projection' in plotviews:
                projection = plotviews['Projection']
            else:
                projection = NXPlotView('Projection')
                self.overplot_box.setChecked(False)
            axes, limits = self.get_projection()
            if len(axes) == 1 and self.overplot_box.isChecked():
                over = True
            else:
                over = False
            projection.plot(self.plotview.data.project(axes, limits, 
                                                       summed=self.summed),
                            over=over)
            if len(axes) == 1:
                self.overplot_box.setVisible(True)
            else:
                self.overplot_box.setVisible(False)
                self.overplot_box.setChecked(False)
            self.plotview.make_active()
            plotviews[projection.label].raise_()
            self.panels.update()
        except NeXusError as error:
            report_error("Plotting Projection", error)

    def mask_data(self):
        try:
            limits = tuple(slice(x,y) for x,y in self.get_limits())
            self.plotview.data.nxsignal[limits] = np.ma.masked
            self.plotview.replot_data()
        except NeXusError as error:
            report_error("Masking Data", error)

    def unmask_data(self):
        try:
            limits = tuple(slice(x,y) for x,y in self.get_limits())
            self.plotview.data.nxsignal.mask[limits] = np.ma.nomask
            self.plotview.replot_data()
        except NeXusError as error:
            report_error("Masking Data", error)

    def spinbox(self):
        spinbox = NXSpinBox()
        spinbox.setAlignment(QtCore.Qt.AlignRight)
        spinbox.setFixedWidth(100)
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(True)
        spinbox.valueChanged[six.text_type].connect(self.set_limits)
        return spinbox

    def block_signals(self, block=True):
        for axis in range(self.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)

    @property
    def rectangle(self):
        if self._rectangle not in self.plotview.ax.patches:
            self._rectangle = self.plotview.ax.add_patch(
                                  Polygon(self.get_rectangle(), closed=True))
            self._rectangle.set_edgecolor(self.plotview._gridcolor)
            self._rectangle.set_facecolor('none')
            self._rectangle.set_linestyle('dashed')
            self._rectangle.set_linewidth(2)
        return self._rectangle

    def get_rectangle(self):
        xp = self.plotview.xaxis.dim
        yp = self.plotview.yaxis.dim
        x0 = self.minbox[xp].minBoundaryValue(self.minbox[xp].index)
        x1 = self.maxbox[xp].maxBoundaryValue(self.maxbox[xp].index)
        y0 = self.minbox[yp].minBoundaryValue(self.minbox[yp].index)
        y1 = self.maxbox[yp].maxBoundaryValue(self.maxbox[yp].index)
        xy = [(x0,y0), (x0,y1), (x1,y1), (x1,y0)]
        if self.plotview.skew is not None:
            return [self.plotview.transform(_x, _y) for _x,_y in xy]
        else:
            return xy

    def draw_rectangle(self):
        self.rectangle.set_xy(self.get_rectangle())
        self.plotview.draw()
        self.rectangle_button.setText("Hide Limits")

    def rectangle_visible(self):
        return self.rectangle_button.text() == "Hide Limits"

    def hide_rectangle(self):
        self.rectangle.set_visible(False)
        self.plotview.draw()
        self.rectangle_button.setText("Show Limits")

    def show_rectangle(self):
        self.rectangle.set_visible(True)
        self.plotview.draw()
        self.rectangle_button.setText("Hide Limits")

    def toggle_rectangle(self):
        if self.rectangle_visible():
            self.hide_rectangle()
        else:
            self.show_rectangle()

    def closeEvent(self, event):
        self.close()
        event.accept()

    def close(self):
        try:
            self._rectangle.remove()
        except Exception as error:
            pass
        self._rectangle = None
        self.plotview.draw()
        self.panels.tabs.removeTab(self.panels.tabs.indexOf(self))
        self.plotview.projection_panel = None
        self.deleteLater()
        self.panels.update()


class NXNavigationToolbar(NavigationToolbar):

    def __init__(self, canvas, parent):
        super(NXNavigationToolbar, self).__init__(canvas, parent)
        self.plotview = canvas.parent()
        self.zoom()

    def __repr__(self):
        return 'NXNavigationToolbar("%s")' % self.plotview.label

    def _icon(self, name):
        return QtGui.QIcon(os.path.join(pkg_resources.resource_filename(
                                        'nexpy.gui', 'resources'), name))

    def _init_toolbar(self):
        self.toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to  previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            (None, None, None, None),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            (None, None, None, None),
            ('Aspect', 'Set aspect ratio to equal', 'equal', 'set_aspect'),
            (None, None, None, None),
            ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
            ('Save', 'Save the figure', 'filesave', 'save_figure'),
            ('Add', 'Add plot data to tree', 'hand', 'add_data')
                )
        super(NXNavigationToolbar, self)._init_toolbar()
        self._actions['set_aspect'].setCheckable(True)
        for action in self.findChildren(QtWidgets.QAction):
            if action.text() == 'Customize':
                action.setToolTip('Customize plot')

    def home(self, autoscale=True):
        super(NXNavigationToolbar, self).home()
        self.plotview.reset_plot_limits(autoscale)

    def edit_parameters(self):
        if self.plotview.customize_panel is None:
            self.plotview.customize_panel = CustomizeDialog(parent=self.plotview)
            self.plotview.customize_panel.show()
        else:
            self.plotview.customize_panel.raise_()

    def add_data(self):
        keep_data(self.plotview.plotdata)

    def release_zoom(self, event):
        'the release mouse button callback in zoom to rect mode'
        super(NXNavigationToolbar, self).release_zoom(event)
        try:
            xdim = self.plotview.xtab.axis.dim
            ydim = self.plotview.ytab.axis.dim
        except AttributeError:
            return
        xmin, xmax = self.plotview.ax.get_xlim()
        ymin, ymax = self.plotview.ax.get_ylim()
        xmin, ymin = self.plotview.inverse_transform(xmin, ymin)
        xmax, ymax = self.plotview.inverse_transform(xmax, ymax)
        self.plotview.xtab.set_limits(xmin, xmax)
        self.plotview.ytab.set_limits(ymin, ymax)
        if event.button == 1:
            self.plotview.zoom = {'x': (xdim, xmin, xmax),
                                  'y': (ydim, ymin, ymax)}
            if self.plotview.projection_panel:
                self.plotview.projection_panel.update_limits()
            elif self.plotview.label != "Projection":
                self.plotview.tab_widget.setCurrentWidget(self.plotview.ptab)

    def release_pan(self, event):
        super(NXNavigationToolbar, self).release_pan(event)
        xmin, xmax = self.plotview.ax.get_xlim()
        ymin, ymax = self.plotview.ax.get_ylim()
        self.plotview.xtab.set_limits(xmin, xmax)
        self.plotview.ytab.set_limits(ymin, ymax)
        if self.plotview.projection_panel:
            self.plotview.projection_panel.update_limits()

    def _update_view(self):
        super(NXNavigationToolbar, self)._update_view()
        lims = self._views()
        if lims is None:
            return
        xmin, xmax, ymin, ymax = lims[0]
        if xmin > xmax:
            if self.plotview.xaxis.reversed:
                self.plotview.xtab.flipped = False
            else:
                self.plotview.xtab.flipped = True
            xmin, xmax = xmax, xmin
        else:
            if self.plotview.xaxis.reversed:
                self.plotview.xtab.flipped = True
            else:
                self.plotview.xtab.flipped = False
        self.plotview.xtab.block_signals(True)
        self.plotview.xtab.axis.set_limits(xmin, xmax)
        self.plotview.xtab.minbox.setValue(xmin)
        self.plotview.xtab.maxbox.setValue(xmax)
        self.plotview.xtab.set_sliders(xmin, xmax)
        self.plotview.xtab.block_signals(False)
        if ymin > ymax:
            if self.plotview.yaxis.reversed:
                self.plotview.ytab.flipped = False
            else:
                self.plotview.ytab.flipped = True
            ymin, ymax = ymax, ymin
        else:
            if self.plotview.yaxis.reversed:
                self.plotview.ytab.flipped = True
            else:
                self.plotview.ytab.flipped = False
        self.plotview.ytab.block_signals(True)
        self.plotview.ytab.axis.set_limits(ymin, ymax)
        self.plotview.ytab.minbox.setValue(ymin)
        self.plotview.ytab.maxbox.setValue(ymax)
        self.plotview.ytab.set_sliders(ymin, ymax)
        self.plotview.ytab.block_signals(False)

    def set_aspect(self):
        if self._actions['set_aspect'].isChecked():
            self.plotview.aspect = 'equal'
        else:
            self.plotview.aspect = 'auto'

    def mouse_move(self, event):
        self._set_cursor(event)
        if event.inaxes and event.inaxes.get_navigate():
            try:
                s = self.plotview.format_coord(event.xdata, event.ydata)
            except (ValueError, OverflowError):
                pass
            self.set_message(s)
        else:
            self.set_message('')


class CustomizeDialog(BaseDialog):

    def __init__(self, parent):
        super(CustomizeDialog, self).__init__(parent, default=True)

        self.plotview = parent

        self.parameters = {}
        pl = self.parameters['labels'] = GridParameters()
        pl.add('title', self.plotview.title, 'Title')
        pl['title'].box.setMinimumWidth(200)
        pl['title'].box.setAlignment(QtCore.Qt.AlignLeft)
        pl.add('xlabel', self.plotview.xaxis.label, 'X-Axis Label')
        pl['xlabel'].box.setMinimumWidth(200)
        pl['xlabel'].box.setAlignment(QtCore.Qt.AlignLeft)
        pl.add('ylabel', self.plotview.yaxis.label, 'Y-Axis Label')
        pl['ylabel'].box.setMinimumWidth(200)
        pl['ylabel'].box.setAlignment(QtCore.Qt.AlignLeft)
        if self.plotview.image is not None:
            image_grid = QtWidgets.QVBoxLayout()
            self.parameters['image'] = self.image_parameters()
            self.update_image_parameters()
            image_grid.addLayout(self.parameters['image'].grid_layout)
            self.set_layout(pl.grid(header=False),
                            image_grid,
                            self.close_buttons())
        else:
            self.curves = self.get_curves()
            self.curve_grids = QtWidgets.QWidget(parent=self)
            self.curve_layout = QtWidgets.QVBoxLayout()
            self.curve_layout.setContentsMargins(0, 20, 0, 0)
            self.curve_box = self.select_box(list(self.curves),
                                             slot=self.select_curve)
            self.curve_box.setMinimumWidth(200)
            layout = QtWidgets.QHBoxLayout()
            layout.addStretch()
            layout.addWidget(self.curve_box)
            layout.addStretch()
            self.curve_layout.addLayout(layout)
            for curve in self.curves:
                self.parameters[curve] = self.curve_parameters(curve)
                self.update_curve_parameters(curve)
                self.initialize_curve(curve)
            self.curve_grids.setLayout(self.curve_layout)
            self.set_layout(pl.grid(header=False),
                            self.curve_grids,
                            self.close_buttons())
        self.update_colors()
        self.set_title('Customize %s' % self.plotview.label)

    def close_buttons(self):
        buttonbox = QtWidgets.QDialogButtonBox(self)
        buttonbox.setOrientation(QtCore.Qt.Horizontal)
        buttonbox.setStandardButtons(QtWidgets.QDialogButtonBox.Apply|
                                     QtWidgets.QDialogButtonBox.Cancel|
                                     QtWidgets.QDialogButtonBox.Save)
        buttonbox.accepted.connect(self.accept)
        buttonbox.rejected.connect(self.reject)
        buttonbox.button(QtWidgets.QDialogButtonBox.Apply).clicked.connect(self.apply)
        buttonbox.button(QtWidgets.QDialogButtonBox.Apply).setDefault(True)
        return buttonbox

    def update(self):
        self.update_labels()
        if self.plotview.image is not None:
            self.update_image_parameters()
        else:
            self.update_curves()
            for curve in self.curves:
                self.update_curve_parameters(curve)
        self.update_colors()

    def update_labels(self):
        pl = self.parameters['labels']
        pl['title'].value = self.plotview.title
        pl['xlabel'].value = self.plotview.xaxis.label
        pl['ylabel'].value = self.plotview.yaxis.label

    def image_parameters(self):
        parameters = GridParameters()
        parameters.add('aspect', 'auto', 'Aspect Ratio')
        parameters.add('skew', 90.0, 'Skew Angle')
        parameters.add('grid', ['On', 'Off'], 'Grid')
        parameters.add('gridcolor', '#ffffff', 'Grid Color')
        parameters.add('gridstyle', list(linestyles.values()), 'Grid Style')
        parameters.grid(title='Image Parameters', header=False)
        return parameters

    def update_image_parameters(self):
        p = self.parameters['image']
        p['aspect'].value = self.plotview._aspect
        p['skew'].value = self.plotview._skew_angle
        if self.plotview._skew_angle is None:
            p['skew'].value = 90.0
        if self.plotview._grid:
            p['grid'].value = 'On'
        else:
            p['grid'].value = 'Off'
        p['gridcolor'].value = rgb2hex(colorConverter.to_rgb(self.plotview._gridcolor))
        p['gridcolor'].color_button = NXColorButton(p['gridcolor'])
        p['gridcolor'].color_button.set_color(to_qcolor(self.plotview._gridcolor))
        p['gridstyle'].value = linestyles[self.plotview._gridstyle]

    @property
    def curve(self):
        return self.curve_box.currentText()

    def get_curves(self):
        lines = self.plotview.ax.get_lines()
        labels = [line.get_label() for line in lines]
        for (i,label) in enumerate(labels):
            labels[i] = '%d: ' % (i+1) + labels[i]
        return dict(zip(labels, lines))

    def update_curves(self):
        curves = self.get_curves()
        new_curves = list(set(curves) - set(self.curves))
        for curve in new_curves:
            self.curves[curve] = curves[curve]
            self.parameters[curve] = self.curve_parameters(curve)
            self.update_curve_parameters(curve)
            self.initialize_curve(curve)
            self.curve_box.addItem(curve)

    def initialize_curve(self, curve):
        pc = self.parameters[curve]
        pc.widget = QtWidgets.QWidget(parent=self.curve_grids)
        pc.widget.setLayout(pc.grid(header=False))
        pc.widget.setVisible(False)
        self.curve_layout.addWidget(pc.widget)
        if curve == self.curve:
            pc.widget.setVisible(True)
        else:
            pc.widget.setVisible(False)

    def curve_parameters(self, curve):
        parameters = GridParameters()
        parameters.add('linestyle', list(linestyles.values()), 'Line Style')
        parameters.add('linewidth', 1.0, 'Line Width')
        parameters.add('linecolor', '#000000', 'Line Color')
        parameters.add('marker', list(markers.values()), 'Marker Style')
        parameters.add('markersize', 1.0, 'Marker Size')
        parameters.add('facecolor', '#000000', 'Face Color')
        parameters.add('edgecolor', '#000000', 'Edge Color')
        parameters.grid(title='Curve Parameters', header=False)
        return parameters

    def update_curve_parameters(self, curve):
        c, p = self.curves[curve], self.parameters[curve]
        p['linestyle'].value = linestyles[c.get_linestyle()]
        p['linewidth'].value = c.get_linewidth()
        p['linecolor'].value = rgb2hex(colorConverter.to_rgb(c.get_color()))
        p['linecolor'].color_button = NXColorButton(p['linecolor'])
        p['linecolor'].color_button.set_color(to_qcolor(c.get_color()))
        p['marker'].value = markers[c.get_marker()]
        p['markersize'].value = c.get_markersize()
        p['facecolor'].value = rgb2hex(colorConverter.to_rgb(c.get_markerfacecolor()))
        p['facecolor'].color_button = NXColorButton(p['facecolor'])
        p['facecolor'].color_button.set_color(to_qcolor(c.get_markerfacecolor()))
        p['edgecolor'].value = rgb2hex(colorConverter.to_rgb(c.get_markeredgecolor()))
        p['edgecolor'].color_button = NXColorButton(p['edgecolor'])
        p['edgecolor'].color_button.set_color(to_qcolor(c.get_markeredgecolor()))

    def update_colors(self):
        if self.plotview.image is not None:
            p = self.parameters['image']
            p.grid_layout.addWidget(p['gridcolor'].color_button, 4, 2, 
                                    alignment=QtCore.Qt.AlignCenter)
        else:
            for curve in self.curves:
                p = self.parameters[curve]
                p.grid_layout.addWidget(p['linecolor'].color_button, 2, 2, 
                                        alignment=QtCore.Qt.AlignCenter)
                p.grid_layout.addWidget(p['facecolor'].color_button, 5, 2, 
                                        alignment=QtCore.Qt.AlignCenter)
                p.grid_layout.addWidget(p['edgecolor'].color_button, 6, 2, 
                                        alignment=QtCore.Qt.AlignCenter)

    def select_curve(self):
        for curve in self.curves:
            self.parameters[curve].widget.setVisible(False)
        self.parameters[self.curve].widget.setVisible(True)

    def apply(self):
        pl = self.parameters['labels']
        self.plotview.title = pl['title'].value
        self.plotview.ax.set_title(self.plotview.title)
        self.plotview.xaxis.label = pl['xlabel'].value
        self.plotview.ax.set_xlabel(self.plotview.xaxis.label)
        self.plotview.yaxis.label = pl['ylabel'].value
        self.plotview.ax.set_ylabel(self.plotview.yaxis.label)
        if self.plotview.image is not None:
            pi = self.parameters['image']
            _aspect = pi['aspect'].value
            try:
                self.plotview._aspect = np.float(_aspect)
            except ValueError:
                if _aspect in ['auto', 'equal']:
                    self.plotview._aspect = _aspect
                else:
                    pi['aspect'].value = self.plotview._aspect = 'auto'
            _skew_angle = pi['skew'].value
            if pi['grid'].value == 'On':
                self.plotview._grid =True
            else:
                self.plotview._grid =False
            self.plotview._gridcolor = pi['gridcolor'].value
            self.plotview._gridstyle = [k for k, v in linestyles.items()
                                        if v == pi['gridstyle'].value][0]
            #reset in case plotview.aspect changed by plotview.skew            
            self.plotview.grid(self.plotview._grid)
            self.plotview.skew = _skew_angle
            self.plotview.aspect = self.plotview._aspect
            if (self.plotview.projection_panel is not None and
                    self.plotview.projection_panel._rectangle is not None):
                self.plotview.projection_panel._rectangle.set_edgecolor(
                    self.plotview._gridcolor)
        else:
            for curve in self.curves:
                c, pc = self.curves[curve], self.parameters[curve]
                linestyle = [k for k, v in linestyles.items()
                             if v == pc['linestyle'].value][0]
                c.set_linestyle(linestyle)
                c.set_linewidth(pc['linewidth'].value)
                c.set_color(pc['linecolor'].value)
                marker = [k for k, v in markers.items()
                          if v == pc['marker'].value][0]
                c.set_marker(marker)
                c.set_markersize(pc['markersize'].value)
                c.set_markerfacecolor(pc['facecolor'].value)
                c.set_markeredgecolor(pc['edgecolor'].value)
        self.plotview.draw()

    def accept(self):
        self.apply()
        self.plotview.customize_panel = None
        super(CustomizeDialog, self).accept()

    def reject(self):
        self.plotview.customize_panel = None
        super(CustomizeDialog, self).reject()

    def closeEvent(self, event):
        self.close()

    def close(self):
        self.plotview.customize_panel = None
        super(CustomizeDialog, self).close()
        self.deleteLater()


class NXColorButton(ColorButton):

    def __init__(self, parameter):
        super(NXColorButton, self).__init__()
        self.parameter = parameter
        self.parameter.box.editingFinished.connect(self.update_color)
        self.colorChanged.connect(self.update_text)

    def update_color(self):
        color = self.text()
        qcolor = to_qcolor(color)
        self.color = qcolor  # defaults to black if not qcolor.isValid()

    def update_text(self, color):
        self.parameter.value = color.name()

    def text(self):
        return self.parameter.value


class NXSymLogNorm(SymLogNorm):
    """
    A subclass of Matplotlib SymLogNorm containing a bug fix
    for backward compatibility to previous versions.
    """
    def __init__(self,  linthresh, linscale=1.0,
                 vmin=None, vmax=None, clip=False):
        super(NXSymLogNorm, self).__init__(linthresh, linscale, vmin, vmax, clip)
        if (not hasattr(self, '_upper') and 
                vmin is not None and vmax is not None):
            self._transform_vmin_vmax()


def keep_data(data):
    from .consoleapp import _nexpy_dir, _tree
    if 'w0' not in _tree:
        _tree['w0'] = nxload(os.path.join(_nexpy_dir, 'w0.nxs'), 'rw')
    ind = []
    for key in _tree['w0']:
        try:
            if key.startswith('s'):
                ind.append(int(key[1:]))
        except ValueError:
            pass
    if ind == []: ind = [0]
    data.nxname = 's'+six.text_type(sorted(ind)[-1]+1)
    _tree['w0'][data.nxname] = data

def centers(axis, dimlen):
    """Return the centers of the axis bins.

    This works regardless if the axis contains bin boundaries or 
    centers.
    
    Parameters
    ----------
    dimlen: int
        Size of the signal dimension. If this one more than the axis 
        size, it is assumed the axis contains bin boundaries.
    """
    ax = axis.astype(np.float32)
    if ax.shape[0] == dimlen+1:
        return (ax[:-1] + ax[1:])/2
    else:
        assert ax.shape[0] == dimlen
        return ax

def boundaries(axis, dimlen):
    """Return the boundaries of the axis bins.

    This works regardless if the axis contains bin boundaries or 
    centers.
    
    Parameters
    ----------
    dimlen: int
        Size of the signal dimension. If this one more than the axis 
        size, it is assumed the axis contains bin boundaries.
    """
    ax = axis.astype(np.float32)
    if ax.shape[0] == dimlen:
        start = ax[0] - (ax[1] - ax[0])/2
        end = ax[-1] + (ax[-1] - ax[-2])/2
        return np.concatenate((np.atleast_1d(start),
                               (ax[:-1] + ax[1:])/2,
                               np.atleast_1d(end)))
    else:
        assert ax.shape[0] == dimlen + 1
        return ax

def fix_projection(shape, axes, limits):
    """Fix the axes and limits for data with dimension sizes of 1.    

    If the shape contains dimensions of size 1, they need to be added 
    back to the list of axis dimensions and slice limits before calling 
    the origina NXdata 'project' function.

    Parameters
    ----------
    shape: tuple or list
        Shape of the signal.
    axes: list
        Original list of axis dimensions.
    limits: list
        Original list of slice limits.

    Returns
    -------
    fixed_axes: list
        List of axis dimensions restoring dimensions of size 1.
    fixed_limits: list
        List of slice limits with (0,0) added for dimensions of size 1.
    """
    fixed_limits = []
    fixed_axes = axes
    for s in shape:
        if s == 1:
            fixed_limits.append((0,0))
        else:
            fixed_limits.append(limits.pop(0))
    for (i,s) in enumerate(shape):
        if s==1:
            fixed_axes=[a+1 if a>=i else a for a in fixed_axes]
    return fixed_axes, fixed_limits
