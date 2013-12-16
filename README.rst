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

.. note:: The latest updates make NeXpy compatible with iPython 1.1.0 and 
          removes the dependency on PyZMQ. If you require a version that is 
          compatible with iPython 0.13, please clone the ipython-0.13 branch
          (https://github.com/nexpy/nexpy/tree/ipython-0.13).

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

Semantic Versioning
-------------------
With the release of v0.1.0, NeXpy will be using `Semantic Versioning 
<http://semver.org/spec/v2.0.0.html>`_.

Acknowledgements
----------------
The `NeXus format <http://www.nexusformat.org>`_ for neutron, x-ray and muon 
data is developed by an international collaboration under the supervision of the 
`NeXus Interational Advisory Committee <http://wiki.nexusformat.org/NIAC>`_. The 
Python tree API used in NeXpy was originally developed by Paul Kienzle, who
also wrote the standard Python interface to the NeXus C-API. The original 
version of NeXpy was initially developed by Boyana Norris, Jason Sarich, and 
Daniel Lowell, using wxPython.
