# -----------------------------------------------------------------------------
# Copyright (c) 2018-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import bisect
import math
import warnings
from operator import attrgetter
from pathlib import Path

import numpy as np
from matplotlib import colors
from matplotlib.patches import Ellipse, Polygon, Rectangle
from nexusformat.nexus import NeXusError, NXfield, NXroot
from pygments.formatter import Formatter
from pygments.lexers import PythonLexer
from pygments.styles import get_style_by_name
from pygments.token import Token

from .pyqt import QtCore, QtGui, QtWidgets, getOpenFileName
from .utils import (boundaries, confirm_action, display_message, find_nearest,
                    format_float, get_color, get_mainwindow, in_dark_mode,
                    natural_sort, report_error)

warnings.filterwarnings("ignore", category=DeprecationWarning)

bold_font = QtGui.QFont()
bold_font.setBold(True)


class NXWidget(QtWidgets.QWidget):

    def __init__(self, parent=None):
        """
        Initialize a NeXpy widget.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        from .consoleapp import _mainwindow
        self.mainwindow = _mainwindow
        if parent is None:
            parent = self.mainwindow
        super().__init__(parent=parent)
        self.set_attributes()

    def set_attributes(self):
        """
        Initialize the attributes of the widget.

        This method should be called by a subclass' __init__ method. It
        sets the attributes of the widget, such as the tree view, the
        tree, the plot view, the main window, default directory, and
        more.

        Attributes
        ----------
        treeview : NXTreeView
            The tree view of the main window.
        tree : NXTree
            The tree of the main window.
        plotview : NXPlotView
            The active plot view of the main window.
        plotviews : list of NXPlotView
            The list of plot views of the main window.
        active_plotview : NXPlotView
            The active plot view of the main window.
        default_directory : str
            The default directory for file dialogs.
        import_file : str or None
            The file to import when the dialog is opened, by default
            None.
        nexus_filter : str
            A string of file filters for the file dialog.
        textbox : dict
            A dictionary of text boxes.
        pushbutton : dict
            A dictionary of push buttons.
        checkbox : dict
            A dictionary of check boxes.
        radiobutton : dict
            A dictionary of radio buttons.
        radiogroup : list of QButtonGroup
            A list of radio button groups.
        confirm_action : function
            A function to ask for confirmation before performing an
            action.
        display_message : function
            A function to display a message in the status bar.
        report_error : function
            A function to report an error.
        thread : QThread or None
            A thread to run a long-running task, by default None.
        bold_font : QFont
            A bold font.
        accepted : bool
            A flag indicating whether the dialog was accepted or not.
        """
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
        """
        Set the layout of the dialog.

        Parameters
        ----------
        *items : layouts or widgets
            A variable number of layouts or widgets to add to the
            dialog.
        **opts : dict
            Options for the layout. The 'spacing' key sets the spacing
            between items in the layout. The default value is 10.

        Returns
        -------
        layout : QVBoxLayout
            The layout of the dialog.
        """
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
        """
        Create a layout from a list of items.

        Parameters
        ----------
        *items : layouts, widgets, or strings
            A variable number of items to add to the layout. A string
            will be added as a label. A stretch can be added by passing
            the string 'stretch'.
        **opts : dict
            Options for the layout. The 'vertical' key sets whether the
            layout is vertical or horizontal. The 'align' key sets the
            alignment of the layout. The 'spacing' key sets the spacing
            between items in the layout. The default value is 20.

        Returns
        -------
        layout : QVBoxLayout or QHBoxLayout
            The created layout.
        """
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
        """
        Add items to the layout of the dialog.

        Parameters
        ----------
        *items : layouts, widgets, or strings
            A variable number of items to add to the layout. A string
            will be added as a label.
        stretch : bool, optional
            Add a stretch to the layout after adding all the items.
            The default value is False.
        """
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
        """
        Insert items into the layout at the given index.

        Parameters
        ----------
        index : int
            The index to insert the items at.
        *items : layouts, widgets, or strings
            A variable number of items to insert into the layout. A
            string will be added as a label.
        """
        for item in reversed(list(items)):
            if isinstance(item, QtWidgets.QLayout):
                self.layout.insertLayout(index, item)
            elif isinstance(item, QtWidgets.QWidget):
                self.layout.insertWidget(index, item)
            elif isinstance(item, str):
                self.layout.addWidget(NXLabel(item))

    def spacer(self, width=0, height=0):
        """Add a spacer to the layout."""
        return QtWidgets.QSpacerItem(width, height)

    def widget(self, item):
        """
        Wrap a layout or widget in a QWidget.

        Parameters
        ----------
        item : QLayout or QWidget
            The item to wrap in a QWidget.

        Returns
        -------
        QWidget
            The widget containing the item.
        """
        widget = QtWidgets.QWidget()
        widget.layout = QtWidgets.QVBoxLayout()
        if isinstance(item, QtWidgets.QLayout):
            widget.layout.addLayout(item)
        elif isinstance(item, QtWidgets.QWidget):
            widget.layout.addWidget(item)
        widget.setVisible(True)
        return widget

    def set_title(self, title):
        """Set the title of the dialog."""
        self.setWindowTitle(title)

    def close_layout(self, message=None, save=False, close=False,
                     progress=False):
        """
        Create a layout for close buttons.
        
        The layout contains a progress bar, buttons, and a status
        message at the bottom of the dialog window.

        Parameters
        ----------
        message : str, optional
            The message to display in the status message widget. Default
            is None.
        save : bool, optional
            Whether the save button should be displayed. Default is
            False.
        close : bool, optional
            Whether the close button should be displayed. Default is
            False.
        progress : bool, optional
            Whether the progress bar should be displayed. Default is
            False.

        Returns
        -------
        layout : QLayout
            The layout containing the status message widget, progress
            bar, and buttons.
        """
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
        """
        Create a layout of buttons for the dialog window.

        Parameters
        ----------
        items : list of tuples
            A list of tuples, where each tuple contains a label and an
            action function.

        Returns
        -------
        layout : QLayout
            The layout containing the buttons.
        """
        layout = QtWidgets.QHBoxLayout()
        layout.addStretch()
        for label, action in items:
            self.pushbutton[label] = NXPushButton(label, action)
            layout.addWidget(self.pushbutton[label])
            layout.addStretch()
        return layout

    def label(self, label, **opts):
        """Create a label widget."""
        return NXLabel(str(label), **opts)

    def labels(self, *labels, **opts):
        """
        Create a layout of labels for the dialog window.

        Parameters
        ----------
        *labels : list of str
            A list of strings to be displayed as labels.
        **opts : dict, optional
            A dictionary of options. The following options are
            recognized:
            - align : str, optional
                The alignment of the labels. The value can be 'left',
                'center', or 'right'. By default, 'center'.
            - header : bool, optional
                If True, the font of the labels will be bold. By
                default, False.

        Returns
        -------
        layout : QLayout
            The layout containing the labels.
        """
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
        """
        Create a layout of text boxes for the dialog window.

        Parameters
        ----------
        *items : list of tuples
            A list of tuples, where each tuple contains a label and a value.
        **opts : dict, optional
            A dictionary of options. The following options are recognized:
            - layout : str, optional
                The orientation of the layout. The value can be 'horizontal'
                or 'vertical'. By default, 'vertical'.

        Returns
        -------
        layout : QLayout
            The layout containing the text boxes.
        """
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
        """
        Create a layout of checkboxes for the dialog window.

        Parameters
        ----------
        *items : list of tuples
            A list of tuples, where each tuple contains a label, a text,
            and a boolean value.
        **opts : dict, optional
            A dictionary of options. The following options are
            recognized:
            - align : str, optional
                The alignment of the labels. The value can be 'left',
                'center', or 'right'. By default, 'center'.
            - vertical : bool, optional
                If True, the checkboxes are laid out vertically. By
                default, False.

        Returns
        -------
        layout : QLayout
            The layout containing the checkboxes.
        """
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
        """
        Create a layout of radio buttons for the dialog window.

        Parameters
        ----------
        *items : list of tuples
            A list of tuples, where each tuple contains a label, a text,
            and a boolean value.
        **opts : dict, optional
            A dictionary of options. The following options are
            recognized:
            - align : str, optional
                The alignment of the labels. The value can be 'left',
                'center', or 'right'. By default, 'center'.
            - vertical : bool, optional
                If True, the radio buttons are laid out vertically. By
                default, False.
            - slot : callable, optional
                A function to be called when a radio button is clicked.
                The function should take one argument, the radio button
                that was clicked.

        Returns
        -------
        layout : QLayout
            The layout containing the radio buttons.
        """
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
        Create a horizontal box layout with a button and a line edit.

        Parameters
        ----------
        text : str, optional
            The text to display on the button. By default, 'Choose File'.
        slot : callable, optional
            A function to be called when the button is clicked. If None,
            the function defaults to self.choose_file.

        Returns
        -------
        layout : QLayout
            The horizontal box layout containing the button and line edit.
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
        Create a horizontal box layout with a button and a line edit for
        selecting a directory.

        Parameters
        ----------
        text : str, optional
            The text to display on the button. By default, 'Choose
            Directory'.
        slot : callable, optional
            A function to be called when the button is clicked. If None,
            the function defaults to self.choose_directory.
        default : bool, optional
            If True, set the default directory for the line edit.
            Otherwise, leave it blank. Default is True.
        suggestion : str, optional
            A suggestion for the default directory. If given, it will be
            used to set the default directory. Otherwise, the default
            directory will be determined by the value of the
            'homedirectory' attribute of the nxgetconfig dictionary.

        Returns
        -------
        layout : QLayout
            The horizontal box layout containing the button and line
            edit.
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
        Open a file dialog for selecting a file.
        
        The initial directory is set to the value of the line edit. If a
        file is selected, the text of the line edit is set to the
        selected file and the default directory of the line edit is set
        to the parent directory of the selected file.
        """
        dirname = self.get_default_directory(self.filename.text())
        filename = Path(getOpenFileName(self, 'Open File', dirname))
        if filename.is_file():
            self.filename.setText(str(filename))
            self.set_default_directory(filename.parent)

    def get_filename(self):
        """Return the selected file."""
        return self.filename.text()

    def choose_directory(self):
        """Open a file dialog and sets the text box to the path."""
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
        """Return the default directory for open/save dialogs."""
        if suggestion is None or not Path(suggestion).exists():
            suggestion = self.default_directory
        suggestion = Path(suggestion)
        if suggestion.exists():
            if not suggestion.is_dir:
                suggestion = suggestion.parent
        suggestion = suggestion.resolve()
        return suggestion

    def set_default_directory(self, suggestion):
        """Define the default directory to use for open/save dialogs."""
        suggestion = Path(suggestion)
        if suggestion.exists():
            if not suggestion.is_dir():
                suggestion = suggestion.parent
            self.default_directory = suggestion
            self.mainwindow.default_directory = self.default_directory

    def get_filesindirectory(self, prefix='', extension='.*', directory=None):
        """
        Return a sorted list of files in the selected directory that
        match the given prefix and extension.

        Parameters
        ----------
        prefix : str, optional
            The prefix of the files to select. Default is an empty string.
        extension : str, optional
            The extension of the files to select. Default is '.*'.
        directory : str or Path, optional
            The directory from which to select the files. If None, the
            current directory is used. Default is None.

        Returns
        -------
        list of Path
            A sorted list of files with the given prefix and extension.
        """
        if directory:
            directory = Path(directory)
        else:
            directory = Path(self.get_directory())
        if not extension.startswith('.'):
            extension = '.'+extension
        return sorted(directory.glob(prefix+'*'+extension), key=natural_sort)

    def select_box(self, choices, default=None, slot=None):
        """
        Create a dropdown box from a list of choices.

        Parameters
        ----------
        choices : list
            The list of choices from which to select.
        default : str, optional
            The default choice. If None, the first choice is selected.
            Default is None.
        slot : callable, optional
            A function to be called when the selection is changed.
            Default is None.

        Returns
        -------
        box : NXComboBox
            The created dropdown box.
        """
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
        """
        Create a dropdown box from a list of the root entries in the
        NeXus tree.

        Parameters
        ----------
        slot : callable, optional
            A function to be called when the selection is changed.
            Default is None.
        text : str, optional
            The text to be displayed on the button to change the root.
            Default is 'Select Root'.

        Returns
        -------
        layout : QLayout
            The created layout containing the dropdown box and button.
        """
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
        """The selected root entry."""
        return self.tree[self.root_box.currentText()]

    def select_entry(self, slot=None, text='Select Entry'):
        """
        Create a dropdown box from a list of the root entries and a list
        of the entries within the selected root entry in the NeXus tree.

        Parameters
        ----------
        slot : callable, optional
            A function to be called when the selection is changed.
            Default is None.
        text : str, optional
            The text to be displayed on the button to change the entry.
            Default is 'Select Entry'.

        Returns
        -------
        layout : QLayout
            The created layout containing the dropdown boxes and button.
        """
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
        """
        Called when the root is changed in the select_entry widget.

        Updates the available entries in the select_entry widget and,
        if the select_data widget is being used, updates the available
        data in the select_data widget.
        """
        self.entry_box.clear()
        self.entry_box.add(*sorted(self.tree[self.root_box.selected].entries))
        if self.data_box:
            self.switch_entry()

    @property
    def entry(self):
        """The selected entry."""
        return self.tree[f"{self.root_box.selected}/{self.entry_box.selected}"]

    def select_data(self, slot=None, text='Select Data'):
        """
        Creates a widget to select data from the NeXus tree.

        The widget consists of a root selector, an entry selector, a
        data selector, and an optional push button. The root selector is
        used to select the root of the data tree, the entry selector is
        used to select the entry that contains the data, and the data
        selector is used to select the actual data. The optional push
        button can be used to perform an action when the data is
        selected.

        Parameters
        ----------
        slot : callable, optional
            A callable that is called when the data is selected.
        text : str, optional
            The text to display on the push button.

        Returns
        -------
        layout : QHBoxLayout
            The layout of the select_data widget.
        """
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
        """
        Update the data box with the names of all NXdata nodes in the
        current entry.
        """
        self.data_box.clear()
        entry_path = Path(self.entry.nxpath)
        paths = []
        for node in self.entry.walk():
            if node.nxclass == 'NXdata':
                paths.append(str(Path(node.nxpath).relative_to(entry_path)))
        self.data_box.add(*sorted(paths, key=natural_sort))

    @property
    def selected_data(self):
        """The selected data."""
        return self.tree[
            f"{self.root_box.selected}/{self.entry_box.selected}/"
            f"{self.data_box.selected}"]

    def read_parameter(self, root, path):
        """
        Read a parameter from the given root and path.

        Returns the value of the parameter as a float if it is a single
        value, otherwise returns the value as is. If the parameter is
        not found, returns None.

        Parameters
        ----------
        root : NXroot
            The root of the NeXus file.
        path : str
            The path of the parameter in the NeXus file.

        Returns
        -------
        value : float or None
            The value of the parameter or None if it is not found.
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
        """
        Create a stack of parameter widgets from the given parameters.

        Parameters
        ----------
        parameters : dict
            A dictionary of parameter names and their corresponding
            values.
        width : int, optional
            The width of each widget in the stack. If not given, the
            width of the first widget is used.

        Returns
        -------
        stack : NXStack
            A stack of parameter widgets.
        """
        return NXStack([p for p in parameters],
                       [parameters[p].widget(header=False, width=width)
                        for p in parameters])

    def grid(self, rows, cols, headers=None, spacing=10):
        """To be replaced with a grid layout in subclasses."""
        pass

    def hide_grid(self, grid):
        """
        Hide all widgets in the given grid layout.

        Parameters
        ----------
        grid : QGridLayout
            The grid layout to be hidden.
        """
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)

    def show_grid(self, grid):
        """
        Show all widgets in the given grid layout.

        Parameters
        ----------
        grid : QGridLayout
            The grid layout to be shown.
        """
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(True)

    def delete_grid(self, grid):
        """
        Delete all widgets in the given grid layout and then delete the grid.

        Parameters
        ----------
        grid : QGridLayout
            The grid layout to be deleted.
        """
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

    def search_layout(self, editor, search_text='Search...', width=200,
                      align='right'):
        """
        Create a search box widget that searches the given text editor.

        The search box is connected to the text editor's highlighter so
        that when the user enters a search string into the box, the all
        occurrences of the string in the text editor will be
        highlighted.

        Parameters
        ----------
        editor : QTextEdit or QPlainTextEdit
            The text editor to be searched.
        search_text : str, optional
            The text to display in the search box.
        width : int, optional
            The width of the search box.
        align : str, optional
            The alignment of the search box.

        Returns
        -------
        box : NXLineEdit
            The search box widget.
        """
        self.search_box = NXLineEdit(width=width, align='right')
        self.search_box.setPlaceholderText(search_text)
        self.search_box.textChanged.connect(editor.highlighter.setSearchText)
        editor.selectionChanged.connect(self.clear_search_box)
        next_button = QtWidgets.QToolButton()
        next_button.setText('↓')
        next_button.clicked.connect(editor.highlighter.findNext)
        prev_button = QtWidgets.QToolButton()
        prev_button.setText('↑')
        prev_button.clicked.connect(editor.highlighter.findPrevious)
        return self.make_layout(self.search_box, next_button, prev_button,
                                align=align, spacing=2)

    def clear_search_box(self):
        """
        Clear the search box.
        """
        self.search_box.clear()

    def start_progress(self, limits):
        """
        Set up a progress bar with the given limits.

        Parameters
        ----------
        limits : tuple
            A tuple of two integers, the start and stop values for the
            progress bar.
        """
        start, stop = limits
        if self.progress_bar:
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(start, stop)
            self.progress_bar.setValue(start)
            self.status_message.setVisible(False)

    def update_progress(self, value=None):
        """
        Update the progress bar with the given value.

        If the value is not given, the progress bar is not updated.
        Otherwise, the progress bar is updated with the given value.

        Parameters
        ----------
        value : int or None
            The value to update the progress bar with. If None, the
            progress bar is not updated.
        """
        if self.progress_bar and value is not None:
            self.progress_bar.setValue(value)
        self.mainwindow._app.processEvents()

    def stop_progress(self):
        """
        Stop the progress bar and make the status message visible.

        The progress bar is hidden and the status message is shown.
        """
        if self.progress_bar:
            self.progress_bar.setVisible(False)
        self.status_message.setVisible(True)

    def progress_layout(self, save=False, close=False):
        """
        Create a layout for the progress bar with close buttons.

        Parameters
        ----------
        save : bool, optional
            Whether to include a save button. Default is False.
        close : bool, optional
            Whether to include a close button. Default is False.

        Returns
        -------
        layout : QLayout
            The layout containing the progress bar and buttons.
        """
        return self.close_layout(save=save, close=close, progress=True)

    def get_node(self):
        """Return the currently selected node in the tree view."""
        return self.treeview.get_node()

    def start_thread(self):
        """Start a new thread using QThread."""
        if self.thread:
            self.stop_thread()
        self.thread = QtCore.QThread()
        return self.thread

    def stop_thread(self):
        """Stop the current thread."""
        if isinstance(self.thread, QtCore.QThread):
            self.thread.exit()
            self.thread.wait()
            self.thread.deleteLater()
        self.thread = None

    def resize(self, width=None, height=None):
        """
        Resize the dialog to the given width and height. If either the
        width or height are not given, the dialog will be resized to its
        minimum size hint.

        Parameters
        ----------
        width : int, optional
            The width of the dialog. Default is None.
        height : int, optional
            The height of the dialog. Default is None.
        """
        self.mainwindow._app.processEvents()
        self.adjustSize()
        self.mainwindow._app.processEvents()
        if width is None or height is None:
            super().resize(self.minimumSizeHint())
        else:
            super().resize(width, height)

    def update(self):
        """To be replaced in subclasses."""
        pass

    def activate(self):
        """
        Make this dialog active and visible.

        This will bring the dialog to the front of other windows and
        give it focus.
        """
        self.setVisible(True)
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def closeEvent(self, event):
        """
        Stop the thread and close the dialog.

        This is called when the dialog is closed. It will stop any
        currently running thread and close the dialog.
        """
        self.stop_thread()
        event.accept()


class NXDialog(QtWidgets.QDialog, NXWidget):

    def __init__(self, parent=None, default=False):
        """
        Initialize a NeXpy dialog.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog. Default is None.
        default : bool, optional
            Whether this is the default dialog. If True, the dialog
            will not be added to the list of dialogs and will not have
            event filtering. Default is False.

        Notes
        -----
        If parent is None, the parent will be set to the main window.
        """
        self.mainwindow = get_mainwindow()
        if parent is None:
            parent = self.mainwindow
        QtWidgets.QDialog.__init__(self, parent=parent)
        self.set_attributes()
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setSizeGripEnabled(True)
        self.mainwindow.dialogs.append(self)
        if not default:
            self.installEventFilter(self)

    def __repr__(self):
        return 'NXDialog(' + self.__class__.__name__ + ')'

    def close_buttons(self, save=False, close=False):
        """
        Create a standard dialog close button box.

        Parameters
        ----------
        save : bool, optional
            If True, the button box will have a 'Save' button
            instead of an 'Ok' button. Default is False.
        close : bool, optional
            If True, the button box will have a 'Close' button
            instead of an 'Ok' button. Default is False.

        Returns
        -------
        QtWidgets.QDialogButtonBox
            The created button box.
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
        """
        Filter events for widgets in the dialog.

        This function is called for every event that occurs within the
        dialog in order to prevent closure when pressing Return or
        Enter. It is also used to catch the Escape key to reject the
        dialog.

        Parameters
        ----------
        widget : QtWidgets.QWidget
            The widget that generated the event.
        event : QtCore.QEvent
            The event that occurred.

        Returns
        -------
        bool
            True if the event was handled.
        """
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
        """
        Called when the dialog is closed.

        This removes the dialog from the main window's list of dialogs.
        """
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
        """
        Initialize a NeXpy panel.

        Parameters
        ----------
        panel : NXPanel
            The parent panel
        title : str, optional
            The title of the dialog, by default 'title'
        tabs : dict, optional
            A dictionary of tabs to add, by default {}
        close : bool, optional
            Whether to add close buttons, by default True
        apply : bool, optional
            Whether to add an apply button, by default True
        reset : bool, optional
            Whether to add a reset button, by default True
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
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
        Create a box with Apply, Reset, and Close buttons.

        Parameters
        ----------
        apply : bool, optional
            Whether to add an Apply button, by default True
        reset : bool, optional
            Whether to add a Reset button, by default True

        Returns
        -------
        QtWidgets.QDialogButtonBox
            The dialog box with Apply, Reset, and Close buttons
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
        """The current tab"""
        return self.tabwidget.currentWidget()

    @tab.setter
    def tab(self, label):
        self.tabwidget.setCurrentWidget(self.tabs[label])

    @property
    def count(self):
        """The number of tabs"""
        return self.tabwidget.count()

    def tab_list(self):
        """The list of tabs"""
        if self.plotview_sort:
            return [tab.tab_label for tab in
                    sorted(self.labels, key=attrgetter('plotview.number'))]
        else:
            return sorted(self.tabs)

    def add(self, label, tab=None, idx=None):
        """
        Add a tab to the tabwidget.

        Parameters
        ----------
        label : str
            The label of the tab
        tab : QWidget, optional
            The tab to be added, by default None
        idx : int, optional
            The index of the tab, by default None

        Raises
        ------
        NeXusError
            If the label is already in the panel
        """
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
        """
        Remove the tab with the given label.

        If the tab is not present in the panel, do nothing.

        Parameters
        ----------
        label : str
            The label of the tab to be removed
        """
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
        """
        Return the index of the given label in the sorted list of labels.

        The labels are sorted alphabetically unless the `plotview_sort`
        attribute is set to True, in which case the plotviews are sorted
        by their number.

        Parameters
        ----------
        label : str
            The label of the tab for which the index is to be returned.

        Returns
        -------
        idx : int
            The index of the given label in the sorted list of labels.
        """
        if self.plotview_sort and label in self.plotviews:
            pv = self.plotviews[label]
            numbers = sorted([t.plotview.number for t in self.labels])
            return bisect.bisect_left(numbers, pv.number)
        else:
            return bisect.bisect_left(sorted(list(self.tabs)), label)

    def activate(self, label, *args, **kwargs):
        """
        Activate the tab with the given label.

        If the tab does not exist, create it using the given arguments
        and keyword arguments. If the tab does exist, simply update it.

        Parameters
        ----------
        label : str
            The label of the tab to be activated.
        *args : any
            Additional arguments to be passed to the tab constructor.
        **kwargs : any
            Additional keyword arguments to be passed to the tab
            constructor.
        """
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
        """
        Update the size policies of the tabs.

        If there are any tabs, set the size policy of all but the
        current tab to Ignored. Set the size policy of the current tab
        to Minimum. Resize the current tab and the containing window.
        """
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
        """Copy the current tab to a new tab."""
        self.tab.copy()

    def reset(self):
        """Reset the current tab."""
        self.tab.reset()

    def apply(self):
        """Apply the current tab."""
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
        """Ensure tabs and panels are closed when closing the window."""
        self.cleanup()
        event.accept()

    def is_running(self):
        """Return True if any tabs are running."""
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

    def __init__(self, label, parent=None):
        """
        Initialize a NeXpy tab with the given label and parent.

        If the parent is given, the tab is added to the parent. If the
        parent is not given, the tab is created without a parent and the
        tabs and labels dictionaries are also created without a parent.

        Parameters
        ----------
        label : str
            The label of the tab
        parent : NXTabPanel, optional
            The parent of the tab. If not given, the tab is created
            without a parent.
        """
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
        """Return the index of the tab in the tab widget."""
        if self.panel:
            return self.panel.tabwidget.indexOf(self)
        else:
            return None

    @property
    def tab_label(self):
        """Return the label of the tab."""
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
        """
        Create a widget to copy the tab to another tab.

        Parameters
        ----------
        text : str, optional
            The text to display on the copy button.
        sync : str, optional
            If given, add a checkbox to allow synchronizing the tabs.

        Returns
        -------
        widget : QWidget
            The widget with the copy button and the drop-down list of tab
            labels to copy to.
        """
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
        """To be implemented by subclasses."""
        pass

    def copy(self):
        """To be implemented by subclasses."""
        pass

    def sort_copybox(self):
        """
        Sort the copybox by the order of the tabs in the panel.

        Select the original selected tab if it still exists in the
        copybox.
        """
        if self.copybox:
            selected = self.copybox.selected
            tabs = self.copybox.items()
            self.copybox.clear()
            for tab in [tab for tab in self.panel.tab_list() if tab in tabs]:
                self.copybox.add(tab)
            if selected in self.copybox:
                self.copybox.select(selected)

    def apply(self):
        """To be implemented by subclasses."""
        pass


class GridParameters(dict):

    def __init__(self, **kwds):
        """
        Initialize a dictionary of parameters for a dialog box grid.

        The keyword arguments should contain the parameters to be
        displayed in the grid. The values of the arguments should be
        either None or a GridParameter object. If None, a GridParameter
        will be created. The name of each GridParameter will be the key
        of the argument, and the value will be the value of the argument.

        Parameters
        ----------
        **kwds : keyword arguments
            The parameters to be displayed in the grid.
        """
        super().__init__(self)
        self.result = None
        self.status_layout = None
        self.update(**kwds)

    def __setitem__(self, key, value):
        """
        Set the value of a key in the dictionary.

        The value should be a GridParameter. If the value is not a
        GridParameter, a ValueError will be raised.

        Parameters
        ----------
        key : str
            The key in the dictionary to be set.
        value : GridParameter
            The value to be set.
        """
        if value is not None and not isinstance(value, GridParameter):
            raise ValueError(f"'{value}' is not a GridParameter")
        super().__setitem__(key, value)
        value.name = key

    def add(self, name, value=None, label=None, vary=None, slot=None,
            color=False, spinbox=None, readonly=False, width=None):
        """
        Add a parameter to the grid.

        Parameters
        ----------
        name : str
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
        readonly : bool, optional
            Whether the field is read-only, default False.
        width : int, optional
            Width of the box, default None
        """
        self.__setitem__(name, GridParameter(value=value, name=name,
                                             label=label, vary=vary,
                                             slot=slot, readonly=readonly,
                                             color=color, spinbox=spinbox,
                                             width=width))

    def grid(self, header=True, title=None, width=None, spacing=2):
        """
        Creates a grid layout from the parameters in the
        GridParameterSet.

        Parameters
        ----------
        header : bool, list or tuple, optional
            Whether to include a header row with column labels. If a
            list or tuple, the labels to be used are the elements of the
            list or tuple. By default, the labels are ['Parameter',
            'Value', 'Fit?'].
        title : str, optional
            A title to be placed above the grid. By default, there is no
            title.
        width : int, optional
            The width of the boxes in the grid. By default, the width is
            not specified.
        spacing : int, optional
            The spacing between rows in the grid. By default, the
            spacing is 2.

        Returns
        -------
        grid : QGridLayout
            The grid layout of the parameters in the GridParameterSet.
        """
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
        """
        Return a QWidget with the parameters in a grid layout.
        
        Parameters
        ----------
        header : bool, optional
            Whether to include a header row with parameter names,
            by default True
        title : str, optional
            The title to be displayed, by default None
        width : int, optional
            The width of each parameter box, by default None
        
        Returns
        -------
        QWidget
            The widget containing the grid layout.
        """
        w = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(self.grid(header=header, title=title, width=width))
        layout.addStretch()
        w.setLayout(layout)
        return w

    def hide_grid(self):
        """Hide all widgets in the parameter grid layout."""
        grid = self.grid_layout
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(False)

    def show_grid(self):
        """Show all widgets in the parameter grid layout."""
        grid = self.grid_layout
        for row in range(grid.rowCount()):
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    widget = item.widget()
                    if widget is not None:
                        widget.setVisible(True)

    def delete_grid(self):
        """Delete all widgets in the parameter grid layout."""
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
        """
        Set the parameters to be used for fitting.

        This creates an instance of a Parameters object from the
        parameters that are to be varied in the fit. The Parameters
        object is an ordered dictionary of Parameter objects.
        """
        from lmfit import Parameter, Parameters
        self.lmfit_parameters = Parameters()
        for p in [p for p in self if self[p].vary]:
            self.lmfit_parameters[p] = Parameter(self[p].name, self[p].value)

    def get_parameters(self, parameters):
        """
        Update the values of all parameters in the GridParameterSet from
        the parameters returned by a fit.

        Parameters
        ----------
        parameters : lmfit.Parameters
            The parameters returned by a fit.
        """
        for p in parameters:
            self[p].value = parameters[p].value

    def refine_parameters(self, residuals, **opts):
        """
        Refine the parameters in the GridParameterSet using a least-squares fit.

        Parameters
        ----------
        residuals : callable
            A function that returns the residuals between the data and the
            model, given the values of the parameters.
        **opts : keyword arguments
            Options for the fit.

        Notes
        -----
        The parameters are updated with the best-fit values.
        """
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
        """
        Create a layout that displays the status of the fit.

        If the fit has not been performed, the text of the status
        message will be 'Waiting to refine'. If the fit has been
        performed, the text of the status message will be the
        message returned by the fit, such as 'Successfully terminated
        [from] lmfit' or 'Aborted [from] lmfit'. The layout also
        contains a button that shows the full report of the fit when
        clicked.

        Returns
        -------
        layout : QHBoxLayout
            The layout containing the status message and the button.
        """
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
        """
        Show the full report of the fit in a message box.

        If the fit has not been performed, this function does not do
        anything. Otherwise, it creates a message box with the title
        'Fit Results' and the informative text set to the full report
        of the fit. The message box contains an OK button to close the
        box.
        """
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
        message_box.exec()

    def restore_parameters(self):
        """
        Restore the initial values of all parameters in the grid.

        This method is used to reset the parameters to their initial
        values. It is called when the user clicks the 'Cancel' button in
        the fit dialog.
        """
        for p in [p for p in self if self[p].vary]:
            self[p].value = self[p].init_value

    def save(self):
        """
        Save all parameters in the grid to a file.

        This method is used to save the values of all parameters in the
        grid to a file. The file is written as a NeXus file with a
        single NXprocess group containing the data, model, and
        parameters. The file name is the name of the data set plus
        '.nxs'. The data, model, and parameters are written using the
        write_group method of the NeXpy NXprocess class.
        """
        for p in self:
            self[p].save()


class GridParameter:

    def __init__(self, name=None, value=None, label=None, vary=None, slot=None,
                 color=False, spinbox=False, readonly=False, width=None):
        """
        Initialize a GridParameter object.

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
        """Save the current parameter to the underlying NeXus field."""

        if isinstance(self.field, NXfield):
            self.field.nxdata = np.array(self.value).astype(self.field.dtype)

    @property
    def value(self):
        """The current value of the parameter."""
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
        """True if the parameter is fixed during a fit."""
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
        """Disable the parameter."""
        if vary is not None:
            self.vary = vary
        self.checkbox.setEnabled(False)

    def enable(self, vary=None):
        """Enable the parameter."""
        if vary is not None:
            self.vary = vary
        self.checkbox.setEnabled(True)


