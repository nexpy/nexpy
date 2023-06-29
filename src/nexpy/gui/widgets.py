# -----------------------------------------------------------------------------
# Copyright (c) 2018-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
A set of customized widgets both for dialogs and plot objects.
"""
import math
import warnings

import numpy as np
from matplotlib import colors
from matplotlib.patches import Ellipse, Polygon, Rectangle

from .pyqt import QtCore, QtGui, QtWidgets
from .utils import (boundaries, find_nearest, format_float, get_color,
                    natural_sort, report_error)

warnings.filterwarnings("ignore", category=DeprecationWarning)

bold_font = QtGui.QFont()
bold_font.setBold(True)


class NXStack(QtWidgets.QWidget):
    """Widget containing a stack of widgets selected by a dropdown menu.

    Attributes
    ----------
    layout : QtWidgets.QVBoxLayout
        Layout of the entire stack.
    stack : QtWidgets.QStackedWidget
        Widget containing the stacked widgets.
    box : QtWidgets.QComboBox
        Pull-down menu containing the stack options.
    """

    def __init__(self, labels, widgets, parent=None):
        """Initialize the widget stack.

        Parameters
        ----------
        labels : list of str
            List of labels to be used in the QComboBox.
        widgets : list of QWidgets
            List of QWidgets to be stacked.
        parent : QObject, optional
            Parent of the NXStack instance (the default is None).
        """
        super().__init__(parent=parent)
        self.layout = QtWidgets.QVBoxLayout()
        self.stack = QtWidgets.QStackedWidget(self)
        self.widgets = dict(zip(labels, widgets))
        self.box = NXComboBox(slot=self.stack.setCurrentIndex, items=labels)
        for widget in widgets:
            self.stack.addWidget(widget)
        self.layout.addWidget(self.box)
        self.layout.addWidget(self.stack)
        self.layout.addStretch()
        self.setLayout(self.layout)

    def add(self, label, widget):
        """Add a widget to the stack.

        Parameters
        ----------
        label : str
            Label used to select the widget in the QComboBox
        widget : QtWidgets.QWidget
            Widget to be added to the stack
        """
        self.box.addItem(label)
        self.stack.addWidget(widget)

    def remove(self, label):
        if label in self.widgets:
            self.stack.removeWidget(self.widgets[label])
            del self.widgets[label]
        self.box.remove(label)


class NXSortModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super().__init__(parent=parent)

    def lessThan(self, left, right):
        try:
            left_text = self.sourceModel().itemFromIndex(left).text()
            right_text = self.sourceModel().itemFromIndex(right).text()
            return natural_sort(left_text) < natural_sort(right_text)
        except Exception:
            return True


class NXScrollArea(QtWidgets.QScrollArea):
    """Scroll area embedding a widget."""

    def __init__(self, content=None, horizontal=False, parent=None):
        """Initialize the scroll area.

        Parameters
        ----------
        content : QtWidgets.QWidget or QtWidgets.QLayout
            Widget or layout to be contained within the scroll area.
        horizontal : bool
            True if a horizontal scroll bar is enabled, default False.
        """
        super().__init__(parent=parent)
        if content:
            if isinstance(content, QtWidgets.QWidget):
                self.setWidget(content)
            elif isinstance(content, QtWidgets.QLayout):
                widget = QtWidgets.QWidget()
                widget.setLayout(content)
                self.setWidget(widget)
        if not horizontal:
            self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setWidgetResizable(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)

    def setWidget(self, widget):
        if isinstance(widget, QtWidgets.QLayout):
            w = QtWidgets.QWidget()
            w.setLayout(widget)
            widget = w
        super().setWidget(widget)
        widget.setMinimumWidth(widget.sizeHint().width() +
                               self.verticalScrollBar().sizeHint().width())


class NXLabel(QtWidgets.QLabel):
    """A text label.

    This is being subclassed from the PyQt QLabel class because of a bug in
    recent versions of PyQt5 (>11) that requires the box to be repainted
    after any programmatic changes.
    """

    def __init__(self, text=None, parent=None, bold=False, width=None,
                 align='left'):
        """Initialize the edit window and optionally set the alignment

        Parameters
        ----------
        text : str, optional
            The default text.
        parent : QWidget
            Parent of the NXLineEdit box.
        bold : bool, optional
            True if the label text is bold, default False.
        width : int, optional
            Fixed width of label.
        align : 'left', 'center', 'right'
            Alignment of text.
        """
        super().__init__(parent=parent)
        if text:
            self.setText(text)
        if bold:
            self.setFont(bold_font)
        if width:
            self.setFixedWidth(width)
        if align == 'left':
            self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        elif align == 'center':
            self.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        elif align == 'right':
            self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def setText(self, text):
        """Function to set the text in the box.

        Parameters
        ----------
        text : str
            Text to replace the text box contents.
        """
        super().setText(str(text))
        self.repaint()


class NXLineEdit(QtWidgets.QLineEdit):
    """An editable text box.

    This is being subclassed from the PyQt QLineEdit class because of a bug in
    recent versions of PyQt5 (>11) that requires the box to be repainted
    after any programmatic changes.
    """

    def __init__(self, text=None, parent=None, slot=None, readonly=False,
                 width=None, align='left'):
        """Initialize the edit window and optionally set the alignment

        Parameters
        ----------
        text : str, optional
            The default text.
        parent : QWidget
            Parent of the NXLineEdit box.
        slot: func, optional
            Slot to be used for editingFinished signals.
        right : bool, optional
            If True, make the box text right-aligned.
        """
        super().__init__(parent=parent)
        if slot:
            self.editingFinished.connect(slot)
        if text is not None:
            self.setText(text)
        if readonly:
            self.setReadOnly(True)
        if width:
            self.setFixedWidth(width)
        if align == 'left':
            self.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        elif align == 'center':
            self.setAlignment(QtCore.Qt.AlignHCenter | QtCore.Qt.AlignVCenter)
        elif align == 'right':
            self.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

    def setText(self, text):
        """Function to set the text in the box.

        Parameters
        ----------
        text : str
            Text to replace the text box contents.
        """
        super().setText(str(text))
        self.repaint()


class NXTextBox(NXLineEdit):
    """Subclass of NXLineEdit with floating point values."""

    def value(self):
        """Return the text box value as a floating point number.

        Returns
        -------
        float
            Value of text box converted to a floating point number
        """
        return float(str(self.text()))

    def setValue(self, value):
        """Set the value of the text box string formatted as a float.

        Parameters
        ----------
        value : str or int or float
            Text box value to be formatted as a float
        """
        self.setText(str(float(f'{value:.4g}')))


class NXPlainTextEdit(QtWidgets.QPlainTextEdit):
    """An editable text window."""

    def __init__(self, text=None, wrap=True, parent=None):
        super().__init__(parent=parent)
        self.setFont(QtGui.QFont('Courier'))
        if not wrap:
            self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        if text:
            self.setPlainText(text)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

    def __repr__(self):
        return 'NXPlainTextEdit()'

    def setPlainText(self, text):
        """Function to set the text in the window.

        Parameters
        ----------
        text : str
            Text to replace the text box contents.
        """
        super().setPlainText(str(text))
        self.repaint()

    def get_text(self, tab_spaces=4):
        """Return the text contained in the edit window.

        Parameters
        ----------
        tab_spaces : int, optional
            Number of spaces to replace tabs (default is 4). If set to 0, tab
            characters are not replaced.

        Returns
        -------
        str
            Current text in the edit window.
        """
        text = self.document().toPlainText().strip()
        if tab_spaces > 0:
            return text.replace('\t', tab_spaces*' ')
        else:
            return text + '\n'


class NXMessageBox(QtWidgets.QMessageBox):
    """A scrollable message box"""

    def __init__(self, title, text, *args, **kwargs):
        super().__init__(*args, **kwargs)
        scroll = NXScrollArea(parent=self)
        self.content = QtWidgets.QWidget()
        scroll.setWidget(self.content)
        scroll.setWidgetResizable(True)
        layout = QtWidgets.QVBoxLayout(self.content)
        layout.addWidget(NXLabel(title, bold=True))
        layout.addWidget(NXLabel(text, self))
        self.layout().addWidget(scroll, 0, 0, 1, self.layout().columnCount())
        self.setStyleSheet("QScrollArea{min-width:300 px; min-height: 400px}")


class NXComboBox(QtWidgets.QComboBox):
    """Dropdown menu for selecting a set of options."""

    def __init__(self, slot=None, items=[], default=None):
        """Initialize the dropdown menu with an initial list of items

        Parameters
        ----------
        slot : func, optional
            A function to be called when a selection is made
        items : list of str, optional
            A list of options to initialize the dropdown menu
        default : str, optional
            The option to be set as default when the menu is initialized
        """
        super().__init__()
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumWidth(80)
        if items:
            self.addItems([str(item) for item in items])
            if default:
                self.setCurrentIndex(self.findText(default))
        if slot:
            self.activated.connect(slot)

    def __iter__(self):
        """Implement key iteration."""
        return self.items().__iter__()

    def __next__(self):
        """Implements key iteration."""
        return self.items().__next__()

    def __contains__(self, item):
        """True if the item is one of the options."""
        return item in self.items()

    def keyPressEvent(self, event):
        """Function to enable the use of cursor keys to make selections.

        `Up` and `Down` keys are used to select options in the dropdown menu.
        `Left` and `Right` keys ar used to expand the dropdown menu to
        display the options.

        Parameters
        ----------
        event : QtCore.QEvent
            Keypress event that triggered the function.
        """
        if (event.key() == QtCore.Qt.Key_Up or
                event.key() == QtCore.Qt.Key_Down):
            super().keyPressEvent(event)
        elif (event.key() == QtCore.Qt.Key_Right or
              event.key() == QtCore.Qt.Key_Left):
            self.showPopup()
        else:
            self.parent().keyPressEvent(event)

    def findText(self, value, **kwargs):
        """Function to return the index of a text value.

        This is needed since h5py now returns byte strings, which will trigger
        ValueErrors unless they are converted to unicode strings.

        Parameters
        ----------
        value :
            Searched value.

        Returns
        -------
        int
            Index of the searched value.
        """
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        return super().findText(str(value), **kwargs)

    def add(self, *items):
        """Add items to the list of options.

        Parameters
        ----------
        *items : list of str
            List of options to be added to the dropdown menu.
        """
        for item in items:
            if item not in self:
                self.addItem(str(item))

    def insert(self, idx, item):
        """Insert item at the specified index.

        Parameters
        ----------
        item : str or int
            List of options to be added to the dropdown menu.
        idx : int
            Index of position before which to insert item
        """
        if item not in self:
            self.insertItem(idx, str(item))

    def remove(self, item):
        """Remove item from the list of options.

        Parameters
        ----------
        item : str or int
            Option to be removed from the dropdown menu.
        """
        if str(item) in self:
            self.removeItem(self.findText(str(item)))

    def items(self):
        """Return a list of the dropdown menu options.

        Returns
        -------
        list of str
            The options currently listed in the dropdown menu
        """
        return [self.itemText(idx) for idx in range(self.count())]

    def sort(self):
        """Sorts the box items in alphabetical order."""
        self.model().sort(0)

    def select(self, item):
        """Select the option matching the text.

        Parameters
        ----------
        item : str
            The option to be selected in the dropdown menu.
        """
        self.setCurrentIndex(self.findText(str(item)))
        self.repaint()

    @property
    def selected(self):
        """Return the currently selected option.

        Returns
        -------
        str
            Currently selected option in the dropdown menu.
        """
        return self.currentText()


class NXCheckBox(QtWidgets.QCheckBox):
    """A checkbox with associated label and slot function."""

    def __init__(self, label=None, slot=None, checked=False):
        """Initialize the checkbox.

        Parameters
        ----------
        label : str, optional
            Text describing the checkbox.
        slot : func, optional
            Function to be called when the checkbox state is changed.
        checked : bool, optional
            Initial checkbox state (the default is False).
        """
        super().__init__(label)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setChecked(checked)
        if slot:
            self.stateChanged.connect(slot)

    def keyPressEvent(self, event):
        """Function to enable the use of cursor keys to change the state.

        `Up` and `Down` keys are used to toggle the checkbox state.

        Parameters
        ----------
        event : QtCore.QEvent
            Keypress event that triggered the function.
        """
        if (event.key() == QtCore.Qt.Key_Up or
                event.key() == QtCore.Qt.Key_Down):
            if self.isChecked():
                self.setCheckState(QtCore.Qt.Unchecked)
            else:
                self.setCheckState(QtCore.Qt.Checked)
        else:
            self.parent().keyPressEvent(event)


class NXPushButton(QtWidgets.QPushButton):
    """A button with associated label and slot function."""

    def __init__(self, label, slot, checkable=False, width=None, parent=None):
        """Initialize button

        Parameters
        ----------
        label : str
            Text describing the button
        slot : func
            Function to be called when the button is pressed
        parent : QObject, optional
            Parent of button.
        """
        super().__init__(label, parent=parent)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setDefault(False)
        self.setAutoDefault(False)
        self.clicked.connect(slot)
        if checkable:
            self.setCheckable(True)
        if width:
            self.setFixedWidth(width)

    def keyPressEvent(self, event):
        """Function to enable the use of keys to press the button.

        `Return`, Enter`, and `Space` keys activate the slot function.

        Parameters
        ----------
        event : QtCore.QEvent
            Keypress event that triggered the function.
        """
        if (event.key() == QtCore.Qt.Key_Return or
            event.key() == QtCore.Qt.Key_Enter or
                event.key() == QtCore.Qt.Key_Space):
            self.clicked.emit()
        else:
            self.parent().keyPressEvent(event)


class NXColorButton(QtWidgets.QPushButton):
    """Push button for selecting colors."""

    colorChanged = QtCore.Signal(QtGui.QColor)

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.setFixedWidth(18)
        self.setStyleSheet("width:18px; height:18px; "
                           "margin: 0px; border: 0px; padding: 0px;"
                           "background-color: white")
        self.setIconSize(QtCore.QSize(12, 12))
        self.clicked.connect(self.choose_color)
        self._color = QtGui.QColor()

    def choose_color(self):
        color = QtWidgets.QColorDialog.getColor(self._color,
                                                self.parentWidget())
        if color.isValid():
            self.set_color(color)

    def get_color(self):
        return self._color

    @QtCore.Slot(QtGui.QColor)
    def set_color(self, color):
        if color != self._color:
            self._color = color
            self.colorChanged.emit(self._color)
            pixmap = QtGui.QPixmap(self.iconSize())
            pixmap.fill(color)
            self.setIcon(QtGui.QIcon(pixmap))
            self.repaint()

    color = QtCore.Property(QtGui.QColor, get_color, set_color)


class NXColorBox(QtWidgets.QWidget):
    """Text box and color square for selecting colors.

    This utilizes the ColorButton class in the formlayout package.

    Attributes
    ----------
    layout : QHBoxLayout
        Layout containing the text and color boxes.
    box : NXLineEdit
        Text box containing the string representation of the color.
    button : QPushButton
        Color button consisting of a colored icon.
    """

    def __init__(self, color='#ffffff', label=None, width=None, parent=None):
        """Initialize the text and color box.

        The selected color can be changed by entering a valid text string or
        by selecting the color using the standard system GUI.

        Valid text strings are HTML hex strings or standard Matplotlib colors.

        Parameters
        ----------
        color : str, optional
            Initial color (the default is '#ffffff', which represents 'white')
        parent : QObject, optional
            Parent of the color box.
        """
        super().__init__(parent=parent)
        self.color_text = get_color(color)
        color = self.qcolor(self.color_text)
        self.layout = QtWidgets.QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        if label:
            self.layout.addStretch()
            self.layout.addWidget(NXLabel(label))
        self.textbox = NXLineEdit(self.color_text,
                                  parent=parent, slot=self.update_color,
                                  width=width, align='right')
        self.layout.addWidget(self.textbox)
        self.button = NXColorButton(parent=parent)
        self.button.color = color
        self.button.colorChanged.connect(self.update_text)
        self.layout.addWidget(self.button)
        self.setLayout(self.layout)
        self.update_color()

    def update_color(self):
        """Set the button color following a change to the text box."""
        try:
            color = self.qcolor(get_color(self.textbox.text()))
            if color.isValid():
                self.button.color = color
                self.color_text = self.textbox.text()
        except ValueError as error:
            report_error("Invalid color", error)
            self.textbox.setText(self.color_text)

    def update_text(self, color):
        """Set the text box string following a change to the color button."""
        self.color_text = colors.to_hex(color.getRgbF())
        self.textbox.setText(self.color_text)

    def qcolor(self, text):
        """Create a QColor from a Matplotlib color."""
        qcolor = QtGui.QColor()
        text = get_color(text)
        if text.startswith('#') and len(text) == 7:
            correct = '#0123456789abcdef'
            for char in text:
                if char.lower() not in correct:
                    return qcolor
        elif text not in list(QtGui.QColor.colorNames()):
            return qcolor
        qcolor.setNamedColor(text)
        return qcolor


class NXSpinBox(QtWidgets.QSpinBox):
    """Subclass of QSpinBox with floating values.

    Parameters
    ----------
    slot : function
        PyQt slot triggered by changing values
    data : array-like, optional
        Values of data to be adjusted by the spin box.

    Attributes
    ----------
    data : array-like
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

    def __init__(self, slot=None, data=None):
        super().__init__()
        self.data = data
        self.validator = QtGui.QDoubleValidator()
        self.old_value = None
        self.diff = None
        self.pause = False
        if slot:
            self.valueChanged.connect(slot)
            self.editingFinished.connect(slot)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.setFixedWidth(100)
        self.setKeyboardTracking(False)
        self.setAccelerated(False)
        self.app = QtWidgets.QApplication.instance()

    def value(self):
        """Return the value of the spin box.

        Returns
        -------
        float
            Floating point number defined by the spin box value
        """
        if self.data is not None:
            return float(self.centers[self.index])
        else:
            return 0.0

    @property
    def centers(self):
        """The values of the data points based on bin centers.

        Returns
        -------
        array-like
            Data points set by the spin box
        """
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
        """Return the current index of the spin box."""
        return super().value()

    @property
    def reversed(self):
        """Return `True` if the data are in reverse order."""
        if self.data[-1] < self.data[0]:
            return True
        else:
            return False

    def setValue(self, value):
        super().setValue(self.valueFromText(value))
        self.repaint()

    def valueFromText(self, text):
        return self.indexFromValue(float(str(text)))

    def textFromValue(self, value):
        try:
            return format_float(float(f'{self.centers[value]:.4g}'))
        except Exception:
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
                super().stepBy(steps)
            else:
                self.pause = True

    def timerEvent(self, event):
        self.app.processEvents()
        if self.app.mouseButtons() & QtCore.Qt.LeftButton:
            super().timerEvent(event)


class NXDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """Subclass of QDoubleSpinBox.

    Parameters
    ----------
    slot : function
        PyQt slot triggered by changing values

    Attributes
    ----------
    validator : QDoubleValidator
        Function to ensure only floating point values are entered.
    old_value : float
        Previously stored value.
    diff : float
        Difference between maximum and minimum values when the box is
        locked.
    """

    def __init__(self, slot=None, editing=None):
        super().__init__()
        self.validator = QtGui.QDoubleValidator()
        self.validator.setRange(-np.inf, np.inf)
        self.validator.setDecimals(1000)
        self.old_value = None
        self.diff = None
        if slot and editing:
            self.valueChanged.connect(slot)
            self.editingFinished.connect(editing)
        elif slot:
            self.valueChanged.connect(slot)
            self.editingFinished.connect(slot)
        self.setAlignment(QtCore.Qt.AlignRight)
        self.setFixedWidth(100)
        self.setKeyboardTracking(False)
        self.setDecimals(2)
        self.steps = np.array([1, 2, 5, 10])
        self.app = QtWidgets.QApplication.instance()

    def validate(self, input_value, position):
        return self.validator.validate(input_value, position)

    def setSingleStep(self, value):
        value = abs(value)
        if value == 0:
            stepsize = 0.01
        else:
            digits = math.floor(math.log10(value))
            multiplier = 10**digits
            stepsize = find_nearest(self.steps, value/multiplier) * multiplier
        super().setSingleStep(stepsize)

    def stepBy(self, steps):
        if self.diff:
            self.setValue(self.value() + steps * self.diff)
        else:
            super().stepBy(steps)
        self.old_value = self.text()

    def valueFromText(self, text):
        value = float(text)
        if value > self.maximum():
            self.setMaximum(value)
        elif value < self.minimum():
            self.setMinimum(value)
        return value

    def textFromValue(self, value):
        if value > 1e6:
            return format_float(value)
        else:
            return format_float(value, width=8)

    def setValue(self, value):
        if value == 0:
            self.setDecimals(2)
        else:
            digits = math.floor(math.log10(abs(value)))
            if digits < 0:
                self.setDecimals(-digits)
            else:
                self.setDecimals(2)
        if value > self.maximum():
            self.setMaximum(value)
        elif value < self.minimum():
            self.setMinimum(value)
        super().setValue(value)
        self.repaint()

    def timerEvent(self, event):
        self.app.processEvents()
        if self.app.mouseButtons() & QtCore.Qt.LeftButton:
            super().timerEvent(event)


class NXSlider(QtWidgets.QSlider):
    """Subclass of QSlider.

    Parameters
    ----------
    slot : function
        PyQt slot triggered by changing values
    move : bool
        True if the slot is triggered by moving the slider. Otherwise,
        it is only triggered on release.
    """

    def __init__(self, slot=None, move=True, inverse=False):
        super().__init__(QtCore.Qt.Horizontal)
        self.setFocusPolicy(QtCore.Qt.NoFocus)
        self.setMinimumWidth(100)
        self.setRange(0, 100)
        self.setSingleStep(5)
        self.setTracking(True)
        self.inverse = inverse
        if self.inverse:
            self.setInvertedAppearance(True)
            self.setValue(100)
        else:
            self.setInvertedAppearance(False)
            self.setValue(0)
        if slot:
            self.sliderReleased.connect(slot)
            if move:
                self.sliderMoved.connect(slot)

    def value(self):
        _value = super().value()
        if self.inverse:
            return self.maximum() - _value
        else:
            return _value

    def setValue(self, value):
        if self.inverse:
            super().setValue(self.maximum() - int(value))
        else:
            super().setValue(int(value))


class NXpatch:
    """Class for a draggable shape on the NXPlotView canvas."""
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
        self.plotview.ax.add_patch(self.shape)

    def __getattr__(self, name):
        """Return Matplotlib attributes if not defined in the class."""
        return getattr(self.shape, name)

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
        contains, _ = self.shape.contains(event)
        if contains:
            return True
        else:
            return False

    def initialize(self, xp, yp):
        """Function to be overridden by shape sub-class."""

    def update(self, x, y):
        """Function to be overridden by shape sub-class."""

    def on_press(self, event):
        """Store coordinates on button press if over the object."""
        if not self.is_inside(event):
            self.press = None
            return
        self.press = self.initialize(event.xdata, event.ydata)
        self.canvas.draw()

    def on_motion(self, event):
        """Move the object if motion activated over the object."""
        if self.press is None:
            return
        if event.inaxes != self.shape.axes:
            return
        self.update(event.xdata, event.ydata)
        self.canvas.draw()

    def on_release(self, event):
        """Reset the data when the button is released."""
        if self.press is None:
            return
        self.press = None
        self.canvas.draw()

    def disconnect(self):
        """Disconnect all the stored connection ids."""
        self.canvas.mpl_disconnect(self.cidpress)
        self.canvas.mpl_disconnect(self.cidrelease)
        self.canvas.mpl_disconnect(self.cidmotion)
        self.plotview.activate()

    def remove(self):
        if self in self.plotview.shapes:
            self.plotview.shapes.remove(self)
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

    def set_linestyle(self, linestyle):
        self.shape.set_linestyle(linestyle)
        self.plotview.draw()

    def set_linewidth(self, linewidth):
        self.shape.set_linewidth(linewidth)
        self.plotview.draw()


class NXcircle(NXpatch):

    def __init__(self, x, y, r, border_tol=0.1, resize=True, plotview=None,
                 **opts):
        x, y, r = float(x), float(y), float(r)
        shape = Ellipse((x, y), 2*r, 2*r, **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'color' not in opts and 'facecolor' not in opts:
            shape.set_facecolor('r')
        super().__init__(shape, border_tol, resize, plotview)
        self.shape.set_label('Circle')
        self.circle = self.shape
        self.circle.height = self.height

    def __repr__(self):
        x, y = self.circle.center
        r = abs(self.circle.width) / 2
        return f'NXcircle({x:g}, {y:g}, {r:g})'

    @property
    def transform(self):
        return self.plotview.ax.transData.transform

    @property
    def inverse_transform(self):
        return self.plotview.ax.transData.inverted().transform

    @property
    def center(self):
        return self.circle.center

    @property
    def radius(self):
        return abs(self.circle.width) / 2.0

    @property
    def width(self):
        return abs(self.circle.width)

    @property
    def height(self):
        return 2 * (self.inverse_transform((0, self.pixel_radius)) -
                    self.inverse_transform((0, 0)))[1]

    @property
    def pixel_radius(self):
        return (self.transform((self.radius, 0)) - self.transform((0, 0)))[0]

    def pixel_shift(self, x, y, x0, y0):
        return tuple(self.transform((x, y)) - self.transform((x0, y0)))

    def radius_shift(self, x, y, xp, yp, x0, y0):
        xt, yt = self.pixel_shift(x, y, x0, y0)
        r = np.sqrt(xt**2 + yt**2)
        xt, yt = self.pixel_shift(xp, yp, x0, y0)
        r0 = np.sqrt(xt**2 + yt**2)
        return (self.inverse_transform((r, 0)) -
                self.inverse_transform((r0, 0)))[0]

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
        xt, yt = self.pixel_shift(xp, yp, x0, y0)
        rt = self.pixel_radius
        if (self.allow_resize and
                (np.sqrt(xt**2 + yt**2) > rt * (1-self.border_tol))):
            expand = True
        else:
            expand = False
        return x0, y0, w0, h0, xp, yp, expand

    def update(self, x, y):
        x0, y0, w0, h0, xp, yp, expand = self.press
        if expand:
            self.circle.width = self.width + \
                self.radius_shift(x, y, xp, yp, x0, y0)
            self.circle.height = self.height
        else:
            self.circle.center = (x0+x-xp, y0+y-yp)


class NXellipse(NXpatch):

    def __init__(self, x, y, dx, dy, border_tol=0.2, resize=True,
                 plotview=None, **opts):
        shape = Ellipse((float(x), float(y)), dx, dy, **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'color' not in opts and 'facecolor' not in opts:
            shape.set_facecolor('r')
        super().__init__(shape, border_tol, resize, plotview)
        self.shape.set_label('Ellipse')
        self.ellipse = self.shape

    def __repr__(self):
        x, y = self.ellipse.center
        w, h = self.ellipse.width, self.ellipse.height
        return f'NXellipse({x:g}, {y:g}, {w:g}, {h:g})'

    @property
    def center(self):
        return self.ellipse.center

    @property
    def width(self):
        return self.ellipse.width

    @property
    def height(self):
        return self.ellipse.height

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
            ((abs(x0-xp) < bt*w0 and
              abs(y0+np.true_divide(h0, 2)-yp) < bt*h0) or
             (abs(x0-xp) < bt*w0
              and abs(y0-np.true_divide(h0, 2)-yp) < bt*h0) or
             (abs(y0-yp) < bt*h0
              and abs(x0+np.true_divide(w0, 2)-xp) < bt*w0) or
             (abs(y0-yp) < bt*h0
              and abs(x0-np.true_divide(w0, 2)-xp) < bt*w0))):
            expand = True
        else:
            expand = False
        return x0, y0, w0, h0, xp, yp, expand

    def update(self, x, y):
        x0, y0, w0, h0, xp, yp, expand = self.press
        dx, dy = (x-xp, y-yp)
        bt = self.border_tol
        if expand:
            if (abs(x0-xp) < bt*w0
                    and abs(y0+np.true_divide(h0, 2)-yp) < bt*h0):
                self.ellipse.height = h0 + dy
            elif (abs(x0-xp) < bt*w0
                    and abs(y0-np.true_divide(h0, 2)-yp) < bt*h0):
                self.ellipse.height = h0 - dy
            elif (abs(y0-yp) < bt*h0
                    and abs(x0+np.true_divide(w0, 2)-xp) < bt*w0):
                self.ellipse.width = w0 + dx
            elif (abs(y0-yp) < bt*h0
                    and abs(x0-np.true_divide(w0, 2)-xp) < bt*w0):
                self.ellipse.width = w0 - dx
        else:
            self.ellipse.set_center((x0+dx, y0+dy))


class NXrectangle(NXpatch):

    def __init__(self, x, y, dx, dy, border_tol=0.1, resize=True,
                 plotview=None, **opts):
        shape = Rectangle((float(x), float(y)), float(dx), float(dy), **opts)
        if 'linewidth' not in opts:
            shape.set_linewidth(1.0)
        if 'color' not in opts and 'facecolor' not in opts:
            shape.set_facecolor('r')
        super().__init__(shape, border_tol, resize, plotview)
        self.shape.set_label('Rectangle')
        self.rectangle = self.shape

    def __repr__(self):
        x, y = self.rectangle.xy
        w, h = self.rectangle.get_width(), self.rectangle.get_height()
        return f'NXrectangle({x:g}, {y:g}, {w:g}, {h:g})'

    @property
    def width(self):
        return self.rectangle.get_width()

    @property
    def height(self):
        return self.rectangle.get_height()

    @property
    def xy(self):
        return self.rectangle.xy

    def set_bounds(self, x, y, dx, dy):
        self.rectangle.set_bounds(x, y, dx, dy)
        self.plotview.draw()

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
            (abs(x0+np.true_divide(w0, 2)-xp) > np.true_divide(w0, 2)-bt*w0 or
             abs(y0+np.true_divide(h0, 2)-yp) > np.true_divide(h0, 2)-bt*h0)):
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
        if 'color' not in opts and 'facecolor' not in opts:
            shape.set_facecolor('r')
        super().__init__(shape, resize=False, plotview=plotview)
        self.shape.set_label('Polygon')
        self.polygon = self.shape

    def __repr__(self):
        xy = self.polygon.xy
        v = xy.shape[0] - 1
        return f'NXpolygon({xy[0][0]:g}, {xy[0][1]:g}, vertices={v})'

    @property
    def xy(self):
        return self.polygon.xy

    def initialize(self, xp, yp):
        xy0 = self.polygon.xy
        return xy0, xp, yp

    def update(self, x, y):
        xy0, xp, yp = self.press
        dxy = (x-xp, y-yp)
        self.polygon.set_xy(xy0+dxy)
