# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import copy
import datetime
import gc
import importlib
import io
import logging
import os
import re
import sys
import time
import traceback as tb
from configparser import ConfigParser
from datetime import datetime
from threading import Thread

import numpy as np
from IPython.core.ultratb import ColorTB
from matplotlib import __version__ as mplversion
from matplotlib import rcParams
from matplotlib.colors import colorConverter, hex2color, rgb2hex
from pkg_resources import parse_version

from .pyqt import QtCore, QtWidgets

try:
    from astropy.convolution import Kernel
except ImportError:
    Kernel = object
try:
    import fabio
except ImportError:
    fabio = None

from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXfield,
                               NXLock, NXLockException, NXnote,
                               nxgetconfig, nxload, nxsetconfig)

ansi_re = re.compile(r'\x1b' + r'\[([\dA-Fa-f;]*?)m')


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


def display_message(message, information=None, width=None):
    """Display a message box with an error message"""
    message_box = QtWidgets.QMessageBox()
    message_box.setText(message)
    if information:
        message_box.setInformativeText(information)
    if width:
        message_box.setStyleSheet(f"QLabel{{min-width:{width} px; }}")
    else:
        message_box.setStyleSheet("QLabel{min-width:250 px; }")
    return message_box.exec_()


def report_exception(*args):
    """Display and log an uncaught exception with its traceback"""
    if len(args) == 3:
        error_type, error, traceback = args[:3]
    elif len(args) == 1:
        exc = args[0]
        error_type, error, traceback = exc.__class__, exc, exc.__traceback__
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


def run_pythonw(script_path):
    """Execute the NeXpy startup script using 'pythonw' on MacOS.

    This relaunches the script in a subprocess using a framework build of
    Python in order to fix the frozen menubar issue in MacOS 10.15 Catalina.

    Based on https://github.com/napari/napari/pull/1554.
    """
    if 'PYTHONEXECUTABLE' in os.environ:
        return
    import platform
    import warnings
    from distutils.version import StrictVersion
    if (StrictVersion(platform.release()) > StrictVersion('19.0.0') and
            'CONDA_PREFIX' in os.environ):
        pythonw_path = os.path.join(sys.exec_prefix, 'bin', 'pythonw')
        if os.path.exists(pythonw_path):
            cwd = os.getcwd()
            cmd = [pythonw_path, script_path]
            env = os.environ.copy()
            if len(sys.argv) > 1:
                cmd.extend(sys.argv[1:])
            import subprocess
            result = subprocess.run(cmd, env=env, cwd=cwd)
            sys.exit(result.returncode)
        else:
            msg = ("'pythonw' executable not found.\n"
                   "To unfreeze the menubar on macOS, "
                   "click away from nexpy to another app, "
                   "then reactivate nexpy. To avoid this problem, "
                   "please install python.app in conda using:\n\n"
                   "conda install -c conda-forge python.app\n")
            warnings.warn(msg)


def is_file_locked(filename, wait=5, expiry=None):
    _lock = NXLock(filename)
    try:
        if expiry is None:
            expiry = nxgetconfig('lockexpiry')
        if _lock.is_stale(expiry=expiry):
            return False
        else:
            _lock.wait(wait)
            return False
    except NXLockException:
        lock_time = modification_time(_lock.lock_file)
        if confirm_action("File locked. Do you want to clear the lock?",
                          f"{filename}\nCreated: {lock_time}",
                          answer="no"):
            _lock.clear()
            return False
        else:
            return True
    else:
        return False


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
        if w is words[-1]:
            lines.append(line)
    return '\n'.join(lines)


def natural_sort(key):
    """Sort numbers according to their value, not their first character"""
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]


def clamp(value, min_value, max_value):
    """Return value constrained to be within defined limits

    Parameters
    ----------
    value : int or float
        Original value
    min_value : int or float
        Allowed minimum value
    max_value : int or float
        Allowed maximum value

    Returns
    -------
    int or float
        Value constrained to be within defined limits
    """
    return max(min_value, min(value, max_value))


