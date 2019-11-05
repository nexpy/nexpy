#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import bisect
import logging
import numbers
import os
import pkg_resources
import re
import shutil
import sys

from posixpath import basename

from .pyqt import QtCore, QtGui, QtWidgets, getOpenFileName, getSaveFileName
import numpy as np
from matplotlib import rcParams, rcParamsDefault
from matplotlib.legend import Legend
from matplotlib.rcsetup import (defaultParams, validate_float, validate_int, 
                                validate_color, validate_aspect)

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from .utils import (confirm_action, display_message, report_error,
                    import_plugin, convertHTML, natural_sort, wrap, human_size,
                    timestamp, format_timestamp, restore_timestamp, get_color,
                    keep_data, fix_projection, modification_time)
from .widgets import (NXCheckBox, NXComboBox, NXColorBox, NXPushButton, NXStack,
                      NXDoubleSpinBox, NXSpinBox, NXpolygon)

from nexusformat.nexus import (NeXusError, NXgroup, NXfield, NXattr, 
                               NXlink, NXlinkgroup, NXlinkfield,
                               NXroot, NXentry, NXdata, NXparameters, nxload)


class NXWidget(QtWidgets.QWidget):
    """Customized widget for NeXpy widgets"""
 
    def __init__(self, parent=None):

        super(NXWidget, self).__init__(parent)
        from .consoleapp import _mainwindow
        self.mainwindow = _mainwindow
        self.mainwindow.current_widget = self
        self.treeview = self.mainwindow.treeview
        self.tree = self.treeview.tree
        self.plotview = self.mainwindow.plotview
        self.plotviews = self.mainwindow.plotviews
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
        self.bold_font =  QtGui.QFont()
        self.bold_font.setBold(True)
        if parent is None:
            parent = self.mainwindow
        self.accepted = False

    def set_layout(self, *items):
        self.layout = QtWidgets.QVBoxLayout()
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                self.layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.addWidget(item)
        self.setLayout(self.layout)

    def make_layout(self, *items, **opts):
        if 'vertical' in opts and opts['vertical'] == True:
            vertical = True
            layout = QtWidgets.QVBoxLayout()
        else:
            vertical = False
            layout = QtWidgets.QHBoxLayout()
            layout.addStretch()
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                layout.addWidget(item)
            if not vertical:
                layout.addStretch()
        return layout

    def add_layout(self, *items):
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                self.layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.addWidget(item)

    def insert_layout(self, index, *items):
        for item in reversed(list(items)):
            if isinstance(item, QtWidgets.QLayout):
                self.layout.insertLayout(index, item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.insertWidget(index, item)

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

    def close_layout(self, message=None, save=False, close=False):
        layout = QtWidgets.QHBoxLayout()
        self.status_message = QtWidgets.QLabel()
        if message:
            self.status_message.setText(message)
        layout.addWidget(self.status_message)
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

    def label(self, label):
        return QtWidgets.QLabel(six.text_type(label))

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
            label_widget = QtWidgets.QLabel(six.text_type(label))
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
            label_box = QtWidgets.QLabel(label)
            label_box.setAlignment(QtCore.Qt.AlignLeft)
            self.textbox[label] = QtWidgets.QLineEdit(six.text_type(value))
            self.textbox[label].setAlignment(QtCore.Qt.AlignLeft)
            item_layout.addWidget(label_box)
            item_layout.addWidget(self.textbox[label])
            layout.addLayout(item_layout)
            layout.addStretch()
        return layout            
            
    def checkboxes(self, *items, **opts):
        if 'align' in opts:
            align = opts['align']
        else:
            align = 'center'
        if 'vertical' in opts and opts['vertical'] == True:
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
        if 'vertical' in opts and opts['vertical'] == True:
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

    def editor(self, text=None, *opts):
        editbox = QtWidgets.QPlainTextEdit()
        if text:
            editbox.setText(text)
        editbox.setFocusPolicy(QtCore.Qt.StrongFocus)
        return editbox

    def filebox(self, text="Choose File", slot=None):
        """
        Creates a text box and button for selecting a file.
        """
        if slot:
            self.filebutton = NXPushButton(text, slot)
        else:
            self.filebutton =  NXPushButton(text, self.choose_file)
        self.filename = QtWidgets.QLineEdit(self)
        self.filename.setMinimumWidth(300)
        filebox = QtWidgets.QHBoxLayout()
        filebox.addWidget(self.filebutton)
        filebox.addWidget(self.filename)
        return filebox
 
    def directorybox(self, text="Choose Directory", slot=None, default=True):
        """
        Creates a text box and button for selecting a directory.
        """
        if slot:
            self.directorybutton = NXPushButton(text, slot)
        else:
            self.directorybutton =  NXPushButton(text, self.choose_directory)
        self.directoryname = QtWidgets.QLineEdit(self)
        self.directoryname.setMinimumWidth(300)
        default_directory = self.get_default_directory()
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
        if os.path.exists(filename): # avoids problems if <Cancel> was selected
            dirname = os.path.dirname(filename)
            self.filename.setText(str(filename))
            self.set_default_directory(dirname)

    def get_filename(self):
        """
        Returns the selected file.
        """
        return self.filename.text()

    def choose_directory(self):
        """
        Opens a file dialog and sets the directory text box to the chosen path.
        """
        dirname = self.get_default_directory()
        dirname = QtWidgets.QFileDialog.getExistingDirectory(self, 
                                                             'Choose Directory', 
                                                             dirname)
        if os.path.exists(dirname):  # avoids problems if <Cancel> was selected
            self.directoryname.setText(str(dirname))
            self.set_default_directory(dirname)

    def get_directory(self):
        """
        Returns the selected directory
        """
        return self.directoryname.text()
    
    def get_default_directory(self, suggestion=None):
        '''return the most recent default directory for open/save dialogs'''
        if suggestion is None or not os.path.exists(suggestion):
            suggestion = self.default_directory
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
        suggestion = os.path.abspath(suggestion)
        return suggestion
    
    def set_default_directory(self, suggestion):
        """Defines the default directory to use for open/save dialogs"""
        if os.path.exists(suggestion):
            if not os.path.isdir(suggestion):
                suggestion = os.path.dirname(suggestion)
            self.default_directory = suggestion

    def get_filesindirectory(self, prefix='', extension='.*', directory=None):
        """
        Returns a list of files in the selected directory.
        
        The files are sorted using a natural sort algorithm that preserves the
        numeric order when a file name consists of text and index so that, e.g., 
        'data2.tif' comes before 'data10.tif'.
        """
        if directory:
            os.chdir(directory)
        else:
            os.chdir(self.get_directory())
        if not extension.startswith('.'):
            extension = '.'+extension
        from glob import glob
        filenames = glob(prefix+'*'+extension)
        return sorted(filenames,key=natural_sort)

    def select_box(self, choices, default=None, slot=None):
        box = NXComboBox()
        for choice in choices:
            box.addItem(choice)
        if default in choices:
            idx = box.findText(default)
            box.setCurrentIndex(idx)
        else:
            box.setCurrentIndex(0)
        if slot:
            box.currentIndexChanged.connect(slot)
        return box

    def select_root(self, slot=None, text='Select Root', other=False):
        layout = QtWidgets.QHBoxLayout()
        box = NXComboBox()
        roots = []
        for root in self.tree.NXroot:
            roots.append(root.nxname)
        if not roots:
            raise NeXusError("No files loaded in the NeXus tree")
        for root in sorted(roots):
            box.addItem(root)
        if not other:
            try:
                node = self.treeview.get_node()
                idx = box.findText(node.nxroot.nxname)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            except Exception:
                box.setCurrentIndex(0)
        layout.addWidget(box)
        if slot:
            layout.addWidget(NXPushButton(text, slot))
        layout.addStretch()
        if not other:
            self.root_box = box
            self.root_layout = layout
        else:
            self.other_root_box = box
            self.other_root_layout = layout
        return layout

    @property
    def root(self):
        return self.tree[self.root_box.currentText()]

    @property
    def other_root(self):
        return self.tree[self.other_root_box.currentText()]

    def select_entry(self, slot=None, text='Select Entry', other=False):
        layout = QtWidgets.QHBoxLayout()
        box = NXComboBox()
        entries = []
        for root in self.tree.NXroot:
            for entry in root.NXentry:
                entries.append(root.nxname+'/'+entry.nxname)
        if not entries:
            raise NeXusError("No entries in the NeXus tree")
        for entry in sorted(entries):
            box.addItem(entry)
        if not other:
            try:
                node = self.treeview.get_node()
                idx = box.findText(node.nxroot.nxname+'/'+node.nxentry.nxname)
                if idx >= 0:
                    box.setCurrentIndex(idx)
            except Exception:
                box.setCurrentIndex(0)
        layout.addStretch()
        layout.addWidget(box)
        if slot:
            layout.addWidget(NXPushButton(text, slot))
        layout.addStretch()
        if not other:
            self.entry_box = box
            self.entry_layout = layout
        else:
            self.other_entry_box = box
            self.other_entry_layout = layout
        return layout

    @property
    def entry(self):
        return self.tree[self.entry_box.currentText()]

    @property
    def other_entry(self):
        return self.tree[self.other_entry_box.currentText()]

    def copy_layout(self, text="Copy"):
        self.copywidget = QtWidgets.QWidget()
        copylayout = QtWidgets.QHBoxLayout()
        self.copybox = NXComboBox()
        self.copy_button = NXPushButton(text, self.copy, self)
        copylayout.addStretch()
        copylayout.addWidget(self.copybox)
        copylayout.addWidget(self.copy_button)
        copylayout.addStretch()
        self.copywidget.setLayout(copylayout)
        self.copywidget.setVisible(False)
        return self.copywidget    

    def copy(self):
        pass

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

    def progress_layout(self, save=False, close=False):
        layout = QtWidgets.QHBoxLayout()
        self.progress_bar = QtWidgets.QProgressBar()
        layout.addWidget(self.progress_bar)
        layout.addStretch()
        layout.addWidget(self.close_buttons(save=save, close=close))
        self.progress_bar.setVisible(False)
        return layout

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

    def update(self):
        pass

    def closeEvent(self, event):
        self.stop_thread()
        super(NXWidget, self).closeEvent(event)
        

class NXTab(NXWidget):
    """Subclass of NXWidget for use as the main widget in a tab.
    
    This adds a stretch to the bottom of the QVBoxLayout to improve the layout 
    of differently sized tabs.
    """

    def set_layout(self, *items):
        self.layout = QtWidgets.QVBoxLayout()
        for item in items:
            if isinstance(item, QtWidgets.QLayout):
                self.layout.addLayout(item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.addWidget(item)
        self.layout.addStretch()
        self.setLayout(self.layout)


class NXDialog(QtWidgets.QDialog, NXWidget):
    """Base dialog class for NeXpy dialogs"""
    
    def __init__(self, parent=None, default=False):
        QtWidgets.QDialog.__init__(self, parent)
        NXWidget.__init__(self, parent)
        self.mainwindow.current_dialog = self
        if not default:
            self.installEventFilter(self)
 
    def close_buttons(self, save=False, close=False):
        """
        Creates a box containing the standard Cancel and OK buttons.
        """
        self.close_box = QtWidgets.QDialogButtonBox(self)
        self.close_box.setOrientation(QtCore.Qt.Horizontal)
        if save:
            self.close_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|
                                              QtWidgets.QDialogButtonBox.Save)
        elif close:
            self.close_box.setStandardButtons(QtWidgets.QDialogButtonBox.Close)
        else:
            self.close_box.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|
                                              QtWidgets.QDialogButtonBox.Ok)
        self.close_box.accepted.connect(self.accept)
        self.close_box.rejected.connect(self.reject)
        return self.close_box

    buttonbox = close_buttons #For backward compatibility

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
        return QtWidgets.QWidget.eventFilter(self, widget, event)

    def accept(self):
        """
        Accepts the result.
        
        This usually needs to be subclassed in each dialog.
        """
        self.accepted = True
        QtWidgets.QDialog.accept(self)
        
    def reject(self):
        """
        Cancels the dialog without saving the result.
        """
        self.accepted = False
        QtWidgets.QDialog.reject(self)


