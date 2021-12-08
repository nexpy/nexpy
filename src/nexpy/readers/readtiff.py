# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Module to read in a TIFF file using 'tifffile' and convert it to NeXus.
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

        self.set_title("Import "+str(filetype))

    def get_data(self):
        self.import_file = self.get_filename()
        if not self.import_file:
            raise NeXusError("No file specified")
        try:
            import tifffile as TIFF
        except ImportError:
            raise NeXusError("Please install the 'tifffile' module")
        im = TIFF.imread(self.import_file)
        z = NXfield(im, name='z')
        y = NXfield(np.arange(z.shape[0], dtype=float), name='y')
        x = NXfield(np.arange(z.shape[1], dtype=float), name='x')

        return NXentry(NXdata(z, (y, x)))
