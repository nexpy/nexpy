# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import bisect
import logging
import numbers
import os
import shutil
from operator import attrgetter
from pathlib import Path

import matplotlib as mpl
import numpy as np
import pkg_resources
from matplotlib.legend import Legend
from matplotlib.rcsetup import validate_aspect, validate_float
from nexusformat.nexus import (NeXusError, NXattr, NXdata, NXentry, NXfield,
                               NXgroup, NXlink, NXroot, NXvirtualfield,
                               nxconsolidate, nxgetconfig, nxload, nxsetconfig)

from .pyqt import QtCore, QtGui, QtWidgets, getOpenFileName, getSaveFileName
from .utils import (confirm_action, convertHTML, display_message,
                    fix_projection, format_mtime, format_timestamp, get_color,
                    get_mtime, human_size, import_plugin, keep_data,
                    natural_sort, report_error, set_style, timestamp, wrap)
from .widgets import (NXCheckBox, NXColorBox, NXComboBox, NXDoubleSpinBox,
                      NXLabel, NXLineEdit, NXPlainTextEdit, NXpolygon,
                      NXPushButton, NXScrollArea, NXSpinBox, NXStack)


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
        filename = getOpenFileName(self, 'Open File', dirname)
        if os.path.exists(filename):
            dirname = os.path.dirname(filename)
            self.filename.setText(str(filename))
            self.set_default_directory(dirname)

    def get_filename(self):
        """
        Returns the selected file.
        """
        return self.filename.text()

    def choose_directory(self):
        """Opens a file dialog and sets the directory text box to the path."""
        dirname = self.get_default_directory()
        dirname = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Directory', dirname)
        if os.path.exists(dirname):  # avoids problems if <Cancel> was selected
            self.directoryname.setText(str(dirname))
            self.set_default_directory(dirname)

    def get_directory(self):
        """Return the selected directory."""
        return self.directoryname.text()

    def get_default_directory(self, suggestion=None):
        """Return the most recent default directory for open/save dialogs."""
        if suggestion is None or not os.path.exists(suggestion):
            suggestion = self.default_directory
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
        suggestion = os.path.abspath(suggestion)
        return suggestion

    def set_default_directory(self, suggestion):
        """Defines the default directory to use for open/save dialogs."""
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
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
            os.chdir(directory)
        else:
            os.chdir(self.get_directory())
        if not extension.startswith('.'):
            extension = '.'+extension
        from glob import glob
        filenames = glob(prefix+'*'+extension)
        return sorted(filenames, key=natural_sort)

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
        except Exception as error:
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


BaseDialog = NXDialog


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
        self.cleanup()
        event.accept()

    def is_running(self):
        try:
            return self.count >= 0
        except RuntimeError as error:
            return False

    def close(self):
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


class NewDialog(NXDialog):
    """Dialog to produce a new workspace in the tree view."""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.names = GridParameters()
        self.names.add('root', self.tree.get_new_name(), 'Workspace', None)
        self.names.add('entry', 'entry', 'Entry', True)

        self.set_layout(self.names.grid(header=None),
                        self.close_layout(save=True))

    def accept(self):
        root = self.names['root'].value
        entry = self.names['entry'].value
        if self.names['entry'].vary:
            self.tree[root] = NXroot(NXentry(name=entry))
            self.treeview.select_node(self.tree[root][entry])
        else:
            self.tree[root] = NXroot()
            self.treeview.select_node(self.tree[root])
        dir = os.path.join(self.mainwindow.backup_dir, timestamp())
        os.mkdir(dir)
        fname = os.path.join(dir, root+'_backup.nxs')
        self.tree[root].save(fname, 'w')
        self.treeview.update()
        logging.info(f"New workspace '{root}' created")
        self.mainwindow.settings.set('backups', fname)
        self.mainwindow.settings.set('session', fname)
        self.mainwindow.settings.save()
        super().accept()


class DirectoryDialog(NXDialog):
    """Dialog to select files in a directory to be opened."""

    def __init__(self, files, directory=None, parent=None):

        super().__init__(parent=parent)

        self.directory = directory
        self.prefix_box = NXLineEdit()
        self.prefix_box.textChanged.connect(self.select_prefix)
        prefix_layout = self.make_layout(NXLabel('Prefix'), self.prefix_box)
        grid = QtWidgets.QGridLayout()
        for i, f in enumerate(files):
            self.checkbox[f] = NXCheckBox(checked=True)
            grid.addWidget(NXLabel(f), i, 0)
            grid.addWidget(self.checkbox[f], i, 1)
        self.set_layout(prefix_layout, NXScrollArea(grid), self.close_layout())
        self.prefix_box.setFocus()

    @property
    def files(self):
        return [f for f in self.checkbox if self.checkbox[f].isChecked()]

    def select_prefix(self):
        prefix = self.prefix_box.text()
        for f in self.checkbox:
            if f.startswith(prefix):
                self.checkbox[f].setChecked(True)
            else:
                self.checkbox[f].setChecked(False)

    def accept(self):
        for i, f in enumerate(self.files):
            fname = os.path.join(self.directory, f)
            if i == 0:
                self.mainwindow.load_file(fname, wait=1)
            else:
                self.mainwindow.load_file(fname, wait=1, recent=False)
        self.treeview.select_top()
        super().accept()


class PlotDialog(NXDialog):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""

    def __init__(self, node, parent=None, lines=False):

        super().__init__(parent=parent)

        if isinstance(node, NXfield):
            self.group = node.nxgroup
            signal_name = node.nxname
        else:
            self.group = node
            signal_name = None

        try:
            self.default_axes = [axis.nxname for axis in self.group.nxaxes]
        except Exception:
            self.default_axes = []

        self.signal_combo = NXComboBox()
        for node in self.group.values():
            if isinstance(node, NXfield) and node.is_plottable():
                self.signal_combo.addItem(node.nxname)
        if self.signal_combo.count() == 0:
            raise NeXusError("No plottable field in group")
        if signal_name:
            idx = self.signal_combo.findText(signal_name)
            if idx >= 0:
                self.signal_combo.setCurrentIndex(idx)
            else:
                signal_name = None
        self.signal_combo.currentIndexChanged.connect(self.choose_signal)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(NXLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.choose_signal()

        self.set_layout(self.grid,
                        self.checkboxes(('lines', 'Plot Lines', lines),
                                        ('over', 'Plot Over', False)),
                        self.close_buttons())
        if self.ndim != 1:
            self.checkbox['lines'].setVisible(False)
            self.checkbox['over'].setVisible(False)
        elif self.plotview.ndim != 1:
            self.checkbox['over'].setVisible(False)
            self.checkbox['over'].setEnabled(False)

        self.set_title("Plot NeXus Data")

    @property
    def signal(self):
        _signal = self.group[self.signal_combo.currentText()]
        if isinstance(_signal, NXlink) and _signal._filename is None:
            return _signal.nxlink
        else:
            return _signal

    @property
    def signal_path(self):
        signal = self.group[self.signal_combo.currentText()]
        if signal.nxroot.nxclass == "NXroot":
            return signal.nxroot.nxname + signal.nxpath
        else:
            return signal.nxpath

    @property
    def ndim(self):
        return self.signal.ndim

    def choose_signal(self):
        row = 0
        self.axis_boxes = {}
        for axis in range(self.ndim):
            row += 1
            self.grid.addWidget(NXLabel(f"Axis {axis}: "), row, 0)
            self.axis_boxes[axis] = self.axis_box(axis)
            self.grid.addWidget(self.axis_boxes[axis], row, 1)
        while row < self.grid.rowCount() - 1:
            self.remove_axis(row)
            row += 1

    def axis_box(self, axis):
        box = NXComboBox()
        axes = []
        for node in self.group.values():
            if isinstance(node, NXfield) and node is not self.signal:
                if self.check_axis(node, axis):
                    axes.append(node.nxname)
                    box.addItem(node.nxname)
        if box.count() > 0:
            box.insertSeparator(0)
        box.insertItem(0, 'NXfield index')
        try:
            if self.default_axes[axis] in axes:
                box.setCurrentIndex(box.findText(self.default_axes[axis]))
            else:
                box.setCurrentIndex(0)
        except Exception:
            box.setCurrentIndex(0)
        return box

    def remove_axis(self, axis):
        row = axis + 1
        for column in range(2):
            item = self.grid.itemAtPosition(row, column)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(False)
                    self.grid.removeWidget(widget)
                    widget.deleteLater()

    def check_axis(self, node, axis):
        if isinstance(node, NXgroup) or node.ndim > 1:
            return False
        axis_len = self.signal.shape[axis]
        if node.ndim == 0:
            node_len = 1
        else:
            node_len = node.shape[0]
        if node_len == axis_len or node_len == axis_len+1:
            return True
        else:
            return False

    def get_axis(self, axis):
        def plot_axis(axis):
            return NXfield(axis.nxvalue, name=axis.nxname, attrs=axis.attrs)
        axis_name = self.axis_boxes[axis].currentText()
        if axis_name == 'NXfield index':
            return NXfield(range(self.signal.shape[axis]),
                           name=f'Axis{axis}')
        else:
            return plot_axis(self.group[axis_name])

    def get_axes(self):
        axes = [self.get_axis(axis) for axis in range(self.ndim)]
        names = [axis.nxname for axis in axes]
        if len(names) != len(set(names)):
            raise NeXusError("Duplicate axes selected")
        return axes

    def accept(self):
        try:
            kwargs = {}
            if self.ndim == 1:
                if self.checkbox['lines'].isChecked():
                    kwargs['marker'] = 'None'
                    kwargs['linestyle'] = '-'
                else:
                    kwargs['marker'] = 'o'
                kwargs['over'] = self.checkbox['over'].isChecked()
            data = NXdata(self.signal, self.get_axes(),
                          title=self.signal_path)
            data.attrs['signal_path'] = self.signal_path
            data.plot(**kwargs)
            super().accept()
        except NeXusError as error:
            report_error("Plotting data", error)


class PlotScalarDialog(NXDialog):
    """Dialog to plot scalar values against values in another tree."""

    def __init__(self, node, parent=None, **kwargs):

        super().__init__(parent=parent)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)

        if isinstance(node, NXfield):
            self.node = node
            self.group = node.nxgroup

        self.signal_combo = NXComboBox()
        signals = [s for s in self.group if self.group[s].size == 1 and
                   self.group[s].is_numeric()]
        if len(signals) == 0:
            raise NeXusError("No numeric scalars in group")
        self.signal_combo.add(*signals)
        if node.nxname in self.signal_combo:
            self.signal_combo.select(node.nxname)

        self.set_layout(
            self.make_layout(self.signal_combo),
            self.textboxes(('Scan', '')),
            self.action_buttons(
                ('Select Scan', self.select_scan),
                ('Select Files', self.select_files)),
            self.checkboxes(
                ('lines', 'Plot Lines', False),
                ('over', 'Plot Over', False)),
            self.action_buttons(
                ('Plot', self.plot_scan),
                ('Copy', self.copy_scan),
                ('Save', self.save_scan)),
            self.close_layout())

        self.set_title("Plot NeXus Field")
        self.kwargs = kwargs
        self.file_box = None
        self.scan_files = None
        self.scan_values = None

    def select_scan(self):
        scan_axis = self.treeview.node
        if not isinstance(scan_axis, NXfield):
            display_message("Scan Panel", "Scan axis must be a NXfield")
        elif scan_axis.shape != () and scan_axis.shape != (1,):
            display_message("Scan Panel", "Scan axis must be a scalar")
        else:
            self.textbox['Scan'].setText(self.treeview.node.nxpath)

    def select_files(self):
        if self.file_box in self.mainwindow.dialogs:
            try:
                self.file_box.close()
            except Exception:
                pass
        self.file_box = NXDialog(parent=self)
        self.file_box.setWindowTitle('Select Files')
        self.file_box.setMinimumWidth(300)
        self.prefix_box = NXLineEdit()
        self.prefix_box.textChanged.connect(self.select_prefix)
        prefix_layout = self.make_layout(NXLabel('Prefix'), self.prefix_box)
        self.files = GridParameters()
        i = 0
        for name in sorted(self.tree, key=natural_sort):
            root = self.tree[name]
            if self.data_path in root:
                i += 1
                if self.scan_path:
                    self.files.add(name, root[self.scan_path], name, True)
                else:
                    self.files.add(name, i, name, True)
                    self.files[name].checkbox.stateChanged.connect(
                        self.update_files)
        self.file_grid = self.files.grid(header=('File', self.scan_header, ''))
        self.scroll_area = NXScrollArea(self.make_layout(self.file_grid))
        self.file_box.set_layout(prefix_layout, self.scroll_area,
                                 self.file_box.close_layout())
        self.file_box.close_box.accepted.connect(self.choose_files)
        self.file_box.show()

    def select_prefix(self):
        prefix = self.prefix_box.text()
        for f in self.files:
            if f.startswith(prefix):
                self.files[f].checkbox.setChecked(True)
            else:
                self.files[f].checkbox.setChecked(False)

    def update_files(self):
        if self.scan_variable is None:
            i = 0
            for f in self.files:
                if self.files[f].vary:
                    i += 1
                    self.files[f].value = i
                else:
                    self.files[f].value = ''

    @property
    def data_path(self):
        return self.group[self.signal_combo.selected].nxpath

    @property
    def scan_path(self):
        return self.textbox['Scan'].text()

    @property
    def scan_variable(self):
        if self.scan_path and self.scan_path in self.group.nxroot:
            return self.group.nxroot[self.scan_path]
        else:
            return None

    @property
    def scan_header(self):
        try:
            return self.scan_variable.nxname.capitalize()
        except AttributeError:
            return 'Variable'

    def scan_axis(self):
        if self.scan_values is None:
            raise NeXusError("Files not selected")
        _values = self.scan_values
        if self.scan_variable is not None:
            _variable = self.scan_variable
            _axis = NXfield(_values, dtype=_variable.dtype,
                            name=_variable.nxname)
            if 'long_name' in _variable.attrs:
                _axis.attrs['long_name'] = _variable.attrs['long_name']
            if 'units' in _variable.attrs:
                _axis.attrs['units'] = _variable.attrs['units']
        else:
            _axis = NXfield(_values, name='file_index', long_name='File Index')
        return _axis

    def choose_files(self):
        try:
            self.scan_files = [self.tree[self.files[f].name]
                               for f in self.files if self.files[f].vary]
            self.scan_values = [self.files[f].value for f in self.files
                                if self.files[f].vary]
        except Exception as error:
            raise NeXusError("Files not selected")

    def get_scan(self):
        signal = self.group[self.data_path]
        axis = self.scan_axis()
        shape = [len(axis)]
        field = NXfield(shape=shape, dtype=signal.dtype, name=signal.nxname)
        for i, f in enumerate(self.scan_files):
            try:
                field[i] = f[self.data_path]
            except Exception as error:
                raise NeXusError(f"Cannot read '{f}'")
            field[i] = f[self.data_path]
        return NXdata(field, axis, title=self.data_path)

    def plot_scan(self):
        try:
            opts = {}
            if self.checkbox['lines'].isChecked():
                opts['marker'] = 'None'
                opts['linestyle'] = '-'
            opts['over'] = self.checkbox['over'].isChecked()
            self.get_scan().plot(**opts)
        except NeXusError as error:
            report_error("Plotting Scan", error)

    def copy_scan(self):
        try:
            self.mainwindow.copied_node = self.mainwindow.copy_node(
                self.get_scan())
        except NeXusError as error:
            report_error("Copying Scan", error)

    def save_scan(self):
        try:
            keep_data(self.get_scan())
        except NeXusError as error:
            report_error("Saving Scan", error)

    def close(self):
        try:
            self.file_box.close()
        except Exception:
            pass
        super().close()


