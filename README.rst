Installation
============
Released versions of NeXpy are available on `PyPI 
<https://pypi.python.org/pypi/NeXpy/>`_ and as a `Conda installation 
<https://anaconda.org/nexpy>`_. 

If you have the `Python Setup Tools <https://pypi.python.org/pypi/setuptools>`_ 
installed, then you can install using either::

    $ pip install nexpy

or:: 

    $ easy_install nexpy 

If you have an Anaconda installation, use::

    $ conda install -c https://conda.anaconda.org/nexpy nexpy

If you have trouble with the pip or easy_install installations, you can install
the package from the source code either by downloading one of the 
`Github releases <https://github.com/nexpy/nexpy/releases>`_ or by cloning the
latest development version in the `NeXpy Git 
repository <https://github.com/nexpy/nexpy>`_::

    $ git clone https://github.com/nexpy/nexpy.git

You can then install NeXpy by changing to the source directory and typing::

    $ python setup.py install

To install in an alternate location::

    $ python setup.py install --prefix=/path/to/installation/dir

As of v0.6.0, the Python API for reading and writing NeXus files is in a 
separate package, `nexusformat <https://github.com/nexpy/nexusformat>`_, which 
is also available on `PyPI <https://pypi.python.org/pypi/nexusformat/>`_ and 
will be automatically installed as a NeXpy dependency if you use pip. 

If the NeXpy GUI is not required, the package may be used in a regular Python
shell. It may be installed using:: 

    $ pip install nexusformat

or:: 

    $ easy_install nexusformat 

or::

    $ conda install -c https://conda.anaconda.org/nexpy nexusformat

The package can also be installed from the source code using the setup commands
described above. The source code is available either by downloading one of the 
`Github releases <https://github.com/nexpy/nexusformat/releases>`_ or by cloning 
the latest development version in the `NeXpy Git repository 
<https://github.com/nexpy/nexusformat>`_::

    $ git clone https://github.com/nexpy/nexusformat.git

Required Libraries
==================
Python Command-Line API
-----------------------
The current version of NeXpy uses h5py to read and write NeXus files because
of its ability to handle large data files. There is therefore no dependency 
on the `NeXus C API <http://download.nexusformat.org/doc/html/napi.html>`_. 
This also means that the current version cannot read and write HDF4 or XML 
NeXus files.

If you only intend to utilize the Python API from the command-line, the only 
other required library is `Numpy <http://numpy.scipy.org>`_.

=================  =================================================
Library            URL
=================  =================================================
nexusformat        https://github.com/nexpy/nexusformat
h5py               http://www.h5py.org
numpy              http://numpy.scipy.org/
=================  =================================================

.. note:: If you need to read HDF4 or XML files now, please clone the 
          old-master branch (https://github.com/nexpy/nexpy/tree/old-master).

NeXpy GUI
---------
The GUI is built using the PyQt. The latest version supports PyQt4, PySide, and
with v0.10.0, PyQt5, and should load whichever library it finds. None are 
listed as a dependency but one or other must be installed. PyQt5 is included
in the 
`Anaconda default distribution <https://store.continuum.io/cshop/anaconda/>`_ 
while PySide is included in the `Enthought Python Distribution
<http://www.enthought.com>`_ or within Enthought's `Canopy Application
<https://www.enthought.com/products/canopy/>`_.

The GUI includes an `IPython shell <http://ipython.org/>`_ and a `Matplotlib
plotting pane <http://matplotlib.sourceforge.net>`_. The IPython shell is
embedded in the Qt GUI using an implementation based on the newly-released
Jupyter QtConsole, which has replaced the old IPython QtConsole.

=================  =================================================
Library            URL
=================  =================================================
jupyter            http://jupyter.org/
IPython v4.0.0     http://ipython.org/
matplotlib v1.4.0  http://matplotlib.sourceforge.net/
pillow             https://pillow.readthedocs.io/
ansi2html          https://pypi.python.org/pypi/ansi2html/
=================  =================================================

.. warning:: Some people have reported that NeXpy crashes on launch on some
             Linux systems. We believe that this may be due to both PyQt4 and
             PyQt5 being installed, although that doesn't cause a problem on 
             all systems. If NeXpy crashes on launch, please try setting the
             environment variable QT_API to either 'pyqt', for the PyQt4 
             library, 'pyqt5' for the PyQt5 library, or 'pyside', for the 
             PySide library, depending on what you have installed, *e.g.*, in 
             BASH, type ::

                 export QT_API=pyqt

.. note:: As of v0.10.3, `ansi2html <https://pypi.python.org/pypi/ansi2html/>`_ 
          has been added as a dependency, since colorized tracebacks are now
          produced by uncaught GUI exceptions and displayed in dialog boxes and
          stored in the log files. 

.. seealso:: If you are having problems linking to the PySide library, you may
             need to run the PySide post-installation script after installing
             PySide, *i.e.*, ``python pyside_postinstall.py -install``. See 
             `this issue <https://github.com/nexpy/nexpy/issues/29>`_.

Additional Packages
-------------------
Additional functionality is provided by other external Python packages. 
Least-squares fitting requires Matt Newville's least-squares fitting package, 
`lmfit-py <http://newville.github.io/lmfit-py>`_. Importers may also require 
libraries to read the imported files in their native format, *e.g.*, `spec2nexus 
<http://spec2nexus.readthedocs.org/>`_ for reading SPEC files and 
`fabio <https://github.com/silx-kit/fabio>`_ for importing TIFF and CBF images. 

.. warning:: As of v0.7.1, NeXpy no longer includes the `tifffile module 
             <https://pypi.python.org/pypi/tifffile>`_. This can now be 
             installed with ``pip install tifffile``.

From v0.9.1, a new 2D smoothing option is available in the list of 
interpolations in the signal tab if `astropy <http://www.astropy.org>`_
is installed. It is labelled 'convolve' and provides, by default, a 
2-pixel Gaussian smoothing of the data. The number of pixels can be 
changed in the shell by setting ``plotview.smooth``.

=================  ==========================================================
Library            URL
=================  ==========================================================
lmfit              http://newville.github.io/lmfit-py/
fabio              https://github.com/silx-kit/fabio
spec2nexus         http://spec2nexus.readthedocs.org/
astropy            http://www.astropy.org
=================  ==========================================================

.. note:: NeXpy should still run without these additional packages, but invoking
          the relevant menu items may trigger an exception.

Semantic Versioning
-------------------
With the release of v0.1.0, NeXpy is using `Semantic Versioning 
<http://semver.org/spec/v2.0.0.html>`_.

User Support
------------
Consult the `NeXpy documentation <http://nexpy.github.io/nexpy/>`_ for details 
of both the Python command-line API and how to use the NeXpy GUI. If you have 
any general questions concerning the use of NeXpy, please address 
them to the `NeXus Mailing List 
<http://download.nexusformat.org/doc/html/mailinglist.html>`_. If you discover
any bugs, please submit a `Github issue 
<https://github.com/nexpy/nexpy/issues>`_, preferably with relevant tracebacks.

Acknowledgements
----------------
The `NeXus format <http://www.nexusformat.org>`_ for neutron, x-ray and muon 
data is developed by an international collaboration under the supervision of the 
`NeXus International Advisory Committee <http://wiki.nexusformat.org/NIAC>`_. 
The Python tree API used in NeXpy was originally developed by Paul Kienzle, who
also wrote the standard Python interface to the NeXus C-API. The original 
version of NeXpy was initially developed by Boyana Norris, Jason Sarich, and 
Daniel Lowell, and Ray Osborn using wxPython, and formed the inspiration
for the current PyQt version.
