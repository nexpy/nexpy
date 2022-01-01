Installation
============
Released versions of NeXpy are available on `PyPI 
<https://pypi.python.org/pypi/NeXpy/>`_ and as a `Conda installation 
<https://anaconda.org/nexpy>`_. 

If you have the `Python Setup Tools <https://pypi.python.org/pypi/setuptools>`_ 
installed, then you can either install using 'pip'::

    $ pip install nexpy

or, if you have an Anaconda installation, NeXpy is now available on the 
conda-forge channel::

    $ conda install -c conda-forge nexpy

.. note:: You can add conda-forge to your default channels so that it is 
          automatically searched when installing. Just type 
          ``conda config --add channels conda-forge``. 

You can install the package from the source code either by downloading one of 
the `Github releases <https://github.com/nexpy/nexpy/releases>`_ or by cloning 
the latest development version in the 
`NeXpy Git repository <https://github.com/nexpy/nexpy>`_::

    $ git clone https://github.com/nexpy/nexpy.git

Then use standard Python tools to build and/or install a distribution from
within the source directory::

    $ python -m build  # build a distribution
    $ python -m pip install .  # install the package

The Python API for reading and writing NeXus files is in a separate package, 
`nexusformat <https://github.com/nexpy/nexusformat>`_, which is also available 
on `PyPI <https://pypi.python.org/pypi/nexusformat/>`_ and conda-forge. 

If the NeXpy GUI is not required, the package may be used in a regular Python
shell. It may be installed using:: 

    $ pip install nexusformat

or::

    $ conda install -c conda-forge nexusformat

The package can also be installed from the source code using the setup commands
described above. The source code is available either by downloading one of the 
`Github releases <https://github.com/nexpy/nexusformat/releases>`_ or by 
cloning the latest development version in the `NeXpy Git repository 
<https://github.com/nexpy/nexusformat>`_::

    $ git clone https://github.com/nexpy/nexusformat.git

Required Libraries
==================
Python Command-Line API
-----------------------
NeXpy provides a GUI interface to the 
`nexusformat API <https://github.com/nexpy/nexusformat>`_, which uses 
`h5py <http://h5py.org>`_ to read and write HDF5 files that implement the 
`NeXus data format standard <https://www.nexusformat.org>`_. It does not use 
the NeXus C API, which means that the current version cannot read and write 
legacy HDF4 or XML NeXus files. One of the 
`NeXus conversion utilities <https://manual.nexusformat.org/utilities.html>`_ 
should be used to convert such files to HDF5.

If you only intend to utilize the Python API from the command-line, the only 
other required libraries iare `NumPy <https://numpy.org>`_ and, if you want
autocompletion within an IPython shell,  `SciPy <http://numpy.scipy.org>`_.

=================  =================================================
Library            URL
=================  =================================================
nexusformat        https://github.com/nexpy/nexusformat
h5py               https://www.h5py.org
numpy              https://numpy.org/
scipy              https://scipy.org/
=================  =================================================

.. note:: If you need to read HDF4 or XML files now, please clone the 
          old-master branch (https://github.com/nexpy/nexpy/tree/old-master).

NeXpy GUI
---------
The GUI is built using the PyQt. The 
`qtpy package <https://github.com/spyder-ide/qtpy>`_ is used to import an 
installed PyQt library, either PyQt5 or PySide2.

The GUI includes an `IPython shell <http://ipython.org/>`_ and a `Matplotlib
plotting pane <http://matplotlib.sourceforge.net>`_. The IPython shell is
embedded in the Qt GUI using an implementation based on the Jupyter QtConsole.

Least-squares fitting of 1D data uses the `lmfit package 
<https://lmfit.github.io/lmfit-py/>`_`.

=================  =================================================
Library            URL
=================  =================================================
IPython            https://ipython.org/
qtconsole          https://qtconsole.readthedocs.io/
matplotlib         https://matplotlib.org/
lmfit              https://lmfit.github.io/lmfit-py/
pylatexenc         https://pylatexenc.readthedocs.io/
pillow             https://pillow.readthedocs.io/
ansi2html          https://pypi.python.org/pypi/ansi2html/
=================  =================================================

Additional Packages
-------------------
Importers may require additional libraries to read the imported files in their 
native format, *e.g.*, `spec2nexus <http://spec2nexus.readthedocs.org/>`_ for 
reading SPEC files and `FabIO <https://github.com/silx-kit/fabio>`_ for 
importing TIFF and CBF images. 

From v0.9.1, a new 2D smoothing option is available in the list of 
interpolations in the signal tab if `astropy <http://www.astropy.org>`_
is installed. It is labelled 'convolve' and provides, by default, a 
2-pixel Gaussian smoothing of the data. The number of pixels can be 
changed in the shell by setting ``plotview.smooth``.

=================  ==========================================================
Library            URL
=================  ==========================================================
fabio              https://pythonhosted.org/fabio/
spec2nexus         http://spec2nexus.readthedocs.org/
astropy            http://www.astropy.org/
=================  ==========================================================

.. note:: NeXpy should still run without these additional packages, but invoking
          the relevant menu items may trigger an exception.

Running the GUI
---------------
To run from the installed location, add the $prefix/bin directory to your path 
if you installed outside the python installation, and then run::

    $ nexpy [-r]

The -r option restores all files loaded in the previous session.

Semantic Versioning
-------------------
NeXpy uses `Semantic Versioning <http://semver.org/spec/v2.0.0.html>`_.

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
for the current PyQt version. I am grateful to Tom Schoonjans for installing
the packages on conda-forge.
