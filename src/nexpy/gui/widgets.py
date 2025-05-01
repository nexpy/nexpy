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
import bisect
import math
import warnings
from operator import attrgetter
from pathlib import Path

import numpy as np
from matplotlib import colors
from matplotlib.patches import Ellipse, Polygon, Rectangle
from nexusformat.nexus import NeXusError, NXfield, NXroot

from .pyqt import QtCore, QtGui, QtWidgets, getOpenFileName
from .utils import (boundaries, confirm_action, display_message, find_nearest,
                    format_float, get_color, natural_sort, report_error)

warnings.filterwarnings("ignore", category=DeprecationWarning)

bold_font = QtGui.QFont()
bold_font.setBold(True)


class NXWidget(QtWidgets.QWidget):
    """Customized widget for NeXpy widgets"""

    def __init__(self, parent=None):

        from .consoleapp import _mainwindow
        self.mainwindow = _mainwindow
        if parent is None:
            parent = self.mainwindow
        super().__init__(parent=parent)
        self.set_attributes()

    def set_attributes(self):
        self.treeview = self.mainwindow.treeview
        self.tree = self.treeview.tree
        self.plotview = self.mainwindow.plotview
        self.plotviews = self.mainwindow.plotviews
        self.active_plotview = self.mainwindow.active_plotview
        self.default_directory = self.mainwindow.default_directory
        self.import_file = None     # must define in subclass
        self.nexus_filter = ';;'.join((
            "NeXus Files (*.nxs *.nx5 *.h5 *.hdf *.hdf5)",
            "Any Files (*.* *)"))
        self.textbox = {}
        self.pushbutton = {}
        self.checkbox = {}
        self.radiobutton = {}
        self.radiogroup = []
        self.mainwindow.radiogroup = self.radiogroup
        self.confirm_action = confirm_action
        self.display_message = display_message
        self.report_error = report_error
        self.thread = None
        self.bold_font = QtGui.QFont()
        self.bold_font.setBold(True)
        self.accepted = False

    def set_layout(self, *items, **opts):
        self.layout = QtWidgets.QVBoxLayout()
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                self.layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.addWidget(item)
            elif item == 'stretch':
                self.layout.addStretch()
        spacing = opts.pop('spacing', 10)
        self.layout.setSpacing(spacing)
        self.setLayout(self.layout)
        return self.layout

    def make_layout(self, *items, **opts):
        vertical = opts.pop('vertical', False)
        align = opts.pop('align', 'center')
        spacing = opts.pop('spacing', 20)
        if vertical:
            layout = QtWidgets.QVBoxLayout()
        else:
            layout = QtWidgets.QHBoxLayout()
            if align == 'center' or align == 'right':
                layout.addStretch()
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                layout.addWidget(item)
            elif item == 'stretch':
                layout.addStretch()
            elif isinstance(item, str):
                layout.addWidget(NXLabel(item))
        if not vertical:
            if align == 'center' or align == 'left':
                layout.addStretch()
        layout.setSpacing(spacing)
        return layout

    def add_layout(self, *items, stretch=False):
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                self.layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.addWidget(item)
            elif isinstance(item, str):
                self.layout.addWidget(NXLabel(item))
        if stretch:
            self.layout.addStretch()

    def insert_layout(self, index, *items):
        for item in reversed(list(items)):
            if isinstance(item, QtWidgets.QLayout):
                self.layout.insertLayout(index, item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.insertWidget(index, item)
            elif isinstance(item, str):
                self.layout.addWidget(NXLabel(item))

    def spacer(self, width=0, height=0):
        return QtWidgets.QSpacerItem(width, height)

    def widget(self, item):
        widget = QtWidgets.QWidget()
        widget.layout = QtWidgets.QVBoxLayout()
        if isinstance(item, QtWidgets.QLayout):
            widget.layout.addLayout(item)
        elif isinstance(item, QtWidgets.QWidget):
            widget.layout.addWidget(item)
        widget.setVisible(True)
        return widget

    def set_title(self, title):
        self.setWindowTitle(title)

    def close_layout(self, message=None, save=False, close=False,
                     progress=False):
        layout = QtWidgets.QHBoxLayout()
        self.status_message = NXLabel()
        if message:
            self.status_message.setText(message)
        layout.addWidget(self.status_message)
        if progress:
            self.progress_bar = QtWidgets.QProgressBar()
            layout.addWidget(self.progress_bar)
            self.progress_bar.setVisible(False)
        else:
            self.progress_bar = None
        layout.addStretch()
        layout.addWidget(self.close_buttons(save=save, close=close))
        return layout

    def action_buttons(self, *items):
        layout = QtWidgets.QHBoxLayout()
        layout.addStretch()
        for label, action in items:
            self.pushbutton[label] = NXPushButton(label, action)
            layout.addWidget(self.pushbutton[label])
            layout.addStretch()
        return layout

    def label(self, label, **opts):
        return NXLabel(str(label), **opts)

    def labels(self, *labels, **opts):
        if 'align' in opts:
            align = opts['align']
        else:
            align = 'center'
        layout = QtWidgets.QVBoxLayout()
        for label in labels:
            horizontal_layout = QtWidgets.QHBoxLayout()
            if align == 'center' or align == 'right':
                horizontal_layout.addStretch()
            label_widget = NXLabel(str(label))
            if 'header' in opts:
                label_widget.setFont(self.bold_font)
            horizontal_layout.addWidget(label_widget)
            if align == 'center' or align == 'left':
                horizontal_layout.addStretch()
            layout.addLayout(horizontal_layout)
        return layout

    def textboxes(self, *items, **opts):
        if 'layout' in opts and opts['layout'] == 'horizontal':
            layout = QtWidgets.QHBoxLayout()
        else:
            layout = QtWidgets.QVBoxLayout()
        for item in items:
            label, value = item
            item_layout = QtWidgets.QHBoxLayout()
            label_box = NXLabel(label)
            self.textbox[label] = NXLineEdit(value)
            item_layout.addWidget(label_box)
            item_layout.addWidget(self.textbox[label])
            layout.addLayout(item_layout)
        return layout

    def checkboxes(self, *items, **opts):
        if 'align' in opts:
            align = opts['align']
        else:
            align = 'center'
        if 'vertical' in opts and opts['vertical'] is True:
            layout = QtWidgets.QVBoxLayout()
        else:
            layout = QtWidgets.QHBoxLayout()
        if align != 'left':
            layout.addStretch()
        for label, text, checked in items:
            self.checkbox[label] = NXCheckBox(text)
            self.checkbox[label].setChecked(checked)
            layout.addWidget(self.checkbox[label])
            layout.addStretch()
        return layout

    def radiobuttons(self, *items, **opts):
        if 'align' in opts:
            align = opts['align']
        else:
            align = 'center'
        if 'vertical' in opts and opts['vertical'] is True:
            layout = QtWidgets.QVBoxLayout()
        else:
            layout = QtWidgets.QHBoxLayout()
        group = QtWidgets.QButtonGroup()
        if 'slot' in opts:
            group.buttonClicked.connect(opts['slot'])
        self.radiogroup.append(group)
        if align != 'left':
            layout.addStretch()
        for label, text, checked in items:
            self.radiobutton[label] = QtWidgets.QRadioButton(text)
            self.radiobutton[label].setChecked(checked)
            layout.addWidget(self.radiobutton[label])
            layout.addStretch()
            group.addButton(self.radiobutton[label])
        return layout

    def filebox(self, text="Choose File", slot=None):
        """
        Creates a text box and button for selecting a file.
        """
        if slot:
            self.filebutton = NXPushButton(text, slot)
        else:
            self.filebutton = NXPushButton(text, self.choose_file)
        self.filename = NXLineEdit(parent=self)
        self.filename.setMinimumWidth(300)
        filebox = QtWidgets.QHBoxLayout()
        filebox.addWidget(self.filebutton)
        filebox.addWidget(self.filename)
        return filebox

    def directorybox(self, text="Choose Directory", slot=None, default=True,
                     suggestion=None):
        """
        Creates a text box and button for selecting a directory.
        """
        if slot:
            self.directorybutton = NXPushButton(text, slot)
        else:
            self.directorybutton = NXPushButton(text, self.choose_directory)
        self.directoryname = NXLineEdit(parent=self)
        self.directoryname.setMinimumWidth(300)
        default_directory = self.get_default_directory(suggestion=suggestion)
        if default and default_directory:
            self.directoryname.setText(default_directory)
        directorybox = QtWidgets.QHBoxLayout()
        directorybox.addWidget(self.directorybutton)
        directorybox.addWidget(self.directoryname)
        return directorybox

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.filename.text())
        filename = Path(getOpenFileName(self, 'Open File', dirname))
        if filename.exists():
            self.filename.setText(str(filename))
            self.set_default_directory(filename.parent)

    def get_filename(self):
        """
        Returns the selected file.
        """
        return self.filename.text()

    def choose_directory(self):
        """Opens a file dialog and sets the directory text box to the path."""
        dirname = str(self.get_default_directory())
        dirname = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Directory', dirname)
        if Path(dirname).exists():  # avoids problems if <Cancel> was selected
            self.directoryname.setText(str(dirname))
            self.set_default_directory(dirname)

    def get_directory(self):
        """Return the selected directory."""
        return self.directoryname.text()

    def get_default_directory(self, suggestion=None):
        """Return the most recent default directory for open/save dialogs."""
        if suggestion is None or not Path(suggestion).exists():
            suggestion = self.default_directory
        suggestion = Path(suggestion)
        if suggestion.exists():
            if not suggestion.is_dir:
                suggestion = suggestion.parent
        suggestion = suggestion.resolve()
        return suggestion

    def set_default_directory(self, suggestion):
        """Defines the default directory to use for open/save dialogs."""
        suggestion = Path(suggestion)
        if suggestion.exists():
            if not suggestion.is_dir():
                suggestion = suggestion.parent
            self.default_directory = suggestion
            self.mainwindow.default_directory = self.default_directory

    def get_filesindirectory(self, prefix='', extension='.*', directory=None):
        """
        Returns a list of files in the selected directory.

        The files are sorted using a natural sort algorithm that preserves the
        numeric order when a file name consists of text and index so that,
        e.g., 'data2.tif' comes before 'data10.tif'.
        """
        if directory:
            directory = Path(directory)
        else:
            directory = Path(self.get_directory())
        if not extension.startswith('.'):
            extension = '.'+extension
        return sorted(directory.glob(prefix+'*'+extension), key=natural_sort)

    def select_box(self, choices, default=None, slot=None):
        box = NXComboBox()
        for choice in choices:
            box.add(choice)
        if default in choices:
            idx = box.findText(default)
            box.setCurrentIndex(idx)
        else:
            box.setCurrentIndex(0)
        if slot:
            box.currentIndexChanged.connect(slot)
        return box

    def select_root(self, slot=None, text='Select Root'):
        layout = QtWidgets.QHBoxLayout()
        if not self.tree.entries:
            raise NeXusError("No entries in the NeXus tree")
        self.root_box = NXComboBox(
            items=sorted(self.tree.entries, key=natural_sort))
        try:
            self.root_box.select(self.treeview.node.nxroot.nxname)
        except Exception:
            pass
        layout.addWidget(self.root_box)
        if slot:
            layout.addWidget(NXPushButton(text, slot))
        layout.addStretch()
        self.root_layout = layout
        return layout

    @property
    def root(self):
        return self.tree[self.root_box.currentText()]

    def select_entry(self, slot=None, text='Select Entry'):
        layout = QtWidgets.QHBoxLayout()
        if not self.tree.entries:
            raise NeXusError("No entries in the NeXus tree")
        self.root_box = NXComboBox(
            slot=self.switch_root,
            items=sorted(self.tree.entries, key=natural_sort))
        try:
            self.root_box.select(self.treeview.node.nxroot.nxname)
        except Exception:
            pass
        self.entry_box = NXComboBox(
            items=sorted(self.tree[self.root_box.selected].entries,
                         key=natural_sort))
        try:
            if not isinstance(self.treeview.node, NXroot):
                self.entry_box.select(self.treeview.node.nxentry.nxname)
        except Exception:
            pass
        self.data_box = None
        layout.addStretch()
        layout.addWidget(self.root_box)
        layout.addWidget(self.entry_box)
        if slot:
            layout.addWidget(NXPushButton(text, slot))
        layout.addStretch()
        self.entry_layout = layout
        return layout

    def switch_root(self):
        self.entry_box.clear()
        self.entry_box.add(*sorted(self.tree[self.root_box.selected].entries))
        if self.data_box:
            self.switch_entry()

    @property
    def entry(self):
        return self.tree[f"{self.root_box.selected}/{self.entry_box.selected}"]

    def select_data(self, slot=None, text='Select Data'):
        layout = QtWidgets.QHBoxLayout()
        if not self.tree.entries:
            raise NeXusError("No entries in the NeXus tree")
        self.root_box = NXComboBox(
            slot=self.switch_root,
            items=sorted(self.tree.entries, key=natural_sort))
        try:
            self.root_box.select(self.treeview.node.nxroot.nxname)
        except Exception:
            pass
        self.entry_box = NXComboBox(
            slot=self.switch_entry,
            items=sorted(self.tree[self.root_box.selected].entries,
                         key=natural_sort))
        try:
            if not isinstance(self.treeview.node, NXroot):
                self.entry_box.select(self.treeview.node.nxentry.nxname)
        except Exception:
            pass
        entry_path = Path(self.entry.nxpath)
        paths = []
        for node in self.entry.walk():
            if node.nxclass == 'NXdata':
                paths.append(str(Path(node.nxpath).relative_to(entry_path)))
        self.data_box = NXComboBox(items=sorted(paths, key=natural_sort))
        try:
            if not isinstance(self.treeview.node, NXroot):
                self.data_box.select(self.treeview.node.nxentry.nxname)
        except Exception:
            pass
        layout.addStretch()
        layout.addWidget(self.root_box)
        layout.addWidget(self.entry_box)
        layout.addWidget(self.data_box)
        if slot:
            layout.addWidget(NXPushButton(text, slot))
        layout.addStretch()
        self.entry_layout = layout
        return layout

    def switch_entry(self):
        self.data_box.clear()
        entry_path = Path(self.entry.nxpath)
        paths = []
        for node in self.entry.walk():
            if node.nxclass == 'NXdata':
                paths.append(str(Path(node.nxpath).relative_to(entry_path)))
        self.data_box.add(*sorted(paths, key=natural_sort))

    @property
    def selected_data(self):
        return self.tree[
            f"{self.root_box.selected}/{self.entry_box.selected}/"
            f"{self.data_box.selected}"]

    def read_parameter(self, root, path):
        """
        Read the value from the NeXus path.

        It will return 'None' if the path is not valid.
        """
        try:
            value = root[path].nxdata
            if isinstance(value, np.ndarray) and value.size == 1:
                return np.float32(value)
            else:
                return value
        except NeXusError:
            return None

    def parameter_stack(self, parameters, width=None):
        """Initialize layouts containing a grid selection box and each grid."""
        return NXStack([p for p in parameters],
                       [parameters[p].widget(header=False, width=width)
                        for p in parameters])

    def grid(self, rows, cols, headers=None, spacing=10):
        pass

    def hide_grid(self, grid):
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)

    def show_grid(self, grid):
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(True)

    def delete_grid(self, grid):
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)
                        grid.removeWidget(widget)
                        widget.deleteLater()
        grid.deleteLater()

    def start_progress(self, limits):
        start, stop = limits
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(start, stop)
            self.progress_bar.setValue(start)
            self.status_message.setVisible(False)

    def update_progress(self, value=None):
        """
        Call the main QApplication.processEvents

        This ensures that GUI items like progress bars get updated
        """
        if self.progress_bar and value is not None:
            self.progress_bar.setValue(value)
        self.mainwindow._app.processEvents()

    def stop_progress(self):
        if self.progress_bar:
            self.progress_bar.setVisible(False)
        self.status_message.setVisible(True)

    def progress_layout(self, save=False, close=False):
        return self.close_layout(save=save, close=close, progress=True)

    def get_node(self):
        """
        Return the node currently selected in the treeview
        """
        return self.treeview.get_node()

    def start_thread(self):
        if self.thread:
            self.stop_thread()
        self.thread = QtCore.QThread()
        return self.thread

    def stop_thread(self):
        if isinstance(self.thread, QtCore.QThread):
            self.thread.exit()
            self.thread.wait()
            self.thread.deleteLater()
        self.thread = None

    def resize(self, width=None, height=None):
        self.mainwindow._app.processEvents()
        self.adjustSize()
        self.mainwindow._app.processEvents()
        if width is None or height is None:
            super().resize(self.minimumSizeHint())
        else:
            super().resize(width, height)

    def update(self):
        pass

    def activate(self):
        self.setVisible(True)
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def closeEvent(self, event):
        self.stop_thread()
        event.accept()


