# -----------------------------------------------------------------------------
# Copyright (c) 2013-2022, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------

"""
A minimal application using the Qt console-style Jupyter frontend.
"""

import logging
import logging.handlers
import os
import shutil
import signal
import sys
import tempfile
from importlib.metadata import entry_points
from pathlib import Path

from IPython import __version__ as ipython_version
from jupyter_client.consoleapp import JupyterConsoleApp, app_aliases, app_flags
from jupyter_core.application import JupyterApp, base_aliases, base_flags
from matplotlib import __version__ as mpl_version
from nexusformat.nexus import NXroot, nxclasses, nxversion
from qtconsole import __version__
from qtconsole.jupyter_widget import JupyterWidget
from qtconsole.rich_jupyter_widget import RichJupyterWidget
from traitlets import Any, CBool, Dict, Unicode
from traitlets.config.application import boolean_flag, catch_config_error

from .. import __version__ as nexpy_version
from .mainwindow import MainWindow
from .pyqt import QtCore, QtGui, QtVersion, QtWidgets
from .treeview import NXtree
from .utils import (NXConfigParser, NXGarbageCollector, NXLogger, define_mode,
                    initialize_settings, report_exception, resource_icon,
                    timestamp_age)

# -----------------------------------------------------------------------------
# Globals
# -----------------------------------------------------------------------------

_tree = None
_shell = None
_mainwindow = None
_nexpy_dir = None
_examples = """
nexpy                      # start the GUI application
"""

# -----------------------------------------------------------------------------
# Aliases and Flags
# -----------------------------------------------------------------------------

flags = dict(base_flags)
qt_flags = {'plain': ({'NXConsoleApp': {'plain': True}},
                      "Disable rich text support.")}
qt_flags.update(boolean_flag(
    'banner', 'NXConsoleApp.display_banner',
    "Display a banner upon starting the QtConsole.",
    "Don't display a banner upon starting the QtConsole."
))
qt_flags.update(app_flags)
flags.update(qt_flags)

aliases = dict(base_aliases)
qt_aliases = dict(style='JupyterWidget.syntax_style',
                  stylesheet='NXConsoleApp.stylesheet',
                  editor='JupyterWidget.editor',
                  paging='ConsoleWidget.paging')
qt_aliases.update(app_aliases)
qt_aliases.update({'gui-completion': 'ConsoleWidget.gui_completion'})
aliases.update(qt_aliases)

qt_aliases = set(qt_aliases)
qt_flags = set(qt_flags)

