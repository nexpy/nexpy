import os
import matplotlib
import sip
for api in ['QString', 'QVariant', 'QDate', 'QDateTime', 'QTextStream', 'QTime', 
            'QUrl']:
    sip.setapi(api, 2)

matplotlib.use('Qt4Agg', warn=False)
from matplotlib.backends.qt_compat import QtCore, QtGui
if QtCore.__name__.lower().startswith('pyqt4'):
    os.environ['QT_API'] = 'pyqt'
elif QtCore.__name__.lower().startswith('pyside'):
    os.environ['QT_API'] = 'pyside'

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