class NXStack(QtWidgets.QWidget):

    def __init__(self, labels, widgets, parent=None):
        """Initialize the NeXpy widget stack.

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
        """
        Add a widget to the stack.

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
        """
        Remove a widget from the stack.

        Parameters
        ----------
        label : str
            Label used to select the widget in the QComboBox
        """
        if label in self.widgets:
            self.stack.removeWidget(self.widgets[label])
            del self.widgets[label]
        self.box.remove(label)


class NXSortModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        """
        Initialize a proxy model for sorting items with natural sorting.

        Parameters
        ----------
        parent : QObject, optional
            The parent object of the proxy model, by default None.
        """
        super().__init__(parent=parent)

    def lessThan(self, left, right):
        """
        Reimplemented from QSortFilterProxyModel.

        Compares two QModelIndex by natural sorting of their text.

        Parameters
        ----------
        left : QModelIndex
        right : QModelIndex

        Returns
        -------
        bool
            True if left is less than right, False otherwise.
        """
        try:
            left_text = self.sourceModel().itemFromIndex(left).text()
            right_text = self.sourceModel().itemFromIndex(right).text()
            return natural_sort(left_text) < natural_sort(right_text)
        except Exception:
            return True


class NXScrollArea(QtWidgets.QScrollArea):

    def __init__(self, content=None, horizontal=False, height=600,
                 parent=None):
        """Initialize the scroll area.

        Parameters
        ----------
        content : QtWidgets.QWidget or QtWidgets.QLayout
            Widget or layout to be contained within the scroll area.
        horizontal : bool
            True if a horizontal scroll bar is enabled, default False.
        height : int
            Maximum height of the scroll area, default 600.
        parent : QObject, optional
            Parent of the scroll area (the default is None).
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
        self.setMaximumHeight(height)
        self.setWidgetResizable(True)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Expanding)

    def setWidget(self, widget):
        """
        Set the widget contained within the scroll area.

        Parameters
        ----------
        widget : QtWidgets.QWidget or QtWidgets.QLayout
            Widget or layout to be contained within the scroll area.
        """
        if isinstance(widget, QtWidgets.QLayout):
            w = QtWidgets.QWidget()
            w.setLayout(widget)
            widget = w
        super().setWidget(widget)
        widget.setMinimumWidth(widget.sizeHint().width() +
                               self.verticalScrollBar().sizeHint().width())


class NXLabel(QtWidgets.QLabel):

    def __init__(self, text=None, parent=None, bold=False, width=None,
                 align='left'):
        """
        Initialize a label with a given text, parent, and styling.

        Parameters
        ----------
        text : str, optional
            The text to be displayed in the label, default None.
        parent : QWidget, optional
            The parent window of the label, default None.
        bold : bool, optional
            Whether to render the text in bold, default False.
        width : int, optional
            The width of the label in pixels, default None.
        align : str, optional
            The alignment of the text in the label, either 'left',
            'center', or 'right', default 'left'.
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

    def __init__(self, text=None, parent=None, slot=None, readonly=False,
                 width=None, align='left'):
        """
        Initialize an line edit box.

        Parameters
        ----------
        text : str, optional
            The text to be displayed in the line edit box, default None.
        parent : QWidget, optional
            The parent window of the line edit box, default None.
        slot : function, optional
            If given, connect the textChanged signal to the slot.
        readonly : bool, optional
            Whether to render the line edit box as read-only, default
            False.
        width : int, optional
            The width of the line edit box in pixels, default None.
        align : str, optional
            The alignment of the text in the line edit box, either
            'left', 'center', or 'right', default 'left'.
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
        self.setToolTip(self.text())

    def setText(self, text):
        """
        Function to set the text in the box.

        Parameters
        ----------
        text : str
            Text to replace the text box contents.
        """
        super().setText(str(text))
        self.setToolTip(self.text())
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


class NXTextEdit(QtWidgets.QTextEdit):

    selectionChanged = QtCore.Signal(str)

    def __init__(self, text=None, parent=None, slot=None, readonly=False,
                 width=None, align='left', autosize=False):
        """
        Initialize a text edit box.

        Parameters
        ----------
        text : str, optional
            The text to be displayed in the text edit box, default None.
        parent : QWidget, optional
            The parent window of the text edit box, default None.
        slot : function, optional
            If given, connect the textChanged signal to the slot.
        readonly : bool, optional
            Whether to render the text edit box as read-only, default
            False.
        width : int, optional
            The width of the text edit box in pixels, default None.
        align : str, optional
            The alignment of the text in the text edit box, either
            'left', 'center', or 'right', default 'left'.
        autosize : bool, optional
            True if the text edit box should automatically resize to fit
            its contents, default False.
        """
        super().__init__(parent=parent)
        if slot:
            self.textChanged.connect(slot)
        if text is not None:
            self.setPlainText(str(text))
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
        self.setToolTip(self.toPlainText())
        self.setStyleSheet(
            "QTextEdit { background-color: white; padding: 2px; }")
        if autosize:
            self.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
            self.document().setDocumentMargin(0)
            self.update_minimum_height()
            self.document().documentLayout().documentSizeChanged.connect(
                self.adjust_height)
        self.cursorPositionChanged.connect(self.handle_selection)
        self.highlighter = NXHighlighter(self)
        self.selectionChanged.connect(self.highlighter.setSearchText)
        self.syntax_colors = False

    def update_minimum_height(self):
        """Calculate height for one line of text including all margins"""
        font_metrics = self.fontMetrics()
        margins = self.contentsMargins()
        line_height = font_metrics.lineSpacing()
        total_margins = margins.top() + margins.bottom()
        self.setFixedHeight(line_height + total_margins)

    def adjust_height(self):
        """Dynamically adjust height based on content"""
        doc_height = self.document().size().height()
        margins = self.contentsMargins()
        total_height = int(doc_height + margins.top() + margins.bottom())
        self.setMinimumHeight(self.fontMetrics().lineSpacing() +
                              margins.top() + margins.bottom())
        self.setFixedHeight(max(total_height, self.minimumHeight()))

    def handle_selection(self):
        cursor = self.textCursor()
        selected = cursor.selectedText()
        if selected and not selected.isspace():
            self.selectionChanged.emit(selected)
        else:
            self.selectionChanged.emit("")


class NXPlainTextEdit(QtWidgets.QPlainTextEdit):
    """An editable text window."""

    selectionChanged = QtCore.Signal(str)

    def __init__(self, text=None, wrap=True, parent=None):
        """
        Initialize the plain text editor.

        Parameters
        ----------
        text : str, optional
            The initial text of the window. If given, the text is set.
            If not given, the window is empty.
        wrap : bool, optional
            If True, the text wraps to the next line if it is longer
            than the window. If False, the text does not wrap, by
            default True.
        parent : QWidget, optional
            The parent window of the text box, by default None.
        """
        super().__init__(parent=parent)
        self.setFont(QtGui.QFont('Courier'))
        if not wrap:
            self.setLineWrapMode(QtWidgets.QPlainTextEdit.NoWrap)
        if text:
            self.setPlainText(text)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.cursorPositionChanged.connect(self.handle_selection)
        self.highlighter = NXHighlighter(self)
        self.selectionChanged.connect(self.highlighter.setSearchText)
        self.syntax_colors = False

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
            Number of spaces to replace tabs (default is 4). If set to
            0, tab characters are not replaced.

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

    def handle_selection(self):
        cursor = self.textCursor()
        selected = cursor.selectedText()
        if selected and not selected.isspace():
            self.selectionChanged.emit(selected)
        else:
            self.selectionChanged.emit("")


class NXFormatter(Formatter):

    def __init__(self, style_name=None):
        if style_name is None:
            if in_dark_mode():
                self.style_name = 'monokai'
            else:
                self.style_name = 'tango'
        else:
            self.style_name = style_name
        style = get_style_by_name(self.style_name)
        self.styles = {}
        for token, style_str in style.styles.items():
            fmt = QtGui.QTextCharFormat()
            if style_str:
                parts = style_str.split()                
                for part in parts:
                    if part == 'bold':
                        fmt.setFontWeight(QtGui.QFont.Bold)
                    elif part == 'italic':
                        fmt.setFontItalic(True)
                    elif part == 'underline':
                        fmt.setFontUnderline(True)
                    elif part.startswith('#'):
                        fmt.setForeground(QtGui.QColor(part))
            self.styles[token] = fmt

    def __repr__(self):
        return f"NXFormatter(style='{self.style_name}')"

    def format_for_token(self, token):
        """
        Return the format for a given token or the default if not found.

        Parameters
        ----------
        token : str
            The token to be formatted.

        Returns
        -------
        fmt : QtGui.QTextCharFormat
            The format for the given token or the default if not found.
        """
        t = token
        while t not in self.styles:
            if t is Token:
                return QtGui.QTextCharFormat()
            t = t.parent
        return self.styles[t]

class NXHighlighter(QtGui.QSyntaxHighlighter):
    """A highlighter for text edit boxes."""

    def __init__(self, editor):
        """
        Initialize the highlighter for the given text editor.

        Parameters
        ----------
        editor : QTextEdit or QPlainTextEdit
            The text editor to be highlighted.
        """
        self.editor = editor
        self.document = editor.document()
        super().__init__(self.document)
        self.lexer = PythonLexer()
        self.formatter = NXFormatter()
        self.searchText = ""
        self.searchFormat = QtGui.QTextCharFormat()
        self.searchFormat.setBackground(QtGui.QColor(255, 255, 0, 150))
        palette = self.editor.palette()
        palette.setBrush(palette.Highlight, QtGui.QColor(255, 255, 0, 100))
        palette.setBrush(palette.HighlightedText,
                         QtGui.QBrush(QtCore.Qt.NoBrush))
        self.editor.setPalette(palette)

    def update_style(self, style_name):
        """
        Update the style of the syntax highlighter.

        Parameters
        ----------
        style_name : str
            The name of the style to be used.
        """
        self.formatter = NXFormatter(style_name)
        self.rehighlight()

    def setSearchText(self, text):
        """
        Set the search text to highlight it in the editor.

        Parameters
        ----------
        text : str
            The text to search for.
        """
        self.searchText = text
        self.rehighlight()

    def findNext(self):
        """Find the next occurrence of the search text."""
        self.editor.blockSignals(True)
        cursor = self.editor.textCursor()
        pos = cursor.selectionEnd()
        found = self.document.find(
            QtCore.QRegularExpression(self.searchText), pos)
        if found.isNull():
            found = self.document.find(
                QtCore.QRegularExpression(self.searchText), 0)
        if not found.isNull():
            self.editor.setTextCursor(found)
            self.editor.ensureCursorVisible()
            extra_selection = QtWidgets.QTextEdit.ExtraSelection()
            extra_selection.cursor = found
            format = QtGui.QTextCharFormat()
            format.setBackground(QtGui.QColor(255, 165, 0, 120))
            extra_selection.format = format
            self.editor.setExtraSelections([extra_selection])
        else:
            self.editor.setExtraSelections([])

        self.editor.blockSignals(False)

    def findPrevious(self):
        """Find the previous occurrence of the search text."""
        self.editor.blockSignals(True)
        cursor = self.editor.textCursor()
        pos = cursor.selectionStart()
        found = self.document.find(
            QtCore.QRegularExpression(self.searchText), pos,
            QtGui.QTextDocument.FindBackward)
        if found.isNull():
            found = self.document.find(
                QtCore.QRegularExpression(self.searchText),
                self.document.characterCount()-1,
                QtGui.QTextDocument.FindBackward)
        if not found.isNull():
            self.editor.setTextCursor(found)
            self.editor.ensureCursorVisible()
            extra_selection = QtWidgets.QTextEdit.ExtraSelection()
            extra_selection.cursor = found
            format = QtGui.QTextCharFormat()
            format.setBackground(QtGui.QColor(255, 165, 0, 120))
            extra_selection.format = format
            self.editor.setExtraSelections([extra_selection])
        else:
            self.editor.setExtraSelections([])
        self.editor.blockSignals(False)

    def highlightBlock(self, text):
        """
        Highlight the given text block in the editor.

        This method is called whenever the text of the editor changes.
        It first checks if the syntax colors are enabled for the editor.
        If they are, it highlights the syntax of the code block using
        the lexer and formatter.  If a search text is specified, it
        highlights the search text using the search format.

        Parameters
        ----------
        text : str
            The text block to highlight.
        """
        if self.editor.syntax_colors:
            offset = 0
            for token, value in self.lexer.get_tokens(text):
                length = len(value)
                if length == 0:
                    continue
                fmt = self.formatter.format_for_token(token)
                self.setFormat(offset, length, fmt)
                offset += length
        if self.searchText:
            expression = QtCore.QRegularExpression(self.searchText)
            it = expression.globalMatch(text)
            while it.hasNext():
                match = it.next()
                start = match.capturedStart()
                length = match.capturedLength()
                overlay_format = QtGui.QTextCharFormat()
                overlay_format.setBackground(self.searchFormat.background())
                self.setFormat(start, length, overlay_format)


class NXMessageBox(QtWidgets.QMessageBox):

    def __init__(self, title, text, *args, **kwargs):

        """
        Initialize a scrollable message box.

        Parameters
        ----------
        title : str
            The title of the message box.
        text : str
            The text of the message box.
        *args :
            Additional arguments to pass to super().__init__.
        **kwargs :
            Additional keyword arguments to pass to super().__init__.
        """
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

    def __init__(self, slot=None, items=[], default=None, align=None):
        """
        Initialize the dropdown menu with an initial list of items

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
            if isinstance(items, dict):
                tooltips = list(items.values())
                items = list(items.keys())
            else:
                tooltips = None
            self.addItems([str(item) for item in items])
            if tooltips:
                for i, tip in enumerate(tooltips):
                    if isinstance(tip, str):
                        self.setItemData(i, tip, QtCore.Qt.ToolTipRole)
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
        """Implement key iteration."""
        return self.items().__next__()

    def __contains__(self, item):
        """True if the item is one of the options."""
        return item in self.items()

    def keyPressEvent(self, event):
        """Function to enable the use of cursor keys to make selections.

        `Up` and `Down` keys are used to select options in the dropdown
        menu. `Left` and `Right` keys ar used to expand the dropdown
        menu to display the options.

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
        """
        Function to return the index of a text value.

        This is needed since h5py now returns byte strings, which will
        trigger ValueErrors unless they are converted to unicode
        strings.

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
        """
        Add a list of items to the dropdown menu.

        If an item is a dictionary, its first key is used as the item
        text and its first value is used as the item tooltip.

        Parameters
        ----------
        *items :
            A variable number of items to add to the dropdown menu.
        """
        for item in items:
            if isinstance(item, dict):
                tooltip = list(item.values())[0]
                item = str(item.keys()[0])
                if item not in self:
                    self.addItem(item)
                if isinstance(tooltip, str):
                    idx = self.findText(item)
                    self.setItemData(idx, tooltip, QtCore.Qt.ToolTipRole)
            elif item not in self:
                self.addItem(str(item))

    def insert(self, idx, item):
        """
        Insert an item into the list of options at the given index.

        Parameters
        ----------
        idx : int
            Index where the item should be inserted.
        item : str or dict
            Item to be inserted. If a string, it is a simple text
            item. If a dictionary, it is expected to contain a single
            key-value pair, where the key is the displayed text and
            the value is the tooltip text.
        """
        if item == "":
            self.insertSeparator(idx)
        elif item not in self:
            if isinstance(item, dict):
                tooltip = list(item.values())[0]
                item = str(item.keys()[0])
                idx = self.findText(item)
                self.insertItem(idx, item)
                if isinstance(tooltip, str):
                    idx = self.findText(item)
                    self.setItemData(idx, tooltip, QtCore.Qt.ToolTipRole)
            else:
                self.insertItem(idx, str(item))

    def remove(self, item):
        """
        Remove item from the list of options.

        Parameters
        ----------
        item : str or int
            Option to be removed from the dropdown menu.
        """
        if str(item) in self:
            self.removeItem(self.findText(str(item)))

    def items(self):
        """
        Return a list of the dropdown menu options.

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
        """
        Select the option matching the text.

        Parameters
        ----------
        item : str
            The option to be selected in the dropdown menu.
        """
        self.setCurrentIndex(self.findText(str(item)))
        self.repaint()

    @property
    def selected(self):
        """
        Return the currently selected option.

        Returns
        -------
        str
            Currently selected option in the dropdown menu.
        """
        return self.currentText()


class NXCheckBox(QtWidgets.QCheckBox):

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
        """
        Function to enable the use of cursor keys to change the state.

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
        """
        Initialize button.

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
        """
        Function to enable the use of keys to press the button.

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

    colorChanged = QtCore.Signal(QtGui.QColor)

    def __init__(self, parent=None):

        """
        Initialize a button for selecting colors.

        Parameters
        ----------
        parent : QObject, optional
            Parent of the color button.
        """
        super().__init__(parent=parent)
        self.setFixedWidth(18)
        self.setStyleSheet("width:18px; height:18px; "
                           "margin: 0px; border: 0px; padding: 0px;"
                           "background-color: white")
        self.setIconSize(QtCore.QSize(12, 12))
        self.clicked.connect(self.choose_color)
        self._color = QtGui.QColor()

    def choose_color(self):
        """
        Open a color dialog and set the button color if a valid color
        is chosen.

        This function is called when the button is clicked.
        """
        color = QtWidgets.QColorDialog.getColor(self._color,
                                                self.parentWidget())
        if color.isValid():
            self.set_color(color)

    def get_color(self):
        """Return the button color."""
        return self._color

    @QtCore.Slot(QtGui.QColor)
    def set_color(self, color):
        """
        Set the color of the button.

        Parameters
        ----------
        color : QtGui.QColor
            Color to be set.

        This function is a slot and can be connected to a signal.
        """
        if color != self._color:
            self._color = color
            self.colorChanged.emit(self._color)
            pixmap = QtGui.QPixmap(self.iconSize())
            pixmap.fill(color)
            self.setIcon(QtGui.QIcon(pixmap))
            self.repaint()

    color = QtCore.Property(QtGui.QColor, get_color, set_color)


