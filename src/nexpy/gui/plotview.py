# -*- coding: utf-8 -*-
"""
Plotting modules.

This module contains the NXPlotView class, which defines plotting
windows and their associated tabs for modifying the axis limits and 
plotting options. 

Attributes
----------
plotview : NXPlotView
    The currently active NXPlotView window
plotviews : dict
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
import sys
import warnings

from posixpath import dirname, basename

import matplotlib as mpl
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import FigureManagerBase, FigureCanvasBase
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
from matplotlib.cbook import mplDeprecation
from mpl_toolkits.axisartist.grid_helper_curvelinear import GridHelperCurveLinear
from mpl_toolkits.axisartist import Subplot
from mpl_toolkits.axisartist.grid_finder import MaxNLocator
from scipy.spatial import Voronoi, voronoi_plot_2d

from nexusformat.nexus import NXfield, NXdata, NXroot, NeXusError, nxload

from .. import __version__
from .utils import report_error, report_exception, find_nearest, iterable

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
default_interpolation = 'nearest'
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
warnings.filterwarnings("ignore", category=mplDeprecation)


def new_figure_manager(label=None, *args, **kwargs):
    """Create a new figure manager instance.

    A new figure number is generated. with numbers > 100 preserved for 
    the Projection and Fit windows.

    Parameters
    ----------
    label : str
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
            missing_nums = sorted(set(range(nums[0], 
                                  nums[-1]+1)).difference(nums))
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
    label : str
        The label of the plotting window to be activated.
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
    """Qt widget containing a NeXpy plot.

    The widget consists of a QVBoxLayout containing a matplotlib canvas 
    over a tab widget, which contains NXPlotTab objects for adjusting 
    plot axes. The first class instance is embedded in the NeXpy main window,
    but subsequent instances are in separate windows.

    Parameters
    ----------
    label : str
        The label used to identify this NXPlotView instance. It can be
        used as the key to select an instance in the 'plotviews' dictionary.
    parent : QWidget
        The parent widget of this window. This needs to be set to 
        the applications QMainWindow if the window is to inherit the 
        application's main menu. If the parameter is not given, it is
        set to the main window defined in the 'consoleapp' module.

    Attributes
    ----------
    label : str
        The label used to identify this NXPlotView instance. It can be
        used as the key to select an instance in the 'plotviews' dictionary.
    number : int
        The number used by Matplotlib to identify the plot. Numbers 
        greater than 100 are reserved for the Projection and Fit plots.
    data : NXdata
        Original NXdata group to be plotted.
    plotdata : NXdata
        Plotted data. If 'data' has more than two dimensions, this 
        contains the 2D slice that is currently plotted.
    signal : NXfield
        Array containing the plotted signal values.
    axes : list
        List of NXfields containing the plotted axes.
    image
        Matplotlib image instance. Set to None for 1D plots.
    colorbar
        Matplotlib color bar.
    rgb_image : bool
        True if the image contains RGB layers.
    vtab : NXPlotTab
        Signal (color) axis for 2D plots.
    xtab : NXPlotTab
        x-axis (horizontal) tab.
    ytab : NXPlotTab
        y-axis (vertical) tab; this is the intensity axis for 1D plots.
    ztab : NXPlotTab
        Tab to define plotting limits for non-plotted dimensions in 
        three- or higher dimensional plots.
    ptab : NXPlotTab
        Tab for defining projections.
    otab : NXPlotTab
        Matplotlib buttons for adjusting plot markers and labels, 
        zooming, and saving plots in files.
    vaxis : NXPlotAxis
        Signal (color) axis values and limits.
    xaxis : NXPlotAxis
        x-axis values and limits.
    yaxis : NXPlotAxis
        y-axis values and limits.
    zaxis : NXPlotAxis
        Currently selected zaxis. For higher-dimensional data, this is
        the dimension selected in the ztab.
    axis : dict
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
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        global plotview, plotviews
        if label in plotviews:
            plotviews[label].close()

        self.figuremanager = new_figure_manager(label)
        self.number = self.figuremanager.num
        self.canvas = self.figuremanager.canvas
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.callbacks.exception_handler = report_exception

        Gcf.set_active(self.figuremanager)
        self.mpl_connect = self.canvas.mpl_connect
        self.button_press_cid = self.mpl_connect('button_press_event', 
                                                 self.on_button_press)
        self.key_press_cid = self.mpl_connect('key_press_event', 
                                              self.on_key_press)
        self.canvas.figure.show = lambda *args: self.show()
        self.figuremanager._cidgcf = self.button_press_cid
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
        self.tab_widget.setFocusPolicy(QtCore.Qt.NoFocus)

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
        self.xmin=self.xmax=self.ymin=self.ymax=self.vmin=self.vmax = None

        self.image = None
        self.colorbar = None
        self.zoom = None
        self._active_mode = self.otab._active
        self.rgb_image = False
        self._aspect = 'auto'
        self._skew_angle = None
        self._legend = None
        self._nameonly = False
        self._grid = False
        self._gridcolor = mpl.rcParams['grid.color']
        self._gridstyle = mpl.rcParams['grid.linestyle']
        self._gridwidth = mpl.rcParams['grid.linewidth']
        self._minorgrid = False
        self._majorlines = []
        self._minorlines = []
        self._linthresh = None
        self._linscale = None
        self._stddev = 2.0
        self._primary_signal_group = None

        # Remove some key default Matplotlib key mappings
        for key in [key for key in mpl.rcParams if key.startswith('keymap')]:
            for shortcut in 'bfghkloprsvxyzAEFGHOPSZ':
                if shortcut in mpl.rcParams[key]:
                    mpl.rcParams[key].remove(shortcut)

        if self.number < 101:
            plotview = self
        plotviews[self.label] = self
        self.plotviews = plotviews

        self.projection_panel = None
        self.customize_panel = None
        self.mask_panel = None
        self.shapes = []

        if self.label != "Main":
            self.add_menu_action()
            self.show()

        self.display_logo()

    def __repr__(self):
        return 'NXPlotView("%s")' % self.label

    def keyPressEvent(self, event):
        """Override the QWidget keyPressEvent.

        This converts the event into a Matplotlib KeyEvent so that keyboard
        shortcuts entered outside the canvas are treated as canvas shortcuts.

        Parameters
        ----------
        event : PyQt QKeyEvent
        """
        key = self.canvas._get_key(event)
        if key is not None:
            FigureCanvasBase.key_press_event(self.canvas, key, guiEvent=event)

    def on_button_press(self, event):
        """Handle mouse button press events in the Matplotlib canvas.

        If there is a mouse click within the plotting axes, the x and y values
        are stored in self.xdata and self.ydata. In addition, a right-click
        restores the original x and y limits without rescaling the color scale.

        Parameters
        ----------
        event : Matplotlib KeyEvent
        """
        self.make_active()
        if event.inaxes:
            self.x, self.y = event.x, event.y
            self.xdata, self.ydata = self.inverse_transform(event.xdata, 
                                                            event.ydata)
        else:
            self.x, self.y, self.xdata, self.ydata = None, None, None, None
        
    def on_key_press(self, event):
        """Handle key press events in the Matplotlib canvas.

        The following keys are defined:
        
        's', 'v'
            Switch to the `Signal` tab.
        'x', 'y', 'z'
            Switch to the `x`, `y` or `z` tabs, respectively.
        'p', 'o'
            Switch to the `Projection` or `Option` tab, respectively.
        'l'
            Toggle log scale (2D only).
        'f', 'b'
            Play the current z-axis values forward or backward, respectively.
        'r'
            Replot the image
        'g'
            Toggle display of the minor grid.
        'A'
            Store the plotted data. This is equivalent to selecting the 
            `Add Data` option button on the toolbar.
        'E'
            Toggle the aspect ratio. This is equivalent to turning the 
            `Aspect Ratio` button on the toolbar on and off.
        'F'
            Toggle the flipping of the y-axis.
        'G'
            Toggle display of the axis grid.
        'O'
            Show the `Edit Parameter` dialog.
        'P', 'Z'
            Toggle the pan or zoom mode, respectively. This is equivalent to 
            clicking on either the `Pan` or `Zoom` button in the toolbar. Both
            modes may be switched off, but only one can be on at any time.
        'S'
            Save the plot. This opens a `Save File` dialog with options for 
            choosing different image formats.

        Parameters
        ----------
        event : Matplotlib KeyEvent
        
        Notes
        -----
        The key that was pressed is stored in the Matplotlib KeyEvent 'key' 
        attribute.
        """
        if event.key == 'f' and self.ndim > 2:
            self.ztab.playforward()
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.ztab))
            self.ztab.axiscombo.setFocus()
        elif event.key == 'b' and self.ndim > 2:
            self.ztab.playback()
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.ztab))
            self.ztab.axiscombo.setFocus()
        elif event.key == ' ' and self.ndim > 2:
            self.ztab.pause()
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.ztab))
            self.ztab.axiscombo.setFocus()
        elif event.key == 'r' and self.ndim > 2:
            self.replot_data()
        elif event.key == 'g':
            self.grid(minor=True)
        elif event.key == 'h':
            self.otab.home(autoscale=False)
        elif event.key == 'l':
            try:
                if self.ndim > 1:
                    if self.vtab.log:
                        self.vtab.log = False
                    else:
                        self.vtab.log = True
            except NeXusError as error:
                report_error("Setting Log Scale", error)
        elif event.key == 's' or event.key == 'v':
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.vtab))
        elif event.key == 'x':
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.xtab))
            self.xtab.axiscombo.setFocus()
        elif event.key == 'y':
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.ytab))
            self.ytab.axiscombo.setFocus()
        elif event.key == 'z' and self.ndim > 2:
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.ztab))
            self.ztab.axiscombo.setFocus()
        elif event.key == 'p' and self.ndim > 1:
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.ptab))
            self.ptab.xbox.setFocus()
        elif event.key == 'o':
            self.tab_widget.setCurrentIndex(self.tab_widget.indexOf(self.otab))
        elif event.key == 'A':
            self.otab.add_data()
        elif event.key == 'E' and self.ndim > 1:
            self.otab.toggle_aspect()
        elif event.key == 'F' and self.ndim > 1:
            if self.ytab.flipped:
                self.ytab.flipped = False
            else:
                self.ytab.flipped = True
        elif event.key == 'H':
            self.otab.home()
        elif event.key == 'G':
            self.grid()
        elif event.key == 'O':
            self.otab.edit_parameters()
        elif event.key == 'P':
            self.otab.pan()
        elif event.key == 'S':
            self.otab.save_figure()
        elif event.key == 'Z':
            self.otab.zoom()

    def activate(self):
        """Restore original signal connections.
        
        This assumes a previous call to the deactivate function, which sets the
        current value of _active_mode.
        """
        if self._active_mode == 'ZOOM':
            self.otab.zoom()
        elif self._active_mode == 'PAN':
            self.otab.pan()        
    
    def deactivate(self):
        """Disable usual signal connections."""
        self._active_mode = self.otab._active
        if self._active_mode == 'ZOOM':
            self.otab.zoom()
        elif self._active_mode == 'PAN':
            self.otab.pan()

    def display_logo(self):
        """Display the NeXpy logo in the plotting pane."""
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
        self.canvas.activateWindow()
        self.canvas.setFocus()
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
        """Open a dialog box for saving the plot as a PNG file."""
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

        Other Parameters
        ----------------
        opts : dict
            This dictionary can contain any valid matplotlib options as
            well as other keyword arguments specified below.
        over : bool
            If True, 1D data is plotted over the existing plot.
        image : bool
            If True, the data are plotted as an RGB image.
        log : bool
            If True, the signal is plotted on a log scale.
        logx : bool
            If True, the x-axis is plotted on a log scale.
        logy : bool
            If True, the y-axis is plotted on a log scale. This is 
            equivalent to 'log=True' for one-dimensional data.
        skew : float
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
                if log:
                    logy = True
                self._nameonly = False
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
            self.reset_log()
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
        if self.xaxis.reversed or self.yaxis.reversed:
            self.replot_axes(draw=False)

        self.offsets = False
        self.aspect = self._aspect

        if self.ndim > 1:
            self.logv = log
        self.logx = logx
        self.logy = logy

        self.grid(self._grid, self._minorgrid)

        self.draw()
        self.otab.push_current()
        mpl.interactive(True)

    def get_plotdata(self, over=False):
        """Return an NXdata group containing the plottable data.

        This function removes size 1 arrays, creates axes if none are 
        specified and initializes the NXPlotAxis instances.
        
        Parameters
        ----------
        over : bool
            If True, the signal and axes values are updated without
            creating a new NXPlotAxis instance.
        """
        signal_group = self.signal_group
        if not over:
            self._primary_signal_group = signal_group

        if (over and signal_group and signal_group == self._primary_signal_group 
            and self.data.nxsignal.valid_axes(self.plotdata.nxaxes)):
            axes = self.plotdata.nxaxes
        elif self.data.plot_axes is not None:
            axes = self.data.plot_axes
        else:
            axes = [NXfield(np.arange(self.shape[i]), name='Axis%s'%i)
                            for i in range(self.ndim)]

        self.axes = [NXfield(axes[i].nxdata, name=axes[i].nxname,
                     attrs=axes[i].safe_attrs) for i in range(self.ndim)]

        if self.ndim > 2:
            idx=[np.s_[0] if s==1 else np.s_[:] 
                for s in self.data.nxsignal.shape]
            for i in range(len(idx)):
                if idx.count(slice(None,None,None)) > 2:
                    try:
                        idx[i] = self.axes[i].index(0.0)
                    except Exception:
                        idx[i] = 0
            signal = self.data.nxsignal[tuple(idx)][()]
        elif self.rgb_image:
            signal = self.data.nxsignal[()]
        else:
            signal = self.data.nxsignal[()].reshape(self.shape)
        if signal.dtype == np.bool:
            signal.dtype = np.int8
        self.signal = signal        

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
        x : ndarray
            Plotted x-values. For 1D data stored in histograms, these 
            are defined by the histogram centers.
        y : ndarray
            Plotted y-values, i.e., the signal array.
        e : ndarray
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
        fmt : str
            The format argument is used to set the color and type of the 
            markers or lines for 1D plots, using the standard matplotlib 
            syntax. The default is set to blue circles. All keyword 
            arguments accepted by matplotlib.pyplot.plot can be used to 
            customize the plot.
        over : bool
            If True, the figure is not cleared and the axes are not
            adjusted. However, the extremal axis values are changed, 
            and the entire range covering all the overplotted data is
            shown by, e.g., by clicking on the 'Home' button or 
            right-clicking on the plot.
        opts : dict
            A dictionary containing Matplotlib options.
        """
        if not over:
            self.figure.clf()
        ax = self.figure.gca()

        if self.e is not None:
            ax.errorbar(self.x, self.y, self.e, fmt=fmt, **opts)
        else:
            ax.plot(self.x, self.y, fmt,  **opts)

        ax.lines[-1].set_label(self.signal_group + self.signal.nxname)

        if over:
            self.xaxis.lo, self.xaxis.hi = ax.get_xlim()
            self.yaxis.lo, self.yaxis.hi = ax.get_ylim()
            self.xaxis.min = min(self.xaxis.min, self.xaxis.lo, self.x.min())
            self.xaxis.max = max(self.xaxis.max, self.xaxis.hi, self.x.max())
            self.yaxis.min = min(self.yaxis.min, self.yaxis.lo, self.y.min())
            self.yaxis.max = max(self.yaxis.max, self.yaxis.hi, self.y.max())
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
            ax.set_xlabel(self.xaxis.label)
            ax.set_ylabel(self.yaxis.label)
            ax.set_title(self.title)

            self.xaxis.min, self.xaxis.max = ax.get_xlim()
            self.yaxis.min, self.yaxis.max = ax.get_ylim()
            self.xaxis.lo, self.xaxis.hi = self.xaxis.min, self.xaxis.max
            self.yaxis.lo, self.yaxis.hi = self.yaxis.min, self.yaxis.max
            
        self.image = None
        self.colorbar = None
        if six.PY3:
            try:
                import mplcursors
                self.mplcursor = mplcursors.cursor(ax.get_lines())
            except ImportError:
                self.mplcursor = None           

    def get_image(self):
        """Initialize the plot's signal and axis values.

        Returns
        -------
        x : ndarray
            Plotted x-values. These are defined by the bin boundaries.
        y : ndarray
            Plotted y-values. These are defined by the bin boundaries.
        v : ndarray
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
        over : bool
            Not currently used.
        opts : dict
            A dictionary containing Matplotlib options.
        """

        if not over:
            self.set_data_limits()
            self.set_data_norm()
            self.figure.clf()
            if self.skew:
                ax = self.figure.add_subplot(Subplot(self.figure, 1, 1, 1, 
                                             grid_helper=self.grid_helper()))
            else:
                ax = self.figure.add_subplot(1, 1, 1)
            ax.autoscale(enable=True)
        else:
            ax = self.ax

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

        if not over and not self.rgb_image:
            self.colorbar = self.figure.colorbar(self.image, ax=ax, 
                                                 norm=self.norm)
            self.colorbar.locator = self.locator
            self.colorbar.formatter = self.formatter
            self.colorbar.update_bruteforce(self.image)

        xlo, ylo = self.transform(self.xaxis.lo, self.yaxis.lo)
        xhi, yhi = self.transform(self.xaxis.hi, self.yaxis.hi)

        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)

        if not over:
            ax.set_xlabel(self.xaxis.label)
            ax.set_ylabel(self.yaxis.label)
            ax.set_title(self.title)

        self.vaxis.min, self.vaxis.max = self.image.get_clim()

    @property
    def signal_group(self):
        """Determine full path of signal."""
        if self.data.nxroot.nxclass == "NXroot":
            return dirname(self.data.nxroot.nxname +
                           self.data.nxsignal.nxpath) + '/'
        elif 'signal_path' in self.data.nxsignal.attrs:
            return dirname(self.data.nxsignal.attrs['signal_path']) + '/'
        else:
            return ''

    @property
    def shape(self):
        """Shape of the original NXdata signal array.
        
        This removes any dimension of size 1. Also, a dimension is 
        removed if the data contain RGB layers.
        
        Returns
        -------
        shape : tuple
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
            self.vaxis.hi = self.vaxis.max = np.max(self.finite_v)
        if self.vtab.symmetric:
            self.vaxis.lo = -self.vaxis.hi
            self.vaxis.min = -self.vaxis.max
        elif self.vaxis.lo is None or self.autoscale:
            self.vaxis.lo = self.vaxis.min = np.min(self.finite_v)
        if self.vtab.log and not self.vtab.symmetric:
            try:
                self.vaxis.hi = max(self.vaxis.hi, 
                                    self.finite_v[self.finite_v>0.0].min())
            except ValueError:
                self.vaxis.lo = max(self.vaxis.lo, 0.01)
            try:
                self.vaxis.lo = max(self.vaxis.lo, 
                                    self.finite_v[self.finite_v>0.0].min())
            except ValueError:
                self.vaxis.lo = max(self.vaxis.lo, 0.01)

    def set_data_norm(self):
        """Set the normalization for 2D plots."""
        if self.vtab.log:
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
        newaxis : bool
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
            axes, limits = fix_projection(self.data.nxsignal.shape, axes, 
                                          limits)
        try:
            self.plotdata = self.data.project(axes, limits, summed=self.summed)
        except Exception:
            self.ztab.pause()
            six.reraise(*sys.exc_info())
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
        self.grid(self._grid, self._minorgrid)

    def replot_image(self):
        """Replot the image."""
        try:
            self.set_data_limits()
            self.set_data_norm()
            self.image.set_norm(self.norm)
            if self.colorbar:
                self.colorbar.locator = self.locator
                self.colorbar.formatter = self.formatter
                self.colorbar.set_norm(self.norm)
                self.colorbar.update_bruteforce(self.image)
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
        locator = MaxNLocator(nbins=9, steps=[1, 2, 2.5, 5, 10])
        self._grid_helper = GridHelperCurveLinear((self.transform, 
                                                   self.inverse_transform),
                                                   grid_locator1=locator,
                                                   grid_locator2=locator)
        return self._grid_helper

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

    def set_log_axis(self, name):
        """Set x and y axis scales when the log option is on or off."""
        if name == 'v' and self.image is not None:
            self.replot_image()
        else:
            ax = self.ax
            if name == 'x':
                if self.logx:
                    self.aspect = 'auto'
                    self.xtab.set_limits(*self.xaxis.log_limits())
                    ax.set_xscale('log')
                else:
                    ax.set_xscale('linear')
            elif name == 'y':
                if self.logy:
                    self.aspect = 'auto'
                    self.ytab.set_limits(*self.yaxis.log_limits())
                    ax.set_yscale('log')
                else:
                    ax.set_yscale('linear')

    def symlog(self, linthresh=None, linscale=None, vmax=None):
        """Use symmetric log normalization in the current plot.

           This implements SymLogNorm, which requires the definition of 
           a region close to zero where a linear interpolation is 
           utilized. The current data is replotted with the new 
           normalization.

        Parameters
        ----------
        linthresh : float)
            Threshold value below which linear interpolation is used.
        linscale : float
            Parameter that stretches the region over which the linear 
            interpolation is used.
        vmax : float
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
            self.colorbar.update_bruteforce(self.image)
            self.image.set_clim(self.vaxis.lo, self.vaxis.hi)
            self.draw()
            self.vtab.set_axis(self.vaxis)

    def set_plot_limits(self, xmin=None, xmax=None, ymin=None, ymax=None, 
                        vmin=None, vmax=None):
        """Set the minimum and maximum values of the plot."""
        if xmin is not None:
            self.xaxis.min = self.xaxis.lo = xmin
        if xmax is not None:
            self.xaxis.max = self.xaxis.hi = xmax
        if ymin is not None:
            self.yaxis.min = self.yaxis.lo = ymin
        if ymax is not None:
            self.yaxis.max = self.yaxis.hi = ymax
        if vmin is not None:
            self.vaxis.min = self.vaxis.lo = vmin
        if vmax is not None:
            self.vaxis.max = self.vaxis.hi = vmax
        if self.ndim == 1:
            self.replot_axes()
        else:
            self.replot_image()
        self.update_tabs()

    def reset_plot_limits(self, autoscale=True):
        """Restore the plot limits to the original values."""
        xmin, xmax, ymin, ymax = self.limits
        self.xaxis.min = self.xaxis.lo = self.xtab.minbox.old_value = xmin
        self.xaxis.max = self.xaxis.hi = self.xtab.maxbox.old_value = xmax
        if self.logx:
            self.xaxis.lo, self.xaxis.hi = self.xaxis.log_limits()
        self.yaxis.min = self.yaxis.lo = self.ytab.minbox.old_value = ymin
        self.yaxis.max = self.yaxis.hi = self.ytab.maxbox.old_value = ymax
        if self.logy:
            self.yaxis.lo, self.yaxis.hi = self.yaxis.log_limits()
        if self.ndim == 1:
            self.replot_axes()
        else:
            if autoscale:
                logv = self.logv
                try:
                    self.vaxis.min = self.vaxis.lo = np.min(self.finite_v)
                    self.vaxis.max = self.vaxis.hi = np.max(self.finite_v)
                except:
                    self.vaxis.min = self.vaxis.lo = 0.0
                    self.vaxis.max = self.vaxis.hi = 0.1
                self.vtab.set_axis(self.vaxis)
                self.logv = logv
            self.replot_image()
        self.update_tabs()

    def reset_log(self):
        for tab in [self.xtab, self.ytab, self.vtab]:
            tab.block_signals(True)
            tab.logbox.setChecked(False)
            tab.block_signals(False)

    @property
    def logx(self):
        return self.xtab.log

    @logx.setter
    def logx(self, value):
        self.xtab.log = value

    @property
    def logy(self):
        return self.ytab.log

    @logy.setter
    def logy(self, value):
        self.ytab.log = value

    @property
    def logv(self):
        return self.vtab.log

    @logv.setter
    def logv(self, value):
        self.vtab.log = value

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
        aspect : float or str
            The value of the aspect ratio. This is either 'auto', to let
            Matplotlib choose the ratio, 'equal', to have the aspect 
            ratio set by their values assuming their unit lengthss are 
            the same, or a floating point value representing the ratio.
            A value of 1 is equivalent to 'equal'.
        """
        if aspect != 'auto' and (self.logx or self.logy):
            raise NeXusError("Cannot set aspect ratio with log axes")
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
            self.ax.set_aspect(self._aspect)
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
        skew_angle : float
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
            self.ax.set_aspect(self._aspect)
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

    autoscale = property(_autoscale, _set_autoscale, 
                         "Property: Autoscale boolean")

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
        cmap : str or Matplotlib cmap
            Value of required color map. If the cmap is not available
            but not in the NeXpy default set, it is added.
        
        Raises
        ------
        NeXusError
            If the requested color map is not available.
        """
        self.vtab.cmap = cmap

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
        self.vtab.interpolation = interpolation

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
        try :
            self._axis_offsets = value
            self.ax.ticklabel_format(useOffset=self._axis_offsets)
            self.draw()
        except Exception as error:
            pass

    offsets = property(_offsets, _set_offsets, 
                       "Property: Axis offsets property")

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

    def legend(self, *items, **opts):
        """Add a legend to the plot."""
        if len(items) == 0:
            handles, labels = self.ax.get_legend_handles_labels()
        elif len(items) == 1:
            handles, _ = self.ax.get_legend_handles_labels()
            labels = items[0]
        else:
            handles, labels = items
        self._nameonly = opts.pop('nameonly', self._nameonly)
        if self._nameonly:
            labels = [basename(label) for label in labels]
        self._legend = self.ax.legend(handles, labels, **opts)
        self._legend.draggable(True)
        self.draw()
        return self._legend

    def remove_legend(self):
        """Remove the legend."""
        if self.ax.get_legend():
            self.ax.get_legend().remove()
        self._legend = None
        self._nameonly = False
        self.draw()

    def grid(self, display=None, minor=False, **opts):
        """Set grid display.
        
        Parameters
        ----------
        display : bool or None
            If True, the grid is displayed. If None, grid display is 
            toggled on or off.
        minor : bool or None
            If True, both major and minor gridlines are displayed.
        opts : dict
            Valid options for displaying grids. If not set, the default
            Matplotlib styles are used.
        """
        if display is True or display is False:
            self._grid = display
        elif opts:
            self._grid = True
        else:
            self._grid = not (self.ax.xaxis._gridOnMajor or
                              self.ax.yaxis._gridOnMajor)
        self._minorgrid = minor
        if self._grid:
            self.ax.xaxis._gridOnMajor = self.ax.yaxis._gridOnMajor = True
            if 'linestyle' in opts:
                self._gridstyle = opts['linestyle']
            else:
                opts['linestyle'] = self._gridstyle
            if 'linewidth' in opts:
                self._gridwidth = opts['linewidth']
            else:
                opts['linewidth'] = self._gridwidth
            if 'color' in opts:
                self._gridcolor = opts['color']
            else:
                opts['color'] = self._gridcolor
            if minor:
                self.ax.xaxis._gridOnMinor = True
                self.ax.yaxis._gridOnMinor = True
                self.ax.minorticks_on()
            else:
                self.ax.xaxis._gridOnMinor = False
                self.ax.yaxis._gridOnMinor = False
                self.ax.minorticks_off()            
            if self.skew:
                self.draw_skewed_grid(minor=minor, **opts)
            else:
                self.ax.grid(self._grid, which='major', axis='both', **opts)
                if minor:
                    opts['linewidth'] = max(self._gridwidth/2, 0.1)
                    self.ax.grid(True, which='minor', axis='both', **opts)
                self.remove_skewed_grid()
        else:
            self.ax.xaxis._gridOnMajor = self.ax.yaxis._gridOnMajor = False
            self.ax.xaxis._gridOnMinor = self.ax.yaxis._gridOnMinor = False
            self.ax.grid(False, which='both', axis='both')
            if self.skew:
                self.remove_skewed_grid()
        self.draw()
        self.update_customize_panel()

    def draw_skewed_grid(self, minor=False, **opts):
        self.remove_skewed_grid()
        self._majorlines = (
            self.xlines(self.ax.xaxis.get_majorticklocs(), **opts) +
            self.ylines(self.ax.yaxis.get_majorticklocs(), **opts))
        if minor:
            opts['linewidth'] = max(self._gridwidth/2, 0.1)
            self._minorlines = (
                self.xlines(self.ax.xaxis.get_minorticklocs(), **opts) +
                self.ylines(self.ax.yaxis.get_minorticklocs(), **opts))

    def remove_skewed_grid(self, major=True, minor=True):
        if major:
            for line in self._majorlines:
                try:
                    line.remove()
                except Exception:
                    pass
        if minor:
            for line in self._minorlines:
                try:
                    line.remove()
                except Exception:
                    pass
        self._majorlines = self._minorlines = []

    def vlines(self, x, ymin=None, ymax=None, y=None, **opts):
        """Plot vertical lines at x-value(s).
        
        Parameters
        ----------
        x : float or list of floats or ndarray
            x-values of vertical line(s)
        y : float
            y-value at which the x-value is determined. This is only 
            required if the plot is skewed.
        ymin : float
            Minimum y-value of vertical line. Defaults to plot minimum.
        ymax : float
            Maximum y-value of vertical line. Defaults to plot maximum.
        opts : dict
            Valid options for displaying lines.

        Returns
        -------
        lines : Matplotlib LineCollection
            Collection of vertical lines.
        """
        if ymin is None:
            ymin = self.ax.get_ylim()[0]
        if ymax is None:
            ymax = self.ax.get_ylim()[1]
        if self.skew is not None and y is not None:
            x, _ = self.transform(x, y)
        lines = self.ax.vlines(x, ymin, ymax, **opts)
        self.canvas.draw()
        self.shapes.append(lines)
        return lines

    vline = vlines

    def hlines(self, y, xmin=None, xmax=None, x=None, **opts):
        """Plot horizontal line at y-value(s).
        
        Parameters
        ----------
        y : float or list of floats or ndarray
            y-values of horizontal line(s)
        x : float
            x-value at which the y-value is determined. This is only 
            required if the plot is skewed.
        xmin : float
            Minimum x-value of horizontal line. Defaults to plot 
            minimum.
        xmax : float
            Maximum x-value of horizontal line. Defaults to plot 
            maximum.
        opts : dict
            Valid options for displaying lines.

        Returns
        -------
        lines : Matplotlib LineCollection
            Collection of horizontal lines.
        """
        if xmin is None:
            xmin = self.ax.get_xlim()[0]
        if xmax is None:
            xmax = self.ax.get_xlim()[1]
        if self.skew is not None and x is not None:
            _, y = self.transform(x, y)
        lines = self.ax.hlines(y, xmin, xmax, **opts)
        self.canvas.draw()
        self.shapes.append(lines)
        return lines

    hline = hlines

    def crosshairs(self, x, y, **opts):
        """Plot crosshairs centered at (x,y).
        
        Parameters
        ----------
        x : float
            x-value of vertical line
        y : float
            y-value of horizontal line
        opts : dict
            Valid options for displaying lines.

        Returns
        -------
        lines : list
            List containing line collections of vertical and horizontal lines.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        crosshairs = []
        crosshairs.append(self.vline(float(x), **opts))
        crosshairs.append(self.hline(float(y), **opts))
        return crosshairs

    def xlines(self, x, ymin=None, ymax=None, **opts):
        """Plot line at constant x-values.
        
        This is similar to vlines, but the line will be skewed if the 
        plot is skewed.
        
        Parameters
        ----------
        x : float or list of floats or ndarray
            x-value of vertical line
        ymin : float
            Minimum y-value of vertical line. Defaults to plot minimum.
        ymax : float
            Maximum y-value of vertical line. Defaults to plot maximum.
        opts : dict
            Valid options for displaying lines.

        Returns
        -------
        line : Line2D
            Matplotlib line object.
        """
        y0, y1 = self.yaxis.min, self.yaxis.max
        if ymin is None:
            ymin = y0
        if ymax is None:
            ymax = y1
        if self.skew is None:
            return self.vlines(x, ymin, ymax, **opts)
        else:
            if not iterable(x):
                x = [x]
            x0, y0 = self.transform(x, ymin)
            x1, y1 = self.transform(x, ymax)
            lines = []
            for i in range(len(x0)):
                line = Line2D([x0[i],x1[i]], [y0,y1], **opts)
                self.ax.add_line(line)
                lines.append(line)
            self.canvas.draw()
            self.shapes.append(lines)
            return lines

    xline = xlines

    def ylines(self, y, xmin=None, xmax=None, **opts):
        """Plot line at constant y-value.
        
        This is similar to hlines, but the line will be skewed if the 
        plot is skewed.
        
        Parameters
        ----------
        y : float or list of floats or ndarray
            y-value of vertical line
        xmin : float
            Minimum x-value of horizontal line. Defaults to plot 
            minimum.
        xmax : float
            Maximum x-value of horizontal line. Defaults to plot 
            maximum.
        opts : dict
            Valid options for displaying lines.

        Returns
        -------
        line : Line2D
            Matplotlib line object.
        """
        x0, x1 = self.xaxis.min, self.xaxis.max
        if xmin is None:
            xmin = x0
        if xmax is None:
            xmax = x1
        if self.skew is None:
            return self.hline(y, xmin, xmax, **opts)
        else:
            if not iterable(y):
                y = [y]
            x0, y0 = self.transform(xmin, y)
            x1, y1 = self.transform(xmax, y)
            lines = []
            for i in range(len(y0)):
                line = Line2D([x0[i], x1[i]], [y0[i], y1[i]], **opts)
                self.ax.add_line(line)
                lines.append(line)
            self.canvas.draw()
            self.shapes.append(lines)
            return lines

    yline = ylines

    def rectangle(self, x, y, dx, dy, **opts):
        """Plot rectangle.
        
        Note
        ----
        The rectangle will be skewed if the plot is skewed.
        
        Parameters
        ----------
        x, y : float
            x and y values of lower left corner
        dx, dy : float
            x and y widths of rectangle
        opts : dict
            Valid options for displaying shapes.

        Returns
        -------
        rectangle : Polygon
            Matplotlib polygon object.
        """
        if self.skew is None:
            rectangle = self.ax.add_patch(Rectangle((float(x),float(y)),
                                          float(dx), float(dy), **opts))
        else:
            xc, yc = [x, x, x+dx, x+dx], [y, y+dy, y+dy, y]
            xy = [self.transform(_x, _y) for _x,_y in zip(xc,yc)]
            rectangle = self.ax.add_patch(Polygon(xy, True, **opts))
        if 'linewidth' not in opts:
            rectangle.set_linewidth(1.0)
        if 'facecolor' not in opts:
            rectangle.set_facecolor('none')
        self.canvas.draw()
        self.shapes.append(rectangle)
        return rectangle

    def polygon(self, xy, closed=True, **opts):
        """Plot closed polygon.
        
        Note
        ----
        The polygon will be skewed if the plot is skewed.
        
        Parameters
        ----------
        xy : tuple
            x and y coordinates as a tuple of paired floats
        closed : bool
            True if the polygon is closed
        opts : dict
            Valid options for displaying shapes.

        Returns
        -------
        rectangle : Polygon
            Matplotlib polygon object.
        """
        if self.skew is not None:
            xy = [self.transform(_x, _y) for _x,_y in xy]
        polygon = self.ax.add_patch(Polygon(xy, closed, **opts))
        if 'linewidth' not in opts:
            polygon.set_linewidth(1.0)
        if 'facecolor' not in opts:
            polygon.set_facecolor('none')
        self.canvas.draw()
        self.shapes.append(polygon)
        return polygon

    def ellipse(self, x, y, dx, dy, **opts):
        """Plot ellipse.
        
        Parameters
        ----------
        x, y : float
            x and y values of ellipse center
        dx, dy : float
            x and y widths of ellipse
        opts : dict
            Valid options for displaying shapes.

        Returns
        -------
        ellipse : Ellipse
            Matplotlib ellipse object.

        Notes
        -----
        The ellipse will be skewed if the plot is skewed.        
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        ellipse = self.ax.add_patch(Ellipse((float(x),float(y)), 
                                             float(dx), float(dy), **opts))
        if 'linewidth' not in opts:
            ellipse.set_linewidth(1.0)
        if 'facecolor' not in opts:
            ellipse.set_facecolor('none')
        self.canvas.draw()
        self.shapes.append(ellipse)
        return ellipse

    def circle(self, x, y, radius, **opts):
        """Plot circle.
        
        Parameters
        ----------
        x, y : float
            x and y values of center of circle.
        radius : float
            radius of circle.
        opts : dict
            Valid options for displaying shapes.

        Returns
        -------
        circle : Circle
            Matplotlib circle object.

        Notes
        -----
        This assumes that the unit lengths of the x and y axes are the 
        same. The circle will be skewed if the plot is skewed.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        circle = self.ax.add_patch(Circle((float(x),float(y)), radius,
                                              **opts))
        if 'linewidth' not in opts:
            circle.set_linewidth(1.0)
        if 'facecolor' not in opts:
            circle.set_facecolor('r')
        if 'edgecolor' not in opts:
            circle.set_edgecolor('k')
        self.canvas.draw()
        self.shapes.append(circle)
        return circle

    def voronoi(self, x, y, z, **opts):
        """Output Voronoi plot based z(x,y) where x and y are pixel centers.

        Parameters
        ----------
        x, y : NXfield
            x and y values of pixel centers - one-dimensional
        z : NXfield
            intensity of pixels - two-dimensional
        """
        self.signal = z
        self.axes = [y.average(1), x.average(0)]
        self.x = self.axes[1].nxdata
        self.y = self.axes[0].nxdata
        self.v = self.signal.nxdata
        self.axis['signal'] = self.vaxis = NXPlotAxis(self.signal)
        self.axis[1] = self.xaxis = NXPlotAxis(self.axes[1])
        self.axis[0] = self.yaxis = NXPlotAxis(self.axes[0])
        
        self.figure.clf()
        x, y, z = x.nxdata, y.nxdata, z.nxdata
        vor = Voronoi([(x[i,j],y[i,j]) for i in range(z.shape[0]) 
                                       for j in range(z.shape[1])])
        if 'show_vertices' not in opts:
            opts['show_vertices'] = False
        if 'show_points' not in opts:
            opts['show_points'] = False
        if 'line_width' not in opts:
            opts['line_width'] = 0.2        
        voronoi_plot_2d(vor, ax=self.ax, **opts)
        z = z.flatten()
        self.vaxis.min = self.vaxis.lo = z.min()
        self.vaxis.max = self.vaxis.hi = z.max()
        self.set_data_norm()
        mapper = mpl.cm.ScalarMappable(norm=self.norm, cmap=self.cmap)
        mapper.set_array(z)
        for r in range(len(vor.point_region)):
            region = vor.regions[vor.point_region[r]]
            polygon = [vor.vertices[i] for i in region if i != -1]
            self.ax.fill(*zip(*polygon), color=mapper.to_rgba(z[r]))
        self.colorbar = self.figure.colorbar(mapper)
        self.xaxis.lo, self.xaxis.hi = x.min(), x.max()
        self.yaxis.lo, self.yaxis.hi = y.min(), y.max()
        self.ax.set_xlabel(self.xaxis.label)
        self.ax.set_ylabel(self.yaxis.label)
        self.ax.set_title('Voronoi Plot')
        self.limits = (self.xaxis.min, self.xaxis.max,
                       self.yaxis.min, self.yaxis.max)
        self.init_tabs()
        self.draw()
        self.otab.push_current()

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
                    self.tab_widget.insertTab(
                        self.tab_widget.indexOf(self.otab),
                        self.ptab, 'projections')
                self.ptab.set_axes()
                self.zoom = None
            if self.ndim > 2:
                self.ztab.set_axis(self.zaxis)
                self.ztab.locked = True
                self.ztab.pause()
                self.ztab.scalebox.setChecked(True)
                if self.tab_widget.indexOf(self.ztab) == -1:
                    self.tab_widget.insertTab(
                        self.tab_widget.indexOf(self.ptab),
                        self.ztab, 'z')
            else:
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.xtab.logbox.setVisible(True)
            self.xtab.axiscombo.setVisible(True)
            self.xtab.flipbox.setVisible(True)
            self.ytab.logbox.setVisible(True)
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
        if self.mask_panel:
            self.mask_panel.close()

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
        """Replace the axis in a plot tab.
        
        Parameters
        ----------
        tab : NXPlotTab
            Tab containing the axis to be changed
        axis : NXPlotAxis
            Axis that replaces the current selection in the tab
        """
        xmin, xmax, ymin, ymax = self.limits
        if ((tab == self.xtab and axis == self.xaxis) or
            (tab == self.ytab and axis == self.yaxis)):
            return
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
            if self.ndim == 1:
                return 'x={:.4g} y={:.4g}'.format(x, y)
            else:
                x, y = self.inverse_transform(x, y)
                if self.xaxis.reversed:
                    col = np.searchsorted(x-self.xaxis.boundaries, 0.0) - 1
                else:
                    col = np.searchsorted(self.xaxis.boundaries-x, 0.0) - 1
                if self.yaxis.reversed:
                    row = np.searchsorted(y-self.yaxis.boundaries, 0.0) - 1
                else:
                    row = np.searchsorted(self.yaxis.boundaries-y, 0.0) - 1
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
        if self.mask_panel:
            self.mask_panel.close()
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
    axis : NXfield
        Field containing the axis values and metadata.
    name : str
        The axis field name.
    data : ndarray
        The axis values.
    dim : int
        Dimension value
    dimlen : int
        Length of equivalent dimension in the signal array. This is used 
        to determine if the axis values are bin centers or boundaries.

    Attributes
    ----------
    name : str
        Axis name.
    data : ndarray
        Array of axis values.
    dim : int
        No. of the axis dimensions (not currently used).
    reversed : bool
        True if the axis values fall with increasing array index.
    equally_spaced : bool
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
                    self.min = np.min(
                        self.boundaries[np.isfinite(self.boundaries)])
                    self.max = np.max(
                        self.boundaries[np.isfinite(self.boundaries)])
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

    def log_limits(self):
        """Return limits with positive values."""
        try:
            minpos = min(self.data[self.data>0.0])
        except ValueError:
            minpos = 1e-300
        return (minpos if self.lo <= 0 else self.lo,
                minpos if self.hi <= 0 else self.hi)

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
    name : str
        Name of the axis.
    axis : bool
        If True, this tab represents a plotted axis.
    log : bool
        If True, a log checkbox should be included.
    zaxis : bool
        If True, this is a tab for selecting the z-axis.
    image : bool
        If True, this is a tab for defining signal options, such as the
        color map or interpolation method.
    plotview : NXPlotView
        Parent window containing this tab.

    Attributes
    ----------
    name : str
        Name of the axis
    plotview : NXPlotView
        Parent window.
    minbox, maxbox : NXSpinBox, NXDoubleSpinBox
        Text boxes for defining the minimum and maximum plot values.
    minslider, maxslider : QSlider
        Sliders for adjusting minimum and maximum plot values.
    """
    def __init__(self, name=None, axis=True, log=True, zaxis=False, image=False,
                 plotview=None):

        super(NXPlotTab, self).__init__()

        self.name = name
        self.plotview = plotview

        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.setMinimumHeight(51)
        hbox = QtWidgets.QHBoxLayout()
        widgets = []

        if axis:
            self.axiscombo = NXComboBox(self.change_axis)
            widgets.append(self.axiscombo)
        else:
            self.axiscombo = None
        if zaxis:
            self.zaxis = True
            self.minbox = self.spinbox(self.read_minbox)
            self.maxbox = self.spinbox(self.read_maxbox)
            self.lockbox = NXCheckBox("Lock", self.change_lock)
            self.lockbox.setChecked(True)
            self.scalebox = NXCheckBox("Autoscale", self.plotview.replot_image)
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
                self.logbox = NXCheckBox("Log", self.change_log)
                self.logbox.setChecked(False)
            else:
                self.logbox = None
            self.flipbox = NXCheckBox("Flip", self.flip_axis)
            widgets.append(self.minbox)
            widgets.extend([self.minslider, self.maxslider])
            widgets.append(self.maxbox)
            if log:
                widgets.append(self.logbox)
            widgets.append(self.flipbox)
            self.lockbox = self.scalebox = None
        if image:
            self.cmapcombo = NXComboBox(self.change_cmap, cmaps, default_cmap)
            self._cached_cmap = default_cmap
            if cmaps.index('spring') > 0:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('spring'))
            if cmaps.index('seismic') > 0:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('seismic'))
            widgets.append(self.cmapcombo)
            self.interpcombo = NXComboBox(self.change_interpolation, 
                                          interpolations, default_interpolation)
            self._cached_interpolation = default_interpolation
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
        axis : NXPlotAxis
            Axis values to be applied to this tab.
        """
        self.block_signals(True)
        self.axis = axis
        if self.zaxis:
            self.minbox.data = self.maxbox.data = self.axis.centers
            self.minbox.setRange(0, len(self.minbox.data)-1)
            self.maxbox.setRange(0, len(self.maxbox.data)-1)
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
            if np.all(self.axis.data <= 0.0):
                self.logbox.setChecked(False)
                self.logbox.setEnabled(False)
            else:
                if self.name != 'v':
                    self.logbox.setChecked(False)
                self.logbox.setEnabled(True)
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
            if self._cached_interpolation in self.plotview.interpolations:
                self.interpcombo.setCurrentIndex(
                    self.interpcombo.findText(self._cached_interpolation))
            else:
                self.interpcombo.setCurrentIndex(
                    self.interpcombo.findText(default_interpolation))
        self.block_signals(False)

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
        slider.setFocusPolicy(QtCore.Qt.NoFocus)
        slider.setMinimumWidth(100)
        slider.setRange(0, 1000)
        slider.setSingleStep(5)
        slider.setValue(0)
        slider.setTracking(True)
        slider.sliderReleased.connect(slot)
        if self.name != 'v':
            slider.sliderMoved.connect(slot)
        return slider

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
            else:
                self.axis.hi = hi
                if hi < self.axis.lo:
                    self.axis.lo = self.axis.data.min()
                    self.minbox.setValue(self.axis.lo)
                    self.minbox.old_value = self.axis.lo
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
                self.axis.hi = hi
                if self.axis.hi < self.axis.lo:
                    self.axis.lo = self.axis.hi
                    self.minbox.setValue(self.axis.lo)
                    self.minbox.old_value = self.axis.lo
                elif np.isclose(self.axis.lo, self.axis.hi):
                    self.replotSignal.replot.emit()
        self.maxbox.old_value = self.axis.hi

    @QtCore.Slot()
    def read_minbox(self):
        lo = self.minbox.value()
        if not self.minbox.isEnabled() or self.axis.locked or \
            np.isclose(lo, self.minbox.old_value):
            return
        if self.name == 'x' or self.name == 'y' or self.name == 'v':
            self.axis.lo = lo
            if lo > self.axis.hi:
                self.axis.hi = self.axis.max = self.axis.data.max()
                self.maxbox.setValue(self.axis.hi)
                self.maxbox.old_value = self.axis.hi
            self.axis.min = self.axis.lo
            self.set_range()
            self.set_sliders(self.axis.lo, self.axis.hi)
            if self.name == 'v':
                self.plotview.autoscale = False
                self.plotview.replot_image()
            else:
                self.plotview.replot_axes()
        else:
            self.axis.lo = lo
            if lo > self.axis.hi:
                self.axis.hi = self.axis.lo
                self.maxbox.setValue(self.axis.hi)
                self.maxbox.old_value = self.axis.hi
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
            self.axis.hi = self.axis.lo + max(
                (self.maxslider.value()*_range/1000), self.axis.min_range)
            self.maxbox.setValue(self.axis.hi)
            _range = max(self.axis.hi - self.axis.min, self.axis.min_range)
            try:
                self.minslider.setValue(1000*(self.axis.lo - self.axis.min) / 
                                        _range)
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
        if self.minslider: 
            self.minslider.blockSignals(block)
        if self.maxslider: 
            self.maxslider.blockSignals(block)
        if self.logbox:
            self.logbox.blockSignals(block)

    def _log(self):
        try:
            return self.logbox.isChecked()
        except Exception:
            return False

    def _set_log(self, value):
        if value and np.all(self.axis.data <= 0.0):
            raise NeXusError("Cannot set log axis when all values are <= 0")
        try:
            if value != self.log:
                self.logbox.setChecked(value)
        except Exception:
            pass
    
    log = property(_log, _set_log, "Property: Log scale")

    def change_log(self):
        try:
            self.plotview.set_log_axis(self.name)
            self.plotview.replot_axes()
        except Exception:
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
            self.axis.min, self.axis.max = nonsingular(self.axis.min, 
                                                       self.axis.max)
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
        self.cmap = self.cmapcombo.currentText()

    def _cmap(self):
        """Return the currently selected color map."""
        return self.cmapcombo.currentText()

    def _set_cmap(self, cmap):
        """Set the color map.
        
        If the color map is available but was not included in the 
        default list when NeXpy was launched, it is added to the list.
        """
        cm = get_cmap(cmap)
        cmap = cm.name
        if cmap != self._cached_cmap:
            idx = self.cmapcombo.findText(cmap)
            if idx < 0:
                if cmap in cmap_d:
                    self.cmapcombo.insertItem(5, cmap)
                    self.cmapcombo.setCurrentIndex(
                        self.cmapcombo.findText(cmap))
                else:
                    raise NeXusError("Invalid Color Map")
            else:
                self.cmapcombo.setCurrentIndex(idx)
            cm.set_bad('k', 1)
            self.plotview.image.set_cmap(cm)
            if self.symmetric:
                self.symmetrize()
                self.plotview.x, self.plotview.y, self.plotview.v = \
                    self.plotview.get_image()
                self.plotview.replot_image()
            else:
                self.minbox.setDisabled(False)
                self.minslider.setDisabled(False)
                if self.is_symmetric_cmap(self._cached_cmap):
                    self.axis.lo = None
                self.plotview.replot_image()
            self._cached_cmap = self.cmap

    cmap = property(_cmap, _set_cmap, "Property: Image color map")
    
    @property
    def symmetric(self):
        """Return True if a divergent color map has been selected."""
        return self.is_symmetric_cmap(self.cmap)

    def is_symmetric_cmap(self, cmap):
        if (self.cmapcombo is not None and
            self.cmapcombo.findText(cmap) >= 
            self.cmapcombo.findText('seismic')):
            return True
        else:
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
        self.interpolation = self.interpcombo.currentText()

    def _interpolation(self):
        return self.interpcombo.currentText()

    def _set_interpolation(self, interpolation):
        if interpolation != self._cached_interpolation:
            idx = self.interpcombo.findText(interpolation)
            if idx >= 0:
                self.interpcombo.setCurrentIndex(idx)
                self._cached_interpolation = interpolation
            else:
                self.interpcombo.setCurrentIndex(0)
            self._cached_interpolation = interpolation
            self.plotview.interpolate()
            self._cached_interpolation = self.interpolation

    interpolation = property(_interpolation, _set_interpolation, 
                             "Property: Image color map")

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
        if self.plotview.ndim < 3:
            return
        try:
            self.maxbox.stepBy(self.playsteps)
            if self.maxbox.pause:
                self.pause()
        except Exception:
            self.pause()
            six.reraise(*sys.exc_info())                        

    def playback(self):
        if self.plotview.ndim < 3:
            return
        try:
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
        except Exception:
            self.pause()
            six.reraise(*sys.exc_info())            

    def pause(self):
        self.playsteps = 0
        self.playback_action.setChecked(False)
        self.playforward_action.setChecked(False)
        self.timer.stop()

    def playforward(self):
        if self.plotview.ndim < 3:
            return
        try:
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
        except Exception:
            self.pause()
            six.reraise(*sys.exc_info())            
            

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
    data : ndarray
        Values of data to be adjusted by the spin box.

    Attributes
    ----------
    data : array
        Data values.
    validator : QDoubleValidator
        Function to ensure only floating point values are entered.
    old_value : float
        Previously stored value.
    diff : float
        Difference between maximum and minimum values when the box is
        locked.
    pause : bool
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


class NXComboBox(QtWidgets.QComboBox):

    def __init__(self, slot=None, items=[], default=None):
        super(NXComboBox, self).__init__()
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumWidth(100)
        if items:
            self.addItems(items)
            if default:
                self.setCurrentIndex(self.findText(default))
        if slot:
            self.activated.connect(slot)

    def keyPressEvent(self, event):
        if (event.key() == QtCore.Qt.Key_Up or 
            event.key() == QtCore.Qt.Key_Down):
            super(NXComboBox, self).keyPressEvent(event)
        elif (event.key() == QtCore.Qt.Key_Right or 
              event.key() == QtCore.Qt.Key_Left):
            self.showPopup()
        else:
            self.parent().keyPressEvent(event)


class NXCheckBox(QtWidgets.QCheckBox):

    def __init__(self, label=None, slot=None, checked=False):
        super(NXCheckBox, self).__init__(label)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setChecked(checked)
        if slot:
            self.stateChanged.connect(slot)

    def keyPressEvent(self, event):
        if (event.key() == QtCore.Qt.Key_Up or 
            event.key() == QtCore.Qt.Key_Down):
            if self.isChecked():
                self.setCheckState(QtCore.Qt.Unchecked)
            else:
                self.setCheckState(QtCore.Qt.Checked)
        else:
            self.parent().keyPressEvent(event)


class NXPushButton(QtWidgets.QPushButton):

    def __init__(self, label, slot, parent=None):
        """Return a QPushButton with the specified label and slot."""
        super(NXPushButton, self).__init__(label, parent)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setDefault(False)
        self.setAutoDefault(False)
        self.clicked.connect(slot)

    def keyPressEvent(self, event):
        if (event.key() == QtCore.Qt.Key_Return or 
            event.key() == QtCore.Qt.Key_Enter or
            event.key() == QtCore.Qt.Key_Space):
            self.clicked.emit()
        else:
            self.parent().keyPressEvent(event)


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


class NXProjectionTab(QtWidgets.QWidget):

    def __init__(self, plotview=None):

        super(NXProjectionTab, self).__init__()

        self.plotview = plotview

        hbox = QtWidgets.QHBoxLayout()
        widgets = []

        self.xbox = NXComboBox(self.set_xaxis)
        widgets.append(QtWidgets.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = NXComboBox(self.set_yaxis)
        self.ylabel = QtWidgets.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)

        self.save_button = NXPushButton("Save", self.save_projection, self)
        widgets.append(self.save_button)

        self.plot_button = NXPushButton("Plot", self.plot_projection, self)
        widgets.append(self.plot_button)

        self.sumbox = NXCheckBox("Sum", self.plotview.replot_data)
        widgets.append(self.sumbox)

        self.overplot_box = NXCheckBox("Over")
        if 'Projection' not in plotviews:
            self.overplot_box.setVisible(False)
        widgets.append(self.overplot_box)

        self.panel_button = NXPushButton("Open Panel", self.open_panel, self)
        widgets.append(self.panel_button)

        hbox.addStretch()
        for w in widgets:
            hbox.addWidget(w)
            hbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        hbox.addStretch()

        self.setLayout(hbox)

        self.setTabOrder(self.xbox, self.ybox)
        self.setTabOrder(self.ybox, self.save_button)
        self.setTabOrder(self.save_button, self.plot_button)
        self.setTabOrder(self.plot_button, self.sumbox)
        self.setTabOrder(self.sumbox, self.overplot_box)
        self.setTabOrder(self.overplot_box, self.panel_button)

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
            self.ybox.setCurrentIndex(
                self.ybox.findText(self.plotview.yaxis.name))

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
        if (len(shape)-len(limits) > 0 and 
            len(shape)-len(limits) == shape.count(1)):
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
                        over=over, fmt='o')
        if len(axes) == 1:
            self.overplot_box.setVisible(True)
        else:
            self.overplot_box.setVisible(False)
            self.overplot_box.setChecked(False)
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

        self.xbox = NXComboBox(self.set_xaxis)
        widgets.append(QtWidgets.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = NXComboBox(self.set_yaxis)
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
            self.lockbox[axis] = NXCheckBox(slot=self.set_lock)
            grid.addWidget(QtWidgets.QLabel(self.plotview.axis[axis].name), 
                                            row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)
            grid.addWidget(self.lockbox[axis], row, 3,
                           alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.save_button = NXPushButton("Save", self.save_projection, self)
        grid.addWidget(self.save_button, row, 1)
        self.plot_button = NXPushButton("Plot", self.plot_projection, self)
        grid.addWidget(self.plot_button, row, 2)
        self.overplot_box = NXCheckBox()
        if 'Projection' not in plotviews:
            self.overplot_box.setVisible(False)
        grid.addWidget(self.overplot_box, row, 3,
                       alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.mask_button = NXPushButton("Mask", self.mask_data, self)
        grid.addWidget(self.mask_button, row, 1)
        self.unmask_button = NXPushButton("Unmask", self.unmask_data, self)
        grid.addWidget(self.unmask_button, row, 2)

        row += 1
        self.sumbox = NXCheckBox("Sum Projections")
        grid.addWidget(self.sumbox, row, 1, 1, 2, 
                       alignment=QtCore.Qt.AlignHCenter)

        layout.addLayout(grid)

        self.copy_row = QtWidgets.QWidget()
        copy_layout = QtWidgets.QHBoxLayout()
        self.copy_box = NXComboBox()
        self.copy_button = NXPushButton("Copy Limits", self.copy_limits, self)
        copy_layout.addStretch()
        copy_layout.addWidget(self.copy_box)
        copy_layout.addWidget(self.copy_button)
        copy_layout.addStretch()
        self.copy_row.setLayout(copy_layout)
        layout.addWidget(self.copy_row)

        button_layout = QtWidgets.QHBoxLayout()
        self.reset_button = NXPushButton("Reset Limits", self.reset_limits, 
                                         self)
        self.rectangle_button = NXPushButton("Hide Limits", 
                                             self.toggle_rectangle, self)
        self.close_button = NXPushButton("Close Panel", self.close, self)
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

        self.xbox.setFocus()

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
            self.ybox.setCurrentIndex(
                self.ybox.findText(self.plotview.yaxis.name))

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
                self.maxbox[axis].setValue(self.minbox[axis].value())
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
                self.minbox[axis].diff = self.maxbox[axis].diff = max(hi - lo, 
                                                                      0.0)
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
        if (len(shape)-len(limits) > 0 and 
            len(shape)-len(limits) == shape.count(1)):
            axes, limits = fix_projection(shape, axes, limits)
        if self.plotview.rgb_image:
            limits.append((None, None))
        return axes, limits

    def save_projection(self):
        try:
            axes, limits = self.get_projection()
            keep_data(self.plotview.data.project(axes, limits,
                                                 summed=self.summed))
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
                            over=over, fmt='o')
            if len(axes) == 1:
                self.overplot_box.setVisible(True)
            else:
                self.overplot_box.setVisible(False)
                self.overplot_box.setChecked(False)
            projection.make_active()
            projection.raise_()
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
            if not self.plotview.data.nxsignal.mask.any():
                self.plotview.data.mask = np.ma.nomask
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
            ('Subplots', 'Configure subplots', 'subplots', 
             'configure_subplots'),
            ('Save', 'Save the figure', 'filesave', 'save_figure'),
            ('Add', 'Add plot data to tree', 'hand', 'add_data')
                )
        super(NXNavigationToolbar, self)._init_toolbar()
        self._actions['set_aspect'].setCheckable(True)
        for action in self.findChildren(QtWidgets.QAction):
            if action.text() == 'Customize':
                action.setToolTip('Customize plot')

    def home(self, autoscale=True):
        """Redraw the plot with the original limits.
        
        This also redraws the grid, if the axes are skewed, since this is not
        automatically handled by Matplotlib.
        
        Parameters
        ----------
        autoscale : bool, optional
            If False, only the x and y axis limits are reset. 
        """
        self.plotview.reset_plot_limits(autoscale)
        if self.plotview.skew:
            self.plotview.grid(self.plotview._grid, self.plotview._minorgrid)

    def edit_parameters(self):
        if self.plotview.customize_panel is None:
            from .datadialogs import CustomizeDialog
            self.plotview.customize_panel = CustomizeDialog(
                parent=self.plotview)
            self.plotview.customize_panel.show()
        else:
            self.plotview.customize_panel.raise_()

    def add_data(self):
        keep_data(self.plotview.plotdata)

    def release(self, event):
        try:
            for zoom_id in self._ids_zoom:
                self.canvas.mpl_disconnect(zoom_id)
            self.remove_rubberband()
        except Exception as error:
            pass
        self._ids_zoom = []
        self._xypress = None
        self._button_pressed = None
        self._zoom_mode = None
        self.plotview.x, self.plotview.y = None, None
        super(NXNavigationToolbar, self).release(event)

    def release_zoom(self, event):
        """The release mouse button callback in zoom to rect mode."""
        if event.button == 1:
            super(NXNavigationToolbar, self).release_zoom(event)
            self._update_release()
            if self.plotview.ndim > 1 and self.plotview.label != "Projection":
                self.plotview.tab_widget.setCurrentWidget(self.plotview.ptab)
        elif event.button == 3:
            if self.plotview.ndim == 1 or not event.inaxes:
                self.home()
            elif (self.plotview.x and self.plotview.y and
                  abs(event.x - self.plotview.x) < 5 and
                  abs(event.y - self.plotview.y) < 5):
                self.home(autoscale=False)
            elif self.plotview.xdata and self.plotview.ydata:
                self.plotview.ptab.open_panel()
                xmin, xmax = sorted([event.xdata, self.plotview.xdata])
                ymin, ymax = sorted([event.ydata, self.plotview.ydata])
                xp, yp = self.plotview.xaxis.dim, self.plotview.yaxis.dim
                self.plotview.projection_panel.maxbox[xp].setValue(str(xmax))
                self.plotview.projection_panel.minbox[xp].setValue(str(xmin))
                self.plotview.projection_panel.maxbox[yp].setValue(str(ymax))
                self.plotview.projection_panel.minbox[yp].setValue(str(ymin))
        self.release(event)

    def release_pan(self, event):
        super(NXNavigationToolbar, self).release_pan(event)
        self._update_release()

    def _update_release(self):
        xmin, xmax = self.plotview.ax.get_xlim()
        ymin, ymax = self.plotview.ax.get_ylim()
        xmin, ymin = self.plotview.inverse_transform(xmin, ymin)
        xmax, ymax = self.plotview.inverse_transform(xmax, ymax)
        self.plotview.xtab.set_limits(xmin, xmax)
        self.plotview.ytab.set_limits(ymin, ymax)
        try:
            xdim = self.plotview.xtab.axis.dim
            ydim = self.plotview.ytab.axis.dim
        except AttributeError:
            return
        self.plotview.zoom = {'x': (xdim, xmin, xmax),
                              'y': (ydim, ymin, ymax)}

    def _update_view(self):
        super(NXNavigationToolbar, self)._update_view()
        xmin, xmax = self.plotview.ax.get_xlim()
        ymin, ymax = self.plotview.ax.get_ylim()
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

    def toggle_aspect(self):
        try:
            if self._actions['set_aspect'].isChecked():
                self.plotview.aspect = 'auto'
            else: 
                self.plotview.aspect = 'equal'
        except NeXusError as error:
            self._actions['set_aspect'].setChecked(False)
            report_error("Setting Aspect Ratio", error)
    
    def set_aspect(self):
        try:
            if self._actions['set_aspect'].isChecked():
                self.plotview.aspect = 'equal'
            else:
                self.plotview.aspect = 'auto'
        except NeXusError as error:
            self._actions['set_aspect'].setChecked(False)
            report_error("Setting Aspect Ratio", error)

    def mouse_move(self, event):
        self._set_cursor(event)
        if event.inaxes and event.inaxes.get_navigate():
            try:
                s = self.plotview.format_coord(event.xdata, event.ydata)
            except (ValueError, OverflowError):
                pass
            self.set_message(s)
            self.plotview.canvas.setFocus()
        else:
            self.set_message('')


class NXpatch(object):
    """Class for a draggable shape on the NXPlotView canvas"""
    lock = None
     
    def __init__(self, shape, border_tol=0.1, plotview=None):
        if plotview:
            self.plotview = get_plotview()
        self.canvas = self.plotview.canvas
        self.shape = shape
        self.border_tol = border_tol
        self.press = None
        self.background = None
        self.allow_resize = True
        self._active = None
        self.plotview.ax.add_patch(self.shape)

    def connect(self):
        'connect to all the events we need'
        self.plotview.deactivate()
        self.cidpress = self.canvas.mpl_connect(
            'button_press_event', self.on_press)
        self.cidrelease = self.canvas.mpl_connect(
            'button_release_event', self.on_release)
        self.cidmotion = self.canvas.mpl_connect(
            'motion_notify_event', self.on_motion)

    def is_inside(self, event):
        if event.inaxes != self.shape.axes: 
            return False
        contains, attrd = self.shape.contains(event)
        if contains:
            return True
        else:
            return False

    def initialize(self, xp, yp):
        """Function to be overridden by shape sub-class."""

    def update(self, x, y):
        """Function to be overridden by shape sub-class"""

    def on_press(self, event):
        'on button press we will see if the mouse is over us and store some data'
        if not self.is_inside(event):
            self.press = None
            return
        self.press = self.initialize(event.xdata, event.ydata)
        self.canvas.draw()

    def on_motion(self, event):
        """on motion we will move the rect if the mouse is over us"""
        if self.press is None: 
            return
        if event.inaxes != self.shape.axes: 
            return
        self.update(event.xdata, event.ydata)
        self.canvas.draw()

    def on_release(self, event):
        'on release we reset the press data'
        if self.press is None:
            return
        self.press = None
        self.canvas.draw()

    def disconnect(self):
        'disconnect all the stored connection ids'
        self.canvas.mpl_disconnect(self.cidpress)
        self.canvas.mpl_disconnect(self.cidrelease)
        self.canvas.mpl_disconnect(self.cidmotion)
        self.plotview.activate()


class NXcircle(NXpatch):

    def __init__(self, x, y, radius, border_tol=0.1, plotview=None, **opts):
        shape = Circle((float(x),float(y)), radius, **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'facecolor' not in opts:
            shape.set_facecolor('r')
        super(NXcircle, self).__init__(shape, border_tol, plotview)
        self.shape.set_label('Circle')
        self.circle = self.shape

    def initialize(self, xp, yp):
        x0, y0 = self.circle.center
        r0 = self.circle.radius
        if (self.allow_resize and
            (np.sqrt((xp-x0)**2 + (yp-y0)**2) > r0 * (1-self.border_tol))):
            expand = True
        else:
            expand = False
        return x0, y0, r0, xp, yp, expand   

    def update(self, x, y):
        x0, y0, r0, xp, yp, expand = self.press
        dx, dy = (x-xp, y-yp)
        bt = self.border_tol
        if expand:
            radius = np.sqrt((xp + dx - x0)**2 + (yp + dy - y0)**2)
            self.shape.set_radius(radius)
        else:
            self.circle.center = (x0 + dx, y0 + dy)
            self.circle.set_radius(r0)


class NXrectangle(NXpatch):

    def __init__(self, x, y, dx, dy, border_tol=0.1, plotview=None, **opts):
        shape = Rectangle((float(x),float(y)), float(dx), float(dy), **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'facecolor' not in opts:
            shape.set_facecolor('r')
        super(NXrectangle, self).__init__(shape, border_tol, plotview)
        self.shape.set_label('Rectangle')
        self.rectangle = self.shape

    def initialize(self, xp, yp):
        x0, y0 = self.rectangle.xy
        w0, h0 = self.rectangle.get_width(), self.rectangle.get_height()
        bt = self.border_tol
        if (self.allow_resize and
            (abs(x0+np.true_divide(w0,2)-xp)>np.true_divide(w0,2)-bt*w0 or
             abs(y0+np.true_divide(h0,2)-yp)>np.true_divide(h0,2)-bt*h0)):
            expand = True
        else:
            expand = False
        return x0, y0, w0, h0, xp, yp, expand   

    def update(self, x, y):
        x0, y0, w0, h0, xp, yp, expand = self.press
        dx, dy = (x-xp, y-yp)
        bt = self.border_tol
        if expand:
            if abs(x0 - xp) < bt * w0:
                self.rectangle.set_x(x0+dx)
                self.rectangle.set_width(w0-dx)
            if abs(x0 + w0 - xp) < bt * w0:
                self.rectangle.set_width(w0+dx)
            elif abs(y0 - yp) < bt * h0:
                self.rectangle.set_y(y0+dy)
                self.rectangle.set_height(h0-dy)
            elif abs(y0 + h0 - yp) < bt * h0:
                self.rectangle.set_height(h0+dy)
        else:
            self.rectangle.set_x(x0+dx)
            self.rectangle.set_y(y0+dy)


class NXSymLogNorm(SymLogNorm):
    """
    A subclass of Matplotlib SymLogNorm containing a bug fix
    for backward compatibility to previous versions.
    """
    def __init__(self,  linthresh, linscale=1.0,
                 vmin=None, vmax=None, clip=False):
        super(NXSymLogNorm, self).__init__(linthresh, linscale, vmin, vmax, 
                                           clip)
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
    dimlen : int
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
    dimlen : int
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
    shape : tuple or list
        Shape of the signal.
    axes : list
        Original list of axis dimensions.
    limits : list
        Original list of slice limits.

    Returns
    -------
    fixed_axes : list
        List of axis dimensions restoring dimensions of size 1.
    fixed_limits : list
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