class NXDialog(QtWidgets.QDialog, NXWidget):
    """Base dialog class for NeXpy dialogs"""

    def __init__(self, parent=None, default=False):
        from .consoleapp import _mainwindow
        self.mainwindow = _mainwindow
        if parent is None:
            parent = self.mainwindow
        QtWidgets.QDialog.__init__(self, parent=parent)
        self.set_attributes()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setSizeGripEnabled(True)
        self.mainwindow.dialogs.append(self)
        if not default:
            self.installEventFilter(self)

    def __repr__(self):
        return 'NXDialog(' + self.__class__.__name__ + ')'

    def close_buttons(self, save=False, close=False):
        """
        Creates a box containing the standard Cancel and OK buttons.
        """
        self.close_box = QtWidgets.QDialogButtonBox(self)
        self.close_box.setOrientation(QtCore.Qt.Horizontal)
        if save:
            self.close_box.setStandardButtons(
                QtWidgets.QDialogButtonBox.Cancel |
                QtWidgets.QDialogButtonBox.Save)
        elif close:
            self.close_box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        else:
            self.close_box.setStandardButtons(
                QtWidgets.QDialogButtonBox.Cancel |
                QtWidgets.QDialogButtonBox.Ok)
        self.close_box.accepted.connect(self.accept)
        self.close_box.rejected.connect(self.reject)
        return self.close_box

    buttonbox = close_buttons  # For backward compatibility

    def eventFilter(self, widget, event):
        """Prevent closure of dialog when pressing [Return] or [Enter]"""
        if event.type() == QtCore.QEvent.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key_Return or key == QtCore.Qt.Key_Enter:
                event = QtGui.QKeyEvent(QtCore.QEvent.KeyPress,
                                        QtCore.Qt.Key_Tab,
                                        QtCore.Qt.NoModifier)
                QtCore.QCoreApplication.postEvent(widget, event)
                return True
            elif key == QtCore.Qt.Key_Escape:
                event.ignore()
                return True
        return QtWidgets.QWidget.eventFilter(self, widget, event)

    def closeEvent(self, event):
        try:
            self.mainwindow.dialogs.remove(self)
        except Exception:
            pass
        event.accept()

    def accept(self):
        """
        Accepts the result.

        This usually needs to be subclassed in each dialog.
        """
        self.accepted = True
        if self in self.mainwindow.dialogs:
            self.mainwindow.dialogs.remove(self)
        QtWidgets.QDialog.accept(self)

    def reject(self):
        """
        Cancels the dialog without saving the result.
        """
        self.accepted = False
        if self in self.mainwindow.dialogs:
            self.mainwindow.dialogs.remove(self)
        QtWidgets.QDialog.reject(self)