BaseDialog = NXDialog
            

class NXPanel(NXDialog):

    def __init__(self, panel, title='title', tabs={}, apply=True, reset=True, 
                 parent=None):
        super(NXPanel, self).__init__(parent)
        self.tab_class = NXTab
        self.plotview_sort = False
        self.tabwidget = QtWidgets.QTabWidget()
        self.tabwidget.currentChanged.connect(self.update)
        self.tabwidget.setElideMode(QtCore.Qt.ElideLeft)
        self.tabs = {}
        self.labels = {}        
        self.panel = panel
        self.title = title
        for label in tabs:
            self.tabs[label] = tabs[label]
            self.labels[tabs[label]] = label
        self.set_layout(self.tabwidget, self.close_buttons(apply, reset))
        self.set_title(title)
        self.setVisible(True)

    def __repr__(self):
        return 'NXPanel("%s")' % self.panel

    def add(self, label, tab=None, idx=None):
        if label in self.tabs:
            raise NeXusError("'%s' already in %s" % (label, self.title))
        self.tabs[label] = tab
        self.labels[tab] = label
        tab.panel = self
        if idx is not None:
            self.tabwidget.insertTab(idx, tab, label)
        else:
            self.tabwidget.addTab(tab, label)
        self.tabwidget.setCurrentWidget(tab)
        self.tabwidget.tabBar().setTabToolTip(self.tabwidget.indexOf(tab), label)
        self.setVisible(True)

    def remove(self, label):
        if label in self.tabs:
            try:
                self.tabwidget.removeTab(self.tabwidget.indexOf(self.tabs[label]))
            except RuntimeError:
                pass
            del self.labels[self.tabs[label]]
            self.tabs[label].deleteLater()
            del self.tabs[label]
        self.update()

    def __contains__(self, label):
        """Implements 'k in d' test"""
        return label in self.tabs

    @property
    def tab(self):
        return self.tabwidget.currentWidget()

    @tab.setter
    def tab(self, label):
        self.tabwidget.setCurrentWidget(self.tabs[label])

    def close_buttons(self, apply=True, reset=True):
        """
        Creates a box containing the standard Apply, Reset and Close buttons.
        """
        box = QtWidgets.QDialogButtonBox(self)
        box.setOrientation(QtCore.Qt.Horizontal)
        if apply and reset:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Apply|
                                   QtWidgets.QDialogButtonBox.Reset|
                                   QtWidgets.QDialogButtonBox.Close)
        elif apply:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Apply|
                                   QtWidgets.QDialogButtonBox.Close)
        elif reset:
            box.setStandardButtons(QtWidgets.QDialogButtonBox.Reset|
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

    def activate(self, label):
        if label not in self.tabs:
            tab = self.tab_class(parent=self)
            if self.plotview_sort:
                if label in self.plotviews:
                    tab.plotview = self.plotviews[label]
                    numbers = sorted([t.plotview.number-1 for t in self.labels])
                    idx = bisect.bisect_left(numbers, tab.plotview.number)
                else:
                    raise NeXusError("Invalid plot label")
            else:
                idx=None
            self.add(label, tab, idx=idx)
        else:
            self.tab = label
            self.tab.update()
        self.setVisible(True)
        self.raise_()
        self.activateWindow()

    def update(self):
        if self.tabwidget.count() == 0:
            self.setVisible(False)
        else:
            self.tab.update()
        self.adjustSize()

    def copy(self):
        self.tab.copy()

    def reset(self):
        self.tab.reset()

    def apply(self):
        self.tab.apply()

    def closeEvent(self, event):
        super(NXPanel, self).closeEvent(event)
        if not self.isVisible():
            for tab in self.tabs:
                self.tabs[tab].close()
            self.deleteLater()
            if self.panel in self.mainwindow.panels:
                del self.mainwindow.panels[self.panel]

    def close(self):
        tab = self.tab
        if tab:
            tab.close()
            self.remove(self.labels[tab])


class GridParameters(OrderedDict):
    """
    A dictionary of parameters to be entered in a dialog box grid.

    All keys must be strings, and valid Python symbol names, and all values
    must be of class GridParameter.
    """
    def __init__(self, **kwds):
        super(GridParameters, self).__init__(self)
        self.result = None
        self.status_layout = None
        self.update(**kwds)

    def __setitem__(self, key, value):
        if value is not None and not isinstance(value, GridParameter):
            raise ValueError("'%s' is not a GridParameter" % value)
        OrderedDict.__setitem__(self, key, value)
        value.name = key

    def add(self, name, value=None, label=None, vary=None, slot=None,
            color=False, validate=None):
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
                                             slot=slot, color=color,
                                             validate=validate))

    def grid(self, header=True, title=None, width=None):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(2)
        header_font = QtGui.QFont()
        header_font.setBold(True)
        row = 0
        if title:
            title_label = QtWidgets.QLabel(title)
            title_label.setFont(header_font)
            title_label.setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(title_label, row, 0, 1, 2)
            row += 1
        if header:
            parameter_label = QtWidgets.QLabel('Parameter')
            parameter_label.setFont(header_font)
            parameter_label.setAlignment(QtCore.Qt.AlignHCenter)
            grid.addWidget(parameter_label, 0, 0)
            value_label = QtWidgets.QLabel('Value')
            value_label.setFont(header_font)
            value_label.setAlignment(QtCore.Qt.AlignHCenter)
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
            fit_label = QtWidgets.QLabel('Fit?')
            fit_label.setFont(header_font)
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
        from lmfit import Parameters, Parameter
        self.lmfit_parameters = Parameters()
        for p in [p for p in self if self[p].vary]:
            self.lmfit_parameters[p] = Parameter(self[p].name, self[p].value)

    def get_parameters(self, parameters):
        for p in parameters:
            self[p].value = parameters[p].value

    def refine_parameters(self, residuals, **opts):
        from lmfit import minimize, fit_report
        self.set_parameters()
        if self.status_layout:
            self.status_message.setText('Fitting...')
            self.status_message.repaint()
        self.result = minimize(residuals, self.lmfit_parameters, **opts)
        self.fit_report = self.result.message+'\n'+fit_report(self.result)
        if self.status_layout:
            self.status_message.setText(self.result.message)
        self.get_parameters(self.result.params)

    def report_layout(self):
        layout = QtWidgets.QHBoxLayout()
        self.status_message = QtWidgets.QLabel()
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


