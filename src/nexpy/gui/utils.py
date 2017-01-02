from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import os
from collections import OrderedDict
from datetime import datetime
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser
import numpy as np
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


def confirm_action(query, information=None, answer=None):
    """Display a message box requesting confirmation"""
    message_box = QtGui.QMessageBox()
    message_box.setText(query)
    if information:
        message_box.setInformativeText(information)
    if answer == 'yes' or answer == 'no':
        message_box.setStandardButtons(QtGui.QMessageBox.Yes | 
                                       QtGui.QMessageBox.No)
        if answer == 'yes':                           
            message_box.setDefaultButton(QtGui.QMessageBox.Yes)
        else:
            message_box.setDefaultButton(QtGui.QMessageBox.No)
    else:
        message_box.setStandardButtons(QtGui.QMessageBox.Ok | 
                                       QtGui.QMessageBox.Cancel)
    return message_box.exec_()


def display_message(message, information=None):
    """Display a message box with an error message"""
    message_box = QtGui.QMessageBox()
    message_box.setText(message)
    if information:
        message_box.setInformativeText(information)
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


def find_nearest(array, value):
    idx = (np.abs(array-value)).argmin()
    return array[idx]

def find_nearest_index(array, value):
    return (np.abs(array-value)).argmin()

def human_size(bytes):
    """Convert a file size to human-readable form"""
    size = np.float(bytes)
    for suffix in ['kB', 'MB', 'GB', 'TB', 'PB', 'EB']:
        size /= 1000
        if size < 1000:
            return '{0:.0f} {1}'.format(size, suffix)


def timestamp():
    """Return a datestamp valid for use in directory names"""
    return datetime.now().strftime('%Y%m%d%H%M%S')


def read_timestamp(time_string):
    """Return a datetime object from the timestamp string"""
    return datetime.strptime(time_string, '%Y%m%d%H%M%S')


def format_timestamp(time_string):
    """Return the timestamp as a formatted string."""
    return datetime.strptime(time_string, '%Y%m%d%H%M%S').isoformat().replace('T', ' ')


def timestamp_age(time_string):
    """Return the number of days since the timestamp"""
    return (datetime.now() - read_timestamp(time_string)).days


def is_timestamp(time_string):
    """Return true if the string is formatted as a timestamp"""
    try:
        return isinstance(read_timestamp(time_string), datetime)
    except ValueError:
        return False


class NXConfigParser(ConfigParser, object):
    """A ConfigParser subclass that preserves the case of option names"""

    def __init__(self, settings_file):
        super(NXConfigParser, self).__init__(allow_no_value=True)
        self.file = settings_file
        super(NXConfigParser, self).read(self.file)
        sections = self.sections()
        if 'recent' not in sections:
            self.add_section('recent')
        if 'backups' not in sections:
            self.add_section('backups')
        if 'recentFiles' in self.options('recent'):
            self.fix_recent()

    def optionxform(self, optionstr):
        return optionstr

    def save(self):
        with open(self.file, 'w') as f:
            self.write(f)

    def purge(self, section):
        for option in self.options(section):
            self.remove_option(section, option)

    def fix_recent(self):
        """Perform backward compatibility fix"""
        paths = [f.strip() for f in self.get('recent', 'recentFiles').split(',')]
        for path in paths:
            self.set("recent", path)
        self.remove_option("recent", "recentFiles")
        self.save()
