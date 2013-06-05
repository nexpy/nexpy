from PySide import QtCore, QtGui
from treemodel import NXTreeModel
from nexpy.api.nexus import NXfield, NXgroup, NXroot, NeXusError

class NXtree(NXgroup):
    """
    NXtree group. This is a subclass of the NXgroup class.

    It is used as the invisible root item for NeXpy tree views.
    """
    nxclass = 'NXtree'
    nxname = 'tree'
    _model = None
    _view = None

    def __setitem__(self, key, value):
        from nexpy.gui.consoleapp import _shell
        super(NXtree, self).__setitem__(key, value)
        _shell[key] = self._entries[key]
    
    def set_changed(self):
        if self._model:
            self._view.clearSelection()
            self._model.treeChanged()
            for node in self.walk():
                if node.changed:
                    if node.nxgroup == self:
                        from nexpy.gui.consoleapp import _mainwindow
                        _mainwindow.user_ns[node.nxname] = node
                    index = self._model.getNodeIndex(node)
                    if index.isValid(): 
                        self._view.update(index)
                    if node.nxgroup:
                        index = self._model.getNodeIndex(node.nxgroup)
                        if index.isValid():
                            self._model.treeChanged(parent=index)
                    node.set_unchanged()

    def walk(self):
        yield self
        for node in self.entries.values():
            if node.changed:
                for child in node.walk():
                    yield child

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
    

class NXTreeView(QtGui.QTreeView):

    def __init__(self, tree, parent=None):
        super(NXTreeView, self).__init__(parent)

        self.tree = tree
        self.setModel(NXTreeModel(self.tree))
        self.tree._model = self.model()
        self.tree._view = self
        self.setSelectionMode(QtGui.QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QtGui.QAbstractItemView.SelectRows)

        # Popup Menu
        self.setContextMenuPolicy( QtCore.Qt.CustomContextMenu )
        self.customContextMenuRequested.connect(self.on_context_menu)

        self.plot_action=QtGui.QAction("Plot Data", self, triggered=self.plot)
        self.overplot_action=QtGui.QAction("Overplot Data", self, triggered=self.oplot)
        self.rename_action=QtGui.QAction("Rename", self, triggered=self.rename)
        self.savefile_action=QtGui.QAction("Save", self, triggered=self.save_file)
        self.savefileas_action=QtGui.QAction("Save as...", self, triggered=self.save_file_as)

        self.popMenu = QtGui.QMenu( self )
        self.popMenu.addAction( self.plot_action )
        self.popMenu.addAction( self.overplot_action )
        self.popMenu.addSeparator()
        self.popMenu.addAction( self.rename_action )
        self.popMenu.addSeparator()
        self.popMenu.addAction( self.savefile_action )
        self.popMenu.addAction( self.savefileas_action )
        
    def plot(self):
        node = self.model().getNode(self.currentIndex())
        self.statusmessage(node)
        try:
            node.plot()
        except:
            pass

    def rename(self):
        node = self.model().getNode(self.currentIndex())
        self.statusmessage(node)
        try:
            node.plot()
        except:
            pass

    def oplot(self):
        node = self.model().getNode(self.currentIndex())
        self.statusmessage(node)
        try:
            node.oplot()
        except:
            pass

    def save_file(self):
        node = self.model().getNode(self.currentIndex())
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
        node = self.model().getNode(self.currentIndex())
        fname, _ = QtGui.QFileDialog.getSaveFileName(self, "Choose a filename")
        if fname:
            try:
                node.save(fname)
            except NeXusError, error_message:
                QtGui.QMessageBox.critical(
                    self, "Error saving file", str(error_message),
                    QtGui.QMessageBox.Ok, QtGui.QMessageBox.NoButton)

    def selectionChanged(self, new, old):
        if new.indexes():
            node = self.model().getNode(new.indexes()[0])
            self.statusmessage(node)
        else:
            self.parent().parent().statusBar().showMessage('')

    def statusmessage(self, node):
        if isinstance(node, NXfield):
            message = node.tree
        else:
            message = node.nxclass+':'+node.nxname+' '+node._str_attrs()
        self.parent().parent().statusBar().showMessage(message.replace('\n','; '))
            

    def on_context_menu(self, point):
         self.popMenu.exec_( self.mapToGlobal(point) )



    
