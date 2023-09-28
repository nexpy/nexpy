# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

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
    keys are defined by the plot window labels.

"""
import copy
import numbers
import os
import warnings
from posixpath import basename, dirname

import matplotlib as mpl
import numpy as np
from matplotlib.backend_bases import FigureManagerBase, NavigationToolbar2
from matplotlib.backends.backend_qt import FigureManagerQT as FigureManager
from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.colors import LogNorm, Normalize, SymLogNorm
from matplotlib.figure import Figure
from matplotlib.image import imread
from matplotlib.lines import Line2D
from matplotlib.ticker import AutoLocator, LogLocator, ScalarFormatter
from pkg_resources import parse_version, resource_filename

from .pyqt import QtCore, QtGui, QtWidgets

try:
    from matplotlib.ticker import LogFormatterSciNotation as LogFormatter
except ImportError:
    from matplotlib.ticker import LogFormatter

from matplotlib.transforms import nonsingular
from mpl_toolkits.axisartist import Subplot
from mpl_toolkits.axisartist.grid_finder import MaxNLocator
from mpl_toolkits.axisartist.grid_helper_curvelinear import \
    GridHelperCurveLinear
from scipy.interpolate import interp1d
from scipy.spatial import Voronoi, voronoi_plot_2d

try:
    import mplcursors
except ImportError:
    mplcursors = None

from nexusformat.nexus import NeXusError, NXdata, NXfield

from .. import __version__
from .datadialogs import (CustomizeDialog, ExportDialog, LimitDialog,
                          ProjectionDialog, ScanDialog, StyleDialog)
from .utils import (boundaries, centers, divgray_map, find_nearest,
                    fix_projection, get_color, in_dark_mode, iterable,
                    keep_data, parula_map, report_error, report_exception,
                    xtec_map)
from .widgets import (NXCheckBox, NXcircle, NXComboBox, NXDoubleSpinBox,
                      NXellipse, NXLabel, NXpolygon, NXPushButton, NXrectangle,
                      NXSlider, NXSpinBox)

active_plotview = None
plotview = None
plotviews = {}

cmaps = ['viridis', 'inferno', 'magma', 'plasma',  # perceptually uniform
         'cividis', 'parula',
         'spring', 'summer', 'autumn', 'winter', 'cool', 'hot',  # sequential
         'bone', 'copper', 'gray', 'pink',
         'turbo', 'jet', 'spectral', 'rainbow', 'hsv',  # miscellaneous
         'tab10', 'tab20', 'xtec',  # qualitative
         'seismic', 'coolwarm', 'twilight', 'divgray',  # diverging
         'RdBu', 'RdYlBu', 'RdYlGn']

if parse_version(mpl.__version__) >= parse_version('3.5.0'):
    mpl.colormaps.register(parula_map())
    mpl.colormaps.register(xtec_map())
    mpl.colormaps.register(divgray_map())
    cmaps = [cm for cm in cmaps if cm in mpl.colormaps]
else:
    from matplotlib.cm import cmap_d, get_cmap, register_cmap
    register_cmap('parula', parula_map())
    register_cmap('xtec', xtec_map())
    register_cmap('divgray', divgray_map())
    cmaps = [cm for cm in cmaps if cm in cmap_d]

if 'viridis' in cmaps:
    default_cmap = 'viridis'
else:
    default_cmap = 'jet'
divergent_cmaps = ['seismic', 'coolwarm', 'twilight', 'divgray',
                   'RdBu', 'RdYlBu', 'RdYlGn',
                   'PiYG', 'PRGn', 'BrBG', 'PuOr', 'RdGy', 'Spectral', 'bwr']
qualitative_cmaps = ['tab10', 'tab20', 'xtec']
interpolations = [
    'nearest', 'bilinear', 'bicubic', 'spline16', 'spline36', 'hanning',
    'hamming', 'hermite', 'kaiser', 'quadric', 'catrom', 'gaussian', 'bessel',
    'mitchell', 'sinc', 'lanczos']
default_interpolation = 'nearest'
try:
    from astropy.convolution import Gaussian2DKernel, convolve
    interpolations.insert(1, 'convolve')
except ImportError:
    pass
linestyles = {'Solid': '-', 'Dashed': '--', 'DashDot': '-.', 'Dotted': ':',
              'LongDashed': (0, (8, 2)),
              'DenselyDotted': (0, (1, 1)),
              'DashDotDotted': (0, (3, 5, 1, 5, 1, 5)),
              'None': 'None'}
markers = {'.': 'point', ',': 'pixel', '+': 'plus', 'x': 'x',
           'o': 'circle', 's': 'square', 'D': 'diamond', 'H': 'hexagon',
           'v': 'triangle_down', '^': 'triangle_up', '<': 'triangle_left',
           '>': 'triangle_right', 'None': 'None'}
logo = imread(resource_filename(
              'nexpy.gui', 'resources/icon/NeXpy.png'))[180:880, 50:1010]
warnings.filterwarnings("ignore", category=DeprecationWarning)


def new_figure_manager(label=None, *args, **kwargs):
    """Create a new figure manager instance.

    A new figure number is generated. with numbers > 100 preserved for
    the Projection and Fit windows.

    Parameters
    ----------
    label : str
        The label used to define
    """
    if label is None:
        label = ''
    if label == 'Projection' or label == 'Scan' or label == 'Fit':
        nums = [plotviews[p].number for p in plotviews
                if plotviews[p].number > 100]
        if nums:
            num = max(nums) + 1
        else:
            num = 101
    else:
        nums = [plotviews[p].number for p in plotviews
                if plotviews[p].number < 100]
        if nums:
            missing_nums = sorted(
                set(range(nums[0], nums[-1]+1)).difference(nums))
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
    global plotview
    if label in plotviews:
        if plotviews[label].number < 101:
            plotviews[label].make_active()
            plotview = plotviews[label]
    else:
        plotview = NXPlotView(label)
    return plotview


def get_plotview():
    """Return the currently active plotting window."""
    return plotview


class NXCanvas(FigureCanvas):
    """Subclass of Matplotlib's FigureCanvas."""

    def __init__(self, figure):

        FigureCanvas.__init__(self, figure)

        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                           QtWidgets.QSizePolicy.MinimumExpanding)

    def get_default_filename(self):
        """Return a string suitable for use as a default filename."""
        basename = (self.manager.get_window_title().replace('NeXpy: ', '')
                    if self.manager is not None else '')
        basename = (basename or 'image').replace(' ', '_')
        filetype = self.get_default_filetype()
        filename = basename + '.' + filetype
        return filename


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

    def set_window_title(self, title):
        try:
            self.window.setWindowTitle(title)
        except AttributeError:
            pass


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

        super().__init__(parent)

        self.setMinimumSize(750, 550)
        self.setSizePolicy(QtWidgets.QSizePolicy.MinimumExpanding,
                           QtWidgets.QSizePolicy.MinimumExpanding)
        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        if label in plotviews:
            plotviews[label].close()

        self.figuremanager = new_figure_manager(label)
        self.number = self.figuremanager.num
        self.canvas = self.figuremanager.canvas
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        self.canvas.callbacks.exception_handler = report_exception

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
            self.label = f"Figure {self.number}"

        self.canvas.setMinimumWidth(700)

        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setFixedHeight(80)
        self.tab_widget.setMinimumWidth(700)

        self.vtab = NXPlotTab('v', axis=False, image=True, plotview=self)
        self.xtab = NXPlotTab('x', plotview=self)
        self.ytab = NXPlotTab('y', plotview=self)
        self.ztab = NXPlotTab('z', zaxis=True, plotview=self)
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

        self.setWindowTitle('NeXpy: '+self.label)

        self.resize(734, 550)

        self.num = 1
        self.axis = {}
        self.xaxis = self.yaxis = self.zaxis = None
        self.xmin = self.xmax = None
        self.ymin = self.ymax = None
        self.vmin = self.vmax = None
        self.plots = {}

        self.image = None
        self.colorbar = None
        self.zoom = None
        self.rgb_image = False
        self.skewed = False
        self._smooth_func = None
        self._smooth_line = None
        self._aspect = 'auto'
        self._skew_angle = None
        self._bad = 'black'
        self._legend = None
        self._grid = False
        self._gridcolor = None
        self._gridstyle = None
        self._gridwidth = None
        self._gridalpha = None
        self._minorgrid = False
        self._majorlines = []
        self._minorlines = []
        self._minorticks = False
        self._active_mode = None
        self._cb_minorticks = False
        self._linthresh = None
        self._linscale = None
        self._stddev = 2.0
        self._primary_signal_group = None

        # Remove some key default Matplotlib key mappings
        for key in [key for key in mpl.rcParams if key.startswith('keymap')]:
            for shortcut in 'bfghkloprsvxyzAEFGHOPSZ':
                if shortcut in mpl.rcParams[key]:
                    mpl.rcParams[key].remove(shortcut)

        global active_plotview, plotview
        active_plotview = self
        if self.number < 101:
            plotview = self
        plotviews[self.label] = self
        self.plotviews = plotviews

        self.panels = self.mainwindow.panels
        self.shapes = []

        if self.label != "Main":
            self.add_menu_action()
            self.show()

        self.display_logo()

    def __repr__(self):
        return f'NXPlotView("{self.label}")'

    def keyPressEvent(self, event):
        """Override the QWidget keyPressEvent.

        This converts the event into a Matplotlib KeyEvent so that keyboard
        shortcuts entered outside the canvas are treated as canvas shortcuts.

        Parameters
        ----------
        event : PyQt QKeyEvent
        """
        self.canvas.keyPressEvent(event)

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
            self.xp, self.yp = event.x, event.y
            self.xdata, self.ydata = self.inverse_transform(event.xdata,
                                                            event.ydata)
            self.coords = [self.xdata if self.axis[i] is self.xaxis else
                           self.ydata if self.axis[i] is self.yaxis else
                           0.5 * (self.axis[i].lo + self.axis[i].hi)
                           for i in range(self.ndim)]
        else:
            self.xp, self.yp, self.xdata, self.ydata = None, None, None, None

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

    def resizeEvent(self, event):
        self.update_panels()
        super().resizeEvent(event)

    def activate(self):
        """Restore original signal connections.

        This assumes a previous call to the deactivate function, which sets the
        current value of _active_mode.
        """
        if self._active_mode == 'zoom rect':
            self.otab.zoom()
        elif self._active_mode == 'pan/zoom':
            self.otab.pan()

    def deactivate(self):
        """Disable usual signal connections."""
        self._active_mode = self.otab.active_mode
        if self._active_mode == 'zoom rect':
            self.otab.zoom()
        elif self._active_mode == 'pan/zoom':
            self.otab.pan()

    def display_logo(self):
        """Display the NeXpy logo in the plotting pane."""
        self.plot(NXdata(logo, title='NeXpy'), image=True)
        self.ax.xaxis.set_visible(False)
        self.ax.yaxis.set_visible(False)
        self.ax.title.set_visible(False)
        self.draw()

    @property
    def screen(self):
        if self.windowHandle():
            return self.windowHandle().screen()
        else:
            return None

    def make_active(self):
        """Make this window active for plotting."""
        global active_plotview, plotview
        active_plotview = self
        if self.number < 101:
            plotview = self
            self.mainwindow.user_ns['plotview'] = self
        self.show()
        if self.label == 'Main':
            self.mainwindow.raise_()
        else:
            self.raise_()
        try:
            self.canvas._update_screen(self.screen)
        except Exception:
            pass
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

    def save(self, fname=None, **opts):
        """Save the current plot to an image file."""
        if fname:
            self.figure.savefig(fname, **opts)
        else:
            self.otab.save_figure()

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
        num = opts.pop("num", max([p for p in self.plots if p < 100]+[1]) + 1)
        self.weighted = opts.pop("weights", False)
        self.interpolation = opts.pop("interpolation", self.interpolation)
        self._aspect = opts.pop("aspect", "auto")
        self._skew_angle = opts.pop("skew", None)
        self._bad = opts.pop("bad", self.bad)

        self.data = data
        if not over:
            self.title = data.nxtitle

        if self.data.nxsignal is None:
            raise NeXusError('No plotting signal defined')
        if self.weighted and self.data.nxweights is None:
            raise NeXusError('Invalid weights in plot data')

        if image:
            self.rgb_image = True
        else:
            self.rgb_image = False

        self.plotdata = self.get_plotdata(over=over)
        if not over:
            self.init_tabs()

        # One-dimensional Plot
        if self.ndim == 1:
            if over:
                self.num = num
            else:
                self.num = 1
                if xmin is not None:
                    self.xaxis.lo = xmin
                if xmax is not None:
                    self.xaxis.hi = xmax
                if ymin is not None:
                    self.yaxis.lo = ymin
                if ymax is not None:
                    self.yaxis.hi = ymax
                if log:
                    logy = True

            self.x, self.y, self.e = self.get_points()
            self.plot_points(fmt=fmt, over=over, **opts)
            self.add_plot()

        # Higher-dimensional plot
        else:
            if xmin is not None:
                self.xaxis.lo = xmin
            else:
                self.xaxis.lo = self.xaxis.min
            if xmax is not None:
                self.xaxis.hi = xmax
            else:
                self.xaxis.hi = self.xaxis.max
            if ymin is not None:
                self.yaxis.lo = ymin
            else:
                self.yaxis.lo = self.yaxis.min
            if ymax is not None:
                self.yaxis.hi = ymax
            else:
                self.yaxis.hi = self.yaxis.max
            if vmin is not None:
                self.vaxis.lo = vmin
            if vmax is not None:
                self.vaxis.hi = vmax
            self.reset_log()
            self.x, self.y, self.v = self.get_image()
            self.plot_image(over, **opts)

        self.limits = (self.xaxis.min, self.xaxis.max,
                       self.yaxis.min, self.yaxis.max)

        self.update_tabs()

        if over:
            self.update_panels()
        else:
            self.remove_panels()

        if self.rgb_image:
            self.ytab.flipped = True
            if self.aspect == 'auto':
                self.aspect = 'equal'
        elif self.xaxis.reversed or self.yaxis.reversed:
            self.replot_axes(draw=False)

        self.offsets = True
        self.cmap = cmap

        if self.ndim > 1 and log:
            self.logv = log
        if logx:
            self.logx = logx
        if logy:
            self.logy = logy

        self.set_plot_defaults()

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

        if (over and signal_group
                and signal_group == self._primary_signal_group
                and self.data.nxsignal.valid_axes(self.plotdata.nxaxes)):
            axes = self.plotdata.nxaxes
        elif self.data.plot_axes is not None:
            axes = self.data.plot_axes
        else:
            axes = [NXfield(np.arange(self.shape[i]), name=f'Axis{i}')
                    for i in range(self.ndim)]

        self.axes = [NXfield(axes[i].nxdata, name=axes[i].nxname,
                     attrs=axes[i].safe_attrs) for i in range(self.ndim)]

        _data = self.data
        _signal = _data.nxsignal
        if self.ndim > 2:
            idx = [np.s_[0] if s == 1 else np.s_[:] for s in _signal.shape]
            for i in range(len(idx)):
                if idx.count(slice(None, None, None)) > 2:
                    try:
                        if self.axes[i].shape[0] == _signal.shape[i]+1:
                            idx[i] = self.axes[i].centers().index(0.0)
                        else:
                            idx[i] = self.axes[i].index(0.0)
                    except Exception:
                        idx[i] = 0
            if self.weighted:
                signal = _data[tuple(idx)].weighted_data().nxsignal[()]
            else:
                signal = _signal[tuple(idx)][()]
        elif self.rgb_image:
            signal = _signal[()]
        else:
            if self.weighted:
                signal = _data.weighted_data().nxsignal[()].reshape(self.shape)
            else:
                signal = _signal[()].reshape(self.shape)
        if signal.dtype == bool:
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
                        = float(self.axis[i].centers[idx[i]])
                self.zaxis = self.axis[self.ndim - 3]
                self.zaxis.lo = self.zaxis.hi = self.axis[self.ndim - 3].lo
            else:
                self.zaxis = None
            self.vaxis = self.axis['signal']
            plotdata = NXdata(self.signal, [self.axes[i] for i in [-2, -1]])
            if self.data.ndim == 2 or self.data.ndim == 3:
                self._skew_angle = self.get_skew_angle(1, 2)
                if self._skew_angle is not None:
                    plotdata.nxangles = self._skew_angle

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

    def plot_points(self, fmt='', over=False, **opts):
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

        if fmt == '':
            if 'color' not in opts:
                opts['color'] = self.colors[(self.num-1) % len(self.colors)]
            if 'marker' not in opts:
                opts['marker'] = 'o'
            if 'linestyle' not in opts and 'ls' not in opts:
                opts['linestyle'] = 'None'

        if self.e is not None:
            self._plot = ax.errorbar(
                self.x, self.y, self.e, fmt=fmt, **opts)[0]
        else:
            if fmt == '':
                self._plot = ax.plot(self.x, self.y, **opts)[0]
            else:
                self._plot = ax.plot(self.x, self.y, fmt, **opts)[0]

        ax.lines[-1].set_label(self.signal_path)

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

            if self.xaxis.lo is not None:
                ax.set_xlim(xmin=self.xaxis.lo)
            else:
                self.xaxis.lo = xlo
            if self.xaxis.hi is not None:
                ax.set_xlim(xmax=self.xaxis.hi)
            else:
                self.xaxis.hi = xhi
            if self.yaxis.lo is not None:
                ax.set_ylim(ymin=self.yaxis.lo)
            else:
                self.yaxis.lo = ylo
            if self.yaxis.hi is not None:
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
            if self._skew_angle and self._aspect == 'equal':
                ax = self.figure.add_subplot(Subplot(self.figure, 1, 1, 1,
                                             grid_helper=self.grid_helper()))
                self.skewed = True
            else:
                ax = self.figure.add_subplot(1, 1, 1)
                self.skewed = False
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

        if parse_version(mpl.__version__) >= parse_version('3.5.0'):
            cm = copy.copy(mpl.colormaps[self.cmap])
        else:
            cm = copy.copy(get_cmap(self.cmap))
        cm.set_bad(self.bad)
        if self.rgb_image or self.regular_grid:
            opts['origin'] = 'lower'
            self.image = ax.imshow(self.v, extent=extent, cmap=cm,
                                   norm=self.norm, **opts)
        else:
            if self.skewed:
                xx, yy = np.meshgrid(self.x, self.y)
                x, y = self.transform(xx, yy)
            else:
                x, y = self.x, self.y
            self.image = ax.pcolormesh(x, y, self.v, cmap=cm, **opts)
            self.image.set_norm(self.norm)
        ax.set_aspect(self.get_aspect())

        if not over and not self.rgb_image:
            self.colorbar = self.figure.colorbar(self.image, ax=ax)
            self.colorbar.locator = self.locator
            self.colorbar.formatter = self.formatter
            self.update_colorbar()

        xlo, ylo = self.transform(self.xaxis.lo, self.yaxis.lo)
        xhi, yhi = self.transform(self.xaxis.hi, self.yaxis.hi)

        ax.set_xlim(xlo, xhi)
        ax.set_ylim(ylo, yhi)

        if not over:
            ax.set_xlabel(self.xaxis.label)
            ax.set_ylabel(self.yaxis.label)
            ax.set_title(self.title)

        self.vaxis.min, self.vaxis.max = self.image.get_clim()

    def add_plot(self):
        if self.num == 1:
            self.plots = {}
            self.ytab.plotcombo.clear()
        p = {}
        p['plot'] = self._plot
        p['x'] = self.x
        p['y'] = self.y
        p['data'] = self.data
        p['path'] = self.signal_path
        p['label'] = self.signal_path
        p['legend_label'] = p['label']
        p['show_legend'] = True
        p['legend_order'] = len(self.plots) + 1
        p['color'] = get_color(p['plot'].get_color())
        p['marker'] = p['plot'].get_marker()
        p['markersize'] = p['plot'].get_markersize()
        p['markerstyle'] = 'filled'
        p['linestyle'] = p['plot'].get_linestyle()
        p['linewidth'] = p['plot'].get_linewidth()
        p['zorder'] = p['plot'].get_zorder()
        p['scale'] = 1.0
        p['offset'] = 0.0
        try:
            p['smooth_function'] = interp1d(self.x, self.y, kind='cubic')
        except Exception:
            p['smooth_function'] = None
        p['smooth_line'] = None
        p['smooth_linestyle'] = 'None'
        p['smoothing'] = False
        if mplcursors and p['marker'] != 'None':
            p['cursor'] = mplcursors.cursor(p['plot'])
        else:
            p['cursor'] = None
        self.plots[self.num] = p
        self.ytab.plotcombo.add(self.num)
        self.ytab.plotcombo.select(self.num)
        self.ytab.reset_smoothing()

    @property
    def signal_group(self):
        """Determine path of signal group."""
        if self.data.nxroot.nxclass == "NXroot":
            return dirname(self.data.nxroot.nxname +
                           self.data.nxsignal.nxpath) + '/'
        elif 'signal_path' in self.data.attrs:
            return dirname(self.data.attrs['signal_path']) + '/'
        else:
            return ''

    @property
    def signal_path(self):
        """Determine full path of signal."""
        return self.signal_group + self.signal.nxname

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
        if len(_shape) > 1:
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
        elif self.vtab.qualitative:
            if self.vaxis.min_data > 0.0:
                self.vaxis.lo = 0.5
            else:
                self.vaxis.lo = -0.5
            if parse_version(mpl.__version__) >= parse_version('3.5.0'):
                nc = len(mpl.colormaps[self.cmap].colors)
            else:
                nc = len(get_cmap(self.cmap).colors)
            self.vaxis.hi = self.vaxis.lo + nc
        elif self.vaxis.lo is None or self.autoscale:
            self.vaxis.lo = np.min(self.finite_v)
        if self.vtab.log and not self.vtab.symmetric:
            self.vtab.set_limits(*self.vaxis.log_limits())

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
                self.norm = SymLogNorm(linthresh, linscale=linscale,
                                       vmin=self.vaxis.lo, vmax=self.vaxis.hi)
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
        xmin, xmax, ymin, ymax = [float(value) for value in self.limits]
        for i in range(self.ndim):
            if i in axes:
                if i == self.xaxis.dim:
                    limits.append((xmin, xmax))
                else:
                    limits.append((ymin, ymax))
            else:
                limits.append((float(self.axis[i].lo), float(self.axis[i].hi)))
        if self.data.nxsignal.shape != self.data.plot_shape:
            axes, limits = fix_projection(self.data.nxsignal.shape, axes,
                                          limits)
        try:
            self.plotdata = self.data.project(axes, limits, summed=self.summed)
            if self.weighted:
                self.plotdata = self.plotdata.weighted_data()
            if self.ndim == 3 and not self._skew_angle:
                self._skew_angle = self.get_skew_angle(*axes)
                if self._skew_angle is not None:
                    self.plotdata.nxangles = self._skew_angle
        except Exception as e:
            self.ztab.pause()
            raise e
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
                self.update_colorbar()
                self.set_minorticks()
            self.image.set_clim(self.vaxis.lo, self.vaxis.hi)
            self.vtab.set_limits(self.vaxis.lo, self.vaxis.hi)
            if self.regular_grid:
                if self.interpolation == 'convolve':
                    self.image.set_interpolation('bicubic')
                else:
                    self.image.set_interpolation(self.interpolation)
            self.replot_axes()
        except Exception:
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
        if self.ndim == 1:
            try:
                self.plot_smooth()
            except NeXusError:
                pass
        if draw:
            self.draw()
        self.update_panels()

    def update_colorbar(self):
        if self.colorbar:
            if parse_version(mpl.__version__) >= parse_version('3.1.0'):
                self.colorbar.update_normal(self.image)
            else:
                self.colorbar.set_norm(self.norm)
                self.colorbar.update_bruteforce(self.image)
            if self.vtab.qualitative:
                vmin, vmax = [int(i+0.5) for i in self.image.get_clim()]
                self.colorbar.set_ticks(range(vmin, vmax))
                if parse_version(mpl.__version__) >= parse_version('3.5.0'):
                    if self.cmap == 'xtec':
                        vmin, vmax = (0.5, self.vaxis.max_data+0.5)
                    else:
                        vmin, vmax = (self.vaxis.min_data-0.5,
                                      self.vaxis.max_data+0.5)
                    self.colorbar.ax.set_ylim(vmin, vmax)

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
        if x is None or y is None or not self.skewed:
            return x, y
        else:
            x, y = np.asarray(x), np.asarray(y)
            angle = np.radians(self.skew)
            return 1.*x+np.cos(angle)*y,  np.sin(angle)*y

    def inverse_transform(self, x, y):
        """Return the inverse transform of the x and y values."""
        if x is None or y is None or not self.skewed:
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
            self.update_panels()
            self.draw()

    def plot_smooth(self):
        """Add smooth line to 1D plot."""
        num = self.num
        if self.plots[num]['smooth_function']:
            self.plots[num]['smoothing'] = self.ytab.smoothing
        else:
            raise NeXusError("Unable to smooth this data")
        for num in self.plots:
            p = self.plots[num]
            if p['smooth_line']:
                p['smooth_line'].remove()
            xs_min, xs_max = self.ax.get_xlim()
            ys_min, ys_max = self.ax.get_ylim()
            if (p['smoothing'] and p['smooth_function'] and
                    xs_min < p['x'].max() and xs_max > p['x'].min()):
                p['plot'].set_linestyle('None')
                xs = np.linspace(max(xs_min, p['x'].min()),
                                 min(xs_max, p['x'].max()), 1000)
                if p['linestyle'] == 'None':
                    p['smooth_linestyle'] = '-'
                elif p['linestyle'].startswith('steps'):
                    p['smooth_linestyle'] = '-'
                else:
                    p['smooth_linestyle'] = p['linestyle']
                p['smooth_line'] = self.ax.plot(xs,
                                                p['smooth_function'](xs),
                                                p['smooth_linestyle'])[0]
                self.ax.set_xlim(xs_min, xs_max)
                self.ax.set_ylim(ys_min, ys_max)
                p['smooth_line'].set_color(p['color'])
                p['smooth_line'].set_label('_smooth_line_' + str(num))
            else:
                p['plot'].set_linestyle(p['linestyle'])
                p['smooth_line'] = None
        self.draw()

    def fit_data(self):
        from .fitdialogs import FitDialog
        if not self.mainwindow.panel_is_running('Fit'):
            self.panels['Fit'] = FitDialog()
        self.panels['Fit'].activate(self.plots[self.num]['data'],
                                    plotview=self,
                                    color=self.plots[self.num]['color'])

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
            if parse_version(mpl.__version__) >= parse_version('3.1.0'):
                self.image.set_norm(SymLogNorm(linthresh, linscale=linscale,
                                               vmin=-vmax, vmax=vmax))
            else:
                self.colorbar.set_norm(SymLogNorm(linthresh, linscale=linscale,
                                                  vmin=-vmax, vmax=vmax))
                self.colorbar.update_bruteforce(self.image)
            self.set_minorticks()
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
        self.xaxis.min = self.xaxis.lo = xmin
        self.xaxis.max = self.xaxis.hi = xmax
        if self.logx:
            self.xaxis.lo, self.xaxis.hi = self.xaxis.log_limits()
        self.yaxis.min = self.yaxis.lo = ymin
        self.yaxis.max = self.yaxis.hi = ymax
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
                except Exception:
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

    def get_aspect(self):
        if self.image and self._aspect == 'equal':
            self.otab._actions['set_aspect'].setChecked(True)
            _axes = self.plotdata.nxaxes
            try:
                if ('scaling_factor' in _axes[-1].attrs and
                        'scaling_factor' in _axes[-2].attrs):
                    _xscale = _axes[-1].attrs['scaling_factor']
                    _yscale = _axes[-2].attrs['scaling_factor']
                    return float(_yscale / _xscale)
                elif 'scaling_factor' in _axes[-1].attrs:
                    return 1.0 / _axes[-1].attrs['scaling_factor']
                elif 'scaling_factor' in _axes[-2].attrs:
                    return _axes[-2].attrs['scaling_factor']
                else:
                    return 'equal'
            except Exception:
                return 'equal'
        elif self._aspect == 'auto':
            self.otab._actions['set_aspect'].setChecked(False)
        else:
            self.otab._actions['set_aspect'].setChecked(True)
        return self._aspect

    @property
    def aspect(self):
        """Return the currently set aspect ratio value."""
        return self._aspect

    @aspect.setter
    def aspect(self, aspect):
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
            self._aspect = aspect
            if aspect == 'auto':
                self.otab._actions['set_aspect'].setChecked(False)
            elif aspect == 'equal':
                self.otab._actions['set_aspect'].setChecked(True)
        if self.ax.get_aspect() != self.get_aspect():
            try:
                if self.skew and self.image is not None:
                    self.replot_data(newaxis=True)
                else:
                    self.ax.set_aspect(self.get_aspect())
                self.canvas.draw()
                self.update_panels()
            except Exception:
                pass

    def get_skew_angle(self, xdim, ydim):
        """Return the skew angle defined by the NXdata attributes.

        If the original data is two- or three-dimensional and the
        'angles' attribute has been defined, this returns the value
        between the x and y axes.

        Parameters
        ----------
        xdim : int
            The dimension number of the x-axis.
        ydim : int
            The dimension number of the y-axis.
        """
        if self.data.nxangles is not None:
            angles = self.data.nxangles
            if self.data.ndim == 2:
                skew = angles
            elif self.data.ndim > 2:
                dim = [i for i in range(self.ndim) if i not in [xdim, ydim]][0]
                skew = angles[dim]
            if not np.isclose(skew, 90.0):
                return skew
        return None

    @property
    def skew(self):
        """Return the skew angle for a 2D plot."""
        return self._skew_angle

    @skew.setter
    def skew(self, skew_angle):
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
        if skew_angle == self._skew_angle:
            return
        try:
            _skew_angle = float(skew_angle)
            if self.skew is not None and np.isclose(self.skew, _skew_angle):
                return
            if np.isclose(_skew_angle, 0.0) or np.isclose(_skew_angle, 90.0):
                _skew_angle = None
        except (ValueError, TypeError):
            if (skew_angle is None or str(skew_angle) == '' or
                str(skew_angle) == 'None' or
                    str(skew_angle) == 'none'):
                _skew_angle = None
            else:
                return
        if self._skew_angle is None and _skew_angle is None:
            return
        else:
            self._skew_angle = _skew_angle
        if self._skew_angle is not None and self._aspect == 'auto':
            self._aspect = 'equal'
        if self.image is not None:
            self.replot_data(newaxis=True)

    @property
    def autoscale(self):
        """Return True if the ztab autoscale checkbox is selected."""
        if self.ndim > 2 and self.ztab.scalebox.isChecked():
            return True
        else:
            return False

    @autoscale.setter
    def autoscale(self, value=True):
        """Set the ztab autoscale checkbox to True or False"""
        self.ztab.scalebox.setChecked(value)

    @property
    def summed(self):
        """Return True if the projection tab is set to sum the data."""
        if self.ptab.summed:
            return True
        else:
            return False

    @property
    def cmap(self):
        """Return the color map set in the vtab."""
        return self.vtab.cmap

    @cmap.setter
    def cmap(self, cmap):
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

    @property
    def colors(self):
        return mpl.rcParams['axes.prop_cycle'].by_key()['color']

    @property
    def bad(self):
        """Return the color defined for bad pixels."""
        return self._bad

    @bad.setter
    def bad(self, bad):
        """Set the bad pixel color.

        Parameters
        ----------
        bad : str or tuple
            Value of the bad color. This can use any of the standard forms
            recognized by Matplotlib, including hex color codes, RGBA tuples,
            and their equivalent names.

        Raises
        ------
        NeXusError
            If the requested value is an invalid color.
        """
        from matplotlib.colors import is_color_like
        if is_color_like(bad):
            self._bad = bad
            if self.image:
                self.image.cmap.set_bad(bad)
                self.draw()
        else:
            raise NeXusError("Invalid color value")

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

    @property
    def interpolation(self):
        """Return the currently selected interpolation method."""
        return self.vtab.interpolation

    @interpolation.setter
    def interpolation(self, interpolation):
        """Set the interpolation method and replot the data."""
        self.vtab.interpolation = interpolation

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
            self.update_panels()

    @property
    def smooth(self):
        """Return standard deviation in pixels of Gaussian smoothing."""
        return self._stddev

    @smooth.setter
    def smooth(self, value):
        """Set standard deviation in pixels of Gaussian smoothing."""
        self._stddev = value
        self.interpolate()

    @property
    def offsets(self):
        """Return the axis offset used in tick labels."""
        return self._axis_offsets

    @offsets.setter
    def offsets(self, value):
        """Set the axis offset used in tick labels and redraw plot."""
        try:
            self._axis_offsets = value
            self.ax.ticklabel_format(useOffset=self._axis_offsets)
            self.draw()
        except Exception:
            pass

    def set_plot_defaults(self):
        self._grid = mpl.rcParams['axes.grid']
        self._gridcolor = mpl.rcParams['grid.color']
        self._gridstyle = mpl.rcParams['grid.linestyle']
        self._gridwidth = mpl.rcParams['grid.linewidth']
        self._gridalpha = mpl.rcParams['grid.alpha']
        self._minorgrid = False
        if self._grid:
            self.grid(self._grid, self._minorgrid)
        self.set_minorticks(default=True)

    def set_minorticks(self, default=False):
        if default:
            self._minorticks = (mpl.rcParams['xtick.minor.visible'] or
                                mpl.rcParams['ytick.minor.visible'])
            self._cb_minorticks = False
        if self._minorticks:
            self.minorticks_on()
        else:
            self.minorticks_off()
        if self._cb_minorticks:
            self.cb_minorticks_on()
        else:
            self.cb_minorticks_off()

    def minorticks_on(self):
        """Turn on minor ticks on the axes."""
        self.ax.minorticks_on()
        self._minorticks = True
        self.draw()

    def minorticks_off(self):
        """Turn off minor ticks on the axes."""
        self.ax.minorticks_off()
        self._minorticks = False
        self.draw()

    def cb_minorticks_on(self):
        """Turn on minor ticks on the colorbar."""
        if self.colorbar:
            self.colorbar.minorticks_on()
            self._cb_minorticks = True
            self.draw()

    def cb_minorticks_off(self):
        """Turn off minor ticks on the axes."""
        if self.colorbar:
            self.colorbar.minorticks_off()
            self._cb_minorticks = False
            self.draw()

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
                    and not self.skewed)
        except Exception:
            return False

    def get_size(self):
        return tuple(self.figure.get_size_inches())

    def set_size(self, width, height):
        if self.label == 'Main':
            raise NeXusError(
                "Cannot change the size of the main window programmatically")
        self.figure.set_size_inches(width, height)

    @property
    def ax(self):
        """The current Matplotlib axes instance."""
        return self.figure.gca()

    def draw(self):
        """Redraw the current plot."""
        self.canvas.draw_idle()

    def clear(self):
        """Clear the NXPlotView figure."""
        self.figure.clear()
        self.draw()

    def legend(self, *items, **opts):
        """Add a legend to the plot."""
        path = opts.pop('path', False)
        group = opts.pop('group', False)
        signal = opts.pop('signal', False)
        ax = opts.pop('ax', self.ax)
        if self.ndim != 1:
            raise NeXusError("Legends are only displayed for 1D plots")
        elif len(items) == 0:
            plots = [self.plots[p] for p in self.plots
                     if self.plots[p]['show_legend']]
            handles = [p['plot'] for p in plots]
            if path:
                if group:
                    labels = [dirname(p['path']) for p in plots]
                else:
                    labels = [p['path'] for p in plots]
            elif group:
                labels = [basename(dirname(p['path'])) for p in plots]
            elif signal:
                labels = [basename(p['path']) for p in plots]
            else:
                labels = [p['legend_label'] for p in plots]
            order = [int(p['legend_order']) for p in plots]
            handles = list(zip(*sorted(zip(order, handles))))[1]
            labels = list(zip(*sorted(zip(order, labels))))[1]
        elif len(items) == 1:
            handles, _ = self.ax.get_legend_handles_labels()
            labels = items[0]
        else:
            handles, labels = items
        _legend = ax.legend(handles, labels, **opts)
        try:
            _legend.set_draggable(True)
        except AttributeError:
            _legend.draggable(True)
        if ax == self.ax:
            self.draw()
            self._legend = _legend
        return _legend

    def remove_legend(self):
        """Remove the legend."""
        if self.ax.get_legend():
            self.ax.get_legend().remove()
        self._legend = None
        self.draw()

    def grid(self, display=None, minor=False, ax=None, **opts):
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
        if ax is None:
            ax = self.ax
        if display is not None:
            self._grid = display
        elif opts:
            self._grid = True
        else:
            self._grid = not self._grid
        self._minorgrid = minor
        if self._grid:
            if 'color' in opts:
                self._gridcolor = opts['color']
            else:
                opts['color'] = self._gridcolor
            if 'linestyle' in opts:
                self._gridstyle = opts['linestyle']
            else:
                opts['linestyle'] = self._gridstyle
            if 'linewidth' in opts:
                self._gridwidth = opts['linewidth']
            else:
                opts['linewidth'] = self._gridwidth
            if 'alpha' in opts:
                self._gridalpha = opts['alpha']
            else:
                opts['alpha'] = self._gridalpha
            if minor:
                ax.minorticks_on()
            self.ax.set_axisbelow('line')
            if self.skew:
                self.draw_skewed_grid(minor=minor, **opts)
            else:
                ax.grid(True, which='major', axis='both', **opts)
                if minor:
                    opts['linewidth'] = max(self._gridwidth/2, 0.1)
                    ax.grid(True, which='minor', axis='both', **opts)
                self.remove_skewed_grid()
        else:
            ax.grid(False, which='both', axis='both')
            if not self._minorticks:
                self.minorticks_off()
            if self.skew:
                self.remove_skewed_grid()
        if self._cb_minorticks:
            self.cb_minorticks_on()
        else:
            self.cb_minorticks_off()
        self.update_panels()
        self.draw()

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
        self.ax.set_ylim(ymin, ymax)
        self.draw()
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
        self.ax.set_xlim(xmin, xmax)
        self.draw()
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
                line = Line2D([x0[i], x1[i]], [y0, y1], **opts)
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
        circle : NXcircle
            NeXpy NXcircle object.

        Notes
        -----
        This assumes that the unit lengths of the x and y axes are the
        same. The circle will be skewed if the plot is skewed.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        if 'linewidth' not in opts:
            opts['linewidth'] = 1.0
        if 'facecolor' not in opts:
            opts['facecolor'] = 'r'
        if 'edgecolor' not in opts:
            opts['edgecolor'] = 'k'
        circle = NXcircle(float(x), float(y), radius, plotview=self, **opts)
        circle.connect()
        self.canvas.draw()
        self.shapes.append(circle)
        return circle

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
        ellipse : NXellipse
            NeXpy NXellipse object.

        Notes
        -----
        The ellipse will be skewed if the plot is skewed.
        """
        if self.skew is not None:
            x, y = self.transform(x, y)
        if 'linewidth' not in opts:
            opts['linewidth'] = 1.0
        if 'facecolor' not in opts:
            opts['facecolor'] = 'r'
        if 'edgecolor' not in opts:
            opts['edgecolor'] = 'k'
        ellipse = NXellipse(float(x), float(y), float(dx), float(dy),
                            plotview=self, **opts)
        ellipse.connect()
        self.canvas.draw()
        self.shapes.append(ellipse)
        return ellipse

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
        rectangle : NXrectangle or NXpolygon
            NeXpy NXrectangle object of NXpolygon object if the axes are
            skewed.
        """
        if 'linewidth' not in opts:
            opts['linewidth'] = 1.0
        if 'facecolor' not in opts:
            opts['facecolor'] = 'none'
        if 'edgecolor' not in opts:
            opts['edgecolor'] = 'k'
        if self.skew is None:
            rectangle = NXrectangle(float(x), float(y), float(dx), float(dy),
                                    plotview=self, **opts)
        else:
            xc, yc = [x, x, x+dx, x+dx], [y, y+dy, y+dy, y]
            xy = [self.transform(_x, _y) for _x, _y in zip(xc, yc)]
            rectangle = NXpolygon(xy, True, plotview=self, **opts)
        rectangle.connect()
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
        rectangle : NXpolygon
            NeXpy NXpolygon object.
        """
        if self.skew is not None:
            xy = [self.transform(_x, _y) for _x, _y in xy]
        if 'linewidth' not in opts:
            opts['linewidth'] = 1.0
        if 'facecolor' not in opts:
            opts['facecolor'] = 'r'
        if 'edgecolor' not in opts:
            opts['edgecolor'] = 'k'
        polygon = NXpolygon(xy, closed, plotview=self, **opts)
        polygon.connect()
        self.canvas.draw()
        self.shapes.append(polygon)
        return polygon

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
        vor = Voronoi([(x[i, j], y[i, j]) for i in range(z.shape[0])
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
        from matplotlib.cm import ScalarMappable
        mapper = ScalarMappable(norm=self.norm, cmap=self.cmap)
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

    def mpl_plot(self, ax=None, title=False, colorbar=False, **kwargs):
        import matplotlib.pyplot as plt
        from nexusformat.nexus.plot import plotview as pv
        label = kwargs.pop('label', None)
        loc = kwargs.pop('loc', 'upper left')
        if ax:
            plt.sca(ax)
        else:
            ax = plt.gca()
        over = False
        if self.plotdata.ndim == 1:
            for i in self.plots:
                p = self.plots[i]
                if p['markerstyle'] == 'open':
                    mfc = '#ffffff'
                else:
                    mfc = p['color']
                pv.plot(p['data'], color=p['color'], ax=ax, over=over,
                        xmin=self.xaxis.lo, xmax=self.xaxis.hi,
                        ymin=self.yaxis.lo, ymax=self.yaxis.hi,
                        marker=p['marker'], markersize=p['markersize'],
                        markerfacecolor=mfc, markeredgecolor=p['color'],
                        linestyle=p['linestyle'], linewidth=p['linewidth'],
                        zorder=p['zorder'], **kwargs)
                over = True
            if self.ax.get_legend():
                self.legend(ax=ax)
        else:
            pv.plot(self.plotdata, ax=ax,
                    image=plotview.rgb_image, log=self.logv,
                    vmin=self.vaxis.lo, vmax=self.vaxis.hi,
                    xmin=self.xaxis.lo, xmax=self.xaxis.hi,
                    ymin=self.yaxis.lo, ymax=self.yaxis.hi,
                    aspect=self.aspect, regular=self.regular_grid,
                    interpolation=self.interpolation,
                    cmap=self.cmap, colorbar=colorbar, bad=self.bad, **kwargs)
        if title:
            ax.set_title(self.ax.get_title())
        else:
            ax.set_title('')
        ax.set_xlabel(self.ax.get_xlabel())
        ax.set_ylabel(self.ax.get_ylabel())
        self.grid(display=self._grid, minor=self._minorgrid, ax=ax)
        if label:
            from matplotlib.offsetbox import AnchoredText
            ax.add_artist(AnchoredText(label, loc=loc, prop=dict(size=20),
                                       frameon=False))

    def block_signals(self, block=True):
        self.xtab.block_signals(block)
        self.ytab.block_signals(block)
        self.ztab.block_signals(block)
        self.vtab.block_signals(block)

    def init_tabs(self):
        """Initialize tabs for a new plot."""
        self.block_signals(True)
        self.xtab.set_axis(self.xaxis)
        self.ytab.set_axis(self.yaxis)
        if self.ndim == 1:
            self.xtab.logbox.setVisible(True)
            self.xtab.axiscombo.setVisible(False)
            self.ytab.axiscombo.setVisible(False)
            self.ytab.plotcombo.setVisible(True)
            self.ytab.logbox.setVisible(True)
            self.ytab.flipbox.setVisible(False)
            self.ytab.smoothbox.setVisible(True)
            if self.label != 'Fit':
                self.ytab.fitbutton.setVisible(True)
            else:
                self.ytab.fitbutton.setVisible(False)
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.vtab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ptab))
        elif self.ndim >= 2:
            self.vtab.set_axis(self.vaxis)
            if self.tab_widget.indexOf(self.vtab) == -1:
                self.tab_widget.insertTab(0, self.vtab, 'signal')
            if self.label != 'Projection':
                if self.tab_widget.indexOf(self.ptab) == -1:
                    self.tab_widget.insertTab(
                        self.tab_widget.indexOf(self.otab),
                        self.ptab, 'projections')
                self.ptab.set_axes()
            if self.ndim > 2:
                self.ztab.set_axis(self.zaxis)
                self.ztab.locked = True
                self.ztab.pause()
                self.ztab.scalebox.setChecked(True)
                if self.tab_widget.indexOf(self.ztab) == -1:
                    if self.tab_widget.indexOf(self.ptab) == -1:
                        idx = self.tab_widget.indexOf(self.otab)
                    else:
                        idx = self.tab_widget.indexOf(self.ptab)
                    self.tab_widget.insertTab(idx, self.ztab, 'z')
            else:
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.xtab.logbox.setVisible(True)
            self.xtab.axiscombo.setVisible(True)
            self.xtab.flipbox.setVisible(True)
            self.ytab.plotcombo.setVisible(False)
            self.ytab.axiscombo.setVisible(True)
            self.ytab.logbox.setVisible(True)
            self.ytab.flipbox.setVisible(True)
            self.ytab.smoothbox.setVisible(False)
            self.ytab.fitbutton.setVisible(False)
            if self.rgb_image:
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.vtab))
            else:
                self.vtab.flipbox.setVisible(False)
        self.block_signals(False)

    def update_tabs(self):
        """Update tabs when limits have changed."""
        self.block_signals(True)
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
        self.block_signals(False)

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
            self.skew = None
            self.replot_data(newaxis=True)
            self.vtab.set_axis(self.vaxis)
        self.update_panels()
        self.otab.update()

    def update_panels(self):
        """Update the option panels."""
        for panel in self.panels:
            if self.label in self.panels[panel].tabs:
                try:
                    self.panels[panel].tabs[self.label].update()
                except Exception:
                    pass

    def remove_panels(self):
        """Remove panels associated with the previous plot."""
        for panel in list(self.panels):
            if self.label in self.panels[panel].tabs:
                try:
                    self.panels[panel].remove(self.label)
                except RuntimeError:
                    self.panels[panel].close()
            elif panel == 'Fit':
                removed_tabs = []
                for tab in self.panels['Fit'].tabs:
                    if tab.startswith(self.label):
                        removed_tabs.append(tab)
                for tab in removed_tabs:
                    self.panels['Fit'].remove(tab)

    def format_coord(self, x, y):
        """Return the x, y, and signal values for the selected pixel."""
        try:
            if self.ndim == 1:
                return f'x={x:.4g} y={y:.4g}'
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
                z = self.v[row, col]
                return f'x={x:.4g} y={y:.4g}\nv={z:.4g}'
        except Exception:
            return ''

    def close_view(self):
        """Remove this window from menus and close associated panels."""
        self.remove_menu_action()
        if self.label in plotviews:
            del plotviews[self.label]
        self.remove_panels()

    def closeEvent(self, event):
        """Close this widget and mark it for deletion."""
        self.close_view()
        self.deleteLater()
        event.accept()

    def close(self):
        self.close_view()
        super().close()


class NXPlotAxis:
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
        self.qualitative_data = False
        if self.data is not None:
            if dimlen is None:
                self.centers = None
                self.boundaries = None
                try:
                    self.min = float(np.min(self.data[np.isfinite(self.data)]))
                    self.max = float(np.max(self.data[np.isfinite(self.data)]))
                except Exception:
                    self.min = 0.0
                    self.max = 0.1
                if ((self.min >= 0 and self.max <= 20) and
                    (np.issubdtype(self.data.dtype, np.integer) or
                     np.all(np.equal(np.mod(self.data, 1.0), 0)))):
                    self.qualitative_data = True
            else:
                if self.data[0] > self.data[-1]:
                    self.reversed = True
                _spacing = self.data[1:] - self.data[:-1]
                _range = self.data.max() - self.data.min()
                if _spacing.size > 0:
                    if max(_spacing) - min(_spacing) > _range/1000:
                        self.equally_spaced = False
                self.centers = centers(self.data, dimlen)
                self.boundaries = boundaries(self.data, dimlen)
                try:
                    self.min = float(np.min(
                        self.boundaries[np.isfinite(self.boundaries)]))
                    self.max = float(np.max(
                        self.boundaries[np.isfinite(self.boundaries)]))
                except Exception:
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
        if 'long_name' in axis.attrs:
            self.label = axis.attrs['long_name']
        elif 'units' in axis.attrs:
            self.label = f"{axis.nxname} ({axis.units})"
        else:
            self.label = axis.nxname

    def __repr__(self):
        return f'NXPlotAxis("{self.name}")'

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
            if _spacing.size > 0:
                if max(_spacing) - min(_spacing) > _range/1000:
                    self.equally_spaced = False
            self.centers = centers(self.data, dimlen)
            self.boundaries = boundaries(self.data, dimlen)

    def set_limits(self, lo, hi):
        """Set the low and high values for the axis."""
        if lo > hi:
            lo, hi = hi, lo
        self.lo, self.hi = lo, hi
        self.diff = float(hi) - float(lo)

    def get_limits(self):
        """Return the low and high values for the axis."""
        return float(self.lo), float(self.hi)

    def log_limits(self):
        """Return limits with positive values."""
        try:
            minpos = min(self.data[self.data > 0.0])
        except ValueError:
            minpos = 0.01
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
        If True, this tab represents a plot axis.
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

    def __init__(self, name=None, axis=True, zaxis=False, image=False,
                 plotview=None):

        super().__init__()

        self.name = name
        self.plotview = plotview
        self.axis = None

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
            self.minbox = NXSpinBox(self.read_minbox)
            self.maxbox = NXSpinBox(self.read_maxbox)
            self.lockbox = NXCheckBox("Lock", self.change_lock)
            self.lockbox.setChecked(True)
            self.scalebox = NXCheckBox("Autoscale", self.change_scale)
            self.scalebox.setChecked(True)
            self.init_toolbar()
            widgets.append(self.minbox)
            widgets.append(self.maxbox)
            widgets.append(self.lockbox)
            widgets.append(self.scalebox)
            widgets.append(self.toolbar)
            self.minslider = self.maxslider = self.slide_max = None
            self.plotcombo = None
            self.flipbox = self.logbox = self.smoothbox = self.fitbutton = None
        else:
            self.zaxis = False
            if self.name == 'y':
                self.plotcombo = NXComboBox(self.select_plot, ['0'])
                self.plotcombo.setMinimumWidth(55)
            else:
                self.plotcombo = None
            self.minbox = NXDoubleSpinBox(self.read_minbox, self.edit_minbox)
            if self.name == 'v':
                self.minslider = NXSlider(self.read_minslider, move=False,
                                          inverse=True)
                self.maxslider = NXSlider(self.read_maxslider, move=False)
            else:
                self.minslider = NXSlider(self.read_minslider, inverse=True)
                self.maxslider = NXSlider(self.read_maxslider)
            self.slider_max = self.maxslider.maximum()
            self.maxbox = NXDoubleSpinBox(self.read_maxbox, self.edit_maxbox)
            self.logbox = NXCheckBox("Log", self.change_log)
            self.flipbox = NXCheckBox("Flip", self.flip_axis)
            if self.name == 'y':
                self.smoothbox = NXCheckBox("Smooth", self.toggle_smoothing)
                self.fitbutton = NXPushButton("Fit", self.fit_data)
            else:
                self.smoothbox = self.fitbutton = None
            if self.name == 'y':
                widgets.append(self.plotcombo)
            widgets.append(self.minbox)
            widgets.extend([self.minslider, self.maxslider])
            widgets.append(self.maxbox)
            widgets.append(self.logbox)
            widgets.append(self.flipbox)
            if self.name == 'y':
                widgets.append(self.smoothbox)
                widgets.append(self.fitbutton)
            self.lockbox = self.scalebox = None
        if image:
            self.image = True
            self.cmapcombo = NXComboBox(self.change_cmap, cmaps, default_cmap)
            self._cached_cmap = default_cmap
            if 'parula' in cmaps:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('parula')+1)
            if 'seismic' in cmaps:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('seismic'))
            if 'tab10' in cmaps:
                self.cmapcombo.insertSeparator(
                    self.cmapcombo.findText('tab10'))
            widgets.append(self.cmapcombo)
            self.interpcombo = NXComboBox(
                self.change_interpolation, interpolations,
                default_interpolation)
            self._cached_interpolation = default_interpolation
            widgets.append(self.interpcombo)
        else:
            self.image = False
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

        self._axis = None

        self._block_count = 0

    def __repr__(self):
        return f'NXPlotTab("{self.name}")'

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
            if axis.lo and axis.hi:
                self.set_range()
                self.set_limits(axis.lo, axis.hi)
                self.set_sliders(axis.lo, axis.hi)
            self.axis.locked = False
            if np.all(self.axis.data[np.isfinite(self.axis.data)] <= 0.0):
                self.logbox.setChecked(False)
                self.logbox.setEnabled(False)
            else:
                if self.name != 'v':
                    self.logbox.setChecked(False)
                self.logbox.setEnabled(True)
            self.flipbox.setChecked(False)
            if self.name == 'y':
                self.smoothbox.setChecked(False)
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
            self._axis = None
        elif self.name == 'x':
            self._axis = self.plotview.ax.xaxis
        elif self.name == 'y':
            self._axis = self.plotview.ax.yaxis
        else:
            self._axis = None
        self.block_signals(False)

    def select_plot(self):
        self.plotview.num = int(self.plotcombo.currentText())
        self.plotview.plotdata = self.plotview.plots[self.plotview.num]['data']
        self.smoothing = self.plotview.plots[self.plotview.num]['smoothing']

    @property
    def offset(self):
        try:
            return float(self._axis.get_offset_text()._text)
        except Exception:
            return 0.0

    def edit_maxbox(self):
        if self.maxbox.text() == self.maxbox.old_value:
            return
        elif self.maxbox.value() <= self.axis.data.min():
            self.block_signals(True)
            self.maxbox.setValue(
                self.maxbox.valueFromText(self.maxbox.old_value))
            self.block_signals(False)
            return
        else:
            self.maxbox.old_value = self.maxbox.text()
        self.axis.hi = self.axis.max = self.maxbox.value()
        if self.name == 'v' and self.symmetric:
            self.axis.lo = self.axis.min = -self.axis.hi
            self.minbox.setValue(-self.axis.hi)
        elif self.axis.hi <= self.axis.lo:
            self.axis.lo = self.axis.data.min()
            self.minbox.setValue(self.axis.lo)
        self.block_signals(True)
        self.set_range()
        self.set_sliders(self.axis.lo, self.axis.hi)
        self.block_signals(False)

    def read_maxbox(self):
        """Update plot based on the maxbox value."""
        self.block_signals(True)
        hi = self.maxbox.value()
        if self.name == 'x' or self.name == 'y' or self.name == 'v':
            self.axis.hi = hi
            if self.name == 'v' and self.symmetric:
                self.axis.lo = -self.axis.hi
                self.minbox.setValue(-hi)
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
                self.minbox.setValue(self.axis.lo)
                self.replotSignal.replot.emit()
            else:
                self.axis.hi = hi
                if self.axis.hi < self.axis.lo:
                    self.axis.lo = self.axis.hi
                    self.minbox.setValue(self.axis.lo)
                elif np.isclose(self.axis.lo, self.axis.hi):
                    self.replotSignal.replot.emit()
        self.block_signals(False)

    def edit_minbox(self):
        if self.minbox.text() == self.minbox.old_value:
            return
        elif self.minbox.value() >= self.axis.data.max():
            self.block_signals(True)
            self.minbox.setValue(
                self.minbox.valueFromText(self.minbox.old_value))
            self.block_signals(False)
            return
        else:
            self.minbox.old_value = self.minbox.text()
        self.axis.lo = self.axis.min = self.minbox.value()
        if self.axis.lo >= self.axis.hi:
            self.axis.hi = self.axis.max = self.axis.data.max()
            self.maxbox.setValue(self.axis.hi)
        self.block_signals(True)
        self.set_range()
        self.set_sliders(self.axis.lo, self.axis.hi)
        self.block_signals(False)

    def read_minbox(self):
        self.block_signals(True)
        lo = self.minbox.value()
        if self.name == 'x' or self.name == 'y' or self.name == 'v':
            self.axis.lo = lo
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
        self.block_signals(False)

    def read_maxslider(self):
        self.block_signals(True)
        if self.name == 'v' and self.symmetric:
            _range = max(self.axis.max, self.axis.min_range)
            self.axis.hi = max((self.maxslider.value()*_range/self.slider_max),
                               self.axis.min_range)
            self.axis.lo = -self.axis.hi
            self.maxbox.setValue(self.axis.hi)
            self.minbox.setValue(self.axis.lo)
            self.minslider.setValue(self.slider_max - self.maxslider.value())
        else:
            self.axis.lo = self.minbox.value()
            _range = max(self.axis.max - self.axis.lo, self.axis.min_range)
            self.axis.hi = self.axis.lo + max(
                (self.maxslider.value() * _range / self.slider_max),
                self.axis.min_range)
            self.maxbox.setValue(self.axis.hi)
            _range = max(self.axis.hi - self.axis.min, self.axis.min_range)
            try:
                self.minslider.setValue(
                    self.slider_max * (self.axis.lo - self.axis.min) / _range)
            except (ZeroDivisionError, OverflowError, RuntimeWarning):
                self.minslider.setValue(0)
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
        self.axis.lo = self.axis.min + (self.minslider.value()*_range /
                                        self.slider_max)
        self.minbox.setValue(self.axis.lo)
        _range = max(self.axis.max-self.axis.lo, self.axis.min_range)
        try:
            self.maxslider.setValue(self.slider_max *
                                    (self.axis.hi-self.axis.lo)/_range)
        except (ZeroDivisionError, OverflowError, RuntimeWarning):
            self.maxslider.setValue(0)
        if self.name == 'x' or self.name == 'y':
            self.plotview.replot_axes()
        else:
            self.plotview.autoscale = False
            self.plotview.replot_image()
        self.block_signals(False)

    def set_sliders(self, lo, hi):
        lo, hi = float(lo), float(hi)
        if np.isclose(lo, hi):
            lo = lo - self.axis.min_range
            hi = hi + self.axis.min_range
        self.block_signals(True)
        _range = max(hi-self.axis.min, self.axis.min_range)
        try:
            self.minslider.setValue(self.slider_max *
                                    (lo - self.axis.min) / _range)
        except (ZeroDivisionError, OverflowError, RuntimeWarning):
            self.minslider.setValue(self.slider_max)
        _range = max(self.axis.max - lo, self.axis.min_range)
        try:
            self.maxslider.setValue(self.slider_max * (hi-lo) / _range)
        except (ZeroDivisionError, OverflowError, RuntimeWarning):
            self.maxslider.setValue(0)
        self.block_signals(False)

    def set_range(self):
        """Set the range and step sizes for the minbox and maxbox."""
        if np.isclose(self.axis.lo, self.axis.hi):
            self.axis.min, self.axis.max = nonsingular(self.axis.min,
                                                       self.axis.max)
        self.minbox.setRange(self.axis.min, self.axis.max)
        self.maxbox.setRange(self.axis.min, self.axis.max)
        stepsize = max((self.axis.max-self.axis.min)/100.0,
                       self.axis.min_range)
        self.minbox.setSingleStep(stepsize)
        self.maxbox.setSingleStep(stepsize)

    def get_limits(self):
        """Return the minbox and maxbox values."""
        return self.minbox.value(), self.maxbox.value()

    def set_limits(self, lo, hi):
        """Set the minbox and maxbox limits and sliders."""
        self.block_signals(True)
        if lo > hi:
            lo, hi = hi, lo
        self.axis.set_limits(lo, hi)
        if self.qualitative:
            self.minbox.setValue(self.axis.min_data)
            self.maxbox.setValue(self.axis.max_data)
        else:
            self.minbox.setValue(lo)
            self.maxbox.setValue(hi)
        if not self.zaxis:
            self.set_sliders(lo, hi)
        self.block_signals(False)

    @QtCore.Slot()
    def reset(self):
        self.set_limits(self.axis.min, self.axis.max)

    def block_signals(self, block=True):
        if block:
            self._block_count += 1
            if self._block_count > 1:
                return
        else:
            self._block_count -= 1
            if self._block_count > 0:
                return
        self.minbox.blockSignals(block)
        self.maxbox.blockSignals(block)
        if self.axiscombo is not None:
            self.axiscombo.blockSignals(block)
        if self.zaxis:
            self.lockbox.blockSignals(block)
            self.scalebox.blockSignals(block)
        else:
            self.minslider.blockSignals(block)
            self.maxslider.blockSignals(block)
            self.flipbox.blockSignals(block)
            self.logbox.blockSignals(block)
            if self.name == 'y':
                self.plotcombo.blockSignals(block)
                self.smoothbox.blockSignals(block)
        if self.image:
            self.cmapcombo.blockSignals(block)
            self.interpcombo.blockSignals(block)

    @property
    def log(self):
        try:
            return self.logbox.isChecked()
        except Exception:
            return False

    @log.setter
    def log(self, value):
        if value and np.all(
                self.axis.data[np.isfinite(self.axis.data)] <= 0.0):
            raise NeXusError("Cannot set log axis when all values are <= 0")
        try:
            if value != self.log:
                self.logbox.setChecked(value)
        except Exception:
            pass

    def change_log(self):
        try:
            if not self.log:
                self.axis.lo = self.axis.min
            self.plotview.set_log_axis(self.name)
        except Exception:
            pass

    @property
    def locked(self):
        try:
            return self.lockbox.isChecked()
        except Exception:
            return False

    @locked.setter
    def locked(self, value):
        try:
            self.axis.locked = value
            if value:
                lo, hi = self.get_limits()
                self.axis.diff = max(hi - lo, 0.0)
                self.maxbox.diff = self.minbox.diff = self.axis.diff
                self.minbox.setEnabled(False)
            else:
                self.axis.locked = False
                self.axis.diff = self.maxbox.diff = self.minbox.diff = 0.0
                self.minbox.setEnabled(True)
            self.lockbox.setChecked(value)
        except Exception:
            pass

    def change_lock(self):
        self.locked = self.locked

    def change_scale(self):
        if self.scalebox.isChecked():
            self.plotview.replot_image()

    @property
    def flipped(self):
        try:
            return self.flipbox.isChecked()
        except Exception:
            return False

    @flipped.setter
    def flipped(self, value):
        try:
            self.flipbox.setChecked(value)
        except Exception:
            pass

    def flip_axis(self):
        try:
            self.plotview.replot_axes()
        except Exception:
            pass

    def change_axis(self):
        """Change the axis for the current tab."""
        names = [self.plotview.axis[i].name for i in range(self.plotview.ndim)]
        idx = names.index(self.axiscombo.currentText())
        self.plotview.change_axis(self, self.plotview.axis[idx])

    def get_axes(self):
        """Return a list of the currently plotted axes."""
        if self.zaxis:
            plot_axes = [self.plotview.xaxis.name, self.plotview.yaxis.name]
            return [axis.nxname for axis in self.plotview.axes
                    if axis.nxname not in plot_axes]
        else:
            return [axis.nxname for axis in self.plotview.axes]

    def change_cmap(self):
        """Change the color map of the current plot."""
        self.cmap = self.cmapcombo.currentText()

    @property
    def cmap(self):
        """Return the currently selected color map."""
        try:
            return self.cmapcombo.currentText()
        except Exception:
            return default_cmap

    @cmap.setter
    def cmap(self, cmap):
        """Set the color map.

        If the color map is available but was not included in the
        default list when NeXpy was launched, it is added to the list.
        """
        global cmaps
        if cmap is None:
            cmap = self._cached_cmap
        try:
            if parse_version(mpl.__version__) >= parse_version('3.5.0'):
                cm = copy.copy(mpl.colormaps[cmap])
            else:
                cm = copy.copy(get_cmap(cmap))
        except ValueError:
            raise NeXusError(f"'{cmap}' is not registered as a color map")
        cmap = cm.name
        if cmap != self._cached_cmap:
            if cmap not in cmaps:
                cmaps.insert(6, cmap)
            idx = self.cmapcombo.findText(cmap)
            if idx < 0:
                if cmap in divergent_cmaps:
                    self.cmapcombo.addItem(cmap)
                else:
                    self.cmapcombo.insertItem(7, cmap)
                self.cmapcombo.setCurrentIndex(self.cmapcombo.findText(cmap))
            else:
                self.cmapcombo.setCurrentIndex(idx)
            cm.set_bad(self.plotview.bad)
            self.plotview.image.set_cmap(cm)
            if self.symmetric:
                if self.is_qualitative_cmap(self._cached_cmap):
                    self.axis.hi = self.axis.max
                self.make_symmetric()
                self.plotview.x, self.plotview.y, self.plotview.v = \
                    self.plotview.get_image()
                self.plotview.replot_image()
            elif self.qualitative:
                self.make_qualitative()
                self.plotview.x, self.plotview.y, self.plotview.v = \
                    self.plotview.get_image()
                self.plotview.replot_image()
            else:
                self.maxbox.setEnabled(True)
                self.minbox.setEnabled(True)
                self.maxslider.setEnabled(True)
                self.minslider.setEnabled(True)
                if self.is_symmetric_cmap(self._cached_cmap):
                    self.axis.lo = self.axis.min
                elif self.is_qualitative_cmap(self._cached_cmap):
                    self.axis.lo = self.axis.min
                    self.axis.hi = self.axis.max
                self.plotview.replot_image()
            self._cached_cmap = self.cmap

    @property
    def symmetric(self):
        """Return True if a divergent color map has been selected."""
        return self.is_symmetric_cmap(self.cmap)

    def is_symmetric_cmap(self, cmap):
        return cmap in divergent_cmaps

    def make_symmetric(self):
        """Symmetrize the minimum and maximum boxes and sliders."""
        self.axis.lo = -self.axis.hi
        self.maxbox.setMinimum(0.0)
        self.minbox.setMinimum(-self.maxbox.maximum())
        self.minbox.setMaximum(0.0)
        self.minbox.setValue(-self.maxbox.value())
        self.maxbox.setEnabled(True)
        self.minbox.setEnabled(False)
        self.minslider.setValue(self.slider_max - self.maxslider.value())
        self.minslider.setEnabled(False)
        self.maxslider.setEnabled(True)

    @property
    def qualitative(self):
        """Return True if a qualitative color map has been selected."""
        if (self.axis and self.axis.qualitative_data and
                self.is_qualitative_cmap(self.cmap)):
            return True
        else:
            return False

    def is_qualitative_cmap(self, cmap):
        return cmap in qualitative_cmaps

    def make_qualitative(self):
        """Remove access to minimum and maximum boxes and sliders."""
        self.minbox.setValue(self.axis.min_data)
        self.maxbox.setValue(self.axis.max_data)
        self.minbox.setEnabled(False)
        self.maxbox.setEnabled(False)
        self.maxslider.setEnabled(False)
        self.minslider.setEnabled(False)

    def change_interpolation(self):
        self.interpolation = self.interpcombo.currentText()

    @property
    def interpolation(self):
        return self.interpcombo.currentText()

    @interpolation.setter
    def interpolation(self, interpolation):
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

    def toggle_smoothing(self):
        try:
            self.plotview.plot_smooth()
        except NeXusError as error:
            report_error("Smoothing data", error)
            self.reset_smoothing()

    def reset_smoothing(self):
        if self.smoothbox:
            self.smoothbox.blockSignals(True)
            self.smoothbox.setChecked(False)
            self.smoothbox.blockSignals(False)

    @property
    def smoothing(self):
        if self.smoothbox:
            return self.smoothbox.isChecked()
        else:
            return False

    @smoothing.setter
    def smoothing(self, smoothing):
        if self.smoothbox:
            self.smoothbox.setChecked(smoothing)

    def fit_data(self):
        self.plotview.fit_data()

    def init_toolbar(self):
        _backward_icon = QtGui.QIcon(
            resource_filename('nexpy.gui', 'resources/backward-icon.png'))
        _pause_icon = QtGui.QIcon(
            resource_filename('nexpy.gui', 'resources/pause-icon.png'))
        _forward_icon = QtGui.QIcon(
            resource_filename('nexpy.gui', 'resources/forward-icon.png'))
        _refresh_icon = QtGui.QIcon(
            resource_filename('nexpy.gui', 'resources/refresh-icon.png'))
        self.toolbar = QtWidgets.QToolBar(parent=self)
        self.toolbar.setIconSize(QtCore.QSize(16, 16))
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
        except Exception as e:
            self.pause()
            raise e

    def playback(self):
        if self.plotview.ndim < 3:
            return
        try:
            self.locked = True
            if self.playsteps == -1:
                self.interval = int(self.timer.interval() / 2)
            else:
                self.playsteps = -1
                self.interval = 1000
            self.timer.setInterval(self.interval)
            self.timer.start(self.interval)
            self.playback_action.setChecked(True)
            self.playforward_action.setChecked(False)
        except Exception as e:
            self.pause()
            raise e

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
                self.interval = int(self.timer.interval() / 2)
            else:
                self.playsteps = 1
                self.interval = 1000
            self.timer.setInterval(self.interval)
            self.timer.start(self.interval)
            self.playforward_action.setChecked(True)
            self.playback_action.setChecked(False)
        except Exception as e:
            self.pause()
            raise e


class NXProjectionTab(QtWidgets.QWidget):

    def __init__(self, plotview=None):

        super().__init__()

        self.plotview = plotview

        self.xlabel = NXLabel('X-Axis:')
        self.xbox = NXComboBox(self.set_xaxis)
        self.ylabel = NXLabel('Y-Axis:')
        self.ybox = NXComboBox(self.set_yaxis)
        self.save_button = NXPushButton("Save", self.save_projection, self)
        self.plot_button = NXPushButton("Plot", self.plot_projection, self)
        self.sumbox = NXCheckBox("Sum", self.plotview.replot_data)
        self.panel_button = NXPushButton("Open Panel", self.open_panel, self)
        self.panel_combo = NXComboBox(slot=self.open_panel,
                                      items=['Projection', 'Limits', 'Scan'])

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addStretch()
        self.layout.addWidget(self.xlabel)
        self.layout.addWidget(self.xbox)
        self.layout.addWidget(self.ylabel)
        self.layout.addWidget(self.ybox)
        self.layout.addWidget(self.save_button)
        self.layout.addWidget(self.plot_button)
        self.layout.addWidget(self.sumbox)
        self.layout.addStretch()
        self.layout.addWidget(self.panel_button)
        self.layout.addWidget(self.panel_combo)
        self.layout.addStretch()
        self.setLayout(self.layout)

        self.setTabOrder(self.xbox, self.ybox)
        self.setTabOrder(self.ybox, self.save_button)
        self.setTabOrder(self.save_button, self.plot_button)
        self.setTabOrder(self.plot_button, self.sumbox)
        self.setTabOrder(self.sumbox, self.panel_button)

    def __repr__(self):
        return f'NXProjectionTab("{self.plotview.label}")'

    def get_axes(self):
        return [self.plotview.axis[axis].name
                for axis in range(self.plotview.ndim)]

    def set_axes(self):
        axes = self.get_axes()
        self.xbox.clear()
        self.xbox.addItems(axes)
        self.xbox.setCurrentIndex(self.xbox.findText(self.plotview.xaxis.name))
        if self.plotview.ndim <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
            self.layout.setSpacing(20)
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0, 'None')
            self.ybox.addItems(axes)
            self.ybox.setCurrentIndex(
                self.ybox.findText(self.plotview.yaxis.name))
            self.layout.setSpacing(5)

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
        except Exception:
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
        axes, limits = self.get_projection()
        if 'Projection' in plotviews:
            projection = plotviews['Projection']
        else:
            projection = NXPlotView('Projection')
        projection.plot(self.plotview.data.project(
            axes, limits, summed=self.summed), fmt='o')
        plotviews[projection.label].make_active()
        if 'Projection' in self.plotview.mainwindow.panels:
            self.plotview.mainwindow.panels['Projection'].update()

    def open_panel(self):
        panel = self.panel_combo.selected
        dialogs = {'Projection': ProjectionDialog, 'Limits': LimitDialog,
                   'Scan': ScanDialog}
        self.plotview.make_active()
        if not self.plotview.mainwindow.panel_is_running(panel):
            self.plotview.panels[panel] = dialogs[panel]()
        self.plotview.panels[panel].activate(self.plotview.label)
        self.plotview.panels[panel].setVisible(True)
        self.plotview.panels[panel].raise_()


class NXNavigationToolbar(NavigationToolbar2QT, QtWidgets.QToolBar):

    toolitems = (
        ('Home', 'Reset original view', 'home', 'home'),
        ('Back', 'Back to  previous view', 'back', 'back'),
        ('Forward', 'Forward to next view', 'forward', 'forward'),
        (None, None, None, None),
        ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
        ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
        (None, None, None, None),
        ('Aspect', 'Set aspect ratio to equal', 'equal', 'set_aspect'),
        ('Customize', 'Customize plot', 'customize', 'edit_parameters'),
        ('Style', 'Modify style', 'modify-style', 'modify_style'),
        (None, None, None, None),
        ('Save', 'Save the figure', 'export-figure', 'save_figure'),
        ('Export', 'Export data', 'export-data', 'export_data'),
        ('Add', 'Add plot data to tree', 'hand', 'add_data')
    )

    def __init__(self, canvas, parent=None, coordinates=True):
        QtWidgets.QToolBar.__init__(self, parent=parent)
        self.setAllowedAreas(QtCore.Qt.BottomToolBarArea)

        self.coordinates = coordinates
        self._actions = {}  # mapping of toolitem method names to QActions.
        self._subplot_dialog = None

        for text, tooltip_text, image_file, callback in self.toolitems:
            if text is None:
                self.addSeparator()
            else:
                a = self.addAction(self._icon(image_file + '.png'),
                                   text, getattr(self, callback))
                self._actions[callback] = a
                if callback in ['zoom', 'pan', 'set_aspect']:
                    a.setCheckable(True)
                if tooltip_text is not None:
                    a.setToolTip(tooltip_text)

        # Add the (x, y) location widget at the right side of the toolbar
        # The stretch factor is 1 which means any resizing of the toolbar
        # will resize this label instead of the buttons.
        if self.coordinates:
            self.locLabel = QtWidgets.QLabel("", self)
            self.locLabel.setAlignment(
                QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            self.locLabel.setSizePolicy(
                QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                      QtWidgets.QSizePolicy.Ignored))
            labelAction = self.addWidget(self.locLabel)
            labelAction.setVisible(True)

        NavigationToolbar2.__init__(self, canvas)
        if in_dark_mode() and (
                parse_version(QtCore.__version__) <= parse_version('5.15')):
            self.setStyleSheet('color: black')
        self.plotview = canvas.parent()
        self.zoom()

    def __repr__(self):
        return f'NXNavigationToolbar("{self.plotview.label}")'

    def _init_toolbar(self):
        pass

    def _icon(self, name, color=None):
        return QtGui.QIcon(os.path.join(resource_filename(
                                        'nexpy.gui', 'resources'), name))

    @property
    def active_mode(self):
        try:
            return self.mode.value
        except AttributeError:
            return self.mode

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
        """Launch the Customize Panel."""
        self.plotview.make_active()
        if not self.plotview.mainwindow.panel_is_running('Customize'):
            self.plotview.panels['Customize'] = CustomizeDialog()
        self.plotview.panels['Customize'].activate(self.plotview.label)
        self.plotview.panels['Customize'].setVisible(True)
        self.plotview.panels['Customize'].raise_()

    def modify_style(self):
        """Launch the Style Panel."""
        self.plotview.make_active()
        if not self.plotview.mainwindow.panel_is_running('Style'):
            self.plotview.panels['Style'] = StyleDialog()
        self.plotview.panels['Style'].activate(self.plotview.label)
        self.plotview.panels['Style'].setVisible(True)
        self.plotview.panels['Style'].raise_()

    def add_data(self):
        """Save the currently plotted data to the scratch workspace."""
        keep_data(self.plotview.plotdata)

    def export_data(self):
        """Launch the Export Dialog to export the current plot or data."""
        if self.plotview.plotdata.ndim == 1:
            data = self.plotview.data
        else:
            data = self.plotview.plotdata
        dialog = ExportDialog(data, parent=self)
        dialog.show()

    def release(self, event):
        """Disconnect signals and remove rubber bands after a right-click zoom.

        There have been multiple changes in Matplotlib in the zoom code, but
        this attempts to follow them in a backwards-compatible way.
        """
        if hasattr(self, '_zoom_info') and self._zoom_info:
            try:
                self.canvas.mpl_disconnect(self._zoom_info.cid)
            except AttributeError:
                self.canvas.mpl_disconnect(self._zoom_info['cid'])
            self.remove_rubberband()
        elif hasattr(self, '_ids_zoom'):
            for zoom_id in self._ids_zoom:
                self.canvas.mpl_disconnect(zoom_id)
            self.remove_rubberband()
            self._ids_zoom = []
            self._xypress = None
            self._button_pressed = None
            self._zoom_mode = None
            super().release(event)

    def release_zoom(self, event):
        """The release mouse button callback in zoom mode."""
        if event.button == 1:
            super().release_zoom(event)
            self._update_release()
        elif event.button == 3:
            self.plotview.zoom = None
            if not event.inaxes:
                self.home(autoscale=False)
            elif (self.plotview.xp and self.plotview.yp and
                  abs(event.x - self.plotview.xp) < 5 and
                  abs(event.y - self.plotview.yp) < 5):
                self.home(autoscale=False)
            elif self.plotview.xdata and self.plotview.ydata:
                xmin, xmax = sorted([event.xdata, self.plotview.xdata])
                ymin, ymax = sorted([event.ydata, self.plotview.ydata])
                if self.plotview.ndim == 1:
                    self.plotview.zoom = {'x': (xmin, xmax), 'y': (ymin, ymax)}
                else:
                    self.plotview.ptab.panel_combo.select('Projection')
                    self.plotview.ptab.open_panel()
                    panel = self.plotview.panels['Projection']
                    tab = panel.tabs[self.plotview.label]
                    tab.minbox[self.plotview.xaxis.dim].setValue(xmin)
                    tab.maxbox[self.plotview.xaxis.dim].setValue(xmax)
                    tab.minbox[self.plotview.yaxis.dim].setValue(ymin)
                    tab.maxbox[self.plotview.yaxis.dim].setValue(ymax)
            self.release(event)

    def release_pan(self, event):
        """The release mouse button callback in pan mode."""
        super().release_pan(event)
        self._update_release()

    def _update_release(self):
        xmin, xmax = self.plotview.ax.get_xlim()
        ymin, ymax = self.plotview.ax.get_ylim()
        xmin, ymin = self.plotview.inverse_transform(xmin, ymin)
        xmax, ymax = self.plotview.inverse_transform(xmax, ymax)
        self.plotview.xtab.set_limits(xmin, xmax)
        self.plotview.ytab.set_limits(ymin, ymax)
        if self.plotview.ndim == 1:
            try:
                self.plotview.plot_smooth()
            except Exception:
                pass
        try:
            xdim = self.plotview.xtab.axis.dim
            ydim = self.plotview.ytab.axis.dim
        except AttributeError:
            return
        self.plotview.zoom = {'x': (xmin, xmax),
                              'y': (ymin, ymax)}
        self.plotview.update_panels()

    def _update_view(self):
        super()._update_view()
        ls = self.plotview.limits
        self.plotview.xtab.axis.min, self.plotview.xtab.axis.max = ls[0], ls[1]
        self.plotview.ytab.axis.min, self.plotview.ytab.axis.max = ls[2], ls[3]
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
        if self.plotview.image:
            self.plotview.update_colorbar()
        self.plotview.update_panels()

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
        try:
            self._update_cursor(event)
        except AttributeError:
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
