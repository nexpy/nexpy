import logging

import pytest
from nexusformat.nexus import NeXusError

from nexpy.gui import utils


class StubMessageBox:

    Ok = Warning = 0

    def __getattr__(self, name):
        return lambda *args, **kwargs: None

    def exec(self):
        return 0


@pytest.fixture(autouse=True)
def stub_message_box(monkeypatch):
    class QtWidgets:
        QMessageBox = StubMessageBox
    monkeypatch.setattr(utils, 'QtWidgets', QtWidgets)


def raise_type_error():
    return None * None


def test_format_traceback_returns_the_traceback():
    try:
        raise_type_error()
    except TypeError as error:
        text = utils.format_traceback(type(error), error, error.__traceback__)
    assert 'TypeError' in text
    assert 'raise_type_error' in text


def test_unexpected_exception_logs_traceback(caplog):
    with caplog.at_level(logging.INFO):
        try:
            raise_type_error()
        except Exception as error:
            utils.report_error('Orienting Lattice', error)
    record, = caplog.records
    assert record.levelno == logging.ERROR
    assert 'TypeError: Orienting Lattice' in record.getMessage()
    assert 'Traceback' in record.getMessage()
    assert 'raise_type_error' in record.getMessage()


def test_nexus_error_logs_message_only(caplog):
    with caplog.at_level(logging.INFO):
        utils.report_error('Opening File', NeXusError('No file selected'))
    record, = caplog.records
    assert record.levelno == logging.WARNING
    assert record.getMessage() == ('NeXusError: Opening File: '
                                   'No file selected')


def test_string_error_is_logged(caplog):
    with caplog.at_level(logging.INFO):
        utils.report_error('Choosing Files', 'Files not selected')
    record, = caplog.records
    assert record.levelno == logging.WARNING
    assert 'Files not selected' in record.getMessage()
