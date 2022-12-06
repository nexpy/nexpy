import os

import pytest


def test_api_imports():
    try:
        import nexpy.api.frills.fit
    except ImportError as error:
        pytest.fail(str(error))


def test_gui_import():
    os.environ['QT_API'] = 'pyqt5'
    try:
        import nexpy.gui.pyqt
        import nexpy.gui.consoleapp
        import nexpy.gui.datadialogs
        import nexpy.gui.fitdialogs
        import nexpy.gui.importdialog
        import nexpy.gui.mainwindow
        import nexpy.gui.plotview
        import nexpy.gui.scripteditor
        import nexpy.gui.treeview
        import nexpy.gui.utils
        import nexpy.gui.widgets
    except ImportError as error:
        pytest.fail(str(error))


def test_reader_import():
    os.environ['QT_API'] = 'pyqt5'
    try:
        import nexpy.gui.pyqt
        import nexpy.readers.readspec
        import nexpy.readers.readstack
        import nexpy.readers.readtiff
        import nexpy.readers.readtxt
    except ImportError as error:
        pytest.fail(str(error))