class NXColorBox(QtWidgets.QWidget):
    """
    Text box and color square for selecting colors.

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
        """
        Initialize the text and color box.

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
        """Set the text box string following a change to the color."""
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
    """
    Subclass of QSpinBox with floating values.

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
        """
        Initialize the spin box with optional slot and data.

        Parameters
        ----------
        slot : function, optional
            PyQt slot triggered by changing values
        data : array-like, optional
            Values of data to be adjusted by the spin box.
        """
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
        """
        Return the value of the spin box.

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
        """
        The values of the data points based on bin centers.

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
        """The values of the data points based on bin boundaries."""
        if self.data is None:
            return None
        else:
            return boundaries(self.centers, self.data.shape[0])

    @property
    def index(self):
        """The current index of the spin box."""
        return super().value()

    @property
    def reversed(self):
        """True if the data are in reverse order."""
        if self.data[-1] < self.data[0]:
            return True
        else:
            return False

    def setValue(self, value):
        """
        Set the value of the spin box.

        This is used to set the spin box value by an external program.
        The value is converted to an index and then set. The spin box
        is then updated.

        Parameters
        ----------
        value : str or int or float
            The value to set the spin box to
        """
        super().setValue(self.valueFromText(value))
        self.repaint()

    def valueFromText(self, text):
        """
        Convert a string to an index value for the spin box.

        This is used to set the spin box value by an external program.
        The value is converted to an index and then set. The spin box
        is then updated.

        Parameters
        ----------
        text : str or int or float
            The value to set the spin box to

        Returns
        -------
        int
            Index value for the spin box
        """
        return self.indexFromValue(float(str(text)))

    def textFromValue(self, value):
        """
        Convert a value to a string for the spin box.

        This is used to set the spin box value by an external program.
        The value is converted to a string and then set. The spin box
        is then updated.

        Parameters
        ----------
        value : int or float
            The value to set the spin box to

        Returns
        -------
        str
            String value for the spin box
        """
        try:
            return format_float(float(f'{self.centers[value]:.4g}'))
        except Exception:
            return ''

    def valueFromIndex(self, idx):
        """
        Convert an index to a value for the spin box.

        Parameters
        ----------
        idx : int
            Index of the spin box

        Returns
        -------
        float
            The value of the spin box at the given index
        """
        if idx < 0:
            return self.centers[0]
        elif idx > self.maximum():
            return self.centers[-1]
        else:
            return self.centers[idx]

    def indexFromValue(self, value):
        """
        Convert a value to an index for the spin box.

        Parameters
        ----------
        value : float
            Value of the spin box

        Returns
        -------
        int
            Index of the spin box
        """
        return (np.abs(self.centers - value)).argmin()

    def minBoundaryValue(self, idx):
        """
        Return the minimum boundary value with the given index.

        Parameters
        ----------
        idx : int
            Index of the spin box

        Returns
        -------
        float
            Minimum boundary value of the spin box at the given index
        """
        if idx <= 0:
            return self.boundaries[0]
        elif idx >= len(self.centers) - 1:
            return self.boundaries[-2]
        else:
            return self.boundaries[idx]

    def maxBoundaryValue(self, idx):
        """
        Return the maximum boundary value with the given index.

        Parameters
        ----------
        idx : int
            Index of the spin box

        Returns
        -------
        float
            Maximum boundary value of the spin box at the given index
        """
        if idx <= 0:
            return self.boundaries[1]
        elif idx >= len(self.centers) - 1:
            return self.boundaries[-1]
        else:
            return self.boundaries[idx+1]

    def validate(self, input_value, pos):
        """
        Validate the input value using the validator.

        Parameters
        ----------
        input_value : str
            Value to be validated

        pos : int
            Position of the input value in the spin box

        Returns
        -------
        tuple
            A tuple of (QValidator.State, str, int)
        """
        return self.validator.validate(input_value, pos)

    @property
    def tolerance(self):
        """The tolerance for the spin box."""
        return self.diff / 100.0

    def stepBy(self, steps):
        """
        Step the spin box by the given number of steps.

        If the difference value is valid, the spin box is stepped by the
        given number of steps. The pause flag is set to False unless the
        stepped value is out of range, in which case it is set to True.

        Parameters
        ----------
        steps : int
            Number of steps to step the spin box
        """
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
        """
        Process events and handle timer events.

        This function is called whenever the timer times out. It
        processes any pending events and calls the base class function
        to handle the timer event when the left mouse button is pressed.
        """
        self.app.processEvents()
        if self.app.mouseButtons() & QtCore.Qt.LeftButton:
            super().timerEvent(event)


class NXDoubleSpinBox(QtWidgets.QDoubleSpinBox):
    """
    Subclass of QDoubleSpinBox.

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
        """
        Initialize a NeXpy spin box with optional slot and editing.

        Parameters
        ----------
        slot : function
            PyQt slot triggered by changing values
        editing : function
            Function to be called when editing is finished

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
        """
        Validate the input value using the validator.

        Parameters
        ----------
        input_value : str
            Value to be validated

        position : int
            Position of the input value in the spin box

        Returns
        -------
        tuple
            A tuple of (QValidator.State, str, int)
        """
        return self.validator.validate(input_value, position)

    def setSingleStep(self, value):
        """
        Set the single step size of the spin box. 
        
        The step is determined by taking the nearest value of the array
        [1, 2, 5, 10] that is closest to the absolute value of the input
        divided by 10 to the power of the number of digits in the value.

        Parameters
        ----------
        value : float
            Value to be used to determine the step size
        """
        value = abs(value)
        if value == 0:
            stepsize = 0.01
        else:
            digits = math.floor(math.log10(value))
            multiplier = 10**digits
            stepsize = find_nearest(self.steps, value/multiplier) * multiplier
        super().setSingleStep(stepsize)

    def stepBy(self, steps):
        """
        Step the spin box by the given number of steps.

        If the difference value is valid, the spin box is stepped by the
        given number of steps. The pause flag is set to False unless the
        stepped value is out of range, in which case it is set to True.

        Parameters
        ----------
        steps : int
            Number of steps to step the spin box
        """
        if self.diff:
            self.setValue(self.value() + steps * self.diff)
        else:
            super().stepBy(steps)
        self.old_value = self.text()

    def valueFromText(self, text):
        """
        Return the value from the text in the spin box.
        
        If the value is not in the range of the spin box, the range is
        extended to include the value.
        """
        value = float(text)
        if value > self.maximum():
            self.setMaximum(value)
        elif value < self.minimum():
            self.setMinimum(value)
        return value

    def textFromValue(self, value):
        """
        Return the text representation of the given value.

        If the value is greater than 1e6, it is formatted with the
        default precision. Otherwise, it is formatted with a precision of
        8 digits.
        """
        if value > 1e6:
            return format_float(value)
        else:
            return format_float(value, width=8)

    def setValue(self, value):
        """
        Set the value of the spin box.

        The number of decimal places is adjusted depending on the value.
        If the value is 0, two decimal places are used. Otherwise, the
        number of decimal places is set to the number of digits
        required to represent the absolute value of the number.
        If the value is out of range of the spin box, the range is
        extended to include the value.
        """
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
        """
        Process events and handle timer events.

        This function is called whenever the timer times out. It
        processes any pending events and calls the base class function
        to handle the timer event when the left mouse button is pressed.
        """
        self.app.processEvents()
        if self.app.mouseButtons() & QtCore.Qt.LeftButton:
            super().timerEvent(event)


class NXSlider(QtWidgets.QSlider):

    def __init__(self, slot=None, move=True, inverse=False):

        """
        Initialize the slider.

        Parameters
        ----------
        slot : function, optional
            The function to be called when the slider is released.
        move : bool, optional
            If True, the function is also called when the slider is moved.
        inverse : bool, optional
            If True, the slider is inverted.
        """
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
        """
        Return the value of the slider as an integer.

        The value is returned as an integer unless the slider is
        inverted, in which case the value is the maximum value of the
        slider minus the integer value of the slider.
        """
        _value = super().value()
        if self.inverse:
            return self.maximum() - _value
        else:
            return _value

    def setValue(self, value):
        """
        Set the value of the slider.

        If the slider is inverted, the value is the maximum value of the
        slider minus the integer value of the slider. Otherwise, the
        value is simply set to the integer value of the slider.
        """
        if self.inverse:
            super().setValue(self.maximum() - int(value))
        else:
            super().setValue(int(value))


class NXpatch:
    """Class for a draggable shape on the NXPlotView canvas."""

    lock = None

    def __init__(self, shape, border_tol=0.1, resize=True, plotview=None):
        """
        Initialize the NXpatch object.

        Parameters
        ----------
        shape : matplotlib.patches
            The Matplotlib shape to be made draggable.
        border_tol : float, optional
            The fraction of the axes that the shape must be within to
            be considered in the axes. This is used to determine whether
            or not the shape can be resized. The default is 0.1.
        resize : bool, optional
            If True, the shape can be resized. If False, the shape can
            only be dragged. The default is True.
        plotview : NXPlotView, optional
            The parent window of the shape. If None, the default is to
            use the most recently created NXPlotView window.
        """
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
        """True if the event is inside the shape."""
        if event.inaxes != self.shape.axes:
            return False
        contains, _ = self.shape.contains(event)
        if contains:
            return True
        else:
            return False

    def initialize(self, xp, yp):
        """Function to be overridden by shape sub-class."""
        pass

    def update(self, x, y):
        """Function to be overridden by shape sub-class."""
        pass

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
        """Remove the shape from the plotview and canvas."""
        if self in self.plotview.shapes:
            self.plotview.shapes.remove(self)
        self.shape.remove()
        self.plotview.draw()

    def set_facecolor(self, color):
        """Set the facecolor of the shape."""
        self.shape.set_facecolor(color)
        self.plotview.draw()

    def set_edgecolor(self, color):
        """Set the edgecolor of the shape."""
        self.shape.set_edgecolor(color)
        self.plotview.draw()

    def set_color(self, color):
        """Set the facecolor and edgecolor of the shape."""
        self.shape.set_facecolor(color)
        self.shape.set_edgecolor(color)
        self.plotview.draw()

    def set_alpha(self, alpha):
        """Set the alpha value of the shape."""
        self.shape.set_alpha(alpha)
        self.plotview.draw()

    def set_linestyle(self, linestyle):
        """Set the linestyle of the shape."""
        self.shape.set_linestyle(linestyle)
        self.plotview.draw()

    def set_linewidth(self, linewidth):
        """Set the linewidth of the shape."""
        self.shape.set_linewidth(linewidth)
        self.plotview.draw()


class NXcircle(NXpatch):

    def __init__(self, x, y, r, border_tol=0.1, resize=True, plotview=None,
                 **opts):
        """
        Initialize the NXcircle object.

        Parameters
        ----------
        x, y : float
            x and y values of circle center
        r : float
            radius of circle
        border_tol : float, optional
            the tolerance for when the mouse is considered to be over the
            border of the shape. The default is 0.1.
        resize : bool, optional
            If True, the shape can be resized. If False, the shape can
            only be dragged. The default is True.
        plotview : NXPlotView, optional
            The parent window of the shape. If None, the default is to
            use the most recently created NXPlotView window.
        opts : dict
            Valid options for displaying shapes.
        """
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
        """Return the transform of the plotview."""
        return self.plotview.ax.transData.transform

    @property
    def inverse_transform(self):
        """Return the inverse transform of the plotview."""
        return self.plotview.ax.transData.inverted().transform

    @property
    def center(self):
        """The center of the circle."""
        return self.circle.center

    @property
    def radius(self):
        """The radius of the circle."""
        return abs(self.circle.width) / 2.0

    @property
    def width(self):
        """The width of the circle."""
        return abs(self.circle.width)

    @property
    def height(self):
        """The height of the circle."""
        return 2 * (self.inverse_transform((0, self.pixel_radius)) -
                    self.inverse_transform((0, 0)))[1]

    @property
    def pixel_radius(self):
        """The pixel radius of the circle."""
        return (self.transform((self.radius, 0)) - self.transform((0, 0)))[0]

    def pixel_shift(self, x, y, x0, y0):
        """Return the pixel shift in x and y directions."""
        return tuple(self.transform((x, y)) - self.transform((x0, y0)))

    def radius_shift(self, x, y, xp, yp, x0, y0):
        """Return the radius shift in x and y directions."""
        xt, yt = self.pixel_shift(x, y, x0, y0)
        r = np.sqrt(xt**2 + yt**2)
        xt, yt = self.pixel_shift(xp, yp, x0, y0)
        r0 = np.sqrt(xt**2 + yt**2)
        return (self.inverse_transform((r, 0)) -
                self.inverse_transform((r0, 0)))[0]

    def set_center(self, x, y):
        """Set the center of the circle."""
        self.circle.center = x, y
        self.plotview.draw()

    def set_radius(self, radius):
        """Set the radius of the circle."""
        self.circle.width = 2.0 * radius
        self.circle.height = self.height
        self.plotview.draw()

    def initialize(self, xp, yp):
        """
        Initialize the shape for dragging or resizing.

        Parameters
        ----------
        xp, yp : float
            x and y values of mouse click

        Returns
        -------
        x0, y0, w0, h0, xp, yp, expand : tuple
            x and y values of center of shape, width and height of
            shape, x and y values of mouse click, and whether the shape
            is being resized or dragged
        """
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
        """
        Update the shape based on the mouse position.

        Parameters
        ----------
        x, y : float
            x and y values of the mouse click

        Notes
        -----
        If the shape is being resized, the radius of the circle is
        changed by an amount proportional to the distance from the
        center of the circle to the current mouse position. If the
        shape is being dragged, the center of the circle is changed
        by an amount proportional to the distance from the center of
        the circle to the current mouse position.
        """
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
        """
        Initialize the NXellipse object.

        Parameters
        ----------
        x, y : float
            x and y values of ellipse center
        dx, dy : float
            x and y widths of ellipse
        border_tol : float, optional
            the tolerance for when the mouse is considered to be over
            the border of the shape. The default is 0.2.
        resize : bool, optional
            If True, the shape can be resized. If False, the shape can
            only be dragged. The default is True.
        plotview : NXPlotView, optional
            The parent window of the shape. If None, the default is to
            use the most recently created NXPlotView window.
        opts : dict
            Valid options for displaying shapes.
        """
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
        """The center of the ellipse."""
        return self.ellipse.center

    @property
    def width(self):
        """The width of the ellipse."""
        return self.ellipse.width

    @property
    def height(self):
        """The height of the ellipse."""
        return self.ellipse.height

    def set_center(self, x, y):
        """Set the center of the ellipse."""
        self.ellipse.set_center((x, y))
        self.plotview.draw()

    def set_width(self, width):
        """Set the width of the ellipse."""
        self.ellipse.width = width
        self.plotview.draw()

    def set_height(self, height):
        """Set the height of the ellipse."""
        self.ellipse.height = height
        self.plotview.draw()

    def initialize(self, xp, yp):
        """
        Initialize the shape for dragging or resizing.

        Parameters
        ----------
        xp, yp : float
            x and y values of mouse click

        Returns
        -------
        x0, y0, w0, h0, xp, yp, expand : tuple
            x and y values of center of shape, width and height of
            shape, x and y values of mouse click, and whether the shape
            is being resized or dragged
        """
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
        """
        Update the shape based on the mouse position.

        Parameters
        ----------
        x, y : float
            x and y values of the mouse click

        Notes
        -----
        If the shape is being resized, the width or height of the
        ellipse is changed by an amount proportional to the distance
        from the center of the ellipse to the current mouse position. If
        the shape is being dragged, the center of the ellipse is changed
        by an amount proportional to the distance from the center of the
        ellipse to the current mouse position.
        """
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
        """
        Initialize the NXrectangle object.

        Parameters
        ----------
        x, y : float
            x and y values of lower left corner
        dx, dy : float
            x and y widths of rectangle
        border_tol : float, optional
            the tolerance for when the mouse is considered to be over the
            border of the shape. The default is 0.1.
        resize : bool, optional
            If True, the shape can be resized. If False, the shape can
            only be dragged. The default is True.
        plotview : NXPlotView, optional
            The parent window of the shape. If None, the default is to
            use the most recently created NXPlotView window.
        opts : dict
            Valid options for displaying shapes.
        """
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
        """The width of the rectangle."""
        return self.rectangle.get_width()

    @property
    def height(self):
        """The height of the rectangle."""
        return self.rectangle.get_height()

    @property
    def xy(self):
        """The x and y values of the lower left corner."""
        return self.rectangle.xy

    def set_bounds(self, x, y, dx, dy):
        """
        Set the bounds of the rectangle.

        Parameters
        ----------
        x, y : float
            x and y values of lower left corner
        dx, dy : float
            x and y widths of rectangle
        """
        self.rectangle.set_bounds(x, y, dx, dy)
        self.plotview.draw()

    def set_left(self, left):
        """
        Set the left edge of the rectangle.

        Parameters
        ----------
        left : float
            the new x-coordinate of the left edge of the rectangle
        """
        self.rectangle.set_x(left)
        self.plotview.draw()

    def set_right(self, right):
        """
        Set the right edge of the rectangle.

        Parameters
        ----------
        right : float
            the new x-coordinate of the right edge of the rectangle
        """
        self.rectangle.set_x(right - self.rectangle.get_width())
        self.plotview.draw()

    def set_bottom(self, bottom):
        """
        Set the bottom edge of the rectangle.

        Parameters
        ----------
        bottom : float
            the new y-coordinate of the bottom edge of the rectangle
        """
        self.rectangle.set_y(bottom)
        self.plotview.draw()

    def set_top(self, top):
        """
        Set the top edge of the rectangle.

        Parameters
        ----------
        top : float
            the new y-coordinate of the top edge of the rectangle
        """
        self.rectangle.set_y(top - self.rectangle.get_height())
        self.plotview.draw()

    def set_width(self, width):
        """
        Set the width of the rectangle.

        Parameters
        ----------
        width : float
            the new width of the rectangle
        """
        self.rectangle.set_width(width)
        self.plotview.draw()

    def set_height(self, height):
        """
        Set the height of the rectangle.

        Parameters
        ----------
        height : float
            the new height of the rectangle
        """
        self.rectangle.set_height(height)
        self.plotview.draw()

    def initialize(self, xp, yp):
        """
        Initialize the shape for dragging or resizing.

        Parameters
        ----------
        xp, yp : float
            x and y values of mouse click

        Returns
        -------
        x0, y0, w0, h0, xp, yp, expand : tuple
            x and y values of center of shape, width and height of
            shape, x and y values of mouse click, and whether the shape
            is being resized or dragged
        """
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
        """
        Update the shape based on the mouse position.

        Parameters
        ----------
        x, y : float
            x and y values of the mouse click

        Notes
        -----
        If the shape is being resized, the width or height of the
        rectangle is changed by an amount proportional to the distance
        from the center of the rectangle to the current mouse position.
        If the shape is being dragged, the center of the rectangle is
        changed by an amount proportional to the distance from the
        center of the rectangle to the current mouse position.
        """
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
        """
        Initialize the NXpolygon object.

        Parameters
        ----------
        xy : tuple
            x and y values of vertices of the polygon
        closed : bool, optional
            If True, the polygon is closed. If False, the polygon is open.
            The default is True.
        plotview : NXPlotView, optional
            The parent window of the shape. If None, the default is to
            use the most recently created NXPlotView window.
        opts : dict
            Valid options for displaying shapes.
        """
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
        """x and y values of vertices of polygon"""
        return self.polygon.xy

    def initialize(self, xp, yp):
        """
        Initialize the shape for dragging or resizing.

        Parameters
        ----------
        xp, yp : float
            x and y values of mouse click

        Returns
        -------
        xy0 : array
            x and y values of vertices of polygon
        xp, yp : float
            x and y values of mouse click
        """
        xy0 = self.polygon.xy
        return xy0, xp, yp

    def update(self, x, y):
        """
        Update the shape based on the mouse position.

        Parameters
        ----------
        x, y : float
            x and y values of the mouse click

        Notes
        -----
        The center of the polygon is changed by an amount proportional
        to the distance from the center of the polygon to the current
        mouse position.
        """
        xy0, xp, yp = self.press
        dxy = (x-xp, y-yp)
        self.polygon.set_xy(xy0+dxy)


class NXline:

    def __init__(self, plotview=None, callback=None):
        """
        Initialize the NXline object.

        Parameters
        ----------
        plotview : NXPlotView or None
            The parent window of the shape. If None, the default is to
            use the most recently created NXPlotView window.
        callback : callable or None
            A callback function to be called when the line is drawn. The
            function should take two arguments, the x and y values of
            the line. If None, the default is to do nothing.
        """
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
        """
        Connect to the canvas button press, release and motion events.

        The Matplotlib events are connected to the following methods:
        - 'button_press_event' to on_press
        - 'button_release_event' to on_release
        - 'motion_notify_event' to on_move
        The plotview is deactivated to prevent zooming and panning.
        """
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
        """Store coordinates on button press if over the object."""
        if event.inaxes != self.ax:
            return
        self.start_point = (event.xdata, event.ydata)
        self.line, = self.ax.plot([event.xdata], [event.ydata], ':w', lw=4)

    def on_move(self, event):
        """Move the object if motion activated over the object."""
        if self.start_point is None or event.inaxes != self.ax:
            return
        self.line.set_data([self.start_point[0], event.xdata],
                           [self.start_point[1], event.ydata])
        self.canvas.draw()

    def on_release(self, event):
        """Reset the data when the button is released."""
        if event.inaxes != self.ax:
            return
        self.end_point = (event.xdata, event.ydata)
        if self.callback:
            self.callback(self.start_point, self.end_point)
        self.disconnect()
        self.line.remove()
        self.canvas.draw()
