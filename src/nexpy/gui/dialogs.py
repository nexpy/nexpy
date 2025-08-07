# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import logging
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.legend import Legend
from matplotlib.rcsetup import validate_aspect, validate_float
from nexusformat.nexus import (NeXusError, NXattr, NXdata, NXentry, NXfield,
                               NXgroup, NXlink, NXroot, NXvirtualfield,
                               nxconsolidate, nxgetconfig, nxload, nxsetconfig)
from nexusformat.nexus.utils import all_dtypes, map_dtype

from .pyqt import QtCore, QtWidgets, getOpenFileName, getSaveFileName
from .utils import (convertHTML, display_message, fix_projection, format_mtime,
                    format_timestamp, get_color, get_mtime, human_size,
                    keep_data, load_plugin, natural_sort, report_error,
                    set_style, timestamp, wrap)
from .widgets import (GridParameters, NXCheckBox, NXComboBox, NXDialog,
                      NXDoubleSpinBox, NXLabel, NXLineEdit, NXPanel,
                      NXPlainTextEdit, NXpolygon, NXPushButton, NXScrollArea,
                      NXSpinBox, NXTab, NXTextEdit, NXWidget)


class NewDialog(NXDialog):

    def __init__(self, parent=None):

        """
        Initialize dialog to produce a new workspace in the tree view.

        Parameters
        ----------
        parent : QWidget, optional
            Parent of the dialog. Default is None.

        Notes
        -----
        The dialog will contain a grid with two entries to name the root
        and entry of the new workspace. The 'save' button is included to
        commit the new workspace to the tree view.
        """
        super().__init__(parent=parent)

        self.names = GridParameters()
        self.names.add('root', self.tree.get_new_name(), 'Workspace', None)
        self.names.add('entry', 'entry', 'Entry', True)
        self.save_box = NXCheckBox("Save File", checked=False)

        self.set_layout(self.names.grid(header=None),
                        self.make_layout(self.save_box,
                                         self.close_buttons(save=True)))

    def accept(self):
        """
        Complete creating a new workspace in the tree view.

        The workspace is added to the tree view and the current file is
        saved as a backup in the backup directory. The backup file name
        is stored in the settings under 'backups' and the current
        session is set to the backup file name.
        """
        root = self.names['root'].value
        entry = self.names['entry'].value
        if self.names['entry'].vary:
            self.tree[root] = NXroot(NXentry(name=entry))
            self.treeview.select_node(self.tree[root][entry])
        else:
            self.tree[root] = NXroot()
            self.treeview.select_node(self.tree[root])
        if self.save_box.isChecked():
            self.treeview.select_node(self.tree[root])
            self.mainwindow.save_file()
        self.treeview.update()
        logging.info(f"New workspace '{root}' created")
        super().accept()


class DirectoryDialog(NXDialog):

    def __init__(self, files, directory=None, parent=None):

        """
        Initialize the dialog to select files in a directory to be
        opened.

        Parameters
        ----------
        files : list of str
            List of files to be displayed in the dialog.
        directory : str, optional
            Directory of the files. Default is to use the current
            directory.
        parent : QWidget, optional
            Parent of the dialog. Default is None.

        Notes
        -----
        The dialog displays a checkbox for each file. The user can
        select files by checking the checkbox. The user can also select
        files by entering a prefix in the 'Prefix' field and all files
        starting with that prefix will be selected. The dialog will
        close when the user clicks on the 'Close' button.
        """
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
        """List of files selected in the dialog."""
        return [f for f in self.checkbox if self.checkbox[f].isChecked()]

    def select_prefix(self):
        """
        Select files in the dialog that start with the prefix in the
        'Prefix' field.
        """
        prefix = self.prefix_box.text()
        for f in self.checkbox:
            if f.startswith(prefix):
                self.checkbox[f].setChecked(True)
            else:
                self.checkbox[f].setChecked(False)

    def accept(self):
        """
        Complete selecting files in the dialog.

        The selected files are added to the tree view and the current
        file is saved as a backup in the backup directory. The backup
        file name is stored in the settings under 'backups' and the
        current session is set to the backup file name.
        """
        for i, f in enumerate(self.files):
            fname = str(Path(self.directory).joinpath(f))
            if i == 0:
                self.mainwindow.load_file(fname, wait=1)
            else:
                self.mainwindow.load_file(fname, wait=1, recent=False)
        self.treeview.select_top()
        super().accept()


class PlotDialog(NXDialog):

    def __init__(self, node, lines=False, parent=None):

        """
        Initialize the dialog to plot arbitrary NeXus data in 1D or 2D.

        Parameters
        ----------
        node : NXfield or NXgroup
            The NeXus field or group to be plotted.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        lines : bool, optional
            Whether to plot the data with lines, by default False
        """
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
        """
        The selected signal to be plotted.

        If the selected signal is a link that refers to a file, the
        actual linked signal is returned. Otherwise, the selected signal
        itself is returned.
        """
        _signal = self.group[self.signal_combo.currentText()]
        if isinstance(_signal, NXlink) and _signal._filename is None:
            return _signal.nxlink
        else:
            return _signal

    @property
    def signal_path(self):
        """
        The path of the selected signal.

        If the selected signal is in a root group, the absolute path is
        returned. Otherwise, the relative path is returned.
        """
        signal = self.group[self.signal_combo.currentText()]
        if signal.nxroot.nxclass == "NXroot":
            return signal.nxroot.nxname + signal.nxpath
        else:
            return signal.nxpath

    @property
    def ndim(self):
        """The number of dimensions of the selected signal."""
        return self.signal.ndim

    def choose_signal(self):
        """
        Set up the axis boxes when a new signal is chosen.

        This will create new axis boxes for each axis of the signal and
        remove any remaining boxes for the old signal.
        """
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
        """
        Create a dropdown box for selecting an axis.

        This will create a dropdown box of all the NXfields in the same
        group as the selected signal. The box will be initialized to the
        default axis if it is among the available options.

        Parameters
        ----------
        axis : int
            The axis for which to create the dropdown box.

        Returns
        -------
        box : NXComboBox
            The created dropdown box.
        """
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
        """
        Remove an axis box from the grid layout.

        Parameters
        ----------
        axis : int
            The axis for which to remove the dropdown box.
        """
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
        """
        Check whether a node can be used as an axis for a signal.

        The node must be a one-dimensional field with a length that matches
        the length of the signal in the given axis. If the node is a
        zero-dimensional field, it is also accepted.

        Parameters
        ----------
        node : NXfield or NXgroup
            The node to check.
        axis : int
            The axis for which to check the node.

        Returns
        -------
        result : bool
            True if the node can be used as an axis, False otherwise.
        """
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
        """
        Return the axis for the given axis number.

        Parameters
        ----------
        axis : int
            The axis number.

        Returns
        -------
        axis : NXfield
            The axis.

        If the selected axis is 'NXfield index', a new NXfield is
        created with values from 0 to the length of the signal in the
        given axis. Otherwise, the selected NXfield is returned with its
        values and attributes.
        """
        def plot_axis(axis):
            return NXfield(axis.nxvalue, name=axis.nxname, attrs=axis.attrs)
        axis_name = self.axis_boxes[axis].currentText()
        if axis_name == 'NXfield index':
            return NXfield(range(self.signal.shape[axis]),
                           name=f'Axis{axis}')
        else:
            return plot_axis(self.group[axis_name])

    def get_axes(self):
        """
        Return a list of NXfields containing the selected axes.

        The axes are determined from the values in the axis boxes. If
        the selected axis is 'NXfield index', a new NXfield is created
        with values from 0 to the length of the signal in the given axis.
        Otherwise, the selected NXfield is returned with its values and
        attributes.

        Raises
        ------
        NeXusError
            If there are duplicate axes selected.
        """
        axes = [self.get_axis(axis) for axis in range(self.ndim)]
        names = [axis.nxname for axis in axes]
        if len(names) != len(set(names)):
            raise NeXusError("Duplicate axes selected")
        return axes

    def accept(self):
        """
        Plot the data using the selected options.

        If the selected options are invalid (e.g. duplicate axes are
        selected), a NeXusError is raised and reported.

        Otherwise, the data is plotted using the NXdata.plot method with
        the selected options. The signal path is stored as an attribute
        of the plotted data.

        After plotting, the dialog is closed with accept().
        """
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

    def __init__(self, node, parent=None, **kwargs):

        """
        Initialize dialog to plot a scalar value against a scan axis.

        Parameters
        ----------
        node : NXfield or NXgroup
            The NeXus field or group to be plotted.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(parent=parent)

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
        """
        Set the scan axis of the dialog to the currently selected node.

        The currently selected node must be a scalar NXfield. If the
        selected node is not a scalar NXfield, a NeXusError is raised and
        reported.
        """
        scan_axis = self.treeview.node
        if not isinstance(scan_axis, NXfield):
            display_message("Scan Panel", "Scan axis must be a NXfield")
        elif scan_axis.shape != () and scan_axis.shape != (1,):
            display_message("Scan Panel", "Scan axis must be a scalar")
        else:
            self.textbox['Scan'].setText(self.treeview.node.nxpath)

    def select_files(self):
        """
        Create a dialog to select files to plot.

        The dialog will show a list of files with checkboxes. The list of
        files is determined by the data_path argument passed to the
        constructor. The list of files is filtered to only include files
        that have a scan axis with the scan_path argument. If no scan_path
        argument is provided, all files are included. The dialog also
        allows the user to select a prefix for the files. The selected
        files are returned as a list of (file name, scan value) tuples.
        """
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
        """Select all files in the list that start with a prefix."""
        prefix = self.prefix_box.text()
        for f in self.files:
            if f.startswith(prefix):
                self.files[f].checkbox.setChecked(True)
            else:
                self.files[f].checkbox.setChecked(False)

    def update_files(self):
        """
        Set the scan value of each file in the dialog to its position
        in the list, or clear the scan value if the file does not vary.
        """
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
        """The path of the selected data signal."""
        return self.group[self.signal_combo.selected].nxpath

    @property
    def scan_path(self):
        """The path of the scan variable, as entered by the user."""
        return self.textbox['Scan'].text()

    @property
    def scan_variable(self):
        """The NXfield object associated with the scan variable."""
        if self.scan_path and self.scan_path in self.group.nxroot:
            return self.group.nxroot[self.scan_path]
        else:
            return None

    @property
    def scan_header(self):
        """The name of the scan axis."""
        try:
            return self.scan_variable.nxname.capitalize()
        except AttributeError:
            return 'Variable'

    def scan_axis(self):
        """
        Return the scan axis for the selected files.

        If the scan variable is not given, return an axis with name 'file_index'
        and long_name 'File Index' with values from 1 to the number of files
        selected.  If the scan variable is given, return an axis with the
        same dtype, name, and attributes (long_name and units) as the
        variable, with the values set to the values given in the files.

        Raises
        ------
        NeXusError
            If the files have not been selected.
        """
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
        """
        Set the scan files and values.

        Raises
        ------
        NeXusError
            If the files have not been selected.
        """
        try:
            self.scan_files = [self.tree[self.files[f].name]
                               for f in self.files if self.files[f].vary]
            self.scan_values = [self.files[f].value for f in self.files
                                if self.files[f].vary]
        except Exception:
            raise NeXusError("Files not selected")

    def get_scan(self):
        """
        Return an NXdata object containing the scan data.

        The scan data is constructed from the selected files and the
        selected signal. The scan values are used to create a new axis
        and the signal values are read from each file and stored in the
        new field.

        Returns
        -------
        NXdata
            The scan data.

        Raises
        ------
        NeXusError
            If the files have not been selected.
        """
        signal = self.group[self.data_path]
        axis = self.scan_axis()
        shape = [len(axis)]
        field = NXfield(shape=shape, dtype=signal.dtype, name=signal.nxname)
        for i, f in enumerate(self.scan_files):
            try:
                field[i] = f[self.data_path]
            except Exception:
                raise NeXusError(f"Cannot read '{f}'")
            field[i] = f[self.data_path]
        return NXdata(field, axis, title=self.data_path)

    def plot_scan(self):
        """
        Plot the scan data.

        This will plot the scan data using the selected options and
        append it to the current plot.

        Raises
        ------
        NeXusError
            If the data cannot be plotted.
        """
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
        """
        Copy the scan data to the clipboard.

        This will copy the scan data to the clipboard so that it can be
        pasted into another application.

        Raises
        ------
        NeXusError
            If the data cannot be copied.
        """
        try:
            self.mainwindow.copied_node = self.mainwindow.copy_node(
                self.get_scan())
        except NeXusError as error:
            report_error("Copying Scan", error)

    def save_scan(self):
        """
        Save the scan data to the clipboard.

        This will save the scan data to the clipboard so that it can be
        pasted into another application.

        Raises
        ------
        NeXusError
            If the data cannot be saved.
        """
        try:
            keep_data(self.get_scan())
        except NeXusError as error:
            report_error("Saving Scan", error)

    def close(self):
        """
        Close the dialog.

        This will close the dialog and remove any temporary file that
        was created. If the file cannot be closed, an error message will
        be displayed.

        Raises
        ------
        NeXusError
            If the dialog cannot be closed.
        """
        try:
            self.file_box.close()
        except Exception:
            pass
        super().close()


class ExportDialog(NXDialog):

    def __init__(self, node, parent=None):

        """
        Initialize the dialog to export data.

        The dialog is initialized with two tabs, the first for exporting
        to a NeXus file and the second for exporting to a text file. The
        NeXus tab allows the entry name and data name to be set. The
        text tab allows the delimiter, title, headers, errors and fields
        to be set.

        Parameters
        ----------
        node : NXfield
            The field to be exported.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
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
        """True if header should be included in exported text file."""
        return self.checkbox['header'].isChecked()

    @property
    def title(self):
        """True if title should be included in exported text file."""
        return self.checkbox['title'].isChecked()

    @property
    def errors(self):
        """True if errors should be included in exported text file."""
        return self.checkbox['errors'].isChecked()

    @property
    def export_fields(self):
        """
        The fields to be exported.

        If the checkbox for exporting all fields is checked, this
        will return all fields in the data. Otherwise, it will return
        the x, y, and error fields.

        Returns
        -------
        list of NXfields
            The fields to be exported.
        """
        if self.checkbox['fields'].isChecked():
            return self.all_fields
        else:
            return self.fields

    @property
    def delimiter(self):
        """
        The delimiter to use in exported text files.

        The delimiter is selected by the user in the export dialog.
        If the user selects 'Tab', the delimiter is '\\t' (encoded as a
        raw string literal). Otherwise, the delimiter is the selected
        character (space, comma, colon, or semicolon).

        Returns
        -------
        str
            The delimiter character.
        """
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
        """The name of the data to be exported."""
        return self.nexus_options['data'].value

    def accept(self):
        """
        Save the data to a file.

        This method is called when the Export button is clicked.
        If the current tab is the NeXus tab, the data is saved to a
        NeXus file. Otherwise, it is saved as a text file.

        If the title or header checkboxes are checked, the title
        and/or header are added to the text file.

        The data is saved with the specified delimiter and the
        specified fields are included in the text file.

        If the user cancels the dialog, this method does nothing.
        """
        if self.tabwidget.currentWidget() is self.nexus_tab:
            fname = getSaveFileName(self, "Choose a Filename",
                                    self.data.nxname+'.nxs',
                                    self.mainwindow.file_filter)
            if fname:
                self.set_default_directory(Path(fname).parent)
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
                self.set_default_directory(Path(fname).parent)
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

        """
        Initialize the dialog to show file-based locks on NeXus files.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None

        Attributes
        ----------
        lockdirectory : Path
            The directory where the file-based locks are stored.
        text_box : NXPlainTextEdit
            The text box to display the list of locked files.
        timer : QTimer
            Timer to update the list of locked files every 5 seconds.
        """
        super().__init__(parent=parent)

        self.lockdirectory = Path(nxgetconfig('lockdirectory'))
        self.text_box = NXPlainTextEdit(wrap=False)
        self.text_box.setReadOnly(True)
        self.set_layout(self.label(f'Lock Directory: {self.lockdirectory}'),
                        self.text_box,
                        self.action_buttons(('Clear Locks', self.clear_locks)),
                        self.close_buttons(close=True))
        self.set_title('Locked Files')
        self.setMinimumWidth(800)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.show_locks)
        self.timer.start(5000)

        self.show_locks()

    def convert_name(self, name):
        """
        Convert the name of a file-based lock to the NeXus path it
        refers to.

        The lock file name is the NeXus path with '!!' separating the
        directories and the extension '.lock'.

        Parameters
        ----------
        name : str
            The name of the lock file.

        Returns
        -------
        str
            The NeXus path of the file being locked.
        """
        return '/' + name.replace('!!', '/').replace('.lock', '')

    def show_locks(self):
        """
        Update the text box with the list of locked files, sorted by
        the date the lock was created.

        The text box is cleared if there are no locked files.
        """
        text = []
        for f in sorted(self.lockdirectory.iterdir(), key=get_mtime):
            if f.suffix == '.lock':
                name = self.convert_name(f.name)
                text.append(f'{format_mtime(f.stat().st_mtime)} {name}')
        if text:
            self.text_box.setPlainText('\n'.join(text))
        else:
            self.text_box.setPlainText('No Files')

    def clear_locks(self):
        """
        Open a dialog to show the list of locked files and allow the
        user to clear locks.

        The dialog contains a scrollable area with a checkbox for each
        locked file. The user can check the box for each file whose lock
        should be cleared and click the 'Clear Lock' button. The locks
        are cleared as soon as the button is clicked and the dialog is
        automatically closed.
        """
        dialog = NXDialog(parent=self)
        locks = []
        for f in sorted(self.lockdirectory.iterdir(), key=get_mtime):
            if f.suffix == '.lock':
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
        """
        Clear selected locks.

        This method is called when the 'Clear Lock' button is clicked.
        It clears the selected locks by deleting the lock file and
        removes the corresponding checkbox from the list of locks.
        Finally, it closes the dialog and updates the list of locks.
        """
        for f in list(self.checkbox):
            if self.checkbox[f].isChecked():
                lock_path = Path(self.lockdirectory).joinpath(f)
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                del self.checkbox[f]
        self.locks_dialog.close()
        self.show_locks()


