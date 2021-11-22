#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
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
import glob
import json
import logging
import os
import re
import sys
import webbrowser
import xml.etree.ElementTree as ET
from copy import deepcopy
from operator import attrgetter
from pathlib import Path

from .pyqt import QtCore, QtGui, QtWidgets, getOpenFileName, getSaveFileName

from IPython.core.magic import magic_escapes
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from nexusformat.nexus import *

from .. import __version__
from .datadialogs import *
from .fitdialogs import FitDialog
from .plotview import NXPlotView
from .scripteditor import NXScriptEditor, NXScriptWindow
from .treeview import NXTreeView
from .utils import (confirm_action, display_message, get_colors, get_name,
                    import_plugin, is_file_locked, load_image, natural_sort,
                    report_error, timestamp)


class NXRichJupyterWidget(RichJupyterWidget):

    def _is_complete(self, source, interactive=True):
        shell = self.kernel_manager.kernel.shell
        status, indent_spaces = shell.input_transformer_manager.check_complete(
                                    source)
        if indent_spaces is None:
            indent = ''
        else:
            indent = ' ' * indent_spaces
        return status != 'incomplete', indent


class MainWindow(QtWidgets.QMainWindow):

    _magic_menu_dict = {}

    def __init__(self, app, tree, settings, config):
        """ Create a MainWindow for the application.

        Parameters
        ----------
        app : QApplication instance
            Parent application.
        tree : NXTree instance
            :class:`NXTree` root of the :class:`NXTreeView` items.
        settings : NXConfigParser instance
            ConfigParser instance for accessing the NeXpy settings file.
        config : JupyterApp.config_file
        """

        super().__init__()
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
        self.settings_file = self.app.settings_file

        mainwindow = QtWidgets.QWidget()

        rightpane = QtWidgets.QWidget()

        self.dialogs = []
        self.panels = {}
        main_plotview = NXPlotView(label="Main", parent=self)
        self.log_window = None
        self._memroot = None

        self.console = NXRichJupyterWidget(config=self.config, parent=rightpane)
        self.console.setMinimumSize(750, 100)
        self.console.setSizePolicy(QtWidgets.QSizePolicy.Expanding, 
                                   QtWidgets.QSizePolicy.Fixed)
        self.console._confirm_exit = True
        self.console.kernel_manager = QtInProcessKernelManager(
                                          config=self.config)
        self.console.kernel_manager.start_kernel()
        self.console.kernel_manager.kernel.gui = 'qt'
        self.console.kernel_client = self.console.kernel_manager.client()
        self.console.kernel_client.start_channels()
        self.console.exit_requested.connect(self.close)
        self.console.show()

        self.shellview = self.console._control
        self.shellview.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.kernel = self.console.kernel_manager.kernel
        self.shell = self.kernel.shell
        self.user_ns = self.console.kernel_manager.kernel.shell.user_ns
        self.shell.ask_exit = self.close
        self.shell._old_stb = self.shell._showtraceback
        try:
            self.shell.set_hook('complete_command', nxcompleter, 
                                re_key=r"(?:.*\=)?(?:.*\()?(?:.*,)?(.+?)\[")
        except NameError:
            pass
        def new_stb(etype, evalue, stb):
            self.shell._old_stb(etype, evalue, [stb[-1]])
            self.shell._last_traceback = stb
        self.shell._showtraceback = new_stb

        right_splitter = QtWidgets.QSplitter(rightpane)
        right_splitter.setOrientation(QtCore.Qt.Vertical)
        right_splitter.addWidget(main_plotview)
        right_splitter.addWidget(self.console)

        rightlayout = QtWidgets.QVBoxLayout()
        rightlayout.addWidget(right_splitter)
        rightlayout.setContentsMargins(0, 0, 0, 0)
        rightpane.setLayout(rightlayout)

        self.tree = tree
        self.treeview = NXTreeView(self.tree, parent=self)
        self.treeview.setMinimumWidth(200)
        self.treeview.setMaximumWidth(400)
        self.treeview.setSizePolicy(QtWidgets.QSizePolicy.Preferred, 
                                    QtWidgets.QSizePolicy.Expanding)
        self.user_ns['plotview'] = self.plotview
        self.user_ns['plotviews'] = self.plotviews = self.plotview.plotviews
        self.user_ns['treeview'] = self.treeview
        self.user_ns['nxtree'] = self.user_ns['_tree'] = self.tree
        self.user_ns['mainwindow'] = self

        left_splitter = QtWidgets.QSplitter(mainwindow)
        left_splitter.setOrientation(QtCore.Qt.Horizontal)
        left_splitter.addWidget(self.treeview)
        left_splitter.addWidget(rightpane)

        mainlayout = QtWidgets.QHBoxLayout()
        mainlayout.addWidget(left_splitter)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainwindow.setLayout(mainlayout)

        self.setCentralWidget(mainwindow)

        self.input_base_classes()

        self.init_menu_bar()

        self.file_filter = ';;'.join((
            "NeXus Files (*.nxs *.nx5 *.nxspe *.h5 *.hdf *.hdf5 *.cxi)",
            "Any Files (*.* *)"))
        self.max_recent_files = 20

        self.setWindowTitle('NeXpy v'+__version__)
        self.statusBar().showMessage('Ready')

        self.treeview.selection_changed()
        self.shellview.setFocus()

    @property
    def plotview(self):
        from .plotview import plotview
        return plotview
        
    @property
    def active_plotview(self):
        from .plotview import active_plotview
        return active_plotview
        
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
        else:
            action.setShortcutContext(QtCore.Qt.ApplicationShortcut)

    def init_menu_bar(self):
        #create menu in the order they should appear in the menu bar
        self.menu_bar = QtWidgets.QMenuBar()
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

        self.newworkspace_action=QtWidgets.QAction("&New...",
            self,
            shortcut=QtGui.QKeySequence.New,
            triggered=self.new_workspace
            )
        self.add_menu_action(self.file_menu, self.newworkspace_action)

        self.openfile_action=QtWidgets.QAction("&Open",
            self,
            shortcut=QtGui.QKeySequence.Open,
            triggered=self.open_file
            )
        self.add_menu_action(self.file_menu, self.openfile_action)

        self.openeditablefile_action=QtWidgets.QAction("Open (read/write)",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+O"),
            triggered=self.open_editable_file
            )
        self.addAction(self.openeditablefile_action)

        self.init_recent_menu()

        self.openimage_action=QtWidgets.QAction("Open Image...",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+O"),
            triggered=self.open_image
            )
        self.add_menu_action(self.file_menu, self.openimage_action)

        self.opendirectory_action=QtWidgets.QAction("Open Directory...",
            self,
            triggered=self.open_directory
            )
        self.add_menu_action(self.file_menu, self.opendirectory_action)

        try:
            import h5pyd
            self.openremotefile_action=QtWidgets.QAction("Open Remote...",
                self,
                triggered=self.open_remote_file
                )
            self.add_menu_action(self.file_menu, self.openremotefile_action)            
        except ImportError:
            pass

        self.savefile_action=QtWidgets.QAction("&Save as...",
            self,
            shortcut=QtGui.QKeySequence.Save,
            triggered=self.save_file
            )
        self.add_menu_action(self.file_menu, self.savefile_action)

        self.duplicate_action=QtWidgets.QAction("&Duplicate...",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+D"),
            triggered=self.duplicate
            )
        self.add_menu_action(self.file_menu, self.duplicate_action)

        self.file_menu.addSeparator()

        self.restore_action=QtWidgets.QAction("Restore Session",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+R"),
            triggered=self.restore_session
            )
        self.add_menu_action(self.file_menu, self.restore_action)

        self.file_menu.addSeparator()

        self.reload_action=QtWidgets.QAction("&Reload",
            self,
            triggered=self.reload
            )
        self.add_menu_action(self.file_menu, self.reload_action)

        self.reload_all_action=QtWidgets.QAction("Reload All",
            self,
            triggered=self.reload_all
            )
        self.add_menu_action(self.file_menu, self.reload_all_action)

        self.remove_action=QtWidgets.QAction("Remove",
            self,
            triggered=self.remove
            )
        self.add_menu_action(self.file_menu, self.remove_action)

        self.remove_all_action=QtWidgets.QAction("Remove All",
            self,
            triggered=self.remove_all
            )
        self.add_menu_action(self.file_menu, self.remove_all_action)

        self.file_menu.addSeparator()

        self.collapse_action=QtWidgets.QAction("Collapse Tree",
            self,
            triggered=self.collapse_tree
            )
        self.add_menu_action(self.file_menu, self.collapse_action)

        self.file_menu.addSeparator()

        self.init_import_menu()

        self.file_menu.addSeparator()

        self.export_action=QtWidgets.QAction("Export",
            self,
            triggered=self.export_data
            )
        self.add_menu_action(self.file_menu, self.export_action)

        self.file_menu.addSeparator()

        self.lockfile_action=QtWidgets.QAction("&Lock File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+L"),
            triggered=self.lock_file
            )
        self.add_menu_action(self.file_menu, self.lockfile_action)

        if sys.platform == 'darwin':
            #This maps onto Cmd+U on a Mac. On other systems, this clashes with 
            #the Ctrl+U command-line editing shortcut.
            unlock_shortcut = QtGui.QKeySequence("Ctrl+U")
        else:
            unlock_shortcut = QtGui.QKeySequence("Ctrl+Shift+U")
        self.unlockfile_action=QtWidgets.QAction("&Unlock File",
            self,
            shortcut=unlock_shortcut,
            triggered=self.unlock_file
            )
        self.add_menu_action(self.file_menu, self.unlockfile_action)

        self.file_menu.addSeparator()

        self.backup_action=QtWidgets.QAction("&Backup File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+B"),
            triggered=self.backup_file
            )
        self.add_menu_action(self.file_menu, self.backup_action)

        self.restore_action=QtWidgets.QAction("Restore Backup...",
            self,
            triggered=self.restore_file
            )
        self.add_menu_action(self.file_menu, self.restore_action)

        self.manage_backups_action=QtWidgets.QAction("Manage Backups...",
            self,
            triggered=self.manage_backups
            )
        self.add_menu_action(self.file_menu, self.manage_backups_action)

        self.file_menu.addSeparator()

        self.open_scratch_action=QtWidgets.QAction("Open Scratch File",
            self,
            triggered=self.open_scratch_file
            )
        self.add_menu_action(self.file_menu, self.open_scratch_action)

        self.purge_scratch_action=QtWidgets.QAction("Purge Scratch File",
            self,
            triggered=self.purge_scratch_file
            )
        self.add_menu_action(self.file_menu, self.purge_scratch_action)

        self.close_scratch_action=QtWidgets.QAction("Close Scratch File",
            self,
            triggered=self.close_scratch_file
            )
        self.add_menu_action(self.file_menu, self.close_scratch_action)

        self.file_menu.addSeparator()

        self.install_plugin_action=QtWidgets.QAction("Install Plugin...",
            self,
            triggered=self.install_plugin
            )
        self.add_menu_action(self.file_menu, self.install_plugin_action)

        self.remove_plugin_action=QtWidgets.QAction("Remove Plugin...",
            self,
            triggered=self.remove_plugin
            )
        self.add_menu_action(self.file_menu, self.remove_plugin_action)

        self.restore_plugin_action=QtWidgets.QAction("Restore Plugin...",
            self,
            triggered=self.restore_plugin
            )
        self.add_menu_action(self.file_menu, self.restore_plugin_action)

        self.file_menu.addSeparator()

        self.preferences_action=QtWidgets.QAction("Edit Preferences",
            self,
            triggered=self.edit_preferences
            )
        self.add_menu_action(self.file_menu, self.preferences_action)

        self.quit_action = QtWidgets.QAction("&Quit",
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

        self.undo_action = QtWidgets.QAction("&Undo",
            self,
            shortcut=QtGui.QKeySequence.Undo,
            statusTip="Undo last action if possible",
            triggered=self.undo_console
            )
        self.add_menu_action(self.edit_menu, self.undo_action, True)

        self.redo_action = QtWidgets.QAction("&Redo",
            self,
            shortcut=QtGui.QKeySequence.Redo,
            statusTip="Redo last action if possible",
            triggered=self.redo_console)
        self.add_menu_action(self.edit_menu, self.redo_action, True)

        self.edit_menu.addSeparator()

        self.cut_action = QtWidgets.QAction("&Cut",
            self,
            shortcut=QtGui.QKeySequence.Cut,
            triggered=self.cut_console
            )
        self.add_menu_action(self.edit_menu, self.cut_action, True)

        self.copy_action = QtWidgets.QAction("&Copy",
            self,
            shortcut=QtGui.QKeySequence.Copy,
            triggered=self.copy_console
            )
        self.add_menu_action(self.edit_menu, self.copy_action, True)

        self.copy_raw_action = QtWidgets.QAction("Copy (Raw Text)",
            self,
            triggered=self.copy_raw_console
            )
        self.add_menu_action(self.edit_menu, self.copy_raw_action)

        self.paste_action = QtWidgets.QAction("&Paste",
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
        self.select_all_action = QtWidgets.QAction("Select &All",
            self,
            shortcut=selectall,
            triggered=self.select_all_console
            )
        self.add_menu_action(self.edit_menu, self.select_all_action, True)

        self.edit_menu.addSeparator()

        self.print_action = QtWidgets.QAction("Print Shell",
            self,
            triggered=self.print_action_console)
        self.add_menu_action(self.edit_menu, self.print_action, True)


    def init_data_menu(self):
        self.data_menu = self.menu_bar.addMenu("Data")

        self.plot_data_action=QtWidgets.QAction("&Plot Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+P"),
            triggered=self.plot_data
            )
        self.add_menu_action(self.data_menu, self.plot_data_action)

        self.plot_line_action=QtWidgets.QAction("Plot Line",
            self,
            triggered=self.plot_line
            )

        self.overplot_data_action=QtWidgets.QAction("Overplot Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+P"),
            triggered=self.overplot_data
            )
        self.add_menu_action(self.data_menu, self.overplot_data_action)

        self.overplot_line_action=QtWidgets.QAction("Overplot Line",
            self,
            triggered=self.overplot_line
            )

        self.multiplot_data_action=QtWidgets.QAction("Plot All Signals",
            self,
            triggered=self.multiplot_data
            )
        self.add_menu_action(self.data_menu, self.multiplot_data_action)

        self.multiplot_lines_action=QtWidgets.QAction(
            "Plot All Signals as Lines",
            self,
            triggered=self.multiplot_lines
            )

        self.plot_weighted_data_action=QtWidgets.QAction("Plot Weighted Data",
            self,
            triggered=self.plot_weighted_data
            )
        self.add_menu_action(self.data_menu, self.plot_weighted_data_action)

        self.plot_image_action=QtWidgets.QAction("Plot RGB(A) Image",
            self,
            triggered=self.plot_image
            )
        self.add_menu_action(self.data_menu, self.plot_image_action)

        self.data_menu.addSeparator()

        self.view_action=QtWidgets.QAction("View Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+V"),
            triggered=self.view_data
            )
        self.add_menu_action(self.data_menu, self.view_action)

        self.add_action=QtWidgets.QAction("Add Data",
            self,
            triggered=self.add_data
            )
        self.add_menu_action(self.data_menu, self.add_action)

        self.initialize_action=QtWidgets.QAction("Initialize Data",
            self,
            triggered=self.initialize_data
            )
        self.add_menu_action(self.data_menu, self.initialize_action)

        self.rename_action=QtWidgets.QAction("Rename Data",
            self,
            triggered=self.rename_data
            )
        self.add_menu_action(self.data_menu, self.rename_action)

        self.copydata_action=QtWidgets.QAction("Copy Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+C"),
            triggered=self.copy_data
            )
        self.add_menu_action(self.data_menu, self.copydata_action)

        self.cutdata_action=QtWidgets.QAction("Cut Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+X"),
            triggered=self.cut_data
            )
        self.add_menu_action(self.data_menu, self.cutdata_action)

        self.pastedata_action=QtWidgets.QAction("Paste Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+V"),
            triggered=self.paste_data
            )
        self.add_menu_action(self.data_menu, self.pastedata_action)

        self.pastelink_action=QtWidgets.QAction("Paste As Link",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+V"),
            triggered=self.paste_link
            )
        self.add_menu_action(self.data_menu, self.pastelink_action)

        self.delete_action=QtWidgets.QAction("Delete Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+X"),
            triggered=self.delete_data
            )
        self.add_menu_action(self.data_menu, self.delete_action)

        self.data_menu.addSeparator()

        self.link_action=QtWidgets.QAction("Show Link",
            self,
            triggered=self.show_link
            )
        self.add_menu_action(self.data_menu, self.link_action)

        self.data_menu.addSeparator()

        self.signal_action=QtWidgets.QAction("Set Signal",
            self,
            triggered=self.set_signal
            )
        self.add_menu_action(self.data_menu, self.signal_action)

        self.default_action=QtWidgets.QAction("Set Default",
            self,
            triggered=self.set_default
            )
        self.add_menu_action(self.data_menu, self.default_action)

        self.data_menu.addSeparator()

        self.fit_action=QtWidgets.QAction("Fit Data",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+F"),
            triggered=self.fit_data
            )
        self.add_menu_action(self.data_menu, self.fit_action)

    def init_plugin_menus(self):
        """Add an menu item for every module in the plugin menus"""
        self.plugin_names = set()
        private_path = self.plugin_dir
        if os.path.isdir(private_path):
            for name in os.listdir(private_path):
                if (os.path.isdir(os.path.join(private_path, name)) and
                    not (name.startswith('_') or name.startswith('.'))):
                    self.plugin_names.add(name)
        public_path = pkg_resources.resource_filename('nexpy', 'plugins')
        for name in os.listdir(public_path):
            if (os.path.isdir(os.path.join(public_path, name)) and
                not (name.startswith('_') or name.startswith('.'))):
                self.plugin_names.add(name)
        plugin_paths = [private_path, public_path]
        for plugin_name in set(sorted(self.plugin_names)):
            try:
                self.add_plugin_menu(plugin_name, plugin_paths)
            except Exception as error:
                logging.info(
                'The "%s" plugin could not be added to the main menu\n%s%s'
                % (plugin_name, 33*' ', error))

    def add_plugin_menu(self, plugin_name, plugin_paths):
        plugin_module = import_plugin(plugin_name, plugin_paths)
        name, actions = plugin_module.plugin_menu()
        plugin_menu = self.menu_bar.addMenu(name)
        for action in actions:
            self.add_menu_action(plugin_menu, QtWidgets.QAction(
                action[0], self, triggered=action[1]))

    def init_view_menu(self):
        self.view_menu = self.menu_bar.addMenu("&View")

        if sys.platform != 'darwin':
            # disable on OSX, where there is always a menu bar
            self.toggle_menu_bar_act = QtWidgets.QAction("Toggle &Menu Bar",
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+M"),
                statusTip="Toggle visibility of menubar",
                triggered=self.toggle_menu_bar)
            self.add_menu_action(self.view_menu, self.toggle_menu_bar_act)

        fs_key = "Ctrl+Meta+F" if sys.platform == 'darwin' else "F11"
        self.full_screen_act = QtWidgets.QAction("&Full Screen",
            self,
            shortcut=fs_key,
            statusTip="Toggle between Fullscreen and Normal Size",
            triggered=self.toggleFullScreen)
        self.add_menu_action(self.view_menu, self.full_screen_act)

        self.view_menu.addSeparator()

        self.increase_font_size = QtWidgets.QAction("Zoom &In",
            self,
            shortcut=QtGui.QKeySequence.ZoomIn,
            triggered=self.increase_font_size_console
            )
        self.add_menu_action(self.view_menu, self.increase_font_size, True)

        self.decrease_font_size = QtWidgets.QAction("Zoom &Out",
            self,
            shortcut=QtGui.QKeySequence.ZoomOut,
            triggered=self.decrease_font_size_console
            )
        self.add_menu_action(self.view_menu, self.decrease_font_size, True)

        self.reset_font_size = QtWidgets.QAction("Zoom &Reset",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+0"),
            triggered=self.reset_font_size_console
            )
        self.add_menu_action(self.view_menu, self.reset_font_size, True)

        self.view_menu.addSeparator()

        self.clear_action = QtWidgets.QAction("&Clear Screen",
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
        self.pop = QtWidgets.QAction("&Update All Magic Menu ",
            self, triggered=self.update_all_magic_menu)
        self.add_menu_action(self.all_magic_menu, self.pop)
        # we need to populate the 'Magic Menu' once the kernel has answer at
        # least once let's do it immediately, but it's assured to works
        self.pop.trigger()

        self.reset_action = QtWidgets.QAction("&Reset",
            self,
            statusTip="Clear all variables from workspace",
            triggered=self.reset_magic_console)
        self.add_menu_action(self.magic_menu, self.reset_action)

        self.history_action = QtWidgets.QAction("&History",
            self,
            statusTip="show command history",
            triggered=self.history_magic_console)
        self.add_menu_action(self.magic_menu, self.history_action)

        self.save_action = QtWidgets.QAction("E&xport History ",
            self,
            statusTip="Export History as Python File",
            triggered=self.save_magic_console)
        self.add_menu_action(self.magic_menu, self.save_action)

        self.who_action = QtWidgets.QAction("&Who",
            self,
            statusTip="List interactive variables",
            triggered=self.who_magic_console)
        self.add_menu_action(self.magic_menu, self.who_action)

        self.who_ls_action = QtWidgets.QAction("Wh&o ls",
            self,
            statusTip="Return a list of interactive variables",
            triggered=self.who_ls_magic_console)
        self.add_menu_action(self.magic_menu, self.who_ls_action)

        self.whos_action = QtWidgets.QAction("Who&s",
            self,
            statusTip="List interactive variables with details",
            triggered=self.whos_magic_console)
        self.add_menu_action(self.magic_menu, self.whos_action)

    def init_window_menu(self):
        self.window_menu = self.menu_bar.addMenu("&Window")
        if sys.platform == 'darwin':
            # add min/maximize actions to OSX, which lacks default bindings.
            self.minimizeAct = QtWidgets.QAction("Mini&mize",
                self,
                shortcut=QtGui.QKeySequence("Ctrl+m"),
                statusTip="Minimize the window/Restore Normal Size",
                triggered=self.toggleMinimized)
            # maximize is called 'Zoom' on OSX for some reason
            self.maximizeAct = QtWidgets.QAction("&Zoom",
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+M"),
                statusTip="Maximize the window/Restore Normal Size",
                triggered=self.toggleMaximized)

            self.add_menu_action(self.window_menu, self.minimizeAct)
            self.add_menu_action(self.window_menu, self.maximizeAct)
            self.window_menu.addSeparator()

        self.tree_action=QtWidgets.QAction("Show Tree",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+T"),
            triggered=self.show_tree
            )
        self.add_menu_action(self.window_menu, self.tree_action)

        self.shell_action=QtWidgets.QAction("Show IPython Shell",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+I"),
            triggered=self.show_shell
            )
        self.add_menu_action(self.window_menu, self.shell_action)

        self.window_menu.addSeparator()

        self.log_action=QtWidgets.QAction("Show Log File",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+L"),
            triggered=self.show_log
            )
        self.add_menu_action(self.window_menu, self.log_action)

        self.script_window_action=QtWidgets.QAction("Show Script Editor",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+S"),
            triggered=self.show_script_window
            )
        self.add_menu_action(self.window_menu, self.script_window_action)

        self.window_menu.addSeparator()

        self.customize_action=QtWidgets.QAction("Show Customize Panel",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+C"),
            triggered=self.show_customize_panel
            )
        self.add_menu_action(self.window_menu, self.customize_action)

        self.limit_action=QtWidgets.QAction("Show Limits Panel",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+L"),
            triggered=self.show_limits_panel
            )
        self.add_menu_action(self.window_menu, self.limit_action)

        self.panel_action=QtWidgets.QAction("Show Projection Panel",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+P"),
            triggered=self.show_projection_panel
            )
        self.add_menu_action(self.window_menu, self.panel_action)

        self.scan_action=QtWidgets.QAction("Show Scan Panel",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+S"),
            triggered=self.show_scan_panel
            )
        self.add_menu_action(self.window_menu, self.scan_action)

        self.window_menu.addSeparator()

        self.show_all_limits_action=QtWidgets.QAction("Show All Limits",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+L"),
            triggered=self.show_all_limits
            )
        self.add_menu_action(self.window_menu, self.show_all_limits_action)

        self.reset_limit_action=QtWidgets.QAction("Reset Plot Limits",
            self,
            triggered=self.reset_axes
            )
        self.add_menu_action(self.window_menu, self.reset_limit_action)

        self.window_menu.addSeparator()

        self.newplot_action=QtWidgets.QAction("New Plot Window",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+N"),
            triggered=self.new_plot_window
            )
        self.add_menu_action(self.window_menu, self.newplot_action)

        self.closewindow_action=QtWidgets.QAction("Close Plot Window",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+W"),
            triggered=self.close_window
            )
        self.add_menu_action(self.window_menu, self.closewindow_action,)

        self.window_menu.addSeparator()

        self.equalizewindow_action=QtWidgets.QAction("Equalize Plot Sizes",
            self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+E"),
            triggered=self.equalize_windows
            )
        self.add_menu_action(self.window_menu, self.equalizewindow_action)

        self.window_menu.addSeparator()

        self.active_action = {}

        self.active_action[1]=QtWidgets.QAction('Main',
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
        self.new_script_action=QtWidgets.QAction("New Script...",
            self,
            triggered=self.new_script
            )
        self.add_menu_action(self.script_menu, self.new_script_action)
        self.open_script_action = QtWidgets.QAction("Open Script...",
            self,
            triggered=self.open_script
            )
        self.add_menu_action(self.script_menu, self.open_script_action)
        self.open_startup_script_action = QtWidgets.QAction(
            "Open Startup Script...",
            self,
            triggered=self.open_startup_script
            )
        self.add_menu_action(self.script_menu, self.open_startup_script_action)

        self.script_menu.addSeparator()

        self.scripts = {}
        self.add_script_directory(self.script_dir, self.script_menu)

    def init_help_menu(self):
        # please keep the Help menu in Mac Os even if empty. It will
        # automatically contain a search field to search inside menus and
        # please keep it spelled in English, as long as Qt Doesn't support
        # a QAction.MenuRole like HelpMenuRole otherwise it will lose
        # this search field functionality

        self.help_menu = self.menu_bar.addMenu("&Help")

        # Help Menu

        self.nexpyHelpAct = QtWidgets.QAction("Open NeXpy &Help Online",
            self,
            triggered=self._open_nexpy_online_help)
        self.add_menu_action(self.help_menu, self.nexpyHelpAct)

        self.notebookHelpAct = QtWidgets.QAction("Open NeXus API Tutorial Online",
            self,
            triggered=self._open_nexusformat_online_notebook)
        self.add_menu_action(self.help_menu, self.notebookHelpAct)

        self.nexusHelpAct = QtWidgets.QAction(
            "Open NeXus Base Class Definitions Online",
            self,
            triggered=self._open_nexus_online_help)
        self.add_menu_action(self.help_menu, self.nexusHelpAct)

        self.help_menu.addSeparator()

        self.ipythonHelpAct = QtWidgets.QAction("Open iPython Help Online",
            self,
            triggered=self._open_ipython_online_help)
        self.add_menu_action(self.help_menu, self.ipythonHelpAct)

        self.intro_console_action = QtWidgets.QAction("&Intro to IPython",
            self,
            triggered=self.intro_console
            )
        self.add_menu_action(self.help_menu, self.intro_console_action)

        self.quickref_console_action = QtWidgets.QAction("IPython &Cheat Sheet",
            self,
            triggered=self.quickref_console
            )
        self.add_menu_action(self.help_menu, self.quickref_console_action)

        self.help_menu.addSeparator()

        self.example_file_action=QtWidgets.QAction("Open Example File",
            self,
            triggered=self.open_example_file
            )
        self.add_menu_action(self.help_menu, self.example_file_action)

        self.example_script_action=QtWidgets.QAction("Open Example Script",
            self,
            triggered=self.open_example_script
            )
        self.add_menu_action(self.help_menu, self.example_script_action)

    def init_recent_menu(self):
        """Add recent files menu item for recently opened files"""
        recent_files = self.settings.options('recent')
        self.recent_menu = self.file_menu.addMenu("Open Recent")
        self.recent_menu.hovered.connect(self.hover_recent_menu)
        self.recent_file_actions = {}
        for i, recent_file in enumerate(recent_files):
            action = QtWidgets.QAction(os.path.basename(recent_file), self,
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
            try:
                import_module = import_plugin(import_name, import_paths)
                import_action = QtWidgets.QAction(
                    "Import "+import_module.filetype, self,
                    triggered=self.show_import_dialog)
                self.add_menu_action(self.import_menu, import_action, self)
                self.importer[import_action] = import_module
            except Exception as error:
                logging.info(
                'The "%s" importer could not be added to the Import menu\n%s%s'
                % (import_name, 33*' ', error))

    def new_workspace(self):
        try:
            dialog = NewDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Creating New Workspace", error)

    def load_file(self, fname, wait=5, recent=True):
        if fname in [self.tree[root].nxfilename for root in self.tree]:
            raise NeXusError('File already open')
            return
        elif not os.path.exists(fname):
            raise NeXusError("'%s' does not exist" % fname)
        elif is_file_locked(fname, wait=wait):
            logging.info("NeXus file '%s' is locked by an external process." 
                         % fname)
            return
        name = self.tree.get_name(fname)
        if Path(self.backup_dir) in Path(fname).parents:
            name = name.replace('_backup', '')
            self.tree[name] = nxload(fname, 'rw')
        else:
            self.tree[name] = nxload(fname)
            self.default_directory = os.path.dirname(fname)
        self.treeview.update()
        self.treeview.select_node(self.tree[name])
        self.treeview.setFocus()
        logging.info("NeXus file '%s' opened as workspace '%s'" % (fname, name))
        self.update_files(fname, recent=recent)

    def open_file(self):
        try:
            fname = getOpenFileName(self, 'Open File (Read Only)',
                                    self.default_directory,  self.file_filter)
            if fname:
                self.load_file(fname)
        except NeXusError as error:
            report_error("Opening File", error)

    def open_editable_file(self):
        try:
            fname = getOpenFileName(self, 'Open File (Read/Write)',
                                    self.default_directory, self.file_filter)
            if fname:
                self.load_file(fname)
        except NeXusError as error:
            report_error("Opening File (Read/Write)", error)

    def open_recent_file(self):
        try:
            fname = self.recent_file_actions[self.sender()][1]
            self.load_file(fname)
        except NeXusError as error:
            report_error("Opening Recent File", error)

    def open_image(self):
        try:
            file_filter = ';;'.join(("Any Files (*.* *)",
                                     "TIFF Files (*.tiff *.tif)",
                                     "CBF Files (*.cbf)",
                                     "JPEG/PNG Files (*.jpg *.jpeg *.png)"))
            fname = getOpenFileName(self, 'Open Image File',
                                    self.default_directory, file_filter)
            if fname is None or not os.path.exists(fname):
                return
            data = load_image(fname)
            if 'images' not in self.tree:
                self.tree['images'] = NXroot()  
            name = get_name(fname, self.tree['images'].entries)
            self.tree['images'][name] = data
            node = self.tree['images'][name]
            self.treeview.select_node(node)
            self.treeview.setFocus()
            self.default_directory = os.path.dirname(fname)
            logging.info("Image file '%s' opened as 'images%s'" 
                         % (fname, node.nxpath))
        except NeXusError as error:
            report_error("Opening Image File", error)

    def open_directory(self):
        try:
            directory = self.default_directory
            directory = QtWidgets.QFileDialog.getExistingDirectory(self, 
                        'Choose Directory', directory)
            if directory is None or not os.path.exists(directory):
                return
            tree_files = [self.tree[root].nxfilename for root in self.tree]
            nxfiles = sorted([f for f in os.listdir(directory) 
                              if ((f.endswith('.nxs') or f.endswith('.nx5') or
                                   f.endswith('.h5') or f.endswith('hdf5') or
                                   f.endswith('hdf') or f.endswith('.cxi') or
                                   f.endswith('nxspe')) and
                              os.path.join(directory, f) not in tree_files and
                              not os.path.islink(os.path.join(directory, f)))],
                             key=natural_sort)
            if len(nxfiles) == 0:
                raise NeXusError("No NeXus files found in directory")
            dialog = DirectoryDialog(nxfiles, directory, parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Opening Directory", error)

    def open_remote_file(self):
        try:
            dialog = RemoteDialog(parent=self)
            dialog.setModal(False)
            dialog.show()
        except NeXusError as error:
            report_error("Opening Remote File", error)

    def hover_recent_menu(self, action):
        position = QtGui.QCursor.pos()
        position.setX(position.x() + 80)
        QtWidgets.QToolTip.showText(
            position, self.recent_file_actions[action][1],
            self.recent_menu, self.recent_menu.actionGeometry(action))

    def update_files(self, filename, recent=True):
        if recent:
            recent_files = self.settings.options('recent')
            try:
                recent_files.remove(filename)
            except ValueError:
                pass
            recent_files.insert(0, filename)
            recent_files = recent_files[:self.max_recent_files]
            for i, recent_file in enumerate(recent_files):
                try:
                    action = [k for k, v in self.recent_file_actions.items()
                              if v[0] == i][0]
                    action.setText(os.path.basename(recent_file))
                    action.setToolTip(recent_file)
                except IndexError:
                    action = QtWidgets.QAction(os.path.basename(recent_file), 
                                               self,
                                               triggered=self.open_recent_file)
                    action.setToolTip(recent_file)
                    self.add_menu_action(self.recent_menu, action, self)
                self.recent_file_actions[action] = (i, recent_file)
            self.settings.purge('recent')
            for recent_file in recent_files:
                self.settings.set('recent', recent_file)
        self.settings.set('session', filename)
        self.settings.save()

    def save_file(self):
        try:
            node = self.treeview.get_node()
            if node is None or not isinstance(node, NXroot):
                raise NeXusError("Only NXroot groups can be saved")
            name = node.nxname
            default_name = os.path.join(self.default_directory, name)
            fname = getSaveFileName(self, "Choose a Filename", default_name,
                                    self.file_filter)
            if fname:
                old_name = node.nxname
                old_fname = node.nxfilename
                if node.nxfilemode == 'r':
                    nxduplicate(old_fname, fname, 'w')
                    root = nxload(fname)
                else:
                    root = node.save(fname, 'w')
                del self.tree[old_name]
                name = self.tree.get_name(fname)
                self.tree[name] = self.user_ns[name] = root
                self.treeview.select_node(self.tree[name])
                self.treeview.update()
                self.default_directory = os.path.dirname(fname)
                self.settings.remove_option('recent', old_fname)
                self.settings.remove_option('session', old_fname)
                self.update_files(fname)
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
                    default_name = os.path.join(self.default_directory, name)
                    fname = getSaveFileName(self, "Choose a Filename",
                                            default_name, self.file_filter)
                    if fname:
                        if is_file_locked(fname):
                            return
                        with NXFile(fname, 'w') as f:
                            f.copyfile(node.nxfile)
                        logging.info("Workspace '%s' duplicated in '%s'"
                                     % (node.nxname, fname))
                        self.load_file(fname)
                else:
                    default_name = self.tree.get_new_name()
                    name, ok = QtWidgets.QInputDialog.getText(self,
                                   "Duplicate Workspace", "Workspace Name:",
                                   text=default_name)
                    if name and ok:
                        self.tree[name] = node
                        logging.info(
                            "Workspace '%s' duplicated as workspace '%s'"
                            % (node.nxname, name))
                if name in self.tree:
                    self.treeview.select_node(self.tree[name])
                    self.treeview.update()
            else:
                raise NeXusError("Only NXroot groups can be duplicated")
        except NeXusError as error:
            report_error("Duplicating File", error)

    def read_session(self):
        self.previous_session = self.settings.options('session')
        self.settings.purge('session')
        self.settings.save()

    def restore_session(self):
        for filename in self.previous_session:
            try:
                self.load_file(filename, recent=False)
            except Exception:
                pass
        self.treeview.select_top()

    def reload(self):
        try:
            node = self.treeview.get_node()
            if not node.file_exists():
                raise NeXusError("%s does not exist" % node.nxfilename)
            elif self.nodefile_locked(node):
                return
            path = node.nxpath
            root = node.nxroot
            name = root.nxname
            if confirm_action("Are you sure you want to reload '%s'?" % name):
                root.reload()
                logging.info("Workspace '%s' reloaded" % name)
                try:
                    self.treeview.select_node(self.tree[name][path])
                except Exception:
                    pass
        except NeXusError as error:
            report_error("Reloading File", error)

    def reload_all(self):
        try:
            if not confirm_action("Reload all modified files?"):
                return
            for name in self.tree:
                node = self.tree[name]
                if node.is_modified():
                    path = node.nxpath
                    root = node.nxroot
                    root.reload()
                    logging.info("'%s' reloaded" % name)
                self.treeview.select_top()
        except NeXusError as error:
            report_error("Reloading All Modified Files", error)

    def remove(self):
        try:
            node = self.treeview.get_node()
            name = node.nxname
            if isinstance(node, NXroot):
                if confirm_action("Are you sure you want to remove '%s'?" 
                                  % name):
                    del self.tree[name]
                    self.settings.remove_option('session', node.nxfilename)
                    self.settings.save()
                    logging.info("'%s' removed from tree" % name)
        except NeXusError as error:
            report_error("Removing File", error)

    def remove_all(self):
        try:
            if not confirm_action("Remove all files?"):
                return
            for name in list(self.tree):
                fname = self.tree[name].nxfilename
                del self.tree[name]
                self.settings.remove_option('session', fname)
                self.settings.save()
                logging.info("'%s' removed from tree" % name)
        except NeXusError as error:
            report_error("Removing All Files", error)

    def collapse_tree(self):
        self.treeview.collapse()

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
                    self.default_directory = os.path.dirname(
                                                self.import_dialog.import_file)
                except Exception:
                    pass
                logging.info("Workspace '%s' imported" % name)
        except NeXusError as error:
            report_error("Importing File", error)

    def export_data(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXdata):
                dialog = ExportDialog(node, parent=self)
                dialog.show()
            else:
                raise NeXusError("Can only export an NXdata group")                  
        except NeXusError as error:
            report_error("Exporting Data", error)

    def lock_file(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot) and node.nxfilemode:
                node.lock()
                self.treeview.update()
                logging.info("Workspace '%s' locked" % node.nxname)
            else:
                raise NeXusError("Can only lock a saved NXroot group")
        except NeXusError as error:
            report_error("Locking File", error)

    def unlock_file(self):
        try:
            node = self.treeview.get_node()
            if not (isinstance(node, NXroot) and node.nxfilemode):
                raise NeXusError("Can only unlock a saved NXroot group")
            elif not node.file_exists():
                raise NeXusError("'%s' does not exist" % node.nfilename)
            elif node.is_modified():
                if confirm_action("File has been modified. Reload?"):
                    node.reload()
                else:
                    return
            elif self.nodefile_locked(node):
                return
            dialog = UnlockDialog(node, parent=self)
            dialog.show()
            self.treeview.update()
        except NeXusError as error:
            report_error("Unlocking File", error)

    def nodefile_locked(self, node):
        return is_file_locked(node.nxfile.filename)

    def backup_file(self):
        try:
            node = self.treeview.get_node()
            if node is not None and not node.file_exists():
                raise NeXusError("%s does not exist" % node.nxfilename)
            if isinstance(node, NXroot):
                dir = os.path.join(self.nexpy_dir, 'backups', timestamp())
                os.mkdir(dir)
                node.backup(dir=dir)
                self.settings.set('backups', node.nxbackup)
                self.settings.save()
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
                if confirm_action("Are you sure you want to restore the file?",
                        "This will overwrite the current contents of '%s'" 
                        % node.nxname):
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
                if confirm_action(
                        "Are you sure you want to purge the scratch file?"):
                    for entry in self.tree['w0'].entries.copy():
                        del self.tree['w0'][entry]
                    logging.info("Workspace 'w0' purged")
        except NeXusError as error:
            report_error("Purging Scratch File", error)

    def close_scratch_file(self):
        try:
            if 'w0' in self.tree:
                if confirm_action(
                        "Do you want to delete the scratch file contents?", 
                        answer='no'):
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

    def restore_plugin(self):
        try:
            dialog = RestorePluginDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Restoring Plugin", error)

    def plot_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                self.treeview.status_message(node)
                if isinstance(node, NXgroup) and node.plottable_data:
                    try:
                        node.plot()
                        self.plotview.make_active()
                        return
                    except KeyError:
                        pass
                elif node.is_plottable():
                    dialog = PlotDialog(node, parent=self)
                    dialog.show()
                elif (isinstance(node, NXfield) and 
                      node.size == 1 and node.is_numeric()):
                    dialog = PlotScalarDialog(node, parent=self)
                    dialog.show()
                else:
                    raise NeXusError("Data not plottable")
        except NeXusError as error:
            report_error("Plotting Data", error)

    def overplot_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                self.treeview.status_message(node)
                node.oplot()
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def plot_line(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                self.treeview.status_message(node)
                if isinstance(node, NXgroup) and node.plottable_data:
                    try:
                        node.plot(marker='None', linestyle='-')
                        self.plotview.make_active()
                    except (KeyError, NeXusError):
                        pass
                elif node.is_plottable():
                    dialog = PlotDialog(node, parent=self, lines=True)
                    dialog.show()
                else:
                    raise NeXusError("Data not plottable")
        except NeXusError as error:
            report_error("Plotting Data", error)

    def overplot_line(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                self.treeview.status_message(node)
                node.oplot(marker='None', linestyle='-')
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def multiplot_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                elif not isinstance(node, NXgroup):
                    raise NeXusError("Multiplots only available for groups.")
                elif 'auxiliary_signals' not in node.attrs:
                    raise NeXusError(
                        "Group must have the 'auxiliary_signals' attribute.")
                self.treeview.status_message(node)
                signals = [node.nxsignal]
                signals.extend([node[signal] for signal 
                                in node.attrs['auxiliary_signals']])
                colors = get_colors(len(signals))
                for i, signal in enumerate(signals):
                    if i == 0:
                        signal.plot(color=colors[i])
                    else:
                        signal.oplot(color=colors[i])
                self.plotview.otab.home()
                self.plotview.legend(signal=True)
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting Data", error)

    def multiplot_lines(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                elif not isinstance(node, NXgroup):
                    raise NeXusError("Multiplots only available for groups.")
                elif 'auxiliary_signals' not in node.attrs:
                    raise NeXusError(
                        "Group must have the 'auxiliary_signals' attribute.")
                self.treeview.status_message(node)
                signals = [node.nxsignal]
                signals.extend([node[signal] for signal 
                                in node.attrs['auxiliary_signals']])
                colors = get_colors(len(signals))
                for i, signal in enumerate(signals):
                    if i == 0:
                        signal.plot(marker='None', linestyle='-', 
                                    color=colors[i])
                    else:
                        signal.oplot(marker='None', linestyle='-',
                                     color=colors[i])
                self.plotview.otab.home()
                self.plotview.legend(signal=True)
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting Data", error)

    def plot_weighted_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                self.treeview.status_message(node)
                node.plot(weights=True)
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting Weighted Data", error)

    def plot_image(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                self.treeview.status_message(node)
                node.implot()
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting RGB(A) Image Data", error)

    def view_data(self):
        try:
            node = self.treeview.get_node()
            if not self.panel_is_running('View'):
                self.panels['View'] = ViewDialog()
            self.panels['View'].activate(node)
        except NeXusError as error:
            report_error("Viewing Data", error)

    def add_data(self):
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                elif node.nxfilemode == 'r':
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
                if not node.exists():
                    raise NeXusError("%s does not exist" % node.nxfullpath)
                elif node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")
                elif isinstance(node, NXgroup):
                    dialog = InitializeDialog(node, parent=self)
                    dialog.exec_()
                else:
                    raise NeXusError(
                                "An NXfield can only be added to an NXgroup")
        except NeXusError as error:
            report_error("Initializing Data", error)

    def rename_data(self):
        try:
            if self is not None:
                node = self.treeview.get_node()
                if node is not None:
                    if not node.exists():
                        raise NeXusError("%s does not exist" % node.nxfullpath)
                    elif (isinstance(node, NXroot) or 
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

    def copy_node(self, node):
        import tempfile
        self._memroot = nxload(tempfile.mkstemp(suffix='.nxs')[1], mode='w',
                               driver='core', backing_store=False)
        self._memroot['entry'] = NXentry()
        if isinstance(node, NXlink):
            node = node.nxlink
        self._memroot['entry'][node.nxname] = node
        self._memroot['entry'].attrs['link'] = [node.nxname, node.nxpath, 
                                                str(node.nxfilename)]
        return self._memroot['entry'][node.nxname]

    @property
    def copied_link(self):
        try:
            return self._memroot['entry'].attrs['link']
        except Exception:
            return None

    def copy_data(self):
        try:
            node = self.treeview.get_node()
            if not isinstance(node, NXroot):
                self.copied_node = self.copy_node(node)
                logging.info("'%s' copied" % node.nxpath)
            else:
                raise NeXusError("Use 'Duplicate File' to copy an NXroot group")
        except NeXusError as error:
            report_error("Copying Data", error)

    def cut_data(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                raise NeXusError("Cannot cut an NXroot group")
            elif node.nxgroup.is_external():
                raise NeXusError(
                    "Cannot cut object in an externally linked group")
            elif node.nxgroup.nxfilemode and node.nxgroup.nxfilemode == 'r':
                raise NeXusError("NeXus file is locked")
            else:
                if confirm_action("Are you sure you want to cut '%s'?"
                                  % (node.nxroot.nxname+node.nxpath)):
                    self.copied_node = self.copy_node(node)
                    logging.info("'%s' cut" % node.nxpath)
                    del node.nxgroup[node.nxname]
        except NeXusError as error:
            report_error("Cutting Data", error)

    def paste_data(self):
        try:
            node = self.treeview.get_node()
            if node.nxfilemode and node.nxfilemode == 'r':
                raise NeXusError("NeXus file is locked")
            elif isinstance(node, NXfield):
                raise NeXusError("Cannot only paste into a NeXus group")
            elif isinstance(node, NXgroup):
                if self.copied_node is None:
                    raise NeXusError("No data in the copy buffer")
                if node.nxfilemode != 'r':
                    dialog = PasteDialog(node, parent=self)
                    dialog.show()
                    logging.info("'%s' pasted to '%s'"
                                 % (self.copied_node.nxpath, node.nxpath))
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data", error)

    def paste_link(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXgroup) and self.copied_link is not None:
                if node.nxfilemode != 'r':
                    dialog = PasteDialog(node, link=True, parent=self)
                    dialog.show()
                    logging.info("'%s' pasted as link to '%s'"
                                 % (self.copied_node.nxpath, node.nxpath))
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data as Link", error)

    def delete_data(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot) and node.nxfilemode:
                raise NeXusError("Cannot delete a NeXus file")
            elif node.nxgroup.is_external():
                raise NeXusError(
                    "Cannot delete object in an externally linked group")
            elif node.nxgroup.nxfilemode and node.nxgroup.nxfilemode == 'r':
                raise NeXusError("NeXus file is locked")
            elif confirm_action("Are you sure you want to delete '%s'?"
                                % (node.nxroot.nxname+node.nxpath)):
                del node.nxgroup[node.nxname]
                logging.info("'%s' deleted" % (node.nxroot.nxname+node.nxpath))
        except NeXusError as error:
            report_error("Deleting Data", error)

    def show_link(self):
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXlink):
                if (node.nxfilename and 
                    node.nxfilename != node.nxroot.nxfilename):
                    fname = node.nxfilename
                    if not os.path.isabs(fname):
                        fname = os.path.join(
                            os.path.dirname(node.nxroot.nxfilename),
                            node.nxfilename)
                    if not os.path.exists(fname):
                        raise NeXusError("External file does not exist")
                    name = self.tree.node_from_file(fname)
                    if name is None:
                        name = self.tree.get_name(fname)
                        self.tree[name] = nxload(fname)
                    self.treeview.select_node(self.tree[name][node.nxtarget])
                    self.treeview.setFocus()
                elif node.nxlink is not None:
                    self.treeview.select_node(node.nxlink)
                else:
                    raise NeXusError("Cannot resolve link")
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
                    elif node.nxgroup.get_default():
                        if not confirm_action("Override existing default?"):
                            return
                    node.set_default()
                    logging.info("Default set to '%s'" % node.nxpath)
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Setting Default", error)

    def fit_data(self):
        try:
            node = self.treeview.get_node()
            if node is None:
                return
            elif ((isinstance(node, NXentry) or isinstance(node, NXprocess)) and 
                  node.nxtitle.startswith('Fit')):
                if 'data' in node and node['data'].ndim > 1:
                    raise NeXusError(
                                "Fitting only enabled for one-dimensional data")
            elif isinstance(node, NXdata):
                if node.ndim > 1:
                    raise NeXusError(
                                "Fitting only enabled for one-dimensional data")
            else:
                raise NeXusError("Select an NXdata group")
            if 'Fit' not in self.panels:
                self.panels['Fit'] = FitDialog()
            self.panels['Fit'].activate(node)
            logging.info("Fitting invoked on'%s'" % node.nxpath)
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
            xml_root = ET.parse(os.path.join(base_class_path, 
                                             nxdl_file)).getroot()
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
        self.nxclasses['NXgroup'] = ('', {}, {})

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
        elif isinstance(data, str):
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
                xaction = QtWidgets.QAction(pmagic,
                    self,
                    triggered=self._make_dynamic_magic(pmagic)
                    )
                xaction_all = QtWidgets.QAction(pmagic,
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

        Will infere the menu name from the identifier at creation if menulabel 
        not given. To do so you have too give menuidentifier as a 
        CamelCassedString
        """
        menu = self._magic_menu_dict.get(menuidentifier,None)
        if not menu :
            if not menulabel:
                menulabel = re.sub("([a-zA-Z]+)([A-Z][a-z])","\g<1> \g<2>",
                                   menuidentifier)
            menu = QtWidgets.QMenu(menulabel, self.magic_menu)
            self._magic_menu_dict[menuidentifier]=menu
            self.magic_menu.insertMenu(self.magic_menu_separator,menu)
        return menu

    def make_active_action(self, number, label):
        if label == 'Projection':
            self.active_action[number] = QtWidgets.QAction(label,
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+P"),
                triggered=lambda: self.plotviews[label].make_active(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        elif label == 'Scan':
            self.active_action[number] = QtWidgets.QAction(label,
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+S"),
                triggered=lambda: self.plotviews[label].make_active(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        elif label == 'Fit':
            self.active_action[number] = QtWidgets.QAction(label,
                self,
                shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+F"),
                triggered=lambda: self.plotviews[label].make_active(),
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
            self.active_action[number] = QtWidgets.QAction(label,
                self,
                triggered=lambda: self.make_active(number),
                checkable=True)
            if number < 10:
                self.active_action[number].setShortcut(
                    QtGui.QKeySequence("Ctrl+%s" % number))
            self.window_menu.insertAction(before_action,
                                          self.active_action[number])
        self.make_active(number)

    def new_plot_window(self):
        new_plotview = NXPlotView(parent=self)

    def close_window(self):
        windows = self.dialogs
        windows += [self.plotviews[pv] for pv in self.plotviews if pv != 'Main']
        for window in windows:
            try:
                if window.isActiveWindow():
                    window.close()
                    break
            except Exception:
                pass

    def equalize_windows(self):
        for label in [label for label in self.plotviews 
                      if (label != 'Main' and label != self.plotview.label)]:
            self.plotviews[label].resize(self.plotview.size())

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

    def reset_axes(self):
        try:
            self.plotview.reset_plot_limits()
        except NeXusError as error:
            report_error("Resetting Plot Limits", error)

    def edit_preferences(self):
        try:
            dialog = PreferencesDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Editing Preferences", error)

    def show_tree(self):
        self.raise_()
        self.treeview.raise_()
        self.treeview.activateWindow()
        self.treeview.setFocus()

    def show_shell(self):
        self.raise_()
        self.shellview.raise_()
        self.shellview.activateWindow()
        self.shellview.setFocus()

    def show_log(self):
        try:
            if self.log_window in self.dialogs:
                self.log_window.show_log()
            else:
                self.log_window = LogDialog(parent=self)
        except NeXusError as error:
            report_error("Showing Log File", error)

    def panel_is_running(self, panel):
        if panel in self.panels:
            if self.panels[panel].is_running():
                return True
            else:
                self.panels[panel].close()
                return False
        else:
            return False

    def show_customize_panel(self):
        try:
            if not self.panel_is_running('Customize'):
                self.panels['Customize'] = CustomizeDialog()
            self.panels['Customize'].activate(self.active_plotview.label)
        except NeXusError as error:
            report_error("Showing Customize Panel", error)

    def show_limits_panel(self):
        try:
            if not self.panel_is_running('Limits'):
                self.panels['Limits'] = LimitDialog()
            self.panels['Limits'].activate(self.active_plotview.label)
        except NeXusError as error:
            report_error("Showing Limits Panel", error)

    def show_all_limits(self):
        try:
            original_plotview = self.plotview
            if not self.panel_is_running('Limits'):
                self.panels['Limits'] = LimitDialog()
            for pv in sorted(self.plotviews.values(), key=attrgetter('number'),
                             reverse=True):
                self.make_active(pv.number)
                self.panels['Limits'].activate(pv.label)
            self.make_active(original_plotview.number)
            self.panels['Limits'].activate(self.active_plotview.label)
        except NeXusError as error:
            report_error("Showing Limits Panel", error)

    def show_projection_panel(self):
        if self.active_plotview.label == 'Projection' or self.plotview.ndim == 1:
            if ('Projection' in self.panels and 
                self.panels['Projection'].isVisible()):
                self.panels['Projection'].raise_()
                self.panels['Projection'].activateWindow()
            return
        try:
            if not self.panel_is_running('Projection'):
                self.panels['Projection'] = ProjectionDialog()
            self.panels['Projection'].activate(self.active_plotview.label)
        except NeXusError as error:
            report_error("Showing Projection Panel", error)

    def show_scan_panel(self):
        if self.plotview.label == 'Projection':
            if 'Scan' in self.panels:
                self.panels['Scan'].raise_()
                self.panels['Scan'].activateWindow()
            return
        try:
            if not self.panel_is_running('Scan'):
                self.panels['Scan'] = ScanDialog()
            self.panels['Scan'].activate(self.plotview.label)
        except NeXusError as error:
            report_error("Showing Scan Panel", error)

    def show_script_window(self):
        if not self.panel_is_running('Editor'):
            self.panels['Editor'] = NXScriptWindow()
        if self.panels['Editor'].count == 0:
            self.new_script()
        else:
            self.panels['Editor'].raise_()    
            self.panels['Editor'].activateWindow()

    def open_script_window(self, file_name):
        if 'Editor' not in self.panels:
            self.panels['Editor'] = NXScriptWindow()
        self.panels['Editor'].activate(file_name)

    def new_script(self):
        try:
            file_name = None
            self.open_script_window(file_name)
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
                self.open_script_window(file_name)
                logging.info("NeXus script '%s' opened" % file_name)
        except NeXusError as error:
            report_error("Editing Script", error)

    def open_startup_script(self):
        try:
            file_name = os.path.join(self.nexpy_dir, 'config.py')
            self.open_script_window(file_name)
            logging.info("NeXus script '%s' opened" % file_name)
        except NeXusError as error:
            report_error("Editing Startup Script", error)


    def open_script_file(self):
        try:
            file_name = self.scripts[self.sender()][1]
            self.open_script_window(file_name)
            logging.info("NeXus script '%s' opened" % file_name)
        except NeXusError as error:
            report_error("Opening Script", error)

    def add_script_directory(self, directory, menu):
        names = sorted(os.listdir(directory))
        for name in names:
            if os.path.isdir(os.path.join(directory, name)):
                d = os.path.join(directory, name)
                m = menu.addMenu(name)
                self.add_script_directory(d, m)
            elif name.endswith('.py'):
                self.add_script_action(os.path.join(directory, name), menu)

    def add_script_action(self, file_name, menu):
        name = os.path.basename(file_name)
        script_action = QtWidgets.QAction(name, self,
                                          triggered=self.open_script_file)
        self.add_menu_action(menu, script_action, self)
        self.scripts[script_action] = (menu, file_name)

    def remove_script_action(self, file_name):
        for action, (menu, name) in self.scripts.items():
            if name == file_name:
                menu.removeAction(action)

    def _open_nexpy_online_help(self):
        url = "https://nexpy.github.io/nexpy/"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexusformat_online_notebook(self):
        url = ("https://colab.research.google.com/github/nexpy/nexusformat/blob/" +
                    "master/src/nexusformat/notebooks/nexusformat.ipynb")
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexus_online_help(self):
        url = "http://download.nexusformat.org/doc/html/classes/base_classes/"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_ipython_online_help(self):
        url = "https://ipython.readthedocs.io/en/stable/"
        webbrowser.open(url, new=1, autoraise=True)

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
            if self.scriptwindow is None:
                self.scriptwindow = NXScriptWindow(self)
            editor = NXScriptEditor(file_name, self)
            self.scriptwindow.setVisible(True)
            self.scriptwindow.raise_()
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
        widget = self.app.app.focusWidget()
        if widget == self.console._control:
            widget = self.console
        try:
            if widget.can_cut():
                widget.cut()
        except Exception:
            pass

    def copy_console(self):
        widget = self.app.app.focusWidget()
        if widget == self.console._control:
            widget = self.console
        try:
            widget.copy()
        except Exception:
            pass

    def copy_raw_console(self):
        self.console._copy_raw_action.trigger()

    def paste_console(self):
        widget = self.app.app.focusWidget()
        if widget == self.console._control:
            widget = self.console
        try:
            if widget.can_paste():
                widget.paste()
        except Exception:
            pass

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

    def intro_console(self):
        self.console.execute("?")

    def quickref_console(self):
        self.console.execute("%quickref")

    def close_files(self):
        for root in [n for n in self.user_ns 
                     if isinstance(self.user_ns[n], NXroot)]:
            self.user_ns[root].close()

    def close_widgets(self):
        windows = self.dialogs
        windows += [self.plotviews[pv] for pv in self.plotviews if pv != 'Main']
        for window in windows:
            try:
                window.close()
            except:
                pass        

    def closeEvent(self, event):
        """Customize the close process to confirm request to quit NeXpy."""
        if confirm_action("Are you sure you want to quit NeXpy?", 
                          icon=self.app.icon_pixmap):
            self.console.kernel_client.stop_channels()
            self.console.kernel_manager.shutdown_kernel()
            self.close_files()
            self.close_widgets()
            logging.info('NeXpy closed\n'+80*'-')
            self._app.quit()
            return event.accept()
        else:
            return event.ignore()
