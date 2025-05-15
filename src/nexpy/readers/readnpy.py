# -----------------------------------------------------------------------------
# Copyright (c) 2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Module to read in a NumPy file and convert it to NeXus.
"""
from pathlib import Path
import numpy as np
from nexusformat.nexus import NeXusError, NXdata, NXentry, NXfield

from nexpy.gui.importdialog import NXImportDialog

filetype = "NumPy Array"


class ImportDialog(NXImportDialog):

    """Dialog to import a NumPy array"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)
        self.set_layout(self.filebox(), self.buttonbox())
        self.set_title("Import " + str(filetype))

    def get_data(self):
        self.import_file = self.get_filename()
        if not self.import_file:
            raise NeXusError("No file specified")
        elif not Path(self.import_file).exists():
            raise NeXusError(f"File {self.import_file} does not exist")
        try:
            data = NXfield(np.load(self.import_file), name='data')
        except Exception as error:
            raise NeXusError(f"Error reading {self.import_file}: {error}")
        return NXentry(NXdata(data))