class SettingsDialog(NXDialog):

    def __init__(self, parent=None):
        """
        Initialize the dialog to set NeXpy settings.

        The dialog is initialized with the current settings and contains
        a grid of parameters. The user can change the parameters and
        click the 'Save As Default' button to save the new settings as
        the default settings. The dialog can be closed by clicking the
        'Close' button.
        """
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
        self.parameters.add('scriptdirectory',
                            self.mainwindow.settings.get('settings',
                                                         'scriptdirectory'),
                            'Script Directory')
        self.parameters.add('definitions', cfg['definitions'],
                            'NeXus Definitions Directory')
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
        """
        Save the current settings as the default settings.

        This method is called when the 'Save As Default' button is
        clicked. It sets the default NeXpy settings to the current
        values and saves them in the configuration file. The default
        settings are used when NeXpy is started. The dialog is closed
        after saving the settings.
        """
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
        self.mainwindow.settings.set('settings', 'scriptdirectory',
                                     self.parameters['scriptdirectory'].value)
        self.mainwindow.settings.set('settings', 'definitions',
                                     cfg['definitions'])
        self.mainwindow.settings.set('settings', 'recursive',
                                     cfg['recursive'])
        self.mainwindow.settings.set('settings', 'style',
                                     self.parameters['style'].value)
        self.mainwindow.settings.save()

    def set_nexpy_settings(self):
        """
        Set NeXpy settings based on the current values in the dialog.

        This method is called when the 'Save As Default' button is
        clicked. It sets the default NeXpy settings to the current
        values in the dialog and saves them in the configuration file.
        The default settings are used when NeXpy is started.
        """
        def check_value(value):
            if not value.strip():
                return None
            return value
        nxsetconfig(memory=self.parameters['memory'].value,
                    maxsize=self.parameters['maxsize'].value,
                    compression=self.parameters['compression'].value,
                    encoding=self.parameters['encoding'].value,
                    lock=self.parameters['lock'].value,
                    lockexpiry=self.parameters['lockexpiry'].value,
                    lockdirectory=check_value(
                        self.parameters['lockdirectory'].value),
                    definitions=check_value(
                        self.parameters['definitions'].value),
                    recursive=self.parameters['recursive'].value)
        set_style(self.parameters['style'].value)

    def accept(self):
        """
        Save the current settings as the default settings.

        This method is called when the dialog is accepted. It sets the
        default NeXpy settings to the current values in the dialog and
        saves them in the configuration file. The default settings are
        used when NeXpy is started. The dialog is closed after saving
        the settings.
        """
        self.set_nexpy_settings()
        super().accept()


class CustomizeDialog(NXPanel):

    def __init__(self, parent=None):
        """
        Initialize the Customize Panel.

        The Customize Panel is initialized with the given parent and its
        tab class is set to CustomizeTab. The plotview_sort flag is set to
        True to sort the plotviews in the Customize Panel.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the Customize Panel. The default is None.
        """
        super().__init__('Customize', title='Customize Panel', parent=parent)
        self.tab_class = CustomizeTab
        self.plotview_sort = True


class CustomizeTab(NXTab):

    legend_location = {v: k for k, v in Legend.codes.items()}

    def __init__(self, label, parent=None):
        """
        Initialize the Customize Tab.

        The Customize Tab is initialized with the given label and
        parent. The active plotview is saved as an instance variable.
        The Customize Tab is divided into sections for labels, plots,
        and grid. The labels section contains parameters for the title,
        x-axis label, y-axis label, and legend. The plots section
        contains parameters for each plot, including line style, marker
        style, marker size, line width, color, and label. The grid
        section contains parameters for the grid style and line width.
        The parameters are saved in a dictionary as instance variables.
        The layout of the Customize Tab is set to a vertical layout with
        a grid layout for each section.
        """
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
        """
        Return a string label for the given plot.

        The label is a concatenation of the plot number and the path of
        the plot.
        """
        return str(plot) + ': ' + self.plots[plot]['path']

    def label_plot(self, label):
        """
        Return the plot number from the given label string.

        The label is a concatenation of the plot number and the path of
        the plot.
        """
        return int(label[:label.index(':')])

    def update(self):
        """
        Update the Customize Tab after a change in the active plotview.

        If the active plotview is an image, the image parameters are
        updated. If the active plotview is a plot, the plot parameters
        are updated. Any plots that are no longer in the active plotview
        are removed.
        """
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
        """
        Return the parameters for the plot labels.

        Returns
        -------
        GridParameters
            A GridParameters object containing parameters for the plot title,
            x-axis label, and y-axis label.
        """
        parameters = GridParameters()
        parameters.add('title', self.plotview.title, 'Title')
        parameters.add('xlabel', self.plotview.xaxis.label, 'X-Axis Label')
        parameters.add('ylabel', self.plotview.yaxis.label, 'Y-Axis Label')
        parameters.grid(title='Plot Labels', header=False, width=200)
        return parameters

    def update_label_parameters(self):
        """
        Update the Customize Tab label parameters from the active plotview.

        This function is called whenever the active plotview changes,
        and it updates the parameters in the Customize Tab label section
        with the title, x-axis label, and y-axis label of the active
        plotview.
        """
        p = self.parameters['labels']
        p['title'].value = self.plotview.title
        p['xlabel'].value = self.plotview.xaxis.label
        p['ylabel'].value = self.plotview.yaxis.label

    def image_parameters(self):
        """
        Return the parameters for image plots.

        Returns
        -------
        GridParameters
            A GridParameters object containing parameters for image plots.
            The parameters include aspect ratio, skew angle, grid, grid color,
            grid style, grid alpha, minor ticks, and color bar minor ticks.
            If the image has a colormap with a bad color, there is also a
            bad color parameter.
        """
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
        """
        Update the tab image parameters from the active plotview.

        This function is called whenever the active plotview changes,
        and it updates the parameters in the Customize Tab image section
        with the aspect ratio, skew angle, grid, grid color, grid style,
        grid alpha, minor ticks, and color bar minor ticks of the active
        plotview.
        """
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
        """
        Create a GridParameters object for a plot.

        This function creates a GridParameters object that contains
        parameters for a plot, including legend label, legend, legend
        order, color, line style, line width, marker, marker style,
        marker size, z-order, scale, and offset. The parameters are
        initialized with the values from the active plotview, and the
        function returns the GridParameters object.

        Parameters
        ----------
        plot : str
            The label of the plot for which to create the parameters.

        Returns
        -------
        GridParameters
            A GridParameters object containing parameters for the plot.
        """
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
        """
        Update the parameters for a given plot.

        This function is called when the properties of a plot are changed
        outside of the Parameters tab. It updates the parameters in the
        Parameters tab with the new values from the plot.

        Parameters
        ----------
        plot : str
            The label of the plot to update.
        """
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
        """
        Return the parameters for the plot attributes.

        These parameters are used in the Parameters Tab of the Customize Dialog
        to set the plot attributes.

        Returns
        -------
        GridParameters
            A GridParameters object containing parameters for the plot legend,
            label, grid, grid color, grid style, grid alpha, and minor ticks.
        """
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
        """
        Update the parameters for the plot attributes in the Parameters
        Tab of the Customize Dialog with the current values from the
        plot.
        """
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
        """True if the legend is empty."""
        labels = [self.plot_label(plot) for plot in self.plots]
        return 'Yes' not in [self.parameters[label]['legend'].value
                             for label in labels]

    def get_legend_order(self):
        """
        Return the order of the legend labels.

        The order is a list of the position of each plot in the list of
        plots, starting from 0.
        """
        order = []
        for plot in self.plots:
            label = self.plot_label(plot)
            order.append(int(self.parameters[label]['legend_order'].value - 1))
        return order

    def plot_index(self, plot):
        """
        Return the index of the given plot in the list of plots.

        Parameters
        ----------
        plot : int
            The index of the plot in the list of plots.

        Returns
        -------
        index : int
            The index of the given plot in the list of plots.
        """
        return list(self.plots).index(plot)

    def update_legend_order(self):
        """
        Update the legend order when the user changes the legend order in the
        Customize dialog.

        If the user selects a legend order that is not in the list of current
        legend orders, it will be added to the list of legend orders. If the
        user selects a legend order that is already in the list of legend
        orders, it will be replaced with the new order.

        If the user selects a legend order that is less than 0 or greater than
        or equal to the length of the list of plots, a ValueError will be
        raised.
        """
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
        """
        Set the legend of the plot.

        If the legend is set to 'None', the legend is removed.
        Otherwise, the legend is set with the specified label and
        location.
        """
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
        """
        Set the grid of the plot.

        If the grid is set to 'On', it is added to the plot. The grid
        color, style, and alpha are set with the specified values.
        The minor ticks are set according to the specified setting.
        If the grid is set to 'Off', it is removed from the plot.
        """
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
        """
        Scale a plot.

        When the scale parameter is changed, the plot is rescaled
        and the offset parameter is updated to be in the same units
        as the scaled plot. The single step of the offset spinbox
        is set to 1% of the offset value, and the range of the spinbox
        is set to be 10 times the absolute value of the offset.
        """
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
        """
        Block or unblock signals on the legend order spin boxes.

        This method is used to prevent recursive calls to the
        legend_order_changed method when the legend order is being
        changed by the legend_order_changed method itself.
        """
        for p in [parameter for parameter in self.parameters if
                  parameter not in ['labels', 'grid']]:
            self.parameters[p]['legend_order'].box.blockSignals(block)

    def reset(self):
        """
        Reset the Customize Tab parameters to their current values in
        the plotview, and update the Customize Tab display accordingly.
        """
        self.update()

    def apply(self):
        """
        Apply the Customize Tab parameters to the plotview.

        This method is called when the "Apply" button is clicked. It
        applies all the changes made in the Customize Tab to the
        plotview, and updates the Customize Tab display accordingly.
        """
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
        """
        Initialize the Style Panel.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the Style Panel. The default is None.
        """
        super().__init__('Style', title='Style Panel', parent=parent)
        self.tab_class = StyleTab
        self.plotview_sort = True


