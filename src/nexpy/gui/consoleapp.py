#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2015, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

""" A minimal application using the Qt console-style Jupyter frontend.
"""

#-----------------------------------------------------------------------------
# Imports
#-----------------------------------------------------------------------------
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import six

import logging
import logging.handlers
import pkg_resources
import os
import shutil
import signal
import sys
import tempfile

from .pyqt import QtCore, QtGui

from .mainwindow import MainWindow
from .treeview import NXtree
from .utils import NXConfigParser, timestamp_age

from nexusformat.nexus import NXroot, nxclasses, nxload

from traitlets.config.application import boolean_flag
from traitlets.config.application import catch_config_error
from qtconsole.jupyter_widget import JupyterWidget
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from qtconsole import styles, __version__
from traitlets import (
    Dict, Unicode, CBool, Any
)

from jupyter_core.application import JupyterApp, base_flags, base_aliases
from jupyter_client.consoleapp import (
        JupyterConsoleApp, app_aliases, app_flags,
    )

#-----------------------------------------------------------------------------
# Globals
#-----------------------------------------------------------------------------

_tree = None
_shell = None
_mainwindow = None
_nexpy_dir = None
_examples = """
nexpy                      # start the GUI application
"""

#-----------------------------------------------------------------------------
# Aliases and Flags
#-----------------------------------------------------------------------------

flags = dict(base_flags)
qt_flags = {
    'plain' : ({'NXConsoleApp' : {'plain' : True}},
            "Disable rich text support."),
}
qt_flags.update(boolean_flag(
    'banner', 'NXConsoleApp.display_banner',
    "Display a banner upon starting the QtConsole.",
    "Don't display a banner upon starting the QtConsole."
))

# and app_flags from the Console Mixin
qt_flags.update(app_flags)
# add frontend flags to the full set
flags.update(qt_flags)

# start with copy of base jupyter aliases
aliases = dict(base_aliases)
qt_aliases = dict(
    style = 'JupyterWidget.syntax_style',
    stylesheet = 'NXConsoleApp.stylesheet',

    editor = 'JupyterWidget.editor',
    paging = 'ConsoleWidget.paging',
)
# and app_aliases from the Console Mixin
qt_aliases.update(app_aliases)
qt_aliases.update({'gui-completion':'ConsoleWidget.gui_completion'})
# add frontend aliases to the full set
aliases.update(qt_aliases)

# get flags&aliases into sets, and remove a couple that
# shouldn't be scrubbed from backend flags:
qt_aliases = set(qt_aliases)
qt_flags = set(qt_flags)

#-----------------------------------------------------------------------------
# NXConsoleApp
#-----------------------------------------------------------------------------

