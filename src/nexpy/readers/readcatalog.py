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
Module to read in data from a Globus Online catalog and convert it to NeXus.

Each importer needs to layout the GUI buttons necessary for defining the imported file 
and its attributes and a single module, get_data, which returns an NXroot or NXentry
object. This will be added to the NeXpy tree.

Two GUI elements are provided for convenience:

    ImportDialog.filebox: Contains a "Choose File" button and a text box. Both 
                          can be used to set the path to the imported file. This 
                          can be retrieved as a string using self.get_filename().
    ImportDialog.close_buttons: Contains a "Cancel" and "OK" button to close the 
                                dialog. This should be placed at the bottom of 
                                all import dialogs.
"""
import os                           #@UnusedImport

from nexpy.gui.pyqt import QtCore, QtGui

import numpy as np
from nexusformat.nexus import *
from nexpy.gui.importdialog import BaseImportDialog

filetype = "Catalog File"

class ImportDialog(BaseImportDialog):
    """Dialog to import data from a Globus Online catalog"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)
        
        from globusonline.catalog.client.examples.catalog_wrapper import CatalogWrapper
        token_file = os.path.join(os.path.expanduser('~'),'.nexpy',
                                  'globusonline', 'gotoken.txt')
        self.wrap = CatalogWrapper(token='file', token_file=token_file)
        _,self.catalogs = self.wrap.catalogClient.get_catalogs()
        catalog_layout = QtGui.QHBoxLayout()
        self.catalog_box = QtGui.QComboBox()
        for catalog in self.catalogs:
            try:
                self.catalog_box.addItem(catalog['config']['name'])
            except:
                pass
        self.catalog_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        catalog_button = QtGui.QPushButton("Choose Catalog")
        catalog_button.clicked.connect(self.get_catalog)
        catalog_layout.addWidget(self.catalog_box)
        catalog_layout.addWidget(catalog_button)
        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(catalog_layout)
        self.layout.addWidget(self.close_buttons())
        self.setLayout(self.layout)
  
        self.setWindowTitle("Import "+str(filetype))

    def get_catalog(self):
        self.catalog_id = self.get_catalog_id(self.catalog_box.currentText())
        _,self.datasets = self.wrap.catalogClient.get_datasets(self.catalog_id)
        dataset_layout = QtGui.QHBoxLayout()
        self.dataset_box = QtGui.QComboBox()
        for dataset in self.datasets:
            try:
                self.dataset_box.addItem(dataset['name'])
            except:
                pass
        self.dataset_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        dataset_button = QtGui.QPushButton("Choose Dataset")
        dataset_button.clicked.connect(self.get_dataset)
        dataset_layout.addWidget(self.dataset_box)
        dataset_layout.addWidget(dataset_button)
        self.layout.insertLayout(1, dataset_layout)            

    def get_catalog_id(self, name):
        for catalog in self.catalogs:
            if catalog['config']['name']==name:
                return catalog['id']
 
    def get_dataset(self):
        self.dataset_id = self.get_dataset_id(self.dataset_box.currentText())
        _,self.members = self.wrap.catalogClient.get_members(self.catalog_id,
                                                             self.dataset_id)
        member_layout = QtGui.QHBoxLayout()
        self.member_box = QtGui.QComboBox()
        for member in self.members:
            try:
                self.member_box.addItem(member['data_uri'])
            except:
                pass
        self.member_box.setSizeAdjustPolicy(QtGui.QComboBox.AdjustToContents)
        member_button = QtGui.QPushButton("Choose Member")
        member_button.clicked.connect(self.get_member)
        member_layout.addWidget(self.member_box)
        member_layout.addWidget(member_button)            
        self.layout.insertLayout(2, member_layout)            

    def get_dataset_id(self, name):
        for dataset in self.datasets:
            if dataset['name']==name:
                return dataset['id']

    def get_member(self):
        print self.catalog_id, self.dataset_id
        self.wrap.transfer_members(self.catalog_id, self.dataset_id, 
            '/Users/rosborn/Desktop')
 
    def get_data(self):
        return NXentry()