class StyleTab(NXTab):

    def __init__(self, label, parent=None):
        """
        Initialize the Style Tab.

        Parameters
        ----------
        label : str
            The label for the tab.
        parent : QWidget, optional
            The parent of the tab. The default is None.
        """
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
        pars = self.plotview.figure.subplotpars
        self.original_layout = {'left': pars.left, 'right': pars.right,
                                'bottom': pars.bottom, 'top': pars.right}


    def label_parameters(self):
        """
        Create a GridParameters object for the plot labels.

        This function creates a GridParameters object that contains
        parameters for the plot labels, including the title, x-axis
        label, and y-axis label. The parameters are initialized with
        the values from the active plotview, and the function returns
        the GridParameters object.
        """
        p = GridParameters()
        p.add('title', self.plotview.title, 'Title')
        p.add('xlabel', self.plotview.xaxis.label, 'X-Axis Label')
        p.add('ylabel', self.plotview.yaxis.label, 'Y-Axis Label')
        p.grid(title='Plot Labels', header=False, width=200)
        return p

    def update_label_parameters(self):
        """
        Update the parameters for the plot labels.

        This function is called whenever the properties of the plot labels
        are changed outside of the Style Tab. It updates the parameters in
        the Style Tab with the new values from the plot.
        """
        p = self.parameters['labels']
        p['title'].value = self.plotview.title
        p['xlabel'].value = self.plotview.xaxis.label
        p['ylabel'].value = self.plotview.yaxis.label

    def font_parameters(self):
        """
        Create a GridParameters object for the plot fonts.

        This function creates a GridParameters object that contains
        parameters for the font sizes of the plot labels, including
        the title, x-axis label, y-axis label, tick labels, and colorbar
        labels (if the plot is an image). The parameters are initialized
        with a value of 0, and the function returns the GridParameters
        object.
        """
        p = GridParameters()
        p.add('title', 0, 'Title Font Size')
        p.add('xlabel', 0, 'X-Label Font Size')
        p.add('ylabel', 0, 'Y-Label Font Size')
        p.add('ticks', 0, 'Tick Font Size')
        if self.plotview.image is not None:
            p.add('colorbar', 10, 'Colorbar Font Size')
        return p

    def update_font_parameters(self):
        """
        Update the parameters for the plot fonts.

        This function is called whenever the font sizes of the plot labels
        are changed outside of the Style Tab. It updates the parameters in
        the Style Tab with the new values from the plot.
        """
        p = self.parameters['fonts']
        p['title'].value = self.plotview.ax.title.get_fontsize()
        p['xlabel'].value = self.plotview.ax.xaxis.label.get_fontsize()
        p['ylabel'].value = self.plotview.ax.yaxis.label.get_fontsize()
        p['ticks'].value = self.plotview.ax.get_xticklabels()[0].get_fontsize()
        if self.plotview.colorbar is not None:
            p['colorbar'].value = (
                self.plotview.colorbar.ax.get_yticklabels()[0].get_fontsize())

    def update(self):
        """
        Update the parameters in the Customize Tab to match the active
        plotview.

        This function is called whenever the active plotview is changed.
        It updates the parameters in the Customize Tab to match the
        active plotview.
        """
        self.update_label_parameters()
        self.update_font_parameters()

    def tight_layout(self):
        """
        Call matplotlib's tight_layout function on the figure.

        This function calls matplotlib's tight_layout function on the
        figure of the active plotview. The current layout is saved
        before calling tight_layout, so that the layout can be reset
        if needed.
        """
        self.plotview.figure.tight_layout()
        self.plotview.draw()

    def reset_layout(self):
        """
        Reset the layout of the active plotview to its previous state.

        This function resets the layout of the active plotview to its
        previous state, which is saved when the tight_layout function
        is called. This is useful if the automatic layout adjustment
        done by tight_layout is not what you want. The original layout
        is restored, and the plot is redrawn.
        """
        self.plotview.figure.subplots_adjust(**self.original_layout)
        self.plotview.draw()

    def adjust_layout(self):
        """
        Call the configure_subplots method of the Options Tab to adjust
        the layout of the active plotview.
        """
        self.plotview.otab.configure_subplots()

    def save_default(self):
        """
        Save the current font settings as the default settings.

        This method is called when the 'Save As Default' button is
        clicked. It sets the default Matplotlib settings to the current
        values and saves them in the configuration file. The default
        settings are used when NeXpy is started. The dialog is closed
        after saving the settings.
        """
        p = self.parameters['fonts']
        mpl.rcParams['axes.titlesize'] = p['title'].value
        mpl.rcParams['axes.labelsize'] = p['xlabel'].value
        mpl.rcParams['xtick.labelsize'] = p['ticks'].value
        mpl.rcParams['ytick.labelsize'] = p['ticks'].value
        self.apply()

    def apply(self):
        """
        Apply the current font settings to the active plotview.

        This method applies the current font settings to the active
        plotview, and redraws the plot. The font sizes of the title,
        axis labels, tick labels, and colorbar labels are updated.
        """
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

    def __init__(self, parent=None):
        """
        Initialize the dialog to set plot window limits.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__('Projection', title='Projection Panel', apply=False,
                         parent=parent)
        self.tab_class = ProjectionTab
        self.plotview_sort = True


class ProjectionTab(NXTab):

    def __init__(self, label, parent=None):

        """
        Initialize the dialog to set plot window limits.

        Parameters
        ----------
        label : str
            The label used to identify this dialog. It can be
            used as the key to select an instance in the 'dialogs' dictionary.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
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
        """
        Initialize the projection limits and copy widgets.

        This function is called when the dialog is first created and
        after the data has been changed. It sets the minimum and maximum
        limits to the centers of the data and sets the current limits to
        the current limits of the plot. The copy widgets are also
        updated to reflect the current state of the other tabs.
        """
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
        """
        Return a list of NXfields containing the selected axes.

        The axes are determined from the values in the axis boxes. If
        the selected axis is 'NXfield index', a new NXfield is created
        with values from 0 to the length of the signal in the given axis.
        Otherwise, the selected NXfield is returned with its values and
        attributes.

        Raises
        ------
        NeXusError
            If there are duplicate axes selected.
        """
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        """
        Set the axes in the tab.

        This function clears the current axes in the x and y boxes and
        adds the axes returned by get_axes. If the number of dimensions
        is less than or equal to 2, then the y label and box are hidden.
        Otherwise, the y label and box are shown and the axes are selected
        as the current y-axis of the plotview.
        """
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
        """Name of the selected x-axis."""
        return self.xbox.currentText()

    def set_xaxis(self):
        """
        Set the x-axis of the plotview to the selected axis.

        If the selected axis is the same as the current y-axis, then
        the y-axis is reset to 'None'.
        """
        if self.xaxis == self.yaxis:
            self.ybox.select('None')
        self.update_overbox()

    @property
    def yaxis(self):
        """Name of the selected y-axis."""
        if self.ndim <= 2:
            return 'None'
        else:
            return self.ybox.selected
        self.update_overbox()

    def set_yaxis(self):
        """
        Set the y-axis of the plotview to the selected axis.

        If the selected axis is the same as the current x-axis, then
        the x-axis is reset to the first axis that is not the same as
        the y-axis. If the y-axis is 'None', then the overbox is shown
        (if the plot is 1D), the lines and select checkboxes are shown,
        and the select mode is set to select. Otherwise, the overbox is
        hidden, the lines and select checkboxes are hidden, and the
        select mode is unset. Finally, the panel is updated.
        """
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
        """
        Set the limits of the projection plot.

        This function is called when the limits of any of the axes
        are changed. It checks if the limits are locked and, if so,
        updates the minimum limit to be equal to the maximum limit minus
        the difference between the two limits. Otherwise, if the minimum
        limit is greater than the maximum limit, it updates the maximum
        limit to be equal to the minimum limit. Finally, it updates the
        plot by calling draw_rectangle.
        """
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
        """
        Return the limits of the plot for the given axis.

        Parameters
        ----------
        axis : int or None
            The axis for which to return the limits. If None, return the
            limits for all axes.

        Returns
        -------
        limits : list of tuples of int
            The limits of the plot for the given axis or axes. Each tuple
            is a pair of start and stop indices.
        """
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
        """
        Enable or disable the 'Lock' checkboxes.

        If the 'Lock' checkbox is checked, the difference between the
        minimum and maximum values of the axis is fixed, and the minimum
        value box is disabled. If the box is unchecked, the difference
        is set to None, and the minimum value box is enabled.
        """
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
        """True if the 'Sum' checkbox is checked."""
        try:
            return self.checkbox["sum"].isChecked()
        except Exception:
            return False

    @summed.setter
    def summed(self, value):
        self.checkbox["sum"].setChecked(value)

    @property
    def lines(self):
        """True if the 'Lines' checkbox is checked."""
        try:
            return self.checkbox["lines"].isChecked()
        except Exception:
            return False

    @lines.setter
    def lines(self, value):
        self.checkbox["lines"].setChecked(value)

    @property
    def over(self):
        """True if the 'Over' checkbox is checked."""
        return self.overbox.isChecked()

    @over.setter
    def over(self, value):
        self.overbox.setVisible(True)
        self.overbox.setChecked(value)

    @property
    def weights(self):
        """True if the 'Weights' checkbox is checked."""
        return self.checkbox["weights"].isChecked()

    @property
    def select(self):
        """True if the 'Select' checkbox is checked."""
        return self.checkbox["select"].isChecked()

    def set_select(self):
        """
        Show or hide the 'Select' widget.

        If the 'Select' checkbox is checked, show the 'Select' widget.
        Otherwise, hide the 'Select' widget.
        """
        if self.checkbox["select"].isChecked():
            self.select_widget.setVisible(True)
        else:
            self.select_widget.setVisible(False)
        self.panel.update()

    def set_maximum(self):
        """
        Uncheck the 'Minimum' checkbox if the 'Maximum' checkbox is
        checked.
        
        If the 'Maximum' checkbox is checked, uncheck the 'Minimum'
        checkbox.
        """
        if self.checkbox["max"].isChecked():
            self.checkbox["min"].setChecked(False)

    def set_minimum(self):
        """
        Uncheck the 'Maximum' checkbox if the 'Minimum' checkbox is
        checked.
        
        If the 'Minimum' checkbox is checked, uncheck the 'Maximum'
        checkbox.
        """
        if self.checkbox["min"].isChecked():
            self.checkbox["max"].setChecked(False)

    def get_projection(self):
        """
        Return the data projected onto the selected axes.

        Returns
        -------
        data : NXdata
            The projected data.

        Notes
        -----
        If the 'Select' checkbox is checked, the data is selected
        according to the parameters in the 'Select' tab before
        projection.
        """
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
        """
        Save the projected data to the scratch workspace.

        Notes
        -----
        If the data does not exist in the scratch workspace, a new data
        group is created with the projected data. If the data does
        exist, the projected data replace the existing data.
        """
        try:
            keep_data(self.get_projection())
        except NeXusError as error:
            report_error("Saving Projection", error)

    def plot_projection(self):
        """
        Plot the projected data.

        Notes
        -----
        If the 'Plot' parameter is set to None, a new plotting window is
        created with the projected data. If the 'Plot' parameter is set to
        an existing plotting window, the projected data are added to
        that window. If the 'Over' parameter is set to True, the projected
        data are plotted over the existing data in the plotting window.
        If the 'Weights' parameter is set, the projected data are weighted
        by those values. If the 'Lines' parameter is set to True, the
        projected data are plotted with lines.
        """
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
        """The plotview that the projected data are plotted in."""
        if 'Projection' in self.plotviews:
            return self.plotviews['Projection']
        else:
            return None

    def mask_data(self):
        """
        Mask the data in the currently defined limits.

        The data are masked by setting the corresponding elements of the
        signal array to np.ma.masked. The plot is then updated to show
        the masked data.
        """
        try:
            limits = tuple(slice(x, y) for x, y in self.get_limits())
            self.plotview.data.nxsignal[limits] = np.ma.masked
            self.plotview.replot_data()
        except NeXusError as error:
            report_error("Masking Data", error)

    def unmask_data(self):
        """
        Unmask the data in the currently defined limits.

        The data are unmasked by setting the corresponding elements of
        the signal array to np.ma.nomask. The plot is then updated to
        show the unmasked data.

        Notes
        -----
        If no data are masked after unmasking, the signal array is reset
        to np.ma.nomask, so that the entire signal array is available
        for plotting.
        """
        try:
            limits = tuple(slice(x, y) for x, y in self.get_limits())
            self.plotview.data.nxsignal.mask[limits] = np.ma.nomask
            if not self.plotview.data.nxsignal.mask.any():
                self.plotview.data.mask = np.ma.nomask
            self.plotview.replot_data()
        except NeXusError as error:
            report_error("Masking Data", error)

    def block_signals(self, block=True):
        """
        Block signals from the limits boxes.

        Parameters
        ----------
        block : bool
            True to block signals, False to unblock signals
        """
        for axis in range(self.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)

    @property
    def rectangle(self):
        """The rectangle defining the projection limits."""
        if self._rectangle not in self.plotview.ax.patches:
            self._rectangle = NXpolygon(self.get_rectangle(), closed=True,
                                        plotview=self.plotview).shape
            self._rectangle.set_edgecolor(self.plotview._gridcolor)
            self._rectangle.set_facecolor('none')
            self._rectangle.set_linestyle('dashed')
            self._rectangle.set_linewidth(2)
        return self._rectangle

    def get_rectangle(self):
        """
        Return the coordinates of the projection limits rectangle.

        The coordinates are returned as a list of four tuples, each
        tuple containing the x and y coordinates of a vertex of the
        rectangle. If the plot is skewed, the coordinates are
        transformed to the skewed coordinates.
        """
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
        """
        Redraw the rectangle in the plot based on the current limits.

        Notes
        -----
        The coordinates of the rectangle are obtained from the limits of
        the x and y axes. If the plot is skewed, the coordinates are
        transformed to the skewed coordinates.
        """
        self.rectangle.set_xy(self.get_rectangle())
        self.plotview.draw()

    def rectangle_visible(self):
        """
        Return True if the rectangle defining the projection limits
        should be visible.

        The rectangle is visible unless the 'Hide Limits' checkbox is
        checked.
        """
        return not self.checkbox["hide"].isChecked()

    def hide_rectangle(self):
        """
        Hide or show the rectangle defining the projection limits based
        on the 'Hide Limits' checkbox.

        If the checkbox is checked, hide the rectangle. Otherwise, show
        it.
        """
        if self.checkbox["hide"].isChecked():
            self.rectangle.set_visible(False)
        else:
            self.rectangle.set_visible(True)
        self.plotview.draw()

    def update_overbox(self):
        """
        Update the overbox in the tabs of the dialog.

        This function is called whenever the data in the plot are changed.
        It checks if the data are one-dimensional and if the y-axis is 'None',
        and if so, sets the overbox to be visible. Otherwise, it hides the
        overbox and sets the checkbox to False. This is used to enable
        plotting additional one-dimensional projections over the current
        projection.
        """
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
        """
        Update the limits boxes and the rectangle in the plot based on
        the current limits of the axes.

        Notes
        -----
        If the limits of the x or y axes have changed, the limits boxes
        are updated to reflect the new limits. The rectangle is then
        redrawn based on the updated limits. The copybox is also updated
        to reflect the current limits.
        """
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
        """
        Copy the limits and other properties from the selected tab.

        Notes
        -----
        This function is called when the 'Copy' button is clicked. It
        copies the limits and other properties from the selected tab and
        updates the limits boxes and the rectangle in the plot.
        """
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
        """
        Reset the limits boxes and the rectangle in the plot to the
        current limits of the axes.

        Notes
        -----
        This function is called when the 'Reset' button is clicked. It
        resets the limits boxes and the rectangle in the plot to the
        current limits of the axes. The limits boxes are updated to
        reflect the current limits of the axes. The rectangle is then
        redrawn based on the updated limits.
        """
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
        """
        Close the dialog and remove the rectangle from the plot.

        Notes
        -----
        This function is called when the dialog is closed. It removes the
        rectangle from the plot and redraws the plot. If an exception is
        raised, it is ignored.
        """
        try:
            if self._rectangle:
                self._rectangle.remove()
            self.plotview.draw()
        except Exception:
            pass