class NXConsoleApp(JupyterApp, JupyterConsoleApp):
    name = 'nexpy-console'
    version = __version__
    description = """
        The NeXpy Console.

        This launches a Console-style application using Qt.

        The console is embedded in a GUI that contains a tree view of
        all NXroot groups and a matplotlib plotting pane. It also has all
        the added benefits of a Jupyter Qt Console with multiline editing,
        autocompletion, tooltips, command line histories and the ability to
        save your session as HTML or print the output.

    """
    examples = _examples

    classes = [JupyterWidget] + JupyterConsoleApp.classes
    flags = Dict(flags)
    aliases = Dict(aliases)
    frontend_flags = Any(qt_flags)
    frontend_aliases = Any(qt_aliases)

    stylesheet = Unicode('', config=True,
        help="path to a custom CSS stylesheet")

    hide_menubar = CBool(False, config=True,
        help="Start the console window with the menu bar hidden.")

    plain = CBool(False, config=True,
        help="Use a plaintext widget instead of rich text (plain can't print/save).")

    display_banner = CBool(True, config=True,
        help="Whether to display a banner upon starting the QtConsole."
    )

    def _plain_changed(self, name, old, new):
        kind = 'plain' if new else 'rich'
        self.config.ConsoleWidget.kind = kind
        if new:
            self.widget_factory = JupyterWidget
        else:
            self.widget_factory = RichJupyterWidget

    # the factory for creating a widget
    widget_factory = Any(RichJupyterWidget)

    def parse_command_line(self, argv=None):
        super(NXConsoleApp, self).parse_command_line(argv)
        self.build_kernel_argv(argv)

    def init_dir(self):
        """Initialize NeXpy home directory"""
        home_dir = os.path.abspath(os.path.expanduser('~'))
        nexpy_dir = os.path.join(home_dir, '.nexpy')
        if not os.path.exists(nexpy_dir):
            parent = os.path.dirname(nexpy_dir)
            if not os.access(parent, os.W_OK):
                nexpy_dir = tempfile.mkdtemp()
            else:
                os.mkdir(nexpy_dir)
        for subdirectory in ['backups', 'functions', 'plugins', 'readers', 
                             'scripts']:
            directory = os.path.join(nexpy_dir, subdirectory)
            if not os.path.exists(directory):
                os.mkdir(directory)
        global _nexpy_dir
        self.nexpy_dir = _nexpy_dir = nexpy_dir
        self.backup_dir = os.path.join(self.nexpy_dir, 'backups')
        self.plugin_dir = os.path.join(self.nexpy_dir, 'plugins')
        self.reader_dir = os.path.join(self.nexpy_dir, 'readers')
        self.script_dir = os.path.join(self.nexpy_dir, 'scripts')
        self.function_dir = os.path.join(self.nexpy_dir, 'functions')
        self.scratch_file = os.path.join(self.nexpy_dir, 'w0.nxs')
        if not os.path.exists(self.scratch_file):
            NXroot().save(self.scratch_file)

    def init_settings(self):
        self.settings = NXConfigParser(os.path.join(self.nexpy_dir, 
                                                    'settings.ini'))
        def backup_age(backup):
            try:
                return timestamp_age(os.path.basename(os.path.dirname(backup)))
            except ValueError:
                return 0
        backups = self.settings.options('backups')
        for backup in backups:
            if not (os.path.exists(backup) and 
                    os.path.realpath(backup).startswith(self.backup_dir)):
                self.settings.remove_option('backups', backup)
            elif backup_age(backup) > 3:
                os.remove(os.path.realpath(backup))
                os.rmdir(os.path.dirname(os.path.realpath(backup))) 
                self.settings.remove_option('backups', backup)
        self.settings.save()

    def init_log(self):
        value = os.getenv("NEXPY_LOG")
        if value == None:
            log_file = os.path.join(self.nexpy_dir, 'nexpy.log')
            hdlr = logging.handlers.RotatingFileHandler(log_file, maxBytes=50000,
                                                        backupCount=5)
            fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            fmtr = logging.Formatter(fmt, None)
            logging.root.setLevel(logging.INFO)
        else:
            hdlr = logging.StreamHandler(stream=sys.stdout)
            fmt = '%(levelname)s %(module)s.%(funcName)s() %(message)s'
            fmtr = logging.Formatter(fmt)
            try:
                logging.root.setLevel(logging.__dict__[value])
            except KeyError:
                print('Invalid log level:', value)
                sys.exit(1)
        hdlr.setFormatter(fmtr)
        logging.root.addHandler(hdlr)
        logging.info('NeXpy launched')
        logging.debug('Log level is: ' + str(value))

    def init_tree(self):
        """Initialize the NeXus tree used in the tree view."""
        global _tree
        self.tree = NXtree()
        _tree = self.tree

    def init_gui(self):
        """Initialize the GUI."""
        self.app = QtGui.QApplication.instance()
        if self.app is None:
            self.app = QtGui.QApplication(['nexpy'])
        self.app.setApplicationName('nexpy')
        self.window = MainWindow(self, self.tree, self.settings, self.config)
        self.window.log = self.log
        global _mainwindow
        _mainwindow = self.window
        try:
            if 'svg' in QtGui.QImageReader.supportedImageFormats():
                self.app.icon = QtGui.QIcon(
                    pkg_resources.resource_filename('nexpy.gui',
                                                    'resources/icon/NeXpy.svg'))
            else:
                self.app.icon = QtGui.QIcon(
                    pkg_resources.resource_filename('nexpy.gui',
                                                    'resources/icon/NeXpy.png'))
            QtGui.QApplication.setWindowIcon(self.app.icon)
        except Exception:
            pass

    def init_shell(self, filename):
        """Initialize imports in the shell."""
        global _shell
        _shell = self.window.user_ns
        s = ("import nexusformat.nexus as nx\n"
             "from nexusformat.nexus import NXgroup, NXfield, NXattr, NXlink\n"
             "from nexusformat.nexus import *\n"
             "import nexpy\n"
             "from nexpy.gui.plotview import NXPlotView")
        six.exec_(s, self.window.user_ns)

        s = ""
        for _class in nxclasses:
            s = "%s=nx.%s\n" % (_class,_class) + s
        six.exec_(s, self.window.user_ns)

        try:
            f = open(os.path.join(os.path.expanduser('~'), '.nexpy',
                                  'config.py'))
            s = ''.join(f.readlines())
            six.exec_(s, self.window.user_ns)
        except:
            s = ("import sys\n"
                 "import os\n"
                 "import h5py as h5\n"
                 "import numpy as np\n"
                 "import numpy.ma as ma\n"
                 "import scipy as sp\n"
                 "import matplotlib as mpl\n"
                 "from matplotlib import pylab, mlab, pyplot\n"
                 "plt = pyplot")
            six.exec_(s,  self.window.user_ns)
        if filename is not None:
            try:
                fname = os.path.expanduser(filename)
                name = self.window.treeview.tree.get_name(fname)
                self.window.treeview.tree[name] = self.window.user_ns[name] \
                                                = nxload(fname)
                self.window.treeview.select_node(self.window.treeview.tree[name])
                logging.info("NeXus file '%s' opened as workspace '%s'"
                              % (fname, name))
                self.window.user_ns[name].plot()
            except Exception:
                pass

    def init_colors(self):
        """Configure the coloring of the widget"""
        # Note: This will be dramatically simplified when colors
        # are removed from the backend.

        # Configure the style.
        self.window.console.set_default_style()

    def init_signal(self):
        """allow clean shutdown on sigint"""
        signal.signal(signal.SIGINT, lambda sig, frame: self.exit(-2))
        # need a timer, so that QApplication doesn't block until a real
        # Qt event fires (can require mouse movement)
        # timer trick from http://stackoverflow.com/q/4938723/938949
        timer = QtCore.QTimer()
        # Let the interpreter run each 200 ms:
        timer.timeout.connect(lambda: None)
        timer.start(200)
        # hold onto ref, so the timer doesn't get cleaned up
        self._sigint_timer = timer

    @catch_config_error
    def initialize(self, filename=None, argv=None):
        super(NXConsoleApp, self).initialize(argv)
        self.init_dir()
        self.init_settings()
        self.init_log()
        self.init_tree()
        self.init_gui()
        self.init_shell(filename)
        self.init_colors()
        self.init_signal()

    def start(self):
        super(NXConsoleApp, self).start()

        # draw the window
        self.window.show()
        self.window.raise_()

        # Start the application main loop.
        self.app.exec_()

#-----------------------------------------------------------------------------
# Main entry point
#-----------------------------------------------------------------------------

def main(filename=None):
    app = NXConsoleApp()
    app.initialize(filename=filename)
    app.start()


if __name__ == '__main__':
    main()
