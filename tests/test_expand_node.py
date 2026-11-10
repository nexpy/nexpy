"""Tests for expanding a tree node that contains an unreadable link."""

from types import SimpleNamespace

import pytest
from nexusformat.nexus import (NeXusError, NXentry, NXgroup, NXlinkgroup,
                               NXroot)

from nexpy.gui.treeview import NXTreeView


def make_view(node):
    """Return a stand-in for a tree view whose only item is `node`."""
    item = SimpleNamespace(node=node)
    return SimpleNamespace(
        _model=SimpleNamespace(itemFromIndex=lambda index: item),
        proxymodel=SimpleNamespace(mapToSource=lambda index: index))


@pytest.fixture
def root(tmp_path, monkeypatch):
    """An unsaved root with a link to a file that cannot be found."""
    monkeypatch.chdir(tmp_path)
    root = NXroot(NXentry(NXgroup(name="data")))
    root["entry/data/metadata"] = NXlinkgroup(
        "/entry/raw", file="external.nxs", name="metadata")
    root["entry/data/other"] = NXgroup()
    return root


def test_unreadable_link_raises(root):
    with pytest.raises(NeXusError):
        root["entry/data/metadata"].entries


def test_expand_skips_unreadable_link(root):
    NXTreeView.expand_node(make_view(root["entry/data"]), 0)