def centers(axis, dimlen):
    """Return the centers of the axis bins.

    This works regardless if the axis contains bin boundaries or
    centers.

    Parameters
    ----------
    dimlen : int
        Size of the signal dimension. If this one more than the axis
        size, it is assumed the axis contains bin boundaries.
    """
    ax = axis.astype(np.float64)
    if ax.shape[0] == dimlen+1:
        return (ax[:-1] + ax[1:])/2
    else:
        assert ax.shape[0] == dimlen
        return ax


def boundaries(axis, dimlen):
    """Return the boundaries of the axis bins.

    This works regardless if the axis contains bin boundaries or
    centers.

    Parameters
    ----------
    dimlen : int
        Size of the signal dimension. If this one more than the axis
        size, it is assumed the axis contains bin boundaries.
    """
    ax = axis.astype(np.float64)
    if ax.shape[0] == 1:
        return ax
    elif ax.shape[0] == dimlen:
        start = ax[0] - (ax[1] - ax[0])/2
        end = ax[-1] + (ax[-1] - ax[-2])/2
        return np.concatenate((np.atleast_1d(start),
                               (ax[:-1] + ax[1:])/2,
                               np.atleast_1d(end)))
    else:
        assert ax.shape[0] == dimlen + 1
        return ax


def keep_data(data):
    """Store the data in the scratch workspace.

    Parameters
    ----------
    data : NXdata
        NXdata group containing the data to be stored

    """
    from .consoleapp import _nexpy_dir, _tree
    if 'w0' not in _tree:
        _tree['w0'] = nxload(os.path.join(_nexpy_dir, 'w0.nxs'), 'rw')
    ind = []
    for key in _tree['w0']:
        try:
            if key.startswith('s'):
                ind.append(int(key[1:]))
        except ValueError:
            pass
    if ind == []:
        ind = [0]
    data.nxname = 's'+str(sorted(ind)[-1]+1)
    _tree['w0'][data.nxname] = data


def fix_projection(shape, axes, limits):
    """Fix the axes and limits for data with dimension sizes of 1.

    If the shape contains dimensions of size 1, they need to be added
    back to the list of axis dimensions and slice limits before calling
    the original NXdata 'project' function.

    Parameters
    ----------
    shape : tuple or list
        Shape of the signal.
    axes : list
        Original list of axis dimensions.
    limits : list
        Original list of slice limits.

    Returns
    -------
    fixed_axes : list
        List of axis dimensions restoring dimensions of size 1.
    fixed_limits : list
        List of slice limits with (0,0) added for dimensions of size 1.
    """
    fixed_limits = []
    fixed_axes = axes
    for s in shape:
        if s == 1:
            fixed_limits.append((0, 0))
        else:
            fixed_limits.append(limits.pop(0))
    for (i, s) in enumerate(shape):
        if s == 1:
            fixed_axes = [a+1 if a >= i else a for a in fixed_axes]
    return fixed_axes, fixed_limits


def find_nearest(array, value):
    idx = (np.abs(array-value)).argmin()
    return array[idx]


def find_nearest_index(array, value):
    return (np.abs(array-value)).argmin()


def format_float(value, width=6):
    """Modified form of the 'g' format specifier."""
    text = "{:.{width}g}".format(value, width=width)
    return re.sub(r"e(-?)0*(\d+)", r"e\1\2", text.replace("e+", "e"))


def human_size(bytes, width=0, decimals=2):
    """Convert a file size to human-readable form"""
    size = float(bytes)
    for unit in [' B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']:
        if size < 1000.0 or unit == 'EB':
            break
        size /= 1000.0
    return "{0:{1}.{2}f} {3}".format(size, width, decimals, unit)


def timestamp():
    """Return a time stamp valid for use in backup directory names"""
    return datetime.now().strftime('%Y%m%d%H%M%S')


def read_timestamp(timestamp):
    """Return a datetime object from the directory time stamp."""
    return datetime.strptime(timestamp, '%Y%m%d%H%M%S')