class NXPanel(NXDialog):

    def __init__(self, panel, title='title', tabs={}, close=True,
                 apply=True, reset=True, parent=None):
        super().__init__(parent=parent)
        self.tab_class = NXTab
        self.plotview_sort = False
        self.tabwidget = QtWidgets.QTabWidget(parent=self)
        self.tabwidget.currentChanged.connect(self.update)
        self.tabwidget.setElideMode(QtCore.Qt.ElideLeft)
        self.tabs = {}
        self.labels = {}
        self.panel = panel
        self.title = title
        for label in tabs:
            self.tabs[label] = tabs[label]
            self.labels[tabs[label]] = label
        if close:
            self.set_layout(self.tabwidget, self.close_buttons(apply, reset))
        else:
            self.set_layout(self.tabwidget)
        self.set_title(title)

    def __repr__(self):
        return f'NXPanel("{self.panel}")'

    def __contains__(self, label):
        """Implements 'k in d' test"""
        return label in self.tabs

    def close_buttons(self, apply=True, reset=True):
        """
        Creates a box containing the standard Apply, Reset and Close buttons.
        """
        box = QtWidgets.QDialogButtonBox(self)
        box.setOrientation(QtCore.Qt.Horizontal)
        if apply and reset:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Apply |
                                   QtWidgets.QDialogButtonBox.Reset |
                                   QtWidgets.QDialogButtonBox.Close)
        elif apply:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Apply |
                                   QtWidgets.QDialogButtonBox.Close)
        elif reset:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Reset |
                                   QtWidgets.QDialogButtonBox.Close)
        else:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        box.setFocusPolicy(QtCore.Qt.NoFocus)
        if apply:
            self.apply_button = box.button(QtWidgets.QDialogButtonBox.Apply)
            self.apply_button.setFocusPolicy(QtCore.Qt.StrongFocus)
            self.apply_button.setDefault(True)
            self.apply_button.clicked.connect(self.apply)
        if reset:
            self.reset_button = box.button(QtWidgets.QDialogButtonBox.Reset)
            self.reset_button.setFocusPolicy(QtCore.Qt.StrongFocus)
            self.reset_button.clicked.connect(self.reset)
        self.close_button = box.button(QtWidgets.QDialogButtonBox.Close)
        self.close_button.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.close_button.clicked.connect(self.close)
        self.close_box = box
        return self.close_box

    @property
    def tab(self):
        return self.tabwidget.currentWidget()

    @tab.setter
    def tab(self, label):
        self.tabwidget.setCurrentWidget(self.tabs[label])

    @property
    def count(self):
        return self.tabwidget.count()

    def tab_list(self):
        if self.plotview_sort:
            return [tab.tab_label for tab in
                    sorted(self.labels, key=attrgetter('plotview.number'))]
        else:
            return sorted(self.tabs)

    def add(self, label, tab=None, idx=None):
        if label in self.tabs:
            raise NeXusError(f"'{label}' already in {self.title}")
        self.tabs[label] = tab
        self.labels[tab] = label
        tab.panel = self
        if idx is not None:
            self.tabwidget.insertTab(idx, tab, label)
        else:
            self.tabwidget.addTab(tab, label)
        self.tabwidget.setCurrentWidget(tab)
        self.tabwidget.tabBar().setTabToolTip(self.tabwidget.indexOf(tab),
                                              label)

    def remove(self, label):
        if label in self.tabs:
            removed_tab = self.tabs[label]
            if removed_tab.copybox:
                for tab in [self.tabs[label] for label in self.tabs
                            if self.tabs[label] is not removed_tab]:
                    if label in tab.copybox:
                        tab.copybox.remove(label)
                    if len(tab.copybox.items()) == 0:
                        tab.copywidget.setVisible(False)
            removed_tab.close()
            self.tabwidget.removeTab(self.tabwidget.indexOf(removed_tab))
            del self.labels[self.tabs[label]]
            del self.tabs[label]
            removed_tab.deleteLater()
        if self.count == 0:
            self.setVisible(False)

    def idx(self, label):
        if self.plotview_sort and label in self.plotviews:
            pv = self.plotviews[label]
            numbers = sorted([t.plotview.number for t in self.labels])
            return bisect.bisect_left(numbers, pv.number)
        else:
            return bisect.bisect_left(sorted(list(self.tabs)), label)

    def activate(self, label, *args, **kwargs):
        if label not in self.tabs:
            kwargs['parent'] = self
            tab = self.tab_class(label, *args, **kwargs)
            self.add(label, tab, idx=self.idx(label))
        else:
            self.tab = label
            self.tab.update()
        self.update()
        self.setVisible(True)
        self.raise_()
        self.activateWindow()

    def update(self):
        if self.count > 0:
            for tab in [self.tabs[label] for label in self.tabs
                        if self.tabs[label] is not self.tab]:
                tab.setSizePolicy(QtWidgets.QSizePolicy.Ignored,
                                  QtWidgets.QSizePolicy.Ignored)
            self.tab.setSizePolicy(QtWidgets.QSizePolicy.Minimum,
                                   QtWidgets.QSizePolicy.Minimum)
            self.tab.resize()
            self.resize()

    def copy(self):
        self.tab.copy()

    def reset(self):
        self.tab.reset()

    def apply(self):
        self.tab.apply()

    def cleanup(self):
        """Close all tabs and panels."""
        try:
            if self.count > 0:
                for tab in self.tabs:
                    self.tabs[tab].close()
        except Exception:
            pass
        try:
            if self.panel in self.mainwindow.panels:
                del self.mainwindow.panels[self.panel]
        except Exception:
            pass
        try:
            if self.panel in self.plotviews:
                self.plotviews[self.panel].close()
        except Exception:
            pass
        try:
            if self in self.mainwindow.dialogs:
                self.mainwindow.dialogs.remove(self)
        except Exception:
            pass

    def closeEvent(self, event):
        """Customise close events to ensure tabs and panels are closed."""
        self.cleanup()
        event.accept()

    def is_running(self):
        try:
            return self.count >= 0
        except RuntimeError:
            return False

    def close(self):
        """Close this tab and its panel if it is the last tab."""
        try:
            if self.count > 0:
                self.remove(self.labels[self.tab])
            if self.count == 0:
                super().close()
        except RuntimeError:
            self.cleanup()
            try:
                super().close()
            except Exception:
                pass


