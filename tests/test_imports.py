"""Import tests to verify all modules can be loaded."""


def test_gui_import():
    """Test that all GUI modules can be imported."""
    import nexpy.gui.pyqt
    import nexpy.gui.consoleapp
    import nexpy.gui.dialogs
    import nexpy.gui.fitdialogs
    import nexpy.gui.importdialog
    import nexpy.gui.mainwindow
    import nexpy.gui.plotview
    import nexpy.gui.scripteditor
    import nexpy.gui.treeview
    import nexpy.gui.utils
    import nexpy.gui.widgets


def test_reader_import():
    """Test that all reader modules can be imported."""
    import nexpy.gui.pyqt
    import nexpy.readers.readspec
    import nexpy.readers.readstack
    import nexpy.readers.readtiff
    import nexpy.readers.readtxt
