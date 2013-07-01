"""
Plotting window
"""
import sys, os, random

import numpy as np

from IPython.external.qt import QtCore, QtGui

import matplotlib
from matplotlib._pylab_helpers import Gcf
from matplotlib import is_interactive
from matplotlib.backend_bases import FigureManagerBase
from matplotlib.backends.backend_qt4 import FigureManagerQT as FigureManager
from matplotlib.backends.backend_qt4agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt4agg import NavigationToolbar2QTAgg as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.image import NonUniformImage
from matplotlib.colors import LogNorm, Normalize
import matplotlib.backends.qt4_editor.figureoptions as figureoptions
import matplotlib._image as _image
import matplotlib.pyplot as plt

from nexpy.api.nexus import NXfield, NXdata, NXroot

def new_figure_manager( num, *args, **kwargs ):
    """
    Create a new figure manager instance
    """
    thisFig = Figure( *args, **kwargs )
    canvas = NXCanvas( thisFig )
    manager = NXFigureManager( canvas, num )
    return manager

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
        FigureManagerBase.__init__( self, canvas, num )
        self.canvas = canvas

        self.window = QtGui.QWidget()
        self.window.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        QtCore.QObject.connect( self.window, QtCore.SIGNAL( 'destroyed()' ),
                            self._widgetclosed )
        self.window._destroying = False

        self.toolbar = NXNavigationToolbar(self.canvas, self.window)
        tbs_height = self.toolbar.sizeHint().height()

        # resize the main window so it will display the canvas with the
        # requested size:
        cs = canvas.sizeHint()
        self.window.resize(cs.width(), cs.height())
        self.window.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding, 
                                  QtGui.QSizePolicy.MinimumExpanding)

        if is_interactive():
            self.window.show()

        # attach a show method to the figure for pylab ease of use
        self.canvas.figure.show = lambda *args: self.window.show()

        def notify_axes_change( fig ):
           # This will be called whenever the current axes is changed
           if self.toolbar is not None:
               self.toolbar.update()
        self.canvas.figure.add_axobserver( notify_axes_change )

plotview = None
cmaps = ['autumn', 'bone', 'cool', 'copper', 'flag', 'gray', 'hot', 
         'hsv', 'jet', 'pink', 'prism', 'spring', 'summer', 'winter', 
         'spectral', 'rainbow']
colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']


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
    def __init__(self, parent=None):
        
        super(NXPlotView, self).__init__(parent)

        self.setSizePolicy(QtGui.QSizePolicy.MinimumExpanding,
                           QtGui.QSizePolicy.MinimumExpanding)

        global plotview
        plotview = self

        self.figuremanager = new_figure_manager(1)
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
            Gcf.set_active(self.figuremanager)
        cid = self.canvas.mpl_connect('button_press_event', make_active)
        self.figuremanager._cidgcf = cid
        self.figure = self.canvas.figure
        self.figure.set_label("Main")
        
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.canvas)

        self.tab_widget = QtGui.QTabWidget()
        self.tab_widget.setFixedHeight(80)

        self.vtab = NXPlotTab('v', axis=False, cmap=True, plotview=self)
        self.xtab = NXPlotTab('x', plotview=self)
        self.ytab = NXPlotTab('y', plotview=self)
        self.ztab = NXPlotTab('z', log=False, zaxis=True, plotview=self)
        self.ptab = NXProjectionTab()
        self.otab = NXNavigationToolbar(self.canvas, self.tab_widget)
        self.tab_widget.addTab(self.xtab, 'x')
        self.tab_widget.addTab(self.ytab, 'y')
        self.tab_widget.addTab(self.otab, 'options')
        self.currentTab = self.otab
        self.tab_widget.setCurrentWidget(self.currentTab)

        vbox.addWidget(self.tab_widget)
        self.setLayout(vbox)

        self.mainplot = NXPlot(self, "Main")
                
