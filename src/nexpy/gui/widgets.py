# -*- coding: utf-8 -*-
"""
This module contains a set of customized widgets both for dialogs and plot objects. 
"""
from __future__ import (absolute_import, division, unicode_literals)
import six

from .pyqt import QtCore, QtGui, QtWidgets

import numpy as np
import warnings

import matplotlib as mpl
from matplotlib.cbook import mplDeprecation
from matplotlib.patches import Circle, Ellipse, Rectangle, Polygon
try:
    from formlayout import ColorLayout, text_to_qcolor
except ImportError:
    from matplotlib.backends.qt_editor.formlayout import (ColorLayout,
                                                          to_qcolor as text_to_qcolor)

warnings.filterwarnings("ignore", category=mplDeprecation)

from .utils import get_color, boundaries


class NXStack(QtWidgets.QWidget):
    """Widget containing a stack of widgets selected by a QComboBox"""
    def __init__(self, labels, widgets, parent=None):
        super(NXStack, self).__init__(parent=parent)
        self.layout = QtWidgets.QVBoxLayout()
        self.stack = QtWidgets.QStackedWidget(self)
        self.box = NXComboBox(slot=self.stack.setCurrentIndex, items=labels)
        for widget in widgets:
            self.stack.addWidget(widget)
        self.layout.addWidget(self.box)
        self.layout.addWidget(self.stack)
        self.setLayout(self.layout)

    def add(self, label, widget):
        self.box.addItem(label)
        self.stack.addWidget(widget)


class NXTextBox(QtWidgets.QLineEdit):
    """Subclass of QLineEdit with floating values."""
    def value(self):
        return float(six.text_type(self.text()))

    def setValue(self, value):
        self.setText(six.text_type(float('%.4g' % value)))


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

    def add(self, *items):
        for item in items:
            self.addItem(item)

    def select(self, item):
        self.setCurrentIndex(self.findText(item))

    @property
    def selected(self):
        return self.currentText()


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


class NXColorBox(QtWidgets.QWidget):

    def __init__(self, color='#ffffff', parent=None):
        super(NXColorBox, self).__init__(parent)
        color = text_to_qcolor(color)
        self.layout = ColorLayout(color)
        self.layout.setContentsMargins(0,0,0,0)
        self.box = self.layout.lineedit
        self.box.editingFinished.connect(self.update_color)
        self.button = self.layout.colorbtn
        self.button.colorChanged.connect(self.update_text)
        self.setLayout(self.layout)
        self.update_color()

    def update_color(self):
        color = text_to_qcolor(get_color(self.box.text()))
        if color.isValid():
            self.button.color = color

    def update_text(self, color):
        self.box.setText(mpl.colors.to_hex(color.getRgbF()))


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


class NXpatch(object):
    """Class for a draggable shape on the NXPlotView canvas"""
    lock = None
     
    def __init__(self, shape, border_tol=0.1, resize=True, plotview=None):
        if plotview:
            self.plotview = plotview
        else:
            from .plotview import get_plotview
            self.plotview = get_plotview()
        self.canvas = self.plotview.canvas
        self.shape = shape
        self.border_tol = border_tol
        self.press = None
        self.background = None
        self.allow_resize = resize
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

    def remove(self):
        self.shape.remove()
        self.plotview.draw()

    def set_facecolor(self, color):
        self.shape.set_facecolor(color)
        self.plotview.draw()

    def set_edgecolor(self, color):
        self.shape.set_edgecolor(color)
        self.plotview.draw()

    def set_color(self, color):
        self.shape.set_facecolor(color)
        self.shape.set_edgecolor(color)
        self.plotview.draw()

    def set_alpha(self, alpha):
        self.shape.set_alpha(alpha)
        self.plotview.draw()