class NXTab(NXWidget):
    """Subclass of NXWidget for use as the main widget in a tab."""

    def __init__(self, label, parent=None):
        super().__init__(parent=parent)
        self._tab_label = label
        if parent:
            self.panel = parent
            self.tabs = parent.tabs
            self.labels = parent.labels
        else:
            self.panel = None
            self.tabs = {}
            self.labels = {}
        self.copybox = None

    def __repr__(self):
        return self.__class__.__name__ + '("' + self.tab_label + '")'

    @property
    def index(self):
        if self.panel:
            return self.panel.tabwidget.indexOf(self)
        else:
            return None

    @property
    def tab_label(self):
        return self._tab_label

    @tab_label.setter
    def tab_label(self, value):
        if self.panel:
            old_label = self.tab_label
            self._tab_label = str(value)
            self.panel.tabwidget.setTabText(self.index, self._tab_label)
            self.panel.labels[self] = self._tab_label
            self.panel.tabs[self._tab_label] = self
            del self.panel.tabs[old_label]

    def copy_layout(self, text="Copy", sync=None):
        self.copywidget = QtWidgets.QWidget()
        copylayout = QtWidgets.QHBoxLayout()
        self.copybox = NXComboBox()
        self.copy_button = NXPushButton(text, self.copy, self)
        copylayout.addStretch()
        copylayout.addWidget(self.copybox)
        copylayout.addWidget(self.copy_button)
        if sync:
            copylayout.addLayout(self.checkboxes(('sync', sync, False)))
        copylayout.addStretch()
        self.copywidget.setLayout(copylayout)
        self.copywidget.setVisible(False)
        return self.copywidget

    def update(self):
        pass

    def copy(self):
        pass

    def sort_copybox(self):
        if self.copybox:
            selected = self.copybox.selected
            tabs = self.copybox.items()
            self.copybox.clear()
            for tab in [tab for tab in self.panel.tab_list() if tab in tabs]:
                self.copybox.add(tab)
            if selected in self.copybox:
                self.copybox.select(selected)


