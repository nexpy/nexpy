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

from .pyqt import QtCore, QtGui
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
                raise NeXusError("Name already in the tree")
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
                print("NeXpy: '%s' added to tree in '%s%s'" % (node.nxname,
                                              group.nxname, node.nxgroup.nxpath))
        else:
            raise NeXusError("Only an NXgroup can be added to the tree")

    def load(self, filename, mode='r'):
        name = self.get_name(filename)
        self[name] = nxload(filename, mode)

    def reload(self, name):
        if name in self:
            root = nxload(self[name].nxfilename, self[name].nxfilemode)
            if isinstance(root, NXroot):
                del self[name]
                self[name] = root
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
            if self.node.tree.count('\n') > 50:
                return '\n'.join(self.node.short_tree.split('\n')[0:50])+'\n...'
            else:
                return self.node.tree
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


class NXSortModel(QtGui.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(NXSortModel, self).__init__(parent)

    def lessThan(self, left, right):
        left_text = self.sourceModel().itemFromIndex(left).text()
        right_text = self.sourceModel().itemFromIndex(right).text()
        return natural_sort(left_text) < natural_sort(right_text)

    
class NXTreeView(QtGui.QTreeView):

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

        self.tree._item = self._model.invisibleRootItem()
        self.tree._item.node = self.tree
        self.tree._model = self._model
        self.tree._view = self
        self.tree._shell = self.mainwindow.user_ns

        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setExpandsOnDoubleClick(False)
        self.doubleClicked.connect(self.plot_data)

        # Popup Menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)


        self.plot_data_action=QtGui.QAction("Plot", self, 
                                       triggered=self.plot_data)
        self.plot_line_action=QtGui.QAction("Plot Line", self, 
                                       triggered=self.plot_line)
        self.overplot_data_action=QtGui.QAction("Overplot", self, 
                                           triggered=self.overplot_data)
        self.overplot_line_action=QtGui.QAction("Overplot Line", self, 
                                           triggered=self.overplot_line)
        self.plot_image_action=QtGui.QAction("Plot RGB(A) Image", self, 
                                           triggered=self.plot_image)
        self.view_action=QtGui.QAction("View...", self, triggered=self.view_data)
        self.add_action=QtGui.QAction("Add...", self, triggered=self.add_data)
        self.initialize_action=QtGui.QAction("Initialize...", self, triggered=self.initialize_data)
        self.rename_action=QtGui.QAction("Rename...", self, triggered=self.rename_data)
        self.copy_action=QtGui.QAction("Copy", self, triggered=self.copy_data)
        self.paste_action=QtGui.QAction("Paste", self, triggered=self.paste_data)
        self.pastelink_action=QtGui.QAction("Paste As Link", self, triggered=self.paste_link)
        self.delete_action=QtGui.QAction("Delete...", self, triggered=self.delete_data)
        self.link_action=QtGui.QAction("Show Link", self, triggered=self.show_link)
        self.signal_action=QtGui.QAction("Set Signal...", self, triggered=self.set_signal)
        self.default_action=QtGui.QAction("Set Default", self, triggered=self.set_default)
        self.fit_action=QtGui.QAction("Fit...", self, triggered=self.fit_data)
        self.savefile_action=QtGui.QAction("Save as...", self, triggered=self.save_file)
        self.duplicate_action=QtGui.QAction("Duplicate...", self, triggered=self.duplicate)
        self.reload_action=QtGui.QAction("Reload...", self, triggered=self.reload)
        self.remove_action=QtGui.QAction("Remove...", self, triggered=self.remove)
        self.lockfile_action=QtGui.QAction("Lock", self, triggered=self.lock_file)
        self.unlockfile_action=QtGui.QAction("Unlock...", self, triggered=self.unlock_file)
        self.backup_action=QtGui.QAction("Backup", self, triggered=self.backup_file)
        self.restore_action=QtGui.QAction("Restore...", self, triggered=self.restore_file)

    def popMenu(self, node):
        menu = QtGui.QMenu(self)
        try:
            if node.is_plottable():
                menu.addAction(self.plot_data_action)
                if ((isinstance(node, NXgroup) and
                    node.nxsignal is not None and 
                    node.nxsignal.plot_rank == 1) or
                    (isinstance(node, NXfield) and node.plot_rank == 1)):
                    menu.addAction(self.plot_line_action)
                    if self.mainwindow.plotview.ndim == 1:
                        menu.addAction(self.overplot_data_action)
                        menu.addAction(self.overplot_line_action)
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
        if isinstance(node, NXgroup) and self.mainwindow.copied_node is not None:
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
        return menu

    def save_file(self):
        self.mainwindow.save_file()

    def duplicate(self):
        self.mainwindow.duplicate()

    def reload(self):
        self.mainwindow.reload()

    def remove(self):
        self.mainwindow.remove()

    def lock_file(self):
        self.mainwindow.lock_file()

    def unlock_file(self):
        self.mainwindow.unlock_file()

    def backup_file(self):
        self.mainwindow.backup_file()

    def restore_file(self):
        self.mainwindow.restore_file()

    def plot_data(self):
        self.mainwindow.plot_data()

    def plot_line(self):
        self.mainwindow.plot_line()

    def overplot_data(self):
        self.mainwindow.overplot_data()

    def overplot_line(self):
        self.mainwindow.overplot_line()

    def plot_image(self):
        self.mainwindow.plot_image()

    def view_data(self):
        self.mainwindow.view_data()

    def add_data(self):
        self.mainwindow.add_data()

    def initialize_data(self):
        self.mainwindow.initialize_data()

    def rename_data(self):
        self.mainwindow.rename_data()

    def copy_data(self):
        self.mainwindow.copy_data()

    def paste_data(self):
        self.mainwindow.paste_data()

    def paste_link(self):
        self.mainwindow.paste_link()

    def delete_data(self):
        self.mainwindow.delete_data()

    def show_link(self):
        self.mainwindow.show_link()

    def set_signal(self):
        self.mainwindow.set_signal()

    def set_default(self):
        self.mainwindow.set_default()

    def fit_data(self):
        self.mainwindow.fit_data()

    def status_message(self, message):
        if isinstance(message, NXfield):
            text = message.tree
        elif isinstance(message, NXgroup):
            text = message._str_name()+' '+message._str_attrs()
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
                                     QtGui.QItemSelectionModel.Select)
        
    def selectionChanged(self, new, old):
        if new.indexes():
            node = self.get_node()
            self.status_message(node)
        else:
            self.status_message('')

    def on_context_menu(self, point):
        self.popMenu(self.get_node()).exec_(self.mapToGlobal(point))

