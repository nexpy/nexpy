import os
import matplotlib
try:
    import sip
    for api in ['QString', 'QVariant', 'QDate', 'QDateTime',
                'QTextStream', 'QTime', 'QUrl']:
        sip.setapi(api, 2)
except ImportError:
    pass

from qtpy import QtCore, QtGui, QtWidgets

if QtCore.PYQT5:
    os.environ['QT_API'] = 'pyqt5'
    QtVersion = 'Qt5Agg'
elif QtCore.PYQT4:
    QtVersion = 'Qt4Agg'
    os.environ['QT_API'] = 'pyqt'
elif QtCore.PYSIDE:
    QtVersion = 'Qt4Agg'
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
