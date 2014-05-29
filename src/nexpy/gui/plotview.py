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
from PySide import QtCore, QtGui
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib._pylab_helpers import Gcf
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_qt4 import FigureManagerQT as FigureManager
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.image import NonUniformImage
from matplotlib.colors import LogNorm, Normalize
from matplotlib.patches import Rectangle

from nexpy.api.nexus import NXfield, NXdata, NXroot, NeXusError

plotview = None
plotviews = {}
cmaps = ['autumn', 'bone', 'cool', 'copper', 'flag', 'gray', 'hot', 
         'hsv', 'jet', 'pink', 'prism', 'spring', 'summer', 'winter', 
         'spectral', 'rainbow']
colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']

def new_figure_manager(label=None, *args, **kwargs):
    """
    Create a new figure manager instance
    
    Figure numbers > 100 are preserved for the Projection and Fit windows.
    """
    if label is None:
        label = ''
    if 'Projection' in label or 'Fit' in label:
        nums = [num for num in plt.get_fignums() if num > 100]
        if nums:
            num = max(nums) + 1
        else:
            num = 101
    else:    
        nums = [num for num in plt.get_fignums() if num < 100]
        if nums:
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

        self.window = QtGui.QWidget()
        self.window.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        QtCore.QObject.connect(self.window, QtCore.SIGNAL('destroyed()'),
                               self._widgetclosed)
        self.window._destroying = False

#        self.toolbar = NXNavigationToolbar(self.canvas, self.window)
#        tbs_height = self.toolbar.sizeHint().height()

        # resize the main window so it will display the canvas with the
        # requested size:
        cs = canvas.sizeHint()
        self.window.resize(cs.width(), cs.height())
        self.window.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, 
                                  QtGui.QSizePolicy.MinimumExpanding)

#        self.window.show()

        # attach a show method to the figure for pylab ease of use
        self.canvas.figure.show = lambda *args: self.window.show()

        def notify_axes_change(fig):
            # This will be called whenever the current axes is changed
            if self.canvas.toolbar is not None:
                self.canvas.toolbar.update()
        self.canvas.figure.add_axobserver(notify_axes_change)

class NXPlotView(QtGui.QWidget):
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
        
        super(NXPlotView, self).__init__(parent)

        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                           QtGui.QSizePolicy.MinimumExpanding)

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
            if 'Projection' not in self.label and 'Fit' not in self.label:
                self.make_active()
            if event.button == 3:
                hasattr(self, 'otab')
                self.otab.home()
        cid = self.canvas.mpl_connect('button_press_event', make_active)
        self.figuremanager._cidgcf = cid
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

        self.vtab = NXPlotTab('v', axis=False, cmap=True, plotview=self)
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

        self.plot = NXPlot(self)
        
        self.window().setWindowTitle(self.label)
 
        global plotview, plotviews
        plotview = self
        plotviews[self.label] = plotview
        self.plotviews = plotviews

        if self.label not in ['Main', 'Fit'] and 'Projection' not in self.label:
            self.add_menu_action()

        self.show()

        #Initialize the plotting window with a token plot
        self.plot.plot(NXdata(signal=NXfield([0,1], name='y'), 
                       axes=NXfield([0,1], name='x')), fmt='wo', mec='w')
        
#        self.grid_cb = QtGui.QCheckBox("Show &Grid")
#        self.grid_cb.setChecked(False)
#        self.grid_cb.stateChanged.connect(self.on_draw)

    def make_active(self):
        global plotview
        plotview = self
        Gcf.set_active(self.figuremanager)
        self.show()
        if self.label == 'Main':
            self.parent().parent().parent().raise_()
        else:
            self.raise_()
        self.update_active()

    def update_active(self):
        if 'Projection' not in self.label and 'Fit' not in self.label:
            from nexpy.gui.consoleapp import _mainwindow
            _mainwindow.update_active(self.label)
    
    def add_menu_action(self):
        from nexpy.gui.consoleapp import _mainwindow
        if self.label not in _mainwindow.active_action:
            _mainwindow.make_active_action(self.label, self.number)
        _mainwindow.update_active(self.label)

    def remove_menu_action(self):
        from nexpy.gui.consoleapp import _mainwindow
        if self.label in _mainwindow.active_action:
            _mainwindow.window_menu.removeAction(_mainwindow.active_action[self.label])
            del _mainwindow.active_action[self.label]
        if self.label == _mainwindow.previous_active:
            _mainwindow.previous_active = 'Main'
        _mainwindow.make_active(_mainwindow.previous_active)

    def save_plot(self):
        """
        Opens a dialog box for saving a plot as a PNG file
        """
        file_choices = "PNG (*.png)|*.png"
        
        path = unicode(QtGui.QFileDialog.getSaveFileName(self, 
                        'Save file', '', 
                        file_choices))
        if path:
            self.canvas.print_figure(path, dpi=self.dpi)
            self.statusBar().showMessage('Saved to %s' % path, 2000)

    def close_view(self):
        self.remove_menu_action()
        Gcf.destroy(self.number)
        del plotviews[self.label]

    def closeEvent(self, event):
        self.close_view()
        self.deleteLater()
        event.accept()
                                    

