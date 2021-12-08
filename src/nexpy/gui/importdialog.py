# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Base class for import dialogs
"""
from .datadialogs import NXDialog

filetype = "Text File"  # Defines the Import Menu label


class NXImportDialog(NXDialog):
    """Base dialog class for NeXpy import dialogs"""

    def __init__(self, parent=None):

        super().__init__(parent)
        self.default_directory = self.mainwindow.default_directory
        self.import_file = None     # must define in subclass

    def get_data(self):
        """Read the data from the imported file.

        This must be defined in each subclass, defining self.import_file
        as the file name

        :returns: :class:`NXroot` or :class:`NXentry` object
        """
        raise NotImplementedError("must override in subclass")

    def accept(self):
        """Completes importing the data into NeXpy."""
        self.accepted = True
        self.mainwindow.import_data()
        super().accept()


BaseImportDialog = NXImportDialog