class GridParameter(object):
    """
    A Parameter is an object to be set in a dialog box grid.
    """
    def __init__(self, name=None, value=None, label=None, vary=None, slot=None,
                 color=False, validate=None):
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
            Whether the field contains a color value
        validate : function, optional
            Function to be used to validate the value
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
                self.colorbox = NXColorBox(value)
                self.box = self.colorbox.box
            else:
                self.box = QtWidgets.QLineEdit()
                self.colorbox = None
            self.box.setAlignment(QtCore.Qt.AlignRight)
            if value is not None:
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
            if slot is not None:
                self.box.editingFinished.connect(slot)
        self.init_value = self.value
        if vary is not None:
            self.checkbox = NXCheckBox()
            self.vary = vary
        else:
            self.checkbox = self.vary = None
        self.label = QtWidgets.QLabel(label)

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
            s.append("'%s'" % self.name)
        sval = repr(self.value)
        s.append(sval)
        return "<GridParameter %s>" % ', '.join(s)

    def save(self):
        if isinstance(self.field, NXfield):
            self.field.nxdata = np.array(self.value).astype(self.field.dtype)

    @property
    def value(self):
        if isinstance(self.box, NXComboBox):
            return self.box.currentText()
        else:
            _value = self.box.text()
            try:
                return np.asscalar(np.array(_value).astype(self.field.dtype))
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
            else:
                if isinstance(value, NXfield):
                    value = value.nxdata
                if isinstance(value, six.text_type):
                    self.box.setText(value)
                else:
                    try:
                        self.box.setText('%.6g' % value)
                    except TypeError:
                        self.box.setText(six.text_type(value))
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

        super(NewDialog, self).__init__(parent)

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
        self.treeview.update()
        logging.info("New workspace '%s' created" % root)
        super(NewDialog, self).accept()


class PlotDialog(NXDialog):
    """Dialog to plot arbitrary NeXus data in one or two dimensions"""
 
    def __init__(self, node, parent=None, **kwargs):

        super(PlotDialog, self).__init__(parent)
 
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

        self.kwargs = kwargs

        self.signal_combo =  NXComboBox() 
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
        self.grid.addWidget(QtWidgets.QLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.choose_signal()

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.grid)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

        self.setWindowTitle("Plot NeXus Data")



    @property
    def signal(self):
        _signal = self.group[self.signal_combo.currentText()]
        if isinstance(_signal, NXlink):
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
            self.grid.addWidget(QtWidgets.QLabel("Axis %s: " % axis), row, 0)
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
        box.insertItem(0,'NXfield index')
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
                           name='Axis%s' % axis)
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
            if self.ndim == 1:
                if 'marker' not in self.kwargs:
                    self.kwargs['marker'] = 'o'
            else:
                self.kwargs.pop('marker', None)
                self.kwargs.pop('linestyle', None)
            data = NXdata(self.signal, self.get_axes(), 
                          title=self.signal_path)
            data.nxsignal.attrs['signal_path'] = self.signal_path
            data.plot(**self.kwargs)
            super(PlotDialog, self).accept()
        except NeXusError as error:
            report_error("Plotting data", error)

    
class ExportDialog(NXDialog):

    def __init__(self, node, parent=None):

        super(ExportDialog, self).__init__(parent)
 
        self.data = node
        self.x = node.nxaxes[0]
        self.y = node.nxsignal
        self.e = node.nxerrors
        self.parameters = GridParameters()
        self.parameters.add('delimiter', '\\t', 'Delimiter')
        
        self.set_layout(self.parameters.grid(header=False),
                        self.checkboxes(('header', 'Header', True),
                                        ('errors', 'Errors', True)),
                        self.close_buttons(save=True))
        if self.e is None:
            self.checkbox['errors'].setChecked(False)
            self.checkbox['errors'].setVisible(False)
        self.set_title('Exporting Data')

    @property
    def header(self):
        return self.checkbox['header'].isChecked()

    @property
    def errors(self):
        return self.checkbox['errors'].isChecked()

    @property
    def delimiter(self):
        delimiter = self.parameters['delimiter'].value.encode('utf-8')
        return delimiter.decode('unicode_escape')

    def accept(self):
        fname = getSaveFileName(self, "Choose a Filename", 
                                self.data.nxname+'.txt')
        if fname:
            self.default_directory = os.path.dirname(fname)
        else:
            return

        if self.errors:
            output = np.array([self.x, self.y, self.e]).T
            if self.header:
                header = self.delimiter.join([self.x.nxname, 
                                              self.y.nxname, 
                                              self.e.nxname])
                np.savetxt(fname, output, header=header, 
                           delimiter=self.delimiter,
                           comments='', fmt=['%g','%g','%g'])
            else:
                np.savetxt(fname, output, delimiter=self.delimiter,
                           comments='', fmt=['%g','%g','%g'])
        else:
            output = np.array([self.x, self.y]).T
            if self.header:
                header = self.delimiter.join([self.x.nxname, self.y.nxname])
                np.savetxt(fname, output, header=header, 
                           delimiter=self.delimiter,
                           comments='', fmt=['%g','%g'])
            else:
                np.savetxt(fname, output, delimiter=self.delimiter,
                           comments='', fmt=['%g','%g'])
        super(ExportDialog, self).accept()


class PreferencesDialog(NXDialog):

    def __init__(self, parent):
        super(PreferencesDialog, self).__init__(parent, default=True)

        categories = ['axes', 'font', 'grid', 'image', 'lines', 
                      'xtick', 'ytick']
        self.parameters = {}
        for category in categories:
            pc = self.parameters[category] = GridParameters()
            for p in [p for p in rcParams if p.startswith(category)]:
                dp = defaultParams[p]
                if 'color' in p:
                    try:
                        pc.add(p, rcParams[p], p, color=True, validate=dp[1])
                    except Exception:
                        pc.add(p, rcParams[p], p, validate=dp[1])
                else:
                    pc.add(p, rcParams[p], p, validate=dp[1])
            
        self.preferences_stack = self.parameter_stack(self.parameters, 
                                                      width=200)
        self.set_layout(self.preferences_stack, self.close_layout(save=True))


class CustomizeDialog(NXPanel):

    def __init__(self, parent=None):
        super(CustomizeDialog, self).__init__('customize', 
                                              title='Customize Plot', 
                                              parent=parent)
        self.tab_class = CustomizeTab
        self.plotview_sort = True


