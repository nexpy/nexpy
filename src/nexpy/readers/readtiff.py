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
Module to read in a TIFF file and convert it to NeXus.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np

from nexusformat.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "TIFF Image"

class ImportDialog(BaseImportDialog):
    """Dialog to import a TIFF image"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
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
