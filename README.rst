Installation
============
Released versions of NeXpy are available on `PyPI 
<https://pypi.python.org/pypi/NeXpy/>`_. If you have the `Python Setup Tools 
<https://pypi.python.org/pypi/setuptools>`_ installed, then you can install 
using either::

    $ pip install nexpy

or:: 

    $ easy_install nexpy 

The latest development versions of NeXpy can be downloaded from the `NeXpy Git 
repository <https://github.com/nexpy/nexpy>`_::

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
The current version of NeXpy uses h5py to read and write NeXus files because
of its ability to handle large data files. There is currently no dependency 
on the `NeXus C API <http://download.nexusformat.org/doc/html/napi.html>`_. 
This also means that the current version cannot read and write HDF4 or XML 
NeXus files, although this functionality will be restored in a future version.
If you only intend to utilize the Python API from the command-line, the only 
other required library is `Numpy <http://numpy.scipy.org>`_.

=================  =================================================
Library            URL
=================  =================================================
h5py               http://www.h5py.org
numpy              http://numpy.scipy.org/
=================  =================================================

.. note:: If you need to read HDF4 or XML files now, please clone the 
          old-master branch (https://github.com/nexpy/nexpy/tree/old-master).

NeXpy GUI
---------
The GUI is built using the `PySide <http://www.pyside.org/>`_ variant of Qt and 
includes an `iPython shell <http://ipython.org/>`_ and a `Matplotlib
plotting pane <http://matplotlib.sourceforge.net>`_. The iPython shell is
embedded in the Qt GUI using an implementation of their QtConsole.
          
=================  =================================================
Library            URL
=================  =================================================
PySide v1.1.0      http://www.pyside.org/
iPython v1.1.0     http://ipython.org/
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
<http://pyspec.sourceforge.net>`_ for reading SPEC files. 

From v0.1.2, a new package for reading floating point TIFF files, tifffile, 
written by `Christoph Gohlke <http://www.lfd.uci.edu/~gohlke/>`_, has been 
incorporated into the NeXpy distribution.

=================  =================================================
Library            URL
=================  =================================================
lmfit              http://newville.github.io/lmfit-py/
pyspec             http://pyspec.sourceforge.net/
=================  =================================================

.. note:: NeXpy should still run without these additional packages, but invoking
          the relevant menu items will trigger an exception. 

Semantic Versioning
-------------------
With the release of v0.1.0, NeXpy is using `Semantic Versioning 
<http://semver.org/spec/v2.0.0.html>`_.

Acknowledgements
----------------
The `NeXus format <http://www.nexusformat.org>`_ for neutron, x-ray and muon 
data is developed by an international collaboration under the supervision of the 
`NeXus International Advisory Committee <http://wiki.nexusformat.org/NIAC>`_. 
The Python tree API used in NeXpy was originally developed by Paul Kienzle, who
also wrote the standard Python interface to the NeXus C-API. The original 
version of NeXpy was initially developed by Boyana Norris, Jason Sarich, and 
Daniel Lowell, and Ray Osborn using wxPython, and formed the inspiration
for the current PySide version.
