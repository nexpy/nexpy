#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Module to read in a folder of image files and convert them to NeXus.

Each importer needs to layout the GUI buttons necessary for defining the imported file 
and its attributes and a single module, get_data, which returns an NXroot or NXentry
object. This will be added to the NeXpy tree.

Two GUI elements are provided for convenience:

    ImportDialog.filebox: Contains a "Choose File" button and a text box. Both can be 
                          used to set the path to the imported file. This can be 
                          retrieved as a string using self.get_filename().
    ImportDialog.buttonbox: Contains a "Cancel" and "OK" button to close the dialog. 
                            This should be placed at the bottom of all import dialogs.
"""

from IPython.external.qt import QtGui
import os, re

import numpy as np
from nexpy.api.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "Image Stack"
maximum = 0.0

class ImportDialog(BaseImportDialog):
    """Dialog to import an image stack (TIFF or CBF)"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.directorybox())
        filter_layout = QtGui.QHBoxLayout()
        prefix_label = QtGui.QLabel('File Prefix')
        self.prefix_box = QtGui.QLineEdit()
        ext_label = QtGui.QLabel('File Extension')
        self.ext_box = QtGui.QLineEdit()
        filter_layout.addWidget(prefix_label)
        filter_layout.addWidget(self.prefix_box)
        filter_layout.addWidget(ext_label)
        filter_layout.addWidget(self.ext_box)
        layout.addLayout(filter_layout)

        status_layout = QtGui.QHBoxLayout()
        self.progress_bar = QtGui.QProgressBar()
        status_layout.addWidget(self.progress_bar)
        self.progress_bar.setVisible(False)
        status_layout.addStretch()
        status_layout.addWidget(self.buttonbox())
        layout.addLayout(status_layout)

        self.setLayout(layout)
  
        self.setWindowTitle("Import "+str(filetype))

    def choose_directory(self):
        super(ImportDialog, self).choose_directory()
        files = self.get_filesindirectory()
        extensions =  set([os.path.splitext(f)[-1] for f in files])
        if not self.get_extension() or not self.get_extension() in extensions:
            if '.tif' in extensions:
                self.ext_box.setText('.tif')
            elif '.tiff' in extensions:
                self.ext_box.setText('.tiff')
            elif '.cbf' in extensions:
                self.ext_box.setText('.cbf')
        if not self.get_prefix():
            extension = self.get_extension()
            files = [f for f in files if f.endswith(extension)]
            parts = []
            for file in files:
                parts.append([t for t in re.split(r'(\d+)', file)])
            prefix=''
            for i in range(len(parts[0])):
                s=set([p[i] for p in parts])
                if i == 0:
                    j = len(s)
                if len(s) == j:
                    prefix += list(s)[0]
                else:
                    break
            self.prefix_box.setText(prefix.strip('-_'))

    def get_prefix(self):
        return self.prefix_box.text().strip()
 
    def get_extension(self):
        extension = self.ext_box.text().strip()
        if not extension.startswith('.'):
            extension = '.'+extension
        return extension
 
    def read_image(self, filename):
        if self.get_extension() == '.cbf':
            import pycbf
            cbf = pycbf.cbf_handle_struct()
            cbf.read_file(str(filename), pycbf.MSG_DIGEST)
            cbf.select_datablock(0)
            cbf.select_category(0)
            cbf.select_column(2)
            imsize = cbf.get_image_size(0)
            return np.fromstring(cbf.get_integerarray_as_string(),np.int32).reshape(imsize)
        else:
            from nexpy.readers.tifffile import tifffile as TIFF
            return TIFF.imread(filename)

    def read_images(self, filenames):
        if self.get_extension() == '.cbf':
            v0 = self.read_image(filenames[0])
            v = np.zeros([len(filenames), v0.shape[0], v0.shape[1]], dtype=np.int32)
            i = 0
            for filename in filenames:
                v[i] = self.read_image(filename)
                i += 1
        else:
            from nexpy.readers.tifffile import tifffile as TIFF
            v = TIFF.TiffSequence(filenames).asarray()        
        global maximum
        if v.max() > maximum:
            maximum = v.max()
        return v

    def get_data(self):
        prefix = self.get_prefix()
        filenames = self.get_filesindirectory(prefix, 
                                              self.get_extension())
        if prefix:
            self.import_file = prefix
        else:
            self.import_file = self.get_directory()       
        v0 = self.read_image(filenames[0])
        x = NXfield(range(v0.shape[1]), dtype=np.uint16, name='x')
        y = NXfield(range(v0.shape[0]), dtype=np.uint16, name='y')
        z = NXfield(range(1,len(filenames)+1), dtype=np.uint16, name='z')
        v = NXfield(shape=(len(filenames),v0.shape[0],v0.shape[1]),
                    dtype=v0.dtype, name='v')
        v[0] = v0
        if v._memfile:
            chunk_size = v._memfile['data'].chunks[0]
        else:
            chunk_size = v.shape[0]/10
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(filenames))
        for i in range(0, len(filenames)):
            try:
                files = []
                for j in range(i,i+chunk_size):
                    files.append(filenames[j])
                    self.progress_bar.setValue(j)
                self.update_progress()
                v[i:i+chunk_size,:,:] = self.read_images(files)
            except IndexError as error:
                pass
        global maximum
        v.maximum = maximum
        return NXentry(NXdata(v,(z,y,x)))