class LimitDialog(NXPanel):

    def __init__(self, parent=None):
        """
        Initialize the dialog to set plot window limits.

        The dialog is initialized with the given parent and its
        tab class is set to LimitTab. The plotview_sort flag is set to
        True to sort the plotviews in the dialog.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the dialog. The default is None.
        """
        super().__init__('Limits', title='Limits Panel', parent=parent)
        self.tab_class = LimitTab
        self.plotview_sort = True


class LimitTab(NXTab):

    def __init__(self, label, parent=None):

        """
        Initialize the dialog to set plot window limits.

        The dialog is initialized with the given parent and the
        given label. It is divided into sections for axes, limits,
        and figure size. The axes section contains parameters for
        the x-axis and y-axis. The limits section contains parameters
        for the minimum, maximum, and lock for each axis. The figure
        size section contains parameters for the horizontal and
        vertical size of the plot window. The parameters are saved
        in a dictionary as instance variables. The layout of the
        dialog is set to a vertical layout with a grid layout for
        each section.
        """
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
        """
        Initialize the projection limits and copy widgets.

        This function is called when the dialog is first created and
        after the data has been changed. It sets the minimum and maximum
        limits to the centers of the data and sets the current limits to
        the current limits of the plot. The copy widgets are also
        updated to reflect the current state of the other tabs.
        """
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
        """
        Return a list of NXfields containing the selected axes.

        The axes are determined from the values in the axis boxes. If
        the selected axis is 'NXfield index', a new NXfield is created
        with values from 0 to the length of the signal in the given
        axis. Otherwise, the selected NXfield is returned with its
        values and attributes.

        Raises
        ------
        NeXusError
            If there are duplicate axes selected.
        """
        return self.plotview.xtab.get_axes()

    def set_axes(self):
        """
        Set the axes in the tab.

        This function clears the current axes in the x and y boxes and
        adds the axes returned by get_axes. If the number of dimensions
        is less than or equal to 2, then the y label and box are hidden.
        Otherwise, the y label and box are shown and the axes are selected
        as the current y-axis of the plotview.
        """
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
        """Axis selected in the x box."""
        return self.xbox.selected

    def set_xaxis(self):
        """
        Set the x-axis of the plotview to the selected axis.

        If the selected axis is the same as the current y-axis, then
        the y-axis is reset to 'None'.
        """
        if self.xaxis == self.yaxis:
            if self.yaxis == self.plotview.yaxis.name:
                self.ybox.select(self.plotview.xaxis.name)
            else:
                self.ybox.select(self.plotview.yaxis.name)

    @property
    def yaxis(self):
        """Axis selected in the y box."""
        return self.ybox.selected

    def set_yaxis(self):
        """
        Set the y-axis of the plotview to the selected axis.

        If the selected axis is the same as the current x-axis, then
        the x-axis is reset to the first axis that is not the same as
        the y-axis. If the y-axis is 'None', then the overbox is shown
        (if the plot is 1D), the lines and select checkboxes are shown,
        and the select mode is set to select. Otherwise, the overbox is
        hidden, the lines and select checkboxes are hidden, and the
        select mode is unset. Finally, the panel is updated.
        """
        if self.yaxis == self.xaxis:
            if self.xaxis == self.plotview.xaxis.name:
                self.xbox.select(self.plotview.yaxis.name)
            else:
                self.xbox.select(self.plotview.xaxis.name)

    def set_limits(self):
        """
        Set the limits of the projection plot.

        This function is called when the limits of any of the axes
        are changed. It checks if the limits are locked and, if so,
        updates the minimum limit to be equal to the maximum limit minus
        the difference between the two limits. Otherwise, if the minimum
        limit is greater than the maximum limit, it updates the maximum
        limit to be equal to the minimum limit. Finally, it updates the
        plot by calling draw_rectangle.
        """
        self.block_signals(True)
        for axis in range(self.ndim):
            if self.lockbox[axis].isChecked():
                min_value = self.maxbox[axis].value() - self.maxbox[axis].diff
                self.minbox[axis].setValue(min_value)
            elif self.minbox[axis].value() > self.maxbox[axis].value():
                self.maxbox[axis].setValue(self.minbox[axis].value())
        self.block_signals(False)

    def get_limits(self, axis=None):
        """
        Return the limits of the plot for the given axis.

        Parameters
        ----------
        axis : int or None
            The axis for which to return the limits. If None, return the
            limits for all axes.

        Returns
        -------
        limits : list of tuples of int
            The limits of the plot for the given axis or axes. Each tuple
            is a pair of start and stop indices.
        """
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
        """
        Enable or disable the 'Lock' checkboxes.

        If the 'Lock' checkbox is checked, the difference between the
        minimum and maximum values of the axis is fixed, and the minimum
        value box is disabled. If the box is unchecked, the difference
        is set to None, and the minimum value box is enabled.
        """
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
        """
        Block signals from the limits boxes.

        Parameters
        ----------
        block : bool
            True to block signals, False to unblock signals
        """
        for axis in range(self.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)
        self.minbox['signal'].blockSignals(block)
        self.maxbox['signal'].blockSignals(block)

    def choose_sync(self):
        """
        If the 'Sync' checkbox is checked, uncheck the 'Sync' checkbox
        in the tab from which the limits are being copied.
        """
        if self.checkbox['sync'].isChecked():
            tab = self.tabs[self.copybox.selected]
            tab.checkbox['sync'].setChecked(False)

    def update(self):
        """
        Update the limits boxes and the rectangle in the plot based on
        the current limits of the axes.

        Notes
        -----
        If the 'Sync' checkbox is checked, the limits of the axes are
        updated from the tab from which the limits are being copied.
        Otherwise, the limits of the axes are updated from the current
        limits of the axes. The limits boxes are then updated to reflect
        the new limits. The rectangle is then redrawn based on the updated
        limits. The copybox is also updated to reflect the current limits.
        """
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
        """
        Update the limits boxes and the rectangle in the plot based on
        the current limits of the axes.

        Notes
        -----
        The limits of the axes are updated from the current limits of
        the axes. The limits boxes are then updated to reflect the new
        limits. The rectangle is then redrawn based on the updated
        limits. The figure size is also updated.
        """
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
        """
        Update the signal limits boxes and the rectangle in the plot
        based on the current limits of the signal axis.

        Notes
        -----
        The limits of the signal axis are updated from the current
        limits of the signal axis. The limits boxes are then updated to
        reflect the new limits. The rectangle is then redrawn based on
        the updated limits.
        """
        minbox, maxbox = self.plotview.vtab.minbox, self.plotview.vtab.maxbox
        self.minbox['signal'].setRange(minbox.minimum(), minbox.maximum())
        self.maxbox['signal'].setRange(maxbox.minimum(), maxbox.maximum())
        self.minbox['signal'].setSingleStep(minbox.singleStep())
        self.maxbox['signal'].setSingleStep(maxbox.singleStep())
        self.minbox['signal'].setValue(minbox.value())
        self.maxbox['signal'].setValue(maxbox.value())

    def update_properties(self):
        """
        Update the properties dictionary from the current state of the
        plot.

        The properties dictionary contains the aspect, logx, logy, and
        skew of the plot. If the 'Sync' checkbox is not checked, the
        cmap, interpolation, and logv are also included in the
        dictionary.
        """
        if self.ndim > 1:
            self.properties = {'aspect': self.plotview.aspect,
                               'logx': self.plotview.logx,
                               'logy': self.plotview.logy,
                               'skew': self.plotview.skew}
            if not self.lockbox['signal'].isChecked():
                self.properties['cmap'] = self.plotview.cmap
                self.properties['interpolation'] = self.plotview.interpolation
                self.properties['logv'] = self.plotview.logv
        else:
            self.properties = {}

    def copy_properties(self, tab):
        """
        Copy properties from another tab to this tab.

        Parameters
        ----------
        tab : LimitTab
            The tab from which to copy the properties.

        Notes
        -----
        This function is called when the 'Copy' button is clicked. It
        compares the properties dictionary of the current tab with the
        properties dictionary of the selected tab, and copies any
        properties that are different into the copied_properties
        dictionary. The copied_properties dictionary is used to update
        the plot when the 'Apply' button is clicked.
        """
        self.update_properties()
        for p in self.properties:
            if self.properties[p] != tab.properties[p]:
                self.copied_properties[p] = tab.properties[p]

    def copy(self):
        """
        Copy properties from another tab to this tab.

        Notes
        -----
        This function is called when the 'Copy' button is clicked. It
        copies the properties from the selected tab to this tab,
        including the x and y axes, limits, and checkbox states.
        If the 'Sync' checkbox is not checked, it also copies the
        cmap, interpolation, and logv properties. It then updates the
        plot based on the new properties.
        """
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
        """
        Reset the plot to the original size and view.

        This function is called when the 'Reset' button is clicked. It
        resets the plot to its original size and view, and updates the
        display accordingly.
        """
        self.plotview.otab.home()
        self.update()

    def apply(self):
        """
        Apply the current limits and options to the plot.

        This function is called when the 'Apply' button is clicked. It
        applies the current limits and options to the plot, and redraws
        the plot. If the limits of the x or y axes have changed, the
        limits boxes are updated to reflect the new limits. The image
        is then redrawn based on the updated limits. The copy widgets
        are also updated to reflect the current state of the other tabs.
        """
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
        """
        Remove this tab from the copybox of all other tabs and from the
        list of tabs that are being synced. If the copybox of another
        tab is empty after removing this tab, hide the copybox.
        """
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

    def __init__(self, parent=None):
        """
        Initialize the dialog to generate parametric scans.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__('Scan', title='Scan Panel', apply=False,
                         reset=False, parent=parent)
        self.tab_class = ScanTab
        self.plotview_sort = True


class ScanTab(NXTab):

    def __init__(self, label, parent=None):

        """
        Initialize a ScanTab object.

        Parameters
        ----------
        label : str
            The title of the tab
        parent : QWidget, optional
            The parent of the tab
        """
        super().__init__(label, parent=parent)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        headers = ['Axis', 'Minimum', 'Maximum']
        width = [50, 100, 100]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            grid.addWidget(label, 0, column)
            grid.setColumnMinimumWidth(column, width[column])
            column += 1
        row = 0
        self.minbox = {}
        self.maxbox = {}
        for axis in range(self.plotview.ndim):
            row += 1
            self.minbox[axis] = NXSpinBox(self.set_limits)
            self.maxbox[axis] = NXSpinBox(self.set_limits)
            grid.addWidget(self.label(self.plotview.axis[axis].name), row, 0)
            grid.addWidget(self.minbox[axis], row, 1)
            grid.addWidget(self.maxbox[axis], row, 2)

        self.set_layout(
            grid, self.checkboxes(("hide", "Hide Limits", False)),
            self.textboxes(('Scan', '')),
            self.action_buttons(('Select Scan', self.select_scan),
                                ('Select Files', self.select_files)),
            self.action_buttons(('Plot', self.plot_scan),
                                ('Copy', self.copy_scan),
                                ('Save', self.save_scan)))
        self.checkbox["hide"].stateChanged.connect(self.hide_rectangle)
        self.file_box = None
        self.scan_files = None
        self.scan_values = None
        self.scan_data = None
        self.scan_root = None
        self.files = None
        self.initialize()
        self._rectangle = None

    def initialize(self):
        """
        Initialize the projection limits and copy widgets.

        This function is called when the dialog is first created and
        after the data has been changed. It sets the minimum and maximum
        limits to the centers of the data and sets the current limits to
        the current limits of the plot. The copy widgets are also
        updated to reflect the current state of the other tabs.
        """
        for axis in range(self.plotview.ndim):
            self.minbox[axis].data = self.maxbox[axis].data = \
                self.plotview.axis[axis].centers
            self.minbox[axis].setMaximum(self.minbox[axis].data.size-1)
            self.maxbox[axis].setMaximum(self.maxbox[axis].data.size-1)
            self.block_signals(True)
            self.minbox[axis].setValue(self.plotview.axis[axis].lo)
            self.maxbox[axis].setValue(self.plotview.axis[axis].hi)
            self.block_signals(False)

    def select_scan(self):
        """
        Set the scan axis of the dialog to the currently selected node.

        The currently selected node must be a scalar NXfield. If the
        selected node is not a scalar NXfield, a NeXusError is raised
        and reported.
        """
        scan_axis = self.treeview.node
        if not isinstance(scan_axis, NXfield):
            display_message("Scan Panel", "Scan axis must be a NXfield")
        elif scan_axis.shape != () and scan_axis.shape != (1,):
            display_message("Scan Panel", "Scan axis must be a scalar")
        else:
            self.textbox['Scan'].setText(self.treeview.node.nxpath)

    def select_files(self):
        """
        Create a dialog to select files to plot.

        The dialog will show a list of files with checkboxes. The list
        of files is determined by the data_path argument passed to the
        constructor. The list of files is filtered to only include files
        that have a scan axis with the scan_path argument. If no
        scan_path argument is provided, all files are included. The
        dialog also allows the user to select a prefix for the files.
        The selected files are returned as a list of (file name, scan
        value) tuples.
        """
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
            except Exception:
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
        """
        Select files in the dialog that start with the prefix in the
        'Prefix' field.
        """
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
        """
        Set the scan value of each file in the dialog to its position
        in the list, or clear the scan value if the file does not vary.
        """
        if self.scan_path:
            i = 0
            for f in self.files:
                if self.files[f].vary:
                    i += 1
                    self.files[f].value = i
                else:
                    self.files[f].value = ''

    def get_axes(self):
        """Return a list of NXfields containing the data axes."""
        return self.plotview.xtab.get_axes()

    def set_limits(self):
        """Plot the limits rectangle when the axis limits change."""
        self.scan_data = None
        self.draw_rectangle()

    def get_limits(self, axis=None):
        """
        Return the limits of the plot for the given axis.

        Parameters
        ----------
        axis : int or None
            The axis for which to return the limits. If None, return the
            limits for all axes.

        Returns
        -------
        limits : list of tuples of int
            The limits of the plot for the given axis or axes. Each
            tuple is a pair of start and stop indices.
        """
        def get_indices(minbox, maxbox):
            start, stop = minbox.index, maxbox.index+1
            if minbox.reversed:
                start, stop = len(maxbox.data)-stop, len(minbox.data)-start
            return start, stop
        if axis:
            return get_indices(self.minbox[axis], self.maxbox[axis])
        else:
            return [get_indices(self.minbox[axis], self.maxbox[axis])
                    for axis in range(self.plotview.ndim)]

    def get_slice(self):
        """
        Return a tuple of slice objects for the axes of the data.

        The slice objects are generated from the limits boxes. The
        start and stop indices of each slice are the start and stop
        values of the corresponding limits box, respectively.

        Returns
        -------
        slice : tuple of slice objects
            A tuple of slice objects for the axes of the data.
        """
        idx = self.get_limits()
        return tuple(slice(start, stop) for (start, stop) in idx)

    @property
    def data_path(self):
        """Return the path to the data to be plotted."""
        return self.plotview.data.nxpath

    @property
    def scan_path(self):
        """The path of the scan variable, as entered by the user."""
        return self.textbox['Scan'].text()

    @property
    def scan_variable(self):
        """The NXfield object associated with the scan variable."""
        if self.scan_path and self.scan_path in self.plotview.data.nxroot:
            return self.plotview.data.nxroot[self.scan_path]
        else:
            return None

    @property
    def scan_header(self):
        """The name of the scan variable, as entered by the user."""
        if self.scan_path and self.scan_path in self.plotview.data.nxroot:
            return (
                self.plotview.data.nxroot[self.scan_path].nxname.capitalize())
        else:
            return 'Variable'

    def choose_files(self):
        """
        Set the scan files and values.

        Raises
        ------
        NeXusError
            If the files have not been selected.
        """
        try:
            self.scan_files = [self.tree[self.files[f].name]
                               for f in self.files if self.files[f].vary]
            self.scan_values = [self.files[f].value for f in self.files
                                if self.files[f].vary]
            self.create_scan_data()
        except Exception:
            report_error("Choosing Scan Files", "Files not selected")

    def create_scan_data(self):
        """Create the consolidated scan data."""
        self.scan_data = nxconsolidate(self.scan_files, self.data_path,
                                       self.scan_path, idx=self.get_slice())
        try:
            if Path(self.scan_root.nxfilename).exists():
                Path(self.scan_root.nxfilename).unlink()
        except Exception:
            pass
        import tempfile
        with nxload(tempfile.mkstemp(suffix='.nxs')[1], mode='w') as root:
            root['data'] = self.scan_data
        self.scan_root = root

    def plot_scan(self):
        """
        Plot the scan data.

        This will plot the scan data using the selected options and
        append it to the current plot.

        Raises
        ------
        NeXusError
            If the data cannot be plotted.
        """
        if self.scan_data is None:
            self.create_scan_data()
        try:
            self.scanview.plot(self.scan_data)
            self.scanview.make_active()
            self.scanview.raise_()
        except NeXusError as error:
            report_error("Plotting Scan", error)

    def copy_scan(self):
        """
        Copy the scan data to the clipboard.

        This will copy the scan data to the clipboard so that it can be
        pasted into another application.

        Raises
        ------
        NeXusError
            If the data cannot be copied.
        """
        if self.scan_data is None:
            self.create_scan_data()
        try:
            self.mainwindow.copied_node = self.mainwindow.copy_node(
                self.scan_data)
        except NeXusError as error:
            report_error("Copying Scan", error)

    def save_scan(self):
        """
        Save the scan data to a file.

        This will save the scan data to a NeXus file using the standard
        NeXus file dialog.

        Raises
        ------
        NeXusError
            If the data cannot be saved.
        """
        if self.scan_data is None:
            self.create_scan_data()
        try:
            keep_data(self.scan_data)
        except NeXusError as error:
            report_error("Saving Scan", error)

    @property
    def scanview(self):
        """The plot view for the scan data."""
        if 'Scan' in self.plotviews:
            return self.plotviews['Scan']
        else:
            from .plotview import NXPlotView
            return NXPlotView('Scan')

    def block_signals(self, block=True):
        """
        Block signals from the limits boxes.

        Parameters
        ----------
        block : bool
            True to block signals, False to unblock signals
        """
        for axis in range(self.plotview.ndim):
            self.minbox[axis].blockSignals(block)
            self.maxbox[axis].blockSignals(block)

    @property
    def rectangle(self):
        """The rectangle defining the projection limits."""
        if self._rectangle not in self.plotview.ax.patches:
            self._rectangle = NXpolygon(self.get_rectangle(), closed=True,
                                        plotview=self.plotview).shape
            self._rectangle.set_edgecolor(self.plotview._gridcolor)
            self._rectangle.set_facecolor('none')
            self._rectangle.set_linestyle('dashed')
            self._rectangle.set_linewidth(2)
        return self._rectangle

    def get_rectangle(self):
        """
        Return the coordinates of the rectangle.

        The coordinates are returned as a list of four tuples, each
        tuple containing the x and y coordinates of a vertex of the
        rectangle. If the plot is skewed, the coordinates are
        transformed to the skewed coordinates.
        """
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
        """
        Redraw the rectangle in the plot based on the current limits.

        Notes
        -----
        The coordinates of the rectangle are obtained from the limits of
        the x and y axes. If the plot is skewed, the coordinates are
        transformed to the skewed coordinates.
        """
        self.rectangle.set_xy(self.get_rectangle())
        self.plotview.draw()

    def rectangle_visible(self):
        """
        Return True if the rectangle defining the projection limits
        should be visible.

        The rectangle is visible unless the 'Hide Limits' checkbox is
        checked.
        """
        return not self.checkbox["hide"].isChecked()

    def hide_rectangle(self):
        """
        Hide or show the rectangle defining the projection limits based
        on the 'Hide Limits' checkbox.

        If the checkbox is checked, hide the rectangle. Otherwise, show
        it.
        """
        if self.checkbox["hide"].isChecked():
            self.rectangle.set_visible(False)
        else:
            self.rectangle.set_visible(True)
        self.plotview.draw()

    def update(self):
        """
        Update the limits boxes and the rectangle in the plot based on
        the current limits of the axes.

        Notes
        -----
        If the limits of the x or y axes have changed, the limits boxes
        are updated to reflect the new limits. The rectangle is then
        redrawn based on the updated limits.
        """
        self.block_signals(True)
        for axis in range(self.plotview.ndim):
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

    def close(self):
        """
        Close the dialog.

        This will close the dialog and remove it from the list of
        dialogs. It will also close the file dialog if it is open.
        """
        try:
            if Path(self.scan_root.nxfilename).exists():
                Path(self.scan_root.nxfilename).unlink()
        except Exception:
            pass
        try:
            self.file_box.close()
        except Exception:
            pass
        try:
            if self._rectangle:
                self._rectangle.remove()
            self.plotview.draw()
        except Exception:
            pass
        super().close()


class ViewDialog(NXPanel):

    def __init__(self, parent=None):
        """
        Initialize the View Panel.

        The View Panel is initialized with the given parent and its
        tab class is set to ViewTab. The apply and reset flags are set to
        False.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the dialog. The default is None.
        """
        super().__init__('View', title='View Panel', apply=False, reset=False,
                         parent=parent)
        self.tab_class = ViewTab

    def activate(self, node):
        """
        Activate a tab showing the properties of a NeXus node.
        
        Parameters
        ----------
        node : NXobject
            The node to be displayed
        """
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

        """
        Initialize a ViewTab object.

        Parameters
        ----------
        label : str
            The title of the tab
        node : NXobject
            The NeXus node to be displayed
        parent : QWidget, optional
            The parent of the tab
        """
        super().__init__(label, parent=parent)

        self.node = node
        self.spinboxes = []

        layout = QtWidgets.QVBoxLayout()
        self.properties = GridParameters()

        self.properties.add('class', node.__class__.__name__, 'Class',
                            readonly=True)
        self.properties.add('name', node.nxname, 'Name', readonly=True)
        self.properties.add('path', node.nxpath, 'Path', readonly=True)
        if node.nxroot.nxfilename:
            self.properties.add('file', node.nxroot.nxfilename, 'File',
                                readonly=True)
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
            self.properties.add('target', node._target, target_path_label,
                                readonly=True)
            if node._filename:
                self.properties.add('linkfile', node._filename,
                                    target_file_label, readonly=True)
            elif node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
                self.properties.add('linkfile', node.nxfilename,
                                    target_file_label, readonly=True)
        elif isinstance(node, NXvirtualfield):
            self.properties.add('vpath', node._vpath, 'Virtual Path',
                                readonly=True)
            self.properties.add('vfiles', node._vfiles, 'Virtual Files',
                                readonly=True)
        elif node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
            self.properties.add('target', node.nxfilepath, 'Target Path',
                                readonly=True)
            self.properties.add('linkfile', node.nxfilename, target_file_label,
                                readonly=True)
        if node.nxfilemode:
            self.properties.add('filemode', node.nxfilemode, 'Mode',
                                readonly=True)
        if target_error:
            pass
        elif isinstance(node, NXfield) and node.shape is not None:
            if node.shape == () or node.shape == (1,):
                self.properties.add('value', str(node.nxvalue), 'Value',
                                    readonly=True)
            self.properties.add('dtype', node.dtype, 'Dtype', readonly=True)
            self.properties.add('shape', str(node.shape), 'Shape',
                                readonly=True)
            self.properties.add('maxshape', str(node.maxshape),
                                'Maximum Shape', readonly=True)
            self.properties.add('fillvalue', str(node.fillvalue), 'Fill Value',
                                readonly=True)
            self.properties.add('chunks', str(node.chunks), 'Chunk Size',
                                readonly=True)
            self.properties.add('compression', str(node.compression),
                                'Compression', readonly=True)
            self.properties.add('compression_opts', str(node.compression_opts),
                                'Compression Options', readonly=True)
            self.properties.add('shuffle', str(node.shuffle), 'Shuffle Filter',
                                readonly=True)
            self.properties.add('fletcher32', str(node.fletcher32),
                                'Fletcher32 Filter', readonly=True)
        elif isinstance(node, NXgroup):
            self.properties.add('entries', len(node.entries), 'No. of Entries',
                                readonly=True)
        layout.addLayout(self.properties.grid(header=False,
                                              title='Properties',
                                              width=200))
        if target_error:
            layout.addWidget(NXLabel(target_error))

        if node.attrs:
            self.attributes = GridParameters()
            for attr in node.attrs:
                self.attributes.add(attr, str(node.attrs[attr]), attr,
                                    readonly=True)
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
        """
        Create a table view for displaying the data in a NeXus field.

        If the data is more than two dimensions, add a row of spinboxes
        to allow the user to select the indices of the data to be
        displayed.
        """
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
        """
        Slot to be called when the user changes the values of the spin
        boxes used to select the data to be displayed in the table view.
        The selected data is passed to the table model, which updates
        the table view. The table view is then resized to fit the new
        data.
        """
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
        """Resizes the table view to fit the contents of the table."""
        self.table_view.resizeColumnsToContents()
        vwidth = self.table_view.verticalHeader().width()
        hwidth = self.table_view.horizontalHeader().length()
        self.table_view.setFixedWidth(vwidth + hwidth)
        vheight = self.table_view.verticalHeader().length()
        hheight = self.table_view.horizontalHeader().height()
        self.table_view.setFixedHeight(vheight + hheight)


class ViewTableModel(QtCore.QAbstractTableModel):

    def __init__(self, data, parent=None):
        """
        Constructor for ViewTableModel
        
        Parameters
        ----------
        data : array-like
            Data to be displayed in the table
        parent : QObject, optional
            Parent object
        
        Notes
        -----
        The data is reshaped to a 2D array if it is not already.
        The origin of the data is recorded and used to determine the
        table's row and column headers.
        """
        super().__init__(parent=parent)
        self._data = self.get_data(data)
        self.origin = [0, 0]

    def get_data(self, data):
        """
        Reshape the data to a 2D array if it is not already

        Parameters
        ----------
        data : array-like
            Data to be displayed in the table

        Returns
        -------
        reshaped_data : array-like
            Data reshaped to a 2D array

        Notes
        -----
        The number of rows and columns is stored in the instance
        variables self.rows and self.columns.
        """
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
        """Number of rows in the table"""
        return self.rows

    def columnCount(self, parent=None):
        """Number of columns in the table"""
        return self.columns

    def data(self, index, role):
        """
        Data to be displayed in the table

        Parameters
        ----------
        index : QModelIndex
            Index of the cell
        role : int
            Role of the data

        Returns
        -------
        data : str
            Data to be displayed in the table

        Notes
        -----
        The data is converted to a string, removing any square brackets
        from the start and end of the string. If the string is longer
        than 10 characters, it is truncated to 10 characters and an
        elipsis is appended. If the data cannot be converted to a float,
        the string is returned as is.
        """
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
        """
        Data to be displayed in the table header

        Parameters
        ----------
        position : int
            Index of the header element
        orientation : Qt.Orientation
            Orientation of the header
        role : int
            Role of the data

        Returns
        -------
        data : str
            Data to be displayed in the table header
        """
        if (orientation == QtCore.Qt.Horizontal and
                role == QtCore.Qt.DisplayRole):
            return str(self.origin[1] + range(10)[position])
        elif (orientation == QtCore.Qt.Vertical and
              role == QtCore.Qt.DisplayRole):
            return str(self.origin[0] + range(10)[position])
        return None

    def choose_data(self, data, origin):
        """
        Choose new data to be displayed in the table

        Parameters
        ----------
        data : array-like
            New data to be displayed in the table
        origin : list of int
            Origin of the new data

        Notes
        -----
        The table view will be updated to display the new data.
        """
        self.layoutAboutToBeChanged.emit()
        self._data = self.get_data(data)
        self.origin = origin
        self.layoutChanged.emit()
        self.headerDataChanged.emit(QtCore.Qt.Horizontal, 0,
                                    min(9, self.columns-1))
        self.headerDataChanged.emit(QtCore.Qt.Vertical, 0, min(9, self.rows-1))


class ValidateDialog(NXPanel):
    """Dialog to view a NeXus field"""

    def __init__(self, parent=None):
        """
        Initialize the dialog to view a NeXus field.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__('Validate', title='Validation Panel', apply=False,
                         reset=False, parent=parent)
        self.tab_class = ValidateTab

    def activate(self, node):
        """
        Activate a tab showing the results of NeXus validation of a NeXus node.

        Parameters
        ----------
        node : NXobject
            The node to be validated
        """
        label = node.nxroot.nxname + node.nxpath
        if label not in self.tabs:
            tab = ValidateTab(label, node, parent=self)
            self.add(label, tab, idx=self.idx(label))
        else:
            self.tab = label
        self.setVisible(True)
        self.raise_()
        self.activateWindow()


