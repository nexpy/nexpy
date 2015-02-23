#!/bin/sh
./setup.py bdist_rpm --requires="h5py,numpy >= 1.6.0,scipy,python-ipython >= 1.1.0,python-matplotlib >= 1.2.0,python-pyside >= 1.1.0"
################################################################################
# python-pyside v1.1.0 rpm has a bug in it where it does not supply the egg-info
# that dist-utils looks for. There is a workaround mentioned in
# https://github.com/nvbn/everpad/issues/401#issuecomment-35834335 which is to
# spoof the system with a fake file in
# /usr/lib/python2.7/dist-packages/PySide-1.1.0-py2.7.egg-info
# or
# /usr/lib/python2.7/site-packages/PySide-1.1.0-py2.7.egg-info
# depending on which install location exists. It appears that v1.2.0 contains
# the missing file.
################################################################################