#        self.grid_cb = QtGui.QCheckBox("Show &Grid")
#        self.grid_cb.setChecked(False)
#        self.grid_cb.stateChanged.connect(self.on_draw)

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
    
    def plot(self, data, fmt, xmin, xmax, ymin, ymax, vmin, vmax, **opts):
        """
        Plots the data into the current matplotlib figure with optional axis limits
        
        This is the function invoked by the NXgroup plot method. It creates an NXPlot 
        object and calls its standard plotting method.
        
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
            This dictionary can contain any valid matplotlib switches.
        """
        label = plt.gcf().get_label()
        if label == "Main":
            plot = self.mainplot
        elif label == "Projection":
            if not hasattr(self, "projection_plot"):
                self.projection_plot = NXPlot(self, "Projection")
            plot = self.projection_plot
        else:
            if not hasattr(self, "projection_plot"):
                self.projection_plot = NXPlot(self, "Projection")
            plot = self.projection_plot        
        plot.plot(data, fmt, xmin, xmax, ymin, ymax, vmin, vmax, **opts)
                                    

class NXPlot(object):
    """
    A NeXpy plotting pane with associated axis and option tabs.
    
    The plot is created using matplotlib and may be contained within the main NeXpy
    plotting pane or in a separate window, depending on the current matplotlib figure.
    """

    def __init__(self, parent, label=None):

        self.plotview = parent
        if label:
            self.label = label
            
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
        self.autoplot = False      
    
    def plot(self, data, fmt, xmin, xmax, ymin, ymax, vmin, vmax, **opts):
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

        if cmap in cmaps: self.set_cmap(cmap)

        self.data = data
        self.title = data.nxtitle
        self.shape, self.axes = self._fixaxes(data.nxsignal, data.nxaxes)
        axis_data = centers(self.shape, self.axes)
        i = 0
        self.axis = {}
        for axis in self.axes:
            self.axis[axis.nxname] = NXPlotAxis(axis)
            self.axis[axis.nxname].centers = axis_data[i]
            self.axis[axis.nxname].dim = i
            i = i + 1
        # Find the centers of the bins for histogrammed data

        self.dims = len(self.shape)

        #One-dimensional Plot
        if self.dims == 1:
            self.plotdata = NXdata(NXfield(data.nxsignal.view().reshape(self.shape),
                                           name=data.nxsignal.nxname,
                                           attrs=data.nxsignal.attrs),
                                   NXfield(axis_data[0], name=self.axes[0].nxname,
                                           attrs=self.axes[0].attrs),
                                   title = self.title)
            if data.nxerrors:
                self.plotdata.errors = NXfield(data.errors.view().reshape(self.shape))
            elif hasattr(data.nxsignal, 'units') and data.nxsignal.units == 'counts':
                self.plotdata.errors = NXfield(np.sqrt(self.plotdata.nxsignal))

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

                if logx: self.xtab.logbox.setChecked(True)
                if log or logy: self.ytab.logbox.setChecked(True)

            if fmt == '': fmt = colors[self.num%len(colors)]+'o'
                
            self.plot1D(fmt, over, **opts)

        #Higher-dimensional plot
        else:
            if self.dims > 2:
                dims = range(self.dims)
                axis = dims[-2:]
                limits = [(axis_data[i][0], axis_data[i][0]) for i in dims[:-2]]
                limits.append((axis_data[-2].min(),axis_data[-2].max()))
                limits.append((axis_data[-1].min(),axis_data[-1].max()))
                self.plotdata = self.data.project(axis,limits)
            else:
                self.plotdata = NXdata(NXfield(data.nxsignal.view().reshape(self.shape),
                                               name=data.nxsignal.nxname,
                                               attrs=data.nxsignal.attrs),
                                       [NXfield(axis_data[-2], name=self.axes[-2].nxname,
                                                attrs=self.axes[-2].attrs),
                                        NXfield(axis_data[-1], name=self.axes[-1].nxname,
                                                attrs=self.axes[-1].attrs)],
                                       title = self.title)

            self.xaxis = self.axis[self.axes[-2].nxname]
            if xmin: self.xaxis.lo = xmin
            if xmax: self.xaxis.hi = xmax

            self.yaxis = self.axis[self.axes[-1].nxname]
            if ymin: self.yaxis.lo = ymin
            if ymax: self.yaxis.hi = ymax

            self.vaxis = NXPlotAxis(self.plotdata.nxsignal)
            if vmin: self.vaxis.lo = vmin
            if vmax: self.vaxis.hi = vmax

            if log: self.vtab.logbox.setChecked(True)
 
            if self.dims > 2:
                self.zaxis = self.axis[self.axes[-3].nxname]
                self.zaxis.lo = self.zaxis.hi = self.zaxis.min
                for axis in self.axes[:-3]:
                    self.axis[axis.nxname].lo = self.axis[axis.nxname].hi \
                        = axis.nxdata[0]
            else:
                zaxis = None                  

            self.plot2D(**opts)

        self.canvas.draw_idle()
        if self.label == "Main":
            self.init_tabs()
        else:
            plt.figure("Main")

    def plot1D(self, fmt, over=False, **opts):

        plt.ioff()
        
        if not over: plt.clf()
        ax = plt.gca()
        if not over: ax.autoscale(enable=True)
        
        self.x = self.plotdata.nxaxes[0].nxdata
        self.y = self.plotdata.nxsignal.nxdata
        if self.plotdata.nxerrors:
            self.e = self.plotdata.nxerrors.nxdata
            ax.errorbar(self.x, self.y, self.e, fmt=fmt, **opts)
        else:
            self.e = None
            ax.plot(self.x, self.y, fmt,  **opts)

        path = self.data.nxsignal.nxpath
        if self.data.nxroot.nxclass == "NXroot":
            path = self.data.nxroot.nxname+path
        ax.lines[-1].set_label(path)

        if not over:

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

        self.xaxis.min, self.xaxis.max = ax.set_xlim()
        self.yaxis.min, self.yaxis.max = ax.set_ylim()
        self.xaxis.lo, self.xaxis.hi = self.xaxis.min, self.xaxis.max
        self.yaxis.lo, self.yaxis.hi = self.yaxis.min, self.yaxis.max

        self.canvas.draw_idle()
        self.otab.push_current()
        plt.ion()

    def plot2D(self, **opts):

        plt.ioff()
        plt.clf()

        self.v = self.plotdata.nxsignal.nxdata.T
        self.x = self.plotdata.nxaxes[0].nxdata
        self.y = self.plotdata.nxaxes[1].nxdata

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

        ax = plt.gca()
        ax.autoscale(enable=True)
        cmap = self.get_cmap()
        extent = (self.xaxis.min,self.xaxis.max,self.yaxis.min,self.yaxis.max)

        self.image = NonUniformImage(ax, extent=extent, cmap=cmap, **opts)
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
            except:
                self.colorbar = plt.colorbar(self.image)
        else:
            self.colorbar = plt.colorbar(self.image)

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
        plt.ion()

    def data2D(self):
        axes = [self.xaxis.dim,self.yaxis.dim]
        limits = []
        for axis in self.axes:
            if self.axis[axis.nxname].dim in axes: 
                limits.append((None,None))
            else:
                limits.append((self.axis[axis.nxname].lo,
                               self.axis[axis.nxname].hi))
        return self.data.project(axes, limits)

    def replot_axes(self):
        ax = self.canvas.figure.gca()
        ax.set_xlim(self.xaxis.get_limits())
        ax.set_ylim(self.yaxis.get_limits())
        self.canvas.draw_idle()
        self.otab.push_current()

    def replot_logs(self):
        ax = self.canvas.figure.gca()
        if self.xtab.logbox.isChecked():
            ax.set_xscale('symlog')
        else:
            ax.set_xscale('linear')
        if self.ytab.logbox.isChecked():
            ax.set_yscale('symlog')
        else:
            ax.set_yscale('linear')
        self.canvas.draw_idle()
        
    @staticmethod
    def show():
        plt.show()    

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
        if self.dims == 1:
            self.xtab.logbox.setVisible(True)
            self.xtab.axiscombo.setVisible(False)
            self.ytab.logbox.setVisible(True)
            self.ytab.axiscombo.setVisible(False)
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.vtab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ztab))
            self.tab_widget.removeTab(self.tab_widget.indexOf(self.ptab))
        elif self.dims >= 2:
            self.vtab.set_axis(self.vaxis)
            if self.tab_widget.indexOf(self.vtab) == -1:
                self.tab_widget.insertTab(0,self.vtab,'signal')
            if self.tab_widget.indexOf(self.ptab) == -1:
                self.tab_widget.insertTab(self.tab_widget.indexOf(self.otab),
                                          self.ptab,'projections')
            self.ptab.set_axes()
            if self.dims > 2:
                self.ztab.set_axis(self.zaxis)
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

    def change_axis(self, tab, axis):
        if tab == self.xtab and axis == self.yaxis:
            self.yaxis = self.ytab.axis = self.xtab.axis
            self.xaxis = self.xtab.axis = axis
            self.plotdata = NXdata(self.plotdata.nxsignal.T, self.plotdata.nxaxes[::-1],
                                   title = self.title)
            self.plot2D()
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.vtab.set_axis(self.vaxis)
        elif tab == self.ytab and axis == self.xaxis:
            self.xaxis = self.xtab.axis = self.ytab.axis
            self.yaxis = self.ytab.axis = axis
            self.plotdata = NXdata(self.plotdata.nxsignal.T, self.plotdata.nxaxes[::-1],
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
            axes = [self.xaxis.dim,self.yaxis.dim]
            limits = []
            for axis in self.axes:
                if self.axis[axis.nxname].dim in axes: 
                    limits.append((None,None))
                else:
                    limits.append((self.axis[axis.nxname].lo,
                                   self.axis[axis.nxname].hi))
            self.plotdata = self.data.project(axes,limits)
            self.plot2D()
            self.xtab.set_axis(self.xaxis)
            self.ytab.set_axis(self.yaxis)
            self.ztab.set_axis(self.zaxis)
            self.vtab.set_axis(self.vaxis)


class NXPlotAxis(object):

    def __init__(self, axis):
        self.name = axis.nxname
        self.data = axis.nxdata
        self.dims = len(axis.nxdata.shape)
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
            self.minbox = self.spinbox(self.read_minbox)
            self.minslider = self.slider(self.read_minslider)
            self.maxslider = self.slider(self.read_maxslider)
            self.maxbox = self.spinbox(self.read_maxbox)
            widgets.append(self.minbox)
            widgets.extend([self.minslider, self.maxslider])
            widgets.append(self.maxbox)
        if zaxis:
            self.lockbox = self.checkbox("Lock", self.set_lock)
            self.scalebox = self.checkbox("Autoscale", self.set_autoscale)
            self.scalebox.setChecked(False)
            self.plotbox = self.checkbox("Autoplot", self.set_autoplot)
            self.plotbox.setChecked(False)
            self.plotbutton =  self.pushbutton("Replot", self.replot)
            widgets.append(self.lockbox)
            widgets.append(self.scalebox)
            widgets.append(self.plotbox)
            widgets.append(self.plotbutton)
        else:
            self.lockbox = None
            self.scalebox = None
            self.plotbox = None
        if log: 
            self.logbox = self.checkbox("Log", self.set_log)
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
        self.plotview = plotview

    def set_axis(self, axis):
        self.plot = self.plotview.mainplot
        self.axis = axis
        if self.zaxis:
            self.minbox.data = self.maxbox.data = self.axis.data  
            self.minbox.data_locked = self.maxbox.data_locked = True      
            self.minbox.setRange(0, len(self.axis.data)-1)
            self.maxbox.setRange(0, len(self.axis.data)-1)
        else:
            self.minbox.set_data(axis.min, axis.max)
            self.maxbox.set_data(axis.min, axis.max)
            self.minbox.data_locked = self.maxbox.data_locked = False
            self.minbox.setRange(0,200)
            self.maxbox.setRange(0,200)            
        self.minbox.setValue(axis.lo)
        self.maxbox.setValue(axis.hi)
        if not self.zaxis:
            self.block_signals(True)
            self.set_sliders(axis.lo, axis.hi)
            self.block_signals(False)
        if self.axiscombo:
            self.axiscombo.clear()
            self.axiscombo.addItems(self.get_axes())
            self.axiscombo.setCurrentIndex(self.axiscombo.findText(axis.name))

    def combobox(self, slot):
        combobox = QtGui.QComboBox()
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
        spinbox.editingFinished.connect(slot)
        spinbox.valueChanged[unicode].connect(slot)
        return spinbox

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
        self.block_signals(True)
        lo, hi = self.minbox.value(), self.maxbox.value()
        self.maxbox.data = self.minbox.data
        if lo is not None and (lo <= hi or self.axis.locked): 
            self.axis.lo = lo
        else:
            self.minbox.setValue(self.axis.lo)
        if self.axis.locked:
            self.axis.hi = self.axis.lo + self.axis.diff
            self.maxbox.setValue(self.axis.hi)
        if self.name == 'x' or self.name == 'y':
            self.set_sliders(self.axis.lo, hi)
            self.plot.replot_axes()
        elif self.name == 'z' and self.plot.autoplot:
            self.replot()
        elif self.name == 'v':
            self.set_sliders(self.axis.lo, hi)
            self.plot.plot2D()
        self.block_signals(False)

    def read_maxbox(self):
        self.block_signals(True)
        lo, hi = self.minbox.value(), self.maxbox.value()
        self.minbox.data = self.maxbox.data
        if hi is not None and (hi >= lo or self.axis.locked): 
            self.axis.hi = hi
        else:
            self.maxbox.setValue(self.axis.hi)
        if self.axis.locked:
            self.axis.lo = self.axis.hi - self.axis.diff
            self.minbox.setValue(self.axis.lo)
        if self.name == 'x' or self.name == 'y':
            self.set_sliders(lo, self.axis.hi)
            self.plot.replot_axes()
        elif self.name == 'z' and self.plot.autoplot:
            self.replot()
        elif self.name == 'v':
            self.set_sliders(lo, self.axis.hi)
            self.plot.plot2D()
        self.block_signals(False)
    
    def read_minslider(self):
        self.block_signals(True)
        self.axis.hi = self.maxbox.value()
        range = max(self.axis.hi-self.minbox.data[0], self.axis.min_range)
        self.axis.lo = self.minbox.data[0] + (self.minslider.value() * range / 1000)
        self.minbox.setValue(self.axis.lo)
        range = max(self.maxbox.data[-1]-self.axis.lo, self.axis.min_range)
        try:
            self.maxslider.setValue(1000*(self.axis.hi-self.axis.lo)/range)
        except ZeroDivisionError, OverflowError:
            self.maxslider.setValue(0)
        if self.name == 'x' or self.name == 'y':
            self.plot.replot_axes()
        else:
            self.plot.plot2D()
        self.block_signals(False)

    def read_maxslider(self):
        self.block_signals(True)
        self.axis.lo = self.minbox.value()
        range = max(self.maxbox.data[-1]-self.axis.lo, self.axis.min_range)
        self.axis.hi = self.axis.lo + (self.maxslider.value() * range / 1000)
        self.maxbox.setValue(self.axis.hi)
        range = max(self.axis.hi - self.minbox.data[0], self.axis.min_range)
        try:
            self.minslider.setValue(1000*(self.axis.lo-self.minbox.data[0])/range)
        except ZeroDivisionError, OverflowError:
            self.minslider.setValue(1000)
        if self.name == 'x' or self.name == 'y':
            self.plot.replot_axes()
        else:
            self.plot.plot2D()
        self.block_signals(False)

    def set_sliders(self, lo, hi):
        range = max(hi-self.minbox.data[0], self.axis.min_range)
        try:
            self.minslider.setValue(1000*(lo-self.minbox.data[0])/range)
        except ZeroDivisionError, OverflowError:
            self.minslider.setValue(1000)
        range = max(self.maxbox.data[-1]-lo, self.axis.min_range)
        try:
            self.maxslider.setValue(1000*(hi-lo)/range)
        except ZeroDivisionError, OverflowError:
            self.maxslider.setValue(0)

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
            self.axis.diff = hi - lo
        else:
            self.axis.locked = False
            self.axis.diff = None

    def set_autoscale(self):
        if self.scalebox.isChecked():
            self.plot.autoscale = True
        else:
            self.plot.autoscale = False

    def set_autoplot(self):
        if self.plotbox.isChecked():
            self.plot.autoplot = True
        else:
            self.plot.autoplot = False

    def replot(self):
        self.plot.plotdata = self.plot.data2D()
        self.plot.plot2D()

    def reset(self):
        self.axis.min = np.nanmin(self.axis.data)
        self.axis.max = np.nanmax(self.axis.data)
        self.minbox.set_data(self.axis.min, self.axis.max)
        self.maxbox.set_data(self.axis.min, self.axis.max)
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


class NXTextBox(QtGui.QLineEdit):

    def value(self):
        return float(unicode(self.text()))

    def setValue(self, value):
        self.setText(str(float('%.4g' % value)))

class NXSpinBox(QtGui.QSpinBox):

    def __init__(self, data=None):
        super(NXSpinBox, self).__init__()
        self.data = data
        self.data_locked = False
        self.validator = QtGui.QDoubleValidator()

    def value(self):
        return float(self.data[super(NXSpinBox, self).value()])

    def setValue(self, value):
        super(NXSpinBox, self).setValue(self.valueFromText(value))

    def valueFromText(self, text):
        try:
            value = float(unicode(text))
            if not self.data_locked:
                if value > self.data[-1]:
                    self.set_data(self.data[0], value)
                elif value < self.data[0]:
                    self.set_data(value, self.data[-1])
            return len(self.data[self.data<value])
        except IndexError:
            return self.maximum()

    def textFromValue(self, value):
        try:
            return str(float('%.4g' % self.data[value]))
        except:
            return ''
    
    def validate(self, input, pos):
        return self.validator.validate(input, pos)

    def set_data(self, min, max):
        if not self.data_locked:
            self.data = np.linspace(min, max, 201)

class NXProjectionTab(QtGui.QWidget):

    def __init__(self):

        super(NXProjectionTab, self).__init__()

        hbox = QtGui.QHBoxLayout()
        widgets = []

        self.xbox = QtGui.QComboBox()
        self.xbox.activated.connect(self.set_xaxis)
        widgets.append(QtGui.QLabel('X-Axis:'))
        widgets.append(self.xbox)

        self.ybox = QtGui.QComboBox()
        self.ybox.activated.connect(self.set_yaxis)
        self.ylabel = QtGui.QLabel('Y-Axis:')
        widgets.append(self.ylabel)
        widgets.append(self.ybox)

        self.plot_button = QtGui.QPushButton("Plot", self)
        self.plot_button.clicked.connect(self.plot_projection)
        widgets.append(self.plot_button)

        self.save_button = QtGui.QPushButton("Save", self)
        self.save_button.clicked.connect(self.save_projection)
        widgets.append(self.save_button)

        hbox.addStretch()
        for w in widgets:
            hbox.addWidget(w)
            hbox.setAlignment(w, QtCore.Qt.AlignVCenter)
        hbox.addStretch()
        
        self.setLayout(hbox)

    def get_axes(self):
        return plotview.xtab.get_axes()

    def set_axes(self):
        axes = self.get_axes()    
        self.xbox.clear()
        self.xbox.addItems(axes)
        self.xbox.setCurrentIndex(self.xbox.findText(plotview.mainplot.xaxis.name))
        self.xaxis = self.xbox.currentText()
        if plotview.mainplot.dims <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
            self.yaxis = 'None'
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0,'None')
            self.ybox.addItems(axes)
            self.ybox.setCurrentIndex(self.ybox.findText(plotview.mainplot.yaxis.name))
            self.yaxis = self.ybox.currentText()

    def set_xaxis(self):
        self.xaxis = self.xbox.currentText()

    def set_yaxis(self):
        self.yaxis = self.ybox.currentText()

    def save_projection(self):
        x = self.get_axes().index(self.xaxis)
        if self.yaxis == 'None':
            axis = [x]
        else:
            y = self.get_axes().index(self.yaxis)
            axis = [x,y]
        limits = [(plotview.mainplot.axis[name].lo, plotview.mainplot.axis[name].hi) 
                    for name in self.get_axes()]
        keep_data(plotview.mainplot.data.project(axis, limits))

    def plot_projection(self):
        x = self.get_axes().index(self.xaxis)
        if self.yaxis == 'None':
            axis = [x]
        else:
            y = self.get_axes().index(self.yaxis)
            axis = [x,y]
        limits = [(plotview.mainplot.axis[name].lo, plotview.mainplot.axis[name].hi) 
                    for name in self.get_axes()]
        plt.figure("Projection")
        plotview.mainplot.data.project(axis, limits).plot()