class NXPlot(object):
    """
    A NeXpy plotting pane with associated axis and option tabs.
    
    The plot is created using matplotlib and may be contained within the main NeXpy
    plotting pane or in a separate window, depending on the current matplotlib figure.
    """

    def __init__(self, parent):

        self.plotview = parent
            
        self.canvas = self.plotview.canvas
        self.figure = self.canvas.figure
        self.num = 0
        self.axis = {}
        self.xaxis = self.yaxis = self.zaxis = None
        self.xmin = self.xmax = self.ymin = self.ymax = self.vmin = self.vmax = None
        self.tab_widget = self.plotview.tab_widget
        self.xtab = self.plotview.xtab
        self.ytab = self.plotview.ytab
        self.ztab = self.plotview.ztab
        self.vtab = self.plotview.vtab
        self.otab = self.plotview.otab
        self.ptab = self.plotview.ptab

        self.set_cmap = self.vtab.set_cmap
        self.get_cmap = self.vtab.get_cmap

        self.colorbar = None
        self.autoscale = False   
        self.zoom = None
    
    def plot(self, data, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             vmin=None, vmax=None, **opts):
        """
        This is the function invoked by the NXPlotView plot method to plot an NXdata
        group with optional limits and matplotlib options
        
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

        over = opts.pop("over",False)
        log = opts.pop("log",False)
        logx = opts.pop("logx",False)
        logy = opts.pop("logy",False)
        cmap = opts.pop("cmap",None)

        if cmap in cmaps: 
            self.set_cmap(cmap)

        self.data = data
        self.title = data.nxtitle

        self.plotdata = self.get_plotdata()

        #One-dimensional Plot
        if self.ndim == 1:
            if over:
                self.num = self.num + 1
            else:
                self.num = 0
                self.xaxis = self.axis[self.axes[0].nxname]
                if xmin: self.xaxis.lo = xmin
                if xmax: self.xaxis.hi = xmax

                self.yaxis = self.axis[data.nxsignal.nxname] = NXPlotAxis(data.nxsignal)
                if ymin: self.yaxis.lo = ymin
                if ymax: self.yaxis.hi = ymax

                if logx: 
                    self.xtab.logbox.setChecked(True)
                else:
                    self.xtab.logbox.setChecked(False)
                if log or logy: 
                    self.ytab.logbox.setChecked(True)
                else:
                    self.ytab.logbox.setChecked(False)

            if fmt == '': fmt = colors[self.num%len(colors)]+'o'
                
            self.plot1D(fmt, over, **opts)

        #Higher-dimensional plot
        else:
           
            self.xaxis = self.axis[self.axes[-1].nxname]
            if xmin: self.xaxis.lo = xmin
            if xmax: self.xaxis.hi = xmax

            self.yaxis = self.axis[self.axes[-2].nxname]
            if ymin: self.yaxis.lo = ymin
            if ymax: self.yaxis.hi = ymax

            self.vaxis = NXPlotAxis(self.plotdata.nxsignal)
            if vmin: self.vaxis.lo = vmin
            if vmax: self.vaxis.hi = vmax

            if log:
                self.vtab.logbox.setChecked(True)
            else:
                self.vtab.logbox.setChecked(False)
 
            if self.ndim > 2:
                self.zaxis = self.axis[self.axes[-3].nxname]
                self.zaxis.lo = self.zaxis.hi = self.zaxis.min
                for axis in self.axes[:-3]:
                    self.axis[axis.nxname].lo = self.axis[axis.nxname].hi \
                        = axis.nxdata[0]
            else:
                self.zaxis = None

            self.plot2D(over, **opts)

        self.canvas.draw_idle()
        if over:
            self.update_tabs()
        else:
            self.init_tabs()

    def plot1D(self, fmt, over=False, **opts):

        mpl.interactive(False)
        
        if not over: 
            self.figure.clf()
        ax = self.figure.gca()
        
        self.x = self.plotdata.nxaxes[0].nxdata
        self.y = self.plotdata.nxsignal.nxdata
        if self.plotdata.nxerrors:
            self.e = self.plotdata.nxerrors.nxdata
        else:
            self.e = None

        if self.x[0] > self.x[-1]:
            self.x = self.x[::-1]
            self.y = self.y[::-1]
            if self.e is not None:
                self.e = self.e[::-1]

        if self.plotdata.nxerrors:
            ax.errorbar(self.x, self.y, self.e, fmt=fmt, **opts)
        else:
            ax.plot(self.x, self.y, fmt,  **opts)

        path = self.data.nxsignal.nxpath
        if self.data.nxroot.nxclass == "NXroot":
            path = self.data.nxroot.nxname+path
        ax.lines[-1].set_label(path)

        if over:
            self.xaxis.min = min(self.xaxis.lo, self.x.min())
            self.xaxis.max = max(self.xaxis.hi, self.x.max())
            _range = self.xaxis.max - self.xaxis.min
            if self.xaxis.min < self.xaxis.lo:
                self.xaxis.min = self.xaxis.min - 0.05*_range
            if self.xaxis.max > self.xaxis.hi:
                self.xaxis.max = self.xaxis.max + 0.05*_range

            self.yaxis.min = min(self.yaxis.lo, self.y.min())
            self.yaxis.max = max(self.yaxis.hi, self.y.max())
            _range = self.yaxis.max - self.yaxis.min
#            if self.yaxis.min < self.yaxis.lo:
#                self.yaxis.min = self.yaxis.min - 0.05*_range
#            if self.yaxis.max > self.yaxis.hi:
#                self.yaxis.max = self.yaxis.max + 0.05*_range
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
                ax.set_xscale('symlog')
            if self.ytab.logbox.isChecked():
                ax.set_yscale('symlog')
            ax.set_xlabel(self.xaxis.label)
            ax.set_ylabel(self.yaxis.label)
            ax.set_title(self.title)

            self.xaxis.min, self.xaxis.max = ax.get_xlim()
            self.yaxis.min, self.yaxis.max = ax.get_ylim()
            self.xaxis.lo, self.xaxis.hi = self.xaxis.min, self.xaxis.max
            self.yaxis.lo, self.yaxis.hi = self.yaxis.min, self.yaxis.max

        self.canvas.draw_idle()
        self.otab.push_current()
        mpl.interactive(True)

    def plot2D(self, over=False, **opts):

        mpl.interactive(False)
        if not over: 
            self.figure.clf()

        self.v = self.plotdata.nxsignal.nxdata
        self.x = self.plotdata.nxaxes[1].nxdata
        self.y = self.plotdata.nxaxes[0].nxdata
        
        if self.x[0] > self.x[-1] and self.y[0] > self.y[-1]:
            self.x = self.x[::-1]
            self.y = self.y[::-1]
            self.v = self.v[::-1,::-1]
        elif self.x[0] > self.x[-1]:
            self.x = self.x[::-1]
            self.v = self.v[:,::-1]
        elif self.y[0] > self.y[-1]:
            self.y = self.y[::-1]
            self.v = self.v[::-1,:]

        if self.vaxis.lo is None or self.autoscale: 
            self.vaxis.lo = np.nanmin(self.v)
        if self.vaxis.hi is None or self.autoscale: 
            self.vaxis.hi = np.nanmax(self.v)
        
        if self.vaxis.lo == self.vaxis.hi:
            self.vaxis.hi = self.vaxis.lo + 1

        if self.vtab.logbox.isChecked():
            if self.vaxis.lo <= 0:
                if np.issubdtype(self.v[0,0],int):
                    vmin = 0.1
                else:
                    vmin = np.nanmax(self.v)*1e-6
                self.v = self.v.clip(vmin)
            else:
                vmin = self.vaxis.lo
            opts["norm"] = LogNorm(vmin, self.vaxis.hi)
        else:
            opts["norm"] = Normalize(self.vaxis.lo, self.vaxis.hi)

        ax = self.figure.gca()
        ax.autoscale(enable=True)
        ax.format_coord = self.format_coord
        cmap = self.get_cmap()
        extent = (self.xaxis.min,self.xaxis.max,self.yaxis.min,self.yaxis.max)

        self.image = NonUniformImage(ax, extent=extent, cmap=cmap, **opts)
        self.image.get_cmap().set_bad('k', 1.0)
        self.image.set_data(self.x, self.y, self.v)
        
        ax.images.append(self.image)

        xlo, xhi = ax.set_xlim(self.xaxis.min,self.xaxis.max)
        ylo, yhi = ax.set_ylim(self.yaxis.min,self.yaxis.max)
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
      
        if self.colorbar:
            try:
                self.colorbar.update_normal(self.image)
            except Exception:
                self.colorbar = self.figure.colorbar(self.image, ax=ax)
        else:
            self.colorbar = self.figure.colorbar(self.image, ax=ax)

        ax.set_xlabel(self.xaxis.label)
        ax.set_ylabel(self.yaxis.label)
        ax.set_title(self.title)

        self.xaxis.min, self.xaxis.max = self.x.min(), self.x.max()
        self.yaxis.min, self.yaxis.max = self.y.min(), self.y.max()
        self.vaxis.min, self.vaxis.max = np.nanmin(self.v), np.nanmax(self.v)
        
        if self.autoscale:
            self.vtab.set_axis(self.vaxis)
        
        self.canvas.draw_idle()
        self.otab.push_current()
        mpl.interactive(True)

    def data2D(self):
        axes = [self.yaxis.dim,self.xaxis.dim]
        limits = []
        for axis in self.axes:
            if self.axis[axis.nxname].dim in axes: 
                limits.append((None,None))
            else:
                limits.append((self.axis[axis.nxname].lo,
                               self.axis[axis.nxname].hi))
        plotdata = self.data.project(axes, limits)
        for axis in plotdata.nxaxes:
            plotdata[axis.nxname] = self.plotdata[axis.nxname]
        return plotdata

    def get_plotdata(self):
        self.shape, self.axes = self._fixaxes(self.data.nxsignal, 
                                              self.data.nxaxes)
        self.ndim = len(self.shape)
        self.axis_data = centers(self.shape, self.axes)
        i = 0
        self.axis = {}
        for axis in self.axes:
            self.axis[axis.nxname] = NXPlotAxis(axis)
            self.axis[axis.nxname].centers = self.axis_data[i]
            self.axis[axis.nxname].dim = i
            i = i + 1

        if self.ndim > 2:
            idx=[np.s_[0] for i in self.data.nxsignal.shape[:-2]]
            idx.extend([np.s_[:],np.s_[:]])
            plotdata = NXdata(self.data.nxsignal[tuple(idx)][()],
                              [NXfield(self.axis_data[i], 
                                       name=self.axes[i].nxname,
                                       attrs=self.axes[i].attrs)
                               for i in [-2,-1]])
            self.shape = self.shape[-2:]
        else:
            plotdata = NXdata(self.data.nxsignal[()],
                              [NXfield(self.axis_data[i], 
                                       name=self.axes[i].nxname,
                                       attrs=self.axes[i].attrs)
                               for i in range(self.ndim)])
            plotdata.nxsignal.shape = self.shape

        if self.ndim == 1:
            if self.data.nxerrors and self.data.nxerrors != self.data.nxsignal:
                plotdata.errors = NXfield(self.data.errors)
                plotdata.errors.shape = self.shape

        plotdata['title'] = self.title
        
        return plotdata

    def replot_axes(self):
        ax = self.figure.gca()
        ax.set_xlim(self.xaxis.get_limits())
        ax.set_ylim(self.yaxis.get_limits())
        self.canvas.draw_idle()
        self.otab.push_current()

    def replot_logs(self):
        ax = self.figure.gca()
        if self.xtab.logbox.isChecked():
            ax.set_xscale('symlog')
        else:
            ax.set_xscale('linear')
        if self.ytab.logbox.isChecked():
            ax.set_yscale('symlog')
        else:
            ax.set_yscale('linear')
        self.canvas.draw_idle()
        
    def show(self):
        self.figure.show()   

    def _fixaxes(self, data, axes):
        """
        Remove length-one dimensions from plottable data
        """
        shape = list(data.shape)
        while 1 in shape: shape.remove(1)
        newaxes = []
        for axis in axes:
            if axis.size > 1: newaxes.append(axis)
        return shape, newaxes

    def init_tabs(self):
        self.xtab.set_axis(self.xaxis)
        self.ytab.set_axis(self.yaxis)
        if self.ndim == 1:
            self.xtab.logbox.setVisible(True)
            self.xtab.axiscombo.setVisible(False)
            self.ytab.logbox.setVisible(True)
            self.ytab.axiscombo.setVisible(False)
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.vtab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ptab))
        elif self.ndim >= 2:
            self.vtab.set_axis(self.vaxis)
            self.vtab.logbox.setChecked(False)
            if self.tab_widget.indexOf(self.vtab) == -1:
                self.tab_widget.insertTab(0,self.vtab,'signal')
            if not self.plotview.label.startswith("Projection"):
                if self.tab_widget.indexOf(self.ptab) == -1:
                    self.tab_widget.insertTab(self.tab_widget.indexOf(self.otab),
                                              self.ptab,'projections')
                self.ptab.set_axes()
                self.zoom = None
            if self.ndim > 2:
                self.ztab.set_axis(self.zaxis)
                self.ztab.lockbox.setChecked(False)
                self.ztab.scalebox.setChecked(False)
                if self.tab_widget.indexOf(self.ztab) == -1:
                    self.tab_widget.insertTab(self.tab_widget.indexOf(self.ptab),
                                              self.ztab,'z')
            else:
                self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.xtab.logbox.setChecked(False)
            self.xtab.logbox.setVisible(False)
            self.xtab.axiscombo.setVisible(True)
            self.ytab.logbox.setChecked(False)
            self.ytab.logbox.setVisible(False)
            self.ytab.axiscombo.setVisible(True)
        if self.ptab.panel:
            self.ptab.panel.close()

    def update_tabs(self):
        self.xtab.minbox.setMinimum(self.xtab.axis.min)
        self.xtab.maxbox.setMaximum(self.xtab.axis.max)
        self.xtab.read_minslider()
        self.xtab.read_maxslider()
        self.xtab.minbox.setValue(self.xtab.axis.lo)
        self.xtab.maxbox.setValue(self.xtab.axis.hi)
        self.ytab.minbox.setMinimum(self.ytab.axis.min)
        self.ytab.maxbox.setMaximum(self.ytab.axis.max)
        self.ytab.read_minslider()
        self.ytab.read_maxslider()
        self.ytab.minbox.setValue(self.ytab.axis.lo)
        self.ytab.maxbox.setValue(self.ytab.axis.hi)

    def change_axis(self, tab, axis):
        if tab == self.xtab and axis == self.yaxis:
            self.yaxis = self.ytab.axis = self.xtab.axis
            self.xaxis = self.xtab.axis = axis
            self.plotdata = NXdata(self.plotdata.nxsignal.T, 
                                   self.plotdata.nxaxes[::-1],
                                   title = self.title)
            self.plot2D()
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
        elif tab == self.ytab and axis == self.xaxis:
            self.xaxis = self.xtab.axis = self.ytab.axis
            self.yaxis = self.ytab.axis = axis
            self.plotdata = NXdata(self.plotdata.nxsignal.T, 
                                   self.plotdata.nxaxes[::-1],
                                   title = self.title)
            self.plot2D()
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
        elif tab == self.ztab:
            self.zaxis = self.ztab.axis = axis
            self.ztab.set_axis(self.zaxis)  
        else:
            if tab == self.xtab:
                self.zaxis = self.ztab.axis = self.xaxis
                self.xaxis = self.xtab.axis = axis
                self.xaxis.locked = False
            elif tab == self.ytab:
                self.zaxis = self.ztab.axis = self.yaxis
                self.yaxis = self.ytab.axis = axis
                self.yaxis.locked = False
            self.xaxis.set_limits(self.xaxis.min, self.xaxis.max)
            self.yaxis.set_limits(self.yaxis.min, self.yaxis.max)
            self.zaxis.set_limits(self.zaxis.min, self.zaxis.min)
            axes = [self.yaxis.dim, self.xaxis.dim]
            limits = []
            for axis in self.axes:
                if self.axis[axis.nxname].dim in axes: 
                    limits.append((None,None))
                else:
                    limits.append((self.axis[axis.nxname].lo,
                                   self.axis[axis.nxname].hi))
            self.plotdata = self.data.project(axes, limits)
            self.plot2D()
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.ztab.set_axis(self.zaxis)
            self.vtab.set_axis(self.vaxis)
            if self.ptab.panel:
                self.ptab.panel.update_limits()

    def format_coord(self, x, y):
        if x >= self.x[0] and x <= self.x[-1] and \
           y >= self.y[0] and y <= self.y[-1]:
            col = (np.abs(self.x-x)).argmin()
            row = (np.abs(self.y-y)).argmin()
            z = self.v[row,col]
            return 'x=%1.4f y=%1.4f\nv=%1.4f'%(x, y, z)
        else:
            return ''


class NXPlotAxis(object):

    def __init__(self, axis):
        self.name = axis.nxname
        self.data = axis.nxdata
        self.ndim = len(axis.nxdata.shape)
        self.dim = None
        if 'signal' in axis.attrs:
            self.signal = True
        else:
            self.signal = False
        if self.data is not None:
            self.min = np.nanmin(self.data)
            self.max = np.nanmax(self.data)
        else:
            self.min = None
            self.max = None
        self.centers = self.data
        self.lo = None
        self.hi = None
        self.diff = None
        self.locked = False
        if hasattr(axis, 'long_name'):
            self.label = axis.long_name
        elif hasattr(axis, 'units'):
            self.label = "%s (%s)" % (axis.nxname, axis.units)
        else:
            self.label = axis.nxname

    def set_limits(self, lo, hi):
        self.lo, self.hi = lo, hi

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

    def __init__(self, name=None, axis=True, log=True, zaxis=False, cmap=False,
                 plotview=None):

        super(NXPlotTab, self).__init__()

        self.name = name

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
            widgets.append(self.minbox)
            widgets.append(self.maxbox)
            self.minslider = self.maxslider = None
        else:
            self.zaxis = False
            self.minbox = self.doublespinbox(self.read_minbox)
            self.minslider = self.slider(self.read_minslider)
            self.maxslider = self.slider(self.read_maxslider)
            self.maxbox = self.doublespinbox(self.read_maxbox)
            widgets.append(self.minbox)
            widgets.extend([self.minslider, self.maxslider])
            widgets.append(self.maxbox)
        if zaxis:
            self.lockbox = self.checkbox("Lock", self.set_lock)
            self.lockbox.setChecked(False)
            self.scalebox = self.checkbox("Autoscale", self.set_autoscale)
            self.scalebox.setChecked(False)
            widgets.append(self.lockbox)
            widgets.append(self.scalebox)
            self.init_toolbar()
            widgets.append(self.toolbar)

        else:
            self.lockbox = None
            self.scalebox = None
        if log: 
            self.logbox = self.checkbox("Log", self.set_log)
            self.logbox.setChecked(False)
            widgets.append(self.logbox)
        else:
            self.logbox = None
        
        if cmap: 
            self.cmapcombo = self.combobox(self.change_cmap)
            widgets.append(self.cmapcombo)
            self.cmapcombo.addItems(cmaps)
            self.cmapcombo.setCurrentIndex(self.cmapcombo.findText('jet')) 
        else:
            self.cmapcombo = None

        if zaxis: hbox.addStretch()
        for w in widgets:
            hbox.addWidget(w)
            hbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        if zaxis: hbox.addStretch()

        self.setLayout(hbox)

        self.replotSignal = NXReplotSignal()
        self.replotSignal.replot.connect(self.replot)       

        self.plotview = plotview

    def set_axis(self, axis):
        self.plot = self.plotview.plot
        self.axis = axis
        if self.zaxis:
            self.minbox.data = self.maxbox.data = self.axis.data  
            self.minbox.setRange(0, len(self.axis.data)-1)
            self.maxbox.setRange(0, len(self.axis.data)-1)
            self.minbox.setValue(axis.lo)
            self.maxbox.setValue(axis.hi)
            self.timer.stop()
            self.playsteps = 0
        else:
            if (axis.max-axis.min) < 1e-8:
                axis.max = axis.min + 1
            self.minbox.setRange(axis.min, axis.max)
            self.maxbox.setRange(axis.min, axis.max)
            self.minbox.setValue(self.minbox.minimum())
            self.maxbox.setValue(self.maxbox.maximum())
            self.minbox.setSingleStep((axis.max-axis.min)/200)
            self.maxbox.setSingleStep((axis.max-axis.min)/200)
        self.minbox.old_value = self.minbox.value()
        self.maxbox.old_value = self.maxbox.value()
        self.minbox.block_replot = self.maxbox.block_replot = False
        if not self.zaxis:
            self.block_signals(True)
            self.set_sliders(self.minbox.minimum(), self.maxbox.maximum())
            self.block_signals(False)
        if self.axiscombo:
            self.axiscombo.clear()
            self.axiscombo.addItems(self.get_axes())
            self.axiscombo.setCurrentIndex(self.axiscombo.findText(axis.name))

    def combobox(self, slot):
        combobox = QtGui.QComboBox()
        combobox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        combobox.setMinimumWidth(100)
        combobox.activated.connect(slot)
        return combobox

    def textbox(self, slot):
        textbox = NXTextBox()
        textbox.setAlignment(QtCore.Qt.AlignRight)
        textbox.setFixedWidth(75)
        textbox.editingFinished.connect(slot)
        return textbox

    def spinbox(self, slot):
        spinbox = NXSpinBox()
        spinbox.setAlignment(QtCore.Qt.AlignRight)
        spinbox.setFixedWidth(100)
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(False)
        spinbox.editingFinished.connect(slot)
        spinbox.valueChanged[unicode].connect(slot)
        return spinbox

    def doublespinbox(self, slot):
        doublespinbox = NXDoubleSpinBox()
        doublespinbox.setAlignment(QtCore.Qt.AlignRight)
        doublespinbox.setFixedWidth(100)
        doublespinbox.setKeyboardTracking(False)
        doublespinbox.editingFinished.connect(slot)
        doublespinbox.valueChanged[unicode].connect(slot)
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
        checkbox.stateChanged.connect(slot)
        return checkbox

    def pushbutton(self, label, slot):
        button = QtGui.QPushButton(label)
        button.clicked.connect(slot)
        return button

    def read_minbox(self):
        if not self.minbox.isEnabled():
            return
        lo, hi = self.minbox.value(), self.maxbox.value()
        if lo == self.minbox.old_value or self.axis.locked:
            return
        if lo is not None and (lo <= hi or self.axis.locked): 
            self.axis.lo = lo
        else:
            self.minbox.setValue(self.axis.lo)
        if self.name == 'x' or self.name == 'y':
            self.set_sliders(self.axis.lo, hi)
            self.plot.replot_axes()
        elif self.name == 'v':
            self.set_sliders(self.axis.lo, hi)
            self.plot.plot2D()
        self.minbox.old_value = self.minbox.value()
        self.maxbox.old_value = self.maxbox.value()

    def read_maxbox(self):
        lo, hi = self.minbox.value(), self.maxbox.value()
        if hi == self.maxbox.old_value:
            return
        replot = False          # TODO: unused variable
        if hi is not None and (hi >= lo or self.axis.locked): 
            self.axis.hi = hi
        else:
            self.maxbox.setValue(self.axis.hi)
        if self.name == 'x' or self.name == 'y':
            self.set_sliders(lo, self.axis.hi)
            self.plot.replot_axes()
        if self.name == 'z' and self.axis.locked:
            self.axis.lo = self.axis.hi - self.axis.diff
            if self.axis.lo <> self.minbox.old_value:
                self.minbox.setValue(self.axis.lo)
                self.replotSignal.replot.emit()
        elif self.name == 'v':
            self.set_sliders(lo, self.axis.hi)
            self.plot.plot2D()
        self.minbox.old_value = self.minbox.value()
        self.maxbox.old_value = self.maxbox.value()
    
    def read_minslider(self):
        self.block_signals(True)
        self.axis.hi = self.maxbox.value()
        _range = max(self.axis.hi-self.minbox.minimum(), self.axis.min_range)
        self.axis.lo = self.minbox.minimum() + (self.minslider.value() * _range / 1000)
        self.minbox.setValue(self.axis.lo)
        _range = max(self.maxbox.maximum()-self.axis.lo, self.axis.min_range)
        try:
            self.maxslider.setValue(1000*(self.axis.hi-self.axis.lo)/_range)
        except (ZeroDivisionError, OverflowError):
            self.maxslider.setValue(0)
        if self.name == 'x' or self.name == 'y':
            self.plot.replot_axes()
        else:
            self.plot.plot2D()
        self.block_signals(False)

    def read_maxslider(self):
        self.block_signals(True)
        self.axis.lo = self.minbox.value()
        _range = max(self.maxbox.maximum()-self.axis.lo, self.axis.min_range)
        self.axis.hi = self.axis.lo + (self.maxslider.value() * _range / 1000)
        self.maxbox.setValue(self.axis.hi)
        _range = max(self.axis.hi - self.minbox.minimum(), self.axis.min_range)
        try:
            self.minslider.setValue(1000*(self.axis.lo-self.minbox.minimum())/_range)
        except (ZeroDivisionError, OverflowError):
            self.minslider.setValue(1000)
        if self.name == 'x' or self.name == 'y':
            self.plot.replot_axes()
        else:
            self.plot.plot2D()
        self.block_signals(False)

    def set_sliders(self, lo, hi):
        self.block_signals(True)
        _range = max(hi-self.minbox.minimum(), self.axis.min_range)
        try:
            self.minslider.setValue(1000*(lo-self.minbox.minimum())/_range)
        except (ZeroDivisionError, OverflowError):
            self.minslider.setValue(1000)
        _range = max(self.maxbox.maximum()-lo, self.axis.min_range)
        try:
            self.maxslider.setValue(1000*(hi-lo)/_range)
        except (ZeroDivisionError, OverflowError):
            self.maxslider.setValue(0)
        self.block_signals(False)

    def block_signals(self, block=True):
        self.minbox.blockSignals(block)
        self.maxbox.blockSignals(block)
        if self.minslider: self.minslider.blockSignals(block)
        if self.maxslider: self.maxslider.blockSignals(block)

    def set_log(self):
        if self.name == 'v':
            self.plot.plot2D()
        else:
            self.plot.replot_logs()

    def set_lock(self):
        if self.lockbox.isChecked():
            self.axis.locked = True
            lo, hi = self.axis.get_limits()
            self.axis.diff = self.maxbox.diff = self.minbox.diff = hi - lo
            self.minbox.setDisabled(True)
        else:
            self.axis.locked = False
            self.axis.diff = self.maxbox.diff = self.minbox.diff = None
            self.minbox.setDisabled(False)

    def set_autoscale(self):
        if self.scalebox.isChecked():
            self.plot.autoscale = True
        else:
            self.plot.autoscale = False

    @QtCore.Slot()
    def replot(self):
        self.block_signals(True)
        self.plot.plotdata = self.plot.data2D()
        self.plot.plot2D()
        self.block_signals(False)

    def reset(self):
        self.axis.min = np.nanmin(self.axis.data)
        self.axis.max = np.nanmax(self.axis.data)
        self.minbox.setRange(self.axis.min, self.axis.max)
        self.maxbox.setRange(self.axis.min, self.axis.max)
        self.set_limits(self.axis.min, self.axis.max)
        if self.name == 'x' or self.name == 'y':
            self.plot.replot_axes()
        elif self.name == 'v':
            self.plot.plot2D()

    def get_limits(self):
        return self.minbox.value(), self.maxbox.value()

    def set_limits(self, lo, hi):
        self.axis.set_limits(lo, hi)
        self.minbox.setValue(lo)
        self.maxbox.setValue(hi)
        if not self.zaxis:
            self.set_sliders(lo, hi)

    def change_axis(self):
        axis = self.plot.axis[self.axiscombo.currentText()]
        self.plot.change_axis(self, axis)
        if self.lockbox:
            if self.axis.locked:
                self.lockbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.lockbox.setCheckState(QtCore.Qt.Unchecked)

    def get_axes(self):
        if self.zaxis:
            plot_axes = [self.plot.xaxis.name, self.plot.yaxis.name]
            return  [axis.nxname for axis in self.plot.axes 
                        if axis.nxname not in plot_axes]
        else:
            return [axis.nxname for axis in self.plot.axes]

    def change_cmap(self):
        self.plot.plot2D()

    def set_cmap(self, cmap):
        self.cmapcombo.setCurrentIndex(self.cmapcombo.findText(cmap))

    def get_cmap(self):
        return self.cmapcombo.currentText()

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
        self.add_action(_refresh_icon, self.replot, "Replot")
        self.toolbar.addSeparator()
        self.add_action(_backward_icon, self.playback, "Play Back")
        self.add_action(_pause_icon, self.playpause, "Pause")
        self.add_action(_forward_icon, self.playforward, "Play Forward")
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.slideshow)
        self.playsteps = 0

    def add_action(self, icon, slot, tooltip):
        action = self.toolbar.addAction(icon, '', slot)
        action.setToolTip(tooltip)

    def slideshow(self):
        self.maxbox.stepBy(self.playsteps)
        if self.maxbox.value() >= self.maxbox.data[-1] or \
           self.minbox.value() <= self.minbox.data[0]:
            self.timer.stop()

    def playback(self):
        self.lockbox.setChecked(True)
        self.set_lock()
        if self.playsteps == -1:
            self.interval = self.timer.interval() / 2
        else:
            self.playsteps = -1
            self.interval = 1000
        self.timer.setInterval(self.interval)
        self.timer.start(self.interval)
        
    def playpause(self):
        self.playsteps = 0
        self.timer.stop()
            
    def playforward(self):
        self.lockbox.setChecked(True)
        self.set_lock()
        if self.playsteps == 1:
            self.interval = self.timer.interval() / 2
        else:
            self.playsteps = 1
            self.interval = 1000
        self.timer.setInterval(self.interval)
        self.timer.start(self.interval)

class NXTextBox(QtGui.QLineEdit):

    def value(self):
        return float(unicode(self.text()))

    def setValue(self, value):
        self.setText(str(float('%.4g' % value)))


class NXSpinBox(QtGui.QSpinBox):

    def __init__(self, data=None):
        super(NXSpinBox, self).__init__()
        self.data = data
        self.validator = QtGui.QDoubleValidator()
        self.old_value = None
        self.diff = None

    def value(self):
        if self.data is not None:
            return float(self.data[self.index])
        else:
            return 0.0

    @property
    def index(self):
        return super(NXSpinBox, self).value()

    def setValue(self, value):
        super(NXSpinBox, self).setValue(self.valueFromText(value))

    def valueFromText(self, text):
        try:
            value = float(unicode(text))
            return len(self.data[self.data<value])
        except IndexError:
            return self.maximum()

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

    def minBoundaryValue(self, idx):
        if idx <= 0:
            return self.data[0] - (np.float(self.data[1]) - 
                                   np.float(self.data[0])) / 2
        elif idx >= len(self.data) - 1:
            return self.data[-1] - (np.float(self.data[-1]) - 
                                    np.float(self.data[-2])) / 2
        else:
            return self.data[idx] - (np.float(self.data[idx]) - 
                                     np.float(self.data[idx-1])) / 2

    def maxBoundaryValue(self, idx):
        if idx <= 0:
            return self.data[0] + (np.float(self.data[1]) - 
                                   np.float(self.data[0])) / 2
        elif idx >= len(self.data) - 1:
            return self.data[-1] + (np.float(self.data[-1]) - 
                                    np.float(self.data[-2])) / 2
        else:
            return self.data[idx] + (np.float(self.data[idx+1]) - 
                                     np.float(self.data[idx])) / 2

    def validate(self, input_value, pos):
        return self.validator.validate(input_value, pos)

    def stepBy(self, steps):
        if self.diff:
            self.setValue(self.value() + steps * self.diff)
        else:
            super(NXSpinBox, self).stepBy(steps)


class NXDoubleSpinBox(QtGui.QDoubleSpinBox):

    def __init__(self, data=None):
        super(NXDoubleSpinBox, self).__init__()
        self.validator = QtGui.QDoubleValidator()
        self.validator.setRange(-np.inf,np.inf)
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


class NXProjectionTab(QtGui.QWidget):

    def __init__(self, plotview=None):

        super(NXProjectionTab, self).__init__()

        hbox = QtGui.QHBoxLayout()
        widgets = []

        self.xbox = QtGui.QComboBox()
        self.xbox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.xbox.activated.connect(self.set_xaxis)
        widgets.append(QtGui.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = QtGui.QComboBox()
        self.ybox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ybox.activated.connect(self.set_yaxis)
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

        self.panel = None
        self.plotview = plotview

    def get_axes(self):
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        axes = self.get_axes()    
        self.xbox.clear()
        self.xbox.addItems(axes)
        self.xbox.setCurrentIndex(self.xbox.findText(self.plotview.plot.xaxis.name))
        self.xaxis = self.xbox.currentText()
        if self.plotview.plot.ndim <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
            self.yaxis = 'None'
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0,'None')
            self.ybox.addItems(axes)
            self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.plot.yaxis.name))
            self.yaxis = self.ybox.currentText()

    def set_xaxis(self):
        self.xaxis = self.xbox.currentText()

    def set_yaxis(self):
        self.yaxis = self.ybox.currentText()

    def get_projection(self):
        x = self.get_axes().index(self.xaxis)
        if self.yaxis == 'None':
            axes = [x]
        else:
            y = self.get_axes().index(self.yaxis)
            axes = [y,x]
        limits = [(self.plotview.plot.axis[name].lo, 
                   self.plotview.plot.axis[name].hi) 
                   for name in self.get_axes()]
        if self.plotview.plot.zoom:
            xdim, xlo, xhi = self.plotview.plot.zoom['x']
            ydim, ylo, yhi = self.plotview.plot.zoom['y']
        else:
            xaxis = self.plotview.plot.xaxis
            xdim, xlo, xhi = xaxis.dim, xaxis.lo, xaxis.hi
            yaxis = self.plotview.plot.yaxis
            ydim, ylo, yhi = yaxis.dim, yaxis.lo, yaxis.hi
            
        limits[xdim] = (xlo, xhi)
        limits[ydim] = (ylo, yhi)
        for axis in axes:
            if axis not in [ydim, xdim]:
                limits[axis] = (None, None)
        shape = self.plotview.plot.data.nxsignal.shape
        if len(shape) - len(limits) == shape.count(1):
            axes, limits = self.fix_projection(shape, axes, limits)
        return axes, limits

    def fix_projection(self, shape, axes, limits):
        axis_map = {}
        for axis in axes:
            axis_map[axis] = limits[axis]
        fixed_limits = []
        for s in shape:
            if s == 1:
                fixed_limits.append((None, None))
            else:
                fixed_limits.append(limits.pop(0))
        fixed_axes = []
        for axis in axes:
            fixed_axes.append(fixed_limits.index(axis_map[axis]))
        return fixed_axes, fixed_limits

    def save_projection(self):
        axes, limits = self.get_projection()
        keep_data(self.plotview.plot.data.project(axes, limits))

    def plot_projection(self):
        axes, limits = self.get_projection()
        projection = change_plotview("Projection - " + self.plotview.label)
        if len(axes) == 1 and self.overplot_box.isChecked():
            over = True
        else:
            over = False
        projection.plot.plot(self.plotview.plot.data.project(axes, limits), 
                             over=over)
        if len(axes) == 1:
            self.overplot_box.setVisible(True)
        else:
            self.overplot_box.setVisible(False)
            self.overplot_box.setChecked(False)
        self.plotview.make_active()
        plotviews[projection.label].raise_()

    def open_panel(self):
        if not self.panel:
            self.panel = NXProjectionPanel(plotview=self.plotview, parent=self)        
        self.panel.show()
        self.panel.update_limits()


class NXProjectionPanel(QtGui.QDialog):

    def __init__(self, plotview=None, parent=None):

        QtGui.QDialog.__init__(self, parent)
 
        self.plotview = plotview

        layout = QtGui.QVBoxLayout()

        axisbox = QtGui.QHBoxLayout()
        widgets = []

        self.xbox = QtGui.QComboBox()
        self.xbox.setCurrentIndex(self.xbox.findText(self.plotview.plot.xaxis.name))
        self.xbox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.xbox.activated.connect(self.set_xaxis)
        widgets.append(QtGui.QLabel('X-Axis:'))
        widgets.append(self.xbox)
        self.xaxis = self.xbox.currentText()

        self.ybox = QtGui.QComboBox()
        self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.plot.yaxis.name))
        self.ybox.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        self.ybox.activated.connect(self.set_yaxis)
        self.ylabel = QtGui.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)
        self.yaxis = self.ybox.currentText()

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
        for axis in self.get_axes():
            row += 1
            self.minbox[axis] = self.spinbox()
            self.maxbox[axis] = self.spinbox()
            self.lockbox[axis] = QtGui.QCheckBox()
            self.lockbox[axis].stateChanged.connect(self.set_lock)
            grid.addWidget(QtGui.QLabel(axis), row, 0)
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

        self.close_button = QtGui.QPushButton("Close Panel", self)
        self.close_button.clicked.connect(self.close)
        self.close_button.setDefault(False)
        self.close_button.setAutoDefault(False)
        layout.addWidget(self.close_button)
        
        self.setLayout(layout)
        self.setWindowTitle('Projection Panel - ' + self.plotview.label)

        for axis in self.get_axes():
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.plot.axis[axis].centers
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.minbox[axis].diff = self.maxbox[axis].diff = None

        for axis in self.get_axes():
            self.minbox[axis].setValue(self.minbox[axis].data[0])
            self.maxbox[axis].setValue(self.minbox[axis].data[-1])
            self.lockbox[axis].setChecked(False)

        self.rectangle = None

    def get_axes(self):
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        axes = self.get_axes()    
        self.xbox.clear()
        self.xbox.addItems(axes)
        self.xbox.setCurrentIndex(self.xbox.findText(self.plotview.plot.xaxis.name))
        self.xaxis = self.xbox.currentText()
        if self.plotview.plot.ndim <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
            self.yaxis = 'None'
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0,'None')
            self.ybox.addItems(axes)
            self.ybox.setCurrentIndex(self.ybox.findText(self.plotview.plot.yaxis.name))
            self.yaxis = self.ybox.currentText()

    def set_xaxis(self):
        self.xaxis = self.xbox.currentText()
        if self.xaxis == self.yaxis:
            self.ybox.setCurrentIndex(self.ybox.findText('None'))
            self.yaxis = 'None'

    def set_yaxis(self):
        yaxis = self.yaxis
        self.yaxis = self.ybox.currentText()
        if self.yaxis == self.xaxis and yaxis != 'None':
            self.xbox.setCurrentIndex(self.xbox.findText(yaxis))
            self.xaxis = yaxis
        else:
            for idx in range(self.xbox.count()):
                if self.xbox.itemText(idx) != self.yaxis:
                    self.xbox.setCurrentIndex(idx)
                    self.xaxis = self.xbox.currentText()
                    break

    def set_limits(self):
        for axis in self.get_axes():
            if self.lockbox[axis].isChecked():
                min_value = self.maxbox[axis].value() - self.maxbox[axis].diff
                self.minbox[axis].setValue(min_value)
            elif self.minbox[axis].value() > self.maxbox[axis].value():
                self.minbox[axis].setValue(self.maxbox[axis].value())
        self.draw_rectangle()

    def get_limits(self, axis=None):
        if axis:
            return self.minbox[axis].index, self.maxbox[axis].index+1
        else:
            return [(self.minbox[axis].index, self.maxbox[axis].index+1) 
                     for axis in self.get_axes()]
    
    def update_limits(self):
        for axis in self.get_axes():
            lo, hi = self.plotview.plot.axis[axis].get_limits()
            self.minbox[axis].setValue(lo)
            self.minbox[axis].stepBy(1)
            self.maxbox[axis].setValue(hi)
            self.maxbox[axis].stepBy(-2)

    def set_lock(self):
        for axis in self.get_axes():
            if self.lockbox[axis].isChecked():
                lo, hi = self.minbox[axis].value(), self.maxbox[axis].value()
                self.minbox[axis].diff = self.maxbox[axis].diff = hi - lo
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
        shape = self.plotview.plot.data.nxsignal.shape
        if len(shape) - len(limits) == shape.count(1):
            axes, limits = self.fix_projection(shape, axes, limits)
        return axes, limits

    def fix_projection(self, shape, axes, limits):
        axis_map = {}
        for axis in axes:
            axis_map[axis] = limits[axis]
        fixed_limits = []
        for s in shape:
            if s == 1:
                fixed_limits.append((None, None))
            else:
                fixed_limits.append(limits.pop(0))
        fixed_axes = []
        for axis in axes:
            fixed_axes.append(fixed_limits.index(axis_map[axis]))
        return fixed_axes, fixed_limits

    def save_projection(self):
        axes, limits = self.get_projection()
        keep_data(self.plotview.plot.data.project(axes, limits))

    def plot_projection(self):
        axes, limits = self.get_projection()
        projection = change_plotview("Projection - " + self.plotview.label)
        if len(axes) == 1 and self.overplot_box.isChecked():
            over = True
        else:
            over = False
        projection.plot.plot(self.plotview.plot.data.project(axes, limits), 
                             over=over)
        if len(axes) == 1:
            self.overplot_box.setVisible(True)
        else:
            self.overplot_box.setVisible(False)
            self.overplot_box.setChecked(False)
        self.plotview.make_active()
        plotviews[projection.label].raise_()

    def mask_data(self):
        try:
            limits = tuple(slice(x,y) for x,y in self.get_limits())
            self.plotview.plot.data.nxsignal[limits] = np.ma.masked
            self.plotview.xtab.replot()
        except NeXusError as error:
            from mainwindow import report_error
            report_error("Masking Data", error)

    def unmask_data(self):
        try:
            limits = tuple(slice(x,y) for x,y in self.get_limits())
            self.plotview.plot.data.nxsignal.mask[limits] = np.ma.nomask
            self.plotview.xtab.replot()
        except NeXusError as error:
            from mainwindow import report_error
            report_error("Masking Data", error)

    def spinbox(self):
        spinbox = NXSpinBox()
        spinbox.setAlignment(QtCore.Qt.AlignRight)
        spinbox.setFixedWidth(100)
        spinbox.setKeyboardTracking(False)
        spinbox.setAccelerated(True)
        spinbox.editingFinished.connect(self.set_limits)
        spinbox.valueChanged[unicode].connect(self.set_limits)
        return spinbox

    def draw_rectangle(self):
        try:
            self.rectangle.remove()
        except:
            pass
        ax = self.plotview.figure.axes[0]
        xp = self.plotview.plot.xaxis.name
        yp = self.plotview.plot.yaxis.name
        x0 = self.minbox[xp].minBoundaryValue(self.minbox[xp].index)
        x1 = self.maxbox[xp].maxBoundaryValue(self.maxbox[xp].index)
        y0 = self.minbox[yp].minBoundaryValue(self.minbox[yp].index)
        y1 = self.maxbox[yp].maxBoundaryValue(self.maxbox[yp].index)
        
        self.rectangle = ax.add_patch(Rectangle((x0,y0),x1-x0,y1-y0))
        self.rectangle.set_color('white')
        self.rectangle.set_facecolor('none')
        self.rectangle.set_linestyle('dashed')
        self.rectangle.set_linewidth(2)
        self.plotview.canvas.draw()

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
        self.plotview.ptab.panel = None
        self.deleteLater()


class NXNavigationToolbar(NavigationToolbar):

    def __init__(self, canvas, parent):
        super(NXNavigationToolbar, self).__init__(canvas, parent)
        self.plotview = canvas.parent()
        self.zoom()

    def _init_toolbar(self):

        self.toolitems = list(self.toolitems)
        self.toolitems.append(('Add', 'Add plot data to the tree', 'hand', 'add_data'))
        super(NXNavigationToolbar, self)._init_toolbar()

    def home(self, *args):
        self.plotview.xtab.reset()
        self.plotview.ytab.reset()
        self.plotview.vtab.reset()
        if self.plotview.ptab.panel:
            self.plotview.ptab.panel.update_limits()            

    def add_data(self):
        keep_data(self.plotview.plot.plotdata)

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
            Xmin,Xmax=a.get_xlim()
            Ymin,Ymax=a.get_ylim()

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
                    self.plotview.plot.zoom = {'x': (xdim, x0, x1), 
                                               'y': (ydim, y0, y1)}
                if self.plotview.label != "Projection":
                    self.plotview.tab_widget.setCurrentWidget(self.plotview.ptab)
            elif self._button_pressed == 3:
                if self._zoom_mode == "x":
                    self.plotview.xtab.set_limits(x0, x1)
                elif self._zoom_mode == "y":
                    self.plotview.ytab.set_limits(y0, y1)
                else:
                    xdim = self.plotview.xtab.axis.dim
                    ydim = self.plotview.ytab.axis.dim
                    self.plotview.plot.zoom = {'x': (xdim, x0, x1), 
                                               'y': (ydim, y0, y1)}
                if self.plotview.label != "Projection":
                    self.plotview.tab_widget.setCurrentWidget(self.plotview.ptab)
            if self.plotview.ptab.panel:
                self.plotview.ptab.panel.update_limits()

        self.draw()
        self._xypress = None
        self._button_pressed = None

        self._zoom_mode = None

        self.push_current()
        self.release(event)

    def release_pan(self, event):
        super(NXNavigationToolbar, self).release_pan(event)
        ax = self.plotview.figure.gca()
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        self.plotview.xtab.set_limits(xmin, xmax)
        self.plotview.ytab.set_limits(ymin, ymax)
        if self.plotview.ptab.panel:
            self.plotview.ptab.panel.update_limits()            

    def _update_view(self):
        super(NXNavigationToolbar, self)._update_view()
        lims = self._views()
        if lims is None: return
        xmin, xmax, ymin, ymax = lims[0]
        self.plotview.xtab.axis.set_limits(xmin, xmax)
        self.plotview.xtab.minbox.setValue(xmin)
        self.plotview.xtab.maxbox.setValue(xmax)
        self.plotview.xtab.set_sliders(xmin, xmax)
        self.plotview.ytab.axis.set_limits(ymin, ymax)
        self.plotview.ytab.minbox.setValue(ymin)
        self.plotview.ytab.maxbox.setValue(ymax)
        self.plotview.ytab.set_sliders(ymin, ymax)

#    def set_cursor(self, cursor):
#        pass


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

def centers(shape, axes):
    """
    Return the centers of the axes.

    This works regardless if the axes contain bin boundaries or centers.
    """
    def findc(axis, dimlen):
        if axis.shape[0] == dimlen+1:
            return (axis.nxdata[:-1] + axis.nxdata[1:])/2
        else:
            assert axis.shape[0] == dimlen
            return axis.nxdata
    return [findc(a,shape[i]) for i,a in enumerate(axes)]

def boundaries(axis, dimlen):
    """
    Return the bin boundary of an axis given the data dimension.

    This works regardless if the axis contains bin boundaries or centers.
    """
    if axis.shape[0] == dimlen:
        start = axis[0] - (axis[1] - axis[0])/2
        end = axis[-1] + (axis[-1] - axis[-2])/2
        return np.concatenate((np.atleast_1d(start),
                               (axis[:-1] + axis[1:])/2,
                               np.atleast_1d(end)))
    else:
        assert axis.shape[0] == dimlen+1
        return axis
