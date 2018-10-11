#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import os
import pkg_resources

from .pyqt import QtCore, QtGui, QtWidgets
from .utils import natural_sort
from nexusformat.nexus import *


class NXtree(NXgroup):
    """
    NXtree group. This is a subclass of the NXgroup class.

    It is used as the invisible root item for NeXpy tree views.
    """
    _model = None
    _view = None
    _item = None
    _shell = None
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
                self.set_changed()
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
            names = [child.text() for child in children]
            for name in item.node:
                if name not in names:
                    item.appendRow(NXTreeItem(item.node[name]))
            for child in children:
                name = child.node.nxname
                if name not in item.node:
                    item.removeRow(child.row())
                elif child.node is not item.node[name]:
                    item.removeRow(child.row())
                    item.appendRow(NXTreeItem(item.node[name]))
        item.node.set_unchanged()
    
    def add(self, node):
        if isinstance(node, NXgroup):
            shell_names = self.get_shell_names(node)
            if shell_names:
                node.nxname = shell_names[0]
            if isinstance(node, NXroot):
                self[node.nxname] = node
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
            root = nxload(self[name].nxfilename, self[name].nxfilemode)
            if isinstance(root, NXroot):
                del self[name]
                self[name] = root
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
        self.node = node
        if isinstance(self.node, NXlink):
            self._linked = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/link-icon.png'))
        elif isinstance(self.node, NXroot):
            self._locked = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/lock-icon.png'))
            self._unlocked = QtGui.QIcon(
                pkg_resources.resource_filename('nexpy.gui',
                                                'resources/unlock-icon.png'))
        super(NXTreeItem, self).__init__(self.node.nxname)

    def text(self):
        return self.node.nxname

    def data(self, role=QtCore.Qt.DisplayRole):
        """
        Returns the data to be displayed in the tree.
        """        
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return self.node.nxname
        elif role == QtCore.Qt.ToolTipRole:
            tree = self.node.short_tree
            if tree.count('\n') > 50:
                return '\n'.join(tree.split('\n')[0:50])+'\n...'
            else:
                return tree
        elif role == QtCore.Qt.DecorationRole:
            if isinstance(self.node, NXroot) and self.node.nxfilemode == 'r':
                return self._locked
            elif isinstance(self.node, NXroot) and self.node.nxfilemode == 'rw':
                return self._unlocked
            elif isinstance(self.node, NXlink):
                return self._linked
            else:
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


