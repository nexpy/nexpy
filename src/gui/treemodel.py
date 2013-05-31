from IPython.external.qt import QtCore, QtGui
import sys

__all__ = ['NXnode', 'NXTreeModel']

class NXnode(object):

    """
    A superclass of the NXobject class defined in the NeXus tree API.
    
    It contains extra modules required for interfacing with the GUI model.
    """

    nxgroup = None
    
    def _childCount(self):
        """
        Returns the number of NeXus objects in the node.
        """
        try:
            return len(self.keys())
        except KeyError, AttributeError:
            return 0
    
    def _child(self, row):
        """
        Returns the NeXus object given by the position (row) in the tree.
        """
        if self is not None:
            try:
                names = sorted(self.keys(), key=natural_sort)
                return self[names[row]]
            except:
                return None
    
    def _row(self):
        """
        Returns the position (row) of the NeXus object in the tree.
        """
        if self.nxgroup is not None:
            names = sorted(self.nxgroup.keys())
            return names.index(self.nxname)
    
    def _display(self):
        """
        Returns a string representation of the NeXus object for display in the tree.
        """
        return self.nxname
        

class NXTreeModel(QtCore.QAbstractItemModel):
    
    def __init__(self, root, parent=None):
        super(NXTreeModel, self).__init__(parent)
        self._rootNode = root

    def rowCount(self, parent=QtCore.QModelIndex()):
        """
        The number of NeXus objects in the parent group.
        """
        if not parent.isValid():
            parentNode = self._rootNode
        else:
            parentNode = parent.internalPointer()
        try:
            return parentNode._childCount()
        except KeyError:
            return 0

    def columnCount(self, parent=QtCore.QModelIndex()):
        """
        Returns the number of columns in the data model = 1
        """
        return 1
    
    def data(self, index, role=QtCore.Qt.DisplayRole):
        """
        Returns the data to be displayed in the tree.
        """        
        if not index.isValid():
            return None

        node = index.internalPointer()

        if role == QtCore.Qt.DisplayRole or role == QtCore.Qt.EditRole:
            return node.nxname

        if role == QtCore.Qt.ToolTipRole:
            if node.tree.count('\n') > 50:
                return '\n'.join(node.tree.split('\n')[0:50])+'\n...'
            else:
                return node.tree

    def setData(self, index, value, role=QtCore.Qt.EditRole):

        if index.isValid():
            
            node = index.internalPointer()
            
            if role == QtCore.Qt.EditRole:
                node.nxname = value
#                self.dataChanged.emit(index, index)
                return True
            
        return False
    
    def headerData(self, section, orientation, role):
        """
        Returns the header string for the tree view.
        """
        if role == QtCore.Qt.DisplayRole:
            if section == 0:
                return "NeXus Trees"

    def flags(self, index):
        """
        Returns flags characterizing the tree view data.
        """
        return QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable #| QtCore.Qt.ItemIsEditable

    def parent(self, index):
        """
        Returns a QModelIndex of the tree item's parent.
        """
        if index.isValid():
            node = self.getNode(index)
            parentNode = node.nxgroup
        else:
            return QtCore.QModelIndex()
        
        if parentNode == self._rootNode:
            return QtCore.QModelIndex()

        return self.createIndex(parentNode._row(), 0, parentNode)
        
    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        """
        Returns a QModelIndex that corresponds to the given row, column and parent node
        """
        parentNode = self.getNode(parent)
        childItem = parentNode._child(row)

        if childItem:
            return self.createIndex(row, column, childItem)
        else:
            return QtCore.QModelIndex()

    def getNode(self, index=QtCore.QModelIndex()):
        """
        Returns the NeXus object corresponding to the QModelIndex.
        """
        if index.isValid():
            node = index.internalPointer()
            if node:
                return node
            
        return self._rootNode

    def getNodeIndex(self, node):
        """
        Returns the QModelIndex of the NeXus node
        """
        treeRows = [node._row()]
        parent = node.nxgroup
        while parent:
            treeRows.append(parent._row())
            parent = parent.nxgroup
        nodeIndex = QtCore.QModelIndex()
        treeRows.reverse()
        for row in treeRows:
            nodeIndex = self.index(row, parent=nodeIndex)
        return nodeIndex

    def treeChanged(self, parent=QtCore.QModelIndex()):
        self.rowsInserted.emit(parent, self.rowCount()-1, self.rowCount()-1)

    def insertRows(self, position, rows, parent=QtCore.QModelIndex()):
        """
        Inserts a NeXus object at a specified position.
        
        Not implemented.
        """
        parentNode = self.getNode(parent)
        
        self.beginInsertRows(parent, position, position + rows - 1)
        
        for row in range(rows):
            
            childCount = parentNode._childCount()
            childNode = NXnode("untitled" + str(childCount))
            success = parentNode.insertChild(position, childNode)
        
        self.endInsertRows()

        return success
    
    def removeRows(self, position, rows, parent=QtCore.QModelIndex()):
        """
        Removes a NeXus object at a specified position.
        
        Not implemented.
        """
        parentNode = self.getNode(parent)
        self.beginRemoveRows(parent, position, position + rows - 1)
        
        for row in range(rows):
            success = parentNode.removeChild(position)
            
        self.endRemoveRows()
        
        return success    

def natural_sort(key):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]    