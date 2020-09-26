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

    parser.add_argument('filenames', nargs='*', 
                        help='NeXus file(s) to open on launch (optional)')
    parser.add_argument('-v', '--version', action='version', 
                        version='%(prog)s v'+nexpy.__version__)
    parser.add_argument('-f', '--faulthandler', action='store_true', 
                        help='enable faulthandler for system crashes')
    args, extra_args = parser.parse_known_args()
    from nexpy.gui.consoleapp import main
    main(args, extra_args)


if __name__ == '__main__':
    main()
