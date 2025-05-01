# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import logging
import numbers
from pathlib import Path

import matplotlib as mpl
import numpy as np
from matplotlib.legend import Legend
from matplotlib.rcsetup import validate_aspect, validate_float
from nexusformat.nexus import (NeXusError, NXattr, NXdata, NXentry, NXfield,
                               NXgroup, NXlink, NXroot, NXvirtualfield,
                               nxconsolidate, nxgetconfig, nxload, nxsetconfig)

from .pyqt import QtCore, QtWidgets, getOpenFileName, getSaveFileName
from .utils import (convertHTML, display_message, fix_projection, format_mtime,
                    format_timestamp, get_color, get_mtime, human_size,
                    keep_data, load_plugin, natural_sort, report_error,
                    set_style, timestamp)
from .widgets import (GridParameters, NXCheckBox, NXComboBox, NXDialog,
                      NXDoubleSpinBox, NXLabel, NXLineEdit, NXPanel,
                      NXPlainTextEdit, NXpolygon, NXPushButton, NXScrollArea,
                      NXSpinBox, NXTab, NXWidget)


BaseDialog = NXDialog


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
        dir = self.mainwindow.backup_dir / timestamp()
        dir.mkdir()
        fname = dir.joinpath(root+'_backup.nxs')
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
            fname = Path(self.directory).joinpath(f)
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
        except Exception:
            raise NeXusError("Files not selected")

    def get_scan(self):
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
        return '/' + name.replace('!!', '/').replace('.lock', '')

    def show_locks(self):
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
        self.mainwindow.settings.set('settings', 'definitions',
                                     cfg['definitions'])
        self.mainwindow.settings.set('settings', 'recursive',
                                     cfg['recursive'])
        self.mainwindow.settings.set('settings', 'style',
                                     self.parameters['style'].value)
        self.mainwindow.settings.save()

    def set_nexpy_settings(self):
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


class ValidateDialog(NXPanel):
    """Dialog to view a NeXus field"""

    def __init__(self, parent=None):
        super().__init__('Validate', title='Validation Panel', apply=False,
                         reset=False, parent=parent)
        self.tab_class = ValidateTab

    def activate(self, node):
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
    """Dialog to display output NeXus validation results."""

    def __init__(self, label, node, parent=None):

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

        self.text_box = QtWidgets.QTextEdit()
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
        """Opens a file dialog to locate the definitions directory."""
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
        """Opens a file dialog to locate an application definition."""
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
        if self.radiobutton['info'].isChecked():
            return 'info'
        elif self.radiobutton['warning'].isChecked():
            return 'warning'
        else:
            return 'error'

    def validate(self):
        self.node.validate(level=self.log_level, application=self.application,
                           definitions=self.definitions)
        self.show_log()
        self.pushbutton['Validate Entry'].setChecked(True)
        for button in ['Check Base Class', 'Inspect Base Class']:
            self.pushbutton[button].setChecked(False)

    def check(self):
        self.node.check(level=self.log_level, definitions=self.definitions)
        self.show_log()
        self.pushbutton['Check Base Class'].setChecked(True)
        for button in ['Validate Entry', 'Inspect Base Class']:
            self.pushbutton[button].setChecked(False)

    def inspect(self):
        self.node.inspect(definitions=self.definitions)
        self.show_log()
        self.pushbutton['Inspect Base Class'].setChecked(True)
        for button in ['Validate Entry', 'Check Base Class']:
            self.pushbutton[button].setChecked(False)

    def select_level(self):
        if self.pushbutton['Validate Entry'].isChecked():
            self.validate()
        elif self.pushbutton['Check Base Class'].isChecked():
            self.check()
        elif self.pushbutton['Inspect Base Class'].isChecked():
            self.inspect()

    def show_log(self):
        handler = logging.getLogger('NXValidate').handlers[0]
        self.text_box.setText(convertHTML(handler.flush()))
        self.setVisible(True)
        self.raise_()
        self.activateWindow()


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
            from nexusformat.nexus.validate import GroupValidator
            self.validator = GroupValidator(self.node.nxclass)
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
            self.standard_groups = self.validator.valid_groups
            for name in self.standard_groups:
                self.combo_box.addItem(name)
            self.combo_box.insertSeparator(self.combo_box.count())
            other_groups = sorted([g for g in self.mainwindow.nxclasses
                                   if g not in self.standard_groups])
            for name in other_groups:
                self.combo_box.addItem(name)
            grid.addWidget(combo_label, 0, 0)
            grid.addWidget(self.combo_box, 0, 1)
            grid.addWidget(name_label, 1, 0)
            grid.addWidget(self.name_box, 1, 1)
            self.select_combo()
        elif class_name == "NXfield":
            combo_label = NXLabel()
            self.combo_box = NXComboBox(self.select_combo)
            self.standard_fields = self.validator.valid_fields
            for name in self.standard_fields:
                self.combo_box.addItem(name)
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
            if (name in self.standard_groups and 
                    '@type' in self.standard_groups[name]):
                self.combo_box.setCurrentText(
                    self.standard_groups[name]['@type'])
            else:
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
                iter(shape)
                return shape
            except TypeError:
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
                fields = sorted(list(set([g for g in
                                self.mainwindow.nxclasses[parent_class][1]])))
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
            self.file_combo.add(file_name.name)
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
        return self.log_directory / self.file_combo.currentText()

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
    """Dialog to restore or purge backup files"""

    def __init__(self, parent=None):

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
        name, ext = Path(backup).stem, Path(backup).suffix
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
    """Dialog to manage NeXus plugins"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.plugins = self.mainwindow.plugins.copy()

        self.settings = self.mainwindow.settings
        for plugin in [p for p in self.settings.options('plugins')
                       if p not in self.plugins]:
            try:
                self.plugins[plugin] = load_plugin(plugin)
            except Exception as error:
                report_error("Managing plugins", error)

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

        self.order_options = list(range(1, len(self.plugins)+1)) +['Disabled']
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
        for row, plugin in enumerate(self.plugins):
            p = self.plugins[plugin]
            order = self.grid.itemAtPosition(row+1, 2).widget().currentText()
            p['order'] = order
        order_set = [int(p['order']) for p in self.plugins.values()
                     if p['order'] != 'Disabled']
        if sorted(order_set) != list(range(1, len(order_set)+1)):
            raise NeXusError("Plugin order must be unique and sequential")

    def sorted_plugins(self):
        plugins = {k: v for k, v in self.plugins.items()
                   if v.get('order') != 'Disabled'}
        return sorted(plugins, key=lambda k: plugins[k]['order'])

    def accept(self):
        try:
            self.update_plugins()
            for name in [p['menu'] for p in self.plugins.values()]:
                self.mainwindow.remove_plugin_menu(name)
            for plugin in self.sorted_plugins():
                p = self.plugins[plugin]
                name, actions = p['menu'], p['actions']
                self.mainwindow.add_plugin_menu(
                    name, actions, before=self.mainwindow.view_menu)
            for plugin in self.plugins:
                self.settings.set('plugins', plugin,
                                  self.plugins[plugin]['order'])
            self.settings.save()
            super().accept()
        except NeXusError as error:
            report_error("Managing plugins", error)
