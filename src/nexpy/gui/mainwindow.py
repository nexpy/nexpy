#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""The Qt MainWindow for NeXpy

This is an expanded version on the iPython QtConsole with the addition
of a Matplotlib plotting pane and a tree view for displaying NeXus data.
"""

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

import imp          #@UnusedImports
import json
import os           #@UnusedImports
import re           #@UnusedImports
import sys          #@UnusedImports
import webbrowser
from threading import Thread

from PySide import QtGui, QtCore
from IPython.core.magic import magic_escapes

def background(f):
    """call a function in a simple thread, to prevent blocking"""
    t = Thread(target=f)
    t.start()
    return t

# local imports
from treeview import NXTreeView
from plotview import NXPlotView
from datadialogs import *           #@UnusedWildImports
from nexpy.api.nexus.tree import nxload, NeXusError, NXFile, NXlink
#from nexpy.api.nexus.tree import NXFile, NXgroup, NXfield, NXroot, NXentry, NXlink

# IPython imports
# require minimum version of IPython for RichIPythonWidget()
import pkg_resources
pkg_resources.require("IPython>="+'1.1.0')
from IPython.qt.console.rich_ipython_widget import RichIPythonWidget
from IPython.qt.inprocess import QtInProcessKernelManager


def report_error(context, error):
    title = type(error).__name__ + ': ' + context
    msgBox = QtGui.QMessageBox()
    msgBox.setText(title)
    msgBox.setInformativeText(str(error))
    msgBox.setStandardButtons(QtGui.QMessageBox.Ok)
    msgBox.setDefaultButton(QtGui.QMessageBox.Ok)
    msgBox.setIcon(QtGui.QMessageBox.Warning)
    return msgBox.exec_()


class MainWindow(QtGui.QMainWindow):

    #---------------------------------------------------------------------------
    # 'object' interface
    #---------------------------------------------------------------------------

    _magic_menu_dict = {}


    def __init__(self, app, tree, config=None):
        """ Create a MainWindow for the application
        
        Parameters
        ----------
        
        app : reference to QApplication parent
        tree : :class:`NXTree` object used as the root of the :class:`NXTreeView` items
        config : IPython configuration
        """

        super(MainWindow, self).__init__()
        self.resize(1000, 800)
        self._app = app
        self._app.setStyle("QMacStyle")
        self.config = config
        self.default_directory = os.path.expanduser('~')
        self.copied_node = None

        mainwindow = QtGui.QWidget()

        rightpane = QtGui.QWidget()

        self.plotview = NXPlotView(label="Main",parent=rightpane)
        self.plotview.setMinimumSize(700, 550)

        self.console = RichIPythonWidget(config=self.config, parent=rightpane)
        self.console.setMinimumSize(700, 100)
        self.console.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        self.console._confirm_exit = True
        self.console.gui_completion = 'droplist'
        self.console.kernel_manager = QtInProcessKernelManager(config=self.config)
        self.console.kernel_manager.start_kernel()
        self.console.kernel_manager.kernel.gui = 'qt4'
        self.console.kernel_client = self.console.kernel_manager.client()
        self.console.kernel_client.start_channels()

        def stop():
            self.console.kernel_client.stop_channels()
            self.console.kernel_manager.shutdown_kernel()
            app.exit()

        self.console.exit_requested.connect(stop)
        self.console.show()

        self.shell = self.console.kernel_manager.kernel.shell
        self.user_ns = self.console.kernel_manager.kernel.shell.user_ns

        right_splitter = QtGui.QSplitter(rightpane)
        right_splitter.setOrientation(QtCore.Qt.Vertical)
        right_splitter.addWidget(self.plotview)
        right_splitter.addWidget(self.console)

        rightlayout = QtGui.QVBoxLayout()        
        rightlayout.addWidget(right_splitter)
        rightlayout.setContentsMargins(0, 0, 0, 0)
        rightpane.setLayout(rightlayout)
        
        self.tree = tree
        self.treeview = NXTreeView(self.tree, parent=mainwindow, mainwindow=self)
        self.treeview.setMinimumWidth(200)
        self.treeview.setMaximumWidth(400)
        self.treeview.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
        self.user_ns['plotview'] = self.plotview
        self.user_ns['plotviews'] = self.plotviews = self.plotview.plotviews
        self.user_ns['treeview'] = self.treeview
        self.user_ns['nxtree'] = self.user_ns['_tree'] = self.tree
        self.user_ns['mainwindow'] = self

        left_splitter = QtGui.QSplitter(mainwindow)
        left_splitter.setOrientation(QtCore.Qt.Horizontal)
        left_splitter.addWidget(self.treeview)
        left_splitter.addWidget(rightpane)

        mainlayout = QtGui.QHBoxLayout()
        mainlayout.addWidget(left_splitter)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainwindow.setLayout(mainlayout)

        self.setCentralWidget(mainwindow)

        self.import_path = pkg_resources.resource_filename('nexpy','readers')

        self.init_menu_bar()

        self.file_filter = ';;'.join((
             "NeXus Files (*.nxs *.nx5 *.h5 *.hdf *.hdf5)",
	         "Any Files (*.* *)"))
        self.setWindowTitle('NeXpy')
        self.statusBar().showMessage('Ready')
        self.console._control.setFocus()

    def close(self):
        """ Called when you quit NeXpy or close the main window.
        """
        title = self.window().windowTitle()
        cancel = QtGui.QMessageBox.Cancel
        okay = QtGui.QMessageBox.Ok         # TODO: unused
        
        msg = "Are you sure you want to quit NeXpy?"
        close = QtGui.QPushButton("&Quit", self)
        close.setShortcut('Q')
        close.clicked.connect(QtCore.QCoreApplication.instance().quit)
        box = QtGui.QMessageBox(QtGui.QMessageBox.Question, title, msg)
        box.addButton(cancel)
        box.addButton(close, QtGui.QMessageBox.YesRole)
        box.setDefaultButton(close)
        box.setEscapeButton(cancel)
        pixmap = QtGui.QPixmap(self._app.icon.pixmap(QtCore.QSize(64,64)))
        box.setIconPixmap(pixmap)
        reply = box.exec_()

        return reply

    # Populate the menu bar with common actions and shortcuts
    def add_menu_action(self, menu, action, defer_shortcut=False):
        """Add action to menu as well as self
        
        So that when the menu bar is invisible, its actions are still available.
        
        If defer_shortcut is True, set the shortcut context to widget-only,
        where it will avoid conflict with shortcuts already bound to the
        widgets themselves.
        """
        menu.addAction(action)
        self.addAction(action)

        if defer_shortcut:
            action.setShortcutContext(QtCore.Qt.WidgetShortcut)
    
    def init_menu_bar(self):
        #create menu in the order they should appear in the menu bar
        self.menu_bar = QtGui.QMenuBar()
        self.init_file_menu()
        self.init_edit_menu()
        self.init_data_menu()
        self.init_view_menu()
        self.init_magic_menu()
        self.init_window_menu()
        self.init_help_menu()
        self.setMenuBar(self.menu_bar)
    
    def init_file_menu(self):
        self.file_menu = self.menu_bar.addMenu("&File")
        
        self.file_menu.addSeparator()

        self.newworkspace_action=QtGui.QAction("&New...",
            self,
            shortcut=QtGui.QKeySequence.New,
            triggered=self.new_workspace
            )
        self.add_menu_action(self.file_menu, self.newworkspace_action, True)  
        
        self.openfile_action=QtGui.QAction("&Open",
            self,
            shortcut=QtGui.QKeySequence.Open,
            triggered=self.open_file
            )
        self.add_menu_action(self.file_menu, self.openfile_action, True)  
        
        self.openeditablefile_action=QtGui.QAction("Open (read/write)",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+O"),
            triggered=self.open_editable_file
            )
        self.addAction(self.openeditablefile_action)  

        self.savefile_action=QtGui.QAction("&Save as...",
            self,
            shortcut=QtGui.QKeySequence.Save,
            triggered=self.save_file
            )
        self.add_menu_action(self.file_menu, self.savefile_action, True)  
        
        self.duplicate_action=QtGui.QAction("&Duplicate...",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+D"),
            triggered=self.duplicate
            )
        self.add_menu_action(self.file_menu, self.duplicate_action, True)  

        self.file_menu.addSeparator()

        self.remove_action=QtGui.QAction("Remove",
            self,
            triggered=self.remove
            )
        self.add_menu_action(self.file_menu, self.remove_action, True)  

        self.file_menu.addSeparator()

        self.lockfile_action=QtGui.QAction("&Lock File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+L"),
            triggered=self.lock_file
            )
        self.add_menu_action(self.file_menu, self.lockfile_action, True)  
        
        self.unlockfile_action=QtGui.QAction("&Unlock File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+U"),
            triggered=self.unlock_file
            )
        self.add_menu_action(self.file_menu, self.unlockfile_action, True)  
        
        self.file_menu.addSeparator()

        self.init_import_menu()
        
        self.file_menu.addSeparator()
        
        printkey = QtGui.QKeySequence(QtGui.QKeySequence.Print)
        if printkey.matches("Ctrl+P") and sys.platform != 'darwin':
            # Only override the default if there is a collision.
            # Qt ctrl = cmd on OSX, so the match gets a false positive on OSX.
            printkey = "Ctrl+Shift+P"
        self.print_action = QtGui.QAction("&Print Shell",
            self,
            shortcut=printkey,
            triggered=self.print_action_console)
        self.add_menu_action(self.file_menu, self.print_action, True)
        
        if sys.platform != 'darwin':
            # OSX always has Quit in the Application menu, only add it
            # to the File menu elsewhere.

            self.file_menu.addSeparator()

            self.quit_action = QtGui.QAction("&Quit",
                self,
                shortcut=QtGui.QKeySequence.Quit,
                triggered=self.close,
            )
            self.add_menu_action(self.file_menu, self.quit_action)

    def init_edit_menu(self):
        self.edit_menu = self.menu_bar.addMenu("&Edit")
        
        self.undo_action = QtGui.QAction("&Undo",
            self,
            shortcut=QtGui.QKeySequence.Undo,
            statusTip="Undo last action if possible",
            triggered=self.undo_console
            )
        self.add_menu_action(self.edit_menu, self.undo_action)

        self.redo_action = QtGui.QAction("&Redo",
            self,
            shortcut=QtGui.QKeySequence.Redo,
            statusTip="Redo last action if possible",
            triggered=self.redo_console)
        self.add_menu_action(self.edit_menu, self.redo_action)

        self.edit_menu.addSeparator()

        self.cut_action = QtGui.QAction("&Cut",
            self,
            shortcut=QtGui.QKeySequence.Cut,
            triggered=self.cut_console
            )
        self.add_menu_action(self.edit_menu, self.cut_action, True)

        self.copy_action = QtGui.QAction("&Copy",
            self,
            shortcut=QtGui.QKeySequence.Copy,
            triggered=self.copy_console
            )
        self.add_menu_action(self.edit_menu, self.copy_action, True)

        self.copy_raw_action = QtGui.QAction("Copy (Raw Text)",
            self,
            triggered=self.copy_raw_console
            )
        self.add_menu_action(self.edit_menu, self.copy_raw_action, True)

        self.paste_action = QtGui.QAction("&Paste",
            self,
            shortcut=QtGui.QKeySequence.Paste,
            triggered=self.paste_console
            )
        self.add_menu_action(self.edit_menu, self.paste_action, True)

        self.edit_menu.addSeparator()
        
        selectall = QtGui.QKeySequence(QtGui.QKeySequence.SelectAll)
        if selectall.matches("Ctrl+A") and sys.platform != 'darwin':
            # Only override the default if there is a collision.
            # Qt ctrl = cmd on OSX, so the match gets a false positive on OSX.
            selectall = "Ctrl+Shift+A"
        self.select_all_action = QtGui.QAction("Select &All",
            self,
            shortcut=selectall,
            triggered=self.select_all_console
            )
        self.add_menu_action(self.edit_menu, self.select_all_action, True)
    
    def init_data_menu(self):
        self.data_menu = self.menu_bar.addMenu("Data")
        
        self.plot_data_action=QtGui.QAction("Plot Data",
            self,
            triggered=self.plot_data
            )
        self.add_menu_action(self.data_menu, self.plot_data_action, True)  
        
        self.overplot_data_action=QtGui.QAction("Overplot Data",
            self,
            triggered=self.overplot_data
            )
        self.add_menu_action(self.data_menu, self.overplot_data_action, True)  

        self.data_menu.addSeparator()

        self.add_action=QtGui.QAction("Add Data",
            self,
            triggered=self.add_data
            )
        self.add_menu_action(self.data_menu, self.add_action, True)  

        self.initialize_action=QtGui.QAction("Initialize Data",
            self,
            triggered=self.initialize_data
            )
        self.add_menu_action(self.data_menu, self.initialize_action, True)  

        self.rename_action=QtGui.QAction("Rename Data",
            self,
            triggered=self.rename_data
            )
        self.add_menu_action(self.data_menu, self.rename_action, True)  

        self.copy_action=QtGui.QAction("Copy Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+C"),
            triggered=self.copy_data
            )
        self.add_menu_action(self.data_menu, self.copy_action, True)  

        self.paste_action=QtGui.QAction("Paste Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+V"),
            triggered=self.paste_data
            )
        self.add_menu_action(self.data_menu, self.paste_action, True)  

        self.pastelink_action=QtGui.QAction("Paste As Link",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+Shift+V"),
            triggered=self.paste_link
            )
        self.add_menu_action(self.data_menu, self.pastelink_action, True)  

        self.delete_action=QtGui.QAction("Delete Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+X"),
            triggered=self.delete_data
            )
        self.add_menu_action(self.data_menu, self.delete_action, True)  

        self.data_menu.addSeparator()
 
        self.link_action=QtGui.QAction("Show Link",
            self,
            triggered=self.show_link
            )
        self.add_menu_action(self.data_menu, self.link_action, True)  

        self.data_menu.addSeparator()
 
        self.signal_action=QtGui.QAction("Set Signal",
            self,
            triggered=self.set_signal
            )
        self.add_menu_action(self.data_menu, self.signal_action, True)  

        self.data_menu.addSeparator()

        self.fit_action=QtGui.QAction("Fit Data",
            self,
            triggered=self.fit_data
            )
        self.add_menu_action(self.data_menu, self.fit_action, True)

        
    def init_view_menu(self):
        self.view_menu = self.menu_bar.addMenu("&View")

        if sys.platform != 'darwin':
            # disable on OSX, where there is always a menu bar
            self.toggle_menu_bar_act = QtGui.QAction("Toggle &Menu Bar",
                self,
                shortcut="Ctrl+Shift+M",
                statusTip="Toggle visibility of menubar",
                triggered=self.toggle_menu_bar)
            self.add_menu_action(self.view_menu, self.toggle_menu_bar_act)
        
        fs_key = "Ctrl+Meta+F" if sys.platform == 'darwin' else "F11"
        self.full_screen_act = QtGui.QAction("&Full Screen",
            self,
            shortcut=fs_key,
            statusTip="Toggle between Fullscreen and Normal Size",
            triggered=self.toggleFullScreen)
        self.add_menu_action(self.view_menu, self.full_screen_act)

        self.view_menu.addSeparator()

        self.increase_font_size = QtGui.QAction("Zoom &In",
            self,
            shortcut=QtGui.QKeySequence.ZoomIn,
            triggered=self.increase_font_size_console
            )
        self.add_menu_action(self.view_menu, self.increase_font_size, True)

        self.decrease_font_size = QtGui.QAction("Zoom &Out",
            self,
            shortcut=QtGui.QKeySequence.ZoomOut,
            triggered=self.decrease_font_size_console
            )
        self.add_menu_action(self.view_menu, self.decrease_font_size, True)

        self.reset_font_size = QtGui.QAction("Zoom &Reset",
            self,
            shortcut="Ctrl+0",
            triggered=self.reset_font_size_console
            )
        self.add_menu_action(self.view_menu, self.reset_font_size, True)

        self.view_menu.addSeparator()

        self.clear_action = QtGui.QAction("&Clear Screen",
            self,
            statusTip="Clear the console",
            triggered=self.clear_magic_console)
        self.add_menu_action(self.view_menu, self.clear_action)

    def init_import_menu(self):
        """Add an import menu item for every module in self.import_path"""
        self.import_names = set()
        self.import_menu = self.file_menu.addMenu("Import")
        private_path = os.path.join(os.path.expanduser('~'), '.nexpy', 'readers')
        if os.path.isdir(private_path):
            sys.path.append(private_path)
            for filename in os.listdir(private_path):
                name, ext = os.path.splitext(filename)
                if name <> '__init__' and ext.startswith('.py'):
                    self.import_names.add(name)
        sys.path.append(self.import_path)
        for filename in os.listdir(self.import_path):
            name, ext = os.path.splitext(filename)
            if name <> '__init__' and ext.startswith('.py'):
                self.import_names.add(name)
        self.importer = {}
        for import_name in sorted(self.import_names):
            fp, pathname, description = imp.find_module(import_name)
            try:
                import_module = imp.load_module(import_name, fp, pathname, description)
            finally:
                if fp:
                    fp.close()
            import_action = QtGui.QAction("Import "+import_module.filetype, self,
                                          triggered=self.show_import_dialog)
            self.add_menu_action(self.import_menu, import_action, self)
            self.importer[import_action] = import_module

    def show_import_dialog(self):
        import_module = self.importer[self.sender()]
        self.import_dialog = import_module.ImportDialog()
        self.import_dialog.show()

    def import_data(self):
        try:
            if self.import_dialog.accepted:
                imported_data = self.import_dialog.get_data()
                try:
                    workspace = self.treeview.tree.get_name(self.import_dialog.import_file)
                except:
                    workspace = self.treeview.tree.get_new_name()
                if isinstance(imported_data, NXentry):
                    self.treeview.tree[workspace] = self.user_ns[workspace] = NXroot(imported_data)
                elif isinstance(imported_data, NXroot):
                    self.treeview.tree[workspace] = self.user_ns[workspace] = imported_data
                else:
                    raise NeXusError('Imported data must be an NXroot or NXentry group')
                self.default_directory = os.path.dirname(self.import_dialog.import_file)
        except NeXusError as error:
            report_error("Importing File", error)

    def new_workspace(self):
        try:
            default_name = self.treeview.tree.get_new_name()
            name, ok = QtGui.QInputDialog.getText(self, 'New Workspace', 
                             'Workspace Name:', text=default_name)        
            if name and ok:
                self.treeview.tree[name] = NXroot(NXentry())
                self.treeview.selectnode(self.treeview.tree[name].entry)
                self.treeview.update()
        except NeXusError as error:
            report_error("Creating New Workspace", error)

    def open_file(self):
        try:
            fname, _ = QtGui.QFileDialog.getOpenFileName(self, 
                           'Open File (Read Only)', self.default_directory, 
                           self.file_filter)
            if fname:
                workspace = self.treeview.tree.get_name(fname)
                self.treeview.tree[workspace] = self.user_ns[workspace] = nxload(fname)
                self.default_directory = os.path.dirname(fname)
        except NeXusError as error:
            report_error("Opening File", error)
  
    def open_editable_file(self):
        try:
            fname, _ = QtGui.QFileDialog.getOpenFileName(self, 
                           'Open File (Read/Write)',
                           self.default_directory, self.file_filter)
            workspace = self.treeview.tree.get_name(fname)
            self.treeview.tree[workspace] = self.user_ns[workspace] = nxload(fname, 'rw')
            self.default_directory = os.path.dirname(fname)
        except NeXusError as error:
            report_error("Opening File (Read/Write)", error)

    def save_file(self):
        try:
            node = self.treeview.getnode()
            if node is None:
                return
            if node.nxfilemode:
                name = self.treeview.tree.get_new_name()
                existing = True
            else:
                name = node.nxname
                existing = False
            default_name = os.path.join(self.default_directory,name)
            dialog = QtGui.QFileDialog()                # TODO: unused
            fname, _ = QtGui.QFileDialog.getSaveFileName(self, 
                           "Choose a Filename", default_name, self.file_filter)
            if fname:
                old_name = node.nxname
                node.save(fname)
                if existing:
                    name = self.treeview.tree.get_name(fname)
                    self.treeview.tree[name] = self.user_ns[name] = nxload(fname, 'rw')
                    del self.treeview.tree[old_name]
                    self.treeview.selectnode(self.treeview.tree[name])
                self.treeview.update()
                self.default_directory = os.path.dirname(fname)
        except NeXusError as error:
            report_error("Saving File", error)

    def duplicate(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXroot):
                if node.nxfilemode:
                    mode = node.nxfilemode              # TODO: unused
                    name = self.treeview.tree.get_new_name()
                    default_name = os.path.join(self.default_directory,name)
                    fname, _ = QtGui.QFileDialog.getSaveFileName(self, 
                                   "Choose a Filename", default_name, 
                                   self.file_filter)
                    if fname:
                        nx_file = NXFile(fname, 'w')
                        nx_file.copyfile(node.nxfile)
                        name = self.treeview.tree.get_name(fname)
                        self.treeview.tree[name] = self.user_ns[name] = nx_file.readfile()                       
                        self.default_directory = os.path.dirname(fname)
                else:
                    default_name = self.treeview.tree.get_new_name()
                    name, ok = QtGui.QInputDialog.getText(self, 
                                   "Duplicate Workspace", "Workspace Name:", 
                                   text=default_name)        
                    if name and ok:
                        self.treeview.tree[name] = node
                self.treeview.selectnode(self.treeview.tree[name])
                self.treeview.update()
            else:
                raise NeXusError("Only NXroot groups can be duplicated")
        except NeXusError as error:
            report_error("Duplicating File", error)

    def remove(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXroot):
                ret = self.confirm_action(
                          "Are you sure you want to remove '%s'?" % node.nxname)
                if ret == QtGui.QMessageBox.Ok:
                    del node.nxgroup[node.nxname]    
        except NeXusError as error:
            report_error("Removing File", error)

    def lock_file(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXroot):
                node.lock()
                self.treeview.update()
        except NeXusError as error:
            report_error("Locking File", error)

    def unlock_file(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXroot):
                ret = self.confirm_action(
                          "Are you sure you want to unlock the file?",
                          "Changes to an unlocked file cannot be reversed")
                if ret == QtGui.QMessageBox.Ok:
                    node.unlock()
                    self.treeview.update()
        except NeXusError as error:
            report_error("Unlocking File", error)

    def plot_data(self, fmt='o'):
        try:
            node = self.treeview.getnode()
            if node:        
                self.treeview.statusmessage(node)
                try:
                    node.plot(fmt)
                except (KeyError, NeXusError):
                    if isinstance(node, NXfield):
                        dialog = PlotDialog(node, self)
                        dialog.show()
        except NeXusError as error:
            report_error("Plotting Data", error)

    def overplot_data(self, fmt='o'):
        try:
            node = self.treeview.getnode()
            if node:        
                self.treeview.statusmessage(node)
                try:
                    node.oplot(fmt)
                except:
                    pass
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def add_data(self):
        try:
            node = self.treeview.getnode()  
            if node:
                if node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")    
                dialog = AddDialog(node, self)
                dialog.show()
            else:
                self.new_workspace()    
        except NeXusError as error:
            report_error("Adding Data", error)

    def initialize_data(self):
        try:
            node = self.treeview.getnode()      
            if node:
                if node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")    
                if isinstance(node, NXgroup):
                    dialog = InitializeDialog(node, self)
                    dialog.show()
                else:
                    raise NeXusError("An NXfield can only be added to an NXgroup")
        except NeXusError as error:
            report_error("Initializing Data", error)

    def rename_data(self):
        if self is not None:
            node = self.treeview.getnode()
            if node:
                if node.nxfilemode != 'r':
                    name, ok = QtGui.QInputDialog.getText(self, 'Rename Data', 
                                   'New Name:', text=node.nxname)        
                    if ok:
                        node.rename(name)
                else:
                    raise NeXusError("NeXus file is locked")  
#        except NeXusError as error:
#            report_error("Renaming Data", error)

    def copy_data(self):
        try:
            node = self.treeview.getnode()
            if not isinstance(node, NXroot):
                self.copied_node = self.treeview.getnode()
            else:
                raise NeXusError("Use 'Duplicate File' to copy an NXroot group")
        except NeXusError as error:
            report_error("Copying Data", error)

    def paste_data(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXgroup) and self.copied_node:
                if node.nxfilemode != 'r':
                    node.insert(self.copied_node)
                else:   
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data", error)
 
    def paste_link(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXgroup) and self.copied_node:
                if node.nxfilemode != 'r':
                    node.makelink(self.copied_node)
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data as Link", error)
 
    def delete_data(self):
        try:
            node = self.treeview.getnode()
            if node:
                if node.nxfilemode != 'r':
                    dialog = DeleteDialog(node, self)
                    dialog.show()
                else:   
                    raise NeXusError("NeXus file is locked") 
        except NeXusError as error:
            report_error("Deleting Data", error)

    def show_link(self):
        try:
            node = self.treeview.getnode()
            if isinstance(node, NXlink):
                self.treeview.selectnode(node.nxlink)
                self.treeview.update()
        except NeXusError as error:
            report_error("Showing Link", error)

    def set_signal(self):
        try:
            node = self.treeview.getnode()
            if node:
                if node.nxfilemode != 'r':
                    if isinstance(node, NXfield) and node.nxgroup:
                        dialog = SignalDialog(node, self)
                        dialog.show()
                    else:
                        raise NeXusError("Only NeXus fields can be a plottable signal")
                else:   
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Setting Signal", error)

    def fit_data(self):
        try:
            node = self.treeview.getnode()
            if node is None:
                return
            try:
                if isinstance(node, NXentry) and node.nxtitle == 'Fit Results':
                    entry = node
                else:
                    raise NameError
            except NameError:
                try:
                    node.plot()
                except KeyError:
                    raise NeXusError("NeXus item not plottable")
                from nexpy.gui.plotview import plotview            
                entry = NXentry(data=plotview.plot.plotdata)
            if len(entry.data.nxsignal.shape) == 1:
                dialog = FitDialog(entry, parent=self)
                dialog.show()
            else:
                raise NeXusError("Fitting only enabled for one-dimensional data")
        except NeXusError as error:
            report_error("Fitting Data", error)

    def confirm_action(self, query, information=None):
        msgBox = QtGui.QMessageBox()
        msgBox.setText(query)
        if information:
            msgBox.setInformativeText(information)
        msgBox.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
        msgBox.setDefaultButton(QtGui.QMessageBox.Ok)
        return msgBox.exec_()
       
    def _make_dynamic_magic(self,magic):
        """Return a function `fun` that will execute `magic` on the console.

        Parameters
        ----------
        magic : string
            string that will be executed as is when the returned function is called

        Returns
        -------
        fun : function
            function with no parameters, when called will execute `magic` on the
            console at call time

        See Also
        --------
        populate_all_magic_menu : generate the "All Magics..." menu

        Notes
        -----
        `fun` execute `magic` the console at the moment it is triggered,
        not the console at the moment it was created.

        This function is mostly used to create the "All Magics..." Menu at run time.
        """
        # need two level nested function to be sure to pass magic
        # to active console **at run time**.
        def inner_dynamic_magic():
            self.console.execute(magic)
        inner_dynamic_magic.__name__ = "dynamics_magic_s"
        return inner_dynamic_magic

    def populate_all_magic_menu(self, display_data=None):
        """Clean "All Magics..." menu and repopulate it with `display_data`

        Parameters
        ----------
        display_data : dict,
            dict of display_data for the magics dict of a MagicsManager.
            Expects json data, as the result of %lsmagic

        """
        for v in self._magic_menu_dict.values():
            v.clear()
        self.all_magic_menu.clear()
        
        if not display_data:
            return
        
        if display_data['status'] != 'ok':
            self.log.warn("%%lsmagic user-expression failed: %s" % display_data)
            return
        
        mdict = json.loads(display_data['data'].get('application/json', {}))
        
        for mtype in sorted(mdict):
            subdict = mdict[mtype]
            prefix = magic_escapes[mtype]
            for name in sorted(subdict):
                mclass = subdict[name]
                magic_menu = self._get_magic_menu(mclass)
                pmagic = prefix + name
                
                # Adding seperate QActions is needed for some window managers
                xaction = QtGui.QAction(pmagic,
                    self,
                    triggered=self._make_dynamic_magic(pmagic)
                    )
                xaction_all = QtGui.QAction(pmagic,
                    self,
                    triggered=self._make_dynamic_magic(pmagic)
                    )
                magic_menu.addAction(xaction)
                self.all_magic_menu.addAction(xaction_all)

    def update_all_magic_menu(self):
        """ Update the list of magics in the "All Magics..." Menu

        Request the kernel with the list of available magics and populate the
        menu with the list received back

        """
        self.console._silent_exec_callback('get_ipython().magic("lsmagic")',
                self.populate_all_magic_menu)

    def _get_magic_menu(self,menuidentifier, menulabel=None):
        """return a submagic menu by name, and create it if needed
       
        parameters:
        -----------

        menulabel : str
            Label for the menu

        Will infere the menu name from the identifier at creation if menulabel not given.
        To do so you have too give menuidentifier as a CamelCassedString
        """
        menu = self._magic_menu_dict.get(menuidentifier,None)
        if not menu :
            if not menulabel:
                menulabel = re.sub("([a-zA-Z]+)([A-Z][a-z])","\g<1> \g<2>",menuidentifier)
            menu = QtGui.QMenu(menulabel,self.magic_menu)
            self._magic_menu_dict[menuidentifier]=menu
            self.magic_menu.insertMenu(self.magic_menu_separator,menu)
        return menu

    def init_magic_menu(self):
        self.magic_menu = self.menu_bar.addMenu("&Magic")
        self.magic_menu_separator = self.magic_menu.addSeparator()
        
        self.all_magic_menu = self._get_magic_menu("AllMagics", menulabel="&All Magics...")

        # This action should usually not appear as it will be cleared when menu
        # is updated at first kernel response. Though, it is necessary when
        # connecting through X-forwarding, as in this case, the menu is not
        # auto updated, SO DO NOT DELETE.
        self.pop = QtGui.QAction("&Update All Magic Menu ",
            self, triggered=self.update_all_magic_menu)
        self.add_menu_action(self.all_magic_menu, self.pop)
        # we need to populate the 'Magic Menu' once the kernel has answer at
        # least once let's do it immediately, but it's assured to works
        self.pop.trigger()

        self.reset_action = QtGui.QAction("&Reset",
            self,
            statusTip="Clear all variables from workspace",
            triggered=self.reset_magic_console)
        self.add_menu_action(self.magic_menu, self.reset_action)

        self.history_action = QtGui.QAction("&History",
            self,
            statusTip="show command history",
            triggered=self.history_magic_console)
        self.add_menu_action(self.magic_menu, self.history_action)

        self.save_action = QtGui.QAction("E&xport History ",
            self,
            statusTip="Export History as Python File",
            triggered=self.save_magic_console)
        self.add_menu_action(self.magic_menu, self.save_action)

        self.who_action = QtGui.QAction("&Who",
            self,
            statusTip="List interactive variables",
            triggered=self.who_magic_console)
        self.add_menu_action(self.magic_menu, self.who_action)

        self.who_ls_action = QtGui.QAction("Wh&o ls",
            self,
            statusTip="Return a list of interactive variables",
            triggered=self.who_ls_magic_console)
        self.add_menu_action(self.magic_menu, self.who_ls_action)

        self.whos_action = QtGui.QAction("Who&s",
            self,
            statusTip="List interactive variables with details",
            triggered=self.whos_magic_console)
        self.add_menu_action(self.magic_menu, self.whos_action)

    def init_window_menu(self):
        self.window_menu = self.menu_bar.addMenu("&Window")
        if sys.platform == 'darwin':
            # add min/maximize actions to OSX, which lacks default bindings.
            self.minimizeAct = QtGui.QAction("Mini&mize",
                self,
                shortcut="Ctrl+m",
                statusTip="Minimize the window/Restore Normal Size",
                triggered=self.toggleMinimized)
            # maximize is called 'Zoom' on OSX for some reason
            self.maximizeAct = QtGui.QAction("&Zoom",
                self,
                shortcut="Ctrl+Shift+M",
                statusTip="Maximize the window/Restore Normal Size",
                triggered=self.toggleMaximized)

            self.add_menu_action(self.window_menu, self.minimizeAct)
            self.add_menu_action(self.window_menu, self.maximizeAct)
            self.window_menu.addSeparator()
        
        self.newplot_action=QtGui.QAction("New Plot Window",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+N"),
            triggered=self.new_plot_window
            )
        self.add_menu_action(self.window_menu, self.newplot_action, True)

        self.window_menu.addSeparator()

        self.active_action = {}
        self.active_action['Main']=QtGui.QAction('Main',
            self,
            shortcut=QtGui.QKeySequence("Ctrl+1"),
            triggered=lambda: self.make_active('Main'),
            checkable=True
            )
        self.add_menu_action(self.window_menu, self.active_action['Main'])
        self.active_action['Main'].setChecked(True)
        self.previous_active = 'Main'

        self.window_separator = self.window_menu.addSeparator()

        self.panel_action=QtGui.QAction("Show Projection Panel",
            self,
            triggered=self.show_projection_panel
            )
        self.add_menu_action(self.window_menu, self.panel_action)

    def make_active_action(self, label, number):
        self.active_action[label]=QtGui.QAction(label,
            self,
            shortcut=QtGui.QKeySequence("Ctrl+%s" % number),
            triggered=lambda: self.make_active(label),
            checkable=True
            )
        self.window_menu.insertAction(self.window_separator, 
                                      self.active_action[label])
        self.make_active(label)

    def new_plot_window(self):
        plotview = NXPlotView()
        
    def update_active(self, name):
        for key in self.active_action.keys():
            if self.active_action[key].isChecked():
                self.previous_active = key
                self.active_action[key].setChecked(False)
        self.active_action[name].setChecked(True)
    
    def make_active(self, name):
        self.update_active(name)
        self.plotviews[name].make_active()

    def show_projection_panel(self):
        from nexpy.gui.plotview import plotview, NXProjectionPanel
        if plotview.ptab.panel:
            plotview.ptab.panel.raise_()
        else:
            plotview.ptab.panel = NXProjectionPanel(plotview=plotview, 
                                                    parent=plotview.ptab)
            plotview.ptab.panel.update_limits()
            plotview.ptab.panel.show()
    
    def init_help_menu(self):
        # please keep the Help menu in Mac Os even if empty. It will
        # automatically contain a search field to search inside menus and
        # please keep it spelled in English, as long as Qt Doesn't support
        # a QAction.MenuRole like HelpMenuRole otherwise it will lose
        # this search field functionality

        self.help_menu = self.menu_bar.addMenu("&Help")      

        # Help Menu

        self.nexpyHelpAct = QtGui.QAction("Open NeXpy &Help Online",
            self,
            triggered=self._open_nexpy_online_help)
        self.add_menu_action(self.help_menu, self.nexpyHelpAct)

        self.ipythonHelpAct = QtGui.QAction("Open iPython Help Online",
            self,
            triggered=self._open_ipython_online_help)
        self.add_menu_action(self.help_menu, self.ipythonHelpAct)

        self.intro_console_action = QtGui.QAction("&Intro to IPython",
            self,
            triggered=self.intro_console
            )
        self.add_menu_action(self.help_menu, self.intro_console_action)

        self.quickref_console_action = QtGui.QAction("IPython &Cheat Sheet",
            self,
            triggered=self.quickref_console
            )
        self.add_menu_action(self.help_menu, self.quickref_console_action)

        self.guiref_console_action = QtGui.QAction("&Qt Console",
            self,
            triggered=self.guiref_console
            )
        self.add_menu_action(self.help_menu, self.guiref_console_action)

    # minimize/maximize/fullscreen actions:

    def toggle_menu_bar(self):
        menu_bar = self.menu_bar
        if menu_bar.isVisible():
            menu_bar.setVisible(False)
        else:
            menu_bar.setVisible(True)

    def toggleMinimized(self):
        if not self.isMinimized():
            self.showMinimized()
        else:
            self.showNormal()

    def _open_nexpy_online_help(self):
        filename="http://nexpy.github.io/nexpy/"
        webbrowser.open(filename, new=1, autoraise=True)

    def _open_ipython_online_help(self):
        filename="http://ipython.org/ipython-doc/stable/index.html"
        webbrowser.open(filename, new=1, autoraise=True)

    def toggleMaximized(self):
        if not self.isMaximized():
            self.showMaximized()
        else:
            self.showNormal()

    # Min/Max imizing while in full screen give a bug
    # when going out of full screen, at least on OSX
    def toggleFullScreen(self):
        if not self.isFullScreen():
            self.showFullScreen()
            if sys.platform == 'darwin':
                self.maximizeAct.setEnabled(False)
                self.minimizeAct.setEnabled(False)
        else:
            self.showNormal()
            if sys.platform == 'darwin':
                self.maximizeAct.setEnabled(True)
                self.minimizeAct.setEnabled(True)

    def set_paging_console(self, paging):
        self.console._set_paging(paging)

    def restart_kernel_console(self):
        self.console.request_restart_kernel()

    def interrupt_kernel_console(self):
        self.console.request_interrupt_kernel()

    def toggle_confirm_restart_console(self):
        widget = self.console
        widget.confirm_restart = not widget.confirm_restart
        self.confirm_restart_kernel_action.setChecked(widget.confirm_restart)

    def update_restart_checkbox(self):
        if self.console is None:
            return
        widget = self.console
        self.confirm_restart_kernel_action.setChecked(widget.confirm_restart)

    def cut_console(self):
        widget = self.console
        if widget.can_cut():
            widget.cut()

    def copy_console(self):
        widget = self.console
        widget.copy()

    def copy_raw_console(self):
        self.console._copy_raw_action.trigger()

    def paste_console(self):
        widget = self.console
        if widget.can_paste():
            widget.paste()

    def undo_console(self):
        self.console.undo()

    def redo_console(self):
        self.console.redo()

    def reset_magic_console(self):
        self.console.execute("%reset")

    def history_magic_console(self):
        self.console.execute("%history")

    def save_magic_console(self):
        self.console.save_magic()

    def clear_magic_console(self):
        self.console.execute("%clear")

    def who_magic_console(self):
        self.console.execute("%who")

    def who_ls_magic_console(self):
        self.console.execute("%who_ls")

    def whos_magic_console(self):
        self.console.execute("%whos")

    def print_action_console(self):
        self.console.print_action.trigger()

    def export_action_console(self):
        self.console.export_action.trigger()

    def select_all_console(self):
        self.console.select_all_action.trigger()

    def increase_font_size_console(self):
        self.console.increase_font_size.trigger()

    def decrease_font_size_console(self):
        self.console.decrease_font_size.trigger()

    def reset_font_size_console(self):
        self.console.reset_font_size.trigger()

    def guiref_console(self):
        self.console.execute("%guiref")

    def intro_console(self):
        self.console.execute("?")

    def quickref_console(self):
        self.console.execute("%quickref")
    #---------------------------------------------------------------------------
    # QWidget interface
    #---------------------------------------------------------------------------

    def closeEvent(self, event):
        """ Confirm NeXpy quit if the window is closed.
        """
        cancel = QtGui.QMessageBox.Cancel
        okay = QtGui.QMessageBox.Ok

        reply = self.close()
        
        if reply == cancel:
            event.ignore()
            return

        if reply == okay:
            event.accept()
