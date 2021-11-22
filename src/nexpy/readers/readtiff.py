#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Module to read in a TIFF file and convert it to NeXus.
"""
import numpy as np
from nexpy.gui.importdialog import NXImportDialog
from nexusformat.nexus import NeXusError, NXdata, NXentry, NXfield

filetype = "TIFF Image"

class ImportDialog(NXImportDialog):
    """Dialog to import a TIFF image"""
 
    def __init__(self, parent=None):

        super().__init__(parent=parent)
        
        self.set_layout(self.filebox(), self.buttonbox())
  
        self.setWindowTitle("Import "+str(filetype))
 
    def get_data(self):
        self.import_file = self.get_filename()
        try:
            import tifffile as TIFF
        except ImportError:
            raise NeXusError("Please install the 'tifffile' module")
        im = TIFF.imread(self.import_file)
        z = NXfield(im, name='z')
        y = NXfield(range(z.shape[0]), name='y')
        x = NXfield(range(z.shape[1]), name='x')
        
        return NXentry(NXdata(z,(y,x)))
