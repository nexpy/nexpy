Installation
============
The NeXpy source code can be downloaded from the Git repository at 
https://github.com/nexpy/nexpy::

    $ git clone http://github.com/nexpy/nexpy.git

To install in the standard Python location::

    $ cd nexpy
    $ python setup.py install

To install in an alternate location::

    $ python setup.py install --prefix=/path/to/insallation/dir

Required Libraries
==================

=================  =================================================
Library               URL
=================  =================================================
PySide v1.1.0         http://www.pyside.org/
iPython v0.13         http://ipython.org/
numpy,scipy           http://numpy.scipy.org
matplotlib v1.1.0     http://matplotlib.sourceforge.net
hdf5                  http://www.hdfgroup.org
mxml                  http://www.minixml.org (XML NeXus files only)
nexus                 http://www.nexusformat.org
lmfit                 http://newville.github.io/lmfit-py (Fitting only)
pyspec                http://pyspec.sourceforge.net (SPEC reader only)
=================  =================================================

The following environment variables may need to be set

NEXUSLIB
    /point/to/lib/libNeXus.so
PYTHONPATH
    must include paths to ipython,numpy,scipy,matplotlib if installed in a 
    nonstandard place

All of the above are included in the Enthought Python Distribution v7.3.

PyQt4 should also work instead of PySide, but it has not been tested. NeXpy 
automatically checks for which PyQt variant is available (PySide or PyQt4 - 
not PyQt). 
