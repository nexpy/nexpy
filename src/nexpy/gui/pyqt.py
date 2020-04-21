import os

from qtpy import QtCore, QtGui, QtWidgets

if QtCore.PYQT5:
    QtVersion = 'Qt5Agg'
    os.environ['QT_API'] = 'pyqt5'
elif QtCore.PYSIDE2:
    QtVersion = 'Qt5Agg'
    os.environ['QT_API'] = 'pyside2'
elif QtCore.PYQT4:
    QtVersion = 'Qt4Agg'
    os.environ['QT_API'] = 'pyqt'
elif QtCore.PYSIDE:
    QtVersion = 'Qt4Agg'
    os.environ['QT_API'] = 'pyside'


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
