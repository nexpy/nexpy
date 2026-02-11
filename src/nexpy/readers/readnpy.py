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
from pathlib import Path

import numpy as np
from nexusformat.nexus import NeXusError, NXfield, NXgroup
from nexpy.gui.importdialog import NXImportDialog

filetype = "NumPy Arrays"


class ImportDialog(NXImportDialog):

    """Dialog to import NumPy arrays"""

    def __init__(self, parent=None):

        super().__init__(parent=parent)
        self.set_layout(self.filebox(), self.selection_layout())
        self.set_title("Import " + str(filetype))

    def choose_file(self):
        super().choose_file()
        if self.import_file:
            if Path(self.import_file).suffix == '.npz':
                self.unlock_class()
                self.import_class = 'NXcollection'
            elif Path(self.import_file).suffix == '.npy':
                self.import_class = 'NXfield'
                self.lock_class()

    def get_data(self):
        try:
            input = np.load(self.import_file)
            if isinstance(input, np.ndarray):
                return NXfield(input)
            else:
                output = NXgroup(name=self.import_name)
                output.nxclass = self.import_class
                if isinstance(input, np.ndarray):
                    output['field'] = NXfield(input)
                elif isinstance(input, np.lib.npyio.NpzFile):
                    for name in input.files:
                        output[name] = NXfield(input[name])
                return output
        except Exception as error:
            raise NeXusError(f"Error reading {self.import_file}: {error}")
