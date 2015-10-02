#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Plotting window
"""

import pkg_resources
import numpy as np
from nexpy.gui.pyqt import QtCore, QtGui
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_qt4 import FigureManagerQT as FigureManager
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.image import NonUniformImage
from matplotlib.colors import LogNorm, Normalize
from matplotlib.cm import get_cmap
from matplotlib.patches import Circle, Ellipse, Rectangle
from matplotlib.transforms import nonsingular

from nexusformat.nexus import NXfield, NXdata, NXroot, NeXusError


plotview = None
plotviews = {}
cmaps = ['autumn', 'bone', 'cool', 'copper', 'flag', 'gray', 'hot', 
         'hsv', 'jet', 'pink', 'prism', 'spring', 'summer', 'winter', 
         'spectral', 'rainbow']
interpolations = ['nearest', 'bilinear', 'bicubic', 'spline16', 'spline36', 
                  'hanning', 'hamming', 'hermite', 'kaiser', 'quadric', 
                  'catrom', 'gaussian', 'bessel', 'mitchell', 'sinc', 'lanczos']

colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']


def report_error(context, error):
    import mainwindow
    mainwindow.report_error(context, error)


def new_figure_manager(label=None, *args, **kwargs):
    """
    Create a new figure manager instance
    
    Figure numbers > 100 are preserved for the Projection and Fit windows.
    """
    if label is None:
        label = ''
    if label == 'Projection':
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
    global plotview, plotviews
    if label in plotviews:
        plotviews[label].make_active()
        plotview = plotviews[label]
    else:
        plotview = NXPlotView(label)   
    return plotview


def get_plotview():
    global plotview
    return plotview


class NXCanvas(FigureCanvas):

    def __init__(self, figure):

        self.axes = figure.add_subplot(111)
        self.axes.hold(False)

        FigureCanvas.__init__(self, figure)

        FigureCanvas.setSizePolicy(self,
                                   QtGui.QSizePolicy.MinimumExpanding,
                                   QtGui.QSizePolicy.MinimumExpanding)
        FigureCanvas.updateGeometry(self)


class NXFigureManager(FigureManager):

    def __init__(self, canvas, num):
        FigureManagerBase.__init__(self, canvas, num)
        self.canvas = canvas

        def notify_axes_change(fig):
            # This will be called whenever the current axes is changed
            if self.canvas.toolbar is not None:
                self.canvas.toolbar.update()
        self.canvas.figure.add_axobserver(notify_axes_change)


class NXPlotView(QtGui.QDialog):
    """
    PyQT widget containing a NeXpy plot.
    
    The widget consists of a QVBoxLayout containing a matplotlib canvas over a 
    tab widget, which contains NXPlotTab objects for adjusting plot axes:
    
        vtab: Intensity axis (color scale) for two- and higher-dimensional plots
        xtab: x-axis (horizontal)
        ytab: y-axis (vertical); this is the intensity axis for one-dimensional plots
        ztab: plotting limits for non-plotted dimensions in three- or higher dimensional
              plots
        ptab: parameters for defining projections (plotted in a separate window)
        otab: Matplotlib buttons for adjusting plot markers and labels, zooming,
              and saving plots as PNG files
    """
    def __init__(self, label=None, parent=None):
        
        if parent is None:
            from nexpy.gui.consoleapp import _mainwindow
            parent = _mainwindow

        super(NXPlotView, self).__init__(parent)

        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                           QtGui.QSizePolicy.MinimumExpanding)

        global plotview, plotviews
        if label in plotviews:
            plotviews[label].close()

        self.figuremanager = new_figure_manager(label)
        self.canvas = self.figuremanager.canvas
        self.canvas.setParent(self)
        self.canvas.setFocusPolicy(QtCore.Qt.ClickFocus)
        # Since we have only one plot, we can use add_axes 
        # instead of add_subplot, but then the subplot
        # configuration tool in the navigation toolbar wouldn't
        # work.
        #
        # self.canvas.mpl_connect('pick_event', self.on_pick)

        Gcf.set_active(self.figuremanager)
        def make_active(event):
            if 'Projection' not in self.label:
                self.make_active()
            if event.button == 1:
                self.xdata = event.xdata
                self.ydata = event.ydata
            elif event.button == 3:
                hasattr(self, 'otab')
                self.otab.home()
        cid = self.canvas.mpl_connect('button_press_event', make_active)
        self.canvas.figure.show = lambda *args: self.show()
        self.figuremanager._cidgcf = cid
        self.figuremanager.window = self
        self._destroying = False
        self.figure = self.canvas.figure
        self.number = self.figuremanager.num
        if label:
            self.label = label
            self.figure.set_label(self.label)
        else:
            self.label = "Figure %d" % self.number
        
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.canvas)

        self.tab_widget = QtGui.QTabWidget()
        self.tab_widget.setFixedHeight(80)

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
        
        vbox.addWidget(self.tab_widget)
        self.setLayout(vbox)

        self.num = 0
        self.axis = {}
        self.xaxis = self.yaxis = self.zaxis = None
        self.xmin = self.xmax = self.ymin = self.ymax = self.vmin = self.vmax = None

        self.colorbar = None
        self.zoom = None
        self.aspect = 'auto'
        
        self.setWindowTitle(self.label)

        plotview = self
        plotviews[self.label] = self
        self.plotviews = plotviews

        self.panel = None

        if self.label != "Main":
            self.add_menu_action()
            self.show()

        #Initialize the plotting window with a token plot
        self.plot(NXdata(signal=NXfield([0,1], name='y'), 
                  axes=NXfield([0,1], name='x')), fmt='wo', mec='w')

#        self.grid_cb = QtGui.QCheckBox("Show &Grid")
#        self.grid_cb.setChecked(False)
#        self.grid_cb.stateChanged.connect(self.on_draw)

    def __repr__(self):
        return 'NXPlotView("%s")' % self.label

    def make_active(self):
        global plotview
        plotview = self
        Gcf.set_active(self.figuremanager)
        self.show()
        from nexpy.gui.consoleapp import _mainwindow, _shell
        if self.label == 'Main':
            _mainwindow.raise_()
        else:
            self.raise_()
        self.update_active()
        _shell['plotview'] = self

    def update_active(self):
        if 'Projection' not in self.label:
            from nexpy.gui.consoleapp import _mainwindow
            _mainwindow.update_active(self.number)
    
    def add_menu_action(self):
        from nexpy.gui.consoleapp import _mainwindow
        if self.label not in _mainwindow.active_action:
            _mainwindow.make_active_action(self.number, self.label)
        _mainwindow.update_active(self.number)

    def remove_menu_action(self):
        from nexpy.gui.consoleapp import _mainwindow
        if self.number in _mainwindow.active_action:
            _mainwindow.window_menu.removeAction(
                _mainwindow.active_action[self.number])
            del _mainwindow.active_action[self.number]
        if self.number == _mainwindow.previous_active:
            _mainwindow.previous_active = 1
        _mainwindow.make_active(_mainwindow.previous_active)

    def save_plot(self):
        """
        Opens a dialog box for saving a plot as a PNG file
        """
        file_choices = "PNG (*.png)|*.png"
        
        path = unicode(getSaveFileName(self, 'Save file', '', file_choices))
        if path:
            self.canvas.print_figure(path, dpi=self.dpi)
            self.statusBar().showMessage('Saved to %s' % path, 2000)

    def plot(self, data, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             vmin=None, vmax=None, **opts):
        """
        This is the function invoked to plot an NXdata group with optional limits
        and matplotlib options
        
        Arguments
        ---------
        data : NXdata
            This is the NXdata object that contains the signal and associated axes.
        fmt : string
            The format argument is used to set the color and type of the markers or lines
            for one-dimensional plots, using the standard matplotlib syntax. The default
            is set to blue circles. All keyword arguments accepted by
            matplotlib.pyplot.plot can be used to customize the plot.
        xmin, xmax, ymin, ymax, vmin, vmax : float
            Axis and signal limits. These parameters are optional keyword arguments
            in the NXgroup plot method; if not specified, they are set to None.
        opts : dict
            This dictionary can contain any valid matplotlib options.
        """

        over = opts.pop("over", False)
        image = opts.pop("image", False)
        log = opts.pop("log", False)
        logx = opts.pop("logx", False)
        logy = opts.pop("logy", False)
        cmap = opts.pop("cmap", None)

        self.data = data
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
                
            self.plot_points(fmt, over, **opts)

        #Higher-dimensional plot
        else:
            if xmin: 
                self.xaxis.lo = xmin
            if xmax: 
                self.xaxis.hi = xmax
            if ymin: 
                self.yaxis.lo = ymin
            if ymax: 
                self.yaxis.hi = ymax
            if vmin: 
                self.vaxis.lo = vmin
            if vmax: 
                self.vaxis.hi = vmax
            if log:
                self.vtab.logbox.setChecked(True)
            else:
                self.vtab.logbox.setChecked(False)
 
            self.plot_image(over, **opts)

        self.limits = (self.xaxis.min, self.xaxis.max,
                       self.yaxis.min, self.yaxis.max)

        if over:
            self.update_tabs()
        else:
            self.init_tabs()

        if self.rgb_image:
            self.aspect = 'equal'
            self.ytab.flipped = True
            self.replot_axes(draw=False)
        elif self.xaxis.reversed or self.yaxis.reversed:
            self.replot_axes(draw=False)
        else:
            self.aspect = 'auto'

        self.offsets = False

        self.draw()
        self.otab.push_current()
        mpl.interactive(True)

    def get_plotdata(self, over=False):
        """Return an NXdata group containing the plottable data
        
        This function removes size 1 arrays, creates axes if none are specified
        and initializes the NXPlotAxis instances.
        """
        if self.ndim > 2:
            idx=[np.s_[0] if s==1 else np.s_[:] for s in self.data.nxsignal.shape]
            for i in range(len(idx)):
                if idx.count(slice(None,None,None)) > 2:
                    idx[i] = 0
            self.signal = self.data.nxsignal[tuple(idx)][()]
        elif self.rgb_image:
            self.signal = self.data.nxsignal[()]
        else:
            self.signal = self.data.nxsignal[()].reshape(self.shape)

        if self.data.plot_axes is not None:
            axes = self.data.plot_axes
        else:
            axes = [NXfield(np.arange(self.shape[i]), name='Axis%s'%i)
                            for i in range(self.ndim)]

        self.axes = [NXfield(axes[i].nxdata, name=axes[i].nxname,
                             attrs=axes[i].safe_attrs) for i in range(self.ndim)]

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
                self.axis[i].dim = i

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
                self.zaxis = self.axis[self.ndim-3]
                self.zaxis.lo = self.zaxis.hi = self.zaxis.min
                for i in range(self.ndim-3):
                    self.axis[i].lo = self.axis[i].hi \
                        = self.axis[i].data.min()
            else:
                self.zaxis = None
            self.vaxis = self.axis['signal']
            plotdata = NXdata(self.signal, [self.axes[i] for i in [-2,-1]])

        plotdata['title'] = self.title
       
        return plotdata

    def get_points(self):
        x = self.xaxis.centers
        y = self.yaxis.data
        if self.errors:
            e = self.errors.nxdata
        else:
            e = None
        return x, y, e
    
    def plot_points(self, fmt, over=False, **opts):

        mpl.interactive(False)
        
        if not over: 
            self.figure.clf()
        ax = self.figure.gca()

        self.x, self.y, self.e = self.get_points()

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

        self.colorbar = None

    def get_image(self):
        x = self.xaxis.boundaries
        y = self.yaxis.boundaries
        v = self.plotdata.nxsignal.nxdata
        return x, y, v

    def plot_image(self, over=False, **opts):

        mpl.interactive(False)
        if not over: 
            self.figure.clf()

        self.x, self.y, self.v = self.get_image()

        self.set_data_limits()
        
        if self.vtab.logbox.isChecked():
            opts["norm"] = LogNorm(self.vaxis.lo, self.vaxis.hi)
        else:
            opts["norm"] = Normalize(self.vaxis.lo, self.vaxis.hi)

        ax = self.figure.gca()
        ax.autoscale(enable=True)
        ax.format_coord = self.format_coord

        if self.xaxis.reversed:
            left, right = self.xaxis.max, self.xaxis.min
        else:
            left, right = self.xaxis.min, self.xaxis.max
        if self.yaxis.reversed:
            bottom, top = self.yaxis.max, self.yaxis.min
        else:
            bottom, top = self.yaxis.min, self.yaxis.max
        extent = (left, right, bottom, top)

        if 'aspect' in opts:
            self.aspect = opts['aspect']
            del opts['aspect']
        if self.rgb_image or self.equally_spaced:
            opts['origin'] = 'lower'
            if 'interpolation' not in opts:
                opts['interpolation'] = 'nearest'
            self.image = ax.imshow(self.v, extent=extent, cmap=self.cmap, 
                                   **opts)
        else:
            self.image = ax.pcolormesh(self.x, self.y, self.v, cmap=self.cmap, 
                                       **opts)
        self.image.get_cmap().set_bad('k', 1.0)
        ax.set_aspect(self.aspect)
        
        if not self.rgb_image:
            self.colorbar = self.figure.colorbar(self.image, ax=ax)

        xlo, xhi = ax.set_xlim(self.xaxis.min, self.xaxis.max)
        ylo, yhi = ax.set_ylim(self.yaxis.min, self.yaxis.max)
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

        self.xaxis.min, self.xaxis.max = self.x.min(), self.x.max()
        self.yaxis.min, self.yaxis.max = self.y.min(), self.y.max()
        
        vmin, vmax = self.image.get_clim()
        if self.vaxis.min > vmin:
            self.vaxis.min = vmin
        if self.vaxis.max < vmax:
            self.vaxis.max = vmax
        
        self.vtab.set_axis(self.vaxis)

    @property
    def shape(self):
        _shape = list(self.data.nxsignal.shape)
        while 1 in _shape:
            _shape.remove(1)
        if self.rgb_image:
            _shape = _shape[:-1]
        return tuple(_shape)

    @property
    def ndim(self):
        return len(self.shape)

    def set_data_limits(self):
        if self.vaxis.lo is None or self.autoscale:
            try:
                self.vaxis.lo = self.vaxis.min = np.nanmin(self.v[self.v>-np.inf])
            except:
                self.vaxis.lo = self.vaxis.min = 0.0
        if self.vaxis.hi is None or self.autoscale:
            try:
                self.vaxis.hi = self.vaxis.max = np.nanmax(self.v[self.v<np.inf])
            except:
                self.vaxis.hi = self.vaxis.max = 0.1
        if self.vtab.logbox.isChecked():
            try:
                self.vaxis.lo = max(self.vaxis.lo, self.v[self.v>0.0].min())
            except ValueError:
                self.vaxis.lo, self.vaxis.hi = (0.01, 0.1)
        self.vtab.set_axis(self.vaxis)

    def replot_data(self, newaxis=False):
        axes = [self.yaxis.dim, self.xaxis.dim]
        limits = []
        xmin, xmax, ymin, ymax = self.limits
        for i in range(self.ndim):
            if i in axes:
                if i == self.xaxis.dim:
                    limits.append((xmin, xmax))
                else:
                    limits.append((ymin, ymax))
            else:
                limits.append((self.axis[i].lo, self.axis[i].hi))
        if self.data.nxsignal.shape != self.data.plot_shape:
            axes, limits = fix_projection(self.data.nxsignal.shape, axes, limits)
        self.plotdata = self.data.project(axes, limits)
        self.plotdata.title = self.title
        if newaxis:
            self.plot_image()
            self.draw()
        elif self.equally_spaced:
            self.x, self.y, self.v = self.get_image()
            self.image.set_data(self.v)
            if self.xaxis.reversed:
                xmin, xmax = xmax, xmin
            if self.yaxis.reversed:
                ymin, ymax = ymax, ymin
            self.image.set_extent((xmin, xmax, ymin, ymax))
            self.replot_image()
        else:
            self.x, self.y, self.v = self.get_image()
            self.image.set_array(self.v.ravel())
            self.replot_image()

    def replot_image(self):
        try:
            self.set_data_limits()
            self.image.set_clim(self.vaxis.lo, self.vaxis.hi)
            self.replot_axes()
        except:
            pass

    def replot_axes(self, draw=True):
        ax = self.figure.gca()
        xmin, xmax = self.xaxis.get_limits()
        if ((self.xaxis.reversed and not self.xtab.flipped) or
            (not self.xaxis.reversed and self.xtab.flipped)):
            ax.set_xlim(xmax, xmin)
        else:
            ax.set_xlim(xmin, xmax)
        ymin, ymax = self.yaxis.get_limits()
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

    def set_log_image(self):
        if self.vtab.logbox.isChecked():
            self.set_data_limits()
            self.image.set_norm(LogNorm(self.vaxis.lo, self.vaxis.hi))
            self.colorbar.set_norm(LogNorm(self.vaxis.lo, self.vaxis.hi))
        else:
            self.image.set_norm(Normalize(self.vaxis.lo, self.vaxis.hi))
            self.colorbar.set_norm(Normalize(self.vaxis.lo, self.vaxis.hi))
        self.replot_image()

    def set_log_axis(self):
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

    def set_plot_limits(self, xmin=None, xmax=None, ymin=None, ymax=None, vmin=None, vmax=None):
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

    def reset_plot_limits(self):
        xmin, xmax, ymin, ymax = self.limits
        self.xaxis.min = self.xaxis.lo = self.xtab.minbox.old_value = xmin
        self.xaxis.max = self.xaxis.hi = self.xtab.maxbox.old_value = xmax
        self.yaxis.min = self.yaxis.lo = self.ytab.minbox.old_value = ymin
        self.yaxis.max = self.yaxis.hi = self.ytab.maxbox.old_value = ymax
        if self.ndim == 1:
            self.replot_axes()
        else:
            try:
                self.vaxis.min = self.vaxis.lo = np.nanmin(self.v[self.v>-np.inf])
                self.vaxis.max = self.vaxis.hi = np.nanmax(self.v[self.v<np.inf])
            except:
                self.vaxis.min = self.vaxis.lo = 0.0
                self.vaxis.max = self.vaxis.hi = 0.1
            self.vtab.set_axis(self.vaxis)
            self.replot_image()
        self.update_tabs()

    def _aspect(self):
        return self._aspect_value
        
    def _set_aspect(self, aspect):
        if aspect == 'auto':
            self._aspect_value = 'auto'
            self.otab._actions['set_aspect'].setChecked(False)
        else:
            self._aspect_value = aspect
            self.otab._actions['set_aspect'].setChecked(True)
        try:
            ax = self.figure.axes[0]
            ax.set_aspect(aspect)
            self.canvas.draw()
        except:
            pass

    aspect = property(_aspect, _set_aspect, "Property: Aspect ratio value")

    def _autoscale(self):
        if self.ndim > 2 and self.ztab.scalebox.isChecked():
            return True
        else:
            return False

    def _set_autoscale(self, value=True):
        self.ztab.scalebox.setChecked(value)

    autoscale = property(_autoscale, _set_autoscale, "Property: Autoscale boolean")

    def _cmap(self):
        return self.vtab.cmap

    def _set_cmap(self, cmap):
        try:
            self.vtab.set_cmap(get_cmap(cmap).name)
            self.vtab.change_cmap()
        except ValueError as error:
            raise NeXusError(str(error))

    cmap = property(_cmap, _set_cmap, "Property: color map")

    def _interpolation(self):
        if not self.equally_spaced:
            return 'nearest'
        else:
            return self.vtab.interpolation

    def _set_interpolation(self, interpolation):
        try:
            self.vtab.set_interpolation(interpolation)
            self.vtab.change_interpolation()
        except ValueError as error:
            raise NeXusError(str(error))

    interpolation = property(_interpolation, _set_interpolation, 
                             "Property: interpolation method")

    def _offsets(self):
        return self._axis_offsets

    def _set_offsets(self, value):
        self._axis_offsets = value
        self.ax.ticklabel_format(useOffset=self._axis_offsets)
        self.draw()

    offsets = property(_offsets, _set_offsets, "Property: Axis offsets property")

    @property
    def equally_spaced(self):
        return self.xaxis.equally_spaced and self.yaxis.equally_spaced

    @property
    def ax(self):
        return self.figure.gca()

    def draw(self):
        self.canvas.draw_idle()

    def vline(self, x, ymin=None, ymax=None, **opts):
        ylo, yhi = self.yaxis.get_limits()
        if ymin is None:
            ymin = ylo
        if ymax is None:
            ymax = yhi
        ax = self.figure.axes[0]
        line = ax.vlines(float(x), ymin, ymax, **opts)
        self.canvas.draw()
        return line

    def hline(self, y, xmin=None, xmax=None, **opts):
        xlo, xhi = self.xaxis.get_limits()
        if xmin is None:
            xmin = xlo
        if xmax is None:
            xmax = xhi
        ax = self.figure.axes[0]
        line = ax.hlines(float(y), xmin, xmax, **opts)
        self.canvas.draw()
        return line

    def vlines(self, x, ymin=None, ymax=None, **opts):
        ylo, yhi = self.yaxis.get_limits()
        if ymin is None:
            ymin = ylo
        if ymax is None:
            ymax = yhi
        ax = self.figure.axes[0]
        lines = ax.vlines(x, ymin, ymax, **opts)
        self.canvas.draw()
        return lines

    def hlines(self, y, xmin=None, xmax=None, **opts):
        xlo, xhi = self.xaxis.get_limits()
        if xmin is None:
            xmin = xlo
        if xmax is None:
            xmax = xhi
        ax = self.figure.axes[0]
        lines = ax.hlines(y, xmin, xmax, **opts)
        self.canvas.draw()
        return lines

    def crosshairs(self, x, y, **opts):
        crosshairs = []
        crosshairs.append(self.vline(float(x), **opts))
        crosshairs.append(self.hline(float(y), **opts))
        return crosshairs        

    def rectangle(self, x, y, dx, dy, **opts):
        ax = self.figure.axes[0]
        rectangle = ax.add_patch(Rectangle((float(x),float(y)), 
                                            float(dx), float(dy), **opts))
        if 'facecolor' not in opts:
            rectangle.set_facecolor('none')
        self.canvas.draw()
        return rectangle

    def ellipse(self, x, y, dx, dy, **opts):
        ax = self.figure.axes[0]
        ellipse = ax.add_patch(Ellipse((float(x),float(y)), 
                                        float(dx), float(dy), **opts))
        if 'facecolor' not in opts:
            ellipse.set_facecolor('none')
        self.canvas.draw()
        return ellipse

    def circle(self, x, y, radius, **opts):
        ax = self.figure.axes[0]
        circle = ax.add_patch(Circle((float(x),float(y)), radius, **opts))
        if 'facecolor' not in opts:
            circle.set_facecolor('none')
        self.canvas.draw()
        return circle

    def init_tabs(self):
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
            if not self.label.startswith("Projection"):
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
        if self.panel:
            self.panel.close()

    def update_tabs(self):
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

    def change_axis(self, tab, axis):
        """Replace the axis in a plot tab"""
        xmin, xmax, ymin, ymax = self.limits
        if tab == self.xtab and axis == self.yaxis:
            self.yaxis = self.ytab.axis = self.xtab.axis
            self.xaxis = self.xtab.axis = axis
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
            self.limits = (ymin, ymax, xmin, xmax)
            self.replot_data(newaxis=True)
        elif tab == self.ytab and axis == self.xaxis:
            self.xaxis = self.xtab.axis = self.ytab.axis
            self.yaxis = self.ytab.axis = axis
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
            self.limits = (ymin, ymax, xmin, xmax)
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
            self.zaxis.set_limits(self.zaxis.min, self.zaxis.min)
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.ztab.set_axis(self.zaxis)
            self.vtab.set_axis(self.vaxis)
            self.ztab.locked = True
            self.replot_data(newaxis=True)
            if self.panel:
                self.panel.update_limits()
        self.otab.update()

    def format_coord(self, x, y):
        try:
            if plotview.xaxis.reversed:
                col = np.searchsorted(x-plotview.xaxis.boundaries, 0.0) - 1
            else:
                col = np.searchsorted(plotview.xaxis.boundaries-x, 0.0) - 1
            if plotview.yaxis.reversed:
                row = np.searchsorted(y-plotview.yaxis.boundaries, 0.0) - 1
            else:
                row = np.searchsorted(plotview.yaxis.boundaries-y, 0.0) - 1
            z = self.v[row,col]
            return 'x=%1.4f y=%1.4f\nv=%1.4g'%(x, y, z)
        except:
            return ''

    def close_view(self):
        self.remove_menu_action()
        Gcf.destroy(self.number)
        if self.label in plotviews:
            del plotviews[self.label]
        if self.panel:
            self.panel.close()
        from nexpy.gui.consoleapp import _mainwindow
        if _mainwindow.panels.tabs.count() == 0:
            _mainwindow.panels.setVisible(False)

    def closeEvent(self, event):
        self.close_view()
        self.deleteLater()
        event.accept()


class NXPlotAxis(object):

    def __init__(self, axis, dim=None, dimlen=None):
        self.name = axis.nxname
        self.data = axis.nxdata
        self.dim = dim
        self.reversed = False
        self.flipped = False
        self.equally_spaced = True
        if self.data is not None:
            if dimlen is None:
                self.centers = None
                self.boundaries = None
                try:
                    self.min = np.nanmin(self.data[self.data>-np.inf])
                    self.max = np.nanmax(self.data[self.data<np.inf])
                except:
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
                    self.min = np.nanmin(self.boundaries[self.boundaries>-np.inf])
                    self.max = np.nanmax(self.boundaries[self.boundaries<np.inf])
                except:
                    self.min = 0.0
                    self.max = 0.1
        else:
            self.centers = None
            self.boundaries = None
            self.min = None
            self.max = None
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
        if lo > hi:
            lo, hi = hi, lo
        self.lo, self.hi = lo, hi
        self.diff = hi - lo

    def get_limits(self):
        return float(self.lo), float(self.hi)

    @property
    def min_range(self):
        return self.max_range*1e-6

    @property
    def max_range(self):
        return self.max - self.min


class NXReplotSignal(QtCore.QObject):
    
    replot = QtCore.Signal() 


class NXPlotTab(QtGui.QWidget):

    def __init__(self, name=None, axis=True, log=True, zaxis=False, image=False,
                 plotview=None):

        super(NXPlotTab, self).__init__()

        self.name = name
        self.plotview = plotview

        hbox = QtGui.QHBoxLayout()
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
            self.scalebox = self.checkbox("Autoscale", self.plotview.replot_image)
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
            self.cmapcombo.setCurrentIndex(self.cmapcombo.findText('jet'))
            widgets.append(self.cmapcombo)
            self.interpolations = interpolations
            self.interpcombo = self.combobox(self.change_interpolation)
            self.interpcombo.addItems(self.interpolations)
            self.set_interpolation('nearest')
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
            if self.plotview.equally_spaced:
                self.interpcombo.setVisible(True)
                self.set_interpolation(self._cached_interpolation)
                self.change_interpolation()         
            else:
                self.interpcombo.setVisible(False)
        self.block_signals(False)

    def combobox(self, slot):
        combobox = QtGui.QComboBox()
        combobox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        combobox.setMinimumWidth(100)
        combobox.activated.connect(slot)
        return combobox

    def spinbox(self, slot):
        spinbox = NXSpinBox()
        spinbox.setAlignment(QtCore.Qt.AlignRight)
        spinbox.setFixedWidth(100)
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(False)
        spinbox.valueChanged.connect(slot)
        return spinbox

    def doublespinbox(self, slot):
        doublespinbox = NXDoubleSpinBox()
        doublespinbox.setAlignment(QtCore.Qt.AlignRight)
        doublespinbox.setFixedWidth(100)
        doublespinbox.setKeyboardTracking(False)
        doublespinbox.editingFinished.connect(slot)
        return doublespinbox

    def slider(self, slot):
        slider = QtGui.QSlider(QtCore.Qt.Horizontal)
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
        checkbox = QtGui.QCheckBox(label)
        checkbox.setChecked(False)
        checkbox.clicked.connect(slot)
        return checkbox

    def pushbutton(self, label, slot):
        button = QtGui.QPushButton(label)
        button.clicked.connect(slot)
        return button

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

    @QtCore.Slot()
    def read_maxbox(self):
        hi = self.maxbox.value()
        if np.isclose(hi, self.maxbox.old_value):
            return
        if self.name == 'x' or self.name == 'y' or self.name == 'v':
            if hi > self.axis.lo:
                self.axis.hi = hi
            else:
                self.maxbox.setValue(self.maxbox.old_value)
                return
            self.axis.max = self.axis.hi
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

    def read_minslider(self):
        self.block_signals(True)
        self.axis.hi = self.maxbox.value()
        _range = max(self.axis.hi - self.axis.min, self.axis.min_range)
        self.axis.lo = self.axis.min + (self.minslider.value() * _range / 1000)
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

    def read_maxslider(self):
        self.block_signals(True)
        self.axis.lo = self.minbox.value()
        _range = max(self.axis.max - self.axis.lo, self.axis.min_range)
        self.axis.hi = self.axis.lo + max((self.maxslider.value() * _range / 1000), self.axis.min_range)
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
            if self.name == 'v':
                if self.plotview.colorbar:
                    self.plotview.set_log_image()
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
        return self.minbox.value(), self.maxbox.value()

    def set_limits(self, lo, hi):
        if lo > hi:
            lo, hi = hi, lo
        self.axis.set_limits(lo, hi)
        self.minbox.setValue(lo)
        self.maxbox.setValue(hi)
        if not self.zaxis:
            self.set_sliders(lo, hi)

    def change_axis(self):
        names = [self.plotview.axis[i].name for i in range(self.plotview.ndim)]
        idx = names.index(self.axiscombo.currentText())
        self.plotview.change_axis(self, self.plotview.axis[idx])

    def get_axes(self):
        if self.zaxis:
            plot_axes = [self.plotview.xaxis.name, self.plotview.yaxis.name]
            return  [axis.nxname for axis in self.plotview.axes 
                     if axis.nxname not in plot_axes]
        else:
            return [axis.nxname for axis in self.plotview.axes]

    def change_cmap(self):
        try:
            self.plotview.image.set_cmap(self.cmap)
            self.plotview.draw()
        except Exception:
            pass

    def set_cmap(self, cmap):
        self.cmapcombo.setCurrentIndex(self.cmapcombo.findText(cmap))

    @property
    def cmap(self):
        return self.cmapcombo.currentText()

    def change_interpolation(self):
        try:
            self.plotview.image.set_interpolation(self.interpolation)
            self.plotview.draw()
            self._cached_interpolation = self.interpolation
        except Exception:
            pass

    def set_interpolation(self, interpolation):
        if interpolation in self.interpolations:
            self.interpcombo.setCurrentIndex(
                self.interpcombo.findText(interpolation))
            self._cached_interpolation = interpolation
        else:
            raise NeXusError('Invalid interpolation method')

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
        self.toolbar = QtGui.QToolBar(parent=self)
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


class NXTextBox(QtGui.QLineEdit):

    def value(self):
        return float(unicode(self.text()))

    def setValue(self, value):
        self.setText(str(float('%.4g' % value)))


class NXSpinBox(QtGui.QSpinBox):

    def __init__(self, data=None):
        super(NXSpinBox, self).__init__()
        self.data = data
        if self.data is not None:
            self.boundaries = boundaries(self.data, self.data.shape[0])
        self.validator = QtGui.QDoubleValidator()
        self.old_value = None
        self.diff = None
        self.pause = False

    def value(self):
        if self.data is not None:
            return float(self.data[self.index])
        else:
            return 0.0

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
        return self.indexFromValue(float(unicode(text)))

    def textFromValue(self, value):
        try:
            return str(float('%.4g' % self.data[value]))
        except:
            return ''

    def valueFromIndex(self, idx):
        if idx < 0:
            return self.data[0]
        elif idx > self.maximum():
            return self.data[-1]
        else:
            return self.data[idx]

    def indexFromValue(self, value):
        return (np.abs(self.data - value)).argmin()

    def minBoundaryValue(self, idx):
        if idx <= 0:
            return self.boundaries[0]
        elif idx >= len(self.data) - 1:
            return self.boundaries[-2]
        else:
            return self.boundaries[idx]

    def maxBoundaryValue(self, idx):
        if idx <= 0:
            return self.boundaries[1]
        elif idx >= len(self.data) - 1:
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
            if (value <= self.data[-1] + self.tolerance) and \
               (value - self.diff >= self.data[0] - self.tolerance):
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


class NXDoubleSpinBox(QtGui.QDoubleSpinBox):

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


class NXProjectionTab(QtGui.QWidget):

    def __init__(self, plotview=None):

        super(NXProjectionTab, self).__init__()

        hbox = QtGui.QHBoxLayout()
        widgets = []

        self.xbox = QtGui.QComboBox()
        self.xbox.currentIndexChanged.connect(self.set_xaxis)
        self.xbox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        widgets.append(QtGui.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = QtGui.QComboBox()
        self.ybox.currentIndexChanged.connect(self.set_yaxis)
        self.ybox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ylabel = QtGui.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)

        self.save_button = QtGui.QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_projection)
        widgets.append(self.save_button)

        self.plot_button = QtGui.QPushButton("Plot", self)
        self.plot_button.clicked.connect(self.plot_projection)
        widgets.append(self.plot_button)
        
        self.overplot_box = QtGui.QCheckBox("Over")
        self.overplot_box.setChecked(False)
        if 'Projection' not in plotviews:
            self.overplot_box.setVisible(False)
        widgets.append(self.overplot_box)

        self.panel_button = QtGui.QPushButton("Open Panel", self)
        self.panel_button.clicked.connect(self.open_panel)
        widgets.append(self.panel_button)

        hbox.addStretch()
        for w in widgets:
            hbox.addWidget(w)
            hbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        hbox.addStretch()
        
        self.setLayout(hbox)

        self.plotview = plotview

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
        keep_data(self.plotview.data.project(axes, limits))

    def plot_projection(self):
        if 'Projection' not in plotviews:
            self.overplot_box.setChecked(False)
        axes, limits = self.get_projection()
        projection = change_plotview("Projection")
        if len(axes) == 1 and self.overplot_box.isChecked():
            over = True
        else:
            over = False
        projection.plot(self.plotview.data.project(axes, limits), over=over)
        if len(axes) == 1:
            self.overplot_box.setVisible(True)
        else:
            self.overplot_box.setVisible(False)
            self.overplot_box.setChecked(False)
        self.plotview.make_active()
        plotviews[projection.label].raise_()
        from nexpy.gui.consoleapp import _mainwindow
        _mainwindow.panels.update()

    def open_panel(self):
        if not self.plotview.panel:
            self.plotview.panel = NXProjectionPanel(plotview=self.plotview)
            self.plotview.panel.update_limits()
        self.plotview.panel.window.setVisible(True)
        self.plotview.panel.window.tabs.setCurrentWidget(self.plotview.panel)
        self.plotview.panel.window.update()
        self.plotview.panel.window.raise_()


class NXProjectionPanels(QtGui.QDialog):

    def __init__(self, parent=None):
        super(NXProjectionPanels, self).__init__(parent)
        layout = QtGui.QVBoxLayout()
        self.tabs = QtGui.QTabWidget(self)
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        self.setWindowTitle('Projection Panel')
        self.tabs.currentChanged.connect(self.update)

    def __repr__(self):
        return 'NXProjectionPanels()'

    @property
    def panels(self):
        return [self.tabs.widget(idx) for idx in range(self.tabs.count())]

    def update(self):
        for panel in self.panels:
            panel.adjustSize()
            if 'Projection' in plotviews and plotviews['Projection'].ndim == 1:
                panel.overplot_box.setVisible(True)
            else:
                panel.overplot_box.setVisible(False)
        if self.tabs.count() == 0:
            self.setVisible(False)

    def closeEvent(self, event):
        self.close()
        event.accept()
        
    def close(self):
        for panel in self.panels:
            panel.close()
        self.setVisible(False)


class NXProjectionPanel(QtGui.QWidget):

    def __init__(self, plotview=None):

        self.plotview = plotview
        self.ndim = self.plotview.ndim

        from nexpy.gui.consoleapp import _mainwindow
        self.window = _mainwindow.panels

        QtGui.QWidget.__init__(self, parent=self.window.tabs)

        layout = QtGui.QVBoxLayout()

        axisbox = QtGui.QHBoxLayout()
        widgets = []

        self.xbox = QtGui.QComboBox()
        self.xbox.currentIndexChanged.connect(self.set_xaxis)
        self.xbox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        widgets.append(QtGui.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = QtGui.QComboBox()
        self.ybox.currentIndexChanged.connect(self.set_yaxis)
        self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.yaxis.name))
        self.ybox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ylabel = QtGui.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)

        self.set_axes()

        axisbox.addStretch()
        for w in widgets:
            axisbox.addWidget(w)
            axisbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        axisbox.addStretch()

        layout.addLayout(axisbox)

        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        headers = ['Axis', 'Minimum', 'Maximum', 'Lock']
        width = [50, 100, 100, 25]
        column = 0
        header_font = QtGui.QFont()
        header_font.setBold(True)
        for header in headers:
            label = QtGui.QLabel()
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
            self.lockbox[axis] = QtGui.QCheckBox()
            self.lockbox[axis].stateChanged.connect(self.set_lock)
            self.lockbox[axis].setChecked(False)
            grid.addWidget(QtGui.QLabel(self.plotview.axis[axis].name), row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)
            grid.addWidget(self.lockbox[axis], row, 3, 
                           alignment=QtCore.Qt.AlignHCenter)

        row += 1          
        self.save_button = QtGui.QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_projection)
        self.save_button.setDefault(False)
        self.save_button.setAutoDefault(False)
        grid.addWidget(self.save_button, row, 1)
        self.plot_button = QtGui.QPushButton("Plot", self)
        self.plot_button.clicked.connect(self.plot_projection)
        self.plot_button.setDefault(False)
        self.plot_button.setAutoDefault(False)
        grid.addWidget(self.plot_button, row, 2)
        self.overplot_box = QtGui.QCheckBox()
        self.overplot_box.setChecked(False)
        if 'Projection' not in plotviews:
            self.overplot_box.setVisible(False)
        grid.addWidget(self.overplot_box, row, 3, 
                       alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.mask_button = QtGui.QPushButton("Mask", self)
        self.mask_button.clicked.connect(self.mask_data)
        self.mask_button.setDefault(False)
        self.mask_button.setAutoDefault(False)
        grid.addWidget(self.mask_button, row, 1)
        self.unmask_button = QtGui.QPushButton("Unmask", self)
        self.unmask_button.clicked.connect(self.unmask_data)
        self.unmask_button.setDefault(False)
        self.unmask_button.setAutoDefault(False)
        grid.addWidget(self.unmask_button, row, 2)

        layout.addLayout(grid)

        button_layout = QtGui.QHBoxLayout()
        self.rectangle_button = QtGui.QPushButton("Hide Rectangle", self)
        self.rectangle_button.clicked.connect(self.show_rectangle)
        self.close_button = QtGui.QPushButton("Close Panel", self)
        self.close_button.clicked.connect(self.close)
        self.close_button.setDefault(False)
        self.close_button.setAutoDefault(False)
        button_layout.addStretch()
        button_layout.addWidget(self.rectangle_button)
        button_layout.addWidget(self.close_button)
        button_layout.addStretch()
        layout.addLayout(button_layout)
        layout.addStretch()
        
        self.setLayout(layout)
        self.window.tabs.insertTab(self.plotview.number-1, self, 
                                   self.plotview.label)
        self.window.tabs.adjustSize()
        self.window.tabs.setCurrentWidget(self)

        self.rectangle = None

        for axis in range(self.ndim):
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.axis[axis].centers
            self.minbox[axis].boundaries = self.maxbox[axis].boundaries = \
                boundaries(self.minbox[axis].data, 
                           self.minbox[axis].data.shape[0])
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.minbox[axis].diff = self.maxbox[axis].diff = None

        self.update_limits()

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
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                min_value = self.maxbox[axis].value() - self.maxbox[axis].diff
                self.minbox[axis].setValue(min_value)
            elif self.minbox[axis].value() > self.maxbox[axis].value():
                self.minbox[axis].setValue(self.maxbox[axis].value())
        self.draw_rectangle()

    def get_limits(self, axis=None):
        if axis:
            _min, _max = self.minbox[axis].index, self.maxbox[axis].index+1
            if _min < _max:
                return _min, _max
            else:
                return _max, _min
        else:
            _limits = [(self.minbox[axis].index, self.maxbox[axis].index)
                       for axis in range(self.ndim)]
            return [(_min, _max+1) if _min <= _max else (_max, _min+1)
                    for _min, _max in _limits]
    
    def update_limits(self):
        for axis in range(self.ndim):
            lo, hi = self.plotview.axis[axis].get_limits()
            self.minbox[axis].setValue(lo)
            self.maxbox[axis].setValue(hi)

    def set_lock(self):
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                lo, hi = self.minbox[axis].value(), self.maxbox[axis].value()
                self.minbox[axis].diff = self.maxbox[axis].diff = max(hi - lo, 0.0)
                self.minbox[axis].setDisabled(True)
            else:
                self.minbox[axis].diff = self.maxbox[axis].diff = None
                self.minbox[axis].setDisabled(False)

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
            keep_data(self.plotview.data.project(axes, limits))
        except NeXusError as error:
            report_error("Saving Projection", error)

    def plot_projection(self):
        try:
            if 'Projection' not in plotviews:
                self.overplot_box.setChecked(False)
            axes, limits = self.get_projection()
            projection = change_plotview("Projection")
            if len(axes) == 1 and self.overplot_box.isChecked():
                over = True
            else:
                over = False
            projection.plot(self.plotview.data.project(axes, limits),
                             over=over)
            if len(axes) == 1:
                self.overplot_box.setVisible(True)
            else:
                self.overplot_box.setVisible(False)
                self.overplot_box.setChecked(False)
            self.plotview.make_active()
            plotviews[projection.label].raise_()
            self.window.update()
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
        spinbox.valueChanged.connect(self.set_limits)
        return spinbox

    def block_signals(self, block=True):
        for axis in range(self.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)

    def show_rectangle(self):
        if self.rectangle is None:
            self.draw_rectangle()
            self.rectangle_button.setText("Hide Rectangle")
        else:
            self.rectangle.remove()
            self.rectangle = None
            self.rectangle_button.setText("Show Rectangle")
        self.plotview.canvas.draw()
        self.window.update()

    def draw_rectangle(self):
        ax = self.plotview.figure.axes[0]
        xp = self.plotview.xaxis.dim
        yp = self.plotview.yaxis.dim
        if self.minbox[xp].reversed:
            x0 = self.minbox[xp].maxBoundaryValue(self.minbox[xp].index)
            x1 = self.maxbox[xp].minBoundaryValue(self.maxbox[xp].index)
        else:
            x0 = self.minbox[xp].minBoundaryValue(self.minbox[xp].index)
            x1 = self.maxbox[xp].maxBoundaryValue(self.maxbox[xp].index)
        if self.minbox[yp].reversed:
            y0 = self.minbox[yp].maxBoundaryValue(self.minbox[yp].index)
            y1 = self.maxbox[yp].minBoundaryValue(self.maxbox[yp].index)
        else:
            y0 = self.minbox[yp].minBoundaryValue(self.minbox[yp].index)
            y1 = self.maxbox[yp].maxBoundaryValue(self.maxbox[yp].index)

        if self.rectangle:
            self.rectangle.set_bounds(x0, y0, x1-x0, y1-y0)
        else:      
            self.rectangle = ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0))
        self.rectangle.set_color('white')
        self.rectangle.set_facecolor('none')
        self.rectangle.set_linestyle('dashed')
        self.rectangle.set_linewidth(2)
        self.plotview.canvas.draw()
        self.rectangle_button.setText("Hide Rectangle")

    def closeEvent(self, event):
        self.close()
        event.accept()

    def close(self):
        try:
            self.rectangle.remove()
        except:
            pass
        self.plotview.canvas.draw()
        self.rectangle = None
        self.window.tabs.removeTab(self.window.tabs.indexOf(self))
        self.plotview.panel = None
        self.deleteLater()
        self.window.update()


class NXNavigationToolbar(NavigationToolbar):

    def __init__(self, canvas, parent):
        super(NXNavigationToolbar, self).__init__(canvas, parent)
        self.plotview = canvas.parent()
        self.zoom()

    def __repr__(self):
        return 'NXNavigationToolbar("%s")' % self.plotview.label

    def _init_toolbar(self):
        self.toolitems = (
            ('Home', 'Reset original view', 'home', 'home'),
            ('Back', 'Back to  previous view', 'back', 'back'),
            ('Forward', 'Forward to next view', 'forward', 'forward'),
            (None, None, None, None),
            ('Pan', 'Pan axes with left mouse, zoom with right', 'move', 'pan'),
            ('Zoom', 'Zoom to rectangle', 'zoom_to_rect', 'zoom'),
            (None, None, None, None),
            ('Aspect', 'Set aspect ratio to equal', 'hand', 'set_aspect'),
            (None, None, None, None),
            ('Subplots', 'Configure subplots', 'subplots', 'configure_subplots'),
            ('Save', 'Save the figure', 'filesave', 'save_figure'),
            ('Add', 'Add plot data to tree', 'hand', 'add_data')
                )
        super(NXNavigationToolbar, self)._init_toolbar()
        self._actions['set_aspect'].setIcon(QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/equal.png')))
        self._actions['set_aspect'].setCheckable(True)

    def home(self, *args):
        super(NXNavigationToolbar, self).home()        
        self.plotview.reset_plot_limits()

    def add_data(self):
        keep_data(self.plotview.plotdata)

    def release_zoom(self, event):
        'the release mouse button callback in zoom to rect mode'
        for zoom_id in self._ids_zoom:
            self.canvas.mpl_disconnect(zoom_id)
        self._ids_zoom = []

        if not self._xypress: return

        last_a = []

        for cur_xypress in self._xypress:
            x, y = event.x, event.y
            lastx, lasty, a, ind, lim, trans = cur_xypress      # TODO: ind & trans are unused
            # ignore singular clicks - 5 pixels is a threshold
            if abs(x-lastx)<5 or abs(y-lasty)<5:
                self._xypress = None
                self.release(event)
                self.draw()
                return

            x0, y0, x1, y1 = lim.extents

            # zoom to rect
            inverse = a.transData.inverted()
            lastx, lasty = inverse.transform_point((lastx, lasty))
            x, y = inverse.transform_point((x, y))
            Xmin, Xmax = a.get_xlim()
            Ymin, Ymax = a.get_ylim()

            # detect twinx,y axes and avoid double zooming
            twinx, twiny = False, False
            if last_a:
                for la in last_a:
                    if a.get_shared_x_axes().joined(a,la): twinx=True
                    if a.get_shared_y_axes().joined(a,la): twiny=True
            last_a.append(a)

            if twinx:
                x0, x1 = Xmin, Xmax
            else:
                if Xmin < Xmax:
                    if x<lastx:  x0, x1 = x, lastx
                    else: x0, x1 = lastx, x
                    if x0 < Xmin: x0=Xmin
                    if x1 > Xmax: x1=Xmax
                else:
                    if x>lastx:  x0, x1 = x, lastx
                    else: x0, x1 = lastx, x
                    if x0 > Xmin: x0=Xmin
                    if x1 < Xmax: x1=Xmax

            if twiny:
                y0, y1 = Ymin, Ymax
            else:
                if Ymin < Ymax:
                    if y<lasty:  y0, y1 = y, lasty
                    else: y0, y1 = lasty, y
                    if y0 < Ymin: y0=Ymin
                    if y1 > Ymax: y1=Ymax
                else:
                    if y>lasty:  y0, y1 = y, lasty
                    else: y0, y1 = lasty, y
                    if y0 > Ymin: y0=Ymin
                    if y1 < Ymax: y1=Ymax

            if self._button_pressed == 1:
                if self._zoom_mode == "x":
                    a.set_xlim((x0, x1))
                    self.plotview.xtab.set_limits(x0, x1)
                elif self._zoom_mode == "y":
                    a.set_ylim((y0, y1))
                    self.plotview.ytab.set_limits(y0, y1)
                else:
                    a.set_xlim((x0, x1))
                    a.set_ylim((y0, y1))
                    self.plotview.xtab.set_limits(x0, x1)
                    self.plotview.ytab.set_limits(y0, y1)
                    xdim = self.plotview.xtab.axis.dim
                    ydim = self.plotview.ytab.axis.dim
                    self.plotview.zoom = {'x': (xdim, x0, x1), 
                                          'y': (ydim, y0, y1)}
                if self.plotview.label != "Projection":
                    self.plotview.tab_widget.setCurrentWidget(self.plotview.ptab)
            elif self._button_pressed == 3:
                if self._zoom_mode == "x":
                    self.plotview.xtab.set_limits(x0, x1)
                elif self._zoom_mode == "y":
                    self.plotview.ytab.set_limits(y0, y1)
                else:
                    xdim = self.plotview.xaxis.dim
                    ydim = self.plotview.yaxis.dim
                    self.plotview.zoom = {'x': (xdim, x0, x1), 
                                          'y': (ydim, y0, y1)}
                if self.plotview.label != "Projection":
                    self.plotview.tab_widget.setCurrentWidget(self.plotview.ptab)
            if self.plotview.panel:
                self.plotview.panel.update_limits()

        self.draw()
        self._xypress = None
        self._button_pressed = None

        self._zoom_mode = None

        self.release(event)

    def release_pan(self, event):
        super(NXNavigationToolbar, self).release_pan(event)
        xmin, xmax = self.plotview.ax.get_xlim()
        ymin, ymax = self.plotview.ax.get_ylim()
        self.plotview.xtab.set_limits(xmin, xmax)
        self.plotview.ytab.set_limits(ymin, ymax)
        if self.plotview.panel:
            self.plotview.panel.update_limits()            

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


def keep_data(data):
    from nexpy.gui.consoleapp import _tree
    if 'w0' not in _tree.keys():
        _tree.add(NXroot(name='w0'))
    ind = []
    for key in _tree['w0'].keys():
        try:
            if key.startswith('s'): 
                ind.append(int(key[1:]))
        except ValueError:
            pass
    if ind == []: ind = [0]
    data.nxname = 's'+str(sorted(ind)[-1]+1)
    _tree['w0'][data.nxname] = data

def centers(axis, dimlen):
    """
    Return the centers of the axis bins.

    This works regardless if the axis contains bin boundaries or centers.
    """
    ax = axis.astype(np.float32)
    if ax.shape[0] == dimlen+1:
        return (ax[:-1] + ax[1:])/2
    else:
        assert ax.shape[0] == dimlen
        return ax

def boundaries(axis, dimlen):
    """
    Return the boundaries of the axis bins.

    This works regardless if the axis contains bin boundaries or centers.
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