class CustomizeTab(NXTab):

    legend_location = {v: k for k, v in Legend.codes.items()}            

    def __init__(self, parent=None):
        super(CustomizeTab, self).__init__(parent=parent)

        from .plotview import markers, linestyles
        self.markers, self.linestyles = markers, linestyles

        self.name = self.plotview.label

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
                self.update_plot_parameters(plot)
            pg = self.parameters['legend'] = GridParameters()
            pg.add('legend', ['None'] + [key.title() for key in Legend.codes], 
                   'Legend')
            pg.add('label', ['Full Path', 'Name Only'], 'Label')
            self.update_legend_parameters()
            self.plot_stack = self.parameter_stack(pp)
            self.set_layout(pl.grid(header=False),
                           self.plot_stack,
                           pg.grid(header=False))
        self.parameters['labels']['title'].box.setFocus()

    def __repr__(self):
        return 'CustomizeTab("%s")' % self.name

    def plot_label(self, plot):
        return plot + ': ' + self.plots[plot]['label']

    def label_plot(self, label):
        return label[:label.index(':')]

    def update(self):
        self.update_labels()
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

    def update_labels(self):
        pl = self.parameters['labels']
        pl['title'].value = self.plotview.title
        pl['xlabel'].value = self.plotview.xaxis.label
        pl['ylabel'].value = self.plotview.yaxis.label

    def image_parameters(self):
        parameters = GridParameters()
        parameters.add('aspect', self.plotview._aspect, 'Aspect Ratio')
        parameters.add('skew', self.plotview._skew_angle, 'Skew Angle')
        parameters.add('grid', ['On', 'Off'], 'Grid')
        parameters.add('gridcolor', get_color(self.plotview._gridcolor), 'Grid Color', 
                       color=True)
        parameters.add('gridstyle', list(self.linestyles.values()), 
                       'Grid Style')
        parameters.grid(title='Image Parameters', header=False, width=125)
        return parameters

    def update_image_parameters(self):
        p = self.parameters['image']
        p['aspect'].value = self.plotview._aspect
        p['skew'].value = self.plotview._skew_angle
        if self.plotview._skew_angle is None:
            p['skew'].value = 90.0
        self.plotview._grid = (self.plotview.ax.xaxis._gridOnMajor and
                               self.plotview.ax.yaxis._gridOnMajor)
        if self.plotview._grid:
            p['grid'].value = 'On'
        else:
            p['grid'].value = 'Off'
        p['gridcolor'].value = get_color(self.plotview._gridcolor)
        p['gridstyle'].value = self.linestyles[self.plotview._gridstyle]

    def plot_parameters(self, plot):
        p = self.plots[plot]
        parameters = GridParameters()
        parameters.add('legend_label', p['legend_label'], 'Label')
        parameters.add('legend', ['Yes', 'No'], 'Add to Legend')
        parameters.add('color', p['color'], 'Color', color=True)
        parameters.add('linestyle', list(self.linestyles.values()), 
                       'Line Style')
        parameters.add('linewidth', p['linewidth'], 'Line Width')
        parameters.add('marker', list(self.markers.values()), 'Marker')
        parameters.add('markerstyle', ['filled', 'open'], 'Marker Style')
        parameters.add('markersize', p['markersize'], 'Marker Size')
        parameters.add('zorder', p['zorder'], 'Z-Order')
        parameters.grid(title='Plot Parameters', header=False, width=125)
        return parameters

    def update_plot_parameters(self, plot):
        label = self.plot_label(plot)
        p, pp = self.plots[plot], self.parameters[label]
        pp['legend_label'].value = p['legend_label']
        if p['show_legend']:
            pp['legend'].value = 'Yes'
        else:
            pp['legend'].value = 'No'
        pp['color'].value = p['color']
        if p['smooth_line']:
            pp['linestyle'].value = self.linestyles[p['smooth_linestyle']]
        else:
            pp['linestyle'].value = self.linestyles[p['linestyle']]
        pp['linewidth'].value = p['linewidth']
        pp['marker'].value = self.markers[p['marker']]
        pp['markerstyle'].value = p['markerstyle']
        pp['markersize'].value = p['markersize']
        pp['zorder'].value = p['zorder']

    def update_legend_parameters(self):
        p = self.parameters['legend']
        if self.plotview.ax.get_legend() and not self.is_empty_legend():
            _loc = self.plotview.ax.get_legend()._loc
            if _loc in self.legend_location:
                p['legend'].value = self.legend_location[_loc].title()
            else:
                p['legend'].value = 'Best'
        else:
            p['legend'].value = 'None'
        if self.plotview._nameonly == True:
            p['label'].value = 'Name Only'
        else:
            p['label'].value = 'Full Path'

    def is_empty_legend(self):
        labels = [self.plot_label(plot) for plot in self.plots]
        return 'Yes' not in [self.parameters[label]['legend'].value 
                             for label in labels]

    def set_legend(self):
        legend_location = self.parameters['legend']['legend'].value.lower()
        label_selection = self.parameters['legend']['label'].value
        if label_selection == 'Full Path':
            _nameonly = False
        else:
            _nameonly = True
        if legend_location == 'none' or self.is_empty_legend():
            self.plotview.remove_legend()
        else:
            plots = []
            labels = []
            for plot in self.plots:
                label = self.plot_label(plot)
                if self.parameters[label]['legend'].value == 'Yes':
                    plots.append(self.plots[plot]['plot'])
                    labels.append(self.plots[plot]['legend_label'])
            self.plotview.legend(plots, labels, nameonly=_nameonly, 
                                 loc=legend_location)         

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
                self.plotview._grid =True
            else:
                self.plotview._grid =False
            self.plotview._gridcolor = pi['gridcolor'].value
            self.plotview._gridstyle = [k for k, v in self.linestyles.items()
                                        if v == pi['gridstyle'].value][0]
            #reset in case plotview.aspect changed by plotview.skew            
            self.plotview.grid(self.plotview._grid)
            self.plotview.skew = _skew_angle
            self.plotview.aspect = self.plotview._aspect
        else:
            for plot in self.plots:
                label = self.plot_label(plot)
                p, pp = self.plots[plot], self.parameters[label]
                p['legend_label'] = pp['legend_label'].value
                if pp['legend'].value == 'Yes':
                    p['show_legend'] = True
                else:
                    p['show_legend'] = False
                p['color'] = pp['color'].value
                p['plot'].set_color(p['color'])
                linestyle = [k for k, v in self.linestyles.items()
                             if v == pp['linestyle'].value][0]
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
        self.update()
        self.plotview.draw()


class ProjectionDialog(NXPanel):
    """Dialog to set plot window limits"""
 
    def __init__(self, parent=None):
        super(ProjectionDialog, self).__init__('projection', title='Projection Panel', 
                                               apply=False, parent=parent)
        self.tab_class = ProjectionTab
        self.plotview_sort = True

    