def format_timestamp(timestamp):
    """Return the directory time stamp as a formatted string."""
    return str(read_timestamp(timestamp))


def restore_timestamp(formatted_timestamp):
    """Return a timestamp from a formatted string."""
    return datetime.strptime(formatted_timestamp,
                             "%Y-%m-%d %H:%M:%S").strftime('%Y%m%d%H%M%S')


def timestamp_age(timestamp):
    """Return the number of days since the timestamp"""
    return (datetime.now() - read_timestamp(timestamp)).days


def is_timestamp(timestamp):
    """Return true if the string is formatted as a directory timestamp."""
    try:
        return isinstance(read_timestamp(timestamp), datetime)
    except ValueError:
        return False


def get_mtime(file_path):
    """Return the file modification time for the specified file path."""
    try:
        return file_path.stat().st_mtime
    except FileNotFoundError:  # due to a race condition
        return 0.0


def format_mtime(mtime):
    """Return the modification time as a formatted string."""
    return str(datetime.fromtimestamp(mtime))[:19]


def modification_time(filename):
    try:
        _mtime = os.path.getmtime(filename)
        return str(datetime.fromtimestamp(_mtime))
    except FileNotFoundError:
        return ''


def convertHTML(text):
    """Replaces ANSI color codes with HTML"""
    try:
        from ansi2html import Ansi2HTMLConverter
        if in_dark_mode():
            conv = Ansi2HTMLConverter(dark_bg=True, inline=True)
        else:
            conv = Ansi2HTMLConverter(dark_bg=False, inline=True)
        return conv.convert(text).replace('AAAAAA', 'FFFFFF')
    except ImportError:
        return ansi_re.sub('', text)


def get_name(filename, entries=[]):
    """Return a valid object name from a filename."""
    name = os.path.splitext(os.path.basename(filename))[0].replace(' ', '_')
    name = "".join([c for c in name.replace('-', '_')
                    if c.isalpha() or c.isdigit() or c == '_'])
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


def get_color(color):
    return rgb2hex(colorConverter.to_rgb(color))


def get_colors(n, first=None, last=None):
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
    if first is None:
        first = rcParams['axes.prop_cycle'].by_key()['color'][0]
    if last is None:
        last = rcParams['axes.prop_cycle'].by_key()['color'][3]
    if not isinstance(first, tuple):
        first = hex2color(first)
    if not isinstance(last, tuple):
        last = hex2color(last)
    return [rgb2hex((first[0]+(last[0]-first[0])*i/(n-1),
                     first[1]+(last[1]-first[1])*i/(n-1),
                     first[2]+(last[2]-first[2])*i/(n-1))) for i in range(n)]


def parula_map():
    """Generate a color map similar to Matlab's Parula for use in NeXpy.

    The color map data are from the 'fake_parula' function provided by
    Ander Biguri, "Perceptually uniform colormaps"
    MATLAB Central File Exchange (2020).
    """
    from matplotlib.colors import LinearSegmentedColormap
    cm_data = [[0.2081, 0.1663, 0.5292],
               [0.2116238095, 0.1897809524, 0.5776761905],
               [0.212252381, 0.2137714286, 0.6269714286],
               [0.2081, 0.2386, 0.6770857143],
               [0.1959047619, 0.2644571429, 0.7279],
               [0.1707285714, 0.2919380952, 0.779247619],
               [0.1252714286, 0.3242428571, 0.8302714286],
               [0.0591333333, 0.3598333333, 0.8683333333],
               [0.0116952381, 0.3875095238, 0.8819571429],
               [0.0059571429, 0.4086142857, 0.8828428571],
               [0.0165142857, 0.4266, 0.8786333333],
               [0.032852381, 0.4430428571, 0.8719571429],
               [0.0498142857, 0.4585714286, 0.8640571429],
               [0.0629333333, 0.4736904762, 0.8554380952],
               [0.0722666667, 0.4886666667,  0.8467],
               [0.0779428571, 0.5039857143, 0.8383714286],
               [0.079347619, 0.5200238095, 0.8311809524],
               [0.0749428571, 0.5375428571, 0.8262714286],
               [0.0640571429, 0.5569857143, 0.8239571429],
               [0.0487714286, 0.5772238095, 0.8228285714],
               [0.0343428571, 0.5965809524, 0.819852381],
               [0.0265, 0.6137, 0.8135],
               [0.0238904762, 0.6286619048, 0.8037619048],
               [0.0230904762, 0.6417857143, 0.7912666667],
               [0.0227714286, 0.6534857143, 0.7767571429],
               [0.0266619048, 0.6641952381, 0.7607190476],
               [0.0383714286, 0.6742714286, 0.743552381],
               [0.0589714286, 0.6837571429, 0.7253857143],
               [0.0843, 0.6928333333, 0.7061666667],
               [0.1132952381, 0.7015, 0.6858571429],
               [0.1452714286, 0.7097571429, 0.6646285714],
               [0.1801333333, 0.7176571429,  0.6424333333],
               [0.2178285714, 0.7250428571, 0.6192619048],
               [0.2586428571, 0.7317142857, 0.5954285714],
               [0.3021714286, 0.7376047619, 0.5711857143],
               [0.3481666667, 0.7424333333, 0.5472666667],
               [0.3952571429, 0.7459, 0.5244428571],
               [0.4420095238, 0.7480809524,  0.5033142857],
               [0.4871238095, 0.7490619048, 0.4839761905],
               [0.5300285714, 0.7491142857, 0.4661142857],
               [0.5708571429, 0.7485190476, 0.4493904762],
               [0.609852381, 0.7473142857, 0.4336857143],
               [0.6473, 0.7456, 0.4188],
               [0.6834190476, 0.7434761905, 0.4044333333],
               [0.7184095238, 0.7411333333, 0.3904761905],
               [0.7524857143, 0.7384, 0.3768142857],
               [0.7858428571, 0.7355666667,  0.3632714286],
               [0.8185047619, 0.7327333333, 0.3497904762],
               [0.8506571429, 0.7299, 0.3360285714],
               [0.8824333333, 0.7274333333, 0.3217],
               [0.9139333333, 0.7257857143, 0.3062761905],
               [0.9449571429, 0.7261142857,  0.2886428571],
               [0.9738952381, 0.7313952381, 0.266647619],
               [0.9937714286, 0.7454571429, 0.240347619],
               [0.9990428571, 0.7653142857,  0.2164142857],
               [0.9955333333, 0.7860571429, 0.196652381],
               [0.988, 0.8066, 0.1793666667],
               [0.9788571429, 0.8271428571, 0.1633142857],
               [0.9697, 0.8481380952, 0.147452381],
               [0.9625857143, 0.8705142857, 0.1309],
               [0.9588714286, 0.8949, 0.1132428571],
               [0.9598238095, 0.9218333333,  0.0948380952],
               [0.9661, 0.9514428571, 0.0755333333],
               [0.9763, 0.9831, 0.0538]]
    return LinearSegmentedColormap.from_list('parula', cm_data)


def xtec_map():
    """Generate a color map for use with the XTEC package.

    The color map data is the same as the 'tab10' map, but with the lowest
    value set to 'white'.
    """
    from matplotlib import colormaps
    from matplotlib.colors import ListedColormap
    cm_data = list(colormaps['tab10'].colors)
    cm_data.insert(0, [1.0, 1.0, 1.0])
    return ListedColormap(cm_data, name='xtec')


def divgray_map():
    """New divergent color map copied from the registered 'gray' map."""
    if parse_version(mplversion) >= parse_version('3.5.0'):
        from matplotlib import colormaps
        cm = copy.copy(colormaps['gray'])
    else:
        from matplotlib.cm import get_cmap
        cm = copy.copy(get_cmap('gray'))
    cm.name = 'divgray'
    return cm


def cmyk_to_rgb(c, m, y, k):
    """Convert CMYK values to RGB values."""
    r = int(255 * (1.0 - (c + k) / 100.))
    g = int(255 * (1.0 - (m + k) / 100.))
    b = int(255 * (1.0 - (y + k) / 100.))
    return r, g, b


def load_image(filename):
    if os.path.splitext(filename.lower())[1] in ['.png', '.jpg', '.jpeg',
                                                 '.gif']:
        from matplotlib.image import imread
        im = imread(filename)
        z = NXfield(im, name='z')
        y = NXfield(range(z.shape[0]), name='y')
        x = NXfield(range(z.shape[1]), name='x')
        if z.ndim > 2:
            rgba = NXfield(range(z.shape[2]), name='rgba')
            if len(rgba) == 3:
                z.interpretation = 'rgb-image'
            elif len(rgba) == 4:
                z.interpretation = 'rgba-image'
            data = NXdata(z, (y, x, rgba))
        else:
            data = NXdata(z, (y, x))
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
        data = NXdata(z, (y, x))
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


def initialize_settings(settings):
    """Initialize NeXpy settings.

    For the nexusformat configuration parameters, precedence is given to
    those that are defined by environment variables, since these might
    be set by the system administrator. If any configuration parameter
    has not been set before, default values are used.

    The environment variable names are in upper case and preceded by 'NX_'

    Parameters
    ----------
    settings : NXConfigParser
        NXConfigParser instance containing NeXpy settings.
    """

    def setconfig(parameter):
        environment_variable = 'NX_'+parameter.upper()
        if environment_variable in os.environ:
            value = os.environ[environment_variable]
        elif settings.has_option('settings', parameter):
            value = settings.get('settings', parameter)
        else:
            value = nxgetconfig(parameter)
        nxsetconfig(**{parameter: value})
        settings.set('settings', parameter, nxgetconfig(parameter))

    for parameter in nxgetconfig():
        setconfig(parameter)

    if settings.has_option('settings', 'style'):
        set_style(settings.get('settings', 'style'))
    else:
        settings.set('settings', 'style', 'default')

    settings.save()


def set_style(style=None):
    from matplotlib.style import use
    if style == 'publication':
        use('default')
        rcParams['axes.titlesize'] = 24
        rcParams['axes.titlepad'] = 20
        rcParams['axes.labelsize'] = 20
        rcParams['axes.labelpad'] = 5
        rcParams['axes.formatter.limits'] = -5, 5
        rcParams['lines.linewidth'] = 3
        rcParams['lines.markersize'] = 10
        rcParams['xtick.labelsize'] = 16
        rcParams['xtick.direction'] = 'in'
        rcParams['xtick.top'] = True
        rcParams['xtick.major.pad'] = 5
        rcParams['xtick.minor.visible'] = True
        rcParams['ytick.labelsize'] = 16
        rcParams['ytick.direction'] = 'in'
        rcParams['ytick.right'] = True
        rcParams['ytick.major.pad'] = 5
        rcParams['ytick.minor.visible'] = True
        rcParams['legend.fontsize'] = 14
        rcParams['figure.autolayout'] = True
    elif style is not None:
        use(style)
    else:
        use('default')


def in_dark_mode():
    try:
        from .consoleapp import _mainwindow
        app = _mainwindow.app.app
        return (app.palette().window().color().value() <
                app.palette().windowText().color().value())
    except Exception:
        return False


def define_mode():

    from .consoleapp import _mainwindow
    if in_dark_mode():
        _mainwindow.console.set_default_style('linux')
        _mainwindow.statusBar().setPalette(_mainwindow.app.app.palette())
    else:
        _mainwindow.console.set_default_style()
        _mainwindow.statusBar().setPalette(_mainwindow.app.app.palette())

    for dialog in _mainwindow.dialogs:
        if dialog.windowTitle() == 'Script Editor':
            for tab in [dialog.tabs[t] for t in dialog.tabs]:
                tab.define_style()
        elif dialog.windowTitle().startswith('Log File'):
            dialog.format_log()

    for plotview in _mainwindow.plotviews.values():
        if in_dark_mode():
            plotview.otab.setStyleSheet('color: white')
        else:
            plotview.otab.setStyleSheet('color: black')


