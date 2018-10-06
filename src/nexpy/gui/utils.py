from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import importlib
import io
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
from .pyqt import QtWidgets, getOpenFileName
from matplotlib.colors import hex2color, rgb2hex
import matplotlib.image as img

try:
    from astropy.convolution import Kernel
except ImportError:
    Kernel = object
try:
    import fabio
except ImportError:
    fabio = None

from nexusformat.nexus import *

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


def confirm_action(query, information=None, answer=None, icon=None):
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
    if icon:
        message_box.setIconPixmap(icon)

    response = message_box.exec_()
    if (response == QtWidgets.QMessageBox.Yes or 
        response == QtWidgets.QMessageBox.Ok):
        return True
    else:
        return False

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


def iterable(obj):
    """Return true if the argument is iterable"""
    try:
        iter(obj)
    except TypeError:
        return False
    return True


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
    """Replaces ANSI color codes with HTML"""
    try:
        from ansi2html import Ansi2HTMLConverter
        conv = Ansi2HTMLConverter(dark_bg=False, inline=True)
        return conv.convert(text).replace('AAAAAA', 'FFFFFF')
    except ImportError:
        return ansi_re.sub('', text)


def get_name(filename, entries=[]):
    """Return a valid object name from a filename."""
    name = os.path.splitext(os.path.basename(filename))[0].replace(' ','_')
    name = "".join([c for c in name.replace('-','_') 
                    if c.isalpha() or c.isdigit() or c=='_'])
    if name in entries:
        ind = []
        for key in entries:
            try:
                if key.startswith(name+'_'): 
                    ind.append(int(key[len(name)+1:]))
            except ValueError:
                pass
        if ind == []: 
            ind = [0]
        name = name+'_'+str(sorted(ind)[-1]+1)
    return name


def get_colors(n, first='#1f77b4', last='#d62728'):
    """Return a list of colors interpolating between the first and last.

    The function accepts both strings representing hex colors and tuples 
    containing RGB values, which must be between 0 and 1.

    Parameters
    ----------
    n : int
        Number of colors to be generated.
    first : str or tuple of float
        First color in the list (defaults to Matplotlib default blue).
    last : str, tuple
        Last color in the list(defaults to Matplotlib default red).

    Returns
    -------
    colors : list
        A list of strings containing hex colors
    """
    if not isinstance(first, tuple):
        first = hex2color(first)
    if not isinstance(last, tuple):
        last = hex2color(last)
    return [rgb2hex((first[0]+(last[0]-first[0])*i/(n-1), 
                     first[1]+(last[1]-first[1])*i/(n-1),
                     first[2]+(last[2]-first[2])*i/(n-1))) for i in range(n)]

def load_image(filename):
    if os.path.splitext(filename.lower())[1] in ['.png', '.jpg', '.jpeg',
                                                 '.gif']:
        im = img.imread(filename)
        z = NXfield(im, name='z')
        y = NXfield(range(z.shape[0]), name='y')
        x = NXfield(range(z.shape[1]), name='x')
        if z.ndim > 2:
            rgba = NXfield(range(z.shape[2]), name='rgba')
            data = NXdata(z, (y,x,rgba))
        else:        
            data = NXdata(z, (y,x))
    else:
        try:
            im = fabio.open(filename)
        except Exception as error:
            if fabio:
                raise NeXusError("Unable to open image")
            else:
                raise NeXusError(
                    "Unable to open image. Please install the 'fabio' module")
        z = NXfield(im.data, name='z')
        y = NXfield(range(z.shape[0]), name='y')
        x = NXfield(range(z.shape[1]), name='x')
        data = NXdata(z,(y,x))
        if im.header:
            header = NXcollection()
            for k, v in im.header.items():
                if v or v == 0:
                    header[k] = v
            data.header = header
        if im.getclassname() == 'CbfImage':
            note = NXnote(type='text/plain', file_name=filename)
            note.data = im.header.pop('_array_data.header_contents', '')
            note.description = im.header.pop(
                '_array_data.header_convention', '')
            data.CBF_header = note
    data.title = filename
    return data


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


class NXLogger(io.StringIO):
    """File-like stream object that redirects writes to the default logger.
    
    An NXLogger instance is used to provide a temporary redirect of 
    sys.stdout and sys.stderr before the IPython kernel starts up.
    """
    def __init__(self):
        super(NXLogger, self).__init__()
        self.logger = logging.getLogger()
        self.log_level = self.logger.getEffectiveLevel()
        self.linebuf = ''

    def write(self, buffer):
        for line in buffer.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


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
