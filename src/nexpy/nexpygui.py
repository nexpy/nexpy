#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2020, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

def main():

    import argparse, os, sys, nexpy

    parser = argparse.ArgumentParser(description="Launch NeXpy")

    parser.add_argument('filename', nargs='?', 
                        help='NeXus file to open on launch (optional)')
    parser.add_argument('-v', '--version', action='version', 
                        version='%(prog)s v'+nexpy.__version__)
    args = parser.parse_args()
    from nexpy.gui.consoleapp import main
    main(args.filename)


if __name__ == '__main__':
    main()
