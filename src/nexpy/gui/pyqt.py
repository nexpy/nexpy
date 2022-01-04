# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import os

from qtpy import QtCore, QtGui, QtWidgets

if QtCore.PYQT5:
    QtVersion = 'PyQt5'
    os.environ['QT_API'] = 'pyqt5'
elif QtCore.PYSIDE2:
    QtVersion = 'PySide2'
    os.environ['QT_API'] = 'pyside2'


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
