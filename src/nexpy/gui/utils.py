from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from .pyqt import QtGui


def report_error(context, error):
    """Display a message box with an error message"""
    title = type(error).__name__ + ': ' + context
    message_box = QtGui.QMessageBox()
    message_box.setText(title)
    message_box.setInformativeText(str(error))
    message_box.setStandardButtons(QtGui.QMessageBox.Ok)
    message_box.setDefaultButton(QtGui.QMessageBox.Ok)
    message_box.setIcon(QtGui.QMessageBox.Warning)
    return message_box.exec_()


def confirm_action(query, information=None):
    """Display a message box requesting confirmation"""
    message_box = QtGui.QMessageBox()
    message_box.setText(query)
    if information:
        message_box.setInformativeText(information)
    message_box.setStandardButtons(QtGui.QMessageBox.Ok | QtGui.QMessageBox.Cancel)
    message_box.setDefaultButton(QtGui.QMessageBox.Ok)
    return message_box.exec_()


def wrap(text, length):
    """Wrap text lines based on a given length"""
    words = text.split()
    lines = []
    line = ''
    for w in words:
        if len(w) + len(line) > length:
            lines.append(line)
            line = ''
        line = line + w + ' '
        if w is words[-1]: lines.append(line)
    return '\n'.join(lines)


def natural_sort(key):
    """Sort numbers according to their value, not their first character"""
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]    


def timestamp():
    """Return a datestamp valid for use in directory names"""
    return datetime.now().strftime('%Y%m%d%H%M%S')
