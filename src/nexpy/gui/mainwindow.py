# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""The Qt MainWindow for NeXpy

This contains a tree view to display NeXus data, a Matplotlib canvas to
plot the data, and a Jupyter console to execute Python commands. The
namespace of the console includes the NeXus data loaded into the tree.
"""

import logging
import sys
import webbrowser
from operator import attrgetter
from pathlib import Path

from nexusformat.nexus import (NeXusError, NXdata, NXentry, NXfield, NXFile,
                               NXgroup, NXlink, NXobject, NXprocess, NXroot,
                               nxcompleter, nxduplicate, nxgetconfig, nxload)
from nexusformat.nexus.utils import get_base_classes
from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from .. import __version__
from .dialogs import (AttributeDialog, CustomizeDialog, DirectoryDialog,
                      EditDialog, ExportDialog, FieldDialog, GroupDialog,
                      LimitDialog, LockDialog, LogDialog, ManageBackupsDialog,
                      ManagePluginsDialog, NewDialog, PasteDialog, PlotDialog,
                      PlotScalarDialog, ProjectionDialog, RenameDialog,
                      ScanDialog, SettingsDialog, SignalDialog, UnlockDialog,
                      ValidateDialog, ViewDialog)
from .plotview import NXPlotView
from .pyqt import QtCore, QtGui, QtWidgets, getOpenFileName, getSaveFileName
from .scripteditor import NXScriptWindow
from .treeview import NXTreeView
from .utils import (confirm_action, define_mode, display_message, get_colors,
                    get_name, is_file_locked, load_image, load_plugin,
                    load_readers, natural_sort, package_files, report_error,
                    timestamp)


class NXRichJupyterWidget(RichJupyterWidget):

    def _is_complete(self, source, interactive=True):
        """Check if source is a complete block of code.

        Parameters
        ----------
        source : str
            Source code to check.
        interactive : bool, optional
            If True, consider IPython syntax like '%%' cell magics.
            Default is True.

        Returns
        -------
        complete : bool
            True if source is complete.
        indent : str
            Indentation to apply to the next input, if any.
        """
        shell = self.kernel_manager.kernel.shell
        status, indent_spaces = shell.input_transformer_manager.check_complete(
            source)
        if indent_spaces is None:
            indent = ''
        else:
            indent = ' ' * indent_spaces
        return status != 'incomplete', indent


class MainWindow(QtWidgets.QMainWindow):

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

        self.dialogs = []
        self.panels = {}
        self.scripts = {}
        self.log_window = None
        self.copied_node = None
        self._memroot = None

        self.default_directory = Path.home()
        self.nexpy_dir = self.app.nexpy_dir
        self.backup_dir = self.app.backup_dir
        self.plugin_dir = self.app.plugin_dir
        self.reader_dir = self.app.reader_dir
        self.model_dir = self.app.model_dir
        self.script_dir = self.app.script_dir
        self.scratch_file = self.app.scratch_file
        self.settings_file = self.app.settings_file

        mainwindow = QtWidgets.QWidget()

        self.mainview = NXPlotView(label="Main", mainwindow=self)

        self.console = NXRichJupyterWidget(config=self.config)
        self.console.setMinimumSize(750, 100)
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

        self.tree = tree
        self.treeview = NXTreeView(self.tree, mainwindow=self)
        self.treeview.setMinimumWidth(200)
        self.treeview.setMaximumWidth(400)

        rightpane = QtWidgets.QWidget()

        right_splitter = QtWidgets.QSplitter(rightpane)
        right_splitter.setOrientation(QtCore.Qt.Vertical)
        right_splitter.addWidget(self.mainview)
        right_splitter.addWidget(self.console)

        rightlayout = QtWidgets.QVBoxLayout()
        rightlayout.addWidget(right_splitter)
        rightlayout.setContentsMargins(0, 0, 0, 0)
        rightpane.setLayout(rightlayout)

        left_splitter = QtWidgets.QSplitter(mainwindow)
        left_splitter.setOrientation(QtCore.Qt.Horizontal)
        left_splitter.addWidget(self.treeview)
        left_splitter.addWidget(rightpane)

        mainlayout = QtWidgets.QHBoxLayout()
        mainlayout.addWidget(left_splitter)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainwindow.setLayout(mainlayout)

        self.setCentralWidget(mainwindow)

        self.user_ns['plotview'] = self.plotview
        self.user_ns['plotviews'] = self.plotviews = self.plotview.plotviews
        self.user_ns['treeview'] = self.treeview
        self.user_ns['nxtree'] = self.tree
        self.user_ns['mainwindow'] = self

        self.nxclasses = get_base_classes()

        self.init_menu_bar()

        self.file_filter = ';;'.join((
            "NeXus Files (*.nxs *.nx5 *.nxspe *.h5 *.hdf *.hdf5 *.cxi)",
            "Any Files (*.* *)"))
        self.max_recent_files = 20

        self.setWindowTitle('NeXpy v'+__version__)
        self.statusBar().showMessage('Ready')

        self.app.app.paletteChanged.connect(self.change_mode)

        self.treeview.selection_changed()
        self.shellview.setFocus()

    def start(self):
        """
        Called after the application has finished initializing to check
        if there are any new plugins available that were not available
        when the application was last run. If so, a message is displayed
        to the user to manage the plugins.
        """
        if self.new_plugins:
            display_message(
                "New plugins are available", 
                "Visit the 'Manage Plugins' menu to enable/disable them.")
            
    @property
    def plotview(self):
        """Return the current plotview"""
        from .plotview import plotview
        return plotview

    @property
    def active_plotview(self):
        """Return the active plotview"""
        from .plotview import active_plotview
        return active_plotview

    def change_mode(self):
        """Called when the application palette changes"""
        define_mode()

    # Populate the menu bar with common actions and shortcuts
    def add_menu_action(self, menu, action, defer_shortcut=False):
        """Add action to menu as well as self

        So that when the menu bar is invisible, its actions are still
        available.

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
        """Initialize the menu bar"""
        self.menu_bar = QtWidgets.QMenuBar()
        self.init_file_menu()
        self.init_edit_menu()
        self.init_data_menu()
        self.init_plugin_menus()
        self.init_view_menu()
        self.init_window_menu()
        self.init_script_menu()
        self.init_help_menu()
        self.setMenuBar(self.menu_bar)

    def init_file_menu(self):
        """Initialize the File menu"""
        self.file_menu = QtWidgets.QMenu("&File", self)
        self.menu_bar.addMenu(self.file_menu)

        self.file_menu.addSeparator()

        self.newworkspace_action = QtWidgets.QAction(
            "&New...", self, shortcut=QtGui.QKeySequence.New,
            triggered=self.new_workspace)
        self.add_menu_action(self.file_menu, self.newworkspace_action)

        self.openfile_action = QtWidgets.QAction(
            "&Open", self, shortcut=QtGui.QKeySequence.Open,
            triggered=self.open_file)
        self.add_menu_action(self.file_menu, self.openfile_action)

        self.openeditablefile_action = QtWidgets.QAction(
            "Open (read/write)", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+O"),
            triggered=self.open_editable_file)
        self.addAction(self.openeditablefile_action)

        self.init_recent_menu()

        self.openimage_action = QtWidgets.QAction(
            "Open Image...", self, shortcut=QtGui.QKeySequence("Ctrl+Alt+O"),
            triggered=self.open_image)
        self.add_menu_action(self.file_menu, self.openimage_action)

        self.opendirectory_action = QtWidgets.QAction(
            "Open Directory...", self, triggered=self.open_directory)
        self.add_menu_action(self.file_menu, self.opendirectory_action)

        self.savefile_action = QtWidgets.QAction(
            "&Save as...", self, shortcut=QtGui.QKeySequence.Save,
            triggered=self.save_file)
        self.add_menu_action(self.file_menu, self.savefile_action)

        self.duplicate_action = QtWidgets.QAction(
            "&Duplicate...", self, shortcut=QtGui.QKeySequence("Ctrl+D"),
            triggered=self.duplicate)
        self.add_menu_action(self.file_menu, self.duplicate_action)

        self.file_menu.addSeparator()

        self.restore_session_action = QtWidgets.QAction(
            "Restore Session", self, shortcut=QtGui.QKeySequence("Ctrl+R"),
            triggered=self.restore_session)
        self.add_menu_action(self.file_menu, self.restore_session_action)

        self.file_menu.addSeparator()

        self.reload_action = QtWidgets.QAction("&Reload", self,
                                               triggered=self.reload)
        self.add_menu_action(self.file_menu, self.reload_action)

        self.reload_all_action = QtWidgets.QAction("Reload All", self,
                                                   triggered=self.reload_all)
        self.add_menu_action(self.file_menu, self.reload_all_action)

        self.remove_action = QtWidgets.QAction("Remove", self,
                                               triggered=self.remove)
        self.add_menu_action(self.file_menu, self.remove_action)

        self.remove_all_action = QtWidgets.QAction("Remove All", self,
                                                   triggered=self.remove_all)
        self.add_menu_action(self.file_menu, self.remove_all_action)

        self.file_menu.addSeparator()

        self.collapse_action = QtWidgets.QAction("Collapse Tree", self,
                                                 triggered=self.collapse_tree)
        self.add_menu_action(self.file_menu, self.collapse_action)

        self.file_menu.addSeparator()

        self.init_import_menu()

        self.file_menu.addSeparator()

        self.export_action = QtWidgets.QAction("Export", self,
                                               triggered=self.export_data)
        self.add_menu_action(self.file_menu, self.export_action)

        self.file_menu.addSeparator()

        self.lockfile_action = QtWidgets.QAction(
            "&Lock File", self, shortcut=QtGui.QKeySequence("Ctrl+L"),
            triggered=self.lock_file)
        self.add_menu_action(self.file_menu, self.lockfile_action)

        if sys.platform == 'darwin':
            # This maps onto Cmd+U on a Mac. On other systems, this clashes
            # with the Ctrl+U command-line editing shortcut.
            unlock_shortcut = QtGui.QKeySequence("Ctrl+U")
        else:
            unlock_shortcut = QtGui.QKeySequence("Ctrl+Shift+U")
        self.unlockfile_action = QtWidgets.QAction("&Unlock File", self,
                                                   shortcut=unlock_shortcut,
                                                   triggered=self.unlock_file)
        self.add_menu_action(self.file_menu, self.unlockfile_action)

        self.lock_action = QtWidgets.QAction(
            "Show File Locks", self, triggered=self.show_locks)
        self.add_menu_action(self.file_menu, self.lock_action)

        self.file_menu.addSeparator()

        self.backup_action = QtWidgets.QAction(
            "&Backup File", self, shortcut=QtGui.QKeySequence("Ctrl+B"),
            triggered=self.backup_file)
        self.add_menu_action(self.file_menu, self.backup_action)

        self.restore_backup_action = QtWidgets.QAction(
            "Restore Backup...", self, triggered=self.restore_file)
        self.add_menu_action(self.file_menu, self.restore_backup_action)

        self.manage_backups_action = QtWidgets.QAction(
            "Manage Backups...", self, triggered=self.manage_backups)
        self.add_menu_action(self.file_menu, self.manage_backups_action)

        self.file_menu.addSeparator()

        self.open_scratch_action = QtWidgets.QAction(
            "Open Scratch File", self, triggered=self.open_scratch_file)
        self.add_menu_action(self.file_menu, self.open_scratch_action)

        self.purge_scratch_action = QtWidgets.QAction(
            "Purge Scratch File", self, triggered=self.purge_scratch_file)
        self.add_menu_action(self.file_menu, self.purge_scratch_action)

        self.close_scratch_action = QtWidgets.QAction(
            "Close Scratch File", self, triggered=self.close_scratch_file)
        self.add_menu_action(self.file_menu, self.close_scratch_action)

        self.file_menu.addSeparator()

        self.manage_plugins_action = QtWidgets.QAction(
            "Manage Plugins...", self, triggered=self.manage_plugins)
        self.add_menu_action(self.file_menu, self.manage_plugins_action)

        self.file_menu.addSeparator()

        self.settings_action = QtWidgets.QAction(
            "Edit Settings", self, triggered=self.edit_settings)
        self.add_menu_action(self.file_menu, self.settings_action)

        self.quit_action = QtWidgets.QAction("&Quit", self,
                                             shortcut=QtGui.QKeySequence.Quit,
                                             triggered=self.close)
        # OSX always has Quit in the Application menu, only add it
        # to the File menu elsewhere.
        if sys.platform == 'darwin':
            self.addAction(self.quit_action)
        else:
            self.file_menu.addSeparator()
            self.add_menu_action(self.file_menu, self.quit_action)

    def init_edit_menu(self):
        """Initialize the Edit menu."""
        self.edit_menu = QtWidgets.QMenu("&Edit", self)
        self.menu_bar.addMenu(self.edit_menu)

        self.undo_action = QtWidgets.QAction(
            "&Undo", self, shortcut=QtGui.QKeySequence.Undo,
            statusTip="Undo last action if possible",
            triggered=self.undo_console)
        self.add_menu_action(self.edit_menu, self.undo_action, True)

        self.redo_action = QtWidgets.QAction(
            "&Redo", self, shortcut=QtGui.QKeySequence.Redo,
            statusTip="Redo last action if possible",
            triggered=self.redo_console)
        self.add_menu_action(self.edit_menu, self.redo_action, True)

        self.edit_menu.addSeparator()

        self.cut_action = QtWidgets.QAction("&Cut", self,
                                            shortcut=QtGui.QKeySequence.Cut,
                                            triggered=self.cut_console)
        self.add_menu_action(self.edit_menu, self.cut_action, True)

        self.copy_action = QtWidgets.QAction("&Copy", self,
                                             shortcut=QtGui.QKeySequence.Copy,
                                             triggered=self.copy_console)
        self.add_menu_action(self.edit_menu, self.copy_action, True)

        self.copy_raw_action = QtWidgets.QAction(
            "Copy (Raw Text)", self, triggered=self.copy_raw_console)
        self.add_menu_action(self.edit_menu, self.copy_raw_action)

        self.paste_action = QtWidgets.QAction(
            "&Paste", self, shortcut=QtGui.QKeySequence.Paste,
            triggered=self.paste_console)
        self.add_menu_action(self.edit_menu, self.paste_action, True)

        self.edit_menu.addSeparator()

        selectall = QtGui.QKeySequence(QtGui.QKeySequence.SelectAll)
        if selectall.matches("Ctrl+A") and sys.platform != 'darwin':
            # Only override the default if there is a collision.
            # Qt ctrl = cmd on OSX, so the match gets a false positive on OSX.
            selectall = "Ctrl+Shift+A"
        self.select_all_action = QtWidgets.QAction(
            "Select &All", self, shortcut=selectall,
            triggered=self.select_all_console)
        self.add_menu_action(self.edit_menu, self.select_all_action, True)

        self.edit_menu.addSeparator()

        self.print_action = QtWidgets.QAction(
            "Print Shell", self, triggered=self.print_action_console)
        self.add_menu_action(self.edit_menu, self.print_action, True)

    def init_data_menu(self):
        """Initialize the Data menu."""
        self.data_menu = QtWidgets.QMenu("Data", self)
        self.menu_bar.addMenu(self.data_menu)

        self.plot_data_action = QtWidgets.QAction(
            "&Plot Data", self, shortcut=QtGui.QKeySequence("Ctrl+P"),
            triggered=self.plot_data)
        self.add_menu_action(self.data_menu, self.plot_data_action)

        self.plot_line_action = QtWidgets.QAction("Plot Line", self,
                                                  triggered=self.plot_line)

        self.overplot_data_action = QtWidgets.QAction(
            "Overplot Data", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+P"),
            triggered=self.overplot_data)
        self.add_menu_action(self.data_menu, self.overplot_data_action)

        self.overplot_line_action = QtWidgets.QAction(
            "Overplot Line", self, triggered=self.overplot_line)

        self.multiplot_data_action = QtWidgets.QAction(
            "Plot All Signals", self, triggered=self.multiplot_data)
        self.add_menu_action(self.data_menu, self.multiplot_data_action)

        self.multiplot_lines_action = QtWidgets.QAction(
            "Plot All Signals as Lines", self, triggered=self.multiplot_lines)

        self.plot_weighted_data_action = QtWidgets.QAction(
            "Plot Weighted Data", self, triggered=self.plot_weighted_data)
        self.add_menu_action(self.data_menu, self.plot_weighted_data_action)

        self.plot_image_action = QtWidgets.QAction("Plot RGB(A) Image", self,
                                                   triggered=self.plot_image)
        self.add_menu_action(self.data_menu, self.plot_image_action)

        self.data_menu.addSeparator()

        self.view_action = QtWidgets.QAction(
            "View Data", self, shortcut=QtGui.QKeySequence("Ctrl+Alt+V"),
            triggered=self.view_data)
        self.add_menu_action(self.data_menu, self.view_action)

        self.validate_action = QtWidgets.QAction(
            "Validate Data", self,
            shortcut=QtGui.QKeySequence("Ctrl+Alt+Shift+V"),
            triggered=self.validate_data)
        self.add_menu_action(self.data_menu, self.validate_action)

        self.data_menu.addSeparator()

        self.group_action = QtWidgets.QAction("Add Group", self,
                                            triggered=self.add_group)
        self.add_menu_action(self.data_menu, self.group_action)

        self.field_action = QtWidgets.QAction("Add Field", self,
                                            triggered=self.add_field)
        self.add_menu_action(self.data_menu, self.field_action)

        self.attribute_action = QtWidgets.QAction("Add Attribute", self,
                                            triggered=self.add_attribute)
        self.add_menu_action(self.data_menu, self.attribute_action)

        self.data_menu.addSeparator()

        self.edit_action = QtWidgets.QAction(
            "Edit Data", self, shortcut=QtGui.QKeySequence("Ctrl+E"),
            triggered=self.edit_data)
        self.add_menu_action(self.data_menu, self.edit_action)

        self.rename_action = QtWidgets.QAction("Rename Data", self,
                                               triggered=self.rename_data)
        self.add_menu_action(self.data_menu, self.rename_action)

        self.delete_action = QtWidgets.QAction(
            "Delete Data", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+Alt+X"),
            triggered=self.delete_data)
        self.add_menu_action(self.data_menu, self.delete_action)

        self.edit_menu.addSeparator()

        self.copydata_action = QtWidgets.QAction(
            "Copy Data", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+C"),
            triggered=self.copy_data)
        self.add_menu_action(self.data_menu, self.copydata_action)

        self.cutdata_action = QtWidgets.QAction(
            "Cut Data", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+X"),
            triggered=self.cut_data)
        self.add_menu_action(self.data_menu, self.cutdata_action)

        self.pastedata_action = QtWidgets.QAction(
            "Paste Data", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+V"),
            triggered=self.paste_data)
        self.add_menu_action(self.data_menu, self.pastedata_action)

        self.pastelink_action = QtWidgets.QAction(
            "Paste As Link", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+Alt+V"),
            triggered=self.paste_link)
        self.add_menu_action(self.data_menu, self.pastelink_action)

        self.data_menu.addSeparator()

        self.link_action = QtWidgets.QAction("Show Link", self,
                                             triggered=self.show_link)
        self.add_menu_action(self.data_menu, self.link_action)

        self.data_menu.addSeparator()

        self.signal_action = QtWidgets.QAction("Set Signal", self,
                                               triggered=self.set_signal)
        self.add_menu_action(self.data_menu, self.signal_action)

        self.default_action = QtWidgets.QAction("Set Default", self,
                                                triggered=self.set_default)
        self.add_menu_action(self.data_menu, self.default_action)

        self.data_menu.addSeparator()

        self.fit_action = QtWidgets.QAction(
            "Fit Data", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+F"),
            triggered=self.fit_data)
        self.add_menu_action(self.data_menu, self.fit_action)
        self.fit_weighted_action = QtWidgets.QAction(
            "Fit Weighted Data", self,
            shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+F"),
            triggered=self.fit_weighted_data)
        self.add_menu_action(self.data_menu, self.fit_weighted_action)

    def init_plugin_menus(self):
        """Add an menu item for every module in the plugin menus"""
        self.plugins = {}
        self.new_plugins = False
        for plugin in self.settings.options('plugins'):
            plugin_order = self.settings.get('plugins', plugin)
            if plugin_order is None:
                self.new_plugins = True
                logging.info(f'New plugin "{plugin}" found but not installed')
            else:
                try:
                    self.plugins[plugin] = load_plugin(plugin, plugin_order)
                    logging.info(f'Installing plugin from "{plugin}"')
                except Exception as error:
                    logging.warning(
                        f'The "{plugin}" plugin could not be added to the '
                        'main menu\n' + 36*' ' + f'Error: {error}')

        def sorted_plugins():
            return sorted(self.plugins, key=lambda k: self.plugins[k]['order'])

        installed_plugins = []

        self.plugin_actions = []
        for plugin in sorted_plugins():
            if self.plugins[plugin]['order'] == 'Disabled':
                continue
            try:
                menu = self.plugins[plugin]['menu']
                actions = self.plugins[plugin]['actions']
                package = self.plugins[plugin]['package']
                if menu in installed_plugins:
                    logging.warning(
                        f'Duplicate plugin menu "{menu}" not added')
                else:
                    self.add_plugin_menu(menu, actions)
                    installed_plugins.append(menu)
                    logging.info(f'Plugin menu "{menu}" added')
            except Exception as error:
                logging.warning(
                    f'Plugin menu "{menu}" from {package} '
                    'could not be added to the main menu\n' + 
                    36*' ' + f'Error: {error}')

    def init_view_menu(self):
        """Initialize the View menu"""
        self.view_menu = QtWidgets.QMenu("&View", self)
        self.menu_bar.addMenu(self.view_menu)

        if sys.platform != 'darwin':
            # disable on OSX, where there is always a menu bar
            self.toggle_menu_bar_act = QtWidgets.QAction(
                "Toggle &Menu Bar", self, shortcut=QtGui.QKeySequence(
                    "Ctrl+Shift+M"),
                statusTip="Toggle visibility of menubar",
                triggered=self.toggle_menu_bar)
            self.add_menu_action(self.view_menu, self.toggle_menu_bar_act)

        fs_key = "Ctrl+Meta+F" if sys.platform == 'darwin' else "F11"
        self.full_screen_act = QtWidgets.QAction(
            "&Full Screen", self, shortcut=fs_key,
            statusTip="Toggle between Fullscreen and Normal Size",
            triggered=self.toggleFullScreen)
        self.add_menu_action(self.view_menu, self.full_screen_act)

        self.view_menu.addSeparator()

        self.increase_font_size = QtWidgets.QAction(
            "Zoom &In", self, shortcut=QtGui.QKeySequence.ZoomIn,
            triggered=self.increase_font_size_console)
        self.add_menu_action(self.view_menu, self.increase_font_size, True)

        self.decrease_font_size = QtWidgets.QAction(
            "Zoom &Out", self, shortcut=QtGui.QKeySequence.ZoomOut,
            triggered=self.decrease_font_size_console)
        self.add_menu_action(self.view_menu, self.decrease_font_size, True)

        self.reset_font_size = QtWidgets.QAction(
            "Zoom &Reset", self, shortcut=QtGui.QKeySequence("Ctrl+0"),
            triggered=self.reset_font_size_console)
        self.add_menu_action(self.view_menu, self.reset_font_size, True)

        self.view_menu.addSeparator()

    def init_window_menu(self):
        """Initialize the Window menu"""
        self.window_menu = QtWidgets.QMenu("&Window", self)
        self.menu_bar.addMenu(self.window_menu)

        if sys.platform == 'darwin':
            # add min/maximize actions to OSX, which lacks default bindings.
            self.minimizeAct = QtWidgets.QAction(
                "Mini&mize", self, shortcut=QtGui.QKeySequence("Ctrl+m"),
                statusTip="Minimize the window/Restore Normal Size",
                triggered=self.toggleMinimized)
            # maximize is called 'Zoom' on OSX for some reason
            self.maximizeAct = QtWidgets.QAction(
                "&Zoom", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+M"),
                statusTip="Maximize the window/Restore Normal Size",
                triggered=self.toggleMaximized)

            self.add_menu_action(self.window_menu, self.minimizeAct)
            self.add_menu_action(self.window_menu, self.maximizeAct)
            self.window_menu.addSeparator()

        self.tree_action = QtWidgets.QAction(
            "Show Tree", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+T"),
            triggered=self.show_tree)
        self.add_menu_action(self.window_menu, self.tree_action)

        self.shell_action = QtWidgets.QAction(
            "Show IPython Shell", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+I"),
            triggered=self.show_shell)
        self.add_menu_action(self.window_menu, self.shell_action)

        self.window_menu.addSeparator()

        self.log_action = QtWidgets.QAction(
            "Show Log File", self, shortcut=QtGui.QKeySequence("Ctrl+Shift+L"),
            triggered=self.show_log)
        self.add_menu_action(self.window_menu, self.log_action)

        self.script_window_action = QtWidgets.QAction(
            "Show Script Editor", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+S"),
            triggered=self.show_script_window)
        self.add_menu_action(self.window_menu, self.script_window_action)

        self.window_menu.addSeparator()

        self.customize_action = QtWidgets.QAction(
            "Show Customize Panel", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Alt+C"),
            triggered=self.show_customize_panel)
        self.add_menu_action(self.window_menu, self.customize_action)

        self.limit_action = QtWidgets.QAction(
            "Show Limits Panel", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Alt+L"),
            triggered=self.show_limits_panel)
        self.add_menu_action(self.window_menu, self.limit_action)

        self.panel_action = QtWidgets.QAction(
            "Show Projection Panel", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Alt+P"),
            triggered=self.show_projection_panel)
        self.add_menu_action(self.window_menu, self.panel_action)

        self.scan_action = QtWidgets.QAction(
            "Show Scan Panel", self, shortcut=QtGui.QKeySequence("Ctrl+Alt+S"),
            triggered=self.show_scan_panel)
        self.add_menu_action(self.window_menu, self.scan_action)

        self.window_menu.addSeparator()

        self.show_all_limits_action = QtWidgets.QAction(
            "Show All Limits", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+Alt+L"),
            triggered=self.show_all_limits)
        self.add_menu_action(self.window_menu, self.show_all_limits_action)

        self.reset_limit_action = QtWidgets.QAction("Reset Plot Limits", self,
                                                    triggered=self.reset_axes)
        self.add_menu_action(self.window_menu, self.reset_limit_action)

        self.window_menu.addSeparator()

        self.newplot_action = QtWidgets.QAction(
            "New Plot Window", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+N"),
            triggered=self.new_plot_window)
        self.add_menu_action(self.window_menu, self.newplot_action)

        self.closewindow_action = QtWidgets.QAction(
            "Close Plot Window", self, shortcut=QtGui.QKeySequence("Ctrl+W"),
            triggered=self.close_window)
        self.add_menu_action(self.window_menu, self.closewindow_action,)

        self.window_menu.addSeparator()

        self.equalize_action = QtWidgets.QAction(
            "Equalize Plot Sizes", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+E"),
            triggered=self.equalize_plots)
        self.add_menu_action(self.window_menu, self.equalize_action)

        self.window_menu.addSeparator()

        self.cascade_action = QtWidgets.QAction(
            "Cascade Plots", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+Alt+C"),
            triggered=self.cascade_plots)
        self.add_menu_action(self.window_menu, self.cascade_action)

        self.tile_action = QtWidgets.QAction(
            "Tile Plots", self, shortcut=QtGui.QKeySequence(
                "Ctrl+Shift+Alt+T"),
            triggered=self.tile_plots)
        self.add_menu_action(self.window_menu, self.tile_action)

        self.window_menu.addSeparator()

        self.active_action = {}

        self.active_action[0] = QtWidgets.QAction(
            'Main', self, shortcut=QtGui.QKeySequence("Ctrl+0"),
            triggered=lambda: self.make_active(0),
            checkable=True)
        self.add_menu_action(self.window_menu, self.active_action[0])
        self.active_action[0].setChecked(True)
        self.previous_active = 0

        self.window_separator = self.window_menu.addSeparator()

    def init_script_menu(self):
        """Initialize the Script menu."""
        self.script_menu = QtWidgets.QMenu("&Script", self)
        self.menu_bar.addMenu(self.script_menu)

        self.new_script_action = QtWidgets.QAction("New Script...", self,
                                                   triggered=self.new_script)
        self.add_menu_action(self.script_menu, self.new_script_action)
        self.open_script_action = QtWidgets.QAction("Open Script...", self,
                                                    triggered=self.open_script)
        self.add_menu_action(self.script_menu, self.open_script_action)
        self.open_startup_script_action = QtWidgets.QAction(
            "Open Startup Script...", self,
            triggered=self.open_startup_script)
        self.add_menu_action(self.script_menu, self.open_startup_script_action)

        self.script_menu.addSeparator()

        if self.settings.has_option('settings', 'scriptdirectory'):
            self.public_script_dir = self.settings.get('settings',
                                                       'scriptdirectory')
        
        self.public_script_menu = QtWidgets.QMenu('Public Scripts', self)
        self.script_menu.addMenu(self.public_script_menu)
        self.add_script_directory(self.public_script_dir,
                                  self.public_script_menu)

        self.script_menu.addSeparator()

        self.private_script_menu = QtWidgets.QMenu('Private Scripts', self)
        self.script_menu.addMenu(self.private_script_menu)
        self.add_script_directory(self.script_dir, self.private_script_menu)

    def init_help_menu(self):
        """Initialize the Help menu."""
        self.help_menu = QtWidgets.QMenu("&Help", self)
        self.menu_bar.addMenu(self.help_menu)

        self.nexpyHelpAct = QtWidgets.QAction(
            "Open NeXpy &Help Online", self,
            triggered=self._open_nexpy_online_help)
        self.add_menu_action(self.help_menu, self.nexpyHelpAct)

        self.notebookHelpAct = QtWidgets.QAction(
            "Open NeXus API Tutorial Online", self,
            triggered=self._open_nexusformat_online_notebook)
        self.add_menu_action(self.help_menu, self.notebookHelpAct)

        self.nexusHelpAct = QtWidgets.QAction(
            "Open NeXus Base Class Definitions Online",
            self,
            triggered=self._open_nexus_online_help)
        self.add_menu_action(self.help_menu, self.nexusHelpAct)

        self.help_menu.addSeparator()

        self.nexpyReleaseAct = QtWidgets.QAction(
            "Open NeXpy Release Notes", self,
            triggered=self._open_nexpy_release_notes)
        self.add_menu_action(self.help_menu, self.nexpyReleaseAct)

        self.nexpyIssuesAct = QtWidgets.QAction(
            "Open NeXpy Issues", self,
            triggered=self._open_nexpy_issues)
        self.add_menu_action(self.help_menu, self.nexpyIssuesAct)

        self.help_menu.addSeparator()

        self.nexusformatReleaseAct = QtWidgets.QAction(
            "Open NeXus API Release Notes", self,
            triggered=self._open_nexusformat_release_notes)
        self.add_menu_action(self.help_menu, self.nexusformatReleaseAct)

        self.nexusformatIssuesAct = QtWidgets.QAction(
            "Open NeXus API Issues", self,
            triggered=self._open_nexusformat_issues)
        self.add_menu_action(self.help_menu, self.nexusformatIssuesAct)

        self.help_menu.addSeparator()

        self.ipythonHelpAct = QtWidgets.QAction(
            "Open iPython Help Online", self,
            triggered=self._open_ipython_online_help)
        self.add_menu_action(self.help_menu, self.ipythonHelpAct)

        self.intro_console_action = QtWidgets.QAction(
            "&Intro to IPython", self, triggered=self.intro_console)
        self.add_menu_action(self.help_menu, self.intro_console_action)

        self.quickref_console_action = QtWidgets.QAction(
            "IPython &Cheat Sheet", self, triggered=self.quickref_console)
        self.add_menu_action(self.help_menu, self.quickref_console_action)

        self.help_menu.addSeparator()

        self.example_file_action = QtWidgets.QAction(
            "Open Example File", self, triggered=self.open_example_file)
        self.add_menu_action(self.help_menu, self.example_file_action)

        self.example_script_action = QtWidgets.QAction(
            "Open Example Script", self, triggered=self.open_example_script)
        self.add_menu_action(self.help_menu, self.example_script_action)

    def init_recent_menu(self):
        """Add recent files menu item for recently opened files"""
        recent_files = self.settings.options('recent')
        self.recent_menu = QtWidgets.QMenu("Open Recent", self)
        self.file_menu.addMenu(self.recent_menu)
        self.recent_menu.hovered.connect(self.hover_recent_menu)
        self.recent_file_actions = {}
        for i, recent_file in enumerate(recent_files):
            action = QtWidgets.QAction(Path(recent_file).name, self,
                                       triggered=self.open_recent_file)
            action.setToolTip(recent_file)
            self.add_menu_action(self.recent_menu, action, self)
            self.recent_file_actions[action] = (i, recent_file)

    def init_import_menu(self):
        """Add an import menu item for every module in the readers directory"""
        self.import_menu = QtWidgets.QMenu("Import", self)
        self.file_menu.addMenu(self.import_menu)
        readers = load_readers()
        self.readers = {}
        for reader in readers:
            try:
                import_action = QtWidgets.QAction(
                    "Import "+readers[reader].filetype, self,
                    triggered=self.show_import_dialog)
                self.add_menu_action(self.import_menu, import_action, self)
                self.readers[import_action] = readers[reader]
            except Exception as error:
                logging.warning(
                    f'The "{reader}" importer could not be added '
                    'to the Import menu\n' + 36*' ' + f'Error: {error}')

    def new_workspace(self):
        """Dialog to create a new workspace"""
        try:
            dialog = NewDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Creating New Workspace", error)

    def load_file(self, fname, wait=5, recent=True):
        """
        Load a NeXus file into the GUI.

        Parameters
        ----------
        fname : str
            Name of the file to be loaded.
        wait : int, optional
            Number of seconds to wait for a file to be unlocked, by default 5.
        recent : bool, optional
            Whether to add the file to the list of recently opened files,
            by default True.

        Raises
        ------
        NeXusError
            If the file is already open, doesn't exist, or is locked.
        """
        if fname in [self.tree[root].nxfilename for root in self.tree]:
            raise NeXusError('File already open')
            return
        elif not Path(fname).exists():
            raise NeXusError(f"'{fname}' does not exist")
        elif is_file_locked(fname, wait=wait):
            logging.info(
                f"NeXus file '{fname}' is locked by an external process.")
            return
        name = self.tree.get_name(fname)
        if self.backup_dir in Path(fname).parents:
            name = name.replace('_backup', '')
            self.tree[name] = nxload(fname, 'rw')
        else:
            self.tree[name] = nxload(fname)
            self.default_directory = Path(fname).parent
        self.treeview.update()
        self.treeview.select_node(self.tree[name])
        self.treeview.setFocus()
        logging.info(f"NeXus file '{fname}' opened as workspace '{name}'")
        self.update_files(fname, recent=recent)

    def open_file(self):
        """Open a NeXus file in read-only mode."""
        try:
            fname = getOpenFileName(self, 'Open File (Read Only)',
                                    self.default_directory,  self.file_filter)
            if fname:
                self.load_file(fname)
        except NeXusError as error:
            report_error("Opening File", error)

    def open_editable_file(self):
        """Open a NeXus file in read-write mode."""
        try:
            fname = getOpenFileName(self, 'Open File (Read/Write)',
                                    self.default_directory, self.file_filter)
            if fname:
                self.load_file(fname)
        except NeXusError as error:
            report_error("Opening File (Read/Write)", error)

    def open_recent_file(self):
        """Open a recently openedNeXus file in read-only mode."""
        try:
            fname = self.recent_file_actions[self.sender()][1]
            self.load_file(fname)
        except NeXusError as error:
            report_error("Opening Recent File", error)

    def open_image(self):
        """Open an image file."""
        try:
            file_filter = ';;'.join(("Any Files (*.* *)",
                                     "TIFF Files (*.tiff *.tif)",
                                     "CBF Files (*.cbf)",
                                     "JPEG/PNG Files (*.jpg *.jpeg *.png)"))
            fname = getOpenFileName(self, 'Open Image File',
                                    self.default_directory, file_filter)
            if fname is None or not Path(fname).exists():
                return
            data = load_image(fname)
            if 'images' not in self.tree:
                self.tree['images'] = NXroot()
            name = get_name(fname, self.tree['images'].entries)
            self.tree['images'][name] = data
            node = self.tree['images'][name]
            self.treeview.select_node(node)
            self.treeview.setFocus()
            self.default_directory = Path(fname).parent
            logging.info(
                f"Image file '{fname}' opened as 'images{node.nxpath}'")
        except NeXusError as error:
            report_error("Opening Image File", error)

    def open_directory(self):
        """Open a directory of NeXus files."""
        try:
            directory = str(self.default_directory)
            directory = QtWidgets.QFileDialog.getExistingDirectory(
                self, 'Choose Directory', directory)
            if directory is None or not Path(directory).exists():
                return
            tree_files = [self.tree[root].nxfilename for root in self.tree]
            nxfiles = sorted([f.name for f in Path(directory).iterdir()
                              if (f.suffix.lower() in 
                                  ('.nxs', '.nx5', '.h5', 'hdf5', 'hdf',
                                   '.cxi', 'nxspe') and
                                  str(f) not in tree_files and
                                  not f.is_symlink())],
                             key=natural_sort)
            if len(nxfiles) == 0:
                raise NeXusError("No NeXus files found in directory")
            dialog = DirectoryDialog(nxfiles, directory, parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Opening Directory", error)

    def hover_recent_menu(self, action):
        """Show the tooltip for a recent file menu action."""
        position = QtGui.QCursor.pos()
        position.setX(position.x() + 80)
        QtWidgets.QToolTip.showText(
            position, self.recent_file_actions[action][1],
            self.recent_menu, self.recent_menu.actionGeometry(action))

    def update_files(self, filename, recent=True):
        """Update the list of recently opened files."""
        filename = str(filename)
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
                    action.setText(Path(recent_file).name)
                    action.setToolTip(recent_file)
                except IndexError:
                    action = QtWidgets.QAction(Path(recent_file).name,
                                               self,
                                               triggered=self.open_recent_file)
                    action.setToolTip(recent_file)
                    self.add_menu_action(self.recent_menu, action, self)
                self.recent_file_actions[action] = (i, recent_file)
            self.settings.purge('recent')
            for recent_file in recent_files:
                if "=" not in recent_file:
                    self.settings.set('recent', recent_file)
        if "=" not in filename:
            self.settings.set('session', filename)
        self.settings.save()

    def save_file(self):
        """Save a NeXus file."""
        try:
            node = self.treeview.get_node()
            if node is None or not isinstance(node, NXroot):
                raise NeXusError("Only NXroot groups can be saved")
            name = node.nxname
            default_name = Path(self.default_directory).joinpath(name)
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
                self.default_directory = Path(fname).parent
                self.settings.remove_option('recent', old_fname)
                self.settings.remove_option('session', old_fname)
                self.update_files(fname)
                logging.info(
                    f"NeXus workspace '{old_name}' saved as '{fname}'")
        except NeXusError as error:
            report_error("Saving File", error)

    def duplicate(self):
        """Duplicate a NeXus file."""
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                if node.nxfile:
                    name = self.tree.get_new_name()
                    default_name = self.default_directory.joinpath(name)
                    fname = getSaveFileName(self, "Choose a Filename",
                                            default_name, self.file_filter)
                    if fname:
                        if is_file_locked(fname):
                            return
                        with NXFile(fname, 'w') as f:
                            f.copyfile(node.nxfile)
                        logging.info(
                            f"Workspace '{node.nxname}' duplicated "
                            f"in '{fname}'")
                        self.load_file(fname)
                else:
                    default_name = self.tree.get_new_name()
                    name, ok = QtWidgets.QInputDialog.getText(
                        self, "Duplicate Workspace", "Workspace Name:",
                        text=default_name)
                    if name and ok:
                        self.tree[name] = node
                        logging.info(
                            f"Workspace '{node.nxname}' duplicated "
                            f"as workspace '{name}'")
                if name in self.tree:
                    self.treeview.select_node(self.tree[name])
                    self.treeview.update()
            else:
                raise NeXusError("Only NXroot groups can be duplicated")
        except NeXusError as error:
            report_error("Duplicating File", error)

    def read_session(self):
        """Read a session file."""
        self.previous_session = self.settings.options('session')
        self.settings.purge('session')
        self.settings.save()

    def restore_session(self):
        """Restore a session file."""
        for filename in self.previous_session:
            try:
                self.load_file(filename, recent=False)
            except Exception:
                pass
        self.treeview.select_top()

    def reload(self):
        """Reload a NeXus file."""
        try:
            node = self.treeview.get_node()
            if not node.file_exists():
                raise NeXusError(f"{node.nxfilename} does not exist")
            elif self.nodefile_locked(node):
                return
            path = node.nxpath
            root = node.nxroot
            name = root.nxname
            if confirm_action(f"Are you sure you want to reload '{name}'?"):
                root.reload()
                logging.info(f"Workspace '{name}' reloaded")
                try:
                    self.treeview.select_node(self.tree[name][path])
                except Exception:
                    pass
        except NeXusError as error:
            report_error("Reloading File", error)

    def reload_all(self):
        """Reload all modified NeXus files in the tree."""
        try:
            if not confirm_action("Reload all modified files?"):
                return
            for name in self.tree:
                node = self.tree[name]
                if node.is_modified():
                    root = node.nxroot
                    root.reload()
                    logging.info(f"'{name}' reloaded")
                self.treeview.select_top()
        except NeXusError as error:
            report_error("Reloading All Modified Files", error)

    def remove(self):
        """Remove a NeXus file from the tree."""
        try:
            node = self.treeview.get_node()
            name = node.nxname
            if isinstance(node, NXroot):
                if node.nxfilename is None:
                    warning = (f"This will delete '{name}' and cannot be "
                               "undone. Save it to a file if you want to keep "
                               "the data for future use.")
                else:
                    warning = "This will remove it from the tree"
                if confirm_action(f"Are you sure you want to remove '{name}'?",
                                  information=warning):
                    del self.tree[name]
                    self.settings.remove_option('session', node.nxfilename)
                    self.settings.save()
                    logging.info(f"'{name}' removed from tree")
        except NeXusError as error:
            report_error("Removing File", error)

    def remove_all(self):
        """Remove all NeXus files from the tree."""
        try:
            if not confirm_action("Remove all files?"):
                return
            for name in list(self.tree):
                fname = self.tree[name].nxfilename
                del self.tree[name]
                self.settings.remove_option('session', fname)
                self.settings.save()
                logging.info(f"'{name}' removed from tree")
        except NeXusError as error:
            report_error("Removing All Files", error)

    def collapse_tree(self):
        """Collapse the tree."""
        self.treeview.collapse()

    def show_import_dialog(self):
        """Show the import dialog."""
        try:
            import_module = self.readers[self.sender()]
            self.import_dialog = import_module.ImportDialog(parent=self)
            self.import_dialog.show()
        except NeXusError as error:
            report_error("Importing File", error)

    def import_data(self):
        """
        Import a file using the selected import plugin.

        This function is called when the import dialog is accepted. It
        imports the data using the selected plugin, adds it to the tree,
        and selects the new node in the treeview.
        """
        try:
            if self.import_dialog.accepted:
                imported_data = self.import_dialog.get_data()
                try:
                    name = self.tree.get_name(self.import_dialog.import_file)
                except Exception:
                    name = self.tree.get_new_name()
                if isinstance(imported_data, NXentry):
                    self.tree[name] = self.user_ns[name] = NXroot(
                        imported_data)
                elif isinstance(imported_data, NXroot):
                    self.tree[name] = self.user_ns[name] = imported_data
                else:
                    raise NeXusError(
                        'Imported data must be an NXroot or NXentry group')
                self.treeview.select_node(self.tree[name])
                self.treeview.setFocus()
                try:
                    self.default_directory = Path(
                        self.import_dialog.import_file).parent
                except Exception:
                    pass
                logging.info(f"Workspace '{name}' imported")
        except NeXusError as error:
            report_error("Importing File", error)

    def export_data(self):
        """Export data to an external file."""
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
        """Lock the current file, preventing it from being modified."""
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot) and node.nxfilemode:
                node.lock()
                self.treeview.update()
                logging.info(f"Workspace '{node.nxname}' locked")
            else:
                raise NeXusError("Can only lock a saved NXroot group")
        except NeXusError as error:
            report_error("Locking File", error)

    def unlock_file(self):
        """Unlock the current file, allowing it to be modified."""
        try:
            node = self.treeview.get_node()
            if not (isinstance(node, NXroot) and node.nxfilemode):
                raise NeXusError("Can only unlock a saved NXroot group")
            elif not node.file_exists():
                raise NeXusError(f"'{node.nfilename}' does not exist")
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
        """Return True if the file is locked."""
        return is_file_locked(node.nxfile.filename)

    def show_locks(self):
        """Show the file locks dialog."""
        try:
            lockdirectory = nxgetconfig('lockdirectory')
            if lockdirectory is None:
                raise NeXusError("No lock file directory defined")
            elif not Path(lockdirectory).exists():
                raise NeXusError(f"'{lockdirectory}' does not exist")
            dialog = LockDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Showing File Locks", error)

    def backup_file(self):
        """Backup the current file."""
        try:
            node = self.treeview.get_node()
            if node is not None and not node.file_exists():
                raise NeXusError(f"{node.nxfilename} does not exist")
            if isinstance(node, NXroot):
                dir = self.nexpy_dir.joinpath('backups', timestamp())
                dir.mkdir()
                node.backup(dir=dir)
                self.settings.set('backups', node.nxbackup)
                self.settings.save()
                display_message(f"Workspace '{node.nxname}' backed up",
                                information=node.nxbackup)
                logging.info(
                    f"Workspace '{node.nxname}' backed up to "
                    f"'{node.nxbackup}'")
            else:
                raise NeXusError("Can only backup a NXroot group")
        except NeXusError as error:
            report_error("Backing Up File", error)

    def restore_file(self):
        """Restore the current file."""
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot):
                if confirm_action(
                        "Are you sure you want to restore the file?",
                        "This will overwrite the current contents of "
                        f"'{node.nxname}'"):
                    node.restore(overwrite=True)
                    self.treeview.update()
                    logging.info(f"Workspace '{node.nxname}' backed up")
            else:
                raise NeXusError("Can only restore a NXroot group")
        except NeXusError as error:
            report_error("Restoring File", error)

    def manage_backups(self):
        """Open the dialog to manage file backups."""
        try:
            dialog = ManageBackupsDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Managing Backups", error)

    def open_scratch_file(self):
        """Open the scratch file in the tree."""
        try:
            self.tree['w0'] = nxload(self.scratch_file, 'rw')
        except NeXusError as error:
            report_error("Opening Scratch File", error)

    def purge_scratch_file(self):
        """Purge the scratch file of all its contents."""
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
        """Close the scratch file and remove it from the tree."""
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

    def add_plugin_menu(self, plugin_name, plugin_actions, before=None):
        """Add a menu item for a plugin to the menu bar."""
        if before is not None:
            plugin_menu = QtWidgets.QMenu(plugin_name, self)
            self.menu_bar.insertMenu(before.menuAction(), plugin_menu)
        else:
            plugin_menu = QtWidgets.QMenu(plugin_name, self)
            self.menu_bar.addMenu(plugin_menu)
        for action in plugin_actions:
            self.add_menu_action(plugin_menu, QtWidgets.QAction(
                action[0], self, triggered=action[1]))
            self.plugin_actions.append(action)

    def remove_plugin_menu(self, plugin_name):
        """Remove a menu item for a plugin from the menu bar."""
        for action in [action for action
                       in self.menuBar().actions()
                       if action.text().lower() == plugin_name.lower()]:
            self.menuBar().removeAction(action)

    def manage_plugins(self):
        """Open the dialog to manage plugins."""
        try:
            dialog = ManagePluginsDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Managing Plugins", error)

    def plot_data(self, new_plot=False):
        """
        Plot the selected data.

        If the selected data is a group, it must have plottable data. If
        the selected data is a field, it must be plottable or be a
        scalar.
        """
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                self.treeview.status_message(node)
                if isinstance(node, NXgroup) and node.plottable_data:
                    try:
                        if new_plot:
                            self.new_plot_window()
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
        """Overplot the selected data."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                self.treeview.status_message(node)
                node.oplot()
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def plot_line(self):
        """Plot the selected data as a line."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                self.treeview.status_message(node)
                if isinstance(node, NXgroup) and node.plottable_data:
                    try:
                        node.plot(marker='None', linestyle='-')
                        self.plotview.make_active()
                    except (KeyError, NeXusError):
                        pass
                elif node.is_plottable():
                    dialog = PlotDialog(node, lines=True, parent=self)
                    dialog.show()
                else:
                    raise NeXusError("Data not plottable")
        except NeXusError as error:
            report_error("Plotting Data", error)

    def overplot_line(self):
        """Overplot the selected data as a line."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                self.treeview.status_message(node)
                node.oplot(marker='None', linestyle='-')
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Overplotting Data", error)

    def multiplot_data(self):
        """Plot all the signals in the selected group"""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
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
        """Plot all the signals in the selected group as lines"""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                elif not isinstance(node, NXgroup):
                    raise NeXusError("Multiplots only available for groups.")
                elif 'auxiliary_signals' not in node.attrs:
                    raise NeXusError(
                        "Group must have the 'auxiliary_signals' attribute.")
                self.treeview.status_message(node)
                signals = [node.nxsignal]
                signals.extend([node[signal] for signal
                                in node.attrs['auxiliary_signals']
                                if signal != node.nxsignal.nxname])
                colors = get_colors(len(signals))
                for i, signal in enumerate(signals):
                    if i == 0:
                        signal.plot(marker='None', linestyle='-',
                                    color=colors[i])
                    else:
                        signal.oplot(marker='None', linestyle='-',
                                     color=colors[i])
                self.plotview.ax.set_title(node.nxroot.nxname + node.nxpath)
                self.plotview.otab.home()
                self.plotview.legend(signal=True)
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting Data", error)

    def plot_weighted_data(self):
        """Plot the selected data with weights."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                self.treeview.status_message(node)
                node.plot(weights=True)
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting Weighted Data", error)

    def plot_image(self):
        """
        Plot the selected data as an image.
        
        This is meant for nodes that contain RGB(A) image data.
        """
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                self.treeview.status_message(node)
                node.implot()
                self.plotview.make_active()
        except NeXusError as error:
            report_error("Plotting RGB(A) Image Data", error)

    def view_data(self):
        """
        View the selected data.

        This will display the selected data in a table, with its
        metadata (attributes, etc.) displayed above the table. The table
        can be sorted by clicking on the column headers.
        """
        try:
            node = self.treeview.get_node()
            if not self.panel_is_running('View'):
                self.panels['View'] = ViewDialog()
            self.panels['View'].activate(node)
        except NeXusError as error:
            report_error("Viewing Data", error)

    def edit_data(self):
        """Open an editor for the selected group."""
        try:
            node = self.treeview.get_node()
            if not self.panel_is_running('Edit'):
                self.panels['Edit'] = EditDialog()
            self.panels['Edit'].activate(node)
        except NeXusError as error:
            report_error("Editing Data", error)

    def validate_data(self):
        """
        Validate the selected data.

        This will run the NeXus validation tools on the selected data,
        displaying any errors or warnings in a new window. The window
        will be reused if it is already open.
        """
        try:
            node = self.treeview.get_node()
            if not self.panel_is_running('Validate'):
                self.panels['Validate'] = ValidateDialog()
            self.panels['Validate'].activate(node)
        except NeXusError as error:
            report_error("Validating Data", error)
        
    def add_group(self):
        """Add a new NeXus group to the selected node."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                elif node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")
                dialog = GroupDialog(node, parent=self)
                dialog.show()
        except NeXusError as error:
            report_error("Adding Group", error)

    def add_field(self):
        """Add a new NeXus field to the selected node."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                elif node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")
                dialog = FieldDialog(node, parent=self)
                dialog.show()
        except NeXusError as error:
            report_error("Adding Field", error)

    def add_attribute(self):
        """Add a new NeXus attribute to the selected node."""
        try:
            node = self.treeview.get_node()
            if node is not None:
                if not node.exists():
                    raise NeXusError(f"{node.nxfullpath} does not exist")
                elif node.nxfilemode == 'r':
                    raise NeXusError("NeXus file is locked")
                dialog = AttributeDialog(node, parent=self)
                dialog.show()
        except NeXusError as error:
            report_error("Adding Attribute", error)

    def rename_data(self):
        """
        Rename the selected data.
        
        Opens a dialog allowing the user to enter a new name for the
        selected data.
        """
        try:
            if self is not None:
                node = self.treeview.get_node()
                if node is not None:
                    if not node.exists():
                        raise NeXusError(f"{node.nxfullpath} does not exist")
                    elif (isinstance(node, NXroot) or
                          node.nxgroup.nxfilemode != 'r'):
                        path = node.nxpath
                        dialog = RenameDialog(node, parent=self)
                        dialog.show()
                        logging.info(f"'{path}' renamed as '{node.nxpath}'")
                    else:
                        raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Renaming Data", error)

    def copy_node(self, node):
        """
        Copies the given node into a temporary NeXus file.

        This method is used by the 'copy' and 'cut' actions to copy a node
        into a temporary NeXus file. The temporary file is created in a
        tempfile and is deleted when the application is closed. The method
        returns the copied node.

        The method first creates a new temporary NeXus file with a single
        group named 'entry'. It then copies the given node into the 'entry'
        group. If the given node is an NXlink, it is resolved to the actual
        node. The method then sets the 'link' attribute of the 'entry' group
        to a tuple containing the name, path, and filename of the copied
        node.

        Parameters
        ----------
        node : NXobject
            The node to be copied.

        Returns
        -------
        NXobject
            The copied node.
        """
        import tempfile
        self._memroot = nxload(tempfile.mkstemp(suffix='.nxs')[1], mode='w',
                               driver='core', backing_store=False)
        self._memroot['entry'] = NXentry()
        if isinstance(node, NXlink):
            node = node.nxlink
        self._memroot['entry'][node.nxname] = node
        if node.nxfilename is None:
            self._memroot['entry'].attrs['link'] = [node.nxname, node.nxpath,
                                                    'None']
        else:
            self._memroot['entry'].attrs['link'] = [node.nxname, node.nxpath,
                                                    node.nxfilename]
        return self._memroot['entry'][node.nxname]

    @property
    def copied_link(self):
        """The link to the copied data in the core memory NeXus file."""
        try:
            return self._memroot['entry'].attrs['link']
        except Exception:
            return None

    def copy_data(self):
        """
        Copy a node to the core memory NeXus file.

        This method copies the currently selected node to a temporary
        NeXus file in core memory. If the currently selected node is an
        NXroot, a NeXusError is raised. The copied node is stored in the
        'copied_node' attribute of the main window. The method logs a
        message to the log file if successful.
        """
        try:
            node = self.treeview.get_node()
            if not isinstance(node, NXroot):
                self.copied_node = self.copy_node(node)
                logging.info(f"'{node.nxpath}' copied")
            else:
                raise NeXusError(
                    "Use 'Duplicate File' to copy an NXroot group")
        except NeXusError as error:
            report_error("Copying Data", error)

    def cut_data(self):
        """
        Cut the selected data.

        This method cuts the currently selected node from the selected
        group and copies it into the core memory NeXus file. If the
        currently selected node is an NXroot, a NeXusError is raised. The
        copied node is stored in the 'copied_node' attribute of the main
        window. The method logs a message to the log file if successful.
        """
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
                if confirm_action("Are you sure you want to cut "
                                  f"'{node.nxroot.nxname+node.nxpath}'?"):
                    self.copied_node = self.copy_node(node)
                    logging.info(f"'{node.nxpath}' cut")
                    del node.nxgroup[node.nxname]
        except NeXusError as error:
            report_error("Cutting Data", error)

    def paste_data(self):
        """
        Paste data from the copy buffer into the selected node.

        This method pastes the data in the copy buffer into the selected
        node. If the selected node is an NXgroup, the data is pasted into
        the group. If the selected node is an NXfield, a NeXusError is
        raised. If the NeXus file is locked, a NeXusError is raised. The
        method logs a message to the log file if successful.
        """
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
                    logging.info(
                        f"'{self.copied_node.nxpath}' pasted to "
                        f"'{node.nxpath}'")
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data", error)

    def paste_link(self):
        """
        Paste the data in the copy buffer as a link.

        This method will paste the data in the copy buffer into the
        selected node as a link. If the selected node is an NXgroup and
        the NeXus file is not locked, a dialog will appear asking for
        the name of the link. The method logs a message to the log file
        if successful.
        """
        
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXgroup) and self.copied_link is not None:
                if node.nxfilemode != 'r':
                    dialog = PasteDialog(node, link=True, parent=self)
                    dialog.show()
                    logging.info(
                        f"'{self.copied_node.nxpath}' pasted as link to "
                        f"'{node.nxpath}'")
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Pasting Data as Link", error)

    def delete_data(self):
        """
        Delete a NeXus node from the tree.

        This method will delete the selected NeXus node from the tree.
        If the selected node is an NXroot, a NeXusError is raised. If the
        selected node is in an externally linked NXgroup, a NeXusError is
        raised. If the NeXus file for the selected node is locked, a
        NeXusError is raised. If the user confirms the deletion, the
        method logs a message to the log file if successful.
        """
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXroot) and node.nxfilemode:
                raise NeXusError("Cannot delete a NeXus file")
            elif node.nxgroup.is_external():
                raise NeXusError(
                    "Cannot delete object in an externally linked group")
            elif node.nxgroup.nxfilemode and node.nxgroup.nxfilemode == 'r':
                raise NeXusError("NeXus file is locked")
            elif confirm_action("Are you sure you want to delete "
                                f"'{node.nxroot.nxname+node.nxpath}'?"):
                del node.nxgroup[node.nxname]
                logging.info(f"'{node.nxroot.nxname + node.nxpath}' deleted")
        except NeXusError as error:
            report_error("Deleting Data", error)

    def show_link(self):
        """
        Select the field or group to which the selected item is linked,
        if it is an NXlink object, *i.e.*, shown with a link icon. If
        the link is external, the linked file is automatically opened
        and the linked object is selected.
        """
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXlink):
                if (node.nxfilename and
                        node.nxfilename != node.nxroot.nxfilename):
                    fname = Path(node.nxfilename)
                    if not Path(fname).is_absolute():
                        fname = Path(node.nxroot.nxfilename).parent.joinpath(
                            node.nxfilename)
                    if not fname.exists():
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
        """
        Set the plottable signal either to the selected field or to any
        field within the selected group. A dialog box allows the user to
        specify axes with compatible dimensions to plot the data
        against.

        The dialog box will be invoked if the selected node is an
        NXobject and the NeXus file is not locked. If the NeXus file is
        locked, a NeXusError is raised. The method logs a message to the
        log file if successful.

        Note
        ----
        The use of the 'Add Data' and 'Set Signal' menu items allows, in
        principle, an entire NeXus data tree to be constructed using
        menu calls.
        """
        try:
            node = self.treeview.get_node()
            if isinstance(node, NXobject):
                if node.nxfilemode != 'r':
                    dialog = SignalDialog(node, parent=self)
                    dialog.show()
                    logging.info(f"Signal set for '{node.nxgroup.nxpath}'")
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Setting Signal", error)

    def set_default(self):
        """
        Set the default attribute in the parent group to the currently
        selected group, *i.e.*, if the selected group is an NXdata
        (NXentry) group, the attribute will be set in the parent NXentry
        (NXroot) group. The default attribute is used to identify the
        default data to be plotted.

        Note
        ----
        When a NXdata group is set as the default, the parent NXentry
        group is also set as the default in the parent NXroot group
        provided one has not already been set. The default entry can be
        overridden.
        """
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
                    logging.info(f"Default set to '{node.nxpath}'")
                else:
                    raise NeXusError("NeXus file is locked")
        except NeXusError as error:
            report_error("Setting Default", error)

    def fit_data(self):
        """
        Fit the selected data.

        This will trigger a dialog box, which allows functions to be
        chosen and parameters to be initialized before calling a
        non-linear least-squares fitting module.

        If the selected node is an NXdata group, it will be fitted. If
        the selected node is an NXentry or NXprocess group and its title
        starts with 'Fit', the data field of this group will be fitted.
        In all other cases, a NeXusError is raised.

        If the data is more than one-dimensional, a NeXusError is
        raised.

        See also
        --------
        :ref:`Fitting NeXus Data`_.
        """
        from .fitdialogs import FitDialog
        try:
            node = self.treeview.get_node()
            if node is None:
                return
            elif ((isinstance(node, NXentry) or isinstance(node, NXprocess))
                  and node.nxtitle.startswith('Fit')):
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
            logging.info(f"Fitting invoked on'{node.nxpath}'")
        except NeXusError as error:
            report_error("Fitting Data", error)

    def fit_weighted_data(self):
        """
        Fit the selected data with weights.

        This will trigger a dialog box, which allows functions to be
        chosen and parameters to be initialized before calling a
        non-linear least-squares fitting module.

        If the selected node is an NXdata group, it will be fitted. If
        the selected node is an NXentry or NXprocess group and its title
        starts with 'Fit', the data field of this group will be fitted.
        In all other cases, a NeXusError is raised.

        If the data is more than one-dimensional, a NeXusError is
        raised.

        See also
        --------
        :ref:`Fitting NeXus Data`_.
        """
        from .fitdialogs import FitDialog
        try:
            node = self.treeview.get_node()
            if node is None:
                return
            elif isinstance(node, NXdata):
                if node.ndim > 1:
                    raise NeXusError(
                        "Fitting only enabled for one-dimensional data")
            else:
                raise NeXusError("Select an NXdata group")
            if 'Fit' not in self.panels:
                self.panels['Fit'] = FitDialog()
            self.panels['Fit'].activate(node.weighted_data())
            logging.info(f"Fitting invoked on'{node.nxpath}'")
        except NeXusError as error:
            report_error("Fitting Data", error)

    def make_active_action(self, number, label):
        """
        Create an action for a new window and add it to the 'Window'
        menu.
        
        Parameters
        ----------
        number : int
            The number of the window, used to generate the shortcut key.
        label : str
            The label of the window, used to create the action text.
        """
        if label == 'Projection':
            self.active_action[number] = QtWidgets.QAction(
                label, self, shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+P"),
                triggered=lambda: self.plotviews[label].make_active(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        elif label == 'Scan':
            self.active_action[number] = QtWidgets.QAction(
                label, self, shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+S"),
                triggered=lambda: self.plotviews[label].make_active(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        elif label == 'Fit':
            self.active_action[number] = QtWidgets.QAction(
                label, self, shortcut=QtGui.QKeySequence("Ctrl+Shift+Alt+F"),
                triggered=lambda: self.plotviews[label].make_active(),
                checkable=False)
            self.window_menu.addAction(self.active_action[number])
        elif label.startswith('Rotation'):
            self.active_action[number] = QtWidgets.QAction(
                label, self,
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
            self.active_action[number] = QtWidgets.QAction(
                label, self, triggered=lambda: self.make_active(number),
                checkable=True)
            if number < 10:
                self.active_action[number].setShortcut(
                    QtGui.QKeySequence(f"Ctrl+{number}"))
            self.window_menu.insertAction(before_action,
                                          self.active_action[number])
        self.make_active(number)

    def new_plot_window(self):
        """Create a new plot window"""
        return NXPlotView()

    def close_window(self):
        """
        Close the currently active window.

        If the window is a dialog, it will be closed. If the window is a
        plot window, it will be closed and removed from the 'Window'
        menu. If the window is not a dialog and not a plot window, it
        will be ignored.

        If an exception is raised, it is ignored.
        """
        windows = self.dialogs
        windows += [self.plotviews[pv]
                    for pv in self.plotviews if pv != 'Main']
        for window in windows:
            try:
                if window.isActiveWindow():
                    window.close()
                    break
            except Exception:
                pass

    def equalize_plots(self):
        """
        Resize all plot windows except the main window and the currently
        active window to the size of the currently active window.

        This is done by iterating over all the plot windows in the
        plotviews dictionary, and resizing each one to the size of the
        currently active window. The currently active window is not
        resized.
        """
        for label in [label for label in self.plotviews
                      if (label != 'Main' and label != self.plotview.label)]:
            self.plotviews[label].resize(self.plotview.size())

    def cascade_plots(self):
        """Cascade plot windows across the available screen."""
        pvs = sorted([self.plotviews[pv] for pv in self.plotviews
                      if self.plotviews[pv].number < 100],
                     key=lambda obj: obj.number)
        self.tile_panels()
        available_geometry = self.app.app.primaryScreen().availableGeometry()
        left, top = available_geometry.left(), available_geometry.top()
        self.move(left, top)
        if len(pvs) <= 1:
            return
        last_left = available_geometry.right() - pvs[-1].width()
        last_top = available_geometry.bottom() - pvs[-1].height()
        offset_x = int((last_left - available_geometry.left()) / (len(pvs)-1))
        offset_y = int((last_top - available_geometry.top()) / (len(pvs)-1))
        for pv in pvs[1:]:
            left += offset_x
            top += offset_y
            pv.move(left, top)
            pv.make_active()

    def tile_plots(self):
        """Tile plot windows across the available screen."""
        pvs = sorted([self.plotviews[pv] for pv in self.plotviews
                      if pv != 'Main' and self.plotviews[pv].number < 100],
                     key=lambda obj: obj.number)
        self.tile_panels()
        available_geometry = self.app.app.primaryScreen().availableGeometry()
        left, top = available_geometry.left(), available_geometry.top()
        self.move(left, top)
        if len(pvs) <= 1:
            return
        left_min = self.treeview.minimumWidth()
        left += left_min
        if sys.platform == 'darwin':
            top_min = 0
        else:
            top_min = (self.frameGeometry().height() - self.geometry().height()
                       + self.menuBar().height())
        top += top_min
        pvs[0].move(left, top)
        pvs[0].make_active()
        for pv in pvs[1:]:
            left += pv.canvas.width()
            if left + pv.canvas.width() > available_geometry.right():
                left = available_geometry.left() + left_min
                top += pv.canvas.height()
            if top + pv.canvas.height() > available_geometry.bottom():
                top = available_geometry.top() + top_min
            pv.move(left, top)
            pv.make_active()

    def tile_panels(self):
        """Tile panels along the bottom of the available screen."""
        available_geometry = self.app.app.primaryScreen().availableGeometry()
        left, bottom = available_geometry.left(), available_geometry.bottom()
        for p in self.panels:
            panel = self.panels[p]
            height = panel.frameGeometry().height()
            width = panel.frameGeometry().width()
            if panel.isVisible():
                if left + width > available_geometry.right():
                    left = available_geometry.left()
                panel.move(left, bottom - height)
                left += width

    def update_active(self, number):
        """
        Update the active window in 'Window' menu.

        This is called whenever a new window is created or an existing
        window is closed. It iterates over all the actions in the
        'Window' menu and checks which action is currently checked. It
        then unchecks the previously active action and checks the
        action of the currently active window. If the number does not
        correspond to any window, it does nothing.

        Parameters
        ----------
        number : int
            The number of the window to be made active.
        """
        for num in self.active_action:
            if self.active_action[num].isChecked():
                self.previous_active = num
                self.active_action[num].setChecked(False)
        if number in self.active_action:
            self.active_action[number].setChecked(True)

    def make_active(self, number):
        """
        Make a window active.

        This function makes the window with the given number active. It
        does this by updating the active window in the 'Window' menu, and
        calling the make_active method of the window.

        Parameters
        ----------
        number : int
            The number of the window to be made active.
        """
        if number in self.active_action:
            self.update_active(number)
            self.plotviews[self.active_action[number].text()].make_active()

    def reset_axes(self):
        """
        Reset the plot limits to the original values.

        This function makes the window with the given number active and
        resets the plot limits to the original values. It does this by
        calling the reset_plot_limits method of the window.
        """
        try:
            self.plotview.reset_plot_limits()
        except NeXusError as error:
            report_error("Resetting Plot Limits", error)

    def edit_settings(self):
        """
        Edit NeXpy settings.

        This function launches the Settings Dialog, which is used to
        edit the various settings used by NeXpy.
        """
        try:
            dialog = SettingsDialog(parent=self)
            dialog.show()
        except NeXusError as error:
            report_error("Editing Settings", error)

    def show_tree(self):
        """Bring the tree view to the front and give it focus."""
        self.raise_()
        self.treeview.raise_()
        self.treeview.activateWindow()
        self.treeview.setFocus()

    def show_shell(self):
        """Bring the shell view to the front and give it focus."""
        self.raise_()
        self.shellview.raise_()
        self.shellview.activateWindow()
        self.shellview.setFocus()

    def show_log(self):
        """Display the log file in a separate window"""
        try:
            if self.log_window in self.dialogs:
                self.log_window.show_log()
            else:
                self.log_window = LogDialog(parent=self)
        except NeXusError as error:
            report_error("Showing Log File", error)

    def panel_is_running(self, panel):
        """
        Check if a panel is running.

        Parameters
        ----------
        panel : str
            The name of the panel to check.

        Returns
        -------
        bool
            True if the panel is running, False otherwise.
        """
        if panel in self.panels:
            if self.panels[panel].is_running():
                return True
            else:
                self.panels[panel].close()
                return False
        else:
            return False

    def show_customize_panel(self):
        """Show the customize panel."""
        try:
            if not self.panel_is_running('Customize'):
                self.panels['Customize'] = CustomizeDialog()
            self.panels['Customize'].activate(self.active_plotview.label)
        except NeXusError as error:
            report_error("Showing Customize Panel", error)

    def show_limits_panel(self):
        """Show the limits panel."""
        try:
            if not self.panel_is_running('Limits'):
                self.panels['Limits'] = LimitDialog()
            self.panels['Limits'].activate(self.active_plotview.label)
        except NeXusError as error:
            report_error("Showing Limits Panel", error)

    def show_all_limits(self):
        """Show the limits panel for all currently open plots."""
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
        """Show the projection panel."""
        if (self.active_plotview.label == 'Projection'
                or self.plotview.ndim == 1):
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
        """Show the scan panel."""
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
        """Show the script editor opening a new script if necessary."""
        if not self.panel_is_running('Editor'):
            self.panels['Editor'] = NXScriptWindow()
        if self.panels['Editor'].count == 0:
            self.new_script()
        else:
            self.panels['Editor'].raise_()
            self.panels['Editor'].activateWindow()

    def open_script_window(self, file_name):
        """Open the script editor."""
        if 'Editor' not in self.panels:
            self.panels['Editor'] = NXScriptWindow()
        self.panels['Editor'].activate(file_name)

    def new_script(self):
        """Open an editor for a new script."""
        try:
            file_name = None
            self.open_script_window(file_name)
            logging.info("Creating new script")
        except NeXusError as error:
            report_error("Editing New Script", error)

    def open_script(self):
        """Open an existing script file in the script editor."""
        try:
            script_dir = self.nexpy_dir.joinpath('scripts')
            file_filter = ';;'.join(("Python Files (*.py)",
                                     "Any Files (*.* *)"))
            file_name = getOpenFileName(self, 'Open Script', script_dir,
                                        file_filter)
            if file_name:
                self.open_script_window(file_name)
                logging.info(f"NeXus script '{file_name}' opened")
        except NeXusError as error:
            report_error("Editing Script", error)

    def open_startup_script(self):
        """Open the startup script in the script editor."""
        try:
            file_name = self.nexpy_dir / 'config.py'
            self.open_script_window(file_name)
            logging.info(f"NeXus script '{file_name}' opened")
        except NeXusError as error:
            report_error("Editing Startup Script", error)

    def open_script_file(self):
        """Open the script file selected in the Script Menu."""
        try:
            file_name = self.scripts[self.sender()][1]
            self.open_script_window(file_name)
            logging.info(f"NeXus script '{file_name}' opened")
        except NeXusError as error:
            report_error("Opening Script", error)

    def add_script_directory(self, directory, menu):
        """
        Recursively add actions for Python scripts in directory to the
        provided menu.

        Parameters
        ----------
        directory : Path
            The directory to search for Python scripts.
        menu : QMenu
            The menu to add the actions to.
        """
        if directory is None or not Path(directory).is_dir():
            menu.setEnabled(False)
            return
        directory = Path(directory)
        names = sorted(path.name for path in directory.iterdir())
        empty_directory = True
        for name in names:
            item_path = directory / name
            if name.startswith('.') or name.startswith('_'):
                continue
            if item_path.is_dir():
                submenu = QtWidgets.QMenu(name, self)
                menu.addMenu(submenu)
                self.add_script_directory(item_path, submenu)
            elif item_path.suffix == '.py':
                self.add_script_action(item_path, menu)
                empty_directory = False
        if empty_directory:
            menu.setEnabled(False)
        else:
            menu.setEnabled(True)

    def add_script_action(self, file_name, menu):
        """
        Add an action for a Python script to the provided menu.

        Parameters
        ----------
        file_name : Path
            The path to the Python script.
        menu : QMenu
            The menu to add the action to.
        """
        name = Path(file_name).name
        script_action = QtWidgets.QAction(name, self,
                                          triggered=self.open_script_file)
        self.add_menu_action(menu, script_action, self)
        self.scripts[script_action] = (menu, str(file_name))

    def refresh_script_menus(self):
        self.public_script_menu.clear()
        self.add_script_directory(self.public_script_dir,
                                  self.public_script_menu)
        self.private_script_menu.clear()
        self.add_script_directory(self.script_dir, self.private_script_menu)

    def _open_nexpy_online_help(self):
        """Open the NeXpy online help in a web browser."""
        url = "https://nexpy.github.io/nexpy/"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexusformat_online_notebook(self):
        """Open the nexusformat online notebook in a web browser."""
        url = (
            "https://colab.research.google.com/github/nexpy/nexusformat/blob/"
            "master/src/nexusformat/notebooks/nexusformat.ipynb")
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexus_online_help(self):
        """Open the Nexus base classes in a web browser."""
        url = "http://download.nexusformat.org/doc/html/classes/base_classes/"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexpy_release_notes(self):
        """Open NeXpy release notes in a web browser."""
        url = "https://github.com/nexpy/nexpy/releases"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexpy_issues(self):
        """Open NeXpy issues in a web browser."""
        url = "https://github.com/nexpy/nexpy/issues"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexusformat_release_notes(self):
        """Open nexusformat release notes in a web browser."""
        url = "https://github.com/nexpy/nexusformat/releases"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_nexusformat_issues(self):
        """Open nexusformat issues in a web browser."""
        url = "https://github.com/nexpy/nexusformat/issues"
        webbrowser.open(url, new=1, autoraise=True)

    def _open_ipython_online_help(self):
        """Open the IPython online help in a web browser."""
        url = "https://ipython.readthedocs.io/en/stable/"
        webbrowser.open(url, new=1, autoraise=True)

    def open_example_file(self):
        """Open an example NeXus file in read-only mode."""
        default_directory = self.default_directory
        self.default_directory = package_files('nexpy').joinpath('examples')
        self.open_file()
        self.default_directory = default_directory

    def open_example_script(self):
        """Open an example NeXus script in the script editor."""
        script_dir = package_files('nexpy').joinpath('examples', 'scripts')
        file_filter = ';;'.join(("Python Files (*.py)",
                                 "Any Files (*.* *)"))
        file_name = getOpenFileName(self, 'Open Script', script_dir,
                                    file_filter)
        if file_name:
            self.open_script_window(file_name)
            logging.info(f"NeXus script '{file_name}' opened")

    def toggle_menu_bar(self):
        """Toggle the visibility of the menu bar."""
        menu_bar = self.menu_bar
        if menu_bar.isVisible():
            menu_bar.setVisible(False)
        else:
            menu_bar.setVisible(True)

    def toggleMinimized(self):
        """Toggle the window between minimized and normal."""
        if not self.isMinimized():
            self.showMinimized()
        else:
            self.showNormal()

    def toggleMaximized(self):
        """Toggle the window between maximized and normal."""
        if not self.isMaximized():
            self.showMaximized()
        else:
            self.showNormal()

    def toggleFullScreen(self):
        """Toggle the window between full screen and normal."""
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
        """Set the paging of the console."""
        self.console._set_paging(paging)

    def restart_kernel_console(self):
        """Restart the kernel in the console."""
        self.console.request_restart_kernel()

    def interrupt_kernel_console(self):
        """Interrupt the kernel in the console."""
        self.console.request_interrupt_kernel()

    def toggle_confirm_restart_console(self):
        """Toggle the confirm restart flag in the console."""
        widget = self.console
        widget.confirm_restart = not widget.confirm_restart
        self.confirm_restart_kernel_action.setChecked(widget.confirm_restart)

    def update_restart_checkbox(self):
        """Update the confirm restart flag in the console."""
        if self.console is None:
            return
        widget = self.console
        self.confirm_restart_kernel_action.setChecked(widget.confirm_restart)

    def cut_console(self):
        """Cut text in the console."""
        widget = self.app.app.focusWidget()
        if widget == self.console._control:
            widget = self.console
        try:
            if widget.can_cut():
                widget.cut()
        except Exception:
            pass

    def copy_console(self):
        """Copy text in the console."""
        widget = self.app.app.focusWidget()
        if widget == self.console._control:
            widget = self.console
        try:
            widget.copy()
        except Exception:
            pass

    def copy_raw_console(self):
        """Copy raw text in the console."""
        self.console._copy_raw_action.trigger()

    def paste_console(self):
        """Paste text in the console."""
        widget = self.app.app.focusWidget()
        if widget == self.console._control:
            widget = self.console
        try:
            if widget.can_paste():
                widget.paste()
        except Exception:
            pass

    def undo_console(self):
        """Undo text in the console."""
        self.console.undo()

    def redo_console(self):
        """Redo text in the console."""
        self.console.redo()

    def print_action_console(self):
        """Print text in the console."""
        self.console.print_action.trigger()

    def select_all_console(self):
        """Select all text in the console."""
        self.console.select_all_action.trigger()

    def increase_font_size_console(self):
        """Increase font size in the console."""
        self.console.increase_font_size.trigger()

    def decrease_font_size_console(self):
        """Decrease font size in the console."""
        self.console.decrease_font_size.trigger()

    def reset_font_size_console(self):
        """Reset font size in the console."""
        self.console.reset_font_size.trigger()

    def intro_console(self):
        """Print the IPython intro in the console."""
        self.console.execute("?")

    def quickref_console(self):
        """Print the IPython quickref in the console."""
        self.console.execute("%quickref")

    def close_files(self):
        """
        Close all open NeXus files in the user namespace.

        This should be called before the application is closed to ensure
        that any changes are flushed to the files and other processes
        can read the files if necessary.
        """
        for root in [n for n in self.user_ns
                     if isinstance(self.user_ns[n], NXroot)]:
            try:
                self.user_ns[root].close()
            except Exception:
                pass

    def closeEvent(self, event):
        """Customize the close event to confirm request to quit."""
        if confirm_action("Are you sure you want to quit NeXpy?",
                          icon=self.app.icon_pixmap):
            self.console.kernel_client.stop_channels()
            self.console.kernel_manager.shutdown_kernel()
            self.close_files()
            logging.info('NeXpy closed\n'+80*'-')
            self._app.quit()
            return event.accept()
        else:
            return event.ignore()