class GridParameters(dict):
    """
    A dictionary of parameters to be entered in a dialog box grid.

    All keys must be strings, and valid Python symbol names, and all values
    must be of class GridParameter.
    """

    def __init__(self, **kwds):
        super().__init__(self)
        self.result = None
        self.status_layout = None
        self.update(**kwds)

    def __setitem__(self, key, value):
        if value is not None and not isinstance(value, GridParameter):
            raise ValueError(f"'{value}' is not a GridParameter")
        super().__setitem__(key, value)
        value.name = key

    def add(self, name, value=None, label=None, vary=None, slot=None,
            color=False, spinbox=None, readonly=False, width=None):
        """
        Convenience function for adding a Parameter:

        Example
        -------
        p = GridParameters()
        p.add(name, value=XX, ...)

        is equivalent to:
        p[name] = GridParameter(name=name, value=XX, ....
        """
        self.__setitem__(name, GridParameter(value=value, name=name,
                                             label=label, vary=vary,
                                             slot=slot, readonly=readonly,
                                             color=color, spinbox=spinbox,
                                             width=width))

    def grid(self, header=True, title=None, width=None, spacing=2):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(spacing)
        if isinstance(header, list) or isinstance(header, tuple):
            headers = header
            header = True
        else:
            headers = ['Parameter', 'Value', 'Fit?']
        row = 0
        if title:
            title_label = NXLabel(title, bold=True, align='center')
            grid.addWidget(title_label, row, 0, 1, 2)
            row += 1
        if header:
            parameter_label = NXLabel(headers[0], bold=True, align='center')
            grid.addWidget(parameter_label, 0, 0)
            value_label = NXLabel(headers[1], bold=True, align='center')
            grid.addWidget(value_label, row, 1)
            row += 1
        vary = False
        for p in self.values():
            grid.addWidget(p.label, row, 0)
            if p.colorbox:
                grid.addWidget(p.colorbox, row, 1, QtCore.Qt.AlignHCenter)
            else:
                grid.addWidget(p.box, row, 1, QtCore.Qt.AlignHCenter)
            if width:
                if p.colorbox:
                    p.colorbox.setFixedWidth(width)
                else:
                    p.box.setFixedWidth(width)
            if p.vary is not None:
                grid.addWidget(p.checkbox, row, 2, QtCore.Qt.AlignHCenter)
                vary = True
            row += 1
        if header and vary:
            fit_label = NXLabel(headers[2], bold=True)
            grid.addWidget(fit_label, 0, 2, QtCore.Qt.AlignHCenter)
        self.grid_layout = grid
        return grid

    def widget(self, header=True, title=None, width=None):
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self.grid(header=header, title=title, width=width))
        layout.addStretch()
        w.setLayout(layout)
        return w

    def hide_grid(self):
        grid = self.grid_layout
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)

    def show_grid(self):
        grid = self.grid_layout
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(True)

    def delete_grid(self):
        grid = self.grid_layout
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)
                        grid.removeWidget(widget)
                        widget.deleteLater()

    def set_parameters(self):
        from lmfit import Parameter, Parameters
        self.lmfit_parameters = Parameters()
        for p in [p for p in self if self[p].vary]:
            self.lmfit_parameters[p] = Parameter(self[p].name, self[p].value)

    def get_parameters(self, parameters):
        for p in parameters:
            self[p].value = parameters[p].value

    def refine_parameters(self, residuals, **opts):
        from lmfit import fit_report, minimize
        self.set_parameters()
        if self.status_layout:
            self.status_message.setText('Fitting...')
        self.result = minimize(residuals, self.lmfit_parameters, **opts)
        self.fit_report = self.result.message+'\n'+fit_report(self.result)
        if self.status_layout:
            self.status_message.setText(self.result.message)
        self.get_parameters(self.result.params)

    def report_layout(self):
        layout = QtWidgets.QHBoxLayout()
        self.status_message = NXLabel()
        if self.result is None:
            self.status_message.setText('Waiting to refine')
        else:
            self.status_message.setText(self.result.message)
        layout.addWidget(self.status_message)
        layout.addStretch()
        layout.addWidget(NXPushButton('Show Report', self.show_report))
        self.status_layout = layout
        return layout

    def show_report(self):
        if self.result is None:
            return
        message_box = QtWidgets.QMessageBox()
        message_box.setText("Fit Results")
        message_box.setInformativeText(self.fit_report)
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
        spacer = QtWidgets.QSpacerItem(500, 0,
                                       QtWidgets.QSizePolicy.Minimum,
                                       QtWidgets.QSizePolicy.Expanding)
        layout = message_box.layout()
        layout.addItem(spacer, layout.rowCount(), 0, 1, layout.columnCount())
        message_box.exec_()

    def restore_parameters(self):
        for p in [p for p in self if self[p].vary]:
            self[p].value = self[p].init_value

    def save(self):
        for p in self:
            self[p].save()


