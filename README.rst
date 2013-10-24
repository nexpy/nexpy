Installation
============
The NeXpy source code can be downloaded from the Git repository at 
https://github.com/nexpy/nexpy::

    $ git clone http://github.com/nexpy/nexpy.git

To install in the standard Python location::

    $ cd nexpy
    $ python setup.py install

To install in an alternate location::

    $ python setup.py install --prefix=/path/to/installation/dir

Required Libraries
==================
Python Command-Line API
-----------------------
NeXpy provides a Python interface to the `NeXus C API
<http://download.nexusformat.org/doc/html/napi.html>`_, which provides a wrapper
for three separate file formats, HDF5, HDF4, and XML. It is necessary
therefore to install the libraries for each format that you anticipate using. If
you install NeXus from source, the configure script will determine what
libraries are available (or you can choose which to include using configure
switches). HDF4 is no longer recommended for new files but may be needed to 
access existing data repositories. If you only intend to utilize the Python API 
from the command-line, the only other required library is `Numpy
<http://numpy.scipy.org>`_.

=================  =================================================
Library            URL
=================  =================================================
nexus              http://www.nexusformat.org/
hdf5               http://www.hdfgroup.org/HDF5/
hdf4               http://www.hdfgroup.org/products/hdf4/
mxml               http://www.minixml.org/
numpy              http://numpy.scipy.org/
=================  =================================================

NeXpy GUI
---------
The GUI is built using Qt, and should work with either PyQt, which can be 
installed from the `PyQt website <http://www.riverbankcomputing.co.uk/>`_, or 
`PySide <http://www.pyside.org/>`_ (although all testing has been performed 
using PySide).

The GUI includes an `iPython shell <http://ipython.org/>`_ and a `Matplotlib
plotting pane <http://matplotlib.sourceforge.net>`_. The iPython shell is
embedded in the Qt GUI using an implementation of their QtConsole.
          
=================  =================================================
Library            URL
=================  =================================================
PySide v1.1.0      http://www.pyside.org/
iPython v0.13      http://ipython.org/
matplotlib v1.1.0  http://matplotlib.sourceforge.net/
=================  =================================================

Most of these packages are included in the `Enthought Python Distribution v7.3 
<http://www.enthought.com>`_ or within Enthought's `Canopy Application
<https://www.enthought.com/products/canopy/>`_.

Additional Packages
-------------------
Additional functionality is provided by other external Python packages. 
Least-squares fitting requires Matt Newville's least-squares fitting package, 
`lmfit-py <http://newville.github.io/lmfit-py>`_. Importers may also require 
libraries to read the imported files in their native format, *e.g.*, `PySpec 
<http://pyspec.sourceforge.net>`_ for reading SPEC files and `PyLibTiff
<http://code.google.com/p/pylibtiff/>`_ for reading float*32 TIFF files (the
standard Python Imaging Library can read conventional TIFF files).

=================  =================================================
Library            URL
=================  =================================================
lmfit              http://newville.github.io/lmfit-py/
pyspec             http://pyspec.sourceforge.net/
pylibtiff          http://code.google.com/p/pylibtiff/
=================  =================================================

Installation Issues
-------------------
NeXpy utilizes the python wrapper to the NeXus C API distributed with the
standard NeXus distribution. This wrapper needs the location of the libNeXus
precompiled binary. It looks in the following places in order:

===================================  =========================
Location                             Operating System
===================================  =========================
os.environ['NEXUSLIB']               All
os.environ['NEXUSDIR']\bin           Windows
os.environ['LD_LIBRARY_PATH']        Unix
os.environ['DYLD_LIBRARY_PATH']      Darwin (*i.e.*, Mac OS X)
PREFIX/libm                          Unix and Darwin
/usr/local/lib                       Unix and Darwin
/usr/lib                             Unix and Darwin
===================================  =========================

* On Windows it looks for one of libNeXus.dll or libNeXus-0.dll.
* On OS X it looks for libNeXus.dylib
* On Unix it looks for libNeXus.so

.. note:: NEXUSDIR defaults to 'C:\\Program Files\\NeXus Data Format'. PREFIX 
          defaults to /usr/local, but is replaced by the value of the prefix 
          switch used when invoking 'configure' if NeXus is installed from 
          source. The import will raise an OSError exception if the library 
          wasn't found or couldn't be loaded. Note that on Windows in particular 
          this may be because the supporting HDF5 dlls were not available in the 
          usual places. If you are extracting the NeXus library from a bundle at 
          runtime, set os.environ['NEXUSLIB'] to the path where it is extracted 
          before the first import of NeXpy.