class ValidateTab(NXTab):

    def __init__(self, label, node, parent=None):

        """
        Initialize the dialog to view a NeXus field.

        Parameters
        ----------
        label : str
            The title of the tab
        node : NXobject
            The NeXus node to be validated
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(label, parent=parent)

        self.node = node

        from nexusformat.nexus.utils import get_definitions
        self.definitions = get_definitions(nxgetconfig('definitions'))
        self.definitions_box = self.directorybox('NeXus Definitions Directory',
                                                 self.choose_definitions,
                                                 suggestion=self.definitions)
        actions = self.action_buttons(
            ('Check Base Class', self.check),
            ('Validate Entry', self.validate),
            ('Inspect Base Class', self.inspect))
        for button in ['Validate Entry', 'Check Base Class',
                       'Inspect Base Class']:
            self.pushbutton[button].setCheckable(True)

        if self.node.nxclass == 'NXroot':
            entry = self.node.NXentry[0]
        elif self.node.nxclass in ['NXentry', 'NXsubentry']:
            entry = self.node
        else:
            entry = None
        if entry is not None:
            self.pushbutton['Validate Entry'].setVisible(True)
            self.application_box = self.filebox('Application Definition',
                                                self.choose_application)
            if 'definition' in entry:
                self.application = entry['definition'].nxvalue
                application_file = self.definitions.joinpath(
                    'applications', Path(self.application+'.nxdl.xml'))
                if application_file.is_file():
                    self.application = application_file
                    self.filename.setText(str(application_file))
                else:
                    self.filename.setText(self.application)
            else:
                self.application = None
        else:
            self.pushbutton['Validate Entry'].setVisible(False)
            self.application_box = None

        self.text_box = NXTextEdit()
        self.text_box.setMinimumWidth(800)
        self.text_box.setMinimumHeight(600)
        self.text_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.text_box.setReadOnly(True)
        radio_buttons = self.radiobuttons(('info', 'Info', False),
                                          ('warning', 'Warning', True),
                                          ('error', 'Error', False),
                                          slot=self.select_level)
        if entry is not None:
            self.set_layout(self.definitions_box, self.application_box,
                            actions, self.text_box, radio_buttons)
        else:
            self.set_layout(self.definitions_box, actions, self.text_box,
                            radio_buttons)
        full_path = self.node.nxroot.nxname + self.node.nxpath
        self.set_title(f"Validation Results for {full_path}")

    def choose_definitions(self):
        """
        Opens a file dialog and sets the definitions directory text box
        to the chosen path. Checks that the directory contains a
        base_classes directory and if it does, sets the definitions to
        this new directory and reloads the application definition and
        runs the currently selected validation action.
        """
        dirname = str(self.definitions)
        dirname = QtWidgets.QFileDialog.getExistingDirectory(
            self, 'Choose Definitions Directory', dirname)
        dirname = Path(dirname)
        if dirname.exists():
            if dirname.joinpath('base_classes').exists():
                self.definitions = dirname
                nxsetconfig(definitions=str(self.definitions))
                self.directoryname.setText(str(dirname))
                if self.application_box is not None:
                    application_name = Path(self.filename.text()).name
                    application_file = self.definitions.joinpath(
                        'applications', Path(application_name))
                    if application_file.is_file():
                        self.application = application_file
                        self.filename.setText(str(application_file))
                if self.pushbutton['Check Base Class'].isChecked():
                    self.check()
                elif self.pushbutton['Validate Entry'].isChecked():
                    self.validate()
                elif self.pushbutton['Inspect Base Class'].isChecked():
                    self.inspect()
            else:
                display_message("Definitions directory is not valid")

    def choose_application(self):
        """
        Opens a file dialog and sets the application definition text box
        to the chosen path. Checks that the file is an application
        definition and if it is, sets the application definition to
        this new file and reloads the application definition and runs
        the currently selected validation action.
        """
        applications_directory = self.definitions.joinpath('applications')
        dirname = str(applications_directory)
        application = Path(getOpenFileName(self, 'Open Application', dirname))
        if application.is_file():
            self.application = application
            self.filename.setText(str(application))
            if self.pushbutton['Validate Entry'].isChecked():
                self.validate()

    @property
    def log_level(self):
        """The current log level ('info', 'warning', or 'error')"""
        if self.radiobutton['info'].isChecked():
            return 'info'
        elif self.radiobutton['warning'].isChecked():
            return 'warning'
        else:
            return 'error'

    def validate(self):
        """
        Validates the NeXus entry against the given application
        definition and definitions. Calls self.show_log() to show the
        validation results and then sets the Validate Entry button to
        True and the Check Base Class and Inspect Base Class buttons to
        False.
        """
        try:
            self.node.validate(level=self.log_level,
                               application=self.application,
                               definitions=self.definitions)
            self.show_log()
            for button in ['Check Base Class', 'Inspect Base Class']:
                self.pushbutton[button].setChecked(False)
        except NeXusError as error:
            report_error("Validating Entry", error)
            self.pushbutton['Validate Entry'].setChecked(False)

    def check(self):
        """
        Checks the NeXus group for compliance with the NeXus base
        classes. Calls self.show_log() to show the validation results
        and then sets the Check Base Class button to True and the
        Validate Entry and Inspect Base Class buttons to False.
        """
        self.node.check(level=self.log_level, definitions=self.definitions)
        self.show_log()
        self.pushbutton['Check Base Class'].setChecked(True)
        for button in ['Validate Entry', 'Inspect Base Class']:
            self.pushbutton[button].setChecked(False)

    def inspect(self):
        """
        Inspects the NeXus base class of the entry. Calls
        self.show_log() to show the inspection results and then sets the
        Inspect Base Class button to True and the Validate Entry and
        Check Base Class buttons to False.
        """
        self.node.inspect(definitions=self.definitions)
        self.show_log()
        self.pushbutton['Inspect Base Class'].setChecked(True)
        for button in ['Validate Entry', 'Check Base Class']:
            self.pushbutton[button].setChecked(False)

    def select_level(self):
        """
        Slot for the level radio buttons. Runs the validation action
        that is currently selected by the user.
        """
        if self.pushbutton['Validate Entry'].isChecked():
            self.validate()
        elif self.pushbutton['Check Base Class'].isChecked():
            self.check()
        elif self.pushbutton['Inspect Base Class'].isChecked():
            self.inspect()

    def show_log(self):
        """
        Shows the validation log. Called by the validation actions to
        show the results of the validation action.
        """
        handler = logging.getLogger('NXValidate').handlers[0]
        self.text_box.setText(convertHTML(handler.flush()))
        self.setVisible(True)
        self.raise_()
        self.activateWindow()


class EditDialog(NXPanel):

    def __init__(self, parent=None):
        """Initialize the Edit Panel.

        Parameters
        ----------
        parent : QWidget, optional
            The parent of the dialog. The default is None.
        """
        super().__init__('Edit', title='Edit Panel', apply=True, reset=False,
                         parent=parent)
        self.tab_class = EditTab

    def activate(self, node):
        """
        Activate a tab to edit the contents of a NeXus group.
        
        Parameters
        ----------
        node : NXobject
            The node to be edited
        """
        label = node.nxroot.nxname + node.nxpath
        if label not in self.tabs:
            tab = EditTab(label, node, parent=self)
            self.add(label, tab, idx=self.idx(label))
        else:
            self.tab = label
        self.setVisible(True)
        self.raise_()
        self.activateWindow()


class EditTab(NXTab):

    def __init__(self, label, node, parent=None):

        """
        Initialize the tab to edit the contents of a NeXus group. Only
        scalar fields are editable in this dialog.

        Parameters
        ----------
        label : str
            The title of the tab
        node : NXobject
            The NeXus node to be edited
        parent : QWidget, optional
            The parent of the tab
        """
        super().__init__(label, parent=parent)

        self.group = node
        if not isinstance(self.group, NXgroup):
            raise NeXusError('The node must be a NeXus group')

        field_list = [f for f in self.group.NXfield if f.ndim == 0]
        if len(field_list) == 0:
            raise NeXusError(f"No scalar fields found in {self.group.nxpath}")

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        headers = ['Field', 'Value', '']
        width = [100, 100, 20]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.grid.addWidget(label, 0, column)
            self.grid.setColumnMinimumWidth(column, width[column])
            column += 1

        row = 1
        for field in field_list:
            self.grid.addWidget(NXLabel(field.nxname), row, 0,
                                QtCore.Qt.AlignTop)
            if field.is_string():
                self.grid.addWidget(NXTextEdit(field.nxvalue, autosize=True),
                                    row, 1, QtCore.Qt.AlignTop)
            else:
                self.grid.addWidget(NXTextEdit(field.nxvalue, align='right',
                                               autosize=True),
                                    row, 1)
                self.grid.addWidget(NXLabel(field.nxunits), row, 2)
            row += 1
        self.grid.setContentsMargins(10, 10, 40, 10)
        self.grid.setSpacing(5)
        if len(field_list) > 10:
            self.scroll_area = NXScrollArea(self.grid, height=800)
            self.scroll_area.setMinimumHeight(200)
            self.set_layout(self.scroll_area)
        else:
            self.set_layout(self.grid)
            self.scroll_area = None
        self.set_title(f'Edit {self.group.nxpath}')

    def resize(self):
        """Update the size of the scroll area and its contents."""
        super().resize()
        if self.scroll_area is not None:
            self.scroll_area.widget().updateGeometry()
            self.scroll_area.updateGeometry()
            self.scroll_area.widget().adjustSize()
            self.scroll_area.adjustSize()

    def apply(self):
        if not self.group.is_modifiable():
            self.display_message('Group is read-only')
            return
        row = 1
        for row in range(1, self.grid.rowCount()):
            field_name = self.grid.itemAtPosition(row, 0).widget().text()
            field = self.group[field_name]
            if field.is_string():
                value = self.grid.itemAtPosition(row, 1).widget().toPlainText()
                if field.nxvalue != value.rstrip():
                    field.nxdata = value.rstrip()
            else:
                value = self.grid.itemAtPosition(row, 1).widget().toPlainText()
                try:
                    value = field.dtype.type(value)
                except ValueError:
                    self.display_message(f'Invalid value for {field.nxname}')
                    return
                if not np.isclose(field.nxvalue, value):
                    field.nxdata = value            


class GroupDialog(NXDialog):

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)
        """
        Initialize the dialog to add a NeXus group.

        Parameters
        ----------
        node : NXobject
            The NeXus node to which a NeXus group will be added.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """

        self.node = node

        self.setWindowTitle("Add NeXus Data")

        self.set_layout(self.define_grid(), self.close_buttons())
        self.set_title("Add NeXus Group")

    def define_grid(self):
        """Defines a grid to set group names and classes.

        Parameters
        ----------
        class_name : str
            The class of the NeXus group to be added.

        Returns
        -------
        grid : QGridLayout
            The grid allowing the name and class of the group to be set.
        """
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        self.standard_groups = self.node.valid_groups()
        valid_groups = {}
        for group in self.standard_groups:
            if 'doc' in self.standard_groups[group]:
                valid_groups[group] = wrap(self.standard_groups[group]['doc'],
                                           width=60, compress=True)
            else:
                valid_groups[group] = ""
        name_label = NXLabel("Name:")
        self.name_box = NXLineEdit()
        group_label = NXLabel("Group Class:")
        self.group_box = NXComboBox(self.select_group, valid_groups)
        self.group_box.insert(len(valid_groups), "")
        other_groups = sorted([g for g in self.mainwindow.nxclasses
                               if g not in self.standard_groups])
        self.group_box.add(*other_groups)
        grid.addWidget(group_label, 0, 0)
        grid.addWidget(self.group_box, 0, 1)
        grid.addWidget(name_label, 1, 0)
        grid.addWidget(self.name_box, 1, 1)
        self.select_group()
        grid.setColumnMinimumWidth(1, 200)
        return grid

    def select_group(self):
        """Set the name to correspond to the selected group."""
        self.set_name(self.group_box.selected)

    def get_name(self):
        """Return the text of the name box."""
        return self.name_box.text().strip()

    def set_name(self, name):
        """
        Set the name of the group.
        
        This is called when a value of the group box is changed. If the
        name is a base class, the leading "NX" is stripped. If it is a name
        defined by the NXDL file, the group class is updated to match.
        """
        if (name in self.standard_groups and 
                '@type' in self.standard_groups[name]):
            self.group_box.setCurrentText(self.standard_groups[name]['@type'])
        else:
            name = name[2:]
        self.name_box.setText(name)

    def accept(self):
        """Add a new NeXus group to the tree."""
        name = self.get_name()
        nxclass = self.group_box.selected
        try:
            if name:
                if name in self.node:
                    raise NeXusError(f"Group '{name}' already exists in '"
                                     f"{self.node.nxpath}'")
            else:
                raise NeXusError("Group name is empty")
            self.node[name] = NXgroup(nxclass=nxclass)
            logging.info(f"'{self.node[name]}' added to '{self.node.nxpath}'")
            super().accept()
        except NeXusError as error:
            report_error("Adding Group", error)


class FieldDialog(NXDialog):

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)
        """
        Initialize the dialog to add a NeXus field.

        Parameters
        ----------
        node : NXobject
            The NeXus node to which a NeXus field will be added.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """

        self.node = node

        self.setWindowTitle("Add NeXus Data")

        self.set_layout(self.define_grid(), self.close_buttons(save=True))
        self.set_title("Add NeXus Field")

    def define_grid(self):
        """
        Defines a grid to set field names, values, units, and datatypes.

        Returns
        -------
        grid : QGridLayout
            The grid of entry fields for adding a NeXus field.
        """
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        self.standard_fields = self.node.valid_fields()
        valid_fields = {}
        for field in self.standard_fields:
            if 'doc' in self.standard_fields[field]:
                valid_fields[field] = wrap(self.standard_fields[field]['doc'],
                                           width=60, compress=True)
            else:
                valid_fields[field] = ""
        name_label = NXLabel("Name:")
        self.name_box = NXLineEdit()
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        self.field_box = NXComboBox(self.select_field, valid_fields)
        if len(valid_fields) > 0:
            grid.addWidget(self.field_box, 0, 2)
        value_label = NXLabel("Value:")
        self.value_box = NXLineEdit()
        self.enumeration_box = NXComboBox(self.select_enumeration)
        self.enumeration_box.setVisible(False)
        grid.addWidget(value_label, 1, 0)
        grid.addWidget(self.value_box, 1, 1)
        grid.addWidget(self.enumeration_box, 1, 2)
        type_label = NXLabel("Datatype:")
        self.type_box = NXComboBox(items=all_dtypes())
        grid.addWidget(type_label, 2, 0)
        grid.addWidget(self.type_box, 2, 1)
        units_label = NXLabel("Units:")
        self.units_box = NXLineEdit()
        grid.addWidget(units_label, 3, 0)
        grid.addWidget(self.units_box, 3, 1)
        longname_label = NXLabel("Long Name:")
        self.longname_box = NXLineEdit()
        grid.addWidget(longname_label, 4, 0)
        grid.addWidget(self.longname_box, 4, 1)
        grid.setColumnMinimumWidth(1, 200)
        if len(valid_fields) > 0:
            self.select_field()
        return grid

    def select_field(self):
        """Set the name to the selected item in the field box."""
        field_name = self.field_box.selected
        self.set_name(field_name)
        self.type_box.clear()
        if field_name in self.standard_fields:
            if "@type" in self.standard_fields[field_name]:
                valid_dtypes = map_dtype(
                    self.standard_fields[field_name]["@type"])
            else:
                valid_dtypes = map_dtype("NX_CHAR")
            self.type_box.add(*valid_dtypes)
            self.type_box.insert(len(valid_dtypes), "")
            other_dtypes = [dt for dt in all_dtypes()
                            if dt not in valid_dtypes]
            self.type_box.add(*other_dtypes)
            if "enumeration" in self.standard_fields[field_name]:
                self.enumeration_box.clear()
                self.enumeration_box.add(
                    *self.standard_fields[field_name]["enumeration"])
                self.enumeration_box.setVisible(True)
                self.select_enumeration()
            else:
                self.enumeration_box.setVisible(False)
                self.value_box.setText("")
        else:
            self.type_box.add(*all_dtypes())
            self.enumeration_box.setVisible(False)

    def select_enumeration(self):
        """Set the value to the selected item in the enumeration box."""
        self.value_box.setText(self.enumeration_box.selected)

    def get_name(self):
        """Return the text of the name box."""
        return self.name_box.text().strip()

    def set_name(self, name):
        """Set the name to the field selected in the dropdown menu."""
        self.name_box.setText(name)

    def get_value(self):
        """
        Return the value of the text box as a python object.
        
        If the value is empty, return None. If the value is a string,
        return the string. If the value is a number, return the number
        as a python object. If the value is a NumPy expression, return
        the result of the expression. If the value can not be
        interpreted as a python object, return the value as a string.
        """
        value = self.value_box.text()
        if value:
            dtype = self.get_type()
            if dtype == "char":
                return value
            else:
                try:
                    return eval(value, {"__builtins__": {}},
                                self.mainwindow.user_ns)
                except Exception:
                    return value
        else:
            return None

    def get_type(self):
        """Return the type of the object as a NumPy dtype."""
        return np.dtype(self.type_box.currentText())

    def get_units(self):
        """Return the text of the units attribute."""
        return self.units_box.text().strip()

    def get_longname(self):
        """Return the text of the long name attribute."""
        return self.longname_box.text().strip()

    def accept(self):
        """Add a new NeXus field to the tree."""
        name = self.get_name()
        value = self.get_value()
        dtype = self.get_type()
        units = self.get_units()
        longname = self.get_longname()
        try:
            if name:
                if name in self.node:
                    raise NeXusError(f"Field '{name}' already exists in "
                                     f"'{self.node.nxpath}'")
                if value:
                    field = NXfield(value, dtype=dtype)
                    self.node[name] = field
                    logging.info(f"'{name}' added to '{self.node.nxpath}'")
                else:
                    raise NeXusError("Field value is empty")
                if units:
                    self.node[name].attrs['units'] = units
                if longname:
                    self.node[name].attrs['long_name'] = longname
                super().accept()
            else:
                raise NeXusError("Field name is empty")
        except NeXusError as error:
            report_error("Adding Field", error)


class AttributeDialog(NXDialog):

    def __init__(self, node, parent=None):

        super().__init__(parent=parent)
        """
        Initialize the dialog to add a NeXus attribute.

        Parameters
        ----------
        node : NXobject
            The NeXus node to which a NeXus attribute will be added.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """

        self.node = node

        self.setWindowTitle("Add NeXus Attribute")

        self.set_layout(self.define_grid(), self.close_buttons(save=True))
        self.set_title("Add NeXus Attribute")

    def define_grid(self):
        """
        Defines a grid to set attribute name and value, and datatype.

        Returns
        -------
        grid : QGridLayout
            The grid of entry fields for adding a NeXus field.
        """
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)

        self.standard_attributes = self.node.valid_attributes()
        valid_attributes = {}
        for attribute in self.standard_attributes:
            if 'doc' in self.standard_attributes[attribute]:
                valid_attributes[attribute] = wrap(
                    self.standard_attributes[attribute]['doc'],
                    width=60, compress=True)
            else:
                valid_attributes[attribute] = ""
        name_label = NXLabel("Name:")
        self.name_box = NXLineEdit()
        grid.addWidget(name_label, 0, 0)
        grid.addWidget(self.name_box, 0, 1)
        self.attr_box = NXComboBox(self.select_attribute, valid_attributes)
        if len(valid_attributes) > 0:
            grid.addWidget(self.attr_box, 0, 2)
        value_label = NXLabel("Value:")
        self.value_box = NXLineEdit()
        self.enumeration_box = NXComboBox(self.select_enumeration)
        self.enumeration_box.setVisible(False)
        grid.addWidget(value_label, 1, 0)
        grid.addWidget(self.value_box, 1, 1)
        grid.addWidget(self.enumeration_box, 1, 2)
        type_label = NXLabel("Datatype:")
        self.type_box = NXComboBox(items=all_dtypes())
        grid.addWidget(type_label, 2, 0)
        grid.addWidget(self.type_box, 2, 1)
        grid.setColumnMinimumWidth(1, 200)
        if len(valid_attributes) > 0:
            self.select_attribute()
        return grid

    def select_attribute(self):
        """Set the name to the selected item in the attribute box."""
        attribute_name = self.attr_box.selected
        self.set_name(attribute_name)
        self.type_box.clear()
        if attribute_name in self.standard_attributes:
            if "@type" in self.standard_attributes[attribute_name]:
                valid_dtypes = map_dtype(
                    self.standard_attributes[attribute_name]["@type"])
            else:
                valid_dtypes = map_dtype("NX_CHAR")
            self.type_box.add(*valid_dtypes)
            self.type_box.insert(len(valid_dtypes), "")
            other_dtypes = [dt for dt in all_dtypes()
                            if dt not in valid_dtypes]
            self.type_box.add(*other_dtypes)
            if "enumeration" in self.standard_attributes[attribute_name]:
                self.enumeration_box.clear()
                self.enumeration_box.add(
                    *self.standard_attributes[attribute_name]["enumeration"])
                self.enumeration_box.setVisible(True)
                if attribute_name not in self.node.attrs:
                    self.select_enumeration()
            else:
                self.enumeration_box.setVisible(False)
                self.value_box.setText("")
        else:
            self.type_box.add(*all_dtypes())
            self.enumeration_box.setVisible(False)
        if attribute_name in self.node.attrs:
            self.value_box.setText(self.node.attrs[attribute_name])

    def select_enumeration(self):
        """Set the value to the selected item in the enumeration box."""
        self.value_box.setText(self.enumeration_box.selected)

    def get_name(self):
        """Return the text of the name box."""
        return self.name_box.text().strip()

    def set_name(self, name):
        """Set the name to the field selected in the dropdown menu."""
        self.name_box.setText(name)

    def get_value(self):
        """
        Return the value of the text box as a python object.
        
        If the value is empty, return None. If the value is a string,
        return the string. If the value is a number, return the number
        as a python object. If the value is a NumPy expression, return
        the result of the expression. If the value can not be
        interpreted as a python object, return the value as a string.
        """
        value = self.value_box.text()
        if value:
            dtype = self.get_type()
            if dtype == "char":
                return value
            else:
                try:
                    return eval(value, {"__builtins__": {}},
                                self.mainwindow.user_ns)
                except Exception:
                    return value
        else:
            return None

    def get_type(self):
        """Return the type of the object as a NumPy dtype."""
        return np.dtype(self.type_box.currentText())

    def accept(self):
        """Add a new NeXus field to the tree."""
        name = self.get_name()
        value = self.get_value()
        dtype = self.get_type()
        try:
            if name:
                if name in self.node.attrs:
                    if value == self.node.attrs[name]:
                        display_message("Adding Attribute",
                                        f"Value of attribute '{name}' in "
                                        f"'{self.node.nxpath}' is unchanged")
                        super().accept()
                        return
                    elif not self.confirm_action(
                            f"Overwrite existing attribute '{name}'?",
                            f"Current value: {self.node.attrs[name]}"):
                        return
                if value:
                    attribute = NXattr(value, dtype=dtype)
                    self.node.attrs[name] = attribute
                    logging.info(
                        f"Attribute '{name}' added to '{self.node.nxpath}'")
                    super().accept()
                else:
                    raise NeXusError("Attribute value is empty")
            else:
                raise NeXusError("Attribute name is empty")
        except NeXusError as error:
            report_error("Adding Attribute", error)


class RenameDialog(NXDialog):

    def __init__(self, node, parent=None):

        """
        Initialize the dialog to rename a NeXus field or attribute.

        The dialog is initialized with a single line edit box and a
        button labeled "Rename". The button is connected to the rename
        slot, which changes the name of the given node to the text in
        the box and then closes the dialog.

        Parameters
        ----------
        node : NXobject
            The NeXus field or attribute to be renamed.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(parent=parent)

        self.node = node

        self.setWindowTitle("Rename NeXus data")

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.define_grid())
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)

    def define_grid(self):
        """
        Defines a grid of entry fields for renaming a NeXus field or
        attribute.

        The grid is defined based on the class of the NeXus field or
        attribute. For a NeXus group, the grid includes a combo box to
        select the group class and a line edit box to enter the new name
        of the group. For a NeXus field or attribute, the grid includes
        a combo box to select the field name and a line edit box to
        enter the new name of the field or attribute.

        Returns
        -------
        grid : QGridLayout
            The grid of entry fields for renaming a NeXus field or
            attribute.
        """
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
            standard_groups = self.node.nxgroup.valid_groups()
            for name in standard_groups:
                self.combo_box.addItem(name)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in self.mainwindow.nxclasses
                                   if g not in standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
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
                fields = self.node.nxgroup.valid_fields()
                for name in fields:
                    self.combo_box.addItem(name)
                if self.node.nxname in fields:
                    self.combo_box.setCurrentIndex(
                        self.combo_box.findText(self.node.nxname))
                else:
                    self.name_box.setText(self.node.nxname)
                grid.addWidget(self.combo_box, 0, 2)
        grid.setColumnMinimumWidth(1, 200)
        return grid

    def get_name(self):
        """Returns the name of the object to be renamed."""
        return self.name_box.text()

    def set_name(self):
        """Sets the name of the object to be renamed."""
        self.name_box.setText(self.combo_box.currentText())

    def get_class(self):
        """Returns the class of the object to be renamed."""
        return self.combo_box.currentText()

    def accept(self):
        """
        Renames the node, and if the node is a group, changes its class.

        The node is renamed to the name in the name box. If the node is
        a group, its class is changed to the class selected in the
        combo box. The dialog is then closed.
        """
        name = self.get_name()
        if name and name != self.node.nxname:
            self.node.rename(name)
        if isinstance(self.node, NXgroup):
            if self.combo_box is not None:
                self.node.nxclass = self.get_class()
        super().accept()