class ExportDialog(NXDialog):

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)

        self.tabwidget = QtWidgets.QTabWidget(parent=self)
        self.tabwidget.setElideMode(QtCore.Qt.ElideLeft)

        self.data = node
        if self.data.ndim == 1 and node.nxsignal is not None:
            self.x = node.nxaxes[0]
            self.y = node.nxsignal
            self.e = node.nxerrors
            if self.x.shape[0] > self.y.shape[0]:
                self.x = node.nxaxes[0].centers()
            self.fields = [f for f in [self.x, self.y, self.e]
                           if f is not None]
            names = [f.nxname for f in self.fields]

            delimiters = ['Tab', 'Space', 'Comma', 'Colon', 'Semicolon']
            self.text_options = GridParameters()
            self.text_options.add('delimiter', delimiters, 'Delimiter')

            text_grid = self.text_options.grid(header=False)
            text_grid.setSpacing(10)

            text_layout = self.make_layout(text_grid,
                                           self.checkboxes(
                                               ('title', 'Title', True),
                                               ('header', 'Headers', True),
                                               ('errors', 'Errors', True),
                                               ('fields', 'All Fields', True)),
                                           vertical=True)
            if self.e is None:
                self.checkbox['errors'].setChecked(False)
                self.checkbox['errors'].setVisible(False)
            self.all_fields = []
            for field in [f for f in self.data.NXfield if f.nxname not in names
                          and f.shape == self.y.shape]:
                self.all_fields.append(field)
            if self.all_fields == []:
                self.checkbox['fields'].setChecked(False)
                self.checkbox['fields'].setVisible(False)
            else:
                self.all_fields = self.fields + self.all_fields

            self.text_tab = NXWidget(parent=self.tabwidget)
            self.text_tab.set_layout(text_layout)

        self.nexus_options = GridParameters()
        self.nexus_options.add('entry', 'entry', 'Name of Entry', True)
        self.nexus_options.add('data', self.data.nxname, 'Name of Data')

        nexus_grid = self.nexus_options.grid(header=None)
        nexus_grid.setSpacing(10)

        self.nexus_tab = NXWidget(parent=self.tabwidget)
        self.nexus_tab.set_layout(nexus_grid)

        self.tabwidget.addTab(self.nexus_tab, 'NeXus File')
        if self.data.ndim == 1:
            self.tabwidget.addTab(self.text_tab, 'Text File')
        self.tabwidget.setCurrentWidget(self.nexus_tab)

        self.set_layout(self.tabwidget, self.close_buttons(save=True))

        self.set_title('Exporting Data')

    @property
    def header(self):
        return self.checkbox['header'].isChecked()

    @property
    def title(self):
        return self.checkbox['title'].isChecked()

    @property
    def errors(self):
        return self.checkbox['errors'].isChecked()

    @property
    def export_fields(self):
        if self.checkbox['fields'].isChecked():
            return self.all_fields
        else:
            return self.fields

    @property
    def delimiter(self):
        delimiter = self.text_options['delimiter'].value
        if delimiter == 'Tab':
            return '\\t'.encode('utf8').decode('unicode_escape')
        elif delimiter == 'Space':
            return ' '
        elif delimiter == 'Comma':
            return ','
        elif delimiter == 'Colon':
            return ':'
        elif delimiter == 'Semicolon':
            return ';'

    @property
    def name(self):
        return self.nexus_options['data'].value

    def accept(self):
        if self.tabwidget.currentWidget() is self.nexus_tab:
            fname = getSaveFileName(self, "Choose a Filename",
                                    self.data.nxname+'.nxs',
                                    self.mainwindow.file_filter)
            if fname:
                self.set_default_directory(os.path.dirname(fname))
            else:
                super().reject()
                return
            entry = self.nexus_options['entry'].value
            if self.nexus_options['entry'].vary:
                root = NXroot(NXentry(name=entry))
                root[entry][self.name] = self.data
            else:
                root = NXroot()
                root[self.name] = self.data
            root.save(fname, 'w')
        else:
            fname = getSaveFileName(self, "Choose a Filename",
                                    self.data.nxname+'.txt')
            if fname:
                self.set_default_directory(os.path.dirname(fname))
            else:
                super().reject()
                return
            header = ''
            if self.title:
                header += self.data.nxtitle
                if self.header:
                    header += '\n'
            if self.header:
                header += self.delimiter.join([f.nxname
                                               for f in self.export_fields])
            output = np.array(self.export_fields).T.astype(str)
            output[output == str(np.nan)] = ''
            np.savetxt(fname, output, header=header, delimiter=self.delimiter,
                       comments='', fmt='%s')

        logging.info(f"Data saved as '{fname}'")
        super().accept()


