import os
import matplotlib
import sip
for api in ['QString', 'QVariant', 'QDate', 'QDateTime', 'QTextStream', 'QTime', 
            'QUrl']:
    sip.setapi(api, 2)

from matplotlib.backends.qt_compat import QtCore, QtGui, QtWidgets
if QtCore.__name__.lower().startswith('pyqt5'):
    os.environ['QT_API'] = 'pyqt5'
    QtVersion = 'Qt5Agg'  
else:
    QtCore.QSortFilterProxyModel = QtGui.QSortFilterProxyModel
    QtCore.QItemSelectionModel = QtGui.QItemSelectionModel
    QtVersion = 'Qt4Agg'  
    if QtCore.__name__.lower().startswith('pyqt4'):
        os.environ['QT_API'] = 'pyqt'
    elif QtCore.__name__.lower().startswith('pyside'):
        os.environ['QT_API'] = 'pyside'
matplotlib.use(QtVersion, warn=False)

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
