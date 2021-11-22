#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import os
import pkg_resources

from nexusformat.nexus import *

from .pyqt import QtCore, QtGui, QtWidgets
from .utils import (display_message, modification_time, natural_sort,
                    report_error)
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
        self._class = 'NXtree'
        self._name = 'tree'
        self._entries = {}
        
    def __setitem__(self, key, value):
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
        del self._entries[key]
        del self._shell[key]
        self.set_changed()

    def set_changed(self):
        self.sync_shell_names()
        if self._model:
            self.sync_children(self._item)
            for row in range(self._item.rowCount()):
                for item in self._item.child(row).walk():
                    self.sync_children(item)
            self._view.dataChanged(self._item.index(), self._item.index())
            self._view.update()
            self._view.status_message(self._view.node)

    def sync_children(self, item):
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
                print("NeXpy: '%s' added to tree in '%s'" % (node.nxname,
                                                             group.nxname))
            else:
                group = NXroot(NXentry(node))
                name = self.get_new_name()
                self[name] = group
                print("NeXpy: '%s' added to tree in '%s%s'" % 
                    (node.nxname, group.nxname, node.nxgroup.nxpath))
        else:
            raise NeXusError("Only an NXgroup can be added to the tree")

    def load(self, filename, mode='r'):
        name = self.get_name(filename)
        self[name] = nxload(filename, mode)
        return self[name]

    def reload(self, name):
        if name in self:
            if isinstance(self[name], NXroot):
                self[name].reload()
            return self[name]
        else:
            raise NeXusError('%s not in the tree')

    def get_name(self, filename):
        name = os.path.splitext(os.path.basename(filename))[0].replace(' ','_')
        name = "".join([c for c in name.replace('-','_') 
                        if c.isalpha() or c.isdigit() or c=='_'])
        if name in self._shell:
            ind = []
            for key in self._shell:
                try:
                    if key.startswith(name+'_'): 
                        ind.append(int(key[len(name)+1:]))
                except ValueError:
                    pass
            if ind == []: ind = [0]
            name = name+'_'+str(sorted(ind)[-1]+1)
        return name

    def get_new_name(self):
        ind = []
        for key in self._shell:
            try:
                if key.startswith('w'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if ind == []: ind = [0]
        return 'w'+str(sorted(ind)[-1]+1)

    def get_shell_names(self, node):
        return [obj[0] for obj in self._shell.items() if id(obj[1]) == id(node) 
                and not obj[0].startswith('_')]

    def sync_shell_names(self):
        for key, value in self.items():
            shell_names = self.get_shell_names(value)
            if key not in shell_names:
                self._shell[key] = value
                if shell_names:
                    del self._shell[shell_names[0]]

    def node_from_file(self, fname):
        fname = os.path.abspath(fname)
        names = [name for name in self if self[name].nxfilename]
        try:   
            return [name for name in names if fname==self[name].nxfilename][0]
        except IndexError:
            return None


class NXTreeItem(QtGui.QStandardItem):

    """
    A subclass of the QtGui.QStandardItem class to return the data from 
    an NXnode.
    """

    def __init__(self, node=None):
        self.name = node.nxname
        self.root = node.nxroot
        self.tree = self.root.nxgroup
        self.path = self.root.nxname + node.nxpath
        if isinstance(node, NXlink):
            self._linked = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/link-icon.png'))
        elif isinstance(node, NXroot):
            self._locked = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/lock-icon.png'))
            self._locked_modified = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/lock-red-icon.png'))
            self._unlocked = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/unlock-icon.png'))
            self._unlocked_modified = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                            'resources/unlock-red-icon.png'))
        super().__init__(node.nxname)

    @property
    def node(self):
        return self.tree[self.path]

    def __repr__(self):
        return "NXTreeItem('%s')" % self.path

    def text(self):
        return self.name

    def data(self, role=QtCore.Qt.DisplayRole):
        """
        Returns the data to be displayed in the tree.
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
        items = []
        if self.hasChildren():
            for row in range(self.rowCount()):
                items.append(self.child(row))
        return items

    def walk(self):
        yield self
        for child in self.children():
            for item in child.walk():
                yield item


class NXTreeView(QtWidgets.QTreeView):

    def __init__(self, tree, parent=None):
        super().__init__(parent=parent)

        self.tree = tree
        self.mainwindow = parent
        self._model = QtGui.QStandardItemModel()
        self.proxymodel = NXSortModel(self)
        self.proxymodel.setSourceModel(self._model)
        self.proxymodel.setDynamicSortFilter(True)
        self.proxymodel.setFilterCaseSensitivity(QtCore.Qt.CaseInsensitive)

        self.setModel(self.proxymodel)

        self._model.setColumnCount(1)
        self._model.setHorizontalHeaderItem(0,QtGui.QStandardItem('NeXus Data'))
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
        self.doubleClicked.connect(self.mainwindow.plot_data)
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
        super().update()

    def selection_changed(self):
        """Enable and disable menu actions based on the selection."""
        node = self.get_node()
        self.mainwindow.savefile_action.setEnabled(False)
        self.mainwindow.duplicate_action.setEnabled(False)
        self.mainwindow.remove_action.setEnabled(False)
        self.mainwindow.lockfile_action.setEnabled(False)
        self.mainwindow.unlockfile_action.setEnabled(False)
        self.mainwindow.backup_action.setEnabled(False)
        self.mainwindow.plot_data_action.setEnabled(False)
        self.mainwindow.plot_line_action.setEnabled(False)
        self.mainwindow.overplot_data_action.setEnabled(False)
        self.mainwindow.overplot_line_action.setEnabled(False)
        self.mainwindow.multiplot_data_action.setEnabled(False)
        self.mainwindow.multiplot_lines_action.setEnabled(False)
        self.mainwindow.plot_weighted_data_action.setEnabled(False)
        self.mainwindow.plot_image_action.setEnabled(False)
        self.mainwindow.export_action.setEnabled(False)
        self.mainwindow.rename_action.setEnabled(False)
        self.mainwindow.add_action.setEnabled(False)
        self.mainwindow.initialize_action.setEnabled(False)
        self.mainwindow.copydata_action.setEnabled(False)
        self.mainwindow.cutdata_action.setEnabled(False)
        self.mainwindow.pastedata_action.setEnabled(False)
        self.mainwindow.pastelink_action.setEnabled(False)
        self.mainwindow.delete_action.setEnabled(False)
        self.mainwindow.link_action.setEnabled(False)
        self.mainwindow.signal_action.setEnabled(False)
        self.mainwindow.default_action.setEnabled(False)
        self.mainwindow.fit_action.setEnabled(False)
        if node is None:
            self.mainwindow.reload_action.setEnabled(False)
            self.mainwindow.reload_all_action.setEnabled(False)
            self.mainwindow.remove_all_action.setEnabled(False)
            self.mainwindow.collapse_action.setEnabled(False)
            self.mainwindow.view_action.setEnabled(False)
            return
        else:
            self.mainwindow.reload_action.setEnabled(True)
            self.mainwindow.reload_all_action.setEnabled(True)
            self.mainwindow.remove_all_action.setEnabled(True)
            self.mainwindow.collapse_action.setEnabled(True)
            self.mainwindow.view_action.setEnabled(True)
            if node.nxgroup.is_modifiable():
                self.mainwindow.rename_action.setEnabled(True)
            if node.is_modifiable() and not isinstance(node, NXlink):
                self.mainwindow.add_action.setEnabled(True)
        if isinstance(node, NXroot):
            self.mainwindow.savefile_action.setEnabled(True)
            self.mainwindow.remove_action.setEnabled(True)
            if node.nxfilemode:
                self.mainwindow.duplicate_action.setEnabled(True)
                if node.nxfilemode == 'r':
                    self.mainwindow.unlockfile_action.setEnabled(True)
                else:
                    self.mainwindow.lockfile_action.setEnabled(True)
                self.mainwindow.backup_action.setEnabled(True)
                if node.nxbackup:
                    self.mainwindow.restore_action.setEnabled(True)
            if node.nxfilemode is None or node.nxfilemode == 'rw':
                if self.mainwindow.copied_node is not None:
                    self.mainwindow.pastedata_action.setEnabled(True)
                    self.mainwindow.pastelink_action.setEnabled(True)
            if node.nxfilemode is None:
                self.mainwindow.delete_action.setEnabled(True)
        else:
            self.mainwindow.copydata_action.setEnabled(True)
            if isinstance(node, NXlink):
                self.mainwindow.link_action.setEnabled(True)
            if isinstance(node, NXdata):
                self.mainwindow.export_action.setEnabled(True)
            if node.is_modifiable():
                if isinstance(node, NXgroup):
                    self.mainwindow.initialize_action.setEnabled(True)
                    if self.mainwindow.copied_node is not None:
                        self.mainwindow.pastedata_action.setEnabled(True)
                        self.mainwindow.pastelink_action.setEnabled(True)
                self.mainwindow.cutdata_action.setEnabled(True)
                if not node.is_linked():
                    self.mainwindow.delete_action.setEnabled(True)
                if isinstance(node, NXentry) or isinstance(node, NXdata):
                    self.mainwindow.default_action.setEnabled(True)
                if isinstance(node, NXdata):
                    self.mainwindow.signal_action.setEnabled(True)
            try:
                if ((isinstance(node, NXdata) and node.plot_rank == 1) or
                    (isinstance(node, NXgroup) and 
                    ('fit' in node or 'model' in node))):
                    self.mainwindow.fit_action.setEnabled(True)
            except Exception as error:
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
        except Exception as error:
            pass

    def expand_node(self, index):
        item = self._model.itemFromIndex(self.proxymodel.mapToSource(index))
        if item and item.node:
            group = item.node
            for name in [n for n in group if isinstance(group[n], NXgroup)]:
                _entries = group[name].entries

    def addMenu(self, action):
        if action.isEnabled():
            self.menu.addAction(action)

    def popMenu(self, node):
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
        self.addMenu(self.mainwindow.add_action)
        self.addMenu(self.mainwindow.initialize_action)
        self.addMenu(self.mainwindow.rename_action)
        self.addMenu(self.mainwindow.delete_action)
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
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.signal_action)
        self.addMenu(self.mainwindow.default_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.reload_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.remove_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.unlockfile_action)
        self.addMenu(self.mainwindow.lockfile_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.savefile_action)
        self.addMenu(self.mainwindow.duplicate_action)
        self.addMenu(self.mainwindow.export_action)
        self.addMenu(self.mainwindow.backup_action)
        self.menu.addSeparator()
        self.addMenu(self.mainwindow.collapse_action)
        return self.menu

    def status_message(self, message):
        if isinstance(message, NXfield) or isinstance(message, NXgroup):
            text = message._str_name()+' '+message._str_attrs()
        elif isinstance(message, NXlink):
            text = message._str_name()
        else:
            text = str(message)
        self.mainwindow.statusBar().showMessage(text.replace('\n','; '))

    def check_modified_files(self):
        try:
            for key in list(self.tree._entries):
                node = self.tree._entries[key]
                if node.nxfilemode and not node.file_exists():
                    _dir = node.nxfile._filedir
                    if not os.path.exists(_dir):
                        display_message("'%s' no longer exists" % _dir)
                        for _key in [k for k in self.tree
                                     if self.tree[k].nxfile._filedir == _dir]:
                            del self.tree[_key]
                        break
                    else:    
                        display_message("'%s' no longer exists" 
                                        % node.nxfilename)
                        del self.tree[key]
                elif node.is_modified():
                    node.lock()
                    node.nxfile.lock = True
                elif node.nxfilemode == 'rw':
                    nxfile = node.nxfile
                    if nxfile.is_locked() and nxfile.locked is False:
                        node.lock()
                        lock_time = modification_time(nxfile.lock_file) 
                        display_message(
                            "'%s' has been locked by an external process" 
                            % node.nxname, "Lock file created: "+lock_time)
                        nxfile.lock = True
            if self.timer.interval() > 1000:
                self.timer.setInterval(1000)
        except Exception as error:
            report_error('Checking Modified Files', error)
            self.timer.setInterval(60000)

    @property
    def node(self):
        return self.get_node()

    def get_node(self):
        item = self._model.itemFromIndex(
                   self.proxymodel.mapToSource(self.currentIndex()))
        if item:
            return item.node
        else:
            return None

    def get_index(self, node):
        items = self._model.findItems(node.nxname, QtCore.Qt.MatchRecursive)
        for item in items:
            if node is item.node:
                return self.proxymodel.mapFromSource(item.index())
        return None

    def select_node(self, node):
        idx = self.get_index(node)
        if idx:
            self.setCurrentIndex(idx)
        self.selectionModel().select(self.currentIndex(),
                                     QtCore.QItemSelectionModel.Select)

    def select_top(self):
        try:
            self.select_node(self.tree[self.tree.__dir__()[0]])
            self.setFocus()
        except Exception:
            pass
        
    def selectionChanged(self, new, old):
        super().selectionChanged(new, old)
        if new.indexes():
            node = self.get_node()
            self.status_message(node)
        else:
            self.status_message('')

    def collapse(self, index=None):
        if index:
            super().collapse(index)
        else:
            self.collapseAll()
            self.setCurrentIndex(self.model().index(0,0))

    def on_context_menu(self, point):
        node = self.get_node()
        if node is not None:
            self.popMenu(self.get_node()).exec_(self.mapToGlobal(point))
