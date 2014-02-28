#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
import os
import pkg_resources

from PySide import QtCore, QtGui
from nexpy.api.nexus import NXfield, NXgroup, NXlink, NXroot, NXentry, NeXusError


def natural_sort(key):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]

    
class NXtree(NXgroup):
    """
    NXtree group. This is a subclass of the NXgroup class.

    It is used as the invisible root item for NeXpy tree views.
    """
    nxclass = 'NXtree'
    nxname = 'tree'
    _model = None
    _view = None
    _item = None

    def __setitem__(self, key, value):
        if isinstance(value, NXroot):
            if key not in self._entries.keys():
                value._group = self
                value._name = key
                self._entries[key] = value
                from nexpy.gui.consoleapp import _shell
                _shell[key] = self._entries[key]
                self.set_changed()
            else:
                raise NeXusError("Name already in the tree")
        else:
            raise NeXusError("Value must be an NXroot group")
    
    def __delitem__(self, key):
        del self._entries[key]
        from nexpy.gui.consoleapp import _shell
        del _shell[key]
        self.set_changed()

    def set_changed(self):
        self.sync_shell_names()
        if self._model:
            if self._item.hasChildren():
                for row in reversed(range(self._item.rowCount())):
                    if self._item.child(row).node.nxname not in self.entries:
                        self._item.removeRow(row)
            for node in self.walk():
                if hasattr(node, "_item"):
                    if isinstance(node, NXlink) and node._item is node.nxlink._item:
                        node._item = NXTreeItem(node)
                else:
                    node._item = NXTreeItem(node)
                if not node._item.isChild(node.nxgroup._item):
                    node.nxgroup._item.appendRow(node._item)
                node._item.removeDuplicateSibling()
                if isinstance(node, NXgroup):
                    node._item.removeMissingChildren()
                node._item.emitDataChanged()
                node.set_unchanged()

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
                print "NeXpy: '%s' added to tree in '%s'" % (node.nxname, 
                                                             group.nxname)
            else:
                group = NXroot(NXentry(node))
                name = self.get_new_name()
                self[name] = group
                print "NeXpy: '%s' added to tree in '%s%s'" % (node.nxname, 
                                              group.nxname, node.nxgroup.nxpath)
        else:
            raise NeXusError("Only an NXgroup can be added to the tree")

    def get_name(self, filename):
        from nexpy.gui.consoleapp import _shell
        name = os.path.splitext(os.path.basename(filename))[0].replace(' ','_')
        name = "".join([c for c in name.replace('-','_') 
                        if c.isalpha() or c.isdigit() or c=='_'])
        if name in _shell.keys():
            ind = []
            for key in _shell.keys():
                try:
                    if key.startswith(name+'_'): 
                        ind.append(int(key[len(name)+1:]))
                except ValueError:
                    pass
            if ind == []: ind = [0]
            name = name+'_'+str(sorted(ind)[-1]+1)
        return name

    def get_new_name(self):
        from nexpy.gui.consoleapp import _shell
        ind = []
        for key in _shell.keys():
            try:
                if key.startswith('w'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if ind == []: ind = [0]
        return 'w'+str(sorted(ind)[-1]+1)

    def get_shell_names(self, node):
        from nexpy.gui.consoleapp import _shell
        return [obj[0] for obj in _shell.items() if id(obj[1]) == id(node) 
                and not obj[0].startswith('_')]

    def sync_shell_names(self):
        from nexpy.gui.consoleapp import _shell
        for key, value in self.entries.items():
            shell_names = self.get_shell_names(value)
            if key not in shell_names:
                _shell[key] = value
                if shell_names:
                    del _shell[shell_names[0]]
    
    def walk(self):
        for node in self.entries.values():
            for child in node.walk():
                yield child


class NXTreeItem(QtGui.QStandardItem):

    """
    A subclass of the QtGui.QStandardItem class to return the data from 
    an NXnode.
    """

    def __init__(self, node):
        self.node = node
        self._linked = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui', 
                                            'resources/link-icon.png'))
        self._locked = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui', 
                                            'resources/lock-icon.png'))
        self._unlocked = QtGui.QIcon(
            pkg_resources.resource_filename('nexpy.gui', 
                                            'resources/unlock-icon.png'))
        super(NXTreeItem, self).__init__(self.node.nxname)

    def text(self):
        return self.node.nxname

    def setText(self, text):
        self.node.rename(text)
        self.setData(self.node)
    
    def data(self, role=QtCore.Qt.DisplayRole):
        """
        Returns the data to be displayed in the tree.
        """        
        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return self.node.nxname
        if role == QtCore.Qt.ToolTipRole:
            if self.node.tree.count('\n') > 50:
                return '\n'.join(self.node.tree.split('\n')[0:50])+'\n...'
            else:
                return self.node.tree
        if role == QtCore.Qt.DecorationRole:
            if isinstance(self.node, NXroot) and self.node.nxfilemode == 'r':
                return self._locked
            elif isinstance(self.node, NXroot) and self.node.nxfilemode == 'rw':
                return self._unlocked
            elif isinstance(self.node, NXlink):
                return self._linked
            else:
                return None

    def setData(self, value, role=QtCore.Qt.EditRole):
        if role == QtCore.Qt.EditRole:
            self.node.rename(value)
            self.emitDataChanged()
            return True           
        return False

    def isChild(self, item):
        if item.hasChildren():
            for row in range(item.rowCount()):
                if item.child(row) is self:
                    return True
        return False

    def removeMissingChildren(self):
        if self.hasChildren():
            for row in reversed(range(self.rowCount())):
                if self.child(row).node.nxname not in self.node.entries:
                    self.removeRow(row)

    def removeDuplicateSibling(self):
        try:
            for row in range(self.parent().rowCount()):
                if self.parent().child(row).text()==self.text():
                    if self is not self.parent().child(row):
                        self.parent().removeRow(row)
                        return
        except AttributeError:
            pass