class LockDialog(NXDialog):
    """Dialog to display file-based locks on NeXus files"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.lockdirectory = nxgetconfig('lockdirectory')
        self.text_box = NXPlainTextEdit(wrap=False)
        self.text_box.setReadOnly(True)
        self.set_layout(self.label(f'Lock Directory: {self.lockdirectory}'),
                        self.text_box,
                        self.action_buttons(('Clear Locks', self.clear_locks)),
                        self.close_buttons(close=True))
        self.set_title(f'Locked Files')
        self.setMinimumWidth(800)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.show_locks)
        self.timer.start(5000)

        self.show_locks()

    def convert_name(self, name):
        return '/' + name.replace('!!', '/').replace('.lock', '')

    def show_locks(self):
        text = []
        for f in sorted(os.scandir(self.lockdirectory), key=get_mtime):
            if f.name.endswith('.lock'):
                name = self.convert_name(f.name)
                text.append(f'{format_mtime(get_mtime(f))} {name}')
        if text:
            self.text_box.setPlainText('\n'.join(text))
        else:
            self.text_box.setPlainText('No Files')

    def clear_locks(self):
        dialog = NXDialog(parent=self)
        locks = []
        for f in sorted(os.scandir(self.lockdirectory), key=get_mtime):
            if f.name.endswith('.lock'):
                name = self.convert_name(f.name)
                locks.append(self.checkboxes((f.name, name, False),
                                             align='left'))
        dialog.scroll_area = NXScrollArea()
        dialog.scroll_widget = NXWidget()
        dialog.scroll_widget.set_layout(*locks)
        dialog.scroll_area.setWidget(dialog.scroll_widget)

        dialog.set_layout(dialog.scroll_area,
                          self.action_buttons(('Clear Lock', self.clear_lock)),
                          dialog.close_buttons(close=True))

        dialog.set_title('Clear Locks')
        self.locks_dialog = dialog
        self.locks_dialog.show()

    def clear_lock(self):
        for f in list(self.checkbox):
            if self.checkbox[f].isChecked():
                try:
                    os.remove(os.path.join(self.lockdirectory, f))
                except FileNotFoundError:
                    pass
                del self.checkbox[f]
        self.locks_dialog.close()
        self.show_locks()


class SettingsDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent=parent, default=True)
        cfg = nxgetconfig()
        self.parameters = GridParameters()
        self.parameters.add('memory', cfg['memory'], 'Memory Limit (MB)')
        self.parameters.add('maxsize', cfg['maxsize'], 'Array Size Limit')
        self.parameters.add('compression', cfg['compression'],
                            'Compression Filter')
        self.parameters.add('encoding', cfg['encoding'], 'Text Encoding')
        self.parameters.add('lock', cfg['lock'], 'Lock Timeout (s)')
        self.parameters.add('lockexpiry', cfg['lockexpiry'], 'Lock Expiry (s)')
        self.parameters.add('lockdirectory', cfg['lockdirectory'],
                            'Lock Directory')
        self.parameters.add('recursive', ['True', 'False'], 'File Recursion')
        self.parameters['recursive'].value = str(cfg['recursive'])
        styles = ['default', 'publication'] + sorted(
            style for style in mpl.style.available if style != 'publication')
        self.parameters.add('style', styles, 'Plot Style')
        self.parameters['style'].value = self.mainwindow.settings.get(
            'settings', 'style')
        self.set_layout(self.parameters.grid(),
                        self.action_buttons(('Save As Default',
                                            self.save_default)),
                        self.close_layout(save=True))
        self.set_title('NeXpy Settings')

    def save_default(self):
        self.set_nexpy_settings()
        cfg = nxgetconfig()
        self.mainwindow.settings.set('settings', 'memory', cfg['memory'])
        self.mainwindow.settings.set('settings', 'maxsize', cfg['maxsize'])
        self.mainwindow.settings.set('settings', 'compression',
                                     cfg['compression'])
        self.mainwindow.settings.set('settings', 'encoding',
                                     cfg['encoding'])
        self.mainwindow.settings.set('settings', 'lock', cfg['lock'])
        self.mainwindow.settings.set('settings', 'lockexpiry',
                                     cfg['lockexpiry'])
        self.mainwindow.settings.set('settings', 'lockdirectory',
                                     cfg['lockdirectory'])
        self.mainwindow.settings.set('settings', 'recursive',
                                     cfg['recursive'])
        self.mainwindow.settings.set('settings', 'style',
                                     self.parameters['style'].value)
        self.mainwindow.settings.save()

    def set_nexpy_settings(self):
        lockdirectory = self.parameters['lockdirectory'].value
        if not lockdirectory.strip():
            lockdirectory = None
        nxsetconfig(memory=self.parameters['memory'].value,
                    maxsize=self.parameters['maxsize'].value,
                    compression=self.parameters['compression'].value,
                    encoding=self.parameters['encoding'].value,
                    lock=self.parameters['lock'].value,
                    lockexpiry=self.parameters['lockexpiry'].value,
                    lockdirectory=lockdirectory,
                    recursive=self.parameters['recursive'].value)
        set_style(self.parameters['style'].value)

    def accept(self):
        self.set_nexpy_settings()
        super().accept()


class CustomizeDialog(NXPanel):

    def __init__(self, parent=None):
        super().__init__('Customize', title='Customize Panel', parent=parent)
        self.tab_class = CustomizeTab
        self.plotview_sort = True


class CustomizeTab(NXTab):

    legend_location = {v: k for k, v in Legend.codes.items()}

    def __init__(self, label, parent=None):
        super().__init__(label, parent=parent)

        from .plotview import linestyles, markers
        self.markers, self.linestyles = markers, linestyles

        self.plotview = self.active_plotview

        self.parameters = {}
        pl = self.parameters['labels'] = self.label_parameters()
        self.update_label_parameters()
        if self.plotview.image is not None:
            pi = self.parameters['image'] = self.image_parameters()
            self.update_image_parameters()
            self.set_layout(pl.grid(header=False),
                            pi.grid(header=False))
        else:
            pp = {}
            self.plots = self.plotview.plots
            for plot in self.plots:
                label = self.plot_label(plot)
                pp[label] = self.parameters[label] = self.plot_parameters(plot)
            self.plot_stack = self.parameter_stack(pp)
            for plot in self.plots:
                self.update_plot_parameters(plot)
            self.legend_order = self.get_legend_order()
            pg = self.parameters['grid'] = self.grid_parameters()
            self.update_grid_parameters()
            self.set_layout(pl.grid(header=False),
                            self.plot_stack,
                            pg.grid(header=False))
        self.parameters['labels']['title'].box.setFocus()

    def plot_label(self, plot):
        return str(plot) + ': ' + self.plots[plot]['path']

    def label_plot(self, label):
        return int(label[:label.index(':')])

    def update(self):
        self.update_label_parameters()
        if self.plotview.image is not None:
            self.update_image_parameters()
        else:
            self.plots = self.plotview.plots
            for plot in self.plots:
                label = self.plot_label(plot)
                if label not in self.parameters:
                    pp = self.parameters[label] = self.plot_parameters(plot)
                    self.plot_stack.add(label, pp.widget(header=False))
                self.update_plot_parameters(plot)
            self.legend_order = self.get_legend_order()
            for label in [la for la in self.parameters
                          if la not in ['labels', 'grid']]:
                if self.label_plot(label) not in self.plots:
                    del self.parameters[label]
                    self.plot_stack.remove(label)

    def label_parameters(self):
        parameters = GridParameters()
        parameters.add('title', self.plotview.title, 'Title')
        parameters.add('xlabel', self.plotview.xaxis.label, 'X-Axis Label')
        parameters.add('ylabel', self.plotview.yaxis.label, 'Y-Axis Label')
        parameters.grid(title='Plot Labels', header=False, width=200)
        return parameters

    def update_label_parameters(self):
        p = self.parameters['labels']
        p['title'].value = self.plotview.title
        p['xlabel'].value = self.plotview.xaxis.label
        p['ylabel'].value = self.plotview.yaxis.label

    def image_parameters(self):
        parameters = GridParameters()
        parameters.add('aspect', self.plotview._aspect, 'Aspect Ratio')
        parameters.add('skew', self.plotview._skew_angle, 'Skew Angle')
        parameters.add('grid', ['On', 'Off'], 'Grid')
        parameters.add('gridcolor', get_color(self.plotview._gridcolor),
                       'Grid Color', color=True)
        parameters.add('gridstyle', list(self.linestyles), 'Grid Style')
        parameters.add('gridalpha', self.plotview._gridalpha, 'Grid Alpha')
        parameters.add('minorticks', ['On', 'Off'], 'Minor Ticks')
        parameters.add('cb_minorticks', ['On', 'Off'], 'Color Bar Minor Ticks')
        try:
            parameters.add('badcolor',
                           get_color(self.plotview.image.cmap.get_bad()),
                           'Bad Color', color=True)
        except AttributeError:
            pass
        parameters.grid(title='Image Parameters', header=False, width=125)
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
        p['gridcolor'].value = get_color(self.plotview._gridcolor)
        p['gridstyle'].value = self.plotview._gridstyle
        p['gridalpha'].value = self.plotview._gridalpha
        if self.plotview._minorticks:
            p['minorticks'].value = 'On'
        else:
            p['minorticks'].value = 'Off'
        if self.plotview._cb_minorticks:
            p['cb_minorticks'].value = 'On'
        else:
            p['cb_minorticks'].value = 'Off'
        try:
            p['badcolor'].value = get_color(self.plotview.image.cmap.get_bad())
        except AttributeError:
            pass

    def plot_parameters(self, plot):
        p = self.plots[plot]
        parameters = GridParameters()
        parameters.add('legend_label', p['legend_label'], 'Legend Label')
        parameters.add('legend', ['Yes', 'No'], 'Add to Legend')
        parameters.add('legend_order', p['legend_order'], 'Legend Order',
                       slot=self.update_legend_order)
        parameters.add('color', p['color'], 'Color', color=True)
        parameters.add('linestyle', list(self.linestyles), 'Line Style')
        parameters.add('linewidth', p['linewidth'], 'Line Width')
        parameters.add('marker', list(self.markers.values()), 'Marker')
        parameters.add('markerstyle', ['filled', 'open'], 'Marker Style')
        parameters.add('markersize', p['markersize'], 'Marker Size')
        parameters.add('zorder', p['zorder'], 'Z-Order')
        parameters.add('scale', 1.0, 'Scale', slot=self.scale_plot,
                       spinbox=True)
        parameters['scale'].box.setSingleStep(0.01)
        parameters.add('offset', 0.0, 'Offset', slot=self.scale_plot,
                       spinbox=True)
        parameters['offset'].box.setSingleStep(10)
        parameters['offset'].box.setMinimum(
            -parameters['offset'].box.maximum())
        parameters.grid(title='Plot Parameters', header=False, width=125)
        return parameters

    def update_plot_parameters(self, plot):
        self.block_signals(True)
        label = self.plot_label(plot)
        p, pp = self.plots[plot], self.parameters[label]
        pp['legend_label'].value = p['legend_label']
        if p['show_legend']:
            pp['legend'].value = 'Yes'
        else:
            pp['legend'].value = 'No'
        pp['legend_order'].value = p['legend_order']
        pp['color'].value = p['color']

        def get_ls(ls):
            return list(self.linestyles)[
                list(self.linestyles.values()).index(ls)]
        if p['smooth_line']:
            pp['linestyle'].value = get_ls(p['smooth_linestyle'])
        else:
            pp['linestyle'].value = get_ls(p['linestyle'])
        pp['linewidth'].value = p['linewidth']
        pp['marker'].value = self.markers[p['marker']]
        pp['markerstyle'].value = p['markerstyle']
        pp['markersize'].value = p['markersize']
        pp['zorder'].value = p['zorder']
        pp['scale'].value = p['scale']
        pp['offset'].value = p['offset']
        self.block_signals(False)

    def grid_parameters(self):
        parameters = GridParameters()
        parameters.add('legend', ['None']+[key.title()
                       for key in Legend.codes], 'Legend')
        parameters.add('label', ['Legend Label', 'Full Path', 'Group Path',
                                 'Group Name', 'Signal Name'], 'Label')
        parameters.add('grid', ['On', 'Off'], 'Grid')
        parameters.add('gridcolor', get_color(self.plotview._gridcolor),
                       'Grid Color', color=True)
        parameters.add('gridstyle', list(self.linestyles), 'Grid Style')
        parameters.add('gridalpha', self.plotview._gridalpha, 'Grid Alpha')
        parameters.add('minorticks', ['On', 'Off'], 'Minor Ticks')
        parameters.grid(title='Plot Attributes', header=False, width=125)
        return parameters

    def update_grid_parameters(self):
        p = self.parameters['grid']
        if self.plotview.ax.get_legend() and not self.is_empty_legend():
            _loc = self.plotview.ax.get_legend()._loc
            if _loc in self.legend_location:
                p['legend'].value = self.legend_location[_loc].title()
            else:
                p['legend'].value = 'Best'
        else:
            p['legend'].value = 'None'
        p['label'].value = 'Label'
        if self.plotview._grid:
            p['grid'].value = 'On'
        else:
            p['grid'].value = 'Off'
        p['gridcolor'].value = get_color(self.plotview._gridcolor)
        p['gridstyle'].value = self.plotview._gridstyle
        p['gridalpha'].value = self.plotview._gridalpha
        if self.plotview._minorticks:
            p['minorticks'].value = 'On'
        else:
            p['minorticks'].value = 'Off'

    def is_empty_legend(self):
        labels = [self.plot_label(plot) for plot in self.plots]
        return 'Yes' not in [self.parameters[label]['legend'].value
                             for label in labels]

    def get_legend_order(self):
        order = []
        for plot in self.plots:
            label = self.plot_label(plot)
            order.append(int(self.parameters[label]['legend_order'].value - 1))
        return order

    def plot_index(self, plot):
        return list(self.plots).index(plot)

    def update_legend_order(self):
        current_label = self.plot_stack.box.selected
        current_plot = self.label_plot(current_label)
        current_order = self.legend_order[self.plot_index(current_plot)]
        order = self.legend_order
        try:
            new_order = int(
                self.parameters[current_label]['legend_order'].value - 1)
            if new_order == current_order:
                return
            elif new_order < 0 or new_order >= len(self.plots):
                raise ValueError
        except Exception:
            self.parameters[current_label]['legend_order'].value = (
                current_order + 1)
            return
        self.block_signals(True)
        for plot in [p for p in self.plots if p != current_plot]:
            label = self.plot_label(plot)
            order = int(self.parameters[label]['legend_order'].value - 1)
            if (new_order > current_order and order > current_order and
                    order <= new_order):
                self.parameters[label]['legend_order'].value = order
            elif (new_order < current_order and order < current_order and
                  order >= new_order):
                self.parameters[label]['legend_order'].value = order + 2
        self.block_signals(False)
        self.legend_order = self.get_legend_order()

    def set_legend(self):
        legend_location = self.parameters['grid']['legend'].value.lower()
        label_selection = self.parameters['grid']['label'].value
        if legend_location == 'none' or self.is_empty_legend():
            self.plotview.remove_legend()
        else:
            if label_selection == 'Legend Label':
                self.plotview.legend(loc=legend_location)
            elif label_selection == 'Full Path':
                self.plotview.legend(path=True, loc=legend_location)
            elif label_selection == 'Group Path':
                self.plotview.legend(group=True, path=True,
                                     loc=legend_location)
            elif label_selection == 'Group Name':
                self.plotview.legend(group=True, loc=legend_location)
            else:
                self.plotview.legend(signal=True, loc=legend_location)

    def set_grid(self):
        if self.plotview.image is None:
            p = self.parameters['grid']
        else:
            p = self.parameters['image']
        if p['grid'].value == 'On':
            self.plotview._grid = True
        else:
            self.plotview._grid = False
        self.plotview._gridcolor = p['gridcolor'].value
        self.plotview._gridstyle = self.linestyles[p['gridstyle'].value]
        self.plotview._gridalpha = p['gridalpha'].value
        if p['minorticks'].value == 'On':
            self.plotview.minorticks_on()
            if self.plotview._grid:
                self.plotview.grid(True, minor=True)
            else:
                self.plotview.grid(False)
        else:
            self.plotview.minorticks_off()
            if self.plotview._grid:
                self.plotview.grid(True, minor=False)
            else:
                self.plotview.grid(False)

    def scale_plot(self):
        plot = self.label_plot(self.plot_stack.box.selected)
        label = self.plot_label(plot)
        scale = self.parameters[label]['scale'].value
        if scale == self.parameters[label]['scale'].box.maximum():
            self.parameters[label]['scale'].box.setMaximum(10*scale)
        self.parameters[label]['scale'].box.setSingleStep(scale/100.0)
        offset = self.parameters[label]['offset'].value
        if offset == self.parameters[label]['offset'].box.maximum():
            self.parameters[label]['offset'].box.setMaximum(10*abs(offset))
        self.parameters[label]['offset'].box.setMinimum(
            -self.parameters[label]['offset'].box.maximum())
        self.parameters[label]['offset'].box.setSingleStep(
            max(abs(offset)/100.0, 1))
        y = self.plotview.plots[plot]['y']
        self.plotview.plots[plot]['plot'].set_ydata((y * scale) + offset)
        self.plotview.draw()

    def block_signals(self, block=True):
        for p in [parameter for parameter in self.parameters if
                  parameter not in ['labels', 'grid']]:
            self.parameters[p]['legend_order'].box.blockSignals(block)

    def reset(self):
        self.update()

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
            try:
                self.plotview._aspect = validate_aspect(pi['aspect'].value)
            except ValueError:
                pi['aspect'].value = self.plotview._aspect
            try:
                _skew_angle = validate_float(pi['skew'].value)
            except ValueError:
                pi['skew'].value = self.plotview.skew
            if pi['grid'].value == 'On':
                self.plotview._grid = True
            else:
                self.plotview._grid = False
            self.plotview._gridcolor = pi['gridcolor'].value
            self.plotview._gridstyle = self.linestyles[pi['gridstyle'].value]
            self.plotview._gridalpha = pi['gridalpha'].value
            if 'badcolor' in pi:
                self.plotview.image.cmap.set_bad(pi['badcolor'].value)
            # reset in case plotview.aspect changed by plotview.skew
            self.plotview.skew = _skew_angle
            self.plotview.aspect = self.plotview._aspect
            if pi['cb_minorticks'].value == 'On':
                self.plotview.cb_minorticks_on()
            else:
                self.plotview.cb_minorticks_off()
        else:
            for plot in self.plots:
                label = self.plot_label(plot)
                p, pp = self.plots[plot], self.parameters[label]
                p['legend_label'] = pp['legend_label'].value
                if pp['legend'].value == 'Yes':
                    p['show_legend'] = True
                else:
                    p['show_legend'] = False
                p['legend_order'] = int(pp['legend_order'].value)
                p['color'] = pp['color'].value
                p['plot'].set_color(p['color'])
                linestyle = self.linestyles[pp['linestyle'].value]
                p['linewidth'] = pp['linewidth'].value
                p['plot'].set_linestyle(linestyle)
                p['plot'].set_linewidth(p['linewidth'])
                marker = [k for k, v in self.markers.items()
                          if v == pp['marker'].value][0]
                p['marker'] = marker
                p['plot'].set_marker(marker)
                p['markersize'] = pp['markersize'].value
                p['plot'].set_markersize(p['markersize'])
                p['markerstyle'] = pp['markerstyle'].value
                if p['markerstyle'] == 'open':
                    p['plot'].set_markerfacecolor('#ffffff')
                else:
                    p['plot'].set_markerfacecolor(p['color'])
                p['plot'].set_markeredgecolor(p['color'])
                p['zorder'] = pp['zorder'].value
                p['plot'].set_zorder(p['zorder'])
                p['scale'] = pp['scale'].value
                p['offset'] = pp['offset'].value
                if p['smooth_line']:
                    if linestyle == 'None':
                        p['smooth_linestyle'] = '-'
                    else:
                        p['smooth_linestyle'] = linestyle
                    p['smooth_line'].set_color(p['color'])
                    p['smooth_line'].set_linewidth(p['linewidth'])
                else:
                    p['linestyle'] = linestyle
            self.set_legend()
            for plot in self.plots:
                p = self.plots[plot]
                if p['smooth_line']:
                    p['plot'].set_linestyle('None')
                    p['smooth_line'].set_linestyle(p['smooth_linestyle'])
        self.set_grid()
        self.update()
        self.plotview.draw()


class StyleDialog(NXPanel):

    def __init__(self, parent=None):
        super().__init__('Style', title='Style Panel', parent=parent)
        self.tab_class = StyleTab
        self.plotview_sort = True


class StyleTab(NXTab):

    def __init__(self, label, parent=None):
        super().__init__(label, parent=parent)

        self.plotview = self.active_plotview

        self.parameters = {}
        pl = self.parameters['labels'] = self.label_parameters()
        self.update_label_parameters()
        pf = self.parameters['fonts'] = self.font_parameters()
        self.update_font_parameters()
        self.set_layout(
            pl.grid(header=False, width=250),
            self.make_layout(pf.grid(header=False, width=100), align='center'),
            self.action_buttons(('Make Sizes Default', self.save_default)),
            self.action_buttons(('Adjust Layout', self.adjust_layout),
                                ('Tighten Layout', self.tight_layout),
                                ('Reset Layout', self.reset_layout)))
        self.set_title('Plot Style')

    def label_parameters(self):
        p = GridParameters()
        p.add('title', self.plotview.title, 'Title')
        p.add('xlabel', self.plotview.xaxis.label, 'X-Axis Label')
        p.add('ylabel', self.plotview.yaxis.label, 'Y-Axis Label')
        p.grid(title='Plot Labels', header=False, width=200)
        return p

    def update_label_parameters(self):
        p = self.parameters['labels']
        p['title'].value = self.plotview.title
        p['xlabel'].value = self.plotview.xaxis.label
        p['ylabel'].value = self.plotview.yaxis.label

    def font_parameters(self):
        p = GridParameters()
        p.add('title', 0, 'Title Font Size')
        p.add('xlabel', 0, 'X-Label Font Size')
        p.add('ylabel', 0, 'Y-Label Font Size')
        p.add('ticks', 0, 'Tick Font Size')
        if self.plotview.image is not None:
            p.add('colorbar', 10, 'Colorbar Font Size')
        return p

    def update_font_parameters(self):
        p = self.parameters['fonts']
        p['title'].value = self.plotview.ax.title.get_fontsize()
        p['xlabel'].value = self.plotview.ax.xaxis.label.get_fontsize()
        p['ylabel'].value = self.plotview.ax.yaxis.label.get_fontsize()
        p['ticks'].value = self.plotview.ax.get_xticklabels()[0].get_fontsize()
        if self.plotview.colorbar is not None:
            p['colorbar'].value = (
                self.plotview.colorbar.ax.get_yticklabels()[0].get_fontsize())

    def update(self):
        self.update_label_parameters()
        self.update_font_parameters()

    def tight_layout(self):
        pars = self.plotview.figure.subplotpars
        self.previous_layout = {'left': pars.left, 'right': pars.right,
                                'bottom': pars.bottom, 'top': pars.right}
        self.plotview.figure.tight_layout()
        self.plotview.draw()

    def reset_layout(self):
        self.plotview.figure.subplots_adjust(**self.previous_layout)
        self.plotview.draw()

    def adjust_layout(self):
        pars = self.plotview.figure.subplotpars
        self.previous_layout = {'left': pars.left, 'right': pars.right,
                                'bottom': pars.bottom, 'top': pars.right}
        self.plotview.otab.configure_subplots()

    def save_default(self):
        p = self.parameters['fonts']
        mpl.rcParams['axes.titlesize'] = p['title'].value
        mpl.rcParams['axes.labelsize'] = p['xlabel'].value
        mpl.rcParams['xtick.labelsize'] = p['ticks'].value
        mpl.rcParams['ytick.labelsize'] = p['ticks'].value
        self.apply()

    def apply(self):
        pl = self.parameters['labels']
        self.plotview.title = pl['title'].value
        self.plotview.ax.set_title(self.plotview.title)
        self.plotview.xaxis.label = pl['xlabel'].value
        self.plotview.ax.set_xlabel(self.plotview.xaxis.label)
        self.plotview.yaxis.label = pl['ylabel'].value
        self.plotview.ax.set_ylabel(self.plotview.yaxis.label)
        pf = self.parameters['fonts']
        self.plotview.ax.title.set_fontsize(pf['title'].value)
        self.plotview.ax.xaxis.label.set_fontsize(pf['xlabel'].value)
        self.plotview.ax.yaxis.label.set_fontsize(pf['ylabel'].value)
        tick_size = pf['ticks'].value
        for label in self.plotview.ax.get_xticklabels():
            label.set_fontsize(tick_size)
        for label in self.plotview.ax.get_yticklabels():
            label.set_fontsize(tick_size)
        if self.plotview.colorbar is not None:
            cb_size = pf['colorbar'].value
            for label in self.plotview.colorbar.ax.get_yticklabels():
                label.set_fontsize(cb_size)
        self.plotview.draw()


class ProjectionDialog(NXPanel):
    """Dialog to set plot window limits"""

    def __init__(self, parent=None):
        super().__init__('Projection', title='Projection Panel', apply=False,
                         parent=parent)
        self.tab_class = ProjectionTab
        self.plotview_sort = True


class ProjectionTab(NXTab):
    """Tab to set plot window limits"""

    def __init__(self, label, parent=None):

        super().__init__(label, parent=parent)

        self.plotview = self.active_plotview
        self.ndim = self.plotview.ndim

        self.xlabel, self.xbox = (self.label('X-Axis'),
                                  NXComboBox(self.set_xaxis))
        self.ylabel, self.ybox = (self.label('Y-Axis'),
                                  NXComboBox(self.set_yaxis))
        axis_layout = self.make_layout(self.xlabel, self.xbox,
                                       self.ylabel, self.ybox)

        self.set_axes()

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        headers = ['Axis', 'Minimum', 'Maximum', 'Lock']
        width = [50, 100, 100, 25]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            grid.addWidget(label, 0, column)
            grid.setColumnMinimumWidth(column, width[column])
            column += 1

        row = 0
        self.minbox = {}
        self.maxbox = {}
        self.lockbox = {}
        for axis in range(self.ndim):
            row += 1
            self.minbox[axis] = NXSpinBox(self.set_limits)
            self.maxbox[axis] = NXSpinBox(self.set_limits)
            self.lockbox[axis] = NXCheckBox(slot=self.set_lock)
            grid.addWidget(self.label(self.plotview.axis[axis].name), row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)
            grid.addWidget(self.lockbox[axis], row, 3,
                           alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.save_button = NXPushButton("Save", self.save_projection, self)
        grid.addWidget(self.save_button, row, 1)
        self.plot_button = NXPushButton("Plot", self.plot_projection, self)
        grid.addWidget(self.plot_button, row, 2)
        self.overbox = NXCheckBox()
        if self.ndim > 1 or self.plot is None or self.plot.ndim > 1:
            self.overbox.setVisible(False)
        grid.addWidget(self.overbox, row, 3, alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.mask_button = NXPushButton("Mask", self.mask_data, self)
        grid.addWidget(self.mask_button, row, 1)
        self.unmask_button = NXPushButton("Unmask", self.unmask_data, self)
        grid.addWidget(self.unmask_button, row, 2)

        self.select_widget = NXWidget()
        sp = self.select_parameters = GridParameters()
        sp.add('divisor', 1.0, 'Divisor')
        sp.add('offset', 0.0, 'Offset')
        sp.add('tol', 0.0, 'Tolerance')
        self.select_widget.set_layout(
            sp.grid(header=False),
            self.checkboxes(("smooth", "Smooth", False),
                            ("symm", "Symmetric", False),
                            ("max", "Max", False),
                            ("min", "Min", False)))
        self.select_widget.setVisible(False)
        self.set_layout(axis_layout, grid,
                        self.checkboxes(("sum", "Sum Projections", False),
                                        ("hide", "Hide Limits", False),
                                        ("weights", "Weight Data", False)),
                        self.checkboxes(("lines", "Plot Lines", False),
                                        ("select", "Plot Selection", False)),
                        self.select_widget,
                        self.copy_layout("Copy Limits"))
        self.checkbox["lines"].setVisible(False)
        self.checkbox["select"].setVisible(False)
        if self.plotview.data.nxweights is None:
            self.checkbox["weights"].setVisible(False)
        elif self.plotview.weighted:
            self.checkbox["weights"].setChecked(True)
        self.checkbox["hide"].stateChanged.connect(self.hide_rectangle)
        self.checkbox["select"].stateChanged.connect(self.set_select)
        self.checkbox["max"].stateChanged.connect(self.set_maximum)
        self.checkbox["min"].stateChanged.connect(self.set_minimum)

        self.initialize()
        self._rectangle = None
        self.xbox.setFocus()

    def initialize(self):
        for axis in range(self.ndim):
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.axis[axis].centers
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.minbox[axis].diff = self.maxbox[axis].diff = None
            self.block_signals(True)
            self.minbox[axis].setValue(self.plotview.axis[axis].lo)
            self.maxbox[axis].setValue(self.plotview.axis[axis].hi)
            self.block_signals(False)

        self.copywidget.setVisible(False)
        for tab in [self.tabs[label] for label in self.tabs
                    if self.tabs[label] is not self]:
            if self.plotview.ndim == tab.plotview.ndim:
                self.copywidget.setVisible(True)
                self.copybox.add(self.labels[tab])
                tab.copybox.add(self.tab_label)
                if not tab.copywidget.isVisible():
                    tab.copywidget.setVisible(True)

    def get_axes(self):
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        axes = self.get_axes()
        self.xbox.clear()
        self.xbox.add(*axes)
        self.xbox.select(self.plotview.xaxis.name)
        if self.ndim <= 2:
            self.ylabel.setVisible(False)
            self.ybox.setVisible(False)
        else:
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            axes.insert(0, 'None')
            self.ybox.add(*axes)
            self.ybox.select(self.plotview.yaxis.name)

    @property
    def xaxis(self):
        return self.xbox.currentText()

    def set_xaxis(self):
        if self.xaxis == self.yaxis:
            self.ybox.select('None')
        self.update_overbox()

    @property
    def yaxis(self):
        if self.ndim <= 2:
            return 'None'
        else:
            return self.ybox.selected
        self.update_overbox()

    def set_yaxis(self):
        if self.yaxis == self.xaxis:
            for idx in range(self.xbox.count()):
                if self.xbox.itemText(idx) != self.yaxis:
                    self.xbox.setCurrentIndex(idx)
                    break
        if self.yaxis == 'None':
            if self.plot and self.plot.ndim == 1:
                self.overbox.setVisible(True)
            self.checkbox["lines"].setVisible(True)
            self.checkbox["select"].setVisible(True)
            self.set_select()
        else:
            self.overbox.setChecked(False)
            self.overbox.setVisible(False)
            self.checkbox["lines"].setVisible(False)
            self.checkbox["select"].setVisible(False)
            self.select_widget.setVisible(False)
        self.panel.update()

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
            return self.checkbox["sum"].isChecked()
        except Exception:
            return False

    @summed.setter
    def summed(self, value):
        self.checkbox["sum"].setChecked(value)

    @property
    def lines(self):
        try:
            return self.checkbox["lines"].isChecked()
        except Exception:
            return False

    @lines.setter
    def lines(self, value):
        self.checkbox["lines"].setChecked(value)

    @property
    def over(self):
        return self.overbox.isChecked()

    @over.setter
    def over(self, value):
        self.overbox.setVisible(True)
        self.overbox.setChecked(value)

    @property
    def weights(self):
        return self.checkbox["weights"].isChecked()

    @property
    def select(self):
        return self.checkbox["select"].isChecked()

    def set_select(self):
        if self.checkbox["select"].isChecked():
            self.select_widget.setVisible(True)
        else:
            self.select_widget.setVisible(False)
        self.panel.update()

    def set_maximum(self):
        if self.checkbox["max"].isChecked():
            self.checkbox["min"].setChecked(False)

    def set_minimum(self):
        if self.checkbox["min"].isChecked():
            self.checkbox["max"].setChecked(False)

    def get_projection(self):
        x = self.get_axes().index(self.xaxis)
        if self.yaxis == 'None':
            axes = [x]
        else:
            y = self.get_axes().index(self.yaxis)
            axes = [y, x]
        limits = self.get_limits()
        shape = self.plotview.data.nxsignal.shape
        if (len(shape)-len(limits) > 0 and
                len(shape)-len(limits) == shape.count(1)):
            axes, limits = fix_projection(shape, axes, limits)
        elif any([limits[axis][1]-limits[axis][0] <= 1 for axis in axes]):
            raise NeXusError("One of the projection axes has zero range")
        if self.plotview.rgb_image:
            limits.append((None, None))
        data = self.plotview.data.project(axes, limits, summed=self.summed)
        if self.select:
            divisor = self.select_parameters['divisor'].value
            offset = self.select_parameters['offset'].value
            tol = self.select_parameters['tol'].value
            symmetric = self.checkbox['symm'].isChecked()
            smooth = self.checkbox['smooth'].isChecked()
            maxima = self.checkbox['max'].isChecked()
            minima = self.checkbox['min'].isChecked()
            return data.select(divisor, offset, symmetric, smooth,
                               maxima, minima, tol)
        else:
            return data

    def save_projection(self):
        try:
            keep_data(self.get_projection())
        except NeXusError as error:
            report_error("Saving Projection", error)

    def plot_projection(self):
        try:
            projection = self.get_projection()
            if self.plot:
                plotview = self.plot
            else:
                from .plotview import NXPlotView
                plotview = NXPlotView('Projection')
                self.over = False
            if self.lines:
                fmt = '-'
            else:
                fmt = 'o'
            plotview.plot(projection, weights=self.weights, over=self.over,
                          fmt=fmt)
            self.update_overbox()
            if plotview.ndim > 1:
                plotview.logv = self.plotview.logv
                plotview.cmap = self.plotview.cmap
                plotview.interpolation = self.plotview.interpolation
            plotview.make_active()
            plotview.raise_()
        except NeXusError as error:
            report_error("Plotting Projection", error)

    @property
    def plot(self):
        if 'Projection' in self.plotviews:
            return self.plotviews['Projection']
        else:
            return None

    def mask_data(self):
        try:
            limits = tuple(slice(x, y) for x, y in self.get_limits())
            self.plotview.data.nxsignal[limits] = np.ma.masked
            self.plotview.replot_data()
        except NeXusError as error:
            report_error("Masking Data", error)

    def unmask_data(self):
        try:
            limits = tuple(slice(x, y) for x, y in self.get_limits())
            self.plotview.data.nxsignal.mask[limits] = np.ma.nomask
            if not self.plotview.data.nxsignal.mask.any():
                self.plotview.data.mask = np.ma.nomask
            self.plotview.replot_data()
        except NeXusError as error:
            report_error("Masking Data", error)

    def block_signals(self, block=True):
        for axis in range(self.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)

    @property
    def rectangle(self):
        if self._rectangle not in self.plotview.ax.patches:
            self._rectangle = NXpolygon(self.get_rectangle(), closed=True,
                                        plotview=self.plotview).shape
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
        xy = [(x0, y0), (x0, y1), (x1, y1), (x1, y0)]
        if self.plotview.skew is not None:
            return [self.plotview.transform(_x, _y) for _x, _y in xy]
        else:
            return xy

    def draw_rectangle(self):
        self.rectangle.set_xy(self.get_rectangle())
        self.plotview.draw()

    def rectangle_visible(self):
        return not self.checkbox["hide"].isChecked()

    def hide_rectangle(self):
        if self.checkbox["hide"].isChecked():
            self.rectangle.set_visible(False)
        else:
            self.rectangle.set_visible(True)
        self.plotview.draw()

    def update_overbox(self):
        if 'Projection' in self.plotviews:
            ndim = self.plotviews['Projection'].ndim
        else:
            ndim = 0
        for tab in self.labels:
            if ndim == 1 and tab.yaxis == 'None':
                tab.overbox.setVisible(True)
            else:
                tab.overbox.setVisible(False)
                tab.overbox.setChecked(False)

    def update(self):
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
                if hi < maxbox.value():
                    maxbox.setValue(maxbox.valueFromIndex(ihi))
        self.block_signals(False)
        self.draw_rectangle()
        self.sort_copybox()

    def copy(self):
        self.block_signals(True)
        tab = self.tabs[self.copybox.selected]
        for axis in range(self.ndim):
            self.minbox[axis].setValue(tab.minbox[axis].value())
            self.maxbox[axis].setValue(tab.maxbox[axis].value())
            self.lockbox[axis].setCheckState(tab.lockbox[axis].checkState())
        self.summed = tab.summed
        self.lines = tab.lines
        self.xbox.select(tab.xbox.selected)
        self.ybox.select(tab.ybox.selected)
        self.block_signals(False)
        self.draw_rectangle()
        self.update_overbox()

    def reset(self):
        self.block_signals(True)
        for axis in range(self.ndim):
            if (self.plotview.axis[axis] is self.plotview.xaxis or
                    self.plotview.axis[axis] is self.plotview.yaxis):
                self.minbox[axis].setValue(self.minbox[axis].data.min())
                self.maxbox[axis].setValue(self.maxbox[axis].data.max())
            else:
                lo, hi = self.plotview.axis[axis].get_limits()
                minbox, maxbox = self.minbox[axis], self.maxbox[axis]
                ilo, ihi = minbox.indexFromValue(lo), maxbox.indexFromValue(hi)
                minbox.setValue(minbox.valueFromIndex(ilo))
                maxbox.setValue(maxbox.valueFromIndex(ihi))
        self.block_signals(False)
        self.update()

    def close(self):
        try:
            if self._rectangle:
                self._rectangle.remove()
            self.plotview.draw()
        except Exception:
            pass


class LimitDialog(NXPanel):
    """Dialog to set plot window limits"""

    def __init__(self, parent=None):
        super().__init__('Limits', title='Limits Panel', parent=parent)
        self.tab_class = LimitTab
        self.plotview_sort = True


class LimitTab(NXTab):
    """Tab to set plot window limits"""

    def __init__(self, label, parent=None):

        super().__init__(label, parent=parent)

        self.plotview = self.active_plotview
        self.ndim = self.plotview.ndim

        if self.ndim > 1:
            self.xlabel, self.xbox = (self.label('X-Axis'),
                                      NXComboBox(self.set_xaxis))
            self.ylabel, self.ybox = (self.label('Y-Axis'),
                                      NXComboBox(self.set_yaxis))
            axis_layout = self.make_layout(self.xlabel, self.xbox,
                                           self.ylabel, self.ybox)
            self.set_axes()
        else:
            axis_layout = None

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        headers = ['Axis', 'Minimum', 'Maximum', 'Lock']
        width = [50, 100, 100, 25]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            grid.addWidget(label, 0, column)
            grid.setColumnMinimumWidth(column, width[column])
            column += 1

        row = 0
        self.minbox = {}
        self.maxbox = {}
        self.lockbox = {}
        for axis in range(self.ndim):
            row += 1
            self.minbox[axis] = NXSpinBox(self.set_limits)
            self.maxbox[axis] = NXSpinBox(self.set_limits)
            self.lockbox[axis] = NXCheckBox(slot=self.set_lock)
            grid.addWidget(self.label(self.plotview.axis[axis].name), row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)
            grid.addWidget(self.lockbox[axis], row, 3,
                           alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.minbox['signal'] = NXDoubleSpinBox()
        self.maxbox['signal'] = NXDoubleSpinBox()
        self.lockbox['signal'] = NXCheckBox()
        grid.addWidget(self.label(self.plotview.axis['signal'].name), row, 0)
        grid.addWidget(self.minbox['signal'], row, 1)
        grid.addWidget(self.maxbox['signal'], row, 2)
        grid.addWidget(self.lockbox['signal'], row, 3,
                       alignment=QtCore.Qt.AlignHCenter)

        self.parameters = GridParameters()
        figure_size = self.plotview.figure.get_size_inches()
        xsize, ysize = figure_size[0], figure_size[1]
        self.parameters.add('xsize', xsize, 'Figure Size (H)')
        self.parameters.add('ysize', ysize, 'Figure Size (V)')
        if self.tab_label == 'Main':
            self.parameters['xsize'].box.setEnabled(False)
            self.parameters['ysize'].box.setEnabled(False)
        self.set_layout(axis_layout, grid,
                        self.parameters.grid(header=False),
                        self.copy_layout("Copy Limits", 'sync'))

        self.checkbox['sync'].stateChanged.connect(self.choose_sync)

        self.initialize()

    def initialize(self):
        for axis in range(self.ndim):
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.axis[axis].centers
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.minbox[axis].diff = self.maxbox[axis].diff = None
            self.block_signals(True)
            self.minbox[axis].setValue(self.plotview.axis[axis].lo)
            self.maxbox[axis].setValue(self.plotview.axis[axis].hi)
            self.block_signals(False)
        self.update_signal()
        self.update_properties()
        self.copied_properties = {}
        self.copywidget.setVisible(False)
        for tab in [self.tabs[label] for label in self.tabs
                    if self.tabs[label] is not self]:
            if self.plotview.ndim == tab.plotview.ndim:
                self.copywidget.setVisible(True)
                self.copybox.add(self.labels[tab])
                tab.copybox.add(self.tab_label)
                if not tab.copywidget.isVisible():
                    tab.copywidget.setVisible(True)

    def get_axes(self):
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        if self.ndim > 1:
            axes = self.get_axes()
            self.xbox.clear()
            self.xbox.add(*axes)
            self.xbox.select(self.plotview.xaxis.name)
            self.ylabel.setVisible(True)
            self.ybox.setVisible(True)
            self.ybox.clear()
            self.ybox.add(*axes)
            self.ybox.select(self.plotview.yaxis.name)

    @property
    def xaxis(self):
        return self.xbox.selected

    def set_xaxis(self):
        if self.xaxis == self.yaxis:
            if self.yaxis == self.plotview.yaxis.name:
                self.ybox.select(self.plotview.xaxis.name)
            else:
                self.ybox.select(self.plotview.yaxis.name)

    @property
    def yaxis(self):
        return self.ybox.selected

    def set_yaxis(self):
        if self.yaxis == self.xaxis:
            if self.xaxis == self.plotview.xaxis.name:
                self.xbox.select(self.plotview.yaxis.name)
            else:
                self.xbox.select(self.plotview.xaxis.name)

    def set_limits(self):
        self.block_signals(True)
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                min_value = self.maxbox[axis].value() - self.maxbox[axis].diff
                self.minbox[axis].setValue(min_value)
            elif self.minbox[axis].value() > self.maxbox[axis].value():
                self.maxbox[axis].setValue(self.minbox[axis].value())
        self.block_signals(False)

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

    def block_signals(self, block=True):
        for axis in range(self.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)
        self.minbox['signal'].blockSignals(block)
        self.maxbox['signal'].blockSignals(block)

    def choose_sync(self):
        if self.checkbox['sync'].isChecked():
            tab = self.tabs[self.copybox.selected]
            tab.checkbox['sync'].setChecked(False)

    def update(self):
        if self.checkbox['sync'].isChecked():
            if self.lockbox['signal'].isChecked():
                self.update_signal()
        else:
            self.update_limits()
            self.update_properties()
        for tab in [self.tabs[label] for label in self.tabs
                    if self.tabs[label] is not self]:
            if (tab.copybox.selected == self.tab_label and
                    tab.checkbox['sync'].isChecked()):
                tab.copy()
        self.sort_copybox()

    def update_limits(self):
        self.block_signals(True)
        self.set_axes()
        for axis in range(self.ndim):
            self.lockbox[axis].setChecked(False)
            self.minbox[axis].setValue(self.plotview.axis[axis].lo)
            self.maxbox[axis].setValue(self.plotview.axis[axis].hi)
        self.update_signal()
        figure_size = self.plotview.figure.get_size_inches()
        self.parameters['xsize'].value = figure_size[0]
        self.parameters['ysize'].value = figure_size[1]
        self.block_signals(False)

    def update_signal(self):
        minbox, maxbox = self.plotview.vtab.minbox, self.plotview.vtab.maxbox
        self.minbox['signal'].setRange(minbox.minimum(), minbox.maximum())
        self.maxbox['signal'].setRange(maxbox.minimum(), maxbox.maximum())
        self.minbox['signal'].setSingleStep(minbox.singleStep())
        self.maxbox['signal'].setSingleStep(maxbox.singleStep())
        self.minbox['signal'].setValue(minbox.value())
        self.maxbox['signal'].setValue(maxbox.value())

    def update_properties(self):
        if self.ndim > 1:
            self.properties = {'aspect': self.plotview.aspect,
                               'cmap': self.plotview.cmap,
                               'interpolation': self.plotview.interpolation,
                               'logv': self.plotview.logv,
                               'logx': self.plotview.logx,
                               'logy': self.plotview.logy,
                               'skew': self.plotview.skew}
        else:
            self.properties = {}

    def copy_properties(self, tab):
        self.update_properties()
        for p in self.properties:
            if self.properties[p] != tab.properties[p]:
                self.copied_properties[p] = tab.properties[p]

    def copy(self):
        tab = self.tabs[self.copybox.selected]
        self.copy_properties(tab)
        self.block_signals(True)
        self.xbox.select(self.get_axes()[tab.get_axes().index(tab.xaxis)])
        self.ybox.select(self.get_axes()[tab.get_axes().index(tab.yaxis)])
        for axis in range(self.ndim):
            self.minbox[axis].setValue(tab.minbox[axis].value())
            self.maxbox[axis].setValue(tab.maxbox[axis].value())
            self.lockbox[axis].setCheckState(tab.lockbox[axis].checkState())
        if not self.lockbox['signal'].isChecked():
            self.plotview.autoscale = False
            self.minbox['signal'].setValue(tab.minbox['signal'].value())
            self.maxbox['signal'].setValue(tab.maxbox['signal'].value())
        if self.tab_label != 'Main':
            self.parameters['xsize'].value = tab.parameters['xsize'].value
            self.parameters['ysize'].value = tab.parameters['ysize'].value
        self.apply()
        self.block_signals(False)

    def reset(self):
        self.plotview.otab.home()
        self.update()

    def apply(self):
        try:
            self.block_signals(True)
            if self.tab_label != 'Main':
                xsize, ysize = (self.parameters['xsize'].value,
                                self.parameters['ysize'].value)
                self.plotview.figure.set_size_inches(xsize, ysize)
            if self.ndim == 1:
                xmin, xmax = self.minbox[0].value(), self.maxbox[0].value()
                ymin, ymax = (self.minbox['signal'].value(),
                              self.maxbox['signal'].value())
                if np.isclose(xmin, xmax):
                    raise NeXusError('X-axis has zero range')
                elif np.isclose(ymin, ymax):
                    raise NeXusError('Y-axis has zero range')
                self.plotview.xtab.set_limits(xmin, xmax)
                self.plotview.ytab.set_limits(ymin, ymax)
                self.plotview.replot_axes()
            else:
                limits = []
                for axis in range(self.ndim):
                    limits.append((self.minbox[axis].value(),
                                   self.maxbox[axis].value()))
                x = self.get_axes().index(self.xaxis)
                xmin, xmax = limits[x][0], limits[x][1]
                y = self.get_axes().index(self.yaxis)
                ymin, ymax = limits[y][0], limits[y][1]
                vmin, vmax = (self.minbox['signal'].value(),
                              self.maxbox['signal'].value())
                if np.isclose(xmin, xmax):
                    raise NeXusError('X-axis has zero range')
                elif np.isclose(ymin, ymax):
                    raise NeXusError('Y-axis has zero range')
                self.plotview.change_axis(self.plotview.xtab,
                                          self.plotview.axis[x])
                self.plotview.change_axis(self.plotview.ytab,
                                          self.plotview.axis[y])
                self.plotview.xtab.set_limits(xmin, xmax)
                self.plotview.ytab.set_limits(ymin, ymax)
                self.plotview.vtab.set_limits(vmin, vmax)
                if self.ndim > 2:
                    self.plotview.ztab.locked = False
                    names = [self.plotview.axis[i].name
                             for i in range(self.ndim)]
                    for axis_name in self.plotview.ztab.axiscombo.items():
                        self.plotview.ztab.axiscombo.select(axis_name)
                        z = names.index(self.plotview.ztab.axiscombo.selected)
                        zmin, zmax = limits[z][0], limits[z][1]
                        self.plotview.ztab.set_axis(self.plotview.axis[z])
                        self.plotview.ztab.set_limits(zmin, zmax)
                self.plotview.replot_data()
                for p in self.copied_properties:
                    setattr(self.plotview, p, self.copied_properties[p])
                self.copied_properties = {}
            self.block_signals(False)
        except NeXusError as error:
            report_error("Setting plot limits", error)
            self.block_signals(False)

    def close(self):
        for tab in [self.tabs[label] for label in self.tabs
                    if self.tabs[label] is not self]:
            if (tab.copybox.selected == self.tab_label and
                    tab.checkbox['sync'].isChecked()):
                tab.checkbox['sync'].setChecked(False)
            if self.tab_label in tab.copybox:
                tab.copybox.remove(self.tab_label)
            if len(tab.copybox.items()) == 0:
                tab.copywidget.setVisible(False)


class ScanDialog(NXPanel):
    """Dialog to set plot window limits"""

    def __init__(self, parent=None):
        super().__init__('Scan', title='Scan Panel', apply=False,
                         reset=False, parent=parent)
        self.tab_class = ScanTab
        self.plotview_sort = True


class ScanTab(NXTab):
    """Tab to generate parametric scans."""

    def __init__(self, label, parent=None):

        super().__init__(label, parent=parent)

        self.set_layout(
            self.textboxes(('Scan', '')),
            self.action_buttons(('Select Scan', self.select_scan),
                                ('Select Files', self.select_files)),
            self.action_buttons(('Plot', self.plot_scan),
                                ('Copy', self.copy_scan),
                                ('Save', self.save_scan)))
        self.file_box = None
        self.scan_files = None
        self.scan_values = None
        self.scan_data = None
        self.files = None

    def select_scan(self):
        scan_axis = self.treeview.node
        if not isinstance(scan_axis, NXfield):
            display_message("Scan Panel", "Scan axis must be a NXfield")
        elif scan_axis.shape != () and scan_axis.shape != (1,):
            display_message("Scan Panel", "Scan axis must be a scalar")
        else:
            self.textbox['Scan'].setText(self.treeview.node.nxpath)

    def select_files(self):
        if self.file_box in self.mainwindow.dialogs:
            try:
                self.file_box.close()
            except Exception:
                pass
        self.file_box = NXDialog(parent=self)
        self.file_box.setWindowTitle('Select Files')
        self.file_box.setMinimumWidth(300)
        self.prefix_box = NXLineEdit()
        self.prefix_box.textChanged.connect(self.select_prefix)
        prefix_layout = self.make_layout(NXLabel('Prefix'), self.prefix_box)
        self.scroll_area = NXScrollArea()
        self.files = GridParameters()
        i = 0
        for name in sorted(self.tree, key=natural_sort):
            root = self.tree[name]
            try:
                if (self.data_path in root and
                        root[self.data_path].nxsignal.exists()):
                    i += 1
                    if self.scan_path:
                        self.files.add(name, root[self.scan_path], name, True)
                    else:
                        self.files.add(name, i, name, True)
                        self.files[name].checkbox.stateChanged.connect(
                            self.update_files)
            except Exception as error:
                pass
        self.file_grid = self.files.grid(header=('File', self.scan_header, ''))
        self.scroll_widget = NXWidget()
        self.scroll_widget.set_layout(self.make_layout(self.file_grid))
        self.scroll_area.setWidget(self.scroll_widget)
        self.file_box.set_layout(prefix_layout, self.scroll_area,
                                 self.file_box.close_layout())
        self.file_box.close_box.accepted.connect(self.choose_files)
        self.file_box.show()

    def select_prefix(self):
        prefix = self.prefix_box.text()
        self.files = GridParameters()
        i = 0
        for name in [n for n in sorted(self.tree, key=natural_sort)
                     if n.startswith(prefix)]:
            root = self.tree[name]
            if (self.data_path in root and
                    root[self.data_path].nxsignal.exists()):
                i += 1
                if self.scan_path in root:
                    self.files.add(name, root[self.scan_path], name, True)
                else:
                    self.files.add(name, i, name, True)
                    self.files[name].checkbox.stateChanged.connect(
                        self.update_files)
        self.file_grid = self.files.grid(header=('File', self.scan_header, ''))
        self.scroll_widget.deleteLater()
        self.scroll_widget = NXWidget()
        self.scroll_widget.set_layout(self.make_layout(self.file_grid))
        self.scroll_area.setWidget(self.scroll_widget)

    def update_files(self):
        if self.scan_path:
            i = 0
            for f in self.files:
                if self.files[f].vary:
                    i += 1
                    self.files[f].value = i
                else:
                    self.files[f].value = ''

    @property
    def data_path(self):
        return self.plotview.data.nxpath

    @property
    def scan_path(self):
        return self.textbox['Scan'].text()

    @property
    def scan_variable(self):
        if self.scan_path and self.scan_path in self.plotview.data.nxroot:
            return self.plotview.data.nxroot[self.scan_path]
        else:
            return None

    @property
    def scan_header(self):
        if self.scan_path and self.scan_path in self.plotview.data.nxroot:
            return (
                self.plotview.data.nxroot[self.scan_path].nxname.capitalize())
        else:
            return 'Variable'

    def choose_files(self):
        try:
            self.scan_files = [self.tree[self.files[f].name]
                               for f in self.files if self.files[f].vary]
            self.scan_values = [self.files[f].value for f in self.files
                                if self.files[f].vary]
            self.scan_data = nxconsolidate(self.scan_files, self.data_path,
                                           self.scan_path)
        except Exception:
            raise NeXusError("Files not selected")

    def plot_scan(self):
        try:
            self.scanview.plot(self.scan_data)
            self.scanview.make_active()
            self.scanview.raise_()
        except NeXusError as error:
            report_error("Plotting Scan", error)

    def copy_scan(self):
        try:
            self.mainwindow.copied_node = self.mainwindow.copy_node(
                self.scan_data)
        except NeXusError as error:
            report_error("Copying Scan", error)

    def save_scan(self):
        try:
            keep_data(self.scan_data)
        except NeXusError as error:
            report_error("Saving Scan", error)

    @property
    def scanview(self):
        if 'Scan' in self.plotviews:
            return self.plotviews['Scan']
        else:
            from .plotview import NXPlotView
            return NXPlotView('Scan')

    def close(self):
        try:
            self.file_box.close()
        except Exception:
            pass
        super().close()


class ViewDialog(NXPanel):
    """Dialog to view a NeXus field"""

    def __init__(self, parent=None):
        super().__init__('View', title='View Panel', apply=False, reset=False,
                         parent=parent)
        self.tab_class = ViewTab

    def activate(self, node):
        label = node.nxroot.nxname + node.nxpath
        if label not in self.tabs:
            tab = ViewTab(label, node, parent=self)
            self.add(label, tab, idx=self.idx(label))
        else:
            self.tab = label
        self.setVisible(True)
        self.raise_()
        self.activateWindow()


class ViewTab(NXTab):

    def __init__(self, label, node, parent=None):

        super().__init__(label, parent=parent)

        self.node = node
        self.spinboxes = []

        layout = QtWidgets.QVBoxLayout()
        self.properties = GridParameters()

        self.properties.add('class', node.__class__.__name__, 'Class')
        self.properties.add('name', node.nxname, 'Name')
        self.properties.add('path', node.nxpath, 'Path')
        if node.nxroot.nxfilename:
            self.properties.add('file', node.nxroot.nxfilename, 'File')
        target_path_label = 'Target Path'
        target_error = None
        if node.file_exists():
            target_file_label = 'Target File'
            if not node.path_exists():
                target_path_label = 'Target Path*'
                target_error = '* Target path does not exist'
        else:
            target_file_label = 'Target File*'
            target_error = '* Target file does not exist'
        if isinstance(node, NXlink):
            self.properties.add('target', node._target, target_path_label)
            if node._filename:
                self.properties.add('linkfile', node._filename,
                                    target_file_label)
            elif node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
                self.properties.add('linkfile', node.nxfilename,
                                    target_file_label)
        elif isinstance(node, NXvirtualfield):
            self.properties.add('vpath', node._vpath, 'Virtual Path')
            self.properties.add('vfiles', node._vfiles, 'Virtual Files')
        elif node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
            self.properties.add('target', node.nxfilepath, 'Target Path')
            self.properties.add('linkfile', node.nxfilename, target_file_label)
        if node.nxfilemode:
            self.properties.add('filemode', node.nxfilemode, 'Mode')
        if target_error:
            pass
        elif isinstance(node, NXfield) and node.shape is not None:
            if node.shape == () or node.shape == (1,):
                self.properties.add('value', str(node), 'Value')
            self.properties.add('dtype', node.dtype, 'Dtype')
            self.properties.add('shape', str(node.shape), 'Shape')
            self.properties.add('maxshape', str(node.maxshape),
                                'Maximum Shape')
            self.properties.add('fillvalue', str(node.fillvalue), 'Fill Value')
            self.properties.add('chunks', str(node.chunks), 'Chunk Size')
            self.properties.add('compression', str(node.compression),
                                'Compression')
            self.properties.add('compression_opts', str(node.compression_opts),
                                'Compression Options')
            self.properties.add('shuffle', str(node.shuffle), 'Shuffle Filter')
            self.properties.add('fletcher32', str(node.fletcher32),
                                'Fletcher32 Filter')
        elif isinstance(node, NXgroup):
            self.properties.add('entries', len(node.entries), 'No. of Entries')
        layout.addLayout(self.properties.grid(header=False,
                                              title='Properties',
                                              width=200))
        if target_error:
            layout.addWidget(NXLabel(target_error))

        if node.attrs:
            self.attributes = GridParameters()
            for attr in node.attrs:
                self.attributes.add(attr, str(node.attrs[attr]), attr)
            layout.addLayout(self.attributes.grid(header=False,
                                                  title='Attributes',
                                                  width=200))

        hlayout = QtWidgets.QHBoxLayout()
        hlayout.addStretch()
        hlayout.addLayout(layout)
        if (isinstance(node, NXfield) and node.shape is not None and
                node.shape != () and node.shape != (1,)):
            try:
                table = self.table()
                hlayout.addLayout(table)
            except OSError:
                pass
        hlayout.addStretch()
        self.setLayout(hlayout)

        self.setWindowTitle(node.nxroot.nxname+node.nxpath)

    def table(self):
        layout = QtWidgets.QVBoxLayout()

        title_layout = QtWidgets.QHBoxLayout()
        title_label = NXLabel('Indices', bold=True)
        title_layout.addStretch()
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        if [s for s in self.node.shape if s > 10]:
            idx = []
            for i, s in enumerate(self.node.shape):
                spinbox = NXSpinBox(self.choose_data, np.arange(s))
                spinbox.setRange(0, s-1)
                if len(self.node.shape) - i > 2:
                    idx.append(0)
                else:
                    idx.append(np.s_[0:min(s, 10)])
                    spinbox.setSingleStep(10)
                self.spinboxes.append(spinbox)
            data = self.node[tuple(idx)][()]
        else:
            data = self.node[()]

        if self.spinboxes:
            box_layout = QtWidgets.QHBoxLayout()
            box_layout.addStretch()
            for spinbox in self.spinboxes:
                box_layout.addWidget(spinbox)
            box_layout.addStretch()
            layout.addLayout(box_layout)

        self.table_view = QtWidgets.QTableView()
        self.table_model = ViewTableModel(data, parent=self)
        self.table_view.setModel(self.table_model)
        self.table_view.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.table_view.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.table_view.setSortingEnabled(False)
        self.set_size()
        layout.addWidget(self.table_view)
        layout.addStretch()

        return layout

    def choose_data(self):
        idx = [int(s.value()) for s in self.spinboxes]
        if len(idx) > 1:
            origin = [idx[-2], idx[-1]]
            for i in [-2, -1]:
                idx[i] = np.s_[idx[i]:min(self.node.shape[i], idx[i]+10)]
        else:
            origin = [idx[0], 0]
            idx[0] = np.s_[idx[0]:min(self.node.shape[0], idx[0]+10)]
        self.table_model.choose_data(self.node[tuple(idx)][()], origin)
        self.set_size()

    def set_size(self):
        self.table_view.resizeColumnsToContents()
        vwidth = self.table_view.verticalHeader().width()
        hwidth = self.table_view.horizontalHeader().length()
        self.table_view.setFixedWidth(vwidth + hwidth)
        vheight = self.table_view.verticalHeader().length()
        hheight = self.table_view.horizontalHeader().height()
        self.table_view.setFixedHeight(vheight + hheight)


class ViewTableModel(QtCore.QAbstractTableModel):

    def __init__(self, data, parent=None):
        super().__init__(parent=parent)
        self._data = self.get_data(data)
        self.origin = [0, 0]

    def get_data(self, data):
        if len(data.shape) == 0:
            self.rows = 1
            self.columns = 1
            return data.reshape((1, 1))
        elif len(data.shape) == 1:
            self.rows = data.shape[0]
            self.columns = 1
            return data.reshape((data.shape[0], 1))
        else:
            self.rows = data.shape[-2]
            self.columns = data.shape[-1]
            return data

    def rowCount(self, parent=None):
        return self.rows

    def columnCount(self, parent=None):
        return self.columns

    def data(self, index, role):
        if not index.isValid():
            return None
        try:
            value = self._data[index.row()][index.column()]
        except IndexError:
            return None
        text = str(value).lstrip('[').rstrip(']')
        if role == QtCore.Qt.DisplayRole:
            try:
                return f'{float(text):.6g}'
            except (TypeError, ValueError):
                return (text[:10] + '..') if len(text) > 10 else text
        elif role == QtCore.Qt.ToolTipRole:
            return text
        return None

    def headerData(self, position, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and
                role == QtCore.Qt.DisplayRole):
            return str(self.origin[1] + range(10)[position])
        elif (orientation == QtCore.Qt.Vertical and
              role == QtCore.Qt.DisplayRole):
            return str(self.origin[0] + range(10)[position])
        return None

    def choose_data(self, data, origin):
        self.layoutAboutToBeChanged.emit()
        self._data = self.get_data(data)
        self.origin = origin
        self.layoutChanged.emit()
        self.headerDataChanged.emit(QtCore.Qt.Horizontal, 0,
                                    min(9, self.columns-1))
        self.headerDataChanged.emit(QtCore.Qt.Vertical, 0, min(9, self.rows-1))


class AddDialog(NXDialog):
    """Dialog to add a NeXus node"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16',
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)

        self.node = node

        class_layout = QtWidgets.QHBoxLayout()
        self.class_box = NXComboBox()
        if isinstance(self.node, NXgroup):
            names = ['NXgroup', 'NXfield', 'NXattr']
        else:
            names = ['NXattr']
        for name in names:
            self.class_box.addItem(name)
        self.class_button = NXPushButton("Add", self.select_class)
        class_layout.addWidget(self.class_box)
        class_layout.addWidget(self.class_button)
        class_layout.addStretch()

        if isinstance(self.node, NXfield):
            self.setWindowTitle("Add NeXus Attribute")
        else:
            self.setWindowTitle("Add NeXus Data")

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(class_layout)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

    def select_class(self):
        self.class_name = self.class_box.currentText()
        if self.class_name == "NXgroup":
            self.layout.insertLayout(1, self.define_grid("NXgroup"))
        elif self.class_name == "NXfield":
            self.layout.insertLayout(1, self.define_grid("NXfield"))
        else:
            self.layout.insertLayout(1, self.define_grid("NXattr"))
        self.class_button.setDisabled(True)
        self.class_box.setDisabled(True)

    def define_grid(self, class_name):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        name_label = NXLabel("Name:")
        self.name_box = NXLineEdit()
        if class_name == "NXgroup":
            combo_label = NXLabel("Group Class:")
            self.combo_box = NXComboBox(self.select_combo)
            standard_groups = sorted(
                list(set([g for g in
                          self.mainwindow.nxclasses[self.node.nxclass][2]])))
            for name in standard_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(
                    self.combo_box.count() - 1,
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in self.mainwindow.nxclasses
                                   if g not in standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(
                    self.combo_box.count() - 1,
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            grid.addWidget(combo_label, 0, 0)
            grid.addWidget(self.combo_box, 0, 1)
            grid.addWidget(name_label, 1, 0)
            grid.addWidget(self.name_box, 1, 1)
            self.select_combo()
        elif class_name == "NXfield":
            combo_label = NXLabel()
            self.combo_box = NXComboBox(self.select_combo)
            fields = sorted(list(set([g for g in
                            self.mainwindow.nxclasses[self.node.nxclass][1]])))
            for name in fields:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(
                    self.combo_box.count() - 1,
                    wrap(self.mainwindow.nxclasses[self.node.nxclass][1]
                         [name][2], 40),
                    QtCore.Qt.ToolTipRole)
            grid.addWidget(name_label, 0, 0)
            grid.addWidget(self.name_box, 0, 1)
            grid.addWidget(self.combo_box, 0, 2)
            value_label = NXLabel("Value:")
            self.value_box = NXLineEdit()
            grid.addWidget(value_label, 1, 0)
            grid.addWidget(self.value_box, 1, 1)
            units_label = NXLabel("Units:")
            self.units_box = NXLineEdit()
            grid.addWidget(units_label, 2, 0)
            grid.addWidget(self.units_box, 2, 1)
            type_label = NXLabel("Datatype:")
            self.type_box = NXComboBox()
            for name in self.data_types:
                self.type_box.addItem(name)
            self.type_box.insertSeparator(0)
            self.type_box.insertItem(0, 'auto')
            self.type_box.setCurrentIndex(0)
            grid.addWidget(type_label, 3, 0)
            grid.addWidget(self.type_box, 3, 1)
        else:
            grid.addWidget(name_label, 0, 0)
            grid.addWidget(self.name_box, 0, 1)
            value_label = NXLabel("Value:")
            self.value_box = NXLineEdit()
            grid.addWidget(value_label, 1, 0)
            grid.addWidget(self.value_box, 1, 1)
            type_label = NXLabel("Datatype:")
            self.type_box = NXComboBox()
            for name in self.data_types:
                self.type_box.addItem(name)
            self.type_box.insertSeparator(0)
            self.type_box.insertItem(0, 'auto')
            self.type_box.setCurrentIndex(0)
            grid.addWidget(type_label, 2, 0)
            grid.addWidget(self.type_box, 2, 1)
        grid.setColumnMinimumWidth(1, 200)
        return grid

    def select_combo(self):
        self.set_name(self.combo_box.currentText())

    def get_name(self):
        return self.name_box.text()

    def set_name(self, name):
        if self.class_name == 'NXgroup':
            name = name[2:]
        self.name_box.setText(name)

    def get_value(self):
        value = self.value_box.text()
        if value:
            dtype = self.get_type()
            if dtype == "char":
                return value
            else:
                from .consoleapp import _shell
                try:
                    return eval(value, {"__builtins__": {}}, _shell)
                except Exception:
                    return value
        else:
            return None

    def get_units(self):
        return self.units_box.text()

    def get_type(self):
        if self.class_name == 'NXgroup':
            return self.combo_box.currentText()
        else:
            dtype = self.type_box.currentText()
            if dtype == "auto":
                return None
            else:
                return dtype

    def accept(self):
        name = self.get_name()
        if self.class_name == "NXgroup":
            nxclass = self.get_type()
            if name:
                self.node[name] = NXgroup(nxclass=nxclass)
            else:
                group = NXgroup(nxclass=nxclass)
                name = group.nxname
                self.node.insert(group)
            logging.info(f"'{self.node[name]}' added to '{self.node.nxpath}'")
        elif name:
            value = self.get_value()
            dtype = self.get_type()
            if value is not None:
                if self.class_name == "NXfield":
                    self.node[name] = NXfield(value, dtype=dtype)
                    logging.info(f"'{name}' added to '{self.node.nxpath}'")
                    units = self.get_units()
                    if units:
                        self.node[name].attrs['units'] = units
                else:
                    self.node.attrs[name] = NXattr(value, dtype=dtype)
                    logging.info(
                        f"Attribute '{name}' added to '{self.node.nxpath}'")
        super().accept()


class InitializeDialog(NXDialog):
    """Dialog to initialize a NeXus field node"""

    data_types = ['float32', 'float64', 'int8', 'uint8', 'int16',
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)

        self.node = node

        self.setWindowTitle("Initialize NeXus Data")

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        name_label = NXLabel("Name:")
        self.name_box = NXLineEdit()
        self.combo_box = NXComboBox(self.select_combo)
        fields = sorted(list(set([g for g in
                        self.mainwindow.nxclasses[self.node.nxclass][1]])))
        for name in fields:
            self.combo_box.addItem(name)
            self.combo_box.setItemData(
                self.combo_box.count()-1,
                wrap(self.mainwindow.nxclasses[self.node.nxclass][1][name][2],
                     40),
                QtCore.Qt.ToolTipRole)
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        grid.addWidget(self.combo_box, 0, 2)
        type_label = NXLabel("Datatype:")
        self.type_box = NXComboBox()
        for name in self.data_types:
            self.type_box.addItem(name)
        self.type_box.setCurrentIndex(0)
        grid.addWidget(type_label, 2, 0)
        grid.addWidget(self.type_box, 2, 1)
        shape_label = NXLabel("Shape:")
        self.shape_box = NXLineEdit()
        grid.addWidget(shape_label, 3, 0)
        grid.addWidget(self.shape_box, 3, 1)
        grid.setColumnMinimumWidth(1, 200)
        fill_label = NXLabel("Fill Value:")
        self.fill_box = NXLineEdit(0)
        grid.addWidget(fill_label, 4, 0)
        grid.addWidget(self.fill_box, 4, 1)
        grid.setColumnMinimumWidth(1, 200)

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(grid)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

    def select_combo(self):
        self.set_name(self.combo_box.currentText())

    def get_name(self):
        return self.name_box.text()

    def set_name(self, name):
        self.name_box.setText(name)

    @property
    def dtype(self):
        return np.dtype(self.type_box.currentText())

    @property
    def shape(self):
        shape = self.shape_box.text().strip()
        if shape == '':
            raise NeXusError("Invalid shape")
        import ast
        try:
            shape = ast.literal_eval(shape)
            try:
                it = iter(shape)
                return shape
            except Exception:
                if isinstance(shape, numbers.Integral):
                    return (shape,)
                else:
                    raise NeXusError("Invalid shape")
        except Exception:
            raise NeXusError("Invalid shape")

    @property
    def fillvalue(self):
        try:
            return np.asarray(eval(self.fill_box.text()), dtype=self.dtype)
        except Exception:
            raise NeXusError("Invalid fill value")

    def accept(self):
        try:
            name = self.get_name().strip()
            if name:
                dtype = self.dtype
                shape = self.shape
                fillvalue = self.fillvalue
                self.node[name] = NXfield(dtype=dtype, shape=shape,
                                          fillvalue=fillvalue)
                logging.info(
                    f"'{self.node[name]}' initialized in '{self.node.nxpath}'")
                super().accept()
            else:
                raise NeXusError("Invalid name")
        except NeXusError as error:
            report_error("Initializing Data", error)


class RenameDialog(NXDialog):
    """Dialog to rename a NeXus node"""

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)

        self.node = node

        self.setWindowTitle("Rename NeXus data")

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.define_grid())
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

    def define_grid(self):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        name_label = NXLabel("New Name:")
        self.name_box = NXLineEdit(self.node.nxname)
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        self.combo_box = None
        if (isinstance(self.node, NXgroup) and
            not isinstance(self.node, NXlink) and
                self.node.nxclass != 'NXroot'):
            combo_label = NXLabel("New Class:")
            self.combo_box = NXComboBox()
            parent_class = self.node.nxgroup.nxclass
            standard_groups = sorted(
                list(set([g for g in
                          self.mainwindow.nxclasses[parent_class][2]])))
            for name in standard_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(
                    self.combo_box.count() - 1,
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in self.mainwindow.nxclasses
                                   if g not in standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(
                    self.combo_box.count() - 1,
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            self.combo_box.addItem('NXgroup')
            self.combo_box.setCurrentIndex(
                self.combo_box.findText(self.node.nxclass))
            grid.addWidget(combo_label, 1, 0)
            grid.addWidget(self.combo_box, 1, 1)
        else:
            parent_class = self.node.nxgroup.nxclass
            if parent_class != 'NXroot' and parent_class != 'NXtree':
                combo_label = NXLabel("Valid Fields:")
                self.combo_box = NXComboBox(self.set_name)
                fields = sorted(list(set([g for g in
                                self.mainwindow.nxclasses[parent_class][1]])))
                for name in fields:
                    self.combo_box.addItem(name)
                    self.combo_box.setItemData(
                        self.combo_box.count() - 1,
                        wrap(self.mainwindow.nxclasses[parent_class][1]
                             [name][2], 40),
                        QtCore.Qt.ToolTipRole)
                if self.node.nxname in fields:
                    self.combo_box.setCurrentIndex(
                        self.combo_box.findText(self.node.nxname))
                else:
                    self.name_box.setText(self.node.nxname)
                grid.addWidget(self.combo_box, 0, 2)
        grid.setColumnMinimumWidth(1, 200)
        return grid

    def get_name(self):
        return self.name_box.text()

    def set_name(self):
        self.name_box.setText(self.combo_box.currentText())

    def get_class(self):
        return self.combo_box.currentText()

    def accept(self):
        name = self.get_name()
        if name and name != self.node.nxname:
            self.node.rename(name)
        if isinstance(self.node, NXgroup):
            if self.combo_box is not None:
                self.node.nxclass = self.get_class()
        super().accept()


class PasteDialog(NXDialog):
    """Dialog to paste to a NeXus group."""

    def __init__(self, node, link=False, parent=None):

        super().__init__(parent=parent)

        self.node = node
        self.copied_node = self.mainwindow.copied_node
        path = node.nxroot.nxname + node.nxpath + '/' + self.copied_node.nxname
        self.link = link

        if self.copied_node.nxname in node:
            self.copied_node.nxname = self.copied_node.nxname + '_copy'

        self.parameters = GridParameters()
        self.parameters.add('name', self.copied_node.nxname,
                            'Name of pasted node')
        self.set_layout(self.parameters.grid(header=False, spacing=10),
                        self.close_layout(save=True))

        self.set_title(f"Pasting '{path}'")

    def accept(self):
        name = self.copied_node.nxname = self.parameters['name'].value
        try:
            if self.link:
                _, target, filename = self.mainwindow.copied_link
                if filename == 'None' or self.node.nxfilename == filename:
                    self.node[name] = NXlink(target)
                else:
                    self.node[name] = NXlink(target, filename)
            else:
                self.node.insert(self.copied_node)
            super().accept()
        except NeXusError as error:
            report_error("Pasting Data", error)


class SignalDialog(NXDialog):
    """Dialog to set the signal of NXdata"""

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)

        if isinstance(node, NXfield):
            self.group = node.nxgroup
            signal_name = node.nxname
        else:
            self.group = node
            if self.group.nxsignal is not None:
                signal_name = self.group.nxsignal.nxname
            else:
                signal_name = None

        self.signal_combo = NXComboBox()
        for node in self.group.values():
            if isinstance(node, NXfield) and node.shape != ():
                self.signal_combo.addItem(node.nxname)
        if self.signal_combo.count() == 0:
            raise NeXusError("No plottable field in group")
        if signal_name:
            idx = self.signal_combo.findText(signal_name)
            if idx >= 0:
                self.signal_combo.setCurrentIndex(idx)
            else:
                self.signal_combo.setCurrentIndex(0)
        else:
            self.signal_combo.setCurrentIndex(0)
        self.signal_combo.currentIndexChanged.connect(self.choose_signal)

        try:
            self.default_axes = [axis.nxname for axis in self.group.nxaxes]
        except Exception:
            self.default_axes = []

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(NXLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.choose_signal()

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.grid)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

        self.setWindowTitle(f"Set signal for {self.group.nxname}")

    @property
    def signal(self):
        return self.group[self.signal_combo.currentText()]

    @property
    def ndim(self):
        return len(self.signal.shape)

    def choose_signal(self):
        row = 1
        self.axis_boxes = {}
        for axis in range(self.ndim):
            self.axis_boxes[axis] = self.axis_box(axis)
            if self.axis_boxes[axis] is not None:
                row += 1
                self.grid.addWidget(NXLabel(f"Axis {axis}: "), row, 0)
                self.grid.addWidget(self.axis_boxes[axis], row, 1)
        while row < self.grid.rowCount() - 1:
            self.remove_axis(row)
            row += 1

    def axis_box(self, axis=0):
        box = NXComboBox(self.choose_axis)
        axes = []
        for node in self.group.values():
            if isinstance(node, NXfield) and node is not self.signal:
                if self.check_axis(node, axis):
                    axes.append(node.nxname)
                    box.addItem(node.nxname)
        if box.count() > 0:
            box.insertSeparator(0)
        box.insertItem(0, 'None')
        try:
            if self.default_axes[axis] in axes:
                box.setCurrentIndex(box.findText(self.default_axes[axis]))
            else:
                box.setCurrentIndex(0)
        except Exception:
            box.setCurrentIndex(0)
        return box

    def choose_axis(self):
        axes = [self.axis_boxes[axis].currentText()
                for axis in range(self.ndim)]
        axes = [axis_name for axis_name in axes if axis_name != 'None']
        if len(set(axes)) < len(axes):
            display_message("Cannot have duplicate axes")

    def remove_axis(self, axis):
        row = axis + 1
        for column in range(2):
            item = self.grid.itemAtPosition(row, column)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.setVisible(False)
                    self.grid.removeWidget(widget)
                    widget.deleteLater()

    def check_axis(self, node, axis):
        if len(node.shape) > 1:
            return False
        try:
            node_len, axis_len = self.signal.shape[axis], node.shape[0]
            if axis_len == node_len or axis_len == node_len+1:
                return True
        except Exception:
            pass
        return False

    def get_axis(self, axis):
        axis_name = self.axis_boxes[axis].currentText()
        if axis_name == 'None':
            return None
        else:
            return self.group[axis_name]

    def get_axes(self):
        return [self.get_axis(axis) for axis in range(self.ndim)]

    def accept(self):
        try:
            self.group.nxsignal = self.signal
            self.group.nxaxes = self.get_axes()
            super().accept()
        except NeXusError as error:
            report_error("Setting signal", error)
            super().reject()


class LogDialog(NXDialog):
    """Dialog to display a NeXpy log file"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.log_directory = self.mainwindow.nexpy_dir

        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setMinimumWidth(800)
        self.text_box.setMinimumHeight(600)
        self.text_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.text_box.setReadOnly(True)
        self.file_combo = NXComboBox(self.show_log)
        for file_name in self.get_filesindirectory(
                'nexpy', extension='.log*', directory=self.log_directory):
            self.file_combo.add(file_name)
        self.file_combo.select('nexpy.log')
        self.issue_button = NXPushButton('Open NeXpy Issue', self.open_issue)
        footer_layout = self.make_layout(self.issue_button,
                                         'stretch',
                                         self.file_combo, 'stretch',
                                         self.close_buttons(close=True),
                                         align='justified')
        self.set_layout(self.text_box, footer_layout)

        self.show_log()

    @property
    def file_name(self):
        return os.path.join(self.log_directory, self.file_combo.currentText())

    def open_issue(self):
        import webbrowser
        url = "https://github.com/nexpy/nexpy/issues"
        webbrowser.open(url, new=1, autoraise=True)

    def mouseReleaseEvent(self, event):
        self.show_log()

    def show_log(self):
        self.format_log()
        self.setVisible(True)
        self.raise_()
        self.activateWindow()

    def format_log(self):
        with open(self.file_name, 'r') as f:
            self.text_box.setText(convertHTML(f.read()))
        self.text_box.verticalScrollBar().setValue(
            self.text_box.verticalScrollBar().maximum())
        self.setWindowTitle(f"Log File: {self.file_name}")

    def reject(self):
        super().reject()
        self.mainwindow.log_window = None


class UnlockDialog(NXDialog):
    """Dialog to unlock a file"""

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)

        self.setWindowTitle("Unlock File")
        self.node = node

        file_size = os.path.getsize(self.node.nxfilename)
        if file_size < 10000000:
            default = True
        else:
            default = False

        self.set_layout(self.labels(
            "<b>Are you sure you want to unlock the file?</b>"),
            self.checkboxes(('backup',
                             f'Backup file ({human_size(file_size)})',
                             default)),
            self.close_buttons())
        self.set_title('Unlocking File')

    def accept(self):
        try:
            if self.checkbox['backup'].isChecked():
                dir = os.path.join(self.mainwindow.backup_dir, timestamp())
                os.mkdir(dir)
                self.node.backup(dir=dir)
                self.mainwindow.settings.set('backups', self.node.nxbackup)
                self.mainwindow.settings.save()
                logging.info(
                    f"Workspace '{self.node.nxname}' backed up to "
                    f"'{self.node.nxbackup}'")
            self.node.unlock()
            logging.info(f"Workspace '{self.node.nxname}' unlocked")
            super().accept()
        except NeXusError as error:
            report_error("Unlocking file", error)


class ManageBackupsDialog(NXDialog):
    """Dialog to restore or purge backup files"""

    def __init__(self, parent=None):

        super().__init__(parent=parent, default=True)

        self.backup_dir = self.mainwindow.backup_dir
        self.mainwindow.settings.read(self.mainwindow.settings_file)
        options = reversed(self.mainwindow.settings.options('backups'))
        backups = []
        for backup in options:
            if os.path.exists(backup):
                backups.append(backup)
            else:
                self.mainwindow.settings.remove_option('backups', backup)
        self.mainwindow.settings.save()
        self.scroll_area = NXScrollArea()
        items = []
        for backup in backups:
            date = format_timestamp(os.path.basename(os.path.dirname(backup)))
            name = self.get_name(backup)
            size = os.path.getsize(backup)
            items.append(
                self.checkboxes((backup,
                                 f"{date}: {name} ({human_size(size)})",
                                 False), align='left'))
        self.scroll_widget = NXWidget()
        self.scroll_widget.set_layout(*items)
        self.scroll_area.setWidget(self.scroll_widget)

        self.set_layout(self.scroll_area,
                        self.action_buttons(('Restore Files', self.restore),
                                            ('Delete Files', self.delete)),
                        self.close_buttons(close=True))

        self.set_title('Manage Backups')

    def get_name(self, backup):
        name, ext = os.path.splitext(os.path.basename(backup))
        return name[:name.find('_backup')] + ext

    def restore(self):
        for backup in self.checkbox:
            if self.checkbox[backup].isChecked():
                name = self.tree.get_name(self.get_name(backup))
                self.tree[name] = self.mainwindow.user_ns[name] = nxload(
                    backup)
                self.checkbox[backup].setChecked(False)
                self.checkbox[backup].setDisabled(True)
                self.display_message(f"Backup file '{name}' has been opened",
                                     "Please save the file for future use")

    def delete(self):
        backups = []
        for backup in self.checkbox:
            if self.checkbox[backup].isChecked():
                backups.append(backup)
        if backups:
            if self.confirm_action("Delete selected backups?",
                                   "\n".join(backups)):
                for backup in backups:
                    if (os.path.exists(backup) and
                            os.path.realpath(backup).startswith(
                                self.backup_dir)):
                        os.remove(os.path.realpath(backup))
                        os.rmdir(os.path.dirname(os.path.realpath(backup)))
                        self.mainwindow.settings.remove_option('backups',
                                                               backup)
                    self.checkbox[backup].setChecked(False)
                    self.checkbox[backup].setDisabled(True)
                self.mainwindow.settings.save()


class InstallPluginDialog(NXDialog):
    """Dialog to install a NeXus plugin"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.local_directory = self.mainwindow.plugin_dir
        self.nexpy_directory = pkg_resources.resource_filename('nexpy',
                                                               'plugins')
        self.backup_dir = self.mainwindow.backup_dir

        self.setWindowTitle("Install Plugin")

        self.set_layout(
            self.directorybox('Choose plugin directory'),
            self.radiobuttons(
                ('local', 'Install locally', True),
                ('nexpy', 'Install in NeXpy', False)),
            self.close_buttons())
        self.set_title('Installing Plugin')

    def get_menu_info(self, plugin_name, plugin_path):
        try:
            plugin_module = import_plugin(plugin_name, [plugin_path])
            return plugin_module.plugin_menu()
        except Exception as error:
            report_error("Installing Plugin", error)

    def install_plugin(self):
        plugin_directory = self.get_directory()
        plugin_name = os.path.basename(os.path.normpath(plugin_directory))
        plugin_path = os.path.dirname(plugin_directory)
        name, actions = self.get_menu_info(plugin_name, plugin_path)
        if name is None:
            raise NeXusError("This directory does not contain a valid plugin")
        if self.radiobutton['local'].isChecked():
            plugin_path = self.local_directory
        else:
            plugin_path = self.nexpy_directory
        installed_path = os.path.join(plugin_path, plugin_name)
        if os.path.exists(installed_path):
            if self.confirm_action("Overwrite plugin?",
                                   f"Plugin '{plugin_name}' already exists"):
                backup = os.path.join(self.backup_dir, timestamp())
                os.mkdir(backup)
                shutil.move(installed_path, backup)
                self.mainwindow.settings.set('plugins',
                                             os.path.join(backup, plugin_name))
                self.mainwindow.settings.save()
            else:
                return
        shutil.copytree(plugin_directory, installed_path)
        for action in [action for action
                       in self.mainwindow.menuBar().actions()
                       if action.text() == name]:
            self.mainwindow.menuBar().removeAction(action)
        self.mainwindow.add_plugin_menu(name, actions)

    def accept(self):
        try:
            self.install_plugin()
            super().accept()
        except NeXusError as error:
            report_error("Installing plugin", error)


class RemovePluginDialog(NXDialog):
    """Dialog to remove a NeXus plugin"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.local_directory = Path(self.mainwindow.plugin_dir)
        self.nexpy_directory = Path(pkg_resources.resource_filename('nexpy',
                                                                    'plugins'))
        self.backup_dir = Path(self.mainwindow.backup_dir)

        local_plugins = []
        for item in self.local_directory.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                local_plugins.append(
                    self.checkboxes((str(item), '   ' + item.name, False),
                                    align='left'))
        nexpy_plugins = []
        for item in self.nexpy_directory.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                nexpy_plugins.append(
                    self.checkboxes((str(item), '   ' + item.name, False),
                                    align='left'))

        if len(local_plugins) == 0 and len(nexpy_plugins) == 0:
            self.display_message('Removing Plugins', 'No plugins to remove')
            self.reject()
        elif len(local_plugins) == 0:
            self.set_layout(NXLabel("NeXpy Plugins", bold=True),
                            *nexpy_plugins,
                            self.close_buttons())
        elif len(nexpy_plugins) == 0:
            self.set_layout(NXLabel("Local Plugins", bold=True),
                            *local_plugins,
                            self.close_buttons())
        else:
            self.set_layout(NXLabel("Local Plugins", bold=True),
                            *local_plugins,
                            NXLabel("NeXpy Plugins", bold=True),
                            *nexpy_plugins,
                            self.close_buttons())

        self.set_title('Removing Plugin')

    def remove_plugin(self):
        for plugin_path in self.checkbox:
            plugin_name = Path(plugin_path).name
            if self.checkbox[plugin_path].isChecked():
                if self.confirm_action(f"Remove '{plugin_path}'?",
                                       "This cannot be reversed"):
                    backup_path = self.backup_dir / timestamp()
                    backup_path.mkdir()
                    shutil.move(str(plugin_path), str(backup_path))
                    self.mainwindow.settings.set(
                        'plugins', str(backup_path.joinpath(plugin_name)))
                self.mainwindow.settings.save()
            else:
                continue
        for action in [action for action
                       in self.mainwindow.menuBar().actions()
                       if action.text().lower() == plugin_name.lower()]:
            self.mainwindow.menuBar().removeAction(action)

    def accept(self):
        try:
            self.remove_plugin()
            super().accept()
        except NeXusError as error:
            report_error("Removing plugin", error)


class RestorePluginDialog(NXDialog):
    """Dialog to restore plugins from backups"""

    def __init__(self, parent=None):

        super().__init__(parent=parent, default=True)

        self.local_directory = self.mainwindow.plugin_dir
        self.nexpy_directory = pkg_resources.resource_filename('nexpy',
                                                               'plugins')
        self.backup_dir = self.mainwindow.backup_dir

        options = reversed(self.mainwindow.settings.options('plugins'))
        self.plugins = []
        for plugin in options:
            if os.path.exists(plugin):
                self.plugins.append(plugin)
            else:
                self.mainwindow.settings.remove_option('plugins', plugin)
        self.mainwindow.settings.save()
        plugin_list = []
        for plugin in self.plugins:
            date = format_timestamp(os.path.basename(os.path.dirname(plugin)))
            name = self.get_name(plugin)
            if plugin is self.plugins[0]:
                checked = True
            else:
                checked = False
            plugin_list.append((plugin, f"{date}: {name}", checked))
        items = []
        items.append(self.radiobuttons(*plugin_list, align='left',
                                       vertical=True))
        items.append(self.radiobuttons(('local', 'Install locally', True),
                                       ('nexpy', 'Install in NeXpy', False)))
        items.append(self.action_buttons(('Restore Plugin', self.restore)))
        items.append(self.close_buttons(close=True))

        self.set_layout(*items)

        self.set_title('Restore Plugin')

    def get_name(self, plugin):
        return os.path.basename(plugin)

    def get_menu_info(self, plugin_name, plugin_path):
        try:
            plugin_module = import_plugin(plugin_name, [plugin_path])
            return plugin_module.plugin_menu()
        except Exception as error:
            report_error("Restoring Plugin", error)

    def remove_backup(self, backup):
        shutil.rmtree(os.path.dirname(os.path.realpath(backup)))
        self.mainwindow.settings.remove_option('plugins', backup)
        self.mainwindow.settings.save()

    def restore(self):
        plugin_name = None
        for plugin_directory in self.plugins:
            if self.radiobutton[plugin_directory].isChecked():
                plugin_name = os.path.basename(plugin_directory)
                break
        if plugin_name is None:
            return
        plugin_path = os.path.dirname(plugin_directory)
        name, actions = self.get_menu_info(plugin_name, plugin_path)
        if name is None:
            raise NeXusError("This directory does not contain a valid plugin")
        if self.radiobutton['local'].isChecked():
            plugin_path = self.local_directory
        else:
            plugin_path = self.nexpy_directory
        restored_path = os.path.join(plugin_path, plugin_name)
        if os.path.exists(restored_path):
            if self.confirm_action("Overwrite plugin?",
                                   f"Plugin '{plugin_name}' already exists"):
                backup_path = os.path.join(self.backup_dir, timestamp())
                os.mkdir(backup_path)
                shutil.move(restored_path, backup_path)
                self.mainwindow.settings.set(
                    'plugins', os.path.join(backup_path, plugin_name))
                self.mainwindow.settings.save()
            else:
                return
        shutil.copytree(plugin_directory, restored_path)
        self.remove_backup(plugin_directory)

        for action in [action for action
                       in self.mainwindow.menuBar().actions()
                       if action.text() == name]:
            self.mainwindow.menuBar().removeAction(action)
        self.mainwindow.add_plugin_menu(name, actions)

        self.accept()
