#!/usr/bin/env python
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013-2014, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------


def main():
    import os, sys

    import matplotlib
    matplotlib.use('Qt4Agg')

    sys.path.insert(0, os.path.abspath(os.path.join('..')))
    from nexpy.gui.consoleapp import main
    main()


if __name__ == '__main__':
    main()