class ProjectionTab(NXTab):
    """Tab to set plot window limits"""
 
    def __init__(self, parent=None):

        super(ProjectionTab, self).__init__(parent=parent)
        if parent:
            self.tabs = parent.tabs
            self.labels = parent.labels

        self.name = self.plotview.label
        self.ndim = self.plotview.ndim

        self.xlabel, self.xbox = self.label('X-Axis'), NXComboBox(self.set_xaxis)
        self.ylabel, self.ybox = self.label('Y-Axis'), NXComboBox(self.set_yaxis)
        axis_layout = self.make_layout(self.xlabel, self.xbox, self.ylabel, self.ybox)
                                       
        self.set_axes()

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
        self.overplot_box = NXCheckBox()
        if 'Projection' not in self.plotviews:
            self.overplot_box.setVisible(False)
        grid.addWidget(self.overplot_box, row, 3,
                       alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.mask_button = NXPushButton("Mask", self.mask_data, self)
        grid.addWidget(self.mask_button, row, 1)
        self.unmask_button = NXPushButton("Unmask", self.unmask_data, self)
        grid.addWidget(self.unmask_button, row, 2)

        self.set_layout(axis_layout, grid, 
                        self.checkboxes(("sum", "Sum Projections", False),
                                        ("lines", "Plot Lines", False),
                                        ("hide", "Hide Limits", False)),
                        self.copy_layout("Copy Limits"))
        self.checkbox["hide"].stateChanged.connect(self.hide_rectangle)                        

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

        self.update()

        self.xbox.setFocus()

    def __repr__(self):
        return 'ProjectionTab("%s")' % self.name

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
            axes.insert(0,'None')
            self.ybox.add(*axes)
            self.ybox.select(self.plotview.yaxis.name)

    @property
    def xaxis(self):
        return self.xbox.currentText()

    def set_xaxis(self):
        if self.xaxis == self.yaxis:
            self.ybox.select('None')

    @property
    def yaxis(self):
        if self.ndim <= 2:
            return 'None'
        else:
            return self.ybox.selected

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
        except:
            return False

    @summed.setter
    def summed(self, value):
        self.checkbox["sum"].setChecked(value)

    @property
    def lines(self):
        try:
            return self.checkbox["lines"].isChecked()
        except:
            return False

    @lines.setter
    def lines(self, value):
        self.checkbox["lines"].setChecked(value)

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
            if 'Projection' in self.plotviews:
                projection = self.plotviews['Projection']
            else:
                from .plotview import NXPlotView
                projection = NXPlotView('Projection')
                self.overplot_box.setChecked(False)
            axes, limits = self.get_projection()
            if len(axes) == 1 and self.overplot_box.isChecked():
                over = True
            else:
                over = False
            if self.lines:
                fmt = '-'
            else:
                fmt = 'o'
            projection.plot(self.plotview.data.project(axes, limits, 
                                                       summed=self.summed),
                            over=over, fmt=fmt)
            if len(axes) == 1:
                self.overplot_box.setVisible(True)
            else:
                self.overplot_box.setVisible(False)
                self.overplot_box.setChecked(False)
            projection.make_active()
            projection.raise_()
            self.tabs.update()
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
            self._rectangle = NXpolygon(self.get_rectangle(), closed=True).shape
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

    def rectangle_visible(self):
        return not self.checkbox["hide"].isChecked()

    def hide_rectangle(self):
        if self.checkbox["hide"].isChecked():
            self.rectangle.set_visible(False)
        else:
            self.rectangle.set_visible(True)
        self.plotview.draw()

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
                if  hi < maxbox.value():
                    maxbox.setValue(maxbox.valueFromIndex(ihi))
            else:
                minbox.setValue(minbox.valueFromIndex(ilo))
                maxbox.setValue(maxbox.valueFromIndex(ihi))
        self.block_signals(False)
        self.draw_rectangle()
        self.copywidget.setVisible(False)
        self.copybox.clear()
        for tab in [self.tabs[label] for label in self.tabs 
                    if self.tabs[label] is not self]:
            if self.plotview.ndim == tab.plotview.ndim:
                self.copywidget.setVisible(True)
                self.copybox.add(self.labels[tab])

    def copy(self):
        self.block_signals(True)
        tab = self.tabs[self.copybox.selected]
        for axis in range(self.ndim):
            self.minbox[axis].setValue(tab.minbox[axis].value())
            self.maxbox[axis].setValue(tab.maxbox[axis].value())
            self.lockbox[axis].setCheckState(tab.lockbox[axis].checkState())
        self.summed = tab.summed
        self.lines = tab.lines
        self.xbox.setCurrentIndex(tab.xbox.currentIndex())
        if self.ndim > 1:
            self.ybox.setCurrentIndex(tab.ybox.currentIndex())
        self.block_signals(False)
        self.draw_rectangle()              

    def reset(self):
        self.block_signals(True)
        for axis in range(self.ndim):
            self.minbox[axis].setValue(self.minbox[axis].data.min())
            self.maxbox[axis].setValue(self.maxbox[axis].data.max())
        self.block_signals(False)
        self.update()

    def close(self):
        try:
            self._rectangle.remove()
        except Exception:
            pass
        self._rectangle = None
        self.plotview.draw()


class LimitDialog(NXPanel):
    """Dialog to set plot window limits"""
 
    def __init__(self, parent=None):
        super(LimitDialog, self).__init__('limit', title='Plot Limits', 
              parent=parent)
        self.tab_class = LimitTab
        self.plotview_sort = True

    
class LimitTab(NXTab):
    """Tab to set plot window limits"""

    def __init__(self, parent=None):

        super(LimitTab, self).__init__(parent=parent)
        if parent:
            self.tabs = parent.tabs
            self.labels = parent.labels

        self.name = self.plotview.label
        self.ndim = self.plotview.ndim
        
        if self.ndim > 1:
            self.xlabel, self.xbox = self.label('X-Axis'), NXComboBox(self.set_xaxis)
            self.ylabel, self.ybox = self.label('Y-Axis'), NXComboBox(self.set_yaxis)
            axis_layout = self.make_layout(self.xlabel, self.xbox, self.ylabel, self.ybox)                                     
            self.set_axes()
        else:
            axis_layout = None

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
            self.minbox[axis] = NXSpinBox()
            self.maxbox[axis] = NXSpinBox()
            self.lockbox[axis] = NXCheckBox(slot=self.set_lock)
            grid.addWidget(self.label(self.plotview.axis[axis].name), row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)
            grid.addWidget(self.lockbox[axis], row, 3,
                           alignment=QtCore.Qt.AlignHCenter)

        row += 1
        self.minbox['signal'] = NXDoubleSpinBox()
        self.maxbox['signal'] = NXDoubleSpinBox()
        grid.addWidget(self.label(self.plotview.axis['signal'].name), row, 0)
        grid.addWidget(self.minbox['signal'], row, 1)
        grid.addWidget(self.maxbox['signal'], row, 2)        

        self.parameters = GridParameters()
        if self.plotview.label != 'Main':
            figure_size = self.plotview.figure.get_size_inches()
            xsize, ysize = figure_size[0], figure_size[1]
            self.parameters.add('xsize', xsize, 'Figure Size (H)')
            self.parameters.add('ysize', ysize, 'Figure Size (V)')

        self.set_layout(axis_layout, grid, 
                        self.parameters.grid(header=False), 
                        self.checkboxes(("hide", "Hide Limits", True)),
                        self.copy_layout("Copy Limits"))
        if self.ndim == 1:
            self.checkbox["hide"].setVisible(False)
        else:
            self.checkbox["hide"].stateChanged.connect(self.hide_rectangle)                        

        self._rectangle = None

        self.initialize()

    def __repr__(self):
        return 'LimitTab("%s")' % self.name

    def initialize(self):
        for axis in range(self.ndim):
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.axis[axis].centers
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.minbox[axis].diff = self.maxbox[axis].diff = None
            self.minbox[axis].setValue(self.plotview.axis[axis].lo)
            self.maxbox[axis].setValue(self.plotview.axis[axis].hi)
            self.minbox[axis].valueChanged[six.text_type].connect(self.set_limits)
            self.maxbox[axis].valueChanged[six.text_type].connect(self.set_limits)
        vaxis = self.plotview.axis['signal']
        self.minbox['signal'].data = self.maxbox['signal'].data = vaxis.data
        self.minbox['signal'].setRange(vaxis.min, vaxis.max)
        self.maxbox['signal'].setRange(vaxis.min, vaxis.max)
        self.minbox['signal'].setValue(vaxis.lo)
        self.maxbox['signal'].setValue(vaxis.hi)
        self.draw_rectangle()
        if self.ndim > 1:
            self.copied_properties = {'aspect': self.plotview.aspect,
                                      'cmap': self.plotview.cmap,
                                      'interpolation': self.plotview.interpolation,
                                      'logv': self.plotview.logv,
                                      'logx': self.plotview.logx,
                                      'logy': self.plotview.logy,
                                      'skew': self.plotview.skew}
        self.copywidget.setVisible(False)
        self.copybox.clear()
        for tab in [self.tabs[label] for label in self.tabs 
                    if self.tabs[label] is not self]:
            if self.plotview.ndim == tab.plotview.ndim:
                self.copywidget.setVisible(True)
                self.copybox.add(self.labels[tab])

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
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                min_value = self.maxbox[axis].value() - self.maxbox[axis].diff
                self.minbox[axis].setValue(min_value)
            elif self.minbox[axis].value() > self.maxbox[axis].value():
                self.maxbox[axis].setValue(self.minbox[axis].value())
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

    @property
    def rectangle(self):
        if self._rectangle not in self.plotview.ax.patches:
            self._rectangle = NXpolygon(self.get_rectangle(), closed=True).shape
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
        if self.ndim > 1:
            self.rectangle.set_xy(self.get_rectangle())
            self.plotview.draw()
            self.hide_rectangle()

    def rectangle_visible(self):
        return not self.checkbox["hide"].isChecked()

    def hide_rectangle(self):
        if self.checkbox["hide"].isChecked():
            self.rectangle.set_visible(False)
        else:
            self.rectangle.set_visible(True)
        self.plotview.draw()

    def update(self):
        self.copywidget.setVisible(False)
        self.copybox.clear()
        for tab in [self.tabs[label] for label in self.tabs 
                    if self.tabs[label] is not self]:
            if self.plotview.ndim == tab.plotview.ndim:
                self.copywidget.setVisible(True)
                self.copybox.add(self.labels[tab])
        self.draw_rectangle()

    def copy(self):
        tab = self.tabs[self.copybox.selected]
        for axis in range(self.ndim):
            self.minbox[axis].setValue(tab.minbox[axis].value())
            self.maxbox[axis].setValue(tab.maxbox[axis].value())
            self.lockbox[axis].setCheckState(tab.lockbox[axis].checkState())
        self.minbox['signal'].setValue(tab.minbox['signal'].value())
        self.maxbox['signal'].setValue(tab.maxbox['signal'].value())
        if self.ndim > 1:
            self.xbox.setCurrentIndex(tab.xbox.currentIndex())
            self.ybox.setCurrentIndex(tab.ybox.currentIndex())
            for p in self.copied_properties:
                self.copied_properties[p] = getattr(tab.plotview, p)
        if self.plotview.label != 'Main':
            if tab.plotview.label == 'Main':
                figure_size = tab.plotview.figure.get_size_inches()
                self.parameters['xsize'].value = figure_size[0]
                self.parameters['ysize'].value = figure_size[1]
            else:
                self.parameters['xsize'].value = tab.parameters['xsize'].value
                self.parameters['ysize'].value = tab.parameters['ysize'].value

    def reset(self):
        self.set_axes()
        for axis in range(self.ndim):
            self.lockbox[axis].setChecked(False)
            self.minbox[axis].setValue(self.plotview.axis[axis].lo)
            self.maxbox[axis].setValue(self.plotview.axis[axis].hi)
        self.minbox['signal'].setValue(self.plotview.axis['signal'].lo)
        self.maxbox['signal'].setValue(self.plotview.axis['signal'].hi)
        if self.plotview.label != 'Main':
            figure_size = self.plotview.figure.get_size_inches()
            self.parameters['xsize'].value = figure_size[0]
            self.parameters['ysize'].value = figure_size[1]
        if self.ndim > 1:
            self.copied_properties = {'aspect': self.plotview.aspect,
                                      'cmap': self.plotview.cmap,
                                      'interpolation': self.plotview.interpolation,
                                      'logv': self.plotview.logv,
                                      'logx': self.plotview.logx,
                                      'logy': self.plotview.logy,
                                      'skew': self.plotview.skew}
        self.update()

    def apply(self):
        try:
            if self.ndim == 1:
                xmin, xmax = self.minbox[0].value(), self.maxbox[0].value()
                ymin, ymax = self.minbox['signal'].value(), self.maxbox['signal'].value()
                if np.isclose(xmin, xmax):
                    raise NeXusError('X-axis has zero range')
                elif np.isclose(ymin, ymax):
                    raise NeXusError('Y-axis has zero range')
                self.plotview.xtab.set_limits(xmin, xmax)
                self.plotview.ytab.set_limits(ymin, ymax)
                self.plotview.replot_axes()
            else:
                x = self.get_axes().index(self.xaxis)
                xmin, xmax = self.minbox[x].value(), self.maxbox[x].value()
                y = self.get_axes().index(self.yaxis)
                ymin, ymax = self.minbox[y].value(), self.maxbox[y].value()
                vmin, vmax = self.minbox['signal'].value(), self.maxbox['signal'].value()
                if np.isclose(xmin, xmax):
                    raise NeXusError('X-axis has zero range')
                elif np.isclose(ymin, ymax):
                    raise NeXusError('Y-axis has zero range')
                elif np.isclose(vmin, vmax):
                    raise NeXusError('Signal has zero range')
                self.plotview.change_axis(self.plotview.xtab, self.plotview.axis[x])
                self.plotview.change_axis(self.plotview.ytab, self.plotview.axis[y])
                self.plotview.xtab.set_limits(xmin, xmax)
                self.plotview.ytab.set_limits(ymin, ymax)
                self.plotview.autoscale = False
                self.plotview.vtab.set_limits(vmin, vmax)
                if self.ndim > 2:
                    self.plotview.ztab.locked = False
                    for axis_name in self.plotview.ztab.axiscombo.items():
                        self.plotview.ztab.axiscombo.select(axis_name)
                        names = [self.plotview.axis[i].name for i in range(self.ndim)]
                        idx = names.index(self.plotview.ztab.axiscombo.selected)
                        self.plotview.ztab.set_axis(self.plotview.axis[idx])
                        self.plotview.ztab.set_limits(self.minbox[idx].value(),
                                                      self.maxbox[idx].value())
                self.plotview.replot_data()
                for p in self.copied_properties:
                    setattr(self.plotview, p, self.copied_properties[p])
            if self.plotview.label != 'Main':
                xsize, ysize = (self.parameters['xsize'].value, 
                                self.parameters['ysize'].value)
                self.plotview.figure.set_size_inches(xsize, ysize)
        except NeXusError as error:
            report_error("Setting plot limits", error)
            self.reset()

    def close(self):
        try:
            self._rectangle.remove()
        except Exception:
            pass
        self._rectangle = None
        self.plotview.draw()
 
    
class ViewDialog(NXDialog):
    """Dialog to view a NeXus field"""

    def __init__(self, node, parent=None):

        super(ViewDialog, self).__init__(parent, default=True)

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
                self.properties.add('linkfile', node._filename, target_file_label)
            elif node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
                self.properties.add('linkfile', node.nxfilename, target_file_label)
        elif node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
            self.properties.add('target', node.nxfilepath, 'Target Path')
            self.properties.add('linkfile', node.nxfilename, target_file_label)
        if node.nxfilemode:
            self.properties.add('filemode', node.nxfilemode, 'Mode')
        if target_error:
            pass
        elif isinstance(node, NXfield) and node.shape is not None:
            if node.shape == () or node.shape == (1,):
                self.properties.add('value', six.text_type(node), 'Value')
            self.properties.add('dtype', node.dtype, 'Dtype')
            self.properties.add('shape', six.text_type(node.shape), 'Shape')
            self.properties.add('maxshape', six.text_type(node.maxshape), 'Maximum Shape')
            self.properties.add('fillvalue', six.text_type(node.fillvalue), 'Fill Value')
            self.properties.add('chunks', six.text_type(node.chunks), 'Chunk Size')
            self.properties.add('compression', six.text_type(node.compression), 
                                'Compression')
            self.properties.add('compression_opts', six.text_type(node.compression_opts), 
                                'Compression Options')
            self.properties.add('shuffle', six.text_type(node.shuffle), 'Shuffle Filter')
            self.properties.add('fletcher32', six.text_type(node.fletcher32), 
                                'Fletcher32 Filter')
        elif isinstance(node, NXgroup):
            self.properties.add('entries', len(node.entries), 'No. of Entries')
        layout.addLayout(self.properties.grid(header=False, 
                                              title='Properties', 
                                              width=200))
        if target_error:
            layout.addWidget(QtWidgets.QLabel(target_error))
        
        layout.addStretch()

        if node.attrs:
            self.attributes = GridParameters()
            for attr in node.attrs:
                self.attributes.add(attr, six.text_type(node.attrs[attr]), attr)
            layout.addLayout(self.attributes.grid(header=False, 
                                                  title='Attributes', 
                                                  width=200))
            layout.addStretch()

        if (isinstance(node, NXfield) and node.shape is not None and 
               node.shape != () and node.shape != (1,)):
            hlayout = QtWidgets.QHBoxLayout()
            hlayout.addLayout(layout)
            hlayout.addLayout(self.table())
            vlayout = QtWidgets.QVBoxLayout()
            vlayout.addLayout(hlayout)
            vlayout.addWidget(self.close_buttons(close=True))
            vlayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
            self.setLayout(vlayout)          
        else:
            layout.addWidget(self.close_buttons(close=True))
            self.setLayout(layout)

        self.setWindowTitle(node.nxroot.nxname+node.nxpath)

    def table(self):
        layout = QtWidgets.QVBoxLayout()

        title_layout = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel('Values')
        header_font = QtGui.QFont()
        header_font.setBold(True)
        title_label.setFont(header_font)
        title_layout.addStretch()
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        layout.addLayout(title_layout)

        if [s for s in self.node.shape if s > 10]:
            idx = []
            for i, s in enumerate(self.node.shape):
                spinbox = QtWidgets.QSpinBox()
                spinbox.setRange(0, s-1)   
                spinbox.valueChanged[six.text_type].connect(self.choose_data)
                if len(self.node.shape) - i > 2:
                    idx.append(0)
                else:
                    idx.append(np.s_[0:min(s,10)])
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
        self.table_model = ViewTableModel(self, data)
        self.table_view.setModel(self.table_model)
        self.table_view.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarAlwaysOff)
        self.table_view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.table_view.setSortingEnabled(False)
        self.set_size()
        layout.addWidget(self.table_view)
        layout.addStretch()

        return layout

    def choose_data(self):
        idx = [s.value() for s in self.spinboxes]
        if len(idx) > 1:
            origin = [idx[-2], idx[-1]]
            for i in [-2,-1]:
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

    def __init__(self, parent, data, *args):
        super(ViewTableModel, self).__init__(parent, *args)
        self._data = self.get_data(data)
        self.origin = [0, 0]

    def get_data(self, data):
        if len(data.shape) == 1:
            self.rows = data.shape[0]
            self.columns = 1
            return data.reshape((data.shape[0],1))
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
        text = six.text_type(value).lstrip('[').rstrip(']')
        if role == QtCore.Qt.DisplayRole:
            try:
                return '%.6g' % float(text)
            except (TypeError, ValueError):
                return (text[:10] + '..') if len(text) > 10 else text
        elif role == QtCore.Qt.ToolTipRole:
            return text
        return None

    def headerData(self, position, orientation, role):
        if (orientation == QtCore.Qt.Horizontal and 
            role == QtCore.Qt.DisplayRole):
            return six.text_type(self.origin[1] + range(10)[position])
        elif (orientation == QtCore.Qt.Vertical and 
              role == QtCore.Qt.DisplayRole):
            return six.text_type(self.origin[0] + range(10)[position])
        return None

    def choose_data(self, data, origin):
        self.layoutAboutToBeChanged.emit()
        self._data = self.get_data(data)
        self.origin = origin
        self.layoutChanged.emit()
        self.headerDataChanged.emit(QtCore.Qt.Horizontal, 0, 
                                    min(9, self.columns-1))
        self.headerDataChanged.emit(QtCore.Qt.Vertical, 0, min(9, self.rows-1))

  
