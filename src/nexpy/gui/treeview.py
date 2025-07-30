# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

from pathlib import Path

from nexusformat.nexus import (NeXusError, NXdata, NXentry, NXfield, NXgroup,
                               NXlink, NXroot, nxload)

from .pyqt import QtCore, QtGui, QtWidgets
from .utils import (display_message, get_name, modification_time, report_error,
                    resource_icon)
from .widgets import NXSortModel


class NXtree(NXgroup):
    """
    NXtree group. This is a subclass of the NXgroup class.

    It is used as the invisible root item for NeXpy tree views.
    """
    _model = None
    _view = None
    _item = None
    _shell = {}
    _attrs = {}

    def __init__(self):
        """Initialize the NXtree group."""
        self._class = 'NXtree'
        self._name = 'tree'
        self._entries = {}

    def __setitem__(self, key, value):
        """
        Add a NeXus tree to the shell.

        Parameters
        ----------
        key : str
            The name of the tree in the shell.
        value : NXroot
            The root group of the tree.

        Raises
        ------
        NeXusError
            If the tree already exists in the shell.
        """
        if isinstance(value, NXroot):
            if key not in self._entries:
                value._group = self
                value._name = key
                self._entries[key] = value
                self._shell[key] = self._entries[key]
                value.set_changed()
            else:
                raise NeXusError("'"+key+"' already in the tree")
        else:
            raise NeXusError("Value must be an NXroot group")

    def __delitem__(self, key):
        """
        Delete a NeXus tree from the shell.

        Parameters
        ----------
        key : str
            The name of the tree in the shell.

        Raises
        ------
        NeXusError
            If the tree does not exist in the shell.
        """
        del self._entries[key]
        del self._shell[key]
        self.set_changed()

    def set_changed(self):
        """
        Mark the tree as changed.

        This method is called when the tree changes. It updates the tree
        view and the shell.
        """
        self.sync_shell_names()
        if self._model:
            self.sync_children(self._item)
            for row in range(self._item.rowCount()):
                for item in self._item.child(row).walk():
                    self.sync_children(item)
            index = self._item.index()
            if index.isValid():
                self._view.dataChanged(index, index)
            self._view.update()
            self._view.status_message(self._view.node)

    def sync_children(self, item):
        """
        Synchronize the children of a tree item with its NeXus group.

        If the NeXus group is a loaded NXgroup, this method adds
        children to the tree item if they are missing and removes them
        if they no longer exist in the NeXus group. This method should
        only be called by the set_changed method.

        Parameters
        ----------
        item : NXTreeItem
            The tree item to be synchronized.
        """
        if isinstance(item.node, NXgroup):
            children = []
            if item.hasChildren():
                for row in range(item.rowCount()):
                    children.append(item.child(row))
            names = [child.name for child in children]
            if item.node.entries_loaded:
                for name in item.node:
                    if name not in names:
                        item.appendRow(NXTreeItem(item.node[name]))
                for child in children:
                    if child.name not in item.node:
                        item.removeRow(child.row())
        item.node.set_unchanged()

    def add(self, node):
        """
        Add a NeXus group to the tree.

        If the NeXus group is a loaded NXgroup, it is added to the tree
        with its name. If the NeXus group is not loaded, it is added to
        a new NXroot group with a default name.

        Parameters
        ----------
        node : NXgroup
            The NeXus group to be added to the tree.

        Raises
        ------
        NeXusError
            If the node is not a NeXus group.
        """
        if isinstance(node, NXgroup):
            shell_names = self.get_shell_names(node)
            if shell_names:
                node.nxname = shell_names[0]
            if isinstance(node, NXroot):
                self[node.nxname] = node
                self[node.nxname]._file_modified = False
            elif isinstance(node, NXentry):
                group = NXroot(node)
                name = self.get_new_name()
                self[name] = group
                print(f"NeXpy: '{node.nxname}' added to tree in "
                      f"'{group.nxname}'")
            else:
                group = NXroot(NXentry(node))
                name = self.get_new_name()
                self[name] = group
                print(f"NeXpy: '{node.nxname}' added to tree in "
                      f"'{group.nxname}{node.nxgroup.nxpath}'")
        else:
            raise NeXusError("Only an NXgroup can be added to the tree")

    def load(self, filename, mode='r'):
        """
        Load a NeXus file into the tree.

        Parameters
        ----------
        filename : str
            The name of the NeXus file to be loaded.
        mode : str, optional
            The mode to open the file, by default 'r'.

        Returns
        -------
        NXroot
            The root group of the loaded tree.
        """
        name = self.get_name(filename)
        self[name] = nxload(filename, mode)
        return self[name]

    def reload(self, name):
        """
        Reload a NeXus tree.

        If the tree is a loaded NXroot, reload it from the file. If the
        tree is not a loaded NXroot, do nothing.

        Parameters
        ----------
        name : str
            The name of the tree to be reloaded.

        Returns
        -------
        NXroot
            The reloaded tree if it is a loaded NXroot, otherwise None.

        Raises
        ------
        NeXusError
            If the tree is not a loaded NXroot.
        """
        if name in self:
            if isinstance(self[name], NXroot):
                self[name].reload()
            return self[name]
        else:
            raise NeXusError(f"{name} not in the tree")

    def get_name(self, filename):
        """
        Return a name for a NeXus tree to be loaded.

        If a tree with the same filename exists, append a number to the
        name.

        Parameters
        ----------
        filename : str
            The name of the NeXus file to be loaded.

        Returns
        -------
        str
            A name for the loaded tree.
        """
        return get_name(filename, self._shell)

    def get_new_name(self):
        """
        Return a new name for a NeXus tree.

        The name is derived from the names of existing trees. If no
        trees exist, the name is 'w0'. If trees exist, the name is the
        largest number plus one, prefixed with 'w'.

        Returns
        -------
        str
            A new name for the tree.
        """
        ind = []
        for key in self._shell:
            try:
                if key.startswith('w'):
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if ind == []:
            ind = [0]
        return 'w'+str(sorted(ind)[-1]+1)

    def get_shell_names(self, node):
        """
        Return the names of the object in the shell namespace.

        Parameters
        ----------
        node : NXobject
            The NeXus object for which to retrieve the names.

        Returns
        -------
        list of str
            The names of the object in the shell namespace.
        """
        return [obj[0] for obj in self._shell.items() if id(obj[1]) == id(node)
                and not obj[0].startswith('_')]

    def sync_shell_names(self):
        """
        Ensure that the shell names are in sync with the tree.

        This method checks if the key in the tree is the same as the key
        in the shell namespace. If not, it assigns the tree key to the
        shell. If the previous key exists in the shell, it is deleted.

        """
        for key, value in self.items():
            shell_names = self.get_shell_names(value)
            if key not in shell_names:
                self._shell[key] = value
                if shell_names:
                    del self._shell[shell_names[0]]

    def node_from_file(self, fname):
        """
        Return the name of the tree item with filename fname.

        Parameters
        ----------
        fname : str
            The name of the file for which to return the tree item name.

        Returns
        -------
        str
            The name of the tree item if found, None otherwise.
        """
        fname = str(Path(fname).resolve())
        names = [name for name in self if self[name].nxfilename]
        try:
            return [name for name in names
                    if fname == self[name].nxfilename][0]
        except IndexError:
            return None


