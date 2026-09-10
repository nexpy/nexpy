"""Tests for graceful handling of inaccessible files and directories.

These are regression tests for failures reported on Windows, where
directory listings, file removals, and directory creation can raise
PermissionError in situations that do not arise on Unix.
"""

from pathlib import Path

import pytest

from nexpy.gui.utils import get_mtime, list_directory, modification_time


def test_list_directory_returns_contents(tmp_path):
    (tmp_path / 'b.py').touch()
    (tmp_path / 'a.py').touch()
    (tmp_path / 'c.txt').touch()

    assert [p.name for p in list_directory(tmp_path)] == ['a.py', 'b.py',
                                                          'c.txt']
    assert [p.name for p in list_directory(tmp_path, pattern='*.py')] == [
        'a.py', 'b.py']


def test_list_directory_missing_directory(tmp_path):
    assert list_directory(tmp_path / 'nonexistent') == []


def test_list_directory_permission_error(tmp_path, monkeypatch):
    """An unreadable directory yields an empty list, not an exception."""
    def unreadable(self):
        raise PermissionError(13, 'Access is denied')

    monkeypatch.setattr(Path, 'iterdir', unreadable)
    assert list_directory(tmp_path) == []


def test_list_directory_glob_permission_error(tmp_path, monkeypatch):
    def unreadable(self, pattern):
        raise PermissionError(13, 'Access is denied')

    monkeypatch.setattr(Path, 'glob', unreadable)
    assert list_directory(tmp_path, pattern='*.py') == []


def test_get_mtime_permission_error(tmp_path, monkeypatch):
    """get_mtime is used as a sort key, so it must never raise."""
    def inaccessible(self, **kwargs):
        raise PermissionError(13, 'Access is denied')

    monkeypatch.setattr(Path, 'stat', inaccessible)
    assert get_mtime(tmp_path / 'file.lock') == 0.0
    assert modification_time(tmp_path / 'file.lock') == ''


def test_init_dir_falls_back_to_temporary_directory(tmp_path, monkeypatch):
    """An unwritable home directory must not abort the launch.

    The fallback previously returned a string rather than a Path, so it
    raised a TypeError as soon as a subdirectory was appended.
    """
    from nexpy.gui.consoleapp import NXConsoleApp

    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path / 'home'))

    real_mkdir = Path.mkdir

    def refuse_home(self, *args, **kwargs):
        if 'home' in self.parts:
            raise PermissionError(13, 'Access is denied')
        return real_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, 'mkdir', refuse_home)

    app = NXConsoleApp.__new__(NXConsoleApp)
    app.init_dir()

    assert isinstance(app.nexpy_dir, Path)
    assert 'home' not in app.nexpy_dir.parts
    assert app.dir_warning is not None
    for directory in (app.backup_dir, app.model_dir, app.plugin_dir,
                      app.reader_dir, app.script_dir):
        assert isinstance(directory, Path)
        assert directory.is_dir()


def test_init_dir_uses_home_when_writable(tmp_path, monkeypatch):
    from nexpy.gui.consoleapp import NXConsoleApp

    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))

    app = NXConsoleApp.__new__(NXConsoleApp)
    app.init_dir()

    assert app.nexpy_dir == tmp_path / '.nexpy'
    assert app.dir_warning is None
    assert app.scratch_file.exists()


@pytest.mark.parametrize('subdirectory', ['backups', 'models', 'plugins',
                                          'readers', 'scripts'])
def test_init_dir_creates_subdirectories(tmp_path, monkeypatch, subdirectory):
    from nexpy.gui.consoleapp import NXConsoleApp

    monkeypatch.setattr(Path, 'home', staticmethod(lambda: tmp_path))

    app = NXConsoleApp.__new__(NXConsoleApp)
    app.init_dir()

    assert (app.nexpy_dir / subdirectory).is_dir()


@pytest.fixture(scope='module')
def qapp():
    """A headless QApplication, required to build the script menus."""
    import os
    os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
    from nexpy.gui.pyqt import QtWidgets
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