class NXcircle(NXpatch):

    def __init__(self, x, y, r, border_tol=0.1, resize=True, plotview=None, **opts):
        x, y, r = float(x), float(y), float(r)
        shape = Ellipse((x,y), r, r, **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'facecolor' not in opts:
            shape.set_facecolor('r')
        super(NXcircle, self).__init__(shape, border_tol, resize, plotview)
        self.shape.set_label('Circle')
        self.circle = self.shape
        self.circle.height = self.height

    def __repr__(self):
        x, y = self.circle.center
        r = abs(self.circle.width) / 2
        return 'NXcircle(%g, %g, %g)' % (x, y, r)

    @property
    def transform(self):
        return self.plotview.ax.transData.transform

    @property
    def inverse_transform(self):
        return self.plotview.ax.transData.inverted().transform

    @property
    def radius(self):
        return abs(self.circle.width) / 2.0

    @property
    def pixel_radius(self):
        return (self.transform((self.radius,0)) - self.transform((0,0)))[0]

    def pixel_shift(self, x, y, x0, y0):
        return tuple(self.transform((x,y)) - self.transform((x0,y0)))

    def radius_shift(self, x, y, xp, yp, x0, y0):
        xt, yt = self.pixel_shift(x, y, x0, y0)
        r = np.sqrt(xt**2 + yt**2)
        xt, yt = self.pixel_shift(xp, yp, x0, y0)
        r0 = np.sqrt(xt**2 + yt**2)
        return (self.inverse_transform((r,0)) - self.inverse_transform((r0,0)))[0]
    
    @property
    def width(self):
        return abs(self.circle.width)

    @property
    def height(self):
        return 2 * (self.inverse_transform((0,self.pixel_radius)) - 
                    self.inverse_transform((0,0)))[1]

    def set_center(self, x, y):
        self.circle.center = x, y
        self.plotview.draw()

    def set_radius(self, radius):
        self.circle.width = 2.0 * radius
        self.circle.height = self.height
        self.plotview.draw()

    def initialize(self, xp, yp):
        x0, y0 = self.circle.center
        w0, h0 = self.width, self.height
        xt, yt, rt = *self.pixel_shift(xp, yp, x0, y0), self.pixel_radius
        if (self.allow_resize and
            (np.sqrt(xt**2 + yt**2) > rt * (1-self.border_tol))):
            expand = True
        else:
            expand = False
        return x0, y0, w0, h0, xp, yp, expand   

    def update(self, x, y):
        x0, y0, w0, h0, xp, yp, expand = self.press
        if expand:
            self.circle.width = self.width + self.radius_shift(x, y, xp, yp, x0, y0)
            self.circle.height = self.height
        else:
            self.circle.center = (x0+x-xp, y0+y-yp)


class NXellipse(NXpatch):

    def __init__(self, x, y, dx, dy, border_tol=0.2, resize=True, plotview=None, **opts):
        shape = Ellipse((float(x),float(y)), dx, dy, **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'facecolor' not in opts:
            shape.set_facecolor('r')
        super(NXellipse, self).__init__(shape, border_tol, resize, plotview)
        self.shape.set_label('Ellipse')
        self.ellipse = self.shape

    def __repr__(self):
        x, y = self.ellipse.center
        w, h = self.ellipse.width, self.ellipse.height
        return 'NXellipse(%g, %g, %g, %g)' % (x, y, w, h)

    def set_center(self, x, y):
        self.ellipse.set_center((x, y))
        self.plotview.draw()

    def set_width(self, width):
        self.ellipse.width = width
        self.plotview.draw()

    def set_height(self, height):
        self.ellipse.height = height
        self.plotview.draw()

    def initialize(self, xp, yp):
        x0, y0 = self.ellipse.center
        w0, h0 = self.ellipse.width, self.ellipse.height
        bt = self.border_tol
        if (self.allow_resize and
            ((abs(x0-xp) < bt*w0 and abs(y0+np.true_divide(h0,2)-yp) < bt*h0) or
             (abs(x0-xp) < bt*w0 and abs(y0-np.true_divide(h0,2)-yp) < bt*h0) or
             (abs(y0-yp) < bt*h0 and abs(x0+np.true_divide(w0,2)-xp) < bt*w0) or
             (abs(y0-yp) < bt*h0 and abs(x0-np.true_divide(w0,2)-xp) < bt*w0))):
            expand = True
        else:
            expand = False
        return x0, y0, w0, h0, xp, yp, expand   

    def update(self, x, y):
        x0, y0, w0, h0, xp, yp, expand = self.press
        dx, dy = (x-xp, y-yp)
        bt = self.border_tol
        if expand:
            if (abs(x0-xp) < bt*w0 and abs(y0+np.true_divide(h0,2)-yp) < bt*h0):
                self.ellipse.height = h0 + dy
            elif (abs(x0-xp) < bt*w0 and abs(y0-np.true_divide(h0,2)-yp) < bt*h0):
                self.ellipse.height = h0 - dy
            elif (abs(y0-yp) < bt*h0 and abs(x0+np.true_divide(w0,2)-xp) < bt*w0):
                self.ellipse.width = w0 + dx
            elif (abs(y0-yp) < bt*h0 and abs(x0-np.true_divide(w0,2)-xp) < bt*w0):
                self.ellipse.width = w0 - dx
        else:
            self.ellipse.set_center((x0+dx, y0+dy))


class NXrectangle(NXpatch):

    def __init__(self, x, y, dx, dy, border_tol=0.1, resize=True, plotview=None, **opts):
        shape = Rectangle((float(x),float(y)), float(dx), float(dy), **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'facecolor' not in opts:
            shape.set_facecolor('r')
        super(NXrectangle, self).__init__(shape, border_tol, resize, plotview)
        self.shape.set_label('Rectangle')
        self.rectangle = self.shape

    def __repr__(self):
        x, y = self.rectangle.xy
        w, h = self.rectangle.get_width(), self.rectangle.get_height()
        return 'NXrectangle(%g, %g, %s, %s)' % (x, y, w, h)

    def set_left(self, left):
        self.rectangle.set_x(left)
        self.plotview.draw()

    def set_right(self, right):
        self.rectangle.set_x(right - self.rectangle.get_width())
        self.plotview.draw()

    def set_bottom(self, bottom):
        self.rectangle.set_y(bottom)
        self.plotview.draw()

    def set_top(self, top):
        self.rectangle.set_y(top - self.rectangle.get_height())
        self.plotview.draw()

    def set_width(self, width):
        self.rectangle.set_width(width)
        self.plotview.draw()

    def set_height(self, height):
        self.rectangle.set_height(height)
        self.plotview.draw()

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
            elif abs(x0 + w0 - xp) < bt * w0:
                self.rectangle.set_width(w0+dx)
            elif abs(y0 - yp) < bt * h0:
                self.rectangle.set_y(y0+dy)
                self.rectangle.set_height(h0-dy)
            elif abs(y0 + h0 - yp) < bt * h0:
                self.rectangle.set_height(h0+dy)
        else:
            self.rectangle.set_x(x0+dx)
            self.rectangle.set_y(y0+dy)


class NXpolygon(NXpatch):

    def __init__(self, xy, closed=True, plotview=None, **opts):
        shape = Polygon(xy, closed, **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'facecolor' not in opts:
            shape.set_facecolor('r')
        super(NXpolygon, self).__init__(shape, resize=False, plotview=plotview)
        self.shape.set_label('Polygon')
        self.polygon = self.shape

    def __repr__(self):
        xy = self.polygon.xy
        v = xy.shape[0] - 1
        return 'NXpolygon(%g, %g, vertices=%s)' % (xy[0][0], xy[0][1], v)

    def initialize(self, xp, yp):
        xy0 = self.polygon.xy
        return xy0, xp, yp 

    def update(self, x, y):
        xy0, xp, yp = self.press
        dxy = (x-xp, y-yp)        
        self.polygon.set_xy(xy0+dxy)