class NXTreeItem(QtGui.QStandardItem):

    """
    A subclass of the QtGui.QStandardItem class to return the data from
    an NXnode.
    """

    def __init__(self, node=None):
        """
        Constructor for the NXTreeItem class.

        Parameters
        ----------
        node : NXnode or None
            The NeXus node for which to create the tree item.

        Initializes the name, root, tree, and path attributes from the
        node. If the node is a link, sets the linked icon. If the node is
        a root, sets the locked, locked modified, unlocked, and unlocked
        modified icons. Calls the parent class constructor with the
        node name.
        """
        self.name = node.nxname
        self.root = node.nxroot
        self.tree = self.root.nxgroup
        self.path = self.root.nxname + node.nxpath
        if isinstance(node, NXlink):
            self._linked = resource_icon('link-icon.png')
        elif isinstance(node, NXroot):
            self._locked = resource_icon('lock-icon.png')
            self._locked_modified = resource_icon('lock-red-icon.png')
            self._unlocked = resource_icon('unlock-icon.png')
            self._unlocked_modified = resource_icon('unlock-red-icon.png')
        super().__init__(node.nxname)

    @property
    def node(self):
        """The selected node in the tree."""
        return self.tree[self.path]

    def __repr__(self):
        return f"NXTreeItem('{self.path}')"

    def text(self):
        """The name of the tree item."""
        return self.name

    def data(self, role=QtCore.Qt.DisplayRole):
        """
        Return the data for the tree item in the given role.

        Parameters
        ----------
        role : int, optional
            The role of the data, by default QtCore.Qt.DisplayRole

        Returns
        -------
        str or QIcon or None
            The name of the tree item for the DisplayRole and EditRole,
            a tooltip for the ToolTipRole, and a QIcon for the
            DecorationRole or None if the node is not a root or link.
        """
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return self.name
        elif role == QtCore.Qt.ToolTipRole:
            try:
                tree = self.node.short_tree
                if tree.count('\n') > 50:
                    return '\n'.join(tree.split('\n')[0:50])+'\n...'
                else:
                    return tree
            except Exception:
                return ''
        elif role == QtCore.Qt.DecorationRole:
            try:
                if isinstance(self.node, NXroot):
                    if self.node.nxfilemode == 'r':
                        if self.node._file_modified:
                            return self._locked_modified
                        else:
                            return self._locked
                    elif self.node.nxfilemode == 'rw':
                        if self.node._file_modified:
                            return self._unlocked_modified
                        else:
                            return self._unlocked
                elif isinstance(self.node, NXlink):
                    return self._linked
                else:
                    return None
            except Exception:
                return None

    def children(self):
        """Return a list of child items."""
        items = []
        if self.hasChildren():
            for row in range(self.rowCount()):
                items.append(self.child(row))
        return items

    def walk(self):
        """Yield the tree item and its children."""
        yield self
        for child in self.children():
            for item in child.walk():
                yield item


