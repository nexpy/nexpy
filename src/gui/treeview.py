from PySide import QtCore, QtGui
from nexpy.api.nexus import NXfield, NXgroup, NXlink, NXroot, NeXusError
from datadialogs import RenameDialog

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
        from nexpy.gui.consoleapp import _shell
        super(NXtree, self).__setitem__(key, value)
        _shell[key] = self._entries[key]
    
    def set_changed(self):
        if self._model:
            for node in self.walk():
                if hasattr(node, "_item"):
                    if isinstance(node, NXlink) and node._item is node.nxlink._item:
                        node._item = NXTreeItem(node)
                else:
                    node._item = NXTreeItem(node)
                if not node._item.isChild(node.nxgroup._item):
                    node.nxgroup._item.appendRow(node._item)
                if node.infile:
                    node._item.setEditable(False)
                node._item.emitDataChanged()
                node.set_unchanged()

    def add(self, node):
        if isinstance(node, NXroot):
            group = node
            from nexpy.gui.consoleapp import _shell
            for key in _shell.keys():
                if id(_shell[key]) == id(group):
                    group.nxname = key
            self[group.nxname] = group
        elif isinstance(node, NXgroup):
            group = NXroot(node)
            ind = []
            for key in self._entries.keys():
                try:
                    if key.startswith('w'): 
                        ind.append(int(key[1:]))
                except ValueError:
                    pass
            if ind == []: ind = [0]
            self[self.get_new_name()] = group
        else:
            raise NeXusError("Only a valid NXgroup can be added to the tree")

    def get_new_name(self):
        ind = []
        for key in self._entries.keys():
            try:
                if key.startswith('w'): 
                    ind.append(int(key[1:]))
            except ValueError:
                pass
        if ind == []: ind = [0]
        return 'w'+str(sorted(ind)[-1]+1)

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
        super(NXTreeItem, self).__init__(self.node.nxname)
        if self.node.infile:
            self.setEditable(False) 

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

    def setData(self, value, role=QtCore.Qt.EditRole):
        if role == QtCore.Qt.EditRole:
            if self.node.infile:
                raise NeXusError("NeXus data already in a file cannot be renamed")
            self.node.rename(value)
            self.emitDataChanged()
            return True           
        return False

    def isChild(self, item):
        if item.hasChildren():
            for index in range(item.rowCount()):
                if item.child(index) is self:
                    return True
        return False

class NXSortModel(QtGui.QSortFilterProxyModel):

    def __init__(self, parent=None):
        super(NXSortModel, self).__init__(parent)

    def lessThan(self, left, right):
        left_text = self.sourceModel().itemFromIndex(left).text()
        right_text = self.sourceModel().itemFromIndex(right).text()
        return natural_sort(left_text) < natural_sort(right_text)

    
class NXTreeView(QtGui.QTreeView):

    def __init__(self, tree, parent=None):
        super(NXTreeView, self).__init__(parent)

        self.tree = tree
        self.mainwindow = None
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

        # Popup Menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_context_menu)

        self.plot_action=QtGui.QAction("Plot Data", self, triggered=self.plot_data)
        self.overplot_action=QtGui.QAction("Overplot Data", self, triggered=self.overplot_data)
        self.rename_action=QtGui.QAction("Rename Data", self, triggered=self.rename_data)
        self.fit_action=QtGui.QAction("Fit Data", self, triggered=self.fit_data)
        self.savefile_action=QtGui.QAction("Save", self, triggered=self.save_file)
        self.savefileas_action=QtGui.QAction("Save as...", self, triggered=self.save_file_as)

        self.popMenu = QtGui.QMenu(self)
        self.popMenu.addAction(self.plot_action)
        self.popMenu.addAction(self.overplot_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.rename_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.fit_action)
        self.popMenu.addSeparator()
        self.popMenu.addAction(self.savefile_action)
        self.popMenu.addAction(self.savefileas_action)

    def getnode(self):
        index = self.currentIndex()
        return self._model.itemFromIndex(self.proxymodel.mapToSource(index)).node
        
    def save_file(self):
        node = self.getnode()
        if node.nxfile:
            try:
                node.save()
            except NeXusError, error_message:
                QtGui.QMessageBox.critical(
                    self, "Error saving file", str(error_message),
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)
        else:
            fname, _ = QtGui.QFileDialog.getSaveFileName(self, "Choose a filename")
            if fname:
                try:
                    node.save(fname)
                except NeXusError, error_message:
                    QtGui.QMessageBox.critical(
                        self, "Error saving file", str(error_message),
                        QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def save_file_as(self):
        node = self.getnode()
        fname, _ = QtGui.QFileDialog.getSaveFileName(self, "Choose a filename")
        if fname:
            try:
                node.save(fname)
            except NeXusError, error_message:
                QtGui.QMessageBox.critical(
                    self, "Error saving file", str(error_message),
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def plot_data(self):
        self.parent().parent().plot_data()

    def overplot_data(self):
        self.parent().parent().overplot_data()

    def rename_data(self):
        self.parent().parent().rename_data()

    def fit_data(self):
        self.parent().parent().fit_data()

    def statusmessage(self, message):
        if isinstance(message, NXfield):
            text = message.tree
        elif isinstance(message, NXgroup):
            text = message.nxclass+':'+message.nxname+' '+message._str_attrs()
        else:
            text = str(message)
        self.parent().parent().statusBar().showMessage(text.replace('\n','; '))

    def selectionChanged(self, new, old):
        if new.indexes():
            node = self.getnode()
            self.statusmessage(node)
        else:
            self.statusmessage('')

    def on_context_menu(self, point):
         self.popMenu.exec_(self.mapToGlobal(point))