class GridParameter:
    """
    A Parameter is an object to be set in a dialog box grid.
    """

    def __init__(self, name=None, value=None, label=None, vary=None, slot=None,
                 color=False, spinbox=False, readonly=False, width=None):
        """
        Parameters
        ----------
        name : str, optional
            Name of the parameter.
        value : float, optional
            Numerical Parameter value or NXfield containing the initial value
        label : str, optional
            Label used in the dialog box.
        vary : bool or None, optional
            Whether the Parameter is fixed during a fit.
        slot : function or None, optional
            Function to be called when the parameter is changed.
        color : bool, optional
            Whether the field contains a color value, default False.
        spinbox : bool, optional
            Whether the field should be a spin box, default False.
        """
        self.name = name
        self._value = value
        if isinstance(value, list) or isinstance(value, tuple):
            self.colorbox = None
            self.box = NXComboBox()
            for v in value:
                self.box.addItem(str(v))
            if slot is not None:
                self.box.currentIndexChanged.connect(slot)
        else:
            if color:
                if value == 'auto':
                    value = None
                self.colorbox = NXColorBox(value)
                value = self.colorbox.color_text
                self.box = self.colorbox.textbox
            elif spinbox:
                self.box = NXDoubleSpinBox(slot=slot)
                self.colorbox = None
            else:
                self.box = NXLineEdit(align='right', slot=slot, width=width)
                self.colorbox = None
            if value is not None:
                self.box.blockSignals(True)
                if isinstance(value, NXfield):
                    if value.shape == () or value.shape == (1,):
                        self.field = value
                        self.value = self.field.nxvalue
                    else:
                        raise NeXusError(
                            "Cannot set a grid parameter to an array")
                else:
                    self.field = None
                    self.value = value
                self.box.blockSignals(False)
            if readonly:
                self.box.setReadOnly(True)
        self.init_value = self.value
        if vary is not None:
            self.checkbox = NXCheckBox()
            self.vary = vary
        else:
            self.checkbox = self.vary = None
        self.label = NXLabel(label)

    def set(self, value=None, vary=None):
        """
        Set or update Parameter attributes.

        Parameters
        ----------
        value : float, optional
            Numerical Parameter value.
        vary : bool, optional
            Whether the Parameter is fixed during a fit.
        """
        if value is not None:
            self._val = value
        if vary is not None:
            self.vary = vary

    def __repr__(self):
        s = []
        if self.name is not None:
            s.append(f"'{self.name}'")
        sval = repr(self.value)
        s.append(sval)
        return f"<GridParameter {', '.join(s)}>"

    def save(self):
        if isinstance(self.field, NXfield):
            self.field.nxdata = np.array(self.value).astype(self.field.dtype)

    @property
    def value(self):
        if isinstance(self.box, NXComboBox):
            return self.box.currentText()
        elif isinstance(self.box, NXDoubleSpinBox):
            return self.box.value()
        else:
            _value = self.box.text()
            try:
                return np.array(_value).astype(self.field.dtype).item()
            except AttributeError:
                try:
                    return float(_value)
                except ValueError:
                    return _value

    @value.setter
    def value(self, value):
        self._value = value
        if value is not None:
            if isinstance(self.box, NXComboBox):
                idx = self.box.findText(value)
                if idx >= 0:
                    self.box.setCurrentIndex(idx)
            elif isinstance(self.box, NXDoubleSpinBox):
                self.box.setValue(value)
            else:
                if isinstance(value, NXfield):
                    value = value.nxvalue
                if isinstance(value, str):
                    self.box.setText(value)
                else:
                    try:
                        self.box.setText(f'{value:.6g}')
                    except TypeError:
                        self.box.setText(str(value))
            if self.colorbox:
                self.colorbox.update_color()

    @property
    def vary(self):
        if self.checkbox is not None:
            return self.checkbox.isChecked()
        else:
            return None

    @vary.setter
    def vary(self, value):
        if self.checkbox is not None:
            if value:
                self.checkbox.setCheckState(QtCore.Qt.Checked)
            else:
                self.checkbox.setCheckState(QtCore.Qt.Unchecked)

    def disable(self, vary=None):
        if vary is not None:
            self.vary = vary
        self.checkbox.setEnabled(False)

    def enable(self, vary=None):
        if vary is not None:
            self.vary = vary
        self.checkbox.setEnabled(True)


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

    def __init__(self, slot=None, items=[], default=None, align=None):
        """Initialize the dropdown menu with an initial list of items

        Parameters
        ----------
        slot : func, optional
            A function to be called when a selection is made
        items : list of str, optional
            A list of options to initialize the dropdown menu
        default : str, optional
            The option to be set as default when the menu is initialized
        align : str, optional
            The alignment of the dropdown menu text
        """
        super().__init__()
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToContents)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setMinimumWidth(80)
        if items:
            self.addItems([str(item) for item in items])
            if default:
                self.setCurrentIndex(self.findText(str(default)))
        if slot:
            self.activated.connect(slot)
        if align:
            self.setEditable(True)
            if align == 'center':
                self.lineEdit().setAlignment(QtCore.Qt.AlignCenter)
            elif align == 'right':
                self.lineEdit().setAlignment(QtCore.Qt.AlignRight)
            elif align == 'left':
                self.lineEdit().setAlignment(QtCore.Qt.AlignLeft)
            self.lineEdit().setReadOnly(True)

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
        """Connect this patch to the plotting window canvas events."""
        self.plotview.deactivate()
        self.cidpress = self.canvas.mpl_connect(
            'button_press_event', self.on_press)
        self.cidrelease = self.canvas.mpl_connect(
            'button_release_event', self.on_release)
        self.cidmotion = self.canvas.mpl_connect(
            'motion_notify_event', self.on_motion)

    def is_inside(self, event):
        """Check if the event is inside the shape."""
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
        shape = Polygon(xy, closed=closed, **opts)
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


