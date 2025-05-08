#!/usr/bin/env python
# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
import argparse
import sys
from pathlib import Path

import nexpy


def main():

    parser = argparse.ArgumentParser(description="Launch NeXpy")

    parser.add_argument('filenames', nargs='*',
                        help='NeXus file(s) to open on launch (optional)')
    parser.add_argument('-v', '--version', action='version',
                        version='%(prog)s v'+nexpy.__version__)
    parser.add_argument('-r', '--restore', action='store_true',
                        help='open files from previous session')
    parser.add_argument('-f', '--faulthandler', action='store_true',
                        help='enable faulthandler for system crashes')
    args = parser.parse_args()

    for i, f in enumerate(args.filenames):
        args.filenames[i] = f"{Path(f).resolve()}"

    if sys.platform == 'darwin':
        from nexpy.gui.utils import run_pythonw
        run_pythonw(__file__)

    from nexpy.gui.consoleapp import main
    main(args)


if __name__ == '__main__':
    main()
