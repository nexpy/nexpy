Adding a File Importer
======================

.. caution::  This section is under development

These are the basic steps to add a new file format importer to NeXpy.

#. Create a Python source code module named *readabcde.py*
   where *abcde* is the name of the new support and does not 
   conflict with existing names.
#. Place that file in the source code tree, in path
   *<nexpy>/src/nexpy/readers/*
#. Inside that file, create several required structures
   as described below.
#. Create other structure as necessary to support the reader.
#. Provide an example data file (or files) in the 
   *<nexpy>/src/nexpy/examples/* directory and update
   the README.rst file there, describing the new example(s).

.. note:: All new file format importers must be placed
   in the NeXpy source code tree in the *readers* subdirectory.

Required Content
----------------

Start with this basic template:

.. code-block:: python
   :linenos:

   #!/usr/bin/env python 
   # -*- coding: utf-8 -*-
   
   '''describe this importer'''
   
   import numpy as np
   from nexpy.api.nexus import *
   from nexpy.gui.importdialog import BaseImportDialog
   
   filetype = 'my file format'   # these words go in the import menu

   class ImportDialog(BaseImportDialog):
       '''Dialog to import my file format'''
    
       def __init__(self, parent=None):
           super(ImportDialog, self).__init__(parent)

           self.accepted = False
           self.import_file = None     # must set in self.get_data()

           self.set_layout(self.filebox(), self.progress_layout(save=True))
  
           self.set_title("Import "+str(filetype))
 
       def get_data(self):
          '''read the data and return either :class:`NXroot` or :class:`NXentry`'''
          # MUST define self.import_file as chosen file name
          # use convenience method to get from dialog widget
          self.import_file = self.get_filename()
          
          x = range(0,10)     # example data
          y = range(1,11)
          return NXroot(NXentry(NXdata(y,x)))

About the GUI layout
--------------------

Each importer needs to layout the GUI buttons in 
*class ImportDialog(BaseImportDialog)* necessary for defining the imported file 
and its attributes and the single module, *get_data()*, which returns either
an *NXroot* or *NXentry* object. This will be added to the NeXpy tree.

Features from the Superclass
----------------------------

Three GUI convenience elements are provided from the superclass 
:class:`nexpy.gui.importdialog.BaseImportDialog`:

*ImportDialog.filebox*: 
Contains a "Choose File" button and a text box. Both can be 
used to set the path to the imported file. This can be 
retrieved as a string using *self.get_filename()*.

*ImportDialog.close_buttons*: 
Contains a "Cancel" and "OK" button to close the dialog. 
This should be placed at the bottom of all import dialogs.
   