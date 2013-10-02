"""The Qt MainWindow for NeXpy

"""

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------

# stdlib imports
import os
import sys
import imp
import re
import webbrowser

# System library imports
from IPython.external.qt import QtGui,QtCore

# local imports
from qtkernelmanager import QtKernelManager
from treeview import NXTreeView
from plotview import NXPlotView
from datadialogs import *
from nexpy.api.nexus.tree import nxload, NeXusError
from nexpy.api.nexus.tree import NXgroup, NXfield, NXroot, NXentry, NXdata

# IPython imports
from IPython.frontend.qt.console.ipython_widget import IPythonWidget

#-----------------------------------------------------------------------------
# Classes
#-----------------------------------------------------------------------------

class MainWindow(QtGui.QMainWindow):

    #---------------------------------------------------------------------------
    # 'object' interface
    #---------------------------------------------------------------------------

    def __init__(self, app, tree, confirm_exit, config=None):
        """ Create a MainWindow for the application
        
        Parameters
        ----------
        
        app : reference to QApplication parent
        """

        super(MainWindow, self).__init__()
        self.resize(1000, 800)
        self._app = app
        self._app.setStyle("QMacStyle")
        self.config = config
        self.confirm_exit = confirm_exit
        self.default_directory = os.path.expanduser('~')
        self.copied_node = None

        mainwindow = QtGui.QWidget()

        rightpane = QtGui.QWidget()

        self.plotview = NXPlotView(label="Main",parent=rightpane)
        self.plotview.setMinimumSize(700, 600)

        self.console = IPythonWidget(config=self.config, parent=rightpane)
        self.console.setMinimumSize(700, 200)
        self.console.setSizePolicy(QtGui.QSizePolicy.Expanding, QtGui.QSizePolicy.Fixed)
        self.console._confirm_exit = self.confirm_exit
        self.console.gui_completion = 'droplist'
        self.console.kernel_manager = QtKernelManager(config=self.config)
        self.console.kernel_manager.start_kernel()
        self.console.kernel_manager.start_channels()
        self.shell = self.console.kernel_manager.kernel.shell
        self.user_ns = self.console.kernel_manager.kernel.shell.user_ns

        rightlayout = QtGui.QVBoxLayout()        
        rightlayout.addWidget(self.plotview)
        rightlayout.addWidget(self.console)
        rightlayout.setContentsMargins(0, 0, 0, 0)
        rightpane.setLayout(rightlayout)
        
        self.tree = tree
        self.treeview = NXTreeView(self.tree,parent=mainwindow)
        self.treeview.setMinimumWidth(200)
        self.treeview.setMaximumWidth(400)
        self.treeview.setSizePolicy(QtGui.QSizePolicy.Preferred, QtGui.QSizePolicy.Expanding)
        self.user_ns['plotview'] = self.plotview
        self.user_ns['treeview'] = self.treeview
        self.user_ns['tree'] = self.tree
        self.user_ns['mainwindow'] = self

        mainlayout = QtGui.QHBoxLayout()
        mainlayout.addWidget(self.treeview)
        mainlayout.addWidget(rightpane)
        mainlayout.setContentsMargins(0, 0, 0, 0)
        mainwindow.setLayout(mainlayout)

        self.setCentralWidget(mainwindow)

        base_path = os.path.abspath(os.path.dirname(__file__))
        icon_path = os.path.join(base_path, 'resources', 'icon', 'NeXpy.svg')
        self.import_path = os.path.join(os.path.abspath(os.path.dirname(base_path)), 
                                        'readers')
        self._app.icon = QtGui.QIcon(icon_path)
        QtGui.QApplication.setWindowIcon(self._app.icon)

        self.init_menu_bar()

        self.setWindowTitle('NeXpy')
        self.statusBar().showMessage('Ready')
        self.console._control.setFocus()

    def close(self,current):
        """ Called when you need to try to close the console widget.
        """

        title = self.window().windowTitle()
        cancel = QtGui.QMessageBox.Cancel
        okay = QtGui.QMessageBox.Ok
        reply = QtGui.QMessageBox.question(self, title,
                "Are you sure you want to close this Console?"+
                "\nThe Kernel and other Consoles will remain active.",
                okay|cancel, defaultButton=okay)
        if reply == okay:
            pass

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
        self.init_file_menu()
        self.init_edit_menu()
        self.init_data_menu()
        self.init_view_menu()
        self.init_magic_menu()
        self.init_window_menu()
        self.init_help_menu()
    
    def init_file_menu(self):
        self.file_menu = self.menuBar().addMenu("&File")
        
        self.file_menu.addSeparator()

        self.newworkspace_action=QtGui.QAction("&New...",
            self,
            shortcut=QtGui.QKeySequence.New,
            triggered=self.new_workspace
            )
        self.add_menu_action(self.file_menu, self.newworkspace_action, True)  
        
        self.openfile_action=QtGui.QAction("&Open (read only)",
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
        self.add_menu_action(self.file_menu, self.openeditablefile_action, True)  

        self.savefile_action=QtGui.QAction("&Save",
            self,
            shortcut=QtGui.QKeySequence.Save,
            triggered=self.save_file
            )
        self.add_menu_action(self.file_menu, self.savefile_action, True)  
        
        self.savefileas_action=QtGui.QAction("Save as...",
            self,
            shortcut=QtGui.QKeySequence.SaveAs,
            triggered=self.save_file_as
            )
        self.add_menu_action(self.file_menu, self.savefileas_action, True)  
        
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
        self.edit_menu = self.menuBar().addMenu("&Edit")
        
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

        self.copy_raw_action = QtGui.QAction("Copy (&Raw Text)",
            self,
            shortcut="Ctrl+Shift+C",
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
        self.data_menu = self.menuBar().addMenu("Data")
        
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
            triggered=self.copy_data
            )
        self.add_menu_action(self.data_menu, self.copy_action, True)  

        self.paste_action=QtGui.QAction("Paste Data",
            self,
            triggered=self.paste_data
            )
        self.add_menu_action(self.data_menu, self.paste_action, True)  

        self.delete_action=QtGui.QAction("Delete Data",
            self,
            triggered=self.delete_data
            )
        self.add_menu_action(self.data_menu, self.delete_action, True)  

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
        self.view_menu = self.menuBar().addMenu("&View")

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
            shortcut='Ctrl+L',
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
            for file in os.listdir(private_path):
                name, ext = os.path.splitext(file)
                if name <> '__init__' and ext.startswith('.py'):
                    self.import_names.add(name)
        sys.path.append(self.import_path)
        for file in os.listdir(self.import_path):
            name, ext = os.path.splitext(file)
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
        if self.import_dialog.accepted:
            workspace = self.treeview.tree.get_new_name()
            self.treeview.tree[workspace] = self.import_dialog.get_data()

    def new_workspace(self):
        default_name = self.treeview.tree.get_new_name()
        name, ok = QtGui.QInputDialog.getText(self, 'New Workspace', 
                         'Workspace Name:', text=default_name)        
        if name and ok:
            self.treeview.tree[name] = NXroot(NXentry())
  
    def open_file(self):
        fname, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open File (Read Only)',
                         self.default_directory, 
                         "NeXus Files (*.nxs *.nx5 *.h5 *.nx4 *.hdf *.xml)")
        workspace = self.treeview.tree.get_name(fname)
        self.treeview.tree[workspace] = self.user_ns[workspace] = nxload(fname)
        self.default_directory = os.path.dirname(fname)
  
    def open_editable_file(self):
        fname, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open File (Read/Write)',
                         self.default_directory, 
                         "NeXus Files (*.nxs *.nx5 *.h5 *.nx4 *.hdf *.xml)")
        workspace = self.treeview.tree.get_name(fname)
        self.treeview.tree[workspace] = self.user_ns[workspace] = nxload(fname, 'rw')
        self.default_directory = os.path.dirname(fname)

    def save_file(self):
        node = self.treeview.getnode()
        if node is None:
            return
        elif node.nxfile and isinstance(node, NXroot):
            try:
                node.save()
            except NeXusError, error_message:
                QtGui.QMessageBox.critical(
                      self, "Error saving file", str(error_message),
                      QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
        else:
            default_name = os.path.join(self.default_directory,node.nxname)
            fname, _ = QtGui.QFileDialog.getSaveFileName(self, 
                             "Choose a Filename",
                             default_name, 
                             "NeXus Files (*.nxs *.nx5 *.h5 *.nx4 *.hdf *.xml)")
            if fname:
                try:
                    node.save(fname)
                except NeXusError, error_message:
                    QtGui.QMessageBox.critical(
                          self, "Error saving file", str(error_message),
                          QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def save_file_as(self):
        node = self.treeview.getnode()
        if node is None:
            return
        default_name = os.path.join(self.default_directory,node.nxname)
        fname, _ = QtGui.QFileDialog.getSaveFileName(self, "Choose a Filename",
                         default_name, 
                         "NeXus Files (*.nxs *.nx5 *.h5 *.nx4 *.hdf *.xml)")
        if fname:
            try:
                node.save(fname)
            except NeXusError, error_message:
                QtGui.QMessageBox.critical(
                    self, "Error saving file", str(error_message),
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def plot_data(self, fmt='o'):
        node = self.treeview.getnode()
        if node:        
            self.treeview.statusmessage(node)
            try:
                node.plot(fmt)
            except KeyError:
                dialog = PlotDialog(node, self)
                dialog.show()
            except NeXusError:
                dialog = PlotDialog(node, self)
                dialog.show()

    def overplot_data(self, fmt='o'):
        node = self.treeview.getnode()
        if node:        
            self.treeview.statusmessage(node)
            try:
                node.oplot(fmt)
            except:
                pass

    def add_data(self):
        node = self.treeview.getnode()      
        if node:
            dialog = AddDialog(node, self)
            dialog.show()
        else:
            self.new_workspace()    

    def initialize_data(self):
        node = self.treeview.getnode()      
        if node:
            if isinstance(node, NXgroup):
                dialog = InitializeDialog(node, self)
                dialog.show()
            else:
                QtGui.QMessageBox.critical(
                    self, "NXfield node selected", 
                    "An NXfield can only be added to an NXgroup",
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)


    def rename_data(self):
        node = self.treeview.getnode()
        if node:        
            name, ok = QtGui.QInputDialog.getText(self, 
                                                  'Rename Data', 'New Name:')        
            if ok:
                node.rename(name)

    def copy_data(self):
        self.copied_node = self.treeview.getnode()

    def paste_data(self):
        node = self.treeview.getnode()
        if isinstance(node, NXgroup) and self.copied_node:
            node.insert(self.copied_node)

    def delete_data(self):
        node = self.treeview.getnode()
        if node:
            dialog = DeleteDialog(node, self)
            dialog.show()      

    def set_signal(self):
        node = self.treeview.getnode()
        if node:
            if isinstance(node, NXfield) and node.nxgroup:
                dialog = SignalDialog(node, self)
                dialog.show()
            else:
                QtGui.QMessageBox.critical(self, "Invalid selection", 
                    "Only NeXus fields can be a plottable signal",
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def fit_data(self):
        node = self.treeview.getnode()
        if node is None:
            return
        try:
            if isinstance(node, NXentry) and node.nxtitle == 'Fit Results':
                entry = node
                entry.data.plot()
            else:
                raise NameError
        except NameError:
            try:
                node.plot()
            except KeyError:
                QtGui.QMessageBox.critical(self, "NeXus item not plottable", 
                    "Only plottable data can be fit",
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
            entry = NXentry(data=self.plotview.mainplot.plotdata)
        if len(entry.data.nxsignal.shape) == 1:
            dialog = FitDialog(entry, parent=self)
            dialog.show()
        else:
            QtGui.QMessageBox.critical(self, "Data not one-dimensional", 
                "Fitting only enabled for one-dimensional data",
                QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
       
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
        `fun` execute `magic` the console at the moment it is triggerd,
        not the console at the moment it has been created.

        This function is mostly used to create the "All Magics..." Menu at run time.
        """
        # need to level nested function  to be sure to past magic
        # on console **at run time**.
        def inner_dynamic_magic():
            self.console.execute(magic)
        inner_dynamic_magic.__name__ = "dynamics_magic_s"
        return inner_dynamic_magic

    def populate_all_magic_menu(self, listofmagic=None):
        """Clean "All Magics..." menu and repopulate it with `listofmagic`

        Parameters
        ----------
        listofmagic : string,
            repr() of a list of strings, send back by the kernel

        Notes
        -----
        `listofmagic`is a repr() of list because it is fed with the result of
        a 'user_expression'
        """
        alm_magic_menu = self.all_magic_menu
        alm_magic_menu.clear()

        # list of protected magic that don't like to be called without argument
        # append '?' to the end to print the docstring when called from the menu
        protected_magic = set(["more","less","load_ext","pycat","loadpy","save"])
        magics=re.findall('\w+', listofmagic)
        for magic in magics:
            if magic in protected_magic:
                pmagic = '%s%s%s'%('%',magic,'?')
            else:
                pmagic = '%s%s'%('%',magic)
            xaction = QtGui.QAction(pmagic,
                self,
                triggered=self._make_dynamic_magic(pmagic)
                )
            alm_magic_menu.addAction(xaction)

    def update_all_magic_menu(self):
        """ Update the list on magic in the "All Magics..." Menu

        Request the kernel with the list of availlable magic and populate the
        menu with the list received back

        """
        # first define a callback which will get the list of all magic and put it in the menu.
        self.console._silent_exec_callback('get_ipython().lsmagic()', self.populate_all_magic_menu)

    def init_magic_menu(self):
        self.magic_menu = self.menuBar().addMenu("&Magic")
        self.all_magic_menu = self.magic_menu.addMenu("&All Magics")

        # This action should usually not appear as it will be cleared when menu
        # is updated at first kernel response. Though, it is necessary when
        # connecting through X-forwarding, as in this case, the menu is not
        # auto updated, SO DO NOT DELETE.
        self.pop = QtGui.QAction("&Update All Magic Menu ",
            self, triggered=self.update_all_magic_menu)
        self.add_menu_action(self.all_magic_menu, self.pop)
        # we need to populate the 'Magic Menu' once the kernel has answer at
        # least once let's do it immedialy, but it's assured to works
        self.pop.trigger()

        self.reset_action = QtGui.QAction("&Reset",
            self,
            statusTip="Clear all varible from workspace",
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
            statusTip="List interactive variable",
            triggered=self.who_magic_console)
        self.add_menu_action(self.magic_menu, self.who_action)

        self.who_ls_action = QtGui.QAction("Wh&o ls",
            self,
            statusTip="Return a list of interactive variable",
            triggered=self.who_ls_magic_console)
        self.add_menu_action(self.magic_menu, self.who_ls_action)

        self.whos_action = QtGui.QAction("Who&s",
            self,
            statusTip="List interactive variable with detail",
            triggered=self.whos_magic_console)
        self.add_menu_action(self.magic_menu, self.whos_action)

    def init_window_menu(self):
        self.window_menu = self.menuBar().addMenu("&Window")
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

    def new_plot_window(self):
        from nexpy.gui.plotview import NXPlotView
        plotview = NXPlotView()
    
    def init_help_menu(self):
        # please keep the Help menu in Mac Os even if empty. It will
        # automatically contain a search field to search inside menus and
        # please keep it spelled in English, as long as Qt Doesn't support
        # a QAction.MenuRole like HelpMenuRole otherwise it will loose
        # this search field fonctionality

        self.help_menu = self.menuBar().addMenu("&Help")
        

        # Help Menu

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

        self.onlineHelpAct = QtGui.QAction("Open Online &Help",
            self,
            triggered=self._open_online_help)
        self.add_menu_action(self.help_menu, self.onlineHelpAct)

    # minimize/maximize/fullscreen actions:

    def toggle_menu_bar(self):
        menu_bar = self.menuBar()
        if menu_bar.isVisible():
            menu_bar.setVisible(False)
        else:
            menu_bar.setVisible(True)

    def toggleMinimized(self):
        if not self.isMinimized():
            self.showMinimized()
        else:
            self.showNormal()

    def _open_online_help(self):
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
        """ Forward the close event to every tabs contained by the windows
        """
        title = self.window().windowTitle()
        cancel = QtGui.QMessageBox.Cancel
        okay = QtGui.QMessageBox.Ok
        
        if self.confirm_exit:
            msg = "Close console and quit?"
            closeall = QtGui.QPushButton("&Quit", self)
            closeall.setShortcut('Q')
            box = QtGui.QMessageBox(QtGui.QMessageBox.Question,
                                    title, msg)
            box.addButton(cancel)
            box.addButton(closeall, QtGui.QMessageBox.YesRole)
            box.setDefaultButton(closeall)
            box.setEscapeButton(cancel)
            pixmap = QtGui.QPixmap(self._app.icon.pixmap(QtCore.QSize(64,64)))
            box.setIconPixmap(pixmap)
            reply = box.exec_()
        else:
            reply = okay
        
        if reply == cancel:
            event.ignore()
            return
        if reply == okay:
            event.accept()
