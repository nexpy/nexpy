# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Module to read in a folder of image files and convert them to NeXus.
"""
import re

import numpy as np
from nexpy.gui.importdialog import NXImportDialog
from nexpy.gui.widgets import NXComboBox, NXLabel, NXLineEdit
from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXentry,
                               NXfield, NXnote)
from qtpy import QtCore, QtWidgets

filetype = "Image Stack"
maximum = 0.0
prefix_pattern = re.compile(r'^([^.]+)(?:(?<!\d)|(?=_))')


class ImportDialog(NXImportDialog):
    """Dialog to import an image stack using Fabio"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        self.filter_box = self.make_filterbox()
        self.rangebox = self.make_rangebox()
        self.set_layout(self.directorybox(),
                        self.filter_box,
                        self.rangebox,
                        self.progress_layout(save=True))

        self.set_title("Import "+str(filetype))

    @property
    def suffix(self):
        return self.suffix_box.text()

    def make_filterbox(self):
        filterbox = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()
        layout.setSpacing(10)
        prefix_label = NXLabel('File Prefix')
        self.prefix_box = NXLineEdit(slot=self.set_range)
        suffix_label = NXLabel('File Suffix')
        self.suffix_box = NXLineEdit(slot=self.get_prefixes)
        extension_label = NXLabel('File Extension')
        self.extension_box = NXLineEdit(slot=self.set_extension)
        layout.addWidget(prefix_label, 0, 0)
        layout.addWidget(self.prefix_box, 0, 1)
        layout.addWidget(suffix_label, 0, 2)
        layout.addWidget(self.suffix_box, 0, 3)
        layout.addWidget(extension_label, 0, 4)
        layout.addWidget(self.extension_box, 0, 5)
        self.prefix_combo = NXComboBox(self.choose_prefix)
        self.extension_combo = NXComboBox(self.choose_extension)
        layout.addWidget(self.prefix_combo, 1, 1,
                         alignment=QtCore.Qt.AlignHCenter)
        layout.addWidget(self.extension_combo, 1, 5,
                         alignment=QtCore.Qt.AlignHCenter)
        filterbox.setLayout(layout)
        filterbox.setVisible(False)
        return filterbox

    def make_rangebox(self):
        rangebox = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        rangeminlabel = NXLabel("Min. index")
        self.rangemin = NXLineEdit(width=150, align='right')
        rangemaxlabel = NXLabel("Max. index")
        self.rangemax = NXLineEdit(width=150, align='right')
        layout.addWidget(rangeminlabel)
        layout.addWidget(self.rangemin)
        layout.addStretch()
        layout.addWidget(rangemaxlabel)
        layout.addWidget(self.rangemax)
        rangebox.setLayout(layout)
        rangebox.setVisible(False)
        return rangebox

    def choose_directory(self):
        super().choose_directory()
        self.get_extensions()
        self.get_prefixes()
        self.filter_box.setVisible(True)

    def get_prefixes(self):
        files = [f.name for f in self.get_filesindirectory()
                 if f.suffix == self.get_extension()]
        self.prefix_combo.clear()
        prefixes = []
        for file in files:
            prefix = prefix_pattern.match(file)
            if prefix:
                prefixes.append(prefix.group(0).strip('_-'))
        for prefix in set(prefixes):
            if prefix != '':
                self.prefix_combo.addItem(prefix)
        if self.get_prefix() not in prefixes:
            self.set_prefix(prefixes[0])
        self.prefix_combo.setCurrentIndex(
            self.prefix_combo.findText(self.get_prefix()))
        try:
            files = [f for f in files if f.startswith(self.get_prefix())]
            min, max = self.get_index(files[0]), self.get_index(files[-1])
            if max < min:
                raise ValueError
            self.set_indices(min, max)
            self.rangebox.setVisible(True)
        except Exception:
            self.set_indices('', '')
            self.rangebox.setVisible(False)

    def get_prefix(self):
        return self.prefix_box.text().strip()

    def choose_prefix(self):
        self.set_prefix(self.prefix_combo.currentText())

    def set_prefix(self, text):
        self.prefix_box.setText(text)
        if self.prefix_combo.findText(text) >= 0:
            self.prefix_combo.setCurrentIndex(self.prefix_combo.findText(text))
        self.get_prefixes()

    def get_extensions(self):
        files = self.get_filesindirectory()
        extensions = set([f.suffix for f in files])
        self.extension_combo.clear()
        for extension in extensions:
            self.extension_combo.addItem(extension)
        if not self.get_extension() or self.get_extension() not in extensions:
            if '.tif' in extensions:
                self.set_extension('.tif')
            elif '.tiff' in extensions:
                self.set_extension('.tiff')
            elif '.cbf' in extensions:
                self.set_extension('.cbf')
            else:
                self.set_extension(list(extensions)[0])
        self.extension_combo.setCurrentIndex(
            self.extension_combo.findText(self.get_extension()))
        return extensions

    def get_extension(self):
        extension = self.extension_box.text().strip()
        if extension and not extension.startswith('.'):
            extension = '.'+extension
        return extension

    def choose_extension(self):
        self.set_extension(self.extension_combo.currentText())

    def set_extension(self, text):
        if not text.startswith('.'):
            text = '.'+text
        self.extension_box.setText(text)
        if self.extension_combo.findText(text) >= 0:
            self.extension_combo.setCurrentIndex(
                self.extension_combo.findText(text))
        self.get_prefixes()

    def get_index(self, filename):
        return int(re.match(fr'^(.*?)([0-9]*){self.suffix}[.](.*)$',
                            str(filename)).groups()[1])

    def get_indices(self):
        try:
            min, max = (int(self.rangemin.text().strip()),
                        int(self.rangemax.text().strip()))
            return min, max
        except Exception:
            return None

    def set_indices(self, min, max):
        self.rangemin.setText(str(min))
        self.rangemax.setText(str(max))

    def get_files(self):
        prefix = self.get_prefix()
        filenames = self.get_filesindirectory(prefix,
                                              self.get_extension())
        if self.get_indices():
            min, max = self.get_indices()
            return [file for file in filenames
                    if self.get_index(file) >= min and
                    self.get_index(file) <= max]
        else:
            return filenames

    def set_range(self):
        files = self.get_filesindirectory(self.get_prefix(),
                                          self.get_extension())
        try:
            min, max = self.get_index(files[0]), self.get_index(files[-1])
            if min > max:
                raise ValueError
            self.set_indices(min, max)
            self.rangebox.setVisible(True)
        except Exception:
            self.set_indices('', '')
            self.rangebox.setVisible(False)

    def read_image(self, filename):
        try:
            import fabio
        except ImportError:
            raise NeXusError("Please install the 'fabio' module")
        im = fabio.open(str(filename))
        return im

    def read_images(self, filenames):
        v0 = self.read_image(filenames[0]).data
        v = np.zeros(
            [len(filenames),
             v0.shape[0],
             v0.shape[1]],
            dtype=np.int32)
        for i, filename in enumerate(filenames):
            v[i] = self.read_image(filename).data
        global maximum
        if v.max() > maximum:
            maximum = v.max()
        return v

    def get_data(self):
        prefix = self.get_prefix()
        if prefix:
            self.import_file = prefix
        else:
            self.import_file = self.get_directory()
        filenames = self.get_files()
        im = self.read_image(filenames[0])
        v0 = im.data
        x = NXfield(range(v0.shape[1]), dtype=np.uint16, name='x')
        y = NXfield(range(v0.shape[0]), dtype=np.uint16, name='y')
        z = NXfield(range(1, len(filenames)+1), dtype=np.uint16, name='z')
        v = NXfield(shape=(len(filenames), v0.shape[0], v0.shape[1]),
                    dtype=v0.dtype, name='v')
        v[0] = v0
        if v._memfile:
            chunk_size = v._memfile['data'].chunks[0]
        else:
            chunk_size = v.shape[0]/10
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(filenames))
        for i in range(0, len(filenames), chunk_size):
            try:
                files = []
                for j in range(i, i+chunk_size):
                    files.append(filenames[j])
                    self.progress_bar.setValue(j)
                self.update_progress()
                v[i:i+chunk_size, :, :] = self.read_images(files)
            except IndexError:
                pass
        global maximum
        v.maximum = maximum

        if im.getclassname() == 'CbfImage':
            note = NXnote(type='text/plain', file_name=self.import_file)
            note.data = im.header.pop('_array_data.header_contents', '')
            note.description = im.header.pop(
                '_array_data.header_convention', '')
        else:
            note = None

        header = NXcollection()
        for key, value in im.header.items():
            header[key] = value

        if note:
            return NXentry(
                NXdata(
                    v, (z, y, x),
                    CBF_header=note, header=header))
        else:
            return NXentry(NXdata(v, (z, y, x), header=header))