class NXline:

    def __init__(self, plotview=None, callback=None):
        if plotview:
            self.plotview = plotview
        else:
            from .plotview import get_plotview
            self.plotview = get_plotview()
        self.callback = callback
        self.ax = self.plotview.ax
        self.canvas = self.plotview.canvas
        self.line = None
        self.start_point = None
        self.connect()

    def connect(self):
        self.cidpress = self.canvas.mpl_connect('button_press_event',
                                                self.on_press)
        self.cidrelease = self.canvas.mpl_connect('button_release_event',
                                                  self.on_release)
        self.cidmotion = self.canvas.mpl_connect('motion_notify_event',
                                                 self.on_move)
        self.plotview.deactivate()

    def disconnect(self):
        """Disconnect all the stored connection ids."""
        self.canvas.mpl_disconnect(self.cidpress)
        self.canvas.mpl_disconnect(self.cidrelease)
        self.canvas.mpl_disconnect(self.cidmotion)
        self.plotview.activate()

    def on_press(self, event):
        if event.inaxes != self.ax:
            return
        self.start_point = (event.xdata, event.ydata)
        self.line, = self.ax.plot([event.xdata], [event.ydata], ':w', lw=4)

    def on_move(self, event):
        if self.start_point is None or event.inaxes != self.ax:
            return
        self.line.set_data([self.start_point[0], event.xdata],
                           [self.start_point[1], event.ydata])
        self.canvas.draw()

    def on_release(self, event):
        if event.inaxes != self.ax:
            return
        self.end_point = (event.xdata, event.ydata)
        if self.callback:
            self.callback(self.start_point, self.end_point)
        self.disconnect()
        self.line.remove()
        self.canvas.draw()