class RemoteDialog(NXDialog):
    """Dialog to open a remote file.
    """ 
    def __init__(self, parent=None):

        try:
            import h5pyd
            from nexusformat.nexus import nxgetserver, nxgetdomain
        except ImportError:
            raise NeXusError("Please install h5pyd for remote data access")

        super(RemoteDialog, self).__init__()
 
        self.parameters = GridParameters()
        self.parameters.add('server', nxgetserver(), 'Server')
        self.parameters.add('domain', nxgetdomain(), 'Domain')
        self.parameters.add('filepath', '', 'File Path')
        self.set_layout(self.parameters.grid(width=200), self.close_buttons())
        self.set_title('Open Remote File')

    def accept(self):
        try:
            from nexusformat.nexus import nxloadremote
            server = self.parameters['server'].value
            domain = self.parameters['domain'].value
            filepath = self.parameters['filepath'].value
            root = nxloadremote(filepath, server=server, domain=domain)
            name = self.mainwindow.treeview.tree.get_name(filepath)               
            self.mainwindow.treeview.tree[name] = \
                self.mainwindow.user_ns[name] = root
            logging.info(
                "Opening remote NeXus file '%s' on '%s' as workspace '%s'"
                % (root.nxfilename, root._file, name))
            super(RemoteDialog, self).accept()
        except NeXusError as error:
            report_error("Opening remote file", error)
            super(RemoteDialog, self).reject()