class NXSortModel(QtGui.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(NXSortModel, self).__init__(parent)

    def lessThan(self, left, right):
        left_text = self.sourceModel().itemFromIndex(left).text()
        right_text = self.sourceModel().itemFromIndex(right).text()
        return natural_sort(left_text) < natural_sort(right_text)

    
class NXTreeView(QtGui.QTreeView):

    def __init__(self, tree, parent=None, mainwindow=None):
        super(NXTreeView, self).__init__(parent)

        self.tree = tree
        self.mainwindow = mainwindow
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
        self.tree._model = self._model
        self.tree._view = self

        self.setEditTriggers(QtGui.QAbstractItemView.NoEditTriggers)
        self.setExpandsOnDoubleClick(False)
        self.doubleClicked.connect(self.plot_data)

        # Popup Menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)

        self.plot_data_action=QtGui.QAction("Plot Data", self, 
                                       triggered=self.plot_data)
        self.plot_line_action=QtGui.QAction("Plot Line", self, 
                                       triggered=self.plot_line)
        self.overplot_data_action=QtGui.QAction("Overplot Data", self, 
                                           triggered=self.overplot_data)
        self.overplot_line_action=QtGui.QAction("Overplot Line", self, 
                                           triggered=self.overplot_line)
        self.add_action=QtGui.QAction("Add Data", self, triggered=self.add_data)
        self.initialize_action=QtGui.QAction("Initialize Data", self, triggered=self.initialize_data)
        self.rename_action=QtGui.QAction("Rename Data", self, triggered=self.rename_data)
        self.copy_action=QtGui.QAction("Copy Data", self, triggered=self.copy_data)
        self.paste_action=QtGui.QAction("Paste Data", self, triggered=self.paste_data)
        self.pastelink_action=QtGui.QAction("Paste As Link", self, triggered=self.paste_link)
        self.delete_action=QtGui.QAction("Delete Data", self, triggered=self.delete_data)
        self.link_action=QtGui.QAction("Show Link", self, triggered=self.show_link)
        self.signal_action=QtGui.QAction("Set Signal", self, triggered=self.set_signal)
        self.fit_action=QtGui.QAction("Fit Data", self, triggered=self.fit_data)
        self.savefile_action=QtGui.QAction("Save as...", self, triggered=self.save_file)
        self.duplicate_action=QtGui.QAction("Duplicate...", self, triggered=self.duplicate)
        self.remove_action=QtGui.QAction("Remove", self, triggered=self.remove)
        self.lockfile_action=QtGui.QAction("Lock File", self, triggered=self.lock_file)
        self.unlockfile_action=QtGui.QAction("Unlock File", self, triggered=self.unlock_file)

        self.popMenu = QtGui.QMenu(self)
        self.popMenu.addAction(self.plot_data_action)
        self.popMenu.addAction(self.plot_line_action)
        self.popMenu.addAction(self.overplot_data_action)
        self.popMenu.addAction(self.overplot_line_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.add_action)
        self.popMenu.addAction(self.initialize_action)
        self.popMenu.addAction(self.rename_action)
        self.popMenu.addAction(self.copy_action)
        self.popMenu.addAction(self.paste_action)
        self.popMenu.addAction(self.pastelink_action)
        self.popMenu.addAction(self.delete_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.link_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.signal_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.fit_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.savefile_action)
        self.popMenu.addAction(self.duplicate_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.remove_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.lockfile_action)
        self.popMenu.addAction(self.unlockfile_action)

    def save_file(self):
        self.mainwindow.save_file()

    def duplicate(self):
        self.mainwindow.duplicate()

    def remove(self):
        self.mainwindow.remove()

    def lock_file(self):
        self.mainwindow.lock_file()

    def unlock_file(self):
        self.mainwindow.unlock_file()

    def plot_data(self):
        self.mainwindow.plot_data()

    def plot_line(self):
        self.mainwindow.plot_data('-')

    def overplot_data(self):
        self.mainwindow.overplot_data()

    def overplot_line(self):
        self.mainwindow.overplot_data('-')

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

    def fit_data(self):
        self.mainwindow.fit_data()

    def statusmessage(self, message):
        if isinstance(message, NXfield):
            text = message.tree
        elif isinstance(message, NXgroup):
            text = message.nxclass+':'+message.nxname+' '+message._str_attrs()
        else:
            text = str(message)
        self.mainwindow.statusBar().showMessage(text.replace('\n','; '))

    def getnode(self):
        item = self._model.itemFromIndex(
                   self.proxymodel.mapToSource(self.currentIndex()))
        if item:
            return item.node
        else:
            return None

    def getindex(self, node):
        return self.proxymodel.mapFromSource(node._item.index())

    def selectnode(self, node):
        self.setCurrentIndex(self.getindex(node))
        
    def selectionChanged(self, new, old):
        if new.indexes():
            node = self.getnode()
            self.statusmessage(node)
        else:
            self.statusmessage('')

    def on_context_menu(self, point):
        self.popMenu.exec_(self.mapToGlobal(point))