class NXTreeView(QtWidgets.QTreeView):

    def __init__(self, tree, mainwindow):
        """
        Initialize a NeXus tree view.

        Parameters
        ----------
        tree : NXtree
            The root of the tree.
        mainwindow : NXMainWindow
            The main window of the application.
        parent : QWidget, optional
            The parent of the view.
        """
        super().__init__()

        self.tree = tree
        self.mainwindow = mainwindow
        self._model = QtGui.QStandardItemModel()
        self.proxymodel = NXSortModel(self)
        self.proxymodel.setSourceModel(self._model)
        self.proxymodel.setDynamicSortFilter(True)
        self.proxymodel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.setModel(self.proxymodel)

        self._model.setColumnCount(1)
        self._model.setHorizontalHeaderItem(
            0, QtGui.QStandardItem('NeXus Data'))
        self.setSortingEnabled(True)
        self.sortByColumn(0, QtCore.Qt.AscendingOrder)

        self.setFocusPolicy(QtCore.Qt.ClickFocus)

        self.tree._item = self._model.invisibleRootItem()
        self.tree._item.node = self.tree
        self.tree._model = self._model
        self.tree._view = self
        self.tree._shell = self.mainwindow.user_ns

        self.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.setExpandsOnDoubleClick(False)
        self.selectionModel().selectionChanged.connect(self.selection_changed)
        self.expanded.connect(self.expand_node)

        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.check_modified_files)
        self.timer.start(1000)

        # Popup Menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)

    def __repr__(self):
        return 'NXTreeView("nxtree")'

    def update(self):
        """Update the tree view."""
        super().update()

    def selection_changed(self):
        """
        Enable or disable menu items based on the selected node.

        This slot is connected to the selectionChanged signal of the
        tree view. It enables or disables actions based on whether the
        currently selected node is a root, group, link, field, or data
        item and whether it is modifiable or not.
        """
        self.mainwindow.savefile_action.setEnabled(False)
        self.mainwindow.duplicate_action.setEnabled(False)
        self.mainwindow.reload_action.setEnabled(False)
        self.mainwindow.remove_action.setEnabled(False)
        self.mainwindow.export_action.setEnabled(False)
        self.mainwindow.lockfile_action.setEnabled(False)
        self.mainwindow.unlockfile_action.setEnabled(False)
        self.mainwindow.backup_action.setEnabled(False)
        self.mainwindow.restore_backup_action.setEnabled(False)
        self.mainwindow.plot_data_action.setEnabled(False)
        self.mainwindow.plot_line_action.setEnabled(False)
        self.mainwindow.overplot_data_action.setEnabled(False)
        self.mainwindow.overplot_line_action.setEnabled(False)
        self.mainwindow.multiplot_data_action.setEnabled(False)
        self.mainwindow.multiplot_lines_action.setEnabled(False)
        self.mainwindow.plot_weighted_data_action.setEnabled(False)
        self.mainwindow.plot_image_action.setEnabled(False)
        self.mainwindow.view_action.setEnabled(False)
        self.mainwindow.validate_action.setEnabled(False)
        self.mainwindow.group_action.setEnabled(False)
        self.mainwindow.field_action.setEnabled(False)
        self.mainwindow.attribute_action.setEnabled(False)
        self.mainwindow.edit_action.setEnabled(False)
        self.mainwindow.rename_action.setEnabled(False)
        self.mainwindow.delete_action.setEnabled(False)
        self.mainwindow.copydata_action.setEnabled(False)
        self.mainwindow.cutdata_action.setEnabled(False)
        self.mainwindow.pastedata_action.setEnabled(False)
        self.mainwindow.pastelink_action.setEnabled(False)
        self.mainwindow.link_action.setEnabled(False)
        self.mainwindow.signal_action.setEnabled(False)
        self.mainwindow.default_action.setEnabled(False)
        self.mainwindow.fit_action.setEnabled(False)
        self.mainwindow.fit_weighted_action.setEnabled(False)
        try:
            node = self.get_node()
        except Exception:
            node = None
        if node is None:
            self.mainwindow.reload_all_action.setEnabled(False)
            self.mainwindow.remove_all_action.setEnabled(False)
            self.mainwindow.collapse_action.setEnabled(False)
            return
        else:
            self.mainwindow.reload_all_action.setEnabled(True)
            self.mainwindow.remove_all_action.setEnabled(True)
            self.mainwindow.collapse_action.setEnabled(True)
            self.mainwindow.view_action.setEnabled(True)
            if node.nxgroup.is_modifiable():
                self.mainwindow.rename_action.setEnabled(True)
        if isinstance(node, NXroot):
            self.mainwindow.savefile_action.setEnabled(True)
            self.mainwindow.reload_action.setEnabled(True)
            self.mainwindow.remove_action.setEnabled(True)
            if node.nxfilemode:
                self.mainwindow.duplicate_action.setEnabled(True)
                if node.nxfilemode == 'r':
                    self.mainwindow.unlockfile_action.setEnabled(True)
                else:
                    self.mainwindow.lockfile_action.setEnabled(True)
                self.mainwindow.backup_action.setEnabled(True)
                if node.nxbackup:
                    self.mainwindow.restore_backup_action.setEnabled(True)
            if node.nxfilemode is None or node.nxfilemode == 'rw':
                if self.mainwindow.copied_node is not None:
                    self.mainwindow.pastedata_action.setEnabled(True)
                    self.mainwindow.pastelink_action.setEnabled(True)
            if node.nxfilemode is None:
                self.mainwindow.delete_action.setEnabled(True)
        else:
            self.mainwindow.copydata_action.setEnabled(True)
            if isinstance(node, NXgroup):
                self.mainwindow.validate_action.setEnabled(True)
                self.mainwindow.edit_action.setEnabled(True)
            if isinstance(node, NXlink):
                self.mainwindow.link_action.setEnabled(True)
            if isinstance(node, NXdata):
                self.mainwindow.export_action.setEnabled(True)
            if node.is_modifiable():
                if isinstance(node, NXgroup):
                    self.mainwindow.group_action.setEnabled(True)
                    self.mainwindow.field_action.setEnabled(True)
                    if self.mainwindow.copied_node is not None:
                        self.mainwindow.pastedata_action.setEnabled(True)
                        self.mainwindow.pastelink_action.setEnabled(True)
                if not (isinstance(node, NXlink) or node.is_linked()):
                    self.mainwindow.attribute_action.setEnabled(True)
                self.mainwindow.cutdata_action.setEnabled(True)
                if not node.is_linked():
                    self.mainwindow.delete_action.setEnabled(True)
                if isinstance(node, NXentry) or isinstance(node, NXdata):
                    self.mainwindow.default_action.setEnabled(True)
                if isinstance(node, NXdata):
                    self.mainwindow.signal_action.setEnabled(True)
            try:
                if isinstance(node, NXdata) and node.plot_rank == 1:
                    self.mainwindow.fit_action.setEnabled(True)
                    if node.nxweights is not None:
                        self.mainwindow.fit_weighted_action.setEnabled(
                            True)
                elif (isinstance(node, NXgroup) and
                      ('fit' in node or 'model' in node)):
                    self.mainwindow.fit_action.setEnabled(True)
            except Exception:
                pass
        try:
            if (isinstance(node, NXdata) or 'default' in node.attrs or
                    node.is_numeric()):
                self.mainwindow.plot_data_action.setEnabled(True)
                if ((isinstance(node, NXgroup) and
                    node.nxsignal is not None and
                    node.nxsignal.plot_rank == 1) or
                        (isinstance(node, NXfield) and node.plot_rank == 1)):
                    self.mainwindow.plot_line_action.setEnabled(True)
                    if self.mainwindow.plotview.ndim == 1:
                        self.mainwindow.overplot_data_action.setEnabled(True)
                        self.mainwindow.overplot_line_action.setEnabled(True)
                    if 'auxiliary_signals' in node.attrs:
                        self.mainwindow.multiplot_data_action.setEnabled(True)
                        self.mainwindow.multiplot_lines_action.setEnabled(True)
                if (isinstance(node, NXgroup) and
                        node.plottable_data is not None):
                    if node.nxweights is not None:
                        self.mainwindow.plot_weighted_data_action.setEnabled(
                            True)
                    if (node.plottable_data.is_image() or
                            (isinstance(node, NXfield) and node.is_image())):
                        self.mainwindow.plot_image_action.setEnabled(True)
        except Exception:
            pass

    def expand_node(self, index):
        """
        Expand the node at index in the treeview.

        Parameters
        ----------
        index : QModelIndex
            The index of the node to expand.
        """
        item = self._model.itemFromIndex(self.proxymodel.mapToSource(index))
        if item and item.node:
            group = item.node
            for name in [n for n in group if isinstance(group[n], NXgroup)]:
                _entries = group[name].entries

    def addMenu(self, action):
        """Add an action to the menu."""
        if action.isEnabled():
            self.menu.addAction(action)

    def popMenu(self, node):
        """
        Create a context menu for the treeview.

        Parameters
        ----------
        node : Node
            The node at the context menu position.

        Returns
        -------
        menu : QMenu
            The context menu.
        """
        self.menu = QtWidgets.QMenu(self)
        self.addMenu(self.mainwindow.plot_data_action)
        self.addMenu(self.mainwindow.plot_line_action)
        self.addMenu(self.mainwindow.overplot_data_action)
        self.addMenu(self.mainwindow.overplot_line_action)
        self.addMenu(self.mainwindow.multiplot_data_action)
        self.addMenu(self.mainwindow.multiplot_lines_action)
        self.addMenu(self.mainwindow.plot_weighted_data_action)
        self.addMenu(self.mainwindow.plot_image_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.view_action)
        self.addMenu(self.mainwindow.validate_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.group_action)
        self.addMenu(self.mainwindow.field_action)
        self.addMenu(self.mainwindow.attribute_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.edit_action)
        self.addMenu(self.mainwindow.rename_action)
        self.addMenu(self.mainwindow.delete_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.copydata_action)
        self.addMenu(self.mainwindow.cutdata_action)
        self.addMenu(self.mainwindow.pastedata_action)
        self.addMenu(self.mainwindow.pastelink_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.link_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.fit_action)
        self.addMenu(self.mainwindow.fit_weighted_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.signal_action)
        self.addMenu(self.mainwindow.default_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.reload_action)
        self.addMenu(self.mainwindow.reload_all_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.remove_action)
        self.addMenu(self.mainwindow.remove_all_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.unlockfile_action)
        self.addMenu(self.mainwindow.lockfile_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.savefile_action)
        self.addMenu(self.mainwindow.duplicate_action)
        self.addMenu(self.mainwindow.export_action)
        self.addMenu(self.mainwindow.backup_action)
        self.addMenu(self.mainwindow.restore_backup_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.collapse_action)
        return self.menu

    def status_message(self, message):
        """
        Display a status message in the status bar of the main window.

        Parameters
        ----------
        message : str or Node
            The message to display. If a Node, it will be converted to a
            string using its _str_name() or _str_attrs() method.
        """
        if isinstance(message, NXfield) or isinstance(message, NXgroup):
            text = message._str_name()+' '+message._str_attrs()
        elif isinstance(message, NXlink):
            text = message._str_name()
        else:
            text = str(message)
        self.mainwindow.statusBar().showMessage(text.replace('\n', '; '))

    def check_modified_files(self):
        """
        Check the files in the tree for modifications.

        This checks the files in the tree for three conditions:

        1. If a file no longer exists, it is removed from the tree.
        2. If a file has been modified by another process, it is locked.
        3. If a file has been locked by another process, the lock flag is set.

        If any of these conditions are met, the tree is refreshed. If any of
        the checks fail, the refresh interval is set to 1 minute.
        """
        try:
            for key in list(self.tree._entries):
                node = self.tree._entries[key]
                if node.nxfilemode and not node.file_exists():
                    _dir = node.nxfile._filedir
                    if not Path(_dir).exists():
                        display_message("Files removed",
                                        f"'{_dir}' no longer exists")
                        for _key in [k for k in self.tree
                                     if self.tree[k].nxfile._filedir == _dir]:
                            del self.tree[_key]
                        break
                    else:
                        display_message(
                            "File removed",
                            f"'{node.nxfilename}' no longer exists")
                        del self.tree[key]
                elif node.is_modified():
                    node.lock()
                    node.nxfile.lock = True
                elif node.nxfilemode == 'rw':
                    nxfile = node.nxfile
                    if nxfile.is_locked() and nxfile.locked is False:
                        node.lock()
                        lock_time = modification_time(nxfile.lock_file)
                        display_message(f"'{node.nxname}' has been locked "
                                        "by an external process",
                                        f"Lock file created: {lock_time}")
                        nxfile.lock = True
            if self.timer.interval() > 1000:
                self.timer.setInterval(1000)
        except Exception as error:
            report_error("Checking Modified Files", error)
            self.timer.setInterval(60000)

    @property
    def node(self):
        """The currently selected node."""
        return self.get_node()

    def get_node(self):
        """Return the currently selected node using the proxy model."""
        item = self._model.itemFromIndex(
            self.proxymodel.mapToSource(self.currentIndex()))
        if item:
            return item.node
        else:
            return None

    def get_index(self, node):
        """
        Return the index of the node in the tree using the proxy model.

        Parameters
        ----------
        node : NXobject
            The NeXus node to find in the tree.

        Returns
        -------
        QModelIndex
            The index of the node in the tree using the proxy model.
        """
        items = self._model.findItems(node.nxname, QtCore.Qt.MatchRecursive)
        for item in items:
            if node is item.node:
                return self.proxymodel.mapFromSource(item.index())
        return None

    def select_node(self, node):
        """
        Select the node in the tree.

        Parameters
        ----------
        node : NXobject
            The NeXus node to select in the tree.
        """
        idx = self.get_index(node)
        if idx:
            self.setCurrentIndex(idx)
        self.selectionModel().select(self.currentIndex(),
                                     QtCore.QItemSelectionModel.Select)

    def select_top(self):
        """
        Select the first node in the tree and set focus to the treeview.

        This is called when the application is started and when a new
        file is opened. It is a convenience method to quickly select the
        first node in the tree and set focus to the treeview.
        """
        try:
            self.select_node(self.tree[self.tree.__dir__()[0]])
            self.setFocus()
        except Exception:
            pass

    def selectionChanged(self, new, old):
        """
        Called whenever the selection in the treeview changes.

        This method is connected to the selectionChanged signal of the
        treeview. It is called whenever the selection in the treeview
        changes. If an item is selected, the status bar of the main
        window is updated with the path of the selected node. If no
        item is selected, the status bar is cleared.

        Parameters
        ----------
        new : QItemSelection
            The new selection in the treeview.
        old : QItemSelection
            The old selection in the treeview.
        """
        super().selectionChanged(new, old)
        if new.indexes():
            node = self.get_node()
            self.status_message(node)
        else:
            self.status_message('')

    def collapse(self, index=None):
        """
        Collapse a node in the tree.

        Parameters
        ----------
        index : QModelIndex or None, optional
            The index of the node to collapse. If None, the entire tree
            is collapsed and the first node is selected. The default is
            None.
        """
        if index:
            super().collapse(index)
        else:
            self.collapseAll()
            self.setCurrentIndex(self.model().index(0, 0))

    def on_context_menu(self, point):
        """
        Called when the context menu is requested in the treeview.

        This method is connected to the customContextMenuRequested signal
        of the treeview. It is called whenever the context menu is
        requested in the treeview. If a node is selected, the context
        menu for that node is displayed at the requested point.

        Parameters
        ----------
        point : QPoint
            The position of the context menu in the treeview.
        """
        node = self.get_node()
        if node is not None:
            self.popMenu(self.get_node()).exec(self.mapToGlobal(point))

    def mouseDoubleClickEvent(self, event):
        """
        Called when the user double-clicks in the treeview.

        If a node is double-clicked, it is plotted in a new plot window
        if the Shift key is held down. Otherwise, it is plotted in the
        current default plot window.

        Parameters
        ----------
        event : QMouseEvent
            The double-click event in the treeview.
        """
        index = self.indexAt(event.pos())
        if index.isValid():
            if event.modifiers() & QtCore.Qt.ShiftModifier:
                self.mainwindow.plot_data(new_plot=True)
            else:
                self.mainwindow.plot_data()
        super().mouseDoubleClickEvent(event)