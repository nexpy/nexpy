# -----------------------------------------------------------------------------
# Copyright (c) 2013-2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

import copy
import gc
import io
import logging
import os
import re
import sys
import textwrap
import traceback as tb
from configparser import ConfigParser
from datetime import datetime

if sys.version_info < (3, 10):
    from importlib_metadata import PackageNotFoundError, entry_points
    from importlib_metadata import version as metadata_version
    from importlib_resources import files as package_files
else:
    from importlib.metadata import PackageNotFoundError, entry_points
    from importlib.metadata import version as metadata_version
    from importlib.resources import files as package_files

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from threading import Thread

import numpy as np
from ansi2html import Ansi2HTMLConverter
from IPython.core.ultratb import FormattedTB
from matplotlib import __version__ as mplversion
from matplotlib import rcParams
from matplotlib.colors import colorConverter, hex2color, rgb2hex
from packaging.version import Version
from PIL import Image

from .pyqt import QtCore, QtGui, QtWidgets

try:
    from astropy.convolution import Kernel
except ImportError:
    Kernel = object
try:
    import fabio
except ImportError:
    fabio = None

from nexusformat.nexus import (NeXusError, NXcollection, NXdata, NXfield,
                               NXLock, NXLockException, NXnote, nxgetconfig,
                               nxload, nxsetconfig)


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
    return message_box.exec()


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

    response = message_box.exec()
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
    return message_box.exec()


def report_exception(*args):
    """Display and log an uncaught exception with its traceback"""
    if len(args) == 3:
        error_type, error, traceback = args[:3]
    elif len(args) == 1:
        exc = args[0]
        error_type, error, traceback = exc.__class__, exc, exc.__traceback__
    message = ''.join(tb.format_exception_only(error_type, error))
    if in_dark_mode():
        theme = 'linux'
    else:
        theme = 'lightbg'
    information = FormattedTB(mode="Context", theme_name=theme).text(
        error_type, error,
                                                   traceback)
    logging.error('Exception in GUI event loop\n'+information+'\n')
    message_box = QtWidgets.QMessageBox()
    message_box.setText(message)
    message_box.setInformativeText(convertHTML(information))
    message_box.setIcon(QtWidgets.QMessageBox.Warning)
    layout = message_box.layout()
    layout.setColumnMinimumWidth(layout.columnCount()-1, 600)
    return message_box.exec()


def run_pythonw(script_path):
    """
    Execute the NeXpy startup script using 'pythonw' on MacOS.

    This relaunches the script in a subprocess using a framework build
    of Python in order to fix the frozen menubar issue in MacOS 10.15
    Catalina.

    Based on https://github.com/napari/napari/pull/1554.
    """
    if 'PYTHONEXECUTABLE' in os.environ:
        return
    import platform
    import warnings

    if (Version(platform.release()) > Version('19.0.0') and
            'CONDA_PREFIX' in os.environ):
        pythonw_path = Path(sys.exec_prefix).joinpath('bin', 'pythonw')
        if pythonw_path.exists():
            cmd = [pythonw_path, script_path]
            env = os.environ.copy()
            if len(sys.argv) > 1:
                cmd.extend(sys.argv[1:])
            import subprocess
            result = subprocess.run(cmd, env=env, cwd=Path.cwd())
            sys.exit(result.returncode)
        else:
            msg = ("'pythonw' executable not found.\n"
                   "To unfreeze the menubar on macOS, "
                   "click away from nexpy to another app, "
                   "then reactivate nexpy. To avoid this problem, "
                   "please install python.app in conda using:\n\n"
                   "conda install -c conda-forge python.app\n")
            warnings.warn(msg)


def get_mainwindow():
    """Return the NeXpy main window"""
    from .consoleapp import _mainwindow
    return _mainwindow


def is_file_locked(filename, wait=5, expiry=None):
    """
    Check if a file is locked.

    Parameters
    ----------
    filename : str
        name of file to check
    wait : int, optional
        number of seconds to wait for file to be unlocked
    expiry : int, optional
        age in seconds at which a lock is considered stale and can be
        cleared

    Returns
    -------
    True if the file is locked, False if it is not.
    """
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


def wrap(text, width=80, compress=False):
    """Wrap text lines based on a given length"""
    if compress:
        text = '\n'.join(re.sub(' +', ' ', line) for line in text.splitlines())
    return '\n'.join(textwrap.fill(line, width) for line in text.splitlines())


def natural_sort(key):
    """Sort numbers according to their value."""
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', str(key))]


def clamp(value, min_value, max_value):
    """
    Return value constrained to be within defined limits

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
    """
    Return the centers of the axis bins.

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
    """
    Return the boundaries of the axis bins.

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
    """
    Store the data in the scratch workspace.

    Parameters
    ----------
    data : NXdata
        NXdata group containing the data to be stored
    """
    mainwindow = get_mainwindow()
    tree = mainwindow.tree
    if 'w0' not in tree:
        tree['w0'] = nxload(mainwindow.nexpy_dir.joinpath('w0.nxs'), 'rw')
    ind = []
    for key in tree['w0']:
        try:
            if key.startswith('s'):
                ind.append(int(key[1:]))
        except ValueError:
            pass
    if ind == []:
        ind = [0]
    data.nxname = 's'+str(sorted(ind)[-1]+1)
    tree['w0'][data.nxname] = data


def fix_projection(shape, axes, limits):
    """
    Fix the axes and limits for data with dimension sizes of 1.

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
    """Return the array value that is closest to the given value."""
    idx = (np.abs(array-value)).argmin()
    return array[idx]


def find_nearest_index(array, value):
    """Return the index of the nearest value in an array."""
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
    """Return the number of days since the timestamp."""
    return (datetime.now() - read_timestamp(timestamp)).days


def is_timestamp(timestamp):
    """Return True if the string is formatted as a timestamp."""
    try:
        return isinstance(read_timestamp(timestamp), datetime)
    except ValueError:
        return False


def get_mtime(file_path):
    """Return the file modification time for the specified file path."""
    try:
        return Path(file_path).stat().st_mtime
    except FileNotFoundError:  # due to a race condition
        return 0.0


def format_mtime(mtime):
    """Return the modification time as a formatted string."""
    return str(datetime.fromtimestamp(mtime))[:19]


def modification_time(filename):
    """Return the file modification time for the specified file path."""
    try:
        _mtime = Path(filename).stat().st_mtime
        return str(datetime.fromtimestamp(_mtime))
    except FileNotFoundError:
        return ''


def convertHTML(text, switch=False):
    """
    Convert text with ANSI escape sequences to HTML.

    Parameters
    ----------
    text : str
        Text containing ANSI escape sequences
    switch : bool, optional
        If True, switch dark mode of the converted text. Default is
        False.

    Returns
    -------
    str
        Text with ANSI escape sequences converted to HTML
    """
    try:
        if switch:
            dark_bg = not in_dark_mode()
        else:
            dark_bg = in_dark_mode()
        conv = Ansi2HTMLConverter(dark_bg=dark_bg, inline=True)
        return conv.convert(text).replace('AAAAAA', 'FFFFFF')
    except ImportError:
        return ansi_re.sub('', text)


def get_name(filename, entries=None):
    """
    Return a valid Python object name based on the filename stem.
    
    If the filename stem already exists in the entries dictionary,
    append a number to the name.

    Parameters
    ----------
    filename : str
        File name
    entries : dict, optional
        Dictionary of existing entry names. If None, no check is made.

    Returns
    -------
    str
        Unique name
    """
    name = re.sub(r'\W|^(?=\d)','_', Path(filename).stem)
    if entries and name in entries:
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
    """Convert color to hex string."""
    return rgb2hex(colorConverter.to_rgb(color))


def get_colors(n, first=None, last=None):
    """
    Return a list of colors interpolating between the first and last.

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
    """
    Generate a color map similar to Matlab's Parula for use in NeXpy.

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
    """
    Generate a color map for use with the XTEC package.

    The color map data is the same as the 'tab10' map, but with the
    lowest value set to 'white'.
    """
    from matplotlib import colormaps
    from matplotlib.colors import ListedColormap
    cm_data = list(colormaps['tab10'].colors)
    cm_data.insert(0, [1.0, 1.0, 1.0])
    return ListedColormap(cm_data, name='xtec')


def divgray_map():
    """New divergent color map copied from the registered 'gray' map."""
    if Version(mplversion) >= Version('3.5.0'):
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
    """
    Load an image file and convert it to a NeXus NXdata object.

    The image can be in any format supported by PIL (Python Imaging
    Library) or fabio. The data is stored in a NXfield in the NXdata
    object with the name 'z'. The axes are named 'y' and 'x' and are
    also stored in NXfield objects.

    If the image is in color, the data is stored in a 3D array and the
    interpretation of the array is set to 'rgb-image' or 'rgba-image'
    depending on the number of color channels.

    The title of the NXdata object is set to the name of the file.

    Parameters
    ----------
    filename : str
        The name of the image file to load.

    Returns
    -------
    data : NXdata
        The loaded image as a NeXus NXdata object.
    """
    if Path(filename).suffix.lower() in ['.png', '.jpg', '.jpeg', '.gif']:
        with Image.open(filename) as PIL_image:
            if PIL_image.mode in ['LA', 'P']:
                im = np.array(PIL_image.convert('RGBA'))
            elif PIL_image.mode not in ['RGB', 'RGBA']:
                im = np.array(PIL_image.convert('RGB'))
            else:
                im = np.array(PIL_image)
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
        except Exception:
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
            data["header"] = header
        if im.getclassname() == 'CbfImage':
            note = NXnote(type='text/plain', file_name=filename)
            note["data"] = im.header.pop('_array_data.header_contents', '')
            note["description"] = im.header.pop(
                '_array_data.header_convention', '')
            data["CBF_header"] = note
    data["title"] = filename
    return data


def import_plugin(plugin_path):
    """
    Import a plugin module from a given path.

    Parameters
    ----------
    plugin_path : Path
        The path to the plugin module.

    Returns
    -------
    module : module
        The imported plugin module, or None if the import failed.
    """
    plugin_name = plugin_path.stem
    if plugin_path.is_dir():
        plugin_path = plugin_path.joinpath('__init__.py')
    if (spec := spec_from_file_location(plugin_name, plugin_path)) is not None:
        module = module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    else:
        return None


def load_plugin(plugin, order=None):
    """
    Load a specified plugin and return its configuration details.

    This function determines if the provided `plugin` parameter is a
    directory or an entry point from the `nexpy.plugins` group. If it is
    a directory, it imports the plugin module, retrieves the menu name
    and actions from the `plugin_menu` function, and returns them along
    with the package name and plugin path. If it is an entry point, it
    loads the entry point, retrieves the menu name and actions, and
    returns them along with the package name and plugin module.

    Parameters
    ----------
    plugin : str
        The path to the plugin directory or the name of the plugin
        module.

    Returns
    -------
    tuple
        A tuple containing the package name, plugin path or module name,
        menu name, and a list of menu actions.
    """
    if Path(plugin).is_dir():
        plugin_path = Path(plugin)
        package = plugin_path.stem
        module = import_plugin(plugin_path)
        menu, actions = module.plugin_menu()
    else:
        eps = entry_points().select(group='nexpy.plugins')
        entry = next((e for e in eps if e.module == plugin), None)
        package = entry.dist.name
        menu, actions = entry.load()()
    return {'package': package, 'menu': menu, 'actions': actions,
            'order': order}


def load_readers():
    """
    Load the available data readers.

    The data readers are loaded from the following sources in order:

    1. The user's private directory, ``~/.nexpy/readers``.
    2. The public directory, ``nexpy/readers``.
    3. The ``nexpy.readers`` entry point.

    The readers are loaded as Python modules and their contents are
    added to a dictionary, which is returned.

    Returns
    -------
    dict
        A dictionary of data readers, where the key is the name of the
        reader and the value is the module containing the reader.
    """
    readers = {}
    private_path = Path.home() / '.nexpy' / 'readers'
    if private_path.exists():
        for reader in private_path.iterdir():
            try:
                reader_module = import_plugin(reader)
                if reader_module is not None:
                    readers[reader.stem] = reader_module
            except Exception:
                pass
    public_path = package_files('nexpy').joinpath('readers')
    for reader in public_path.glob('*.py'):
        if reader.stem != '__init__':
            try:
                reader_module = import_plugin(reader)
                if reader_module is not None:
                    readers[reader.stem] = reader_module
            except Exception:
                pass
    eps = entry_points().select(group='nexpy.readers')
    for entry in eps:
        try:
            readers[entry.name] = entry.load()
        except Exception:
            pass
            
    return readers


def load_models():
    """
    Load the available models.

    The models are loaded from the following sources in order:

    1. The user's private directory, ``~/.nexpy/models``.
    2. The public directory, ``nexpy/models``.
    3. The ``nexpy.models`` entry point.

    The models are loaded as Python modules and their contents are added
    to a dictionary, which is returned.

    Returns
    -------
    dict
        A dictionary of models, where the key is the name of the model
        and the value is the module containing the model.
    """
    models = {}
    private_path = Path.home() / '.nexpy' / 'models'
    if private_path.exists():
        for model in private_path.iterdir():
            try:
                model_module = import_plugin(model)
                if model_module is not None:
                    models[model.stem] = model_module
            except Exception:
                pass
    public_path = package_files('nexpy').joinpath('models')
    for model in public_path.glob('*.py'):
        if model.stem != '__init__':
            try:
                model_module = import_plugin(model)
                if model_module is not None:
                    models[model.stem] = model_module
            except Exception:
                pass
    eps = entry_points().select(group='nexpy.models')
    for entry in eps:
        try:
            models[entry.name] = entry.load()
        except Exception:
            pass
    return models


def is_installed(package_name):
    """
    Check if a package is installed.

    Parameters
    ----------
    package_name : str
        Name of the package to check.

    Returns
    -------
    bool
        True if the package is installed, False otherwise.
    """
    try:
        metadata_version(package_name)
        return True
    except PackageNotFoundError:
        return False


def resource_file(filename):
    """Return the full path to a resource file within the package."""
    return str(package_files('nexpy.gui.resources').joinpath(filename))


def resource_icon(filename):
    """Return a Qt icon from a resource file within the package."""
    return QtGui.QIcon(resource_file(filename))


def initialize_settings(settings):
    """
    Initialize NeXpy settings.

    For the nexusformat configuration parameters, precedence is given to
    those that are defined by environment variables, since these might
    be set by the system administrator. If any configuration parameter
    has not been set before, default values are used.

    The environment variable names are in upper case and preceded by
    'NX_'

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

    script_directory = os.environ.get('NX_SCRIPTDIRECTORY', '')
    if script_directory and Path(script_directory).is_dir():
        settings.set('settings', 'scriptdirectory', script_directory)
    elif not settings.has_option('settings', 'scriptdirectory'):
        settings.set('settings', 'scriptdirectory', None)

    if 'plugins' not in settings.sections():
        settings.add_section('plugins')

    settings.save()


def set_style(style=None):
    """
    Set the style of Matplotlib plots.

    Parameters
    ----------
    style : str, optional
        Name of the style sheet to use. If None, the default style is
        used. If 'publication', the style is set to a format suitable
        for publication.
    """
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
    """
    Return True if the application is in dark mode, False otherwise.

    This works by comparing the value of the window and windowText
    colors in the application's palette. If the window color is darker
    than the windowText color, the application is in dark mode.
    Otherwise, it is in light mode. If the application is not properly
    initialized, this function will return False.

    Returns
    -------
    bool
        True if the application is in dark mode, False otherwise.
    """
    try:
        mainwindow = get_mainwindow()
        app = mainwindow.app.app
        return (app.palette().window().color().value() <
                app.palette().windowText().color().value())
    except Exception:
        return False


def define_mode():
    """
    Define the display mode for the application.

    This function changes the style of the console, the colors of the
    status bar, and the colors of the script editor text boxes based on
    the value of the in_dark_mode function.

    This function is typically called when the application is first
    launched or when the user changes the display mode from the menu.
    """
    mainwindow = get_mainwindow()
    if in_dark_mode():
        mainwindow.console.set_default_style('linux')
        mainwindow.shell.colors = 'linux'
        mainwindow.statusBar().setPalette(mainwindow.app.app.palette())
    else:
        mainwindow.console.set_default_style()
        mainwindow.shell.colors = 'lightbg'
        mainwindow.statusBar().setPalette(mainwindow.app.app.palette())

    for dialog in mainwindow.dialogs:
        if dialog.windowTitle() == 'Script Editor':
            for tab in [dialog.tabs[t] for t in dialog.tabs]:
                tab.define_style()
        elif dialog.windowTitle().startswith('Log File'):
            dialog.switch_mode()

    for plotview in mainwindow.plotviews.values():
        if in_dark_mode():
            plotview.otab.setStyleSheet('color: white')
        else:
            plotview.otab.setStyleSheet('color: black')


def rotate_point(point, angle=45.0, center=[0.0, 0.0], aspect=1.0):
    """
    Rotate a point around a given center by a given angle

    Parameters
    ----------
    point: 2-element list
        The point to rotate
    angle: float
        The angle of the rotation in degrees
    center: 2-element list
        The center of the rotation
    aspect: float
        The aspect ratio, i.e., the ratio of y-axis to the x-axis units

    Returns
    -------
    2-element list
        The rotated point
    """
    cp = np.subtract(point, center)
    angle = np.radians(angle)
    px = cp[0] * np.cos(angle) - aspect * cp[1] * np.sin(angle)
    py = (cp[0] * np.sin(angle) / aspect) + cp[1] * np.cos(angle)
    return list(np.add([px, py], center))


def rotate_data(data, angle=45, aspect='equal'):
    """
    Rotate a 2D NXdata object by a specified angle.

    Parameters
    ----------
    data : NXdata
        NXdata object containing the 2D data to be rotated.
    angle : float, optional
        Angle of rotation in degrees. Default is 45.
    aspect : str or float, optional
        Aspect ratio of the data for rotation calculations. If a float
        is provided, it is used to adjust the rotation angle. Default is
        'equal'.

    Returns
    -------
    NXdata
        A new NXdata object containing the rotated data and axes.

    Raises
    ------
    NeXusError
        If the input data is not 2D.

    Notes
    -----
    The rotation is performed about the geometric center of the data
    using the scipy.ndimage.rotate function. The axes are recalculated
    to match the new dimensions of the rotated data.
    """
    if data.ndim != 2:
        raise NeXusError('Can only rotate 2D data.')
    elif aspect == 'auto':
        raise NeXusError('Aspect ratio must be defined.')
    elif aspect == 'equal':
        aspect = 1.0

    x = data.nxaxes[1]
    y = data.nxaxes[0]
    x0 = (x[0] + x[-1])/2
    y0 = (y[0] + y[-1])/2

    if np.isclose(angle, 0.0):
        data.attrs['x0'] = x0
        data.attrs['y0'] = y0
        return data
    elif np.isclose(np.abs(angle), 90.0):
        signal = NXfield(np.swapaxes(data.nxsignal, 0, 1), name=data.nxsignal,
                         attrs=data.nxsignal.safe_attrs)
        if data.nxerrors is not None:
            errors = NXfield(np.swapaxes(data.nxerrors, 0, 1),
                             name=data.nxerrors,
                             attrs=data.nxerrors.safe_attrs)
        else:
            errors = None
        if data.nxweights is not None:
            weights = NXfield(np.swapaxes(data.nxweights, 0, 1),
                              name=data.nxweights,
                              attrs=data.nxweights.safe_attrs)
        else:
            weights = None
        y = data.nxaxes[0]
        x = data.nxaxes[1]
        result = NXdata(signal, (x, y), errors=errors, weights=weights)
        result.attrs['x0'] = x0
        result.attrs['y0'] = y0
        return result

    original_data = data.nxsignal
    original_errors = data.nxerrors
    original_weights = data.nxweights
    x_name = f"{x.nxname} * cos({angle}°) - {y.nxname} * sin({angle}°)"
    y_name = f"{x.nxname} * sin({angle}°) + {y.nxname} * cos({angle}°)"

    corners = [rotate_point((x.min(), y.min()), angle, (x0, y0), aspect),
               rotate_point((x.max(), y.min()), angle, (x0, y0), aspect),
               rotate_point((x.max(), y.max()), angle, (x0, y0), aspect),
               rotate_point((x.min(), y.max()), angle, (x0, y0), aspect)]
    xmin, ymin = np.min(corners, axis=0)
    xmax, ymax = np.max(corners, axis=0)

    angle = np.radians(angle)

    from scipy.ndimage import rotate, zoom

    if not np.isclose(aspect, 1.0):
        ny, nx = original_data.shape
        zoom_y = aspect * (((y.max() - y.min()) * nx) /
                           ((x.max() - x.min()) * ny))
        original_data = zoom(original_data, (zoom_y, 1), order=1)
    else:
        rotated_aspect = None

    # The angle is negative because scipy assumes a top-left origin
    angle = - np.degrees(angle)

    rotated_data = NXfield(rotate(original_data, angle, axes=(1,0),
                                  reshape=True, order=1, mode='constant',
                                  cval=0.0), name=data.nxsignal.nxname)
    if np.all(original_data >= 0.0):
        vmin = np.min(original_data[np.nonzero(original_data)])
        rotated_data[(rotated_data!=0) & (np.abs(rotated_data)<vmin)] = vmin
    ny, nx = rotated_data.shape
    rotated_x = NXfield(np.linspace(xmin, xmax, nx), name='rotated_x',
                        long_name=x_name)
    rotated_y = NXfield(np.linspace(ymin, ymax, ny), name='rotated_y',
                        long_name=y_name)
    rotated_aspect = ((xmax - xmin) * ny) / ((ymax - ymin) * nx)
    if original_errors is not None:
        rotated_errors = NXfield(rotate(original_errors, angle, axes=(1,0),
                                        reshape=True, order=1,
                                        mode='constant', cval=0.0),
                                 name=data.nxerrors.nxname)
    if original_weights is not None:
        rotated_weights = NXfield(rotate(original_weights, angle, axes=(1,0),
                                         reshape=True, order=1,
                                         mode='constant', cval=0.0),
                                  name=data.nxweights.nxname)
    result = NXdata(rotated_data, (rotated_y, rotated_x), title=data.nxtitle)
    result.attrs['aspect'] = rotated_aspect
    result.attrs['x0'] = x0
    result.attrs['y0'] = y0
    if original_errors is not None:
        result.nxerrors = rotated_errors
    if original_weights is not None:
        result.nxweights = rotated_weights
    return result


class NXListener(QtCore.QObject):

    change_signal = QtCore.Signal(str)

    def start(self, fn):
        """
        Start the listener thread.

        Parameters
        ----------
        fn : callable
            A callable object that takes one argument, the listener
            object.
        """
        Thread(target=self.listen, args=(fn,), daemon=True).start()

    def listen(self, fn):
        """Listen for changes in the signal."""
        fn(self)

    def respond(self, signal):
        """Respond to a change in the signal."""
        self.change_signal.emit(signal)


class NXConfigParser(ConfigParser, object):

    def __init__(self, settings_file):
        """
        Initialize the NXConfigParser object.

        Parameters
        ----------
        settings_file : str
            The name of the settings file to read from and write to.

        Notes
        -----
        The settings file is read in and the sections 'backups',
        'plugins', 'settings', 'recent', and 'session' are added if they
        do not already exist. The internal representation of the
        ConfigParser object is fixed for compatibility with older
        versions of NeXpy.
        """
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

    def __repr__(self):
        return f"NXConfigParser('{self.file}')"

    def set(self, section, option, value=None):
        """Set an option in the specified section."""
        if value is not None:
            super().set(section, option, str(value))
        else:
            super().set(section, str(option))

    def optionxform(self, optionstr):
        """Do not convert options to lowercase."""
        return optionstr

    def save(self):
        """Save the settings file."""
        with open(self.file, 'w') as f:
            self.write(f)

    def purge(self, section):
        """Remove all options in the specified section."""
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
    """
    File-like stream object that redirects writes to the default logger.

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
    """
    Perform Python garbage collection manually every 10 seconds.

    This is done to ensure that garbage collection only happens in the
    GUI thread, as otherwise Qt can crash. It is based on code by Fabio
    Zadrozny (https://tinyurl.com/5hdj79sp).
    """

    def __init__(self, parent=None):

        """
        Initialize the garbage collector object.

        The garbage collector is disabled and a timer is set up to
        manually collect garbage every 10 seconds. This is done to
        prevent garbage collection from happening in a non-GUI thread,
        which can crash Qt.
        """
        QtCore.QObject.__init__(self, parent=parent)
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()
        gc.disable()
        self.timer.start(10000)

    def check(self):
        """Manually collect garbage."""
        l0, l1, l2 = gc.get_count()
        if l0 > self.threshold[0]:
            gc.collect(0)
            if l1 > self.threshold[1]:
                gc.collect(1)
                if l2 > self.threshold[2]:
                    gc.collect(2)


class NXValidationHandler(logging.handlers.BufferingHandler):

    def shouldFlush(self, record):
        """Disable flushing the buffer on every record."""
        return False

    def flush(self):
        """Flush the buffer on completion."""
        text = []
        if self.buffer:
            for record in self.buffer:
                text.append(self.format(record))
            self.buffer.clear()
        return "\n".join(text)


class Gaussian3DKernel(Kernel):

    _separable = True
    _is_bool = False

    def __init__(self, stddev, **kwargs):
        """
        Initialize a Gaussian 3D kernel for use in image processing.

        Parameters
        ----------
        stddev : float
            Standard deviation of the Gaussian kernel. The resulting
            kernel will have a size of 8*stddev, rounded up to the
            nearest odd integer.
        """
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
