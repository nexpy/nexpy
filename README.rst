Installation
============
Released versions of NeXpy are available on `PyPI
<https://pypi.python.org/pypi/NeXpy/>`__ and `conda-forge
<https://anaconda.org/conda-forge/nexpy>`__.

You can therefore install using 'pip'::

    $ pip install nexpy

or 'conda'::

    $ conda install -c conda-forge nexpy

.. note:: You can add conda-forge to your default channels so that it is
          automatically searched when installing. Just type
          ``conda config --add channels conda-forge``.

If you have the `Python Setup Tools
<https://pypi.python.org/pypi/setuptools>`__, you can install the
package from the source code either by downloading one of the `Github
releases <https://github.com/nexpy/nexpy/releases>`__ or by cloning the
latest development version in the `NeXpy Git repository
<https://github.com/nexpy/nexpy>`__::

    $ git clone https://github.com/nexpy/nexpy.git

Then use standard Python tools to build and/or install a distribution
from within the source directory::

    $ python -m build  # build a distribution
    $ python -m pip install .  # install the package

The Python API for reading and writing NeXus files is in a separate
package, `nexusformat <https://github.com/nexpy/nexusformat>`__, which
is also available on `PyPI <https://pypi.python.org/pypi/nexusformat>`__
and `conda-forge <https://anaconda.org/conda-forge/nexusformat>`__.

If the NeXpy GUI is not required, the package may be used in any Python
shell. It may be installed using::

    $ pip install nexusformat

or::

    $ conda install -c conda-forge nexusformat

The package can also be installed from the source code either by
downloading one of the `Github releases
<https://github.com/nexpy/nexusformat/releases>`__ or by cloning the
latest development version in the `NeXpy Git repository
<https://github.com/nexpy/nexusformat>`__::

    $ git clone https://github.com/nexpy/nexusformat.git

Version 2.0.0
-------------
In preparation for the release of v2.0.0, beta versions of both packages
have been uploaded to the `PyPI server
<https://pypi.org/project/NeXpy/2.0.0b1/>`__. Users are invited to test
it by installing using pip::

    $ pip install nexpy==2.0.0b1

New features include the ability to rotate 2D plots, validate NeXus
groups against the standard, and enable/disable/reorder plugin menus
dynamically.

See the `release notes
<https://github.com/nexpy/nexpy/releases/tag/v2.0.0b1>`__ for more
details. Please report any issues to `Github
<https://github.com/nexpy/nexpy/issues>`__ with relevant tracebacks.

Required Libraries
==================
Python Command-Line API
-----------------------
NeXpy provides a GUI interface to the `nexusformat API
<https://github.com/nexpy/nexusformat>`__, which uses `h5py
<http://h5py.org>`__ to read and write HDF5 files that implement the
`NeXus data format standard <https://www.nexusformat.org>`__. It does
not use the NeXus C API, which means that the current version cannot
read and write legacy HDF4 or XML NeXus files. One of the `NeXus
conversion utilities <https://manual.nexusformat.org/utilities.html>`__
should be used to convert such files to HDF5.

If you only intend to utilize the Python API from the command-line, the
only other required libraries are `NumPy <https://numpy.org>`__ and
`SciPy <http://scipy.org>`__. Autocompletion of group and field paths
within an open file is available if `IPython <https://ipython.org/>`__
is installed.

=================  =================================================
Library            URL
=================  =================================================
nexusformat        https://github.com/nexpy/nexusformat
h5py               https://www.h5py.org
numpy              https://numpy.org/
scipy              https://scipy.org/
IPython            https://ipython.org/
=================  =================================================

NeXpy GUI
---------
The GUI is built using the PyQt. The `qtpy package
<https://github.com/spyder-ide/qtpy>`__ is used to import whatever PyQt
library is installed, whether PyQt5, PyQt6, PySide2, or PySide6.

NeXpy embeds an `IPython shell <http://ipython.org/>`__ and `Matplotlib
plotting pane <http://matplotlib.sourceforge.net>`__, within a Qt GUI
based on the Jupyter QtConsole with an in-process kernel.

Least-squares fitting of 1D data uses the `LMFIT package
<https://lmfit.github.io/lmfit-py/>`__.

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
mplcursors         https://mplcursors.readthedocs.io/
=================  =================================================

Additional Packages
-------------------
Importers may require additional libraries to read the imported files in their
native format, *e.g.*, `spec2nexus <http://spec2nexus.readthedocs.org/>`__ for
reading SPEC files and `FabIO <https://pythonhosted.org/fabio/>`__ for
importing TIFF and CBF images.

From v0.9.1, a new 2D smoothing option is available in the list of
interpolations in the signal tab if `astropy <http://www.astropy.org>`__
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
          the relevant menu items may trigger a warning.

Running the GUI
---------------
To run from the installed location, add the $prefix/bin directory to your path
if you installed outside the python installation, and then run::

    $ nexpy [-r]

The -r option restores all files loaded in the previous session.

Semantic Versioning
-------------------
NeXpy uses `Semantic Versioning <http://semver.org/spec/v2.0.0.html>`__.

User Support
------------
Consult the `NeXpy documentation <http://nexpy.github.io/nexpy/>`__ for
details of both the Python command-line API and how to use the NeXpy
GUI. If you have any general questions concerning the use of NeXpy,
please address them to the `NeXus Mailing List
<http://download.nexusformat.org/doc/html/mailinglist.html>`__. If you
discover any bugs, please submit a `Github issue
<https://github.com/nexpy/nexpy/issues>`__, preferably with relevant
tracebacks.

Acknowledgements
----------------
The `NeXus format <http://www.nexusformat.org>`__ for neutron, x-ray and
muon data is developed by an international collaboration under the
supervision of the `NeXus International Advisory Committee
<https://www.nexusformat.org/NIAC.html>`__. The Python tree API used in
NeXpy was originally developed by Paul Kienzle, who also wrote the
standard Python interface to the NeXus C-API. The original version of
NeXpy was initially developed by Boyana Norris, Jason Sarich, and Daniel
Lowell, and Ray Osborn using wxPython, and formed the inspiration for
the current PyQt version. I am grateful to Tom Schoonjans for installing
the packages on conda-forge.
