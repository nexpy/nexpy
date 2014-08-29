from PySide import QtGui
import get_ei, convert_qe

def plugin_menu(parent):
    menu = QtGui.QMenu('Chopper')
    menu.addAction(QtGui.QAction('Get Incident Energy', parent, 
                   triggered=get_ei.show_dialog))
    menu.addAction(QtGui.QAction('Convert to Q-E', parent, 
                   triggered=convert_qe.show_dialog))
    return menu
