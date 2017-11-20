from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import importlib
import logging
import os
import re
import sys

from collections import OrderedDict
from datetime import datetime
from IPython.core.ultratb import ColorTB
import traceback as tb
try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser
import numpy as np
from .pyqt import QtWidgets

try:
    from astropy.convolution import Kernel
except ImportError:
    Kernel = object


ansi_re = re.compile('\x1b' + r'\[([\dA-Fa-f;]*?)m')


def report_error(context, error):
    """Display a message box with an error message"""
    title = type(error).__name__ + ': ' + context
    message_box = QtWidgets.QMessageBox()
    message_box.setText(title)
    message_box.setInformativeText(str(error))
    message_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    message_box.setDefaultButton(QtWidgets.QMessageBox.Ok)
    message_box.setIcon(QtWidgets.QMessageBox.Warning)
    return message_box.exec_()


def confirm_action(query, information=None, answer=None):
    """Display a message box requesting confirmation"""
    message_box = QtWidgets.QMessageBox()
    message_box.setText(query)
    if information:
        message_box.setInformativeText(information)
    if answer == 'yes' or answer == 'no':
        message_box.setStandardButtons(QtWidgets.QMessageBox.Yes | 
                                       QtWidgets.QMessageBox.No)
        if answer == 'yes':                           
            message_box.setDefaultButton(QtWidgets.QMessageBox.Yes)
        else:
            message_box.setDefaultButton(QtWidgets.QMessageBox.No)
    else:
        message_box.setStandardButtons(QtWidgets.QMessageBox.Ok | 
                                       QtWidgets.QMessageBox.Cancel)
    return message_box.exec_()


def display_message(message, information=None):
    """Display a message box with an error message"""
    message_box = QtWidgets.QMessageBox()
    message_box.setText(message)
    if information:
        message_box.setInformativeText(information)
    return message_box.exec_()


def report_exception(*args):
    """Display and log an uncaught exception with its traceback"""
    if len(args) == 3:
        error_type, error, traceback = args[:3]
    elif len(args) == 1:
        if six.PY3:
            exc = args[0]
            error_type, error, traceback = exc.__class__, exc, exc.__traceback__
        else:
            error_type, error, traceback = sys.exc_info()
    message = ''.join(tb.format_exception_only(error_type, error))
    information = ColorTB(mode="Context").text(error_type, error, traceback)
    logging.error('Exception in GUI event loop\n'+information+'\n')
    message_box = QtWidgets.QMessageBox()
    message_box.setText(message)
    message_box.setInformativeText(convertHTML(information))
    message_box.setIcon(QtWidgets.QMessageBox.Warning)
    layout = message_box.layout()
    layout.setColumnMinimumWidth(layout.columnCount()-1, 600)
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
    return datetime.strptime(time_string, 
                             '%Y%m%d%H%M%S').isoformat().replace('T', ' ')


def restore_timestamp(time_string):
    """Return a timestamp from a formatted string."""
    return datetime.strptime(time_string, 
                             "%Y-%m-%d %H:%M:%S").strftime('%Y%m%d%H%M%S')


def timestamp_age(time_string):
    """Return the number of days since the timestamp"""
    return (datetime.now() - read_timestamp(time_string)).days


def is_timestamp(time_string):
    """Return true if the string is formatted as a timestamp"""
    try:
        return isinstance(read_timestamp(time_string), datetime)
    except ValueError:
        return False


def convertHTML(text):
    try:
        from ansi2html import Ansi2HTMLConverter
        conv = Ansi2HTMLConverter(dark_bg=False, inline=True)
        return conv.convert(text).replace('AAAAAA', 'FFFFFF')
    except ImportError:
        return ansi_re.sub('', text)


class NXimporter(object):
    def __init__(self, paths):
        self.paths = paths

    def __enter__(self):
        for path in reversed(self.paths):
            sys.path.insert(0, path)

    def __exit__(self, exc_type, exc_value, traceback):
        for path in self.paths:
            sys.path.remove(path)


def import_plugin(name, paths):
    with NXimporter(paths):
        plugin_module = importlib.import_module(name)
        if hasattr(plugin_module, '__file__'): #Not a namespace module
            return plugin_module
        else:
            raise ImportError('Plugin cannot be a namespace module')


class NXConfigParser(ConfigParser, object):
    """A ConfigParser subclass that preserves the case of option names"""

    def __init__(self, settings_file):
        super(NXConfigParser, self).__init__(allow_no_value=True)
        self.file = settings_file
        self._optcre = re.compile( #makes '=' the only valid key/value delimiter
            r"(?P<option>.*?)\s*(?:(?P<vi>=)\s*(?P<value>.*))?$", re.VERBOSE)
        super(NXConfigParser, self).read(self.file)
        sections = self.sections()
        if 'recent' not in sections:
            self.add_section('recent')
        if 'backups' not in sections:
            self.add_section('backups')
        if 'plugins' not in sections:
            self.add_section('plugins')
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
        paths = [f.strip() for f 
                 in self.get('recent', 'recentFiles').split(',')]
        for path in paths:
            self.set("recent", path)
        self.remove_option("recent", "recentFiles")
        self.save()


class Gaussian3DKernel(Kernel):

    _separable = True
    _is_bool = False

    def __init__(self, stddev, **kwargs):
        x = np.linspace(-15., 15., 17)
        y = np.linspace(-15., 15., 17)
        z = np.linspace(-15., 15., 17)
        X,Y,Z = np.meshgrid(x,y,z)
        array = np.exp(-(X**2+Y**2+Z**2)/(2*stddev**2))
        self._default_size = _round_up_to_odd_integer(8 * stddev)
        super(Gaussian3DKernel, self).__init__(array)
        self.normalize()
        self._truncation = np.abs(1. - self._array.sum())