class NXNavigationToolbar(NavigationToolbar):

    def _init_toolbar(self):

        self.basedir = os.path.join(matplotlib.rcParams[ 'datapath' ],'images')

        a = self.addAction(self._icon('home.png'), 'Home', self.home)
        a.setToolTip('Reset original view')
        a = self.addAction(self._icon('back.png'), 'Back', self.back)
        a.setToolTip('Back to previous view')
        a = self.addAction(self._icon('forward.png'), 'Forward', self.forward)
        a.setToolTip('Forward to next view')
        self.addSeparator()
        a = self.addAction(self._icon('move.png'), 'Pan', self.pan)
        a.setToolTip('Pan axes with left mouse, zoom with right')
        a = self.addAction(self._icon('zoom_to_rect.png'), 'Zoom', self.zoom)
        a.setToolTip('Zoom to rectangle')
        self.addSeparator()

        a = self.addAction(self._icon("qt4_editor_options.png"),
                           'Customize', self.edit_parameters)
        a.setToolTip('Edit curves line and axes parameters')

        self.addSeparator()

        a = self.addAction(self._icon('filesave.png'), 'Save',
                self.save_figure)
        a.setToolTip('Save the figure')

        a = self.addAction(self._icon('hand.png'), 'Add',
                self.add_data)
        a.setToolTip('Add plot data to the tree')

        self.buttons = {}

        # Add the x,y location widget at the right side of the toolbar
        # The stretch factor is 1 which means any resizing of the toolbar
        # will resize this label instead of the buttons.
        if self.coordinates:
            self.locLabel = QtGui.QLabel( "", self )
            self.locLabel.setAlignment(
                    QtCore.Qt.AlignRight | QtCore.Qt.AlignTop )
            self.locLabel.setSizePolicy(
                QtGui.QSizePolicy(QtGui.QSizePolicy.Expanding,
                                  QtGui.QSizePolicy.Ignored))
            labelAction = self.addWidget(self.locLabel)
            labelAction.setVisible(True)

        # reference holder for subplots_adjust window
        self.adj_window = None

    if figureoptions is not None:
        def edit_parameters(self):
            allaxes = self.canvas.figure.get_axes()
            if len(allaxes) == 1:
                axes = allaxes[0]
            else:
                titles = []
                for axes in allaxes:
                    title = axes.get_title()
                    ylabel = axes.get_ylabel()
                    if title:
                        fmt = "%(title)s"
                        if ylabel:
                            fmt += ": %(ylabel)s"
                        fmt += " (%(axes_repr)s)"
                    elif ylabel:
                        fmt = "%(axes_repr)s (%(ylabel)s)"
                    else:
                        fmt = "%(axes_repr)s"
                    titles.append(fmt % dict(title = title,
                                         ylabel = ylabel,
                                         axes_repr = repr(axes)))
                item, ok = QtGui.QInputDialog.getItem(self, 'Customize',
                                                      'Select axes:', titles,
                                                      0, False)
                if ok:
                    axes = allaxes[titles.index(unicode(item))]
                else:
                    return

            figureoptions.figure_edit(axes, self)

    def home(*args):
        plotview.xtab.reset()
        plotview.ytab.reset()
        plotview.vtab.reset()

    def add_data(self):
        keep_data(plotview.mainplot.plotdata)

    def release_zoom(self, event):
        'the release mouse button callback in zoom to rect mode'
        for zoom_id in self._ids_zoom:
            self.canvas.mpl_disconnect(zoom_id)
        self._ids_zoom = []

        if not self._xypress: return

        last_a = []

        for cur_xypress in self._xypress:
            x, y = event.x, event.y
            lastx, lasty, a, ind, lim, trans = cur_xypress
            # ignore singular clicks - 5 pixels is a threshold
            if abs(x-lastx)<5 or abs(y-lasty)<5:
                self._xypress = None
                self.release(event)
                self.draw()
                return

            x0, y0, x1, y1 = lim.extents

            # zoom to rect
            inverse = a.transData.inverted()
            lastx, lasty = inverse.transform_point( (lastx, lasty) )
            x, y = inverse.transform_point( (x, y) )
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
                    plotview.xtab.set_limits(x0, x1)
                elif self._zoom_mode == "y":
                    a.set_ylim((y0, y1))
                    plotview.ytab.set_limits(y0, y1)
                else:
                    a.set_xlim((x0, x1))
                    a.set_ylim((y0, y1))
                    plotview.xtab.set_limits(x0, x1)
                    plotview.ytab.set_limits(y0, y1)
                plotview.tab_widget.setCurrentWidget(plotview.ptab)
            elif self._button_pressed == 3:
                if self._zoom_mode == "x":
                    plotview.xtab.set_limits(x0, x1)
                elif self._zoom_mode == "y":
                    plotview.ytab.set_limits(y0, y1)
                else:
                    plotview.xtab.set_limits(x0, x1)
                    plotview.ytab.set_limits(y0, y1)
                plotview.tab_widget.setCurrentWidget(plotview.ptab)

        self.draw()
        self._xypress = None
        self._button_pressed = None

        self._zoom_mode = None

        self.push_current()
        self.release(event)

    def _update_view(self):
         super(NXNavigationToolbar, self)._update_view()
         lims = self._views()
         if lims is None: return
         xmin, xmax, ymin, ymax = lims[0]
         plotview.xtab.axis.set_limits(xmin, xmax)
         plotview.xtab.minbox.setValue(xmin)
         plotview.xtab.maxbox.setValue(xmax)
         plotview.xtab.set_sliders(xmin, xmax)
         plotview.ytab.axis.set_limits(ymin, ymax)
         plotview.ytab.minbox.setValue(ymin)
         plotview.ytab.maxbox.setValue(ymax)
         plotview.ytab.set_sliders(ymin, ymax)

#    def set_cursor( self, cursor ):
#        pass


def keep_data(data):
    from nexpy.gui.consoleapp import _tree
    if 'w0' not in _tree.keys():
        scratch_space = _tree.add(NXroot(name='w0'))
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