class PasteDialog(NXDialog):

    def __init__(self, node, link=False, parent=None):

        """
        Initialize the dialog to paste a node.

        The dialog is initialized with the pasted node's name and
        a checkbox to link the pasted node to the original node.

        Parameters
        ----------
        node : NXobject
            The parent node of the pasted node.
        link : bool, optional
            Whether to link the pasted node to the original node, by
            default False.
        parent : QWidget, optional
            The parent window of the dialog, by default None.
        """
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
        """
        Pasts the node into the given node.

        The pasted node is inserted into the given node with the name
        given in the name box. If the link checkbox is checked, the
        pasted node is pasted as a link to the original node. The
        dialog is then closed.

        If the node is a group, the pasted node is added to the group.
        If the node is a field, the pasted node is added to the
        parent group of the field.

        Parameters
        ----------
        node : NXobject
            The node into which the pasted node is to be inserted.
        """
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

    def __init__(self, node, parent=None):

        """
        Initialize the dialog to choose a signal from a group.

        Parameters
        ----------
        node : NXfield or NXgroup
            The NeXus field or group from which to choose a signal.
        parent : QWidget, optional
            The parent window of the dialog, by default None.
        """
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
        """ The selected signal. """
        return self.group[self.signal_combo.currentText()]

    @property
    def ndim(self):
        """ The number of dimensions of the selected signal. """
        return len(self.signal.shape)

    def choose_signal(self):
        """
        Set up the axis boxes when a new signal is chosen.

        This will create new axis boxes for each axis of the signal and
        remove any remaining boxes for the old signal.
        """
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
        """
        Create a dropdown box for selecting an axis.

        This will create a dropdown box of all the NXfields in the same
        group as the selected signal. The box will be initialized to the
        default axis if it is among the available options.

        Parameters
        ----------
        axis : int
            The axis for which to create the dropdown box.

        Returns
        -------
        box : NXComboBox
            The created dropdown box.
        """
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
        """
        Check if the selected axes are valid.

        This function is connected to the currentIndexChanged signal of
        each axis box. It checks if the selected axes are valid by
        checking if there are any duplicate axes selected. If there are,
        it displays a message box with an error message.
        """
        axes = [self.axis_boxes[axis].currentText()
                for axis in range(self.ndim)]
        axes = [axis_name for axis_name in axes if axis_name != 'None']
        if len(set(axes)) < len(axes):
            display_message("Cannot have duplicate axes")

    def remove_axis(self, axis):
        """
        Remove an axis box from the grid layout.

        Parameters
        ----------
        axis : int
            The axis for which to remove the dropdown box.
        """
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
        """
        Check if a node can be used as an axis for a signal.

        The node must be a one-dimensional field with a length that
        matches the length of the signal in the given axis. If the
        node is a zero-dimensional field, it is also accepted.

        Parameters
        ----------
        node : NXfield or NXgroup
            The node to check.
        axis : int
            The axis for which to check the node.

        Returns
        -------
        result : bool
            True if the node can be used as an axis, False otherwise.
        """
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
        """
        Return the axis for the given axis number.

        Parameters
        ----------
        axis : int
            The axis number.

        Returns
        -------
        axis : NXfield or None
            The axis or None if the selected axis is 'None'.
        """
        axis_name = self.axis_boxes[axis].currentText()
        if axis_name == 'None':
            return None
        else:
            return self.group[axis_name]

    def get_axes(self):
        """
        Return a list of NXfields containing the selected axes.

        The axes are determined from the values in the axis boxes. If
        the selected axis is 'None', None is returned for that axis.
        Otherwise, the selected NXfield is returned with its values and
        attributes.

        Returns
        -------
        axes : list of NXfield
            The axes.
        """
        return [self.get_axis(axis) for axis in range(self.ndim)]

    def accept(self):
        """
        Set the signal and axes for the group.

        Set the signal and axes for the group according to the values in
        the signal and axis boxes. If the selected axes are invalid
        (e.g. duplicate axes are selected), a NeXusError is raised and
        reported.

        Otherwise, the signal and axes are set and the dialog is closed
        with accept().
        """
        try:
            self.group.nxsignal = self.signal
            self.group.nxaxes = self.get_axes()
            super().accept()
        except NeXusError as error:
            report_error("Setting signal", error)
            super().reject()