class NXSortModel(QtCore.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(NXSortModel, self).__init__(parent)

    def lessThan(self, left, right):
        left_text = self.sourceModel().itemFromIndex(left).text()
        right_text = self.sourceModel().itemFromIndex(right).text()
        return natural_sort(left_text) < natural_sort(right_text)

    
class NXTreeView(QtWidgets.QTreeView):

    def __init__(self, tree, parent):
        super(NXTreeView, self).__init__(parent)

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

        # Popup Menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)


        self.plot_data_action=QtWidgets.QAction("Plot", self, 
                                    triggered=self.mainwindow.plot_data)
        self.plot_line_action=QtWidgets.QAction("Plot Line", self, 
                                    triggered=self.mainwindow.plot_line)
        self.overplot_data_action=QtWidgets.QAction("Overplot", self, 
                                    triggered=self.mainwindow.overplot_data)
        self.overplot_line_action=QtWidgets.QAction("Overplot Line", self, 
                                    triggered=self.mainwindow.overplot_line)
        self.multiplot_data_action=QtWidgets.QAction("Plot All Signals", self, 
                                    triggered=self.mainwindow.multiplot_data)
        self.multiplot_lines_action=QtWidgets.QAction(
                                    "Plot All Signals as Lines", self, 
                                    triggered=self.mainwindow.multiplot_lines)
        self.plot_image_action=QtWidgets.QAction("Plot RGB(A) Image", self, 
                                    triggered=self.mainwindow.plot_image)
        self.view_action=QtWidgets.QAction("View...", self, 
                                    triggered=self.mainwindow.view_data)
        self.add_action=QtWidgets.QAction("Add...", self, 
                                    triggered=self.mainwindow.add_data)
        self.initialize_action=QtWidgets.QAction("Initialize...", self, 
                                    triggered=self.mainwindow.initialize_data)
        self.rename_action=QtWidgets.QAction("Rename...", self, 
                                    triggered=self.mainwindow.rename_data)
        self.copy_action=QtWidgets.QAction("Copy", self, 
                                    triggered=self.mainwindow.copy_data)
        self.paste_action=QtWidgets.QAction("Paste", self, 
                                    triggered=self.mainwindow.paste_data)
        self.pastelink_action=QtWidgets.QAction("Paste As Link", self, 
                                    triggered=self.mainwindow.paste_link)
        self.delete_action=QtWidgets.QAction("Delete...", self, 
                                    triggered=self.mainwindow.delete_data)
        self.link_action=QtWidgets.QAction("Show Link", self, 
                                    triggered=self.mainwindow.show_link)
        self.signal_action=QtWidgets.QAction("Set Signal...", self, 
                                    triggered=self.mainwindow.set_signal)
        self.default_action=QtWidgets.QAction("Set Default", self, 
                                    triggered=self.mainwindow.set_default)
        self.fit_action=QtWidgets.QAction("Fit...", self, 
                                    triggered=self.mainwindow.fit_data)
        self.savefile_action=QtWidgets.QAction("Save as...", self, 
                                    triggered=self.mainwindow.save_file)
        self.duplicate_action=QtWidgets.QAction("Duplicate...", self, 
                                    triggered=self.mainwindow.duplicate)
        self.reload_action=QtWidgets.QAction("Reload...", self, 
                                    triggered=self.mainwindow.reload)
        self.remove_action=QtWidgets.QAction("Remove...", self, 
                                    triggered=self.mainwindow.remove)
        self.lockfile_action=QtWidgets.QAction("Lock", self, 
                                    triggered=self.mainwindow.lock_file)
        self.unlockfile_action=QtWidgets.QAction("Unlock...", self, 
                                     triggered=self.mainwindow.unlock_file)
        self.backup_action=QtWidgets.QAction("Backup", self, 
                                    triggered=self.mainwindow.backup_file)
        self.restore_action=QtWidgets.QAction("Restore...", self, 
                                    triggered=self.mainwindow.restore_file)
        self.collapse_action=QtWidgets.QAction("Collapse Tree", self,
                                    triggered=self.collapse)

    def popMenu(self, node):
        menu = QtWidgets.QMenu(self)
        from .plotview import plotview
        try:
            if node.is_plottable():
                menu.addAction(self.plot_data_action)
                if ((isinstance(node, NXgroup) and
                    node.nxsignal is not None and 
                    node.nxsignal.plot_rank == 1) or
                    (isinstance(node, NXfield) and node.plot_rank == 1)):
                    menu.addAction(self.plot_line_action)
                    if plotview.ndim == 1:
                        menu.addAction(self.overplot_data_action)
                        menu.addAction(self.overplot_line_action)
                    if 'auxiliary_signals' in node.attrs:
                        menu.addAction(self.multiplot_data_action)
                        menu.addAction(self.multiplot_lines_action)
                if ((isinstance(node, NXgroup) and 
                     node.plottable_data is not None and
                     node.plottable_data.nxsignal is not None and
                     node.plottable_data.nxsignal.plot_rank > 2) or
                    (isinstance(node, NXfield) and node.plot_rank > 2)):
                    menu.addAction(self.plot_image_action)
                menu.addSeparator()
        except Exception:
            pass
        menu.addAction(self.view_action)
        if not isinstance(node, NXlink):
            menu.addAction(self.add_action)
        if not isinstance(node, NXroot):
            if isinstance(node, NXgroup):
                menu.addAction(self.initialize_action)
        menu.addAction(self.rename_action)
        if isinstance(node, NXroot) and not node.nxfilemode:
            menu.addAction(self.delete_action)
        elif not isinstance(node, NXroot):
            menu.addAction(self.delete_action)
        menu.addSeparator()
        if not isinstance(node, NXroot):
            menu.addAction(self.copy_action)
        if (isinstance(node, NXgroup) and 
            self.mainwindow.copied_node is not None):
            menu.addAction(self.paste_action)
            menu.addAction(self.pastelink_action)
        if isinstance(node, NXlink):
            menu.addSeparator()
            menu.addAction(self.link_action)
        if not isinstance(node, NXroot):
            menu.addSeparator()
            if isinstance(node, NXgroup):
                menu.addAction(self.fit_action)
                menu.addSeparator()
                menu.addAction(self.signal_action)
        if isinstance(node, NXentry) or isinstance(node, NXdata):
            menu.addAction(self.default_action)
        menu.addSeparator()
        if isinstance(node, NXroot):
            menu.addAction(self.savefile_action)
            if node.nxfilemode:
                menu.addAction(self.duplicate_action)
            menu.addSeparator()
        if node.nxfilemode:
            menu.addAction(self.reload_action)
        if isinstance(node, NXroot) and node.nxfilemode:
            menu.addAction(self.duplicate_action)
            menu.addSeparator()
            menu.addAction(self.remove_action)
            menu.addSeparator()
            if node.nxfilemode == 'r':
                menu.addAction(self.unlockfile_action)
            else:
                menu.addAction(self.lockfile_action)
            menu.addSeparator()
            menu.addAction(self.backup_action)
            if node.nxbackup:
                menu.addAction(self.restore_action)
            menu.addSeparator
        menu.addSeparator()
        menu.addAction(self.collapse_action)
        return menu

    def status_message(self, message):
        if isinstance(message, NXfield) or isinstance(message, NXgroup):
            text = message._str_name()+' '+message._str_attrs()
        elif isinstance(message, NXlink):
            text = message._str_name()
        else:
            text = str(message)
        self.mainwindow.statusBar().showMessage(text.replace('\n','; '))

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
        
    def selectionChanged(self, new, old):
        super(NXTreeView, self).selectionChanged(new, old)
        if new.indexes():
            node = self.get_node()
            self.status_message(node)
        else:
            self.status_message('')

    def collapse(self, index=None):
        if index:
            super(NXTreeView, self).collapse(index)
        else:
            self.collapseAll()
            self.setCurrentIndex(self.model().index(0,0))

    def on_context_menu(self, point):
        self.popMenu(self.get_node()).exec_(self.mapToGlobal(point))

