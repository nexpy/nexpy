import importlib
import os
import pkgutil
from collections import defaultdict

import pytest


def test_gui_import():
    os.environ['QT_API'] = 'pyqt5'
    try:
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


QT_MODULES = ('PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'qtpy')


def _get_qt_ancestors(cls):
    """Get all Qt classes in a class's MRO."""
    return {c for c in cls.__mro__
            if any(c.__module__.startswith(m) for m in QT_MODULES)}


def _find_diamond_inheritance(cls):
    """Return {qt_class: [bases]} for any Qt class inherited through multiple bases."""
    if len(cls.__bases__) < 2:
        return {}

    qt_to_bases = defaultdict(list)
    for base in cls.__bases__:
        for qt_cls in _get_qt_ancestors(base):
            qt_to_bases[qt_cls].append(base)

    return {qt_cls: bases for qt_cls, bases in qt_to_bases.items()
            if len(bases) >= 2}


def _iter_nexpy_gui_classes():
    """Yield all classes defined in nexpy.gui modules."""
    import nexpy.gui

    for _, name, _ in pkgutil.iter_modules(nexpy.gui.__path__):
        try:
            mod = importlib.import_module(f'nexpy.gui.{name}')
        except ImportError:
            continue

        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if isinstance(attr, type) and attr.__module__.startswith('nexpy.gui'):
                yield attr


def test_no_diamond_inheritance():
    """Ensure no Qt class is inherited through multiple base classes."""
    violations = [
        f'{cls.__name__}: {", ".join(c.__name__ for c in diamonds)}'
        for cls in _iter_nexpy_gui_classes()
        if (diamonds := _find_diamond_inheritance(cls))
    ]

    if violations:
        pytest.fail(
            f"Diamond inheritance found in {len(violations)} class(es):\n"
            + '\n'.join(f'  - {v}' for v in violations)
        )
