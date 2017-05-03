#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2016, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Module to read in an image file and convert it to NeXus.
"""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import numpy as np
import matplotlib.image as img

from nexusformat.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "Image"

class ImportDialog(BaseImportDialog):
    """Dialog to import an image"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        self.set_layout(self.filebox(), self.buttonbox())
  
        self.setWindowTitle("Import "+str(filetype))
 
    def get_data(self):
        self.import_file = self.get_filename()
        try:
            im = img.imread(self.import_file)
        except IOError as error:
            raise NeXusError(error)
        z = NXfield(im, name='z')
        y = NXfield(range(z.shape[0]), name='y')
        x = NXfield(range(z.shape[1]), name='x')
        if z.ndim > 2:
            rgba = NXfield(range(z.shape[2]), name='rgba')
            return NXentry(NXdata(z, (y,x,rgba)))
        else:        
            return NXentry(NXdata(z, (y,x)))
