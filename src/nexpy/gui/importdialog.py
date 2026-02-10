# -----------------------------------------------------------------------------
# Copyright (c) 2013-2026, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
Base class for import dialogs
"""
from pathlib import Path

from nexusformat.nexus import NeXusError

from .widgets import NXDialog, NXHierarchicalComboBox, NXLabel, NXLineEdit

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
        self.import_file = None
        self.import_name = None
        self.selection_buttons = self.radiobuttons(
            ('tree', "Save to Tree", True),
            ('selection', "Save to Selection", False))

    def selection_layout(self):
        self.imported_name_box = NXLineEdit()
        main_groups = ['NXdata', 'NXmonitor', 'NXlog', 'NXcollection',
                        'NXparameters']
        other_groups = sorted([g for g in self.mainwindow.nxclasses
                               if g not in main_groups])
        all_groups = main_groups + [''] + other_groups
        self.imported_class_box = NXHierarchicalComboBox(items=all_groups)
        output_layout = self.make_layout(NXLabel("Imported Name"),
                                         self.imported_name_box,
                                         NXLabel("Imported Class"),
                                         self.imported_class_box,
                                         align='justified')
        close_layout = self.make_layout(self.selection_buttons,
                                        self.close_buttons(save=True),
                                        align='justified')
        return self.make_layout(output_layout, close_layout,
                                vertical=True)

    def choose_file(self):
        super().choose_file()
        self.import_file = self.get_filename()
        if not self.import_file:
            raise NeXusError("No file specified")
        elif not Path(self.import_file).exists():
            raise NeXusError(f"File {self.import_file} does not exist")
        else:
            self.import_name = self.import_file

    @property
    def import_name(self):
        try:
            return self.imported_name_box.text()
        except AttributeError:
            return Path(self.import_file).stem if self.import_file else ""

    @import_name.setter
    def import_name(self, name):
        name = Path(name).stem if name else ""
        try:
            self.imported_name_box.setText(name)
        except AttributeError:
            pass

    @property
    def import_class(self):
        try:
            return self.imported_class_box.currentText()
        except AttributeError:
            return "NXdata"

    @property
    def add_tree(self):
        return self.radiobutton['tree'].isChecked()

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
