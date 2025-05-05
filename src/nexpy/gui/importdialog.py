# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Base class for import dialogs
"""
from .widgets import NXDialog

filetype = "Text File"  # Defines the Import Menu label


class NXImportDialog(NXDialog):

    def __init__(self, parent=None):

        """
        Initialize the import dialog base class.

        Parameters
        ----------
        parent : QWidget, optional
            The parent window of the dialog, by default None

        Notes
        -----
        Each subclass must define self.import_file as the file name
        """
        super().__init__(parent)
        self.default_directory = self.mainwindow.default_directory
        self.import_file = None     # must define in subclass

    def get_data(self):
        """
        Read the data and return either a NXroot or NXentry group.

        Notes
        -----
        Must be overridden in subclass.
        """
        raise NotImplementedError("must override in subclass")

    def accept(self):
        """
        Accepts the result.

        This usually needs to be subclassed in each dialog.
        """
        self.accepted = True
        self.mainwindow.import_data()
        super().accept()


BaseImportDialog = NXImportDialog
