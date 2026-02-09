# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Module to read in a text file and convert it to NeXus.

This is provided as an example of writing an import dialog. Each new
importer needs to layout the GUI buttons necessary for defining the
imported file and its attributes and a single module, get_data, which
returns an NXroot or NXentry object. This will be added to the NeXpy
tree.

Two GUI elements are provided for convenience:

    ImportDialog.filebox: Contains a "Choose File" button and a text
                          box. Both can be used to set the path to the
                          imported file. This can be retrieved as a
                          string using self.get_filename().
    ImportDialog.buttonbox: Contains a "Cancel" and "OK" button to close
                            the dialog. This should be placed at the
                            bottom of all import dialogs.
"""
from pathlib import Path

import numpy as np
from nexpy.gui.importdialog import NXImportDialog
from nexpy.gui.utils import parse_label, report_error
from nexpy.gui.widgets import (NXCheckBox, NXComboBox, NXLabel, NXLineEdit,
                               NXPushButton, NXTextEdit)
from nexpy.gui.pyqt import QtGui
from nexusformat.nexus import NXdata, NXentry, NXfield, NXgroup
from nexusformat.nexus.validate import GroupValidator

filetype = "Text File"


class ImportDialog(NXImportDialog):
    """Dialog to import a text file"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16',
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.textbox = NXTextEdit()
        self.textbox.setMinimumWidth(400)
        self.textbox.setMinimumHeight(200)
        self.textbox.setReadOnly(True)

        self.text = []

        self.skipbox = NXLineEdit(0, slot=self.write_box, width=20,
                                  align='center')
        self.headbox = NXCheckBox(slot=self.write_box)
        self.titlebox = NXCheckBox(slot=self.write_box)
        self.delimiters = {'Whitespace': None, 'Tab': '\t', 'Space': ' ',
                           'Comma': ',', 'Colon': ':', 'Semicolon': ';'}
        self.delcombo = NXComboBox(items=self.delimiters)

        self.groupbox = NXLineEdit('data')
        validator = GroupValidator('NXentry')
        standard_groups = validator.valid_groups
        other_groups = sorted([g for g in self.mainwindow.nxclasses
                               if g not in standard_groups])
        self.groupcombo = NXComboBox(self.select_class, standard_groups)
        self.groupcombo.insertSeparator(self.groupcombo.count())
        self.groupcombo.add(*other_groups)
        self.groupcombo.select('NXdata')
        self.fieldcombo = NXComboBox(self.select_field)
        self.fieldbox = NXLineEdit(slot=self.update_field)
        self.typecombo = NXComboBox(self.update_field, self.data_types,
                                    default='float64')
        self.signalcombo = NXComboBox(self.update_field,
                                      ['field', 'signal', 'axis', 'errors',
                                       'exclude'], default='field')
        self.field_layout = self.make_layout(
            NXLabel('Output Fields', bold=True),
            self.make_layout(self.fieldcombo, self.fieldbox,
                             self.typecombo, self.signalcombo),
            spacing=5, vertical=True)
        self.customizebutton = NXPushButton('Customize Fields',
                                            self.customize_data)

        self.set_layout(self.filebox(slot=self.read_file), self.textbox,
                        self.make_layout('Title Row', self.titlebox,
                                         'stretch',
                                         'Skipped Rows', self.skipbox,
                                         'stretch',
                                         'Header Row', self.headbox,
                                         'stretch',
                                         'Delimiters', self.delcombo),
                        NXLabel('Output Group', bold=True),
                        self.make_layout('Class', self.groupcombo,
                                         'Name', self.groupbox, align='left'),
                        self.make_layout(self.customizebutton,
                                         self.close_buttons(save=True),
                                         align='justified'),
                        spacing=5)
        self.set_title("Import "+str(filetype))
        self.data = None

    def read_file(self):
        """Read the text file"""
        if self.get_filename() == '':
            self.choose_file()
        file_path = Path(self.get_filename())
        if file_path.exists():
            self.import_file = file_path
            with open(self.import_file, 'r') as f:
                text = f.read()
                self.text = []
                for line in text.splitlines():
                    if line.split():
                        self.text.append(line)
            if [s for s in self.text if '\t' in s]:
                self.delcombo.select('Tab')
            self.write_box()

    def write_box(self):
        """
        Write the file text to the text preview box.

        If the first line of the text is a title, it is colored red.
        If any lines are skipped, they are faded. If there is a line of
        headers, it is colored blue.
        """
        processed_text = "\n".join(self.text).replace('\t', ' \t\u25B3')
        self.textbox.setPlainText(processed_text)
        cursor = self.textbox.textCursor()
        if self.has_title and len(self.text) > 0:
            title_fmt = QtGui.QTextCharFormat()
            title_fmt.setForeground(QtGui.QColor("red"))
            title_fmt.setFontWeight(QtGui.QFont.Weight.Bold)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfLine,
                                QtGui.QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(title_fmt)
            skip_start_index = 1
        else:
            skip_start_index = 0
        faded_fmt = QtGui.QTextCharFormat()
        faded_fmt.setForeground(QtGui.QColor(180, 180, 180))
        for i in range(skip_start_index, skip_start_index + self.skip_header):
            if i < len(self.text):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
                for _ in range(i):
                    cursor.movePosition(
                        QtGui.QTextCursor.MoveOperation.NextBlock)
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfLine,
                                    QtGui.QTextCursor.MoveMode.KeepAnchor)
                cursor.setCharFormat(faded_fmt)
        header_idx = header_idx = skip_start_index + self.skip_header
        if self.has_header and len(self.text) > header_idx:
            header_fmt = QtGui.QTextCharFormat()
            header_fmt.setForeground(QtGui.QColor("blue"))        
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.Start)
            for _ in range(header_idx):
                cursor.movePosition(QtGui.QTextCursor.MoveOperation.NextBlock)
            cursor.movePosition(QtGui.QTextCursor.MoveOperation.EndOfLine,
                                QtGui.QTextCursor.MoveMode.KeepAnchor)
            cursor.setCharFormat(header_fmt)
        self.textbox.repaint()

    def select_class(self):
        """Update the group and field combo boxes for the selected class"""
        self.groupbox.setText(self.groupcombo.selected[2:])
        if self.groupcombo.selected not in ['NXdata', 'NXmonitor', 'NXlog']:
            for item in ['signal', 'axis', 'errors']:
                self.signalcombo.remove(item)
        else:
            self.signalcombo.add('signal', 'axis', 'errors')

    def select_field(self):
        """Update the combo boxes for the selected field"""
        col = self.fieldcombo.selected
        self.fieldbox.setText(self.data[col]['name'])
        self.typecombo.select(self.data[col]['dtype'])
        self.signalcombo.select(self.data[col]['signal'])

    def update_field(self):
        """Update the field data structure with the current values"""
        col = self.fieldcombo.selected
        self.data[col]['name'] = self.fieldbox.text()
        self.data[col]['dtype'] = self.typecombo.selected
        self.data[col]['signal'] = self.signalcombo.selected
        for c in [c for c in self.fieldcombo if c != col]:
            if (self.data[c]['signal'] in ['signal', 'axis', 'errors'] and
                    self.data[c]['signal'] == self.data[col]['signal']):
                self.data[c]['signal'] = 'field'

    @property
    def has_title(self):
        if self.titlebox.isChecked():
            return True
        else:
            return None

    @property
    def has_header(self):
        if self.headbox.isChecked():
            return True
        else:
            return None

    @property
    def skip_header(self):
        try:
            return int(self.skipbox.text())
        except ValueError:
            return 0

    def read_data(self):
        """Read the text file and create the data structure"""
        if self.has_title:
            self.title = self.text[0]
        else:
            self.title = None
        delimiter = self.delimiters[self.delcombo.selected]
        skip_header = self.skip_header
        if self.has_title:
            skip_header += 1
        if self.has_header:
            self.headers = self.text[skip_header].split(delimiter)
        else:
            self.headers = None
        skip_header += 1
        try:
            input = np.genfromtxt(self.text, delimiter=delimiter,
                                  skip_header=skip_header,
                                  dtype=None, autostrip=True, encoding='utf8')
        except ValueError as error:
            report_error("Importing Text File", error)
            self.data = None
            return
        self.data = {}
        for i, _ in enumerate(input[0]):
            if self.headers:
                name, units = parse_label(self.headers[i])
            else:
                name, units = 'Col'+str(i+1), None
            dtype = input.dtype.name
            if dtype not in self.data_types:
                dtype = 'char'
            data = [c[i] for c in input]
            signal = 'field'
            if self.groupcombo.selected in ['NXdata', 'NXmonitor', 'NXlog']:
                if i <= 2 and dtype != 'char':
                    signal = ['axis', 'signal', 'errors'][i]
            self.data['Col'+str(i+1)] = {'name': name, 'units': units,
                                         'dtype': dtype, 'signal': signal,
                                         'data': data}

    def customize_data(self):
        """Create combo boxes to allow the fields to be customized."""
        self.read_data()
        if self.data is not None:
            self.fieldcombo.add(*list(self.data))
            self.fieldcombo.select('Col1')
            self.fieldbox.setText(self.data['Col1']['name'])
            self.typecombo.select(self.data['Col1']['dtype'])
            self.signalcombo.select(self.data['Col1']['signal'])
            self.insert_layout(5, self.field_layout)

    def get_data(self):
        """Return the data as an NXentry"""
        group = NXgroup(name=self.groupbox.text())
        group.nxclass = self.groupcombo.selected
        if self.title:
            group['title'] = self.title
        for i, col in enumerate([c for c in self.data
                                 if self.data[c]['signal'] != 'exclude']):
            name = self.data[col]['name']
            group[name] = NXfield(self.data[col]['data'],
                                  dtype=self.data[col]['dtype'])
            if self.data[col]['units']:
                group[name].nxunits = self.data[col]['units']
            if self.has_header and name != self.headers[i]:
                group[name].long_name = self.headers[i]
            if isinstance(group, NXdata):
                if self.data[col]['signal'] == 'signal':
                    group.nxsignal = group[name]
                elif self.data[col]['signal'] == 'axis':
                    group.nxaxes = [group[name]]
                elif self.data[col]['signal'] == 'signal':
                    group.nxerrors = group[name]
        return NXentry(group)

    def accept(self):
        """Complete the data import."""
        if self.data is None:
            self.read_data()
            if self.data is None:
                self.raise_()
                self.activateWindow()
                return
        self.accepted = True
        super().accept()