# -----------------------------------------------------------------------------
# NXConsoleApp
# -----------------------------------------------------------------------------


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

    hide_menubar = CBool(
        False, config=True,
        help="Start the console window with the menu bar hidden.")

    plain = CBool(False, config=True,
                  help="Use a plaintext widget instead of rich text.")

    display_banner = CBool(
        True, config=True,
        help="Whether to display a banner upon starting the QtConsole.")

    def _plain_changed(self, name, old, new):
        kind = 'plain' if new else 'rich'
        self.config.ConsoleWidget.kind = kind
        if new:
            self.widget_factory = JupyterWidget
        else:
            self.widget_factory = RichJupyterWidget

    widget_factory = Any(RichJupyterWidget)

    def parse_command_line(self, argv=None):
        super().parse_command_line(argv)
        self.build_kernel_argv(argv)

    def init_dir(self):
        """Initialize NeXpy home directory"""
        nexpy_dir = Path.home() / '.nexpy'
        if not nexpy_dir.exists():
            if not os.access(Path.home(), os.W_OK):
                nexpy_dir = tempfile.mkdtemp()
            else:
                nexpy_dir.mkdir(exist_ok=True)
        for subdirectory in ['backups', 'models', 'plugins', 'readers',
                             'writers', 'scripts']:
            directory = nexpy_dir / subdirectory
            directory.mkdir(exist_ok=True)
        global _nexpy_dir
        self.nexpy_dir = _nexpy_dir = nexpy_dir
        self.backup_dir = self.nexpy_dir / 'backups'
        self.plugin_dir = self.nexpy_dir / 'plugins'
        self.reader_dir = self.nexpy_dir / 'readers'
        self.writer_dir = self.nexpy_dir / 'writers'
        self.script_dir = self.nexpy_dir / 'scripts'
        self.scratch_file = self.nexpy_dir / 'w0.nxs'
        if not self.scratch_file.exists():
            NXroot().save(self.scratch_file)

    def init_settings(self):
        """Initialize access to the NeXpy settings file."""
        self.settings_file = self.nexpy_dir / 'settings.ini'
        self.settings = NXConfigParser(self.settings_file)
        initialize_settings(self.settings)

        def backup_age(backup):
            try:
                return timestamp_age(Path(backup).parent.name)
            except ValueError:
                return 0

        backups = self.settings.options('backups')
        for backup in backups:
            if not (Path(backup).exists() and
                    self.backup_dir in Path(backup).parents):
                if backup in backups:
                    self.settings.remove_option('backups', backup)
            elif backup_age(backup) > 5:
                try:
                    shutil.rmtree(Path(backup).parent)
                    if backup in backups:
                        self.settings.remove_option('backups', backup)
                except OSError:
                    pass
        self.settings.save()

    def init_log(self):
        """Initialize the NeXpy logger."""
        log_file = self.nexpy_dir / 'nexpy.log'
        handler = logging.handlers.RotatingFileHandler(log_file,
                                                       maxBytes=50000,
                                                       backupCount=5)
        fmt = '%(asctime)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(fmt, None)
        handler.setFormatter(formatter)
        try:
            if logging.root.hasHandlers():
                for h in logging.root.handlers:
                    logging.root.removeHandler(h)
        except Exception:
            pass
        logging.root.addHandler(handler)
        levels = {'CRITICAL': logging.CRITICAL, 'ERROR': logging.ERROR,
                  'WARNING': logging.WARNING, 'INFO': logging.INFO,
                  'DEBUG': logging.DEBUG}
        level = os.getenv("NEXPY_LOG")
        if level is None or level.upper() not in levels:
            level = 'INFO'
        else:
            level = level.upper()
        logging.root.setLevel(levels[level])
        logging.info('NeXpy launched')
        logging.info('Log level is ' + level)
        logging.info('Python ' + sys.version.split()[0] + ': '
                     + sys.executable)
        logging.info(QtVersion)
        logging.info('IPython v' + ipython_version)
        logging.info('Matplotlib v' + mpl_version)
        logging.info('NeXpy v' + nexpy_version)
        logging.info('nexusformat v' + nxversion)
        sys.stdout = sys.stderr = NXLogger()

    def init_plugins(self):
        """Initialize the NeXpy plugins."""
        def initialize_plugin(plugin_group, plugin_dir):
            plugin = None
            plugins = self.settings.options(plugin_group)
            for path in plugin_dir.iterdir():
                if (path.is_dir() and not (path.name.startswith('_') or
                                           path.name.startswith('.'))):
                    plugin  = str(path)
                    if plugin not in plugins:
                        self.settings.set(plugin_group, plugin, value=None)
            if 'nexpy.' + plugin_group in entry_points():
                for entry in entry_points()['nexpy.'+plugin_group]:
                    plugin = entry.module
                    if plugin not in plugins:
                        self.settings.set(plugin_group, plugin, value=None)
        initialize_plugin('plugins', self.plugin_dir)
        initialize_plugin('readers', self.reader_dir)
        initialize_plugin('writers', self.writer_dir)

    def init_tree(self):
        """Initialize the NeXus tree used in the tree view."""
        global _tree
        self.tree = NXtree()
        _tree = self.tree

    def init_config(self):
        self.config.ConsoleWidget.input_sep = ''
        self.config.Completer.use_jedi = False

    def init_gui(self):
        """Initialize the GUI."""
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication(['nexpy'])
        self.app.setApplicationName('nexpy')
        sys.excepthook = report_exception
        try:
            if 'svg' in QtGui.QImageReader.supportedImageFormats():
                self.app.icon = resource_icon('NeXpy.svg')
            else:
                self.app.icon = resource_icon('NeXpy.png')
            QtWidgets.QApplication.setWindowIcon(self.app.icon)
            self.icon_pixmap = QtGui.QPixmap(
                self.app.icon.pixmap(QtCore.QSize(64, 64)))
        except Exception:
            self.icon_pixmap = None
        self.app.setStyleSheet("""QToolTip {color:darkblue;
                                            background-color:beige}""")
        self.window = MainWindow(self, self.tree, self.settings, self.config)
        self.window.log = self.log
        self.gc = NXGarbageCollector(self.window)
        global _mainwindow
        _mainwindow = self.window

    def init_shell(self, args):
        """Initialize imports in the shell."""
        global _shell
        _shell = self.window.user_ns
        s = ("import nexusformat.nexus as nx\n"
             "from nexusformat.nexus import NXgroup, NXfield, NXattr, NXlink\n"
             "from nexusformat.nexus import *\n"
             "import nexpy\n"
             "from nexpy.gui.plotview import NXPlotView")
        exec(s, self.window.user_ns)

        s = ""
        for _class in nxclasses:
            s = f"{_class}=nx.{_class}\n" + s
        exec(s, self.window.user_ns)

        default_script = ["import sys\n",
                          "import os\n",
                          "import h5py as h5\n",
                          "import numpy as np\n",
                          "import numpy.ma as ma\n",
                          "import scipy as sp\n",
                          "import matplotlib as mpl\n",
                          "from matplotlib import pylab, mlab, pyplot\n",
                          "plt = pyplot\n"]
        config_file = self.nexpy_dir / 'config.py'
        if not config_file.exists():
            with open(config_file, 'w') as f:
                f.writelines(default_script)
        with open(config_file) as f:
            s = f.readlines()
        try:
            exec('\n'.join(s), self.window.user_ns)
        except Exception:
            exec('\n'.join(default_script), self.window.user_ns)
        self.window.read_session()
        for i, filename in enumerate(args.filenames):
            try:
                self.window.load_file(filename)
            except Exception:
                pass
        if args.restore:
            self.window.restore_session()

    def init_colors(self):
        """Configure the coloring of the widget"""
        define_mode()

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
    def initialize(self, args, extra_args):
        if args.faulthandler:
            import faulthandler
            faulthandler.enable(all_threads=False)
        super().initialize(extra_args)
        self.init_dir()
        self.init_settings()
        self.init_log()
        self.init_plugins()
        self.init_tree()
        self.init_config()
        self.init_gui()
        self.init_shell(args)
        self.init_colors()
        self.init_signal()

    def start(self):
        super().start()

        # draw the window
        self.window.show()

        # Issue startup messages
        self.window.start()

        # Start the application main loop.
        self.app.exec()


# -----------------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------------


def main(args, extra_args):
    app = NXConsoleApp()
    app.initialize(args, extra_args)
    app.start()
    sys.exit(0)


if __name__ == '__main__':
    main()
