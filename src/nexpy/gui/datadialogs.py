# -----------------------------------------------------------------------------
# Copyright (c) 2025, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import warnings

from .dialogs import *

warnings.warn(
    "The module 'nexpy.gui.datadialogs' is deprecated and will be removed " +
    "in a future release. Please use 'nexpy.gui.dialogs' instead.",
    DeprecationWarning,
    stacklevel=2
)