class LogDialog(NXDialog):

    def __init__(self, parent=None):

        """
        Initialize the dialog to display the NeXpy log file.

        The dialog shows the contents of the NeXpy log file in a text
        box. The file can be selected from a drop down box. The dialog
        also has an 'Open NeXpy Issue' button that opens the NeXpy
        issues page on GitHub.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(parent=parent)

        self.log_directory = self.mainwindow.nexpy_dir

        self.text_box = NXTextEdit()
        self.text_box.setMinimumWidth(800)
        self.text_box.setMinimumHeight(600)
        self.text_box.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.text_box.setReadOnly(True)

        self.switch_box = NXCheckBox('Switch Light/Dark Mode',
                                     self.switch_mode)
        self.file_combo = NXComboBox(self.show_log)
        for file_name in self.get_filesindirectory(
                'nexpy', extension='.log*', directory=self.log_directory):
            self.file_combo.add(file_name.name)
        self.file_combo.select('nexpy.log')
        self.issue_button = NXPushButton('Open NeXpy Issue', self.open_issue)
        footer_layout = self.make_layout(self.switch_box, 'stretch',
                                         self.file_combo, 'stretch',
                                         self.issue_button,
                                         self.close_buttons(close=True),
                                         align='justified')
        self.set_layout(self.search_layout(self.text_box, 'Search Log...'),
                        self.text_box, footer_layout)

        self.show_log()

    @property
    def file_name(self):
        """Return the full path to the selected log file"""
        return self.log_directory / self.file_combo.currentText()

    def open_issue(self):
        """Open the NeXpy issues page on GitHub in a browser."""
        import webbrowser
        url = "https://github.com/nexpy/nexpy/issues"
        webbrowser.open(url, new=1, autoraise=True)

    def mouseReleaseEvent(self, event):
        """Show the log file when the dialog is clicked"""
        self.show_log()

    def show_log(self):
        """
        Show the selected log file in the dialog.

        Format the log file, make the dialog visible, raise it to the
        top of the window stack, and give it focus.
        """
        self.format_log()
        self.text_box.verticalScrollBar().setValue(
            self.text_box.verticalScrollBar().maximum())
        self.setVisible(True)
        self.raise_()
        self.activateWindow()

    def format_log(self):
        """
        Format the selected log file and show it in the dialog.

        This method reads the log file, formats it as HTML, and sets the
        text box to show the formatted log. The vertical scrollbar is
        set to the bottom of the text to show the most recent log
        messages. The window title is also set to the name of the log
        file.
        """
        switch = self.switch_box.isChecked()
        with open(self.file_name, 'r') as f:
            self.text_box.setText(convertHTML(f.read(), switch=switch))
        self.setWindowTitle(f"Log File: {self.file_name}")

    def switch_mode(self):
        """
        Switch the log file between light and dark mode.

        This method is called when the switch box is checked. It
        formats the log file and shows it in the dialog.
        """
        scroll_position = self.text_box.verticalScrollBar().value()
        self.format_log()
        self.text_box.verticalScrollBar().setValue(scroll_position)

    def reject(self):
        """
        Close the dialog and remove the reference to it from the main
        window.
        """
        super().reject()
        self.mainwindow.log_window = None


class UnlockDialog(NXDialog):

    def __init__(self, node, parent=None):

        """
        Initialize the dialog to unlock a file.

        The dialog is initialized with a label describing the action,
        a checkbox to backup the file, and a button to unlock the file.
        The checkbox is checked by default if the file is smaller than
        10MB.

        Parameters
        ----------
        node : NXroot
            The root of the NeXus tree.
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(parent=parent)

        self.setWindowTitle("Unlock File")
        self.node = node

        file_size = Path(self.node.nxfilename).stat().st_size
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
        """
        Unlock the file.

        If the checkbox is checked, the file is backed up to
        the backup directory before unlocking. The backup file
        name is stored in the settings under 'backups' and the
        current session is set to the backup file name.

        If the file is not backed up, the file is unlocked
        without saving the backup file name.

        If there is an error, an error message is displayed.
        """
        try:
            if self.checkbox['backup'].isChecked():
                dir = self.mainwindow.backup_dir / timestamp()
                dir.mkdir()
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

    def __init__(self, parent=None):

        """
        Initialize the dialog to manage backups.

        The dialog shows a list of backups, with the date, name and size
        of each backup. The user can check the boxes of the backups to
        be restored or deleted.

        The dialog contains buttons to restore or delete the selected
        backups.

        The dialog is closed by clicking the 'Close' button.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(parent=parent, default=True)

        self.backup_dir = self.mainwindow.backup_dir
        self.mainwindow.settings.read(self.mainwindow.settings_file)
        options = reversed(self.mainwindow.settings.options('backups'))
        backups = []
        for backup in options:
            backup_path = Path(backup).resolve()
            if backup_path.exists() and (
                    self.backup_dir in backup_path.parents):
                backups.append(backup_path)
            else:
                self.mainwindow.settings.remove_option('backups', backup)
        self.mainwindow.settings.save()
        self.scroll_area = NXScrollArea()
        items = []
        for backup in backups:
            date = format_timestamp(backup.parent.name)
            name = self.get_name(backup)
            size = backup.stat().st_size
            items.append(
                self.checkboxes((str(backup),
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
        """Get the name of the backup file."""
        name, ext = Path(backup).stem, Path(backup).suffix
        return name[:name.find('_backup')] + ext

    def restore(self):
        """
        Restore the selected backup files.

        The selected backup files are restored and loaded into the
        tree view. The backup files are disabled in the dialog and
        the display message is updated to indicate that the files
        have been opened and should be saved for future use.
        """
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
        """
        Delete the selected backup files.

        The selected backup files are deleted and removed from the list
        of backups. The display message is updated to indicate that the
        files have been deleted.
        """
        backups = []
        for backup in self.checkbox:
            if self.checkbox[backup].isChecked():
                backups.append(backup)
        if backups:
            if self.confirm_action("Delete selected backups?",
                                   "\n".join(backups)):
                for backup in backups:
                    backup_path = Path(backup).resolve()
                    if backup_path.exists() and (
                            self.backup_dir in backup_path.parents):
                        backup_path.unlink()
                        backup_path.parent.rmdir()
                        self.mainwindow.settings.remove_option('backups',
                                                               str(backup))
                    self.checkbox[backup].setChecked(False)
                    self.checkbox[backup].setDisabled(True)
                self.mainwindow.settings.save()


class ManagePluginsDialog(NXDialog):

    def __init__(self, parent=None):

        """
        Initialize the dialog to manage plugins.

        The dialog is initialized with a grid of widgets showing the
        package name, menu name, and order of each plugin. The order
        can be set to either a number or 'Disabled'. The settings are
        saved when the dialog is closed.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None
        """
        super().__init__(parent=parent)

        self.plugins = self.mainwindow.plugins.copy()

        self.settings = self.mainwindow.settings
        for plugin in [p for p in self.settings.options('plugins')
                       if p not in self.plugins]:
            try:
                self.plugins[plugin] = load_plugin(plugin)
            except Exception:
                self.plugins[plugin] = {'package': plugin,
                                        'menu': 'unavailable',
                                        'actions': [],
                                        'order': 'Disabled'}

        self.grid = QtWidgets.QGridLayout()
        self.grid.setSpacing(10)
        headers = ['Package', 'Menu Name', 'Order']
        width = [100, 50, 50]
        column = 0
        for header in headers:
            label = NXLabel(header, bold=True, align='center')
            self.grid.addWidget(label, 0, column)
            self.grid.setColumnMinimumWidth(column, width[column])
            column += 1
        self.order_options = list(range(1, len(self.plugins)+1)) + ['Disabled']
        for row, plugin in enumerate(self.plugins):
            p = self.plugins[plugin]
            self.grid.addWidget(NXLabel(p['package']), row+1, 0)
            self.grid.addWidget(NXLabel(p['menu']), row+1, 1)
            self.grid.addWidget(NXComboBox(items=self.order_options,
                                           default=p['order'] or 'Disabled',
                                           align='center'), row+1, 2)

        self.set_layout(self.grid, self.close_buttons(save=True))
        self.set_title('Managing Plugins')

    def update_plugins(self):
        """
        Update the plugin order.

        The order of the plugins is updated by reading the values from
        the grid of widgets. The order is checked to ensure that it is
        unique and sequential, and an error is raised if it is not. If a
        plugin is unavailable, the order is set to 'Disabled' and the
        selection is reset.
        """
        for row, plugin in enumerate(self.plugins):
            order_combo = self.grid.itemAtPosition(row+1, 2).widget()
            order = order_combo.selected
            if order == 'Disabled':
                self.plugins[plugin]['order'] = 'Disabled'
            else:
                if self.plugins[plugin]['menu'] == 'unavailable':
                    try:
                        self.plugins[plugin] = load_plugin(plugin)
                    except Exception as error:
                        self.plugins[plugin]['order'] = 'Disabled'
                        order_combo.select('Disabled')
                        raise NeXusError(
                            f"Plugin '{plugin}' could not be loaded\n{error}")
                else:
                    self.plugins[plugin]['order'] = order
        order_set = [int(p['order']) for p in self.plugins.values()
                     if p['order'] != 'Disabled']
        if sorted(order_set) != list(range(1, len(order_set)+1)):
            raise NeXusError("Plugin order must be unique and sequential")

    def sorted_plugins(self):
        """
        Return a sorted list of plugins in the order of their menu
        appearance.
        
        Only plugins with an order that is not 'Disabled' are included
        in the sorted list. The list is sorted by the order of the
        plugins.
        """
        plugins = {k: v for k, v in self.plugins.items()
                   if v.get('order') != 'Disabled'}
        return sorted(plugins, key=lambda k: plugins[k]['order'])

    def accept(self):
        """
        Save the updated plugin configuration and refresh the main window.

        This method updates the order of plugins, removes existing plugin
        menus, and adds them back in the updated order. It saves the
        updated plugin settings to the configuration file and closes the
        dialog. If an error occurs, it reports the error without applying 
        the changes.

        Raises
        ------
        NeXusError
            If the plugin order is not unique and sequential, or if there
            is an error in managing the plugins.
        """

        try:
            self.update_plugins()
            for name in [p['menu'] for p in self.plugins.values()]:
                self.mainwindow.remove_plugin_menu(name)
            for plugin in self.sorted_plugins():
                p = self.plugins[plugin]
                name, actions = p['menu'], p['actions']
                self.mainwindow.add_plugin_menu(
                    name, actions, before=self.mainwindow.view_menu)
                self.mainwindow.plugins[plugin] = p
            for plugin in self.plugins:
                self.settings.set('plugins', plugin,
                                  self.plugins[plugin]['order'])
            self.settings.save()
            super().accept()
        except NeXusError as error:
            report_error("Managing plugins", error)
