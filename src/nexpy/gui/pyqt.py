import os
import matplotlib
import sip
for api in ['QString', 'QVariant', 'QDate', 'QDateTime', 'QTextStream', 'QTime', 
            'QUrl']:
    sip.setapi(api, 2)

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets
if QtCore.__name__.lower().startswith('pyqt5'):
    os.environ['QT_API'] = 'pyqt5'
    QtGui.QSortFilterProxyModel = QtCore.QSortFilterProxyModel
    QtGui.QItemSelectionModel = QtCore.QItemSelectionModel
    matplotlib.use('Qt5Agg', warn=False)    
elif QtCore.__name__.lower().startswith('pyqt4'):
    os.environ['QT_API'] = 'pyqt4'
    matplotlib.use('Qt4Agg', warn=False)    
elif QtCore.__name__.lower().startswith('pyside'):
    os.environ['QT_API'] = 'pyside'
    matplotlib.use('Qt4Agg', warn=False)    

def getOpenFileName(*args, **kwargs):
    fname = QtWidgets.QFileDialog.getOpenFileName(*args, **kwargs)
    if isinstance(fname, tuple):
        fname = fname[0]
    return fname

def getSaveFileName(*args, **kwargs):
    fname = QtWidgets.QFileDialog.getSaveFileName(*args, **kwargs)
    if isinstance(fname, tuple):
        fname = fname[0]
    return fname