class NXListener(QtCore.QObject):

    change_signal = QtCore.Signal(str)

    def start(self, fn):
        Thread(target=self.listen, args=(fn,), daemon=True).start()

    def listen(self, fn):
        fn(self)

    def respond(self, signal):
        self.change_signal.emit(signal)


class NXImporter:
    def __init__(self, paths):
        self.paths = [str(p) for p in paths]

    def __enter__(self):
        for path in reversed(self.paths):
            sys.path.insert(0, path)

    def __exit__(self, exc_type, exc_value, traceback):
        for path in self.paths:
            sys.path.remove(path)


def import_plugin(name, paths):
    with NXImporter(paths):
        plugin_module = importlib.import_module(name)
        if hasattr(plugin_module, '__file__'):  # Not a namespace module
            return plugin_module
        else:
            raise ImportError('Plugin cannot be a namespace module')


class NXConfigParser(ConfigParser, object):
    """A ConfigParser subclass that preserves the case of option names"""

    def __init__(self, settings_file):
        super().__init__(allow_no_value=True)
        self.file = settings_file
        self._optcre = re.compile(  # makes '=' the only valid delimiter
            r"(?P<option>.*?)\s*(?:(?P<vi>=)\s*(?P<value>.*))?$", re.VERBOSE)
        super().read(self.file)
        sections = self.sections()
        if 'backups' not in sections:
            self.add_section('backups')
        if 'plugins' not in sections:
            self.add_section('plugins')
        if 'settings' not in sections:
            self.add_section('settings')
        if 'recent' not in sections:
            self.add_section('recent')
        if 'session' not in sections:
            self.add_section('session')
        self.fix_compatibility()

    def set(self, section, option, value=None):
        if value is not None:
            super().set(section, option, str(value))
        else:
            super().set(section, option)

    def optionxform(self, optionstr):
        return optionstr

    def save(self):
        with open(self.file, 'w') as f:
            self.write(f)

    def purge(self, section):
        for option in self.options(section):
            self.remove_option(section, option)

    def fix_compatibility(self):
        """Perform backward compatibility fixes"""
        if 'preferences' in self.sections():
            for option in self.options('preferences'):
                self.set('settings', option, self.get('preferences', option))
            self.remove_section('preferences')
            self.save()
        if 'recentFiles' in self.options('recent'):
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
        super().__init__()
        self.logger = logging.getLogger()
        self.log_level = self.logger.getEffectiveLevel()
        self.linebuf = ''

    def write(self, buffer):
        for line in buffer.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())


class NXGarbageCollector(QtCore.QObject):
    """Perform Python garbage collection manually every 10 seconds.

    This is done to ensure that garbage collection only happens in the GUI
    thread, as otherwise Qt can crash. It is based on code by Fabio Zadrozny
    (https://pydev.blogspot.com/2014/03/should-python-garbage-collector-be.html)
    """

    def __init__(self, parent=None):

        QtCore.QObject.__init__(self, parent=parent)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()
        gc.disable()
        self.timer.start(10000)

    def check(self):
        l0, l1, l2 = gc.get_count()
        if l0 > self.threshold[0]:
            gc.collect(0)
            if l1 > self.threshold[1]:
                gc.collect(1)
                if l2 > self.threshold[2]:
                    gc.collect(2)


class Gaussian3DKernel(Kernel):

    _separable = True
    _is_bool = False

    def __init__(self, stddev, **kwargs):
        def _round_up_to_odd_integer(value):
            import math
            i = int(math.ceil(value))
            if i % 2 == 0:
                return i + 1
            else:
                return i
        x = np.linspace(-15., 15., 17)
        y = np.linspace(-15., 15., 17)
        z = np.linspace(-15., 15., 17)
        X, Y, Z = np.meshgrid(x, y, z)
        array = np.exp(-(X**2+Y**2+Z**2)/(2*stddev**2))
        self._default_size = _round_up_to_odd_integer(8 * stddev)
        super().__init__(array)
        self.normalize()
        self._truncation = np.abs(1. - self._array.sum())
