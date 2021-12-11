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
import os

import numpy as np
from nexpy.gui.importdialog import NXImportDialog
from nexpy.gui.utils import report_error
from nexpy.gui.widgets import (NXCheckBox, NXComboBox, NXLabel, NXLineEdit,
                               NXPushButton)
from nexusformat.nexus import NXdata, NXentry, NXfield, NXgroup
from qtpy import QtWidgets

filetype = "Text File"


class ImportDialog(NXImportDialog):
    """Dialog to import a text file"""

    data_types = ['char', 'float32', 'float64', 'int8', 'uint8', 'int16',
                  'uint16', 'int32', 'uint32', 'int64', 'uint64']

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.textbox = QtWidgets.QTextEdit()
        self.textbox.setMinimumWidth(400)
        self.textbox.setMinimumHeight(200)
        self.textbox.setReadOnly(True)

        self.skipbox = NXLineEdit(0, width=20, align='center')
        self. headbox = NXCheckBox()
        self.delimiters = {'Whitespace': None, 'Tab': '\t', 'Space': ' ',
                           'Comma': ',', 'Colon': ':', 'Semicolon': ';'}
        self.delcombo = NXComboBox(items=self.delimiters)

        self.groupbox = NXLineEdit('data')
        standard_groups = sorted(list(set([g for g in
                                 self.mainwindow.nxclasses['NXentry'][2]])))
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
                        self.make_layout('Header Row', self.headbox,
                                         'stretch',
                                         'Skipped Rows', self.skipbox,
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
        if self.get_filename() == '':
            self.choose_file()
        if os.path.exists(self.get_filename()):
            self.import_file = self.get_filename()
            with open(self.import_file, 'r') as f:
                text = f.read()
                self.textbox.setText(text.replace('\t', ' \t\u25B3'))
                self.textbox.repaint()
                self.text = []
                for line in text.splitlines():
                    if line.split():
                        self.text.append(line)
            if [s for s in self.text if '\t' in s]:
                self.delcombo.select('Tab')

    def select_class(self):
        self.groupbox.setText(self.groupcombo.selected[2:])
        if self.groupcombo.selected not in ['NXdata', 'NXmonitor', 'NXlog']:
            for item in ['signal', 'axis', 'errors']:
                self.signalcombo.remove(item)
        else:
            self.signalcombo.add('signal', 'axis', 'errors')

    def select_field(self):
        col = self.fieldcombo.selected
        self.fieldbox.setText(self.data[col]['name'])
        self.typecombo.select(self.data[col]['dtype'])
        self.signalcombo.select(self.data[col]['signal'])

    def update_field(self):
        col = self.fieldcombo.selected
        self.data[col]['name'] = self.fieldbox.text()
        self.data[col]['dtype'] = self.typecombo.selected
        self.data[col]['signal'] = self.signalcombo.selected
        for c in [c for c in self.fieldcombo if c != col]:
            if (self.data[c]['signal'] in ['signal', 'axis', 'errors'] and
                    self.data[c]['signal'] == self.data[col]['signal']):
                self.data[c]['signal'] = 'field'

    @property
    def header(self):
        if self.headbox.isChecked():
            return True
        else:
            return None

    def read_data(self):
        delimiter = self.delimiters[self.delcombo.selected]
        skip_header = int(self.skipbox.text())
        if self.header:
            self.headers = self.text[skip_header].split(delimiter)
        else:
            self.headers = None
        try:
            input = np.genfromtxt(self.text, delimiter=delimiter,
                                  names=self.header, skip_header=skip_header,
                                  dtype=None, autostrip=True, encoding='utf8')
        except ValueError as error:
            report_error("Importing Text File", error)
            self.data = None
            return
        self.data = {}
        for i, _ in enumerate(input[0]):
            if input.dtype.names is not None:
                name = input.dtype.names[i]
                dtype = input.dtype[i].name
            else:
                name = 'Col'+str(i+1)
                dtype = input.dtype.name
            if dtype not in self.data_types:
                dtype = 'char'
            data = [c[i] for c in input]
            signal = 'field'
            if self.groupcombo.selected in ['NXdata', 'NXmonitor', 'NXlog']:
                if i <= 2 and dtype != 'char':
                    signal = ['axis', 'signal', 'errors'][i]
            self.data['Col'+str(i+1)] = {'name': name, 'dtype': dtype,
                                         'signal': signal, 'data': data}

    def customize_data(self):
        self.read_data()
        if self.data is not None:
            self.fieldcombo.add(*list(self.data))
            self.fieldcombo.select('Col1')
            self.fieldbox.setText(self.data['Col1']['name'])
            self.typecombo.select(self.data['Col1']['dtype'])
            self.signalcombo.select(self.data['Col1']['signal'])
            self.insert_layout(5, self.field_layout)

    def get_data(self):
        group = NXgroup(name=self.groupbox.text())
        group.nxclass = self.groupcombo.selected
        for i, col in enumerate([c for c in self.data
                                 if self.data[c]['signal'] != 'exclude']):
            name = self.data[col]['name']
            group[name] = NXfield(self.data[col]['data'],
                                  dtype=self.data[col]['dtype'])
            if self.header and name != self.headers[i]:
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
        """
        Completes the data import.
        """
        if self.data is None:
            self.read_data()
            if self.data is None:
                self.raise_()
                self.activateWindow()
                return
        self.accepted = True
        self.mainwindow.import_data()
        super().accept()