@pytest.fixture
def script_menu_host(qapp):
    """A minimal widget providing the script-menu methods of MainWindow."""
    from nexpy.gui.mainwindow import MainWindow
    from nexpy.gui.pyqt import QtWidgets

    class ScriptMenuHost(QtWidgets.QWidget):
        max_script_depth = MainWindow.max_script_depth
        add_script_directory = MainWindow.add_script_directory
        add_script_action = MainWindow.add_script_action

        def __init__(self):
            super().__init__()
            self.scripts = {}

        def add_menu_action(self, menu, action, defer_shortcut):
            menu.addAction(action)

        def open_script_file(self):
            pass

    return ScriptMenuHost()


def test_add_script_directory_finds_scripts(script_menu_host, tmp_path):
    from nexpy.gui.pyqt import QtWidgets

    (tmp_path / 'one.py').touch()
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'sub' / 'two.py').touch()

    menu = QtWidgets.QMenu('Scripts', script_menu_host)
    script_menu_host.add_script_directory(tmp_path, menu)

    names = sorted(Path(f).name for _, f in script_menu_host.scripts.values())
    assert names == ['one.py', 'two.py']


def test_add_script_directory_survives_symlink_loop(script_menu_host,
                                                    tmp_path):
    """A directory linking back to an ancestor must not recurse forever.

    This reproduces the Windows 'AppData\\Local\\Application Data'
    junction, which points back at its own parent.
    """
    from nexpy.gui.pyqt import QtWidgets

    (tmp_path / 'script.py').touch()
    loop = tmp_path / 'loop'
    try:
        loop.symlink_to(tmp_path, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip('symbolic links are not supported on this platform')

    menu = QtWidgets.QMenu('Scripts', script_menu_host)
    script_menu_host.add_script_directory(tmp_path, menu)

    names = [Path(f).name for _, f in script_menu_host.scripts.values()]
    assert names == ['script.py']


def test_add_script_directory_unreadable(script_menu_host, tmp_path,
                                         monkeypatch):
    from nexpy.gui.pyqt import QtWidgets

    def unreadable(self):
        raise PermissionError(13, 'Access is denied')

    monkeypatch.setattr(Path, 'iterdir', unreadable)

    menu = QtWidgets.QMenu('Scripts', script_menu_host)
    script_menu_host.add_script_directory(tmp_path, menu)

    assert not menu.isEnabled()
    assert script_menu_host.scripts == {}


def test_list_directory_missing_is_silent(tmp_path, caplog):
    """A missing directory is normal and must not log a warning."""
    with caplog.at_level('WARNING'):
        assert list_directory(tmp_path / 'nonexistent') == []
    assert caplog.records == []


def test_list_directory_unreadable_logs_warning(tmp_path, monkeypatch,
                                                caplog):
    def unreadable(self):
        raise PermissionError(13, 'Access is denied')

    monkeypatch.setattr(Path, 'iterdir', unreadable)
    with caplog.at_level('WARNING'):
        assert list_directory(tmp_path) == []
    assert len(caplog.records) == 1
    assert 'Access is denied' in caplog.records[0].getMessage()


@pytest.mark.parametrize('directory', [None, '', '   '])
def test_add_script_directory_ignores_unset_directory(script_menu_host,
                                                      tmp_path, monkeypatch,
                                                      directory):
    """An unset script directory must not be read as the working directory.

    Path('') is the current working directory, so a blank
    'scriptdirectory' setting previously caused the whole tree below the
    launch directory to be scanned recursively. On Windows that reaches
    'AppData\\Local\\Application Data', which raises
    PermissionError: [WinError 5].
    """
    from nexpy.gui.pyqt import QtWidgets

    (tmp_path / 'stray.py').touch()
    monkeypatch.chdir(tmp_path)

    menu = QtWidgets.QMenu('Public Scripts', script_menu_host)
    script_menu_host.add_script_directory(directory, menu)

    assert not menu.isEnabled()
    assert script_menu_host.scripts == {}


def test_initialize_settings_repairs_blank_script_directory(tmp_path,
                                                            monkeypatch):
    """A blank script directory in an existing settings file is reset."""
    from nexpy.gui.utils import NXConfigParser, initialize_settings

    monkeypatch.delenv('NX_SCRIPTDIRECTORY', raising=False)
    settings_file = tmp_path / 'settings.ini'
    settings_file.write_text('[settings]\nscriptdirectory = \n')

    settings = NXConfigParser(settings_file)
    assert settings.get('settings', 'scriptdirectory') == ''

    initialize_settings(settings)

    assert settings.get('settings', 'scriptdirectory') is None
