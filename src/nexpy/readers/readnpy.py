# -----------------------------------------------------------------------------
# Copyright (c) 2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Module to read a NumPy file and convert the array(s) to NeXus fields.
"""
import numpy as np
from nexusformat.nexus import NeXusError, NXdata, NXfield

from nexpy.gui.importdialog import NXImportDialog


filetype = "NumPy Arrays"


class ImportDialog(NXImportDialog):

    """Dialog to import NumPy arrays"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)
        self.set_layout(self.filebox(), self.selection_layout())
        self.set_title("Import " + str(filetype))

    def get_data(self):
        try:
            input = np.load(self.import_file)
            output = NXdata()
            if isinstance(input, np.ndarray):
                output['field'] = NXfield(input)
            elif isinstance(input, np.lib.npyio.NpzFile):
                for name in input.files:
                    output[name] = NXfield(input[name])
            return output
        except Exception as error:
            raise NeXusError(f"Error reading {self.import_file}: {error}")
