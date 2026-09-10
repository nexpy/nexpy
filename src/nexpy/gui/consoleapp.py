# -----------------------------------------------------------------------------
# Copyright (c) 2013-2026, NeXpy Development Team.
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
from pathlib import Path

from h5py import __version__ as h5py_version
from IPython import __version__ as ipython_version
from matplotlib import __version__ as mpl_version
from nexusformat.nexus import NXroot, nxclasses, nxversion
from qtconsole.qtconsoleapp import JupyterQtConsoleApp

from .. import __version__ as nexpy_version
from .mainwindow import MainWindow
from .pyqt import QtCore, QtGui, QtVersion, QtWidgets
from .treeview import NXtree
from .utils import (NXConfigParser, NXGarbageCollector, NXLogger, define_mode,
                    display_message, entry_points, initialize_settings,
                    list_directory, report_exception, resource_icon,
                    timestamp_age)


_mainwindow = None


class NXConsoleApp(JupyterQtConsoleApp):

    def init_dir(self):
        """
        Initialize the NeXpy directory.

        This method creates the NeXpy directory tree and scratch file if
        they do not already exist. The NeXpy directory is created in the
        user's home directory as ~/.nexpy. If the user does not have
        write access to the home directory, a temporary directory is
        created instead.

        The directories are created without checking permissions in
        advance, because `os.access` does not reflect access control
        lists on Windows and can report a directory as writable when it
        is not.
        """
        subdirectories = ['backups', 'models', 'plugins', 'readers',
                          'scripts']

        def make_directories(nexpy_dir):
            """Create the directory tree, returning True if successful."""
            try:
                nexpy_dir.mkdir(parents=True, exist_ok=True)
                for subdirectory in subdirectories:
                    (nexpy_dir / subdirectory).mkdir(exist_ok=True)
            except OSError:
                return False
            return True

        nexpy_dir = Path.home() / '.nexpy'
        self.dir_warning = None
        if not make_directories(nexpy_dir):
            temporary_dir = Path(tempfile.mkdtemp())
            self.dir_warning = (
                f"Unable to use '{nexpy_dir}'. NeXpy settings, scripts, and "
                f"backups will be stored in '{temporary_dir}' and will be "
                "lost when this session ends.")
            if not make_directories(temporary_dir):
                raise OSError(f"Unable to create the NeXpy directory tree in "
                              f"either '{nexpy_dir}' or '{temporary_dir}'")
            nexpy_dir = temporary_dir
        self.nexpy_dir = nexpy_dir
        self.backup_dir = self.nexpy_dir / 'backups'
        self.model_dir = self.nexpy_dir / 'models'
        self.plugin_dir = self.nexpy_dir / 'plugins'
        self.reader_dir = self.nexpy_dir / 'readers'
        self.script_dir = self.nexpy_dir / 'scripts'
        self.scratch_file = self.nexpy_dir / 'w0.nxs'
        if not self.scratch_file.exists():
            try:
                NXroot().save(self.scratch_file)
            except Exception as error:
                self.dir_warning = (
                    f"Unable to create the scratch file "
                    f"'{self.scratch_file}': {error}")

    def init_settings(self):
        """
        Initialize NeXpy settings.

        This method initializes the NeXpy settings file located at
        ~/.nexpy/settings.ini. If the file does not exist, it is
        created. Any backups that are older than 5 days are removed.
        """
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
        """
        Initialize the NeXpy log file.

        The log file is named 'nexpy.log' and is located in the NeXpy
        home directory. The log file is rotated every 50KB. The log
        level is set to 'INFO' unless the environment variable NEXPY_LOG
        is set to 'DEBUG', 'INFO', 'WARNING', 'ERROR', or 'CRITICAL'.
        """
        log_file = self.nexpy_dir / 'nexpy.log'
        try:
            handler = logging.handlers.RotatingFileHandler(log_file,
                                                           maxBytes=50000,
                                                           backupCount=5)
        except OSError as error:
            handler = logging.StreamHandler()
            self.log_warning = (f"Unable to open the log file '{log_file}': "
                                f"{error}")
        else:
            self.log_warning = None
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S')
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
        logging.info('Python ' + sys.version)
        logging.info(sys.executable)
        logging.info(QtVersion)
        logging.info('IPython v' + ipython_version)
        logging.info('Matplotlib v' + mpl_version)
        logging.info('h5py v' + h5py_version)
        logging.info('NeXpy v' + nexpy_version)
        logging.info('nexusformat v' + nxversion)
        if self.log_warning:
            logging.warning(self.log_warning)
        if self.dir_warning:
            logging.warning(self.dir_warning)
        sys.stdout = sys.stderr = NXLogger()

    def init_plugins(self):
        """
        Initialize plugins.

        This method looks for plugins stored as files in the NeXpy
        directory or registered as entry points, and adds them to the
        list of plugins in the NeXpy settings file. These will be added
        as additional menu items if enabled by the Manage Plugins
        dialog.
        """
        eps = entry_points()
        plugin = None
        plugins = self.settings.options('plugins')
        for path in list_directory(self.plugin_dir):
            if (path.is_dir() and not (path.name.startswith('_') or
                                       path.name.startswith('.'))):
                plugin  = str(path)
                if plugin not in plugins:
                    self.settings.set('plugins', plugin, value=None)
        group_name = 'nexpy.plugins'
        for entry in eps.select(group=group_name):
            plugin = entry.module
            if plugin not in plugins:
                self.settings.set('plugins', plugin, value=None)

    def init_tree(self):
        """Initialize the root element of the NeXpy tree view."""
        self.tree = NXtree()

    def init_config(self):
        """Initialize the configuration options for the NeXpy console."""
        self.config.ConsoleWidget.input_sep = ''
        self.config.Completer.use_jedi = False
        self.config.RichJupyterWidget.banner = (
            f"Python {sys.version}\n"
            f"GUI: {QtVersion} | Shell: IPython v{ipython_version} | "
            f"Graphics: Matplotlib v{mpl_version}\n"
            f"NeXpy v{nexpy_version} | nexusformat v{nxversion} "
            f"| h5py v{h5py_version}")
        self.config.RichJupyterWidget.include_other_output = False
        self.config.InteractiveShell.banner1 = ""
        self.config.InteractiveShell.banner2 = ""
        self.config.InteractiveShell.enable_tip = False

    def init_gui(self):
        """
        Initialize the NeXpy graphical user interface.

        This creates a QApplication instance if it does not exist, sets
        the application name to 'nexpy', and sets the exception hook to
        report exceptions in the log file. A MainWindow is created,
        along with a garbage collector to periodically collect any NeXus
        objects that are no longer referenced.
        """
        self.app = QtWidgets.QApplication.instance()
        if self.app is None:
            self.app = QtWidgets.QApplication(['nexpy'])
        self.app.setApplicationName('nexpy')
        sys.excepthook = report_exception
        try:
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
        try:
            if not config_file.exists():
                with open(config_file, 'w') as f:
                    f.writelines(default_script)
            with open(config_file) as f:
                s = f.readlines()
        except OSError as error:
            logging.warning(f"Unable to read the startup script "
                            f"'{config_file}': {error}")
            s = default_script
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

    def init_mode(self):
        """Configure the dark/light mode of the NeXpy widgets."""
        define_mode()

    def init_signal(self):
        """
        Initialize the signal handler for the application.

        The signal handler is configured to start a timer, so that the
        interpreter will be given a chance to run every 200
        milliseconds. This is necessary because the application could be
        blocked waiting for a real Qt event to occur, and the signal
        handler needs to have a chance to run.

        This code is based on the following code from Stack Overflow:
        http://stackoverflow.com/q/4938723/938949
        """
        signal.signal(signal.SIGINT, lambda sig, frame: self.exit(-2))
        timer = QtCore.QTimer()
        timer.timeout.connect(lambda: None)
        timer.start(200)
        self._sigint_timer = timer

    def initialize(self, args):
        """
        Initialize the NeXpy application.

        This method is called by JupyterConsoleApp to initialize the
        application. It is responsible for initializing the configuration,
        logging, plugins, tree view, shell and graphical user interface.

        Parameters
        ----------
        args : argparse.Namespace
            The parsed command line arguments.
        """
        if args.faulthandler:
            import faulthandler
            faulthandler.enable(all_threads=False)
        self.init_dir()
        self.init_settings()
        self.init_log()
        self.init_plugins()
        self.init_tree()
        self.init_config()
        self.init_gui()
        self.init_shell(args)
        self.init_mode()
        self.init_signal()
        if self.dir_warning:
            display_message("NeXpy directory is not writable",
                            self.dir_warning)

    def start(self):
        """
        Start the application.

        This method starts the application main loop. It is called by
        JupyterConsoleApp after the application has been initialized.

        This method is responsible for drawing the window, issuing
        startup messages, and starting the application main loop.
        """
        self.window.show()
        self.window.start()
        self.app.exec()


def main(args):
    """
    Main entry point for NeXpy console application.

    Parameters
    ----------
    args : list of str
        List of command line arguments.
    """
    app = NXConsoleApp()
    app.initialize(args)
    app.start()
    sys.exit(0)


if __name__ == '__main__':
    main()
