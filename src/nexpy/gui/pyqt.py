from qtconsole.qt import QtCore, QtGui, QtSvg, QT_API

def getOpenFileName(*args, **kwargs):
    fname = QtGui.QFileDialog.getOpenFileName(*args, **kwargs)
    if isinstance(fname, tuple):
        fname = fname[0]
    return fname

def getSaveFileName(*args, **kwargs):
    fname = QtGui.QFileDialog.getSaveFileName(*args, **kwargs)
    if isinstance(fname, tuple):
        fname = fname[0]
    return fname