class AddDialog(NXDialog):
    """Dialog to add a NeXus node"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16', 
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']
 
    def __init__(self, node, parent=None):

        super(AddDialog, self).__init__(parent)

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

        name_label = QtWidgets.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("Name:")
        self.name_box = QtWidgets.QLineEdit()
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        if class_name == "NXgroup":
            combo_label = QtWidgets.QLabel()
            combo_label.setAlignment(QtCore.Qt.AlignLeft)
            combo_label.setText("Group Class:")
            self.combo_box = NXComboBox(self.select_combo)
            standard_groups = sorted(list(set([g for g in 
                self.mainwindow.nxclasses[self.node.nxclass][2]])))
            for name in standard_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in self.mainwindow.nxclasses 
                                   if g not in standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            grid.addWidget(combo_label, 0, 0)
            grid.addWidget(self.combo_box, 0, 1)
            grid.addWidget(name_label, 1, 0)
            grid.addWidget(self.name_box, 1, 1)
            self.select_combo()
        elif class_name == "NXfield":
            combo_label = QtWidgets.QLabel()
            combo_label.setAlignment(QtCore.Qt.AlignLeft)
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
            value_label = QtWidgets.QLabel()
            value_label.setAlignment(QtCore.Qt.AlignLeft)
            value_label.setText("Value:")
            self.value_box = QtWidgets.QLineEdit()
            self.value_box.setAlignment(QtCore.Qt.AlignLeft)
            grid.addWidget(value_label, 1, 0)
            grid.addWidget(self.value_box, 1, 1)
            units_label = QtWidgets.QLabel()
            units_label.setAlignment(QtCore.Qt.AlignLeft)
            units_label.setText("Units:")
            self.units_box = QtWidgets.QLineEdit()
            self.units_box.setAlignment(QtCore.Qt.AlignLeft)
            grid.addWidget(units_label, 2, 0)
            grid.addWidget(self.units_box, 2, 1)
            type_label = QtWidgets.QLabel()
            type_label.setAlignment(QtCore.Qt.AlignLeft)
            type_label.setText("Datatype:")
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
            value_label = QtWidgets.QLabel()
            value_label.setAlignment(QtCore.Qt.AlignLeft)
            value_label.setText("Value:")
            self.value_box = QtWidgets.QLineEdit()
            self.value_box.setAlignment(QtCore.Qt.AlignLeft)
            grid.addWidget(value_label, 1, 0)
            grid.addWidget(self.value_box, 1, 1)
            type_label = QtWidgets.QLabel()
            type_label.setAlignment(QtCore.Qt.AlignLeft)
            type_label.setText("Datatype:")
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
            logging.info("'%s' added to '%s'" 
                         % (self.node[name], self.node.nxpath)) 
        elif name:
            value = self.get_value()
            dtype = self.get_type()
            if value is not None:
                if self.class_name == "NXfield":
                    self.node[name] = NXfield(value, dtype=dtype)
                    logging.info("'%s' added to '%s'" 
                                 % (name, self.node.nxpath)) 
                    units = self.get_units()
                    if units:
                        self.node[name].attrs['units'] = units
                else:
                    self.node.attrs[name] = NXattr(value, dtype=dtype)
                    logging.info("Attribute '%s' added to '%s'" 
                         % (name, self.node.nxpath)) 
        super(AddDialog, self).accept()

    
class InitializeDialog(NXDialog):
    """Dialog to initialize a NeXus field node"""

    data_types = ['float32', 'float64', 'int8', 'uint8', 'int16', 
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']
 
    def __init__(self, node, parent=None):

        super(InitializeDialog, self).__init__(parent)
 
        self.node = node

        self.setWindowTitle("Initialize NeXus Data")

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        name_label = QtWidgets.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("Name:")
        self.name_box = QtWidgets.QLineEdit()
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
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
        type_label = QtWidgets.QLabel()
        type_label.setAlignment(QtCore.Qt.AlignLeft)
        type_label.setText("Datatype:")
        self.type_box = NXComboBox()
        for name in self.data_types:
            self.type_box.addItem(name)
        self.type_box.setCurrentIndex(0)
        grid.addWidget(type_label, 2, 0)
        grid.addWidget(self.type_box, 2, 1)
        shape_label = QtWidgets.QLabel()
        shape_label.setAlignment(QtCore.Qt.AlignLeft)
        shape_label.setText("Shape:")
        self.shape_box = QtWidgets.QLineEdit()
        self.shape_box.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(shape_label, 3, 0)
        grid.addWidget(self.shape_box, 3, 1)
        grid.setColumnMinimumWidth(1, 200)
        fill_label = QtWidgets.QLabel()
        fill_label.setAlignment(QtCore.Qt.AlignLeft)
        fill_label.setText("Fill Value:")
        self.fill_box = QtWidgets.QLineEdit('0')
        self.fill_box.setAlignment(QtCore.Qt.AlignLeft)
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
                logging.info("'%s' initialized in '%s'" 
                         % (self.node[name], self.node.nxpath)) 
                super(InitializeDialog, self).accept()
            else:
                raise NeXusError("Invalid name")
        except NeXusError as error:
            report_error("Initializing Data", error)

    
class RenameDialog(NXDialog):
    """Dialog to rename a NeXus node"""

    def __init__(self, node, parent=None):

        super(RenameDialog, self).__init__(parent)

        self.node = node

        self.setWindowTitle("Rename NeXus data")

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.define_grid())
        self.layout.addWidget(self.close_buttons()) 
        self.setLayout(self.layout)

    def define_grid(self):
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        name_label = QtWidgets.QLabel()
        name_label.setAlignment(QtCore.Qt.AlignLeft)
        name_label.setText("New Name:")
        self.name_box = QtWidgets.QLineEdit(self.node.nxname)
        self.name_box.setAlignment(QtCore.Qt.AlignLeft)
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        self.combo_box = None
        if (isinstance(self.node, NXgroup) and 
            not isinstance(self.node, NXlink) and 
            self.node.nxclass != 'NXroot'):
            combo_label = QtWidgets.QLabel()
            combo_label.setAlignment(QtCore.Qt.AlignLeft)
            combo_label.setText("New Class:")
            self.combo_box = NXComboBox()
            parent_class = self.node.nxgroup.nxclass
            standard_groups = sorted(list(set([g for g in 
                                  self.mainwindow.nxclasses[parent_class][2]])))
            for name in standard_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
                    wrap(self.mainwindow.nxclasses[name][0], 40),
                    QtCore.Qt.ToolTipRole)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in self.mainwindow.nxclasses 
                                   if g not in standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
                self.combo_box.setItemData(self.combo_box.count()-1, 
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
                combo_label = QtWidgets.QLabel()
                combo_label.setAlignment(QtCore.Qt.AlignLeft)
                combo_label.setText("Valid Fields:")
                self.combo_box = NXComboBox(self.set_name)
                fields = sorted(list(set([g for g in 
                                self.mainwindow.nxclasses[parent_class][1]])))
                for name in fields:
                    self.combo_box.addItem(name)
                    self.combo_box.setItemData(
                       self.combo_box.count()-1, 
                       wrap(self.mainwindow.nxclasses[parent_class][1][name][2], 
                            40),
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
        super(RenameDialog, self).accept()

    
class SignalDialog(NXDialog):
    """Dialog to set the signal of NXdata"""
 
    def __init__(self, node, parent=None):

        super(SignalDialog, self).__init__(parent)

        if isinstance(node, NXfield):
            self.group = node.nxgroup
            signal_name = node.nxname
        else:
            self.group = node
            if self.group.nxsignal is not None:
                signal_name = self.group.nxsignal.nxname
            else:
                signal_name = None

        self.signal_combo =  NXComboBox() 
        for node in self.group.values():
            if isinstance(node, NXfield) and node.shape != ():
                self.signal_combo.addItem(node.nxname)
        if self.signal_combo.count() == 0:
            raise NeXusError("No plottable field in group")
        if signal_name:
            idx =  self.signal_combo.findText(signal_name)
            if idx >= 0:
                self.signal_combo.setCurrentIndex(idx)
            else:
                self.signal_combo.setCurrentIndex(0)
        else:
            self.signal_combo.setCurrentIndex(0)
        self.signal_combo.currentIndexChanged.connect(self.choose_signal)

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        self.grid.addWidget(QtWidgets.QLabel('Signal :'), 0, 0)
        self.grid.addWidget(self.signal_combo, 0, 1)
        self.choose_signal()

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.grid)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

        self.setWindowTitle("Set signal for %s" % self.group.nxname)

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
                self.grid.addWidget(QtWidgets.QLabel("Axis %s: " % axis), 
                                    row, 0)
                self.grid.addWidget(self.axis_boxes[axis], row, 1)
        while row < self.grid.rowCount() - 1:
            self.remove_axis(row)
            row += 1   

    def axis_box(self, axis=0):
        box = NXComboBox()
        for node in self.group.values():
            if node is not self.signal and self.check_axis(node, axis):
                box.addItem(node.nxname)
        if box.count() == 0:
            return None
        if 'axes' in self.signal.attrs:
            from nexusformat.nexus.tree import _readaxes
            default_axis = _readaxes(self.signal.axes)[axis]
        else:
            axes = self.group.nxaxes
            if axes is not None:
                default_axis = self.group.nxaxes[axis].nxname
            else:
                default_axis = None
        if default_axis:
            try:
                box.setCurrentIndex(box.findText(default_axis))
            except Exception:
                pass
        else:
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
        try:
            return self.group[self.axis_boxes[axis].currentText()]
        except Exception:
            return None

    def get_axes(self):
        return [self.get_axis(axis) for axis in range(self.ndim)]

    def accept(self):
        try:
            axes = self.get_axes()
            if None in axes:
                raise NeXusError("Unable to set axes")
            if len(set([axis.nxname for axis in axes])) < len(axes):
                raise NeXusError("Cannot have duplicate axes")
            self.group.nxsignal = self.signal
            self.group.nxaxes = axes
            super(SignalDialog, self).accept()
        except NeXusError as error:
            report_error("Setting signal", error)
            super(SignalDialog, self).reject()

    
class LogDialog(NXDialog):
    """Dialog to display a NeXpy log file"""
 
    def __init__(self, parent=None):

        super(LogDialog, self).__init__(parent)
 
        self.log_directory = self.mainwindow.nexpy_dir
 
        layout = QtWidgets.QVBoxLayout()
        self.text_box = QtWidgets.QTextEdit()
        self.text_box.setMinimumWidth(800)
        self.text_box.setMinimumHeight(600)
        self.text_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.text_box.setReadOnly(True)
        layout.addWidget(self.text_box)
        footer_layout = QtWidgets.QHBoxLayout()
        self.file_combo = NXComboBox(self.show_log)
        for file_name in self.get_filesindirectory('nexpy', extension='.log*',
                                                directory=self.log_directory):
            self.file_combo.addItem(file_name)
        self.file_combo.setCurrentIndex(self.file_combo.findText('nexpy.log'))
        close_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        close_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        close_box.setFocus()
        close_box.rejected.connect(self.reject)
        footer_layout.addStretch()
        footer_layout.addWidget(self.file_combo)
        footer_layout.addWidget(close_box)
        layout.addLayout(footer_layout)
        self.setLayout(layout)

        self.show_log()

    @property
    def file_name(self):
        return os.path.join(self.log_directory, self.file_combo.currentText())

    def mouseReleaseEvent(self, event):
        self.show_log()

    def show_log(self):
        with open(self.file_name, 'r') as f:
            self.text_box.setText(convertHTML(f.read()))
        self.text_box.verticalScrollBar().setValue(
            self.text_box.verticalScrollBar().maximum())
        self.setWindowTitle("Log File: %s" % self.file_name)
        self.setVisible(True)
        self.raise_()
        self.activateWindow()

    def reject(self):
        super(LogDialog, self).reject()
        self.mainwindow.log_window = None


class UnlockDialog(NXDialog):
    """Dialog to unlock a file"""

    def __init__(self, node, parent=None):

        super(UnlockDialog, self).__init__(parent)

        self.setWindowTitle("Unlock File")
        self.node = node

        file_size = os.path.getsize(self.node.nxfilename)
        if file_size < 10000000:
            default = True
        else:
            default = False

        self.set_layout(self.labels(
                            "<b>Are you sure you want to unlock the file?</b>"),
                        self.checkboxes(('backup', 'Backup file (%s)' 
                                         % human_size(file_size), default)),
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
                logging.info("Workspace '%s' backed up to '%s'" 
                             % (self.node.nxname, self.node.nxbackup))
            self.node.unlock()
            logging.info("Workspace '%s' unlocked" % self.node.nxname)
            super(UnlockDialog, self).accept()
        except NeXusError as error:
            report_error("Unlocking file", error)


class ManageBackupsDialog(NXDialog):
    """Dialog to restore or purge backup files"""

    def __init__(self, parent=None):

        super(ManageBackupsDialog, self).__init__(parent, default=True)
 
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
        items = []
        for backup in backups:
            date = format_timestamp(os.path.basename(os.path.dirname(backup)))
            name = self.get_name(backup)
            size = os.path.getsize(backup)
            items.append(
                self.checkboxes((backup, '%s: %s (%s)' 
                                         % (date, name, human_size(size)), 
                                 False), align='left'))
        items.append(self.action_buttons(('Restore Files', self.restore),
                                         ('Delete Files', self.delete)))
        items.append(self.close_buttons(close=True))

        self.set_layout(*items)

        self.set_title('Manage Backups')

    def get_name(self, backup):
        name, ext = os.path.splitext(os.path.basename(backup))
        return name[:name.find('_backup')] + ext

    def restore(self):
        for backup in self.checkbox:
            if self.checkbox[backup].isChecked():
                name = self.tree.get_name(self.get_name(backup))
                self.tree[name] = self.mainwindow.user_ns[name] = nxload(backup)
                self.checkbox[backup].setChecked(False)
                self.checkbox[backup].setDisabled(True)

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
                        os.path.realpath(backup).startswith(self.backup_dir)):
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

        super(InstallPluginDialog, self).__init__(parent)

        self.local_directory = self.mainwindow.plugin_dir
        self.nexpy_directory = pkg_resources.resource_filename('nexpy', 
                                                               'plugins')
        self.backup_dir = self.mainwindow.backup_dir

        self.setWindowTitle("Install Plugin")

        self.set_layout(self.directorybox('Choose plugin directory'), 
                        self.radiobuttons(('local', 'Install locally', True),
                                          ('nexpy', 'Install in NeXpy', False)), 
                        self.close_buttons())
        self.set_title('Installing Plugin')

    def get_menu_name(self, plugin_name, plugin_path):
        try:
            plugin_module = import_plugin(plugin_name, [plugin_path])
            name, _ = plugin_module.plugin_menu()
            return name
        except Exception:
            return None

    def install_plugin(self):        
        plugin_directory = self.get_directory()
        plugin_name = os.path.basename(os.path.normpath(plugin_directory))
        plugin_path = os.path.dirname(plugin_directory)
        plugin_menu_name = self.get_menu_name(plugin_name, plugin_path)
        if plugin_menu_name is None:
            raise NeXusError("This directory does not contain a valid plugin")
        if self.radiobutton['local'].isChecked():
            plugin_path = self.local_directory
        else:
            plugin_path = self.nexpy_directory
        installed_path = os.path.join(plugin_path, plugin_name)
        if os.path.exists(installed_path):
            if self.confirm_action("Overwrite plugin?", 
                                   "Plugin '%s' already exists" % plugin_name):
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
                       if action.text() == plugin_menu_name]:
            self.mainwindow.menuBar().removeAction(action)   
        self.mainwindow.add_plugin_menu(plugin_name, [plugin_path])

    def accept(self):
        try:
            self.install_plugin()
            super(InstallPluginDialog, self).accept()
        except NeXusError as error:
            report_error("Installing plugin", error)


class RemovePluginDialog(NXDialog):
    """Dialog to remove a NeXus plugin"""

    def __init__(self, parent=None):

        super(RemovePluginDialog, self).__init__(parent)
 
        self.local_directory = self.mainwindow.plugin_dir
        self.nexpy_directory = pkg_resources.resource_filename('nexpy', 
                                                               'plugins')
        self.backup_dir = self.mainwindow.backup_dir

        self.setWindowTitle("Remove Plugin")

        self.set_layout(self.directorybox('Choose plugin directory'), 
                        self.radiobuttons(('local', 'Local plugin', True),
                                          ('nexpy', 'NeXpy plugin', False)), 
                        self.close_buttons())
        self.set_title('Removing Plugin')
        self.radiobutton['local'].clicked.connect(self.set_local_directory)
        self.radiobutton['nexpy'].clicked.connect(self.set_nexpy_directory)
        self.set_local_directory()

    def set_local_directory(self):
        self.set_default_directory(self.local_directory)
        self.directoryname.setText(self.local_directory)

    def set_nexpy_directory(self):
        self.set_default_directory(self.nexpy_directory)
        self.directoryname.setText(self.nexpy_directory)

    def get_menu_name(self, plugin_name, plugin_path):
        try:
            plugin_module = import_plugin(plugin_name, [plugin_path])
            name, _ = plugin_module.plugin_menu()
            return name
        except:
            return None

    def remove_plugin(self):
        plugin_directory = self.get_directory()
        if (os.path.dirname(plugin_directory) != self.local_directory and
            os.path.dirname(plugin_directory) != self.nexpy_directory):
            raise NeXusError("Directory '%s' not in plugins directory"
                             % plugin_directory)
        plugin_name = os.path.basename(os.path.normpath(plugin_directory))
        plugin_menu_name = self.get_menu_name(plugin_name, plugin_directory)
        if plugin_menu_name is None:
            raise NeXusError("This directory does not contain a valid plugin")
        if os.path.exists(plugin_directory):
            if self.confirm_action("Remove '%s'?" % plugin_directory, 
                                   "This cannot be reversed"):
                backup = os.path.join(self.backup_dir, timestamp())
                os.mkdir(backup)
                shutil.move(plugin_directory, backup)
                self.mainwindow.settings.set('plugins', 
                                             os.path.join(backup, plugin_name))
                self.mainwindow.settings.save()
            else:
                return
        for action in [action for action 
                       in self.mainwindow.menuBar().actions() 
                        if action.text().lower() == plugin_name.lower()]:
            self.mainwindow.menuBar().removeAction(action)   

    def accept(self):
        try:
            self.remove_plugin()
            super(RemovePluginDialog, self).accept()
        except NeXusError as error:
            report_error("Removing plugin", error)

class RestorePluginDialog(NXDialog):
    """Dialog to restore plugins from backups"""

    def __init__(self, parent=None):

        super(RestorePluginDialog, self).__init__(parent, default=True)
 
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
            plugin_list.append((plugin, '%s: %s' % (date, name), checked)) 
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

    def get_menu_name(self, plugin_name, plugin_path):
        try:
            plugin_module = import_plugin(plugin_name, [plugin_path])
            name, _ = plugin_module.plugin_menu()
            return name
        except Exception:
            return None

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
        plugin_menu_name = self.get_menu_name(plugin_name, plugin_path)
        if plugin_menu_name is None:
            raise NeXusError("This directory does not contain a valid plugin")
        if self.radiobutton['local'].isChecked():
            plugin_path = self.local_directory
        else:
            plugin_path = self.nexpy_directory
        restored_path = os.path.join(plugin_path, plugin_name)
        if os.path.exists(restored_path):
            if self.confirm_action("Overwrite plugin?", 
                                   "Plugin '%s' already exists" % plugin_name):
                backup = os.path.join(self.backup_dir, timestamp())
                os.mkdir(backup)
                shutil.move(restored_path, backup)
                self.mainwindow.settings.set('plugins', 
                                             os.path.join(backup, plugin_name))
                self.mainwindow.settings.save()
            else:
                return
        shutil.copytree(plugin_directory, restored_path)
        self.remove_backup(plugin_directory)

        for action in [action for action 
                       in self.mainwindow.menuBar().actions() 
                       if action.text() == plugin_menu_name]:
            self.mainwindow.menuBar().removeAction(action)   
        self.mainwindow.add_plugin_menu(plugin_name, [plugin_path])

        self.accept()
