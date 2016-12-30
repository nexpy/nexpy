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

This is an expanded version on the Jupyter QtConsole with the addition
of a Matplotlib plotting pane and a tree view for displaying NeXus data.
"""

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import glob
import imp
import json
import logging
import os
import re
import sys
import webbrowser
import xml.etree.ElementTree as ET
from threading import Thread

from .pyqt import QtGui, QtCore, getOpenFileName, getSaveFileName
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole.inprocess import QtInProcessKernelManager
from IPython.core.magic import magic_escapes

from nexusformat.nexus import (nxload, NeXusError, NXFile, NXobject,
                               NXfield, NXgroup, NXlink, NXroot, NXentry)

from .. import __version__
from .treeview import NXTreeView
from .plotview import NXPlotView, NXProjectionPanels
from .datadialogs import *
from .scripteditor import NXScriptWindow, NXScriptEditor
from .utils import confirm_action, report_error, display_message, timestamp


class NXRichJupyterWidget(RichJupyterWidget):

    def _is_complete(self, source, interactive=True):
        shell = self.kernel_manager.kernel.shell
        status, indent_spaces = shell.input_transformer_manager.check_complete(source)
        if indent_spaces is None:
            indent = ''
        else:
            indent = ' ' * indent_spaces
        return status != 'incomplete', indent


class MainWindow(QtGui.QMainWindow):

    #---------------------------------------------------------------------------
    # 'object' interface
    #---------------------------------------------------------------------------

    _magic_menu_dict = {}


    def __init__(self, app, tree, settings, config):
        """ Create a MainWindow for the application

        Parameters
        ----------

        app : reference to QApplication parent
        tree : :class:`NXTree` object used as the rootr of the :class:`NXTreeView` items
        config : Jupyter configuration
        """

        super(MainWindow, self).__init__()
        self.resize(1000, 800)
        self.app = app
        self._app = app.app
        self._app.setStyle("QMacStyle")
        self.settings = settings
        self.config = config
        self.copied_node = None

        self.default_directory = os.path.expanduser('~')
        self.nexpy_dir = self.app.nexpy_dir
        self.backup_dir = self.app.backup_dir
        self.plugin_dir = self.app.plugin_dir
        self.reader_dir = self.app.reader_dir
        self.script_dir = self.app.script_dir
        self.function_dir = self.app.function_dir
        self.scratch_file = self.app.scratch_file

        mainwindow = QtGui.QWidget()

        rightpane = QtGui.QWidget()

        self.plotview = NXPlotView(label="Main", parent=self)
        self.panels = NXProjectionPanels(self)
        self.panels.setVisible(False)
        self.editors = NXScriptWindow(self)
        self.editors.setVisible(False)

        self.console = NXRichJupyterWidget(config=self.config, parent=rightpane)
        self.console.setMinimumSize(700, 100)
        self.console.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        self.console.resize(727, 223)
        self.console._confirm_exit = True
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

        if 'gui_completion' not in self.config['ConsoleWidget']:
            self.console.gui_completion = 'droplist'
        if 'input_sep' not in self.config['JupyterWidget']:
            self.console.input_sep = ''

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
        self.treeview = NXTreeView(self.tree, parent=self)
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

        self.input_base_classes()

        self.init_menu_bar()

        self.file_filter = ';;'.join((
            "NeXus Files (*.nxs *.nx5 *.h5 *.hdf *.hdf5 *.cxi)",
            "Any Files (*.* *)"))
        self.max_recent_files = 20

        self.setWindowTitle('NeXpy v'+__version__)
        self.statusBar().showMessage('Ready')
        self.console._control.setFocus()

    def close(self):
        """ Called when you quit NeXpy or close the main window.
        """
        title = self.window().windowTitle()
        cancel = QtGui.QMessageBox.Cancel
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
        self.init_plugin_menus()
        self.init_view_menu()
        self.init_magic_menu()
        self.init_window_menu()
        self.init_script_menu()
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

        self.init_recent_menu()

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

        self.reload_action=QtGui.QAction("&Reload",
            self,
            triggered=self.reload
            )
        self.add_menu_action(self.file_menu, self.reload_action, True)

        self.remove_action=QtGui.QAction("Remove",
            self,
            triggered=self.remove
            )
        self.add_menu_action(self.file_menu, self.remove_action, True)

        self.file_menu.addSeparator()

        self.init_import_menu()

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

        self.backup_action=QtGui.QAction("&Backup File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+B"),
            triggered=self.backup_file
            )
        self.add_menu_action(self.file_menu, self.backup_action, True)

        self.restore_action=QtGui.QAction("Restore Backup...",
            self,
            triggered=self.restore_file
            )
        self.add_menu_action(self.file_menu, self.restore_action, True)

        self.manage_backups_action=QtGui.QAction("Manage Backups...",
            self,
            triggered=self.manage_backups
            )
        self.add_menu_action(self.file_menu, self.manage_backups_action, True)

        self.file_menu.addSeparator()

        self.open_scratch_action=QtGui.QAction("Open Scratch File",
            self,
            triggered=self.open_scratch_file
            )
        self.add_menu_action(self.file_menu, self.open_scratch_action, True)

        self.purge_scratch_action=QtGui.QAction("Purge Scratch File",
            self,
            triggered=self.purge_scratch_file
            )
        self.add_menu_action(self.file_menu, self.purge_scratch_action, True)

        self.close_scratch_action=QtGui.QAction("Close Scratch File",
            self,
            triggered=self.close_scratch_file
            )
        self.add_menu_action(self.file_menu, self.close_scratch_action, True)

        self.file_menu.addSeparator()

        self.install_plugin_action=QtGui.QAction("Install Plugin",
            self,
            triggered=self.install_plugin
            )
        self.add_menu_action(self.file_menu, self.install_plugin_action, True)

        self.remove_plugin_action=QtGui.QAction("Remove Plugin",
            self,
            triggered=self.remove_plugin
            )
        self.add_menu_action(self.file_menu, self.remove_plugin_action, True)

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

        self.quit_action = QtGui.QAction("&Quit",
            self,
            shortcut=QtGui.QKeySequence.Quit,
            triggered=self.close,
            )
        # OSX always has Quit in the Application menu, only add it
        # to the File menu elsewhere.
        if sys.platform == 'darwin':
            self.addAction(self.quit_action)
        else:
            self.file_menu.addSeparator()
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

        self.plot_image_action=QtGui.QAction("Plot RGB(A) Image",
            self,
            triggered=self.plot_image
            )
        self.add_menu_action(self.data_menu, self.plot_image_action, True)

        self.data_menu.addSeparator()

        self.view_action=QtGui.QAction("View Data",
            self,
            triggered=self.view_data
            )
        self.add_menu_action(self.data_menu, self.view_action, True)

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

        self.copydata_action=QtGui.QAction("Copy Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+C"),
            triggered=self.copy_data
            )
        self.add_menu_action(self.data_menu, self.copydata_action, True)

        self.pastedata_action=QtGui.QAction("Paste Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+V"),
            triggered=self.paste_data
            )
        self.add_menu_action(self.data_menu, self.pastedata_action, True)

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

        self.default_action=QtGui.QAction("Set Default",
            self,
            triggered=self.set_default
            )
        self.add_menu_action(self.data_menu, self.default_action, True)

        self.data_menu.addSeparator()

        self.fit_action=QtGui.QAction("Fit Data",
            self,
            triggered=self.fit_data
            )
        self.add_menu_action(self.data_menu, self.fit_action, True)

    def init_plugin_menus(self):
        """Add an menu item for every module in the plugin menus"""
        self.plugin_names = set()
        private_path = self.plugin_dir
        if os.path.isdir(private_path):
            for name in os.listdir(private_path):
                if os.path.isdir(os.path.join(private_path, name)):
                    self.plugin_names.add(name)
        public_path = pkg_resources.resource_filename('nexpy', 'plugins')
        for name in os.listdir(public_path):
            if os.path.isdir(os.path.join(public_path, name)):
                self.plugin_names.add(name)
        plugin_paths = [private_path, public_path] # Private path overrides public
        for plugin_name in set(sorted(self.plugin_names)):
            try:
                self.add_plugin_menu(plugin_name, plugin_paths)
            except Exception as error:
                logging.info(
                'The "%s" plugin could not be added to the main menu\n%s%s'
                % (plugin_name, 40*' ', error))

    def add_plugin_menu(self, plugin_name, plugin_paths):
        fp = None
        try:
            fp, pathname, description = imp.find_module(plugin_name, plugin_paths)
            plugin_module = imp.load_module(plugin_name, fp, pathname, description)
            name, actions = plugin_module.plugin_menu()
            plugin_menu = self.menu_bar.addMenu(name)
            for action in actions:
                self.add_menu_action(plugin_menu, QtGui.QAction(
                    action[0], self, triggered=action[1]))
        except Exception as error:
            raise Exception(error)
        finally:
            if fp:
                fp.close()

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

    def init_magic_menu(self):
        self.magic_menu = self.menu_bar.addMenu("&Magic")
        self.magic_menu_separator = self.magic_menu.addSeparator()

        self.all_magic_menu = self._get_magic_menu("AllMagics",
                                                   menulabel="&All Magics...")

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

        self.log_action=QtGui.QAction("Show Log File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+L"),
            triggered=self.show_log
            )
        self.add_menu_action(self.window_menu, self.log_action)

        self.panel_action=QtGui.QAction("Show Projection Panel",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+P"),
            triggered=self.show_projection_panel
            )
        self.add_menu_action(self.window_menu, self.panel_action)

        self.script_window_action=QtGui.QAction("Show Script Editor",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+S"),
            triggered=self.show_script_window
            )
        self.add_menu_action(self.window_menu, self.script_window_action)

        self.window_menu.addSeparator()

        self.limit_action=QtGui.QAction("Change Plot Limits",
            self,
            triggered=self.limit_axes
            )
        self.add_menu_action(self.window_menu, self.limit_action)

        self.reset_limit_action=QtGui.QAction("Reset Plot Limits",
            self,
            triggered=self.reset_axes
            )
        self.add_menu_action(self.window_menu, self.reset_limit_action)

        self.window_menu.addSeparator()

        self.newplot_action=QtGui.QAction("New Plot Window",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+N"),
            triggered=self.new_plot_window
            )
        self.add_menu_action(self.window_menu, self.newplot_action, True)

        self.closewindow_action=QtGui.QAction("Close Plot Window",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+W"),
            triggered=self.close_window
            )
        self.add_menu_action(self.window_menu, self.closewindow_action, True)

        self.window_menu.addSeparator()

        self.equalizewindow_action=QtGui.QAction("Equalize Plot Sizes",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+E"),
            triggered=self.equalize_windows
            )
        self.add_menu_action(self.window_menu, self.equalizewindow_action, True)

        self.window_menu.addSeparator()

        self.active_action = {}

        self.active_action[1]=QtGui.QAction('Main',
            self,
            shortcut=QtGui.QKeySequence("Ctrl+1"),
            triggered=lambda: self.make_active(1),
            checkable=True
            )
        self.add_menu_action(self.window_menu, self.active_action[1])
        self.active_action[1].setChecked(True)
        self.previous_active = 1

        self.window_separator = self.window_menu.addSeparator()

    def init_script_menu(self):
        self.script_menu = self.menu_bar.addMenu("&Script")
        self.new_script_action=QtGui.QAction("New Script...",
            self,
            triggered=self.new_script
            )
        self.add_menu_action(self.script_menu, self.new_script_action)
        self.open_script_action=QtGui.QAction("Open Script...",
            self,
            triggered=self.open_script
            )
        self.add_menu_action(self.script_menu, self.open_script_action)

        self.script_menu.addSeparator()

        self.scripts = {}
        files = os.listdir(self.script_dir)
        for file_name in files:
            if file_name.endswith('.py'):
                self.add_script_action(os.path.join(self.script_dir, file_name))

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

        self.nexusHelpAct = QtGui.QAction("Open NeXus Base Class Definitions Online",
            self,
            triggered=self._open_nexus_online_help)
        self.add_menu_action(self.help_menu, self.nexusHelpAct)

        self.help_menu.addSeparator()

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

        self.help_menu.addSeparator()

        self.example_file_action=QtGui.QAction("Open Example File",
            self,
            triggered=self.open_example_file
            )
        self.add_menu_action(self.help_menu, self.example_file_action, True)

        self.example_script_action=QtGui.QAction("Open Example Script",
            self,
            triggered=self.open_example_script
            )
        self.add_menu_action(self.help_menu, self.example_script_action, True)

    def init_recent_menu(self):
        """Add recent files menu item for recently opened files"""
        recent_files = self.settings.options("recent")
        self.recent_menu = self.file_menu.addMenu("Open Recent")
        self.recent_menu.hovered.connect(self.hover_recent_menu)
        self.recent_file_actions = {}
        for i, recent_file in enumerate(recent_files):
            action = QtGui.QAction(os.path.basename(recent_file), self,
                                   triggered=self.open_recent_file)
            action.setToolTip(recent_file)
            self.add_menu_action(self.recent_menu, action, self)
            self.recent_file_actions[action] = (i, recent_file)

    def init_import_menu(self):
        """Add an import menu item for every module in the readers directory"""
        self.import_names = set()
        self.import_menu = self.file_menu.addMenu("Import")
        private_path = self.reader_dir
        if os.path.isdir(private_path):
            for filename in os.listdir(private_path):
                name, ext = os.path.splitext(filename)
                if name != '__init__' and ext.startswith('.py'):
                    self.import_names.add(name)
        public_path = pkg_resources.resource_filename('nexpy', 'readers')
        for filename in os.listdir(public_path):
            name, ext = os.path.splitext(filename)
            if name != '__init__' and ext.startswith('.py'):
                self.import_names.add(name)
        self.importer = {}
        import_paths = [private_path, public_path]
        for import_name in sorted(self.import_names):
            fp, pathname, description = imp.find_module(import_name, import_paths)
            try:
                import_module = imp.load_module(import_name, fp, pathname, description)
                import_action = QtGui.QAction("Import "+import_module.filetype, self,
                                              triggered=self.show_import_dialog)
                self.add_menu_action(self.import_menu, import_action, self)
                self.importer[import_action] = import_module
            except Exception as error:
                logging.info(
                'The "%s" importer could not be added to the Import menu\n%s%s'
                % (import_name, 40*' ', error))
            finally:
                if fp:
                    fp.close()

    def new_workspace(self):
        try:
            default_name = self.tree.get_new_name()
            name, ok = QtGui.QInputDialog.getText(self, 'New Workspace',
                             'Workspace Name:', text=default_name)
            if name and ok:
                self.tree[name] = NXroot(NXentry())
                self.treeview.select_node(self.tree[name].entry)
                self.treeview.update()
                logging.info("New workspace '%s' created" % name)
        except NeXusError as error:
            report_error("Creating New Workspace", error)

    def open_file(self):
        try:
            fname = getOpenFileName(self, 'Open File (Read Only)',
                                    self.default_directory,  self.file_filter)
            if fname:
                name = self.tree.get_name(fname)
                self.tree[name] = nxload(fname)
                self.treeview.select_node(self.tree[name])
                self.default_directory = os.path.dirname(fname)
                logging.info("NeXus file '%s' opened as workspace '%s'"
                             % (fname, name))
                self.update_recent_files(fname)
        except (NeXusError, IOError) as error:
            report_error("Opening File", error)

    def open_editable_file(self):
        try:
            fname = getOpenFileName(self, 'Open File (Read/Write)',
                                    self.default_directory, self.file_filter)
            if fname:
                name = self.tree.get_name(fname)
                self.tree[name] = nxload(fname, 'rw')
                self.treeview.select_node(self.tree[name])
                self.default_directory = os.path.dirname(fname)
                logging.info("NeXus file '%s' opened (unlocked) as workspace '%s'"
                             % (fname, name))
                self.update_recent_files(fname)
        except (NeXusError, IOError) as error:
            report_error("Opening File (Read/Write)", error)

    def open_recent_file(self):
        try:
            fname = self.recent_file_actions[self.sender()][1]
            name = self.tree.get_name(fname)
            self.tree[name] = nxload(fname)
            self.treeview.select_node(self.tree[name])
            self.default_directory = os.path.dirname(fname)
            logging.info("NeXus file '%s' opened as workspace '%s'"
                         % (fname, name))
            self.update_recent_files(fname)
        except (NeXusError, IOError) as error:
            report_error("Opening Recent File", error)

    def hover_recent_menu(self, action):
        position = QtGui.QCursor.pos()
        position.setX(position.x() + 80)
        QtGui.QToolTip.showText(
            position, self.recent_file_actions[action][1],
            self.recent_menu, self.recent_menu.actionGeometry(action))

    def update_recent_files(self, recent_file):
        recent_files = self.settings.options("recent")
        try:
            recent_files.remove(recent_file)
        except ValueError:
            pass
        recent_files.insert(0, recent_file)
        recent_files = recent_files[:self.max_recent_files]
        for i, recent_file in enumerate(recent_files):
            try:
                action = [k for k, v in self.recent_file_actions.items()
                          if v[0] == i][0]
                action.setText(os.path.basename(recent_file))
                action.setToolTip(recent_file)
            except IndexError:
                action = QtGui.QAction(os.path.basename(recent_file), self,
                                          triggered=self.open_recent_file)
                action.setToolTip(recent_file)
                self.add_menu_action(self.recent_menu, action, self)
            self.recent_file_actions[action] = (i, recent_file)
        self.settings.purge("recent")
        for recent_file in recent_files:
            self.settings.set("recent", recent_file)
        self.settings.save()

    def save_file(self):
        try:
            node = self.treeview.get_node()
            if node is None or not isinstance(node, NXroot):
                raise NeXusError("Only NXroot groups can be saved")
            if node.nxfilemode:
                name = self.tree.get_new_name()
                existing = True
            else:
                name = node.nxname
                existing = False
            default_name = os.path.join(self.default_directory, name)
            fname = getSaveFileName(self, "Choose a Filename", default_name,
                                    self.file_filter)
            if fname:
                old_name = node.nxname
                root = node.save(fname, 'w')
                del self.tree[old_name]
                name = self.tree.get_name(fname)
                self.tree[name] = self.user_ns[name] = root
                self.treeview.select_node(self.tree[name])
                self.treeview.update()
                self.default_directory = os.path.dirname(fname)
                logging.info("NeXus workspace '%s' saved as '%s'"
                             % (old_name, fname))
        except NeXusError as error:
            report_error("Saving File", error)

    def duplicate(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                if node.nxfile:
                    name = self.tree.get_new_name()
                    default_name = os.path.join(self.default_directory,name)
                    fname = getSaveFileName(self, "Choose a Filename",
                                            default_name, self.file_filter)
                    if fname:
                        with NXFile(fname, 'w') as f:
                            f.copyfile(node.nxfile)
                        name = self.tree.get_name(fname)
                        self.tree[name] = nxload(fname)
                        self.default_directory = os.path.dirname(fname)
                        logging.info("Workspace '%s' duplicated in '%s'"
                                     % (node.nxname, fname))
                else:
                    default_name = self.tree.get_new_name()
                    name, ok = QtGui.QInputDialog.getText(self,
                                   "Duplicate Workspace", "Workspace Name:",
                                   text=default_name)
                    if name and ok:
                        self.tree[name] = node
                        logging.info("Workspace '%s' duplicated as workspace '%s'"
                                     % (node.nxname, name))
                if name in self.tree:
                    self.treeview.select_node(self.tree[name])
                    self.treeview.update()
            else:
                raise NeXusError("Only NXroot groups can be duplicated")
        except NeXusError as error:
            report_error("Duplicating File", error)

    def reload(self):
        try:
            node = self.treeview.get_node()
            path = node.nxpath
            root = node.nxroot
            name = root.nxname
            ret = confirm_action("Are you sure you want to reload '%s'?" % name)
            if ret == QtGui.QMessageBox.Ok:
                self.tree.reload(name)
                logging.info("Workspace '%s' reloaded" % name)
                try:
                    self.treeview.select_node(self.tree[name][path])
                except Exception:
                    pass
        except NeXusError as error:
            report_error("Reloading File", error)

    def remove(self):
        try:
            node = self.treeview.get_node()
            name = node.nxname
            if isinstance(node, NXroot):
                ret = confirm_action(
                          "Are you sure you want to remove '%s'?" % name)
                if ret == QtGui.QMessageBox.Ok:
                    del self.tree[name]
                    logging.info("Workspace '%s' removed" % name)
        except NeXusError as error:
            report_error("Removing File", error)

    def show_import_dialog(self):
        try:
            import_module = self.importer[self.sender()]
            self.import_dialog = import_module.ImportDialog(parent=self)
            self.import_dialog.show()
        except NeXusError as error:
            report_error("Importing File", error)

    def import_data(self):
        try:
            if self.import_dialog.accepted:
                imported_data = self.import_dialog.get_data()
                try:
                    name = self.tree.get_name(self.import_dialog.import_file)
                except Exception:
                    name = self.tree.get_new_name()
                if isinstance(imported_data, NXentry):
                    self.tree[name] = self.user_ns[name] = NXroot(imported_data)
                elif isinstance(imported_data, NXroot):
                    self.tree[name] = self.user_ns[name] = imported_data
                else:
                    raise NeXusError(
                        'Imported data must be an NXroot or NXentry group')
                self.treeview.select_node(self.tree[name])
                self.treeview.setFocus()
                try:
                    self.default_directory = os.path.dirname(self.import_dialog.import_file)
                except Exception:
                    pass
                logging.info("Workspace '%s' imported" % name)
        except NeXusError as error:
            report_error("Importing File", error)

    def lock_file(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                node.lock()
                self.treeview.update()
                logging.info("Workspace '%s' locked" % node.nxname)
            else:
                raise NeXusError("Can only lock a NXroot group")
        except NeXusError as error:
            report_error("Locking File", error)

    def unlock_file(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                dialog = UnlockDialog(node, parent=self)
                dialog.show()
                self.treeview.update()
            else:
                raise NeXusError("Can only unlock a NXroot group")
        except NeXusError as error:
            report_error("Unlocking File", error)

    def backup_file(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                dir = os.path.join(self.nexpy_dir, 'backups', timestamp())
                os.mkdir(dir)
                node.backup(dir=dir)
                self.settings.set('backups', node.nxbackup)
                display_message("Workspace '%s' backed up" % node.nxname, 
                                information=node.nxbackup)
                logging.info("Workspace '%s' backed up to '%s'" 
                             % (node.nxname, node.nxbackup))
            else:
                raise NeXusError("Can only backup a NXroot group")
        except NeXusError as error:
            report_error("Backing Up File", error)

    def restore_file(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                ret = confirm_action(
                          "Are you sure you want to restore the file?",
                          "This will overwrite the current contents of '%s'"
                          % node.nxname)
                if ret == QtGui.QMessageBox.Ok:
                    node.restore(overwrite=True)
                    self.treeview.update()
                    logging.info("Workspace '%s' backed up" % node.nxname)
            else:
                raise NeXusError("Can only restore a NXroot group")
        except NeXusError as error:
            report_error("Restoring File", error)

    def manage_backups(self):
        try:
            dialog = ManageBackupsDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Managing Backups", error)

    def open_scratch_file(self):
        try:
            self.tree['w0'] = nxload(self.scratch_file, 'rw')
        except NeXusError as error:
            report_error("Opening Scratch File", error)

    def purge_scratch_file(self):
        try:
            if 'w0' in self.tree:
                ret = confirm_action(
                          "Are you sure you want to purge the scratch file?")
                if ret == QtGui.QMessageBox.Ok:
                    for entry in self.tree['w0'].entries.copy():
                        del self.tree['w0'][entry]
                    logging.info("Workspace 'w0' purged")
        except NeXusError as error:
            report_error("Purging Scratch File", error)

    def close_scratch_file(self):
        try:
            if 'w0' in self.tree:
                ret = confirm_action(
                          "Do you want to delete the scratch file contents?", 
                          answer='no')
                if ret == QtGui.QMessageBox.Yes:
                    for entry in self.tree['w0'].entries.copy():
                        del self.tree['w0'][entry]
                    logging.info("Workspace 'w0' purged")
                del self.tree['w0']
        except NeXusError as error:
            report_error("Purging Scratch File", error)

    def install_plugin(self):
        try:
            dialog = InstallPluginDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Installing Plugin", error)

    def remove_plugin(self):
        try:
            dialog = RemovePluginDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Removing Plugin", error)

    def plot_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                self.treeview.status_message(node)
                if isinstance(node, NXgroup):
                    try:
                        node.plot(fmt='o')
                        return
                    except (KeyError, NeXusError):
                        pass
                if node.is_plottable():
                    dialog = PlotDialog(node, parent=self, fmt='o')
                    dialog.show()
                else:
                    raise NeXusError("Data not plottable")
        except NeXusError as error:
            report_error("Plotting Data", error)

    def overplot_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                self.treeview.status_message(node)
                node.oplot(fmt='o')
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def plot_line(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                self.treeview.status_message(node)
                if isinstance(node, NXgroup):
                    try:
                        node.plot(fmt='-')
                        return
                    except (KeyError, NeXusError):
                        pass
                if node.is_plottable():
                    dialog = PlotDialog(node, parent=self, fmt='-')
                    dialog.show()
                else:
                    raise NeXusError("Data not plottable")
        except NeXusError as error:
            report_error("Plotting Data", error)

    def overplot_line(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                self.treeview.status_message(node)
                node.oplot(fmt='-')
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def plot_image(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                self.treeview.status_message(node)
                node.implot()
        except NeXusError as error:
            report_error("Plotting RGB(A) Image Data", error)

    def view_data(self):
        try:
            node = self.treeview.get_node()
            self.viewdialog = ViewDialog(node, parent=self)
            self.viewdialog.show()
        except NeXusError as error:
            report_error("Viewing Data", error)

    def add_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")
                dialog = AddDialog(node, parent=self)
                dialog.exec_()
            else:
                self.new_workspace()
        except NeXusError as error:
            report_error("Adding Data", error)

    def initialize_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")
                if isinstance(node, NXgroup):
                    dialog = InitializeDialog(node, parent=self)
                    dialog.exec_()
                else:
                    raise NeXusError("An NXfield can only be added to an NXgroup")
        except NeXusError as error:
            report_error("Initializing Data", error)

    def rename_data(self):
        try:
            if self is not None:
                node = self.treeview.get_node()
                if node is not None:
                    if (isinstance(node, NXroot) or 
                           node.nxgroup.nxfilemode != 'r'):
                        path = node.nxpath
                        dialog = RenameDialog(node, parent=self)
                        dialog.exec_()
                        logging.info("'%s' renamed as '%s'"
                                     % (path, node.nxpath))
                    else:
                        raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Renaming Data", error)

    def copy_data(self):
        try:
            node = self.treeview.get_node()
            if not isinstance(node, NXroot):
                self.copied_node = self.treeview.get_node()
                logging.info("'%s' copied" % self.copied_node.nxpath)
            else:
                raise NeXusError("Use 'Duplicate File' to copy an NXroot group")
        except NeXusError as error:
            report_error("Copying Data", error)

    def paste_data(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXgroup) and self.copied_node is not None:
                if node.nxfilemode != 'r':
                    node.insert(self.copied_node)
                    logging.info("'%s' pasted to '%s'"
                                 % (self.copied_node.nxpath, node.nxpath))
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data", error)

    def paste_link(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXgroup) and self.copied_node is not None:
                if node.nxfilemode != 'r':
                    node.makelink(self.copied_node)
                    logging.info("'%s' pasted as link to '%s'"
                                 % (self.copied_node.nxpath, node.nxpath))
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data as Link", error)

    def delete_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if node.nxroot.nxfilemode != 'r':
                    ret = confirm_action('Are you sure you want to delete "%s"?'
                                         % (node.nxroot.nxname+node.nxpath))
                    if ret == QtGui.QMessageBox.Ok:
                        del node.nxgroup[node.nxname]
                        logging.info("'%s' deleted" % 
                                     (node.nxroot.nxname+node.nxpath))
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Deleting Data", error)

    def show_link(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXlink):
                if node.nxfilename and node.nxfilename != node.nxroot.nxfilename:
                    fname = node.nxfilename
                    if not os.path.isabs(fname):
                        fname = os.path.join(os.path.dirname(node.nxroot.nxfilename),
                                             node.nxfilename)
                    name = self.tree.node_from_file(fname)
                    if name is None:
                        name = self.tree.get_name(fname)
                        self.tree[name] = nxload(fname)
                    self.treeview.select_node(self.tree[name][node.nxtarget])
                    self.treeview.setFocus()
                else:
                    self.treeview.select_node(node.nxlink)
                self.treeview.update()
        except NeXusError as error:
            report_error("Showing Link", error)

    def set_signal(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXobject):
                if node.nxfilemode != 'r':
                    dialog = SignalDialog(node, parent=self)
                    dialog.show()
                    logging.info("Signal set for '%s'" % node.nxgroup.nxpath)
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Setting Signal", error)

    def set_default(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXentry) or isinstance(node, NXdata):               
                if node.nxfilemode != 'r':
                    if node.nxgroup is None:
                        raise NeXusError("There is no parent group")
                    if 'default' in node.nxgroup.attrs:
                        ret = confirm_action("Override existing default?")
                        if ret != QtGui.QMessageBox.Ok:
                            return
                    node.nxgroup.attrs['default'] = node.nxname
                    if node.nxgroup in node.nxroot.values():
                        if 'default' not in node.nxroot.attrs:
                            node.nxroot.attrs['default'] = node.nxgroup.nxname
                    logging.info("Default set to '%s'" % node.nxpath)
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Setting Default", error)

    def fit_data(self):
        try:
            try:
                from .fitdialogs import FitDialog
            except ImportError:
                logging.info("The lmfit module is not installed")
                raise NeXusError("Please install the lmfit module")
            node = self.treeview.get_node()
            if node is None:
                return
            elif isinstance(node, NXentry) and node.nxtitle == 'Fit Results':
                entry = node
                if not entry.data.is_plottable():
                    raise NeXusError("NeXus item not plottable")
            elif isinstance(node, NXdata):
                entry = NXentry(data=node)
            else:
                raise NeXusError("Select an NXdata group")
            if len(entry.data.nxsignal.shape) == 1:
                self.fitdialog = FitDialog(entry)
                self.fitdialog.show()
                logging.info("Fitting invoked on'%s'" % node.nxpath)
            else:
                raise NeXusError("Fitting only enabled for one-dimensional data")
        except NeXusError as error:
            report_error("Fitting Data", error)

    def input_base_classes(self):
        base_class_path = pkg_resources.resource_filename(
                              'nexpy', 'definitions/base_classes')
        nxdl_files = map(os.path.basename,
            glob.glob(os.path.join(base_class_path,'*.nxdl.xml')))
        pattern = re.compile(r'[\t\n ]+')
        self.nxclasses = {}
        for nxdl_file in nxdl_files:
            class_name = nxdl_file.split('.')[0]
            xml_root = ET.parse(os.path.join(base_class_path, nxdl_file)).getroot()
            class_doc = ''
            class_groups = {}
            class_fields = {}
            for child in xml_root:
                name = dtype = units = doc = ''
                if child.tag.endswith('doc'):
                    try:
                        class_doc = re.sub(pattern, ' ', child.text).strip()
                    except TypeError:
                        pass
                if child.tag.endswith('field'):
                    try:
                        name = child.attrib['name']
                        dtype = child.attrib['type']
                        units = child.attrib['units']
                    except KeyError:
                        pass
                    for element in child:
                        if element.tag.endswith('doc'):
                            try:
                                doc = re.sub(pattern, ' ', element.text).strip()
                            except TypeError:
                                pass
                    class_fields[name] = (dtype, units, doc)
                elif child.tag.endswith('group'):
                    try:
                        dtype = child.attrib['type']
                        name = child.attrib['name']
                    except KeyError:
                        pass
                    for element in child:
                        if element.tag.endswith('doc'):
                            try:
                                doc = re.sub(pattern, ' ', element.text).strip()
                            except TypeError:
                                pass
                    class_groups[dtype] = (name, doc)
            self.nxclasses[class_name] = (class_doc, class_fields, class_groups)

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
        inner_dynamic_magic.__name__ = str("dynamics_magic_s")
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

        data = display_data['data'].get('application/json', {})
        if isinstance(data, dict):
            mdict = data
        elif isinstance(data, six.text_type):
            mdict = json.loads(data)
        else:
            return

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

    def _get_magic_menu(self, menuidentifier, menulabel=None):
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
                menulabel = re.sub("([a-zA-Z]+)([A-Z][a-z])","\g<1> \g<2>",
                                   menuidentifier)
            menu = QtGui.QMenu(menulabel, self.magic_menu)
            self._magic_menu_dict[menuidentifier]=menu
            self.magic_menu.insertMenu(self.magic_menu_separator,menu)
        return menu

    def make_active_action(self, number, label):
        if label == 'Projection':
            self.active_action[number] = QtGui.QAction(label,
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+P"),
                triggered=lambda: self.plotviews[label].raise_(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        elif label == 'Fit':
            self.active_action[number] = QtGui.QAction(label,
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+F"),
                triggered=lambda: self.plotviews[label].raise_(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        else:
            numbers = [num for num in sorted(self.active_action) if num < 100]
            if number > numbers[-1]:
                before_action = self.window_separator
            else:
                for num in numbers:
                    if num > number:
                        break
                before_action = self.active_action[num]
            self.active_action[number] = QtGui.QAction(label,
                self,
                shortcut=QtGui.QKeySequence("Ctrl+%s" % number),
                triggered=lambda: self.make_active(number),
                checkable=True)
            self.window_menu.insertAction(before_action,
                                          self.active_action[number])
        self.make_active(number)

    def new_plot_window(self):
        plotview = NXPlotView(parent=self)

    def close_window(self):
        from .plotview import plotview
        if plotview.number != 1:
            plotview.close()

    def equalize_windows(self):
        if 'Main' in self.plotviews:
            for label in [label for label in self.plotviews if label != 'Main']:
                self.plotviews[label].resize(self.plotviews['Main'].size())

    def update_active(self, number):
        for num in self.active_action:
            if self.active_action[num].isChecked():
                self.previous_active = num
                self.active_action[num].setChecked(False)
        if number in self.active_action:
            self.active_action[number].setChecked(True)

    def make_active(self, number):
        if number in self.active_action:
            self.update_active(number)
            self.plotviews[self.active_action[number].text()].make_active()

    def limit_axes(self):
        try:
            from .plotview import plotview
            dialog = LimitDialog(parent=self)
            dialog.exec_()
        except NeXusError as error:
            report_error("Changing Plot Limits", error)

    def reset_axes(self):
        try:
            from .plotview import plotview
            plotview.reset_plot_limits()
        except NeXusError as error:
            report_error("Resetting Plot Limits", error)

    def show_log(self):
        try:
            dialog = LogDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Showing Log File", error)

    def show_projection_panel(self):
        from .plotview import plotview
        if plotview.label != 'Projection' and plotview.ndim > 1:
            plotview.ptab.open_panel()
        elif self.panels.tabs.count() != 0:
            self.panels.raise_()

    def show_script_window(self):
        if self.editors.tabs.count() == 0:
            self.new_script()
        else:
            self.editors.setVisible(True)
            self.editors.raise_()

    def new_script(self):
        try:
            file_name = None
            editor = NXScriptEditor(file_name, parent=self)
            self.editors.setVisible(True)
            self.editors.raise_()
            logging.info("Creating new script")
        except NeXusError as error:
            report_error("Editing New Script", error)

    def open_script(self):
        try:
            script_dir = os.path.join(self.nexpy_dir, 'scripts')
            file_filter = ';;'.join(("Python Files (*.py)",
                                         "Any Files (*.* *)"))
            file_name = getOpenFileName(self, 'Open Script', script_dir,
                                        file_filter)
            if file_name:
                editor = NXScriptEditor(file_name, self)
                self.editors.setVisible(True)
                self.editors.raise_()
                logging.info("NeXus script '%s' opened" % file_name)
        except NeXusError as error:
            report_error("Editing Script", error)

    def open_script_file(self):
        try:
            file_name = self.scripts[self.sender()]
            dialog = NXScriptEditor(file_name, self)
            dialog.show()
            self.editors.setVisible(True)
            self.editors.raise_()
            logging.info("NeXus script '%s' opened" % file_name)
        except NeXusError as error:
            report_error("Opening Script", error)

    def add_script_action(self, file_name):
        name = os.path.basename(file_name)
        script_action = QtGui.QAction("Open "+name, self,
                               triggered=self.open_script_file)
        self.add_menu_action(self.script_menu, script_action, self)
        self.scripts[script_action] = file_name

    def remove_script_action(self, file_name):
        for action, name in self.scripts.items():
            if name == file_name:
                self.script_menu.removeAction(action)

    def _open_nexpy_online_help(self):
        filename = "http://nexpy.github.io/nexpy/"
        webbrowser.open(filename, new=1, autoraise=True)

    def _open_nexus_online_help(self):
        filename = "http://download.nexusformat.org/doc/html/classes/base_classes/"
        webbrowser.open(filename, new=1, autoraise=True)

    def _open_ipython_online_help(self):
        filename = "http://ipython.org/ipython-doc/stable/index.html"
        webbrowser.open(filename, new=1, autoraise=True)

    def open_example_file(self):
        default_directory = self.default_directory
        self.default_directory = pkg_resources.resource_filename('nexpy', 
                                                                 'examples')
        self.open_file()
        self.default_directory = default_directory

    def open_example_script(self):
        script_dir = pkg_resources.resource_filename('nexpy', 
                                            os.path.join('examples', 'scripts'))
        file_filter = ';;'.join(("Python Files (*.py)",
                                         "Any Files (*.* *)"))
        file_name = getOpenFileName(self, 'Open Script', script_dir,
                                    file_filter)
        if file_name:
            editor = NXScriptEditor(file_name, self)
            self.editors.setVisible(True)
            self.editors.raise_()
            logging.info("NeXus script '%s' opened" % file_name)

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
            logging.info('NeXpy closed')
            event.accept()
