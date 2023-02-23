Introduction
============
NeXpy provides a high-level python interface to HDF5 files, particularly those
stored as NeXus data, within a simple GUI. It is designed to provide an 
intuitive interactive toolbox allowing users both to access existing NeXus 
files and to create new NeXus-conforming data structures without expert 
knowledge of the file format.

See the [NeXpy documentation](http://nexpy.github.io/nexpy) for more details.

Installing and Running
======================
Released versions of NeXpy can be installed using either

```
    $ pip install nexpy
```

or::

```
    $ conda install -c conda-forge nexpy
```

The source code can be downloaded from the NeXpy Git repository:

```
    $ git clone https://github.com/nexpy/nexpy.git
```

Prerequisites
=============
Python Command-Line API
-----------------------
NeXpy provides a GUI interface to the 
[nexusformat API](https://github.com/nexpy/nexusformat), which uses 
[h5py](https://www.h5py.org) to read and write HDF5 files that implement the 
[NeXus data format standard](https://www.nexusformat.org). It does not use the 
NeXus C API, which means that the current version cannot read and write legacy
HDF4 or XML NeXus files. One of the 
[NeXus conversion utilities](https://manual.nexusformat.org/utilities.html)
should be used to convert such files to HDF5.

If you only intend to utilize the Python API from the command-line, the only 
other required libraries are [NumPy](http://numpy.org) and 
[SciPy](http://scipy.org). Autocompletion of group and field paths within an
open file is available if [IPython](https://ipython.org/) is installed.

* [nexusformat](https://github.com/nexpy/nexusformat)
* [h5py](https://www.h5py.org)
* [numpy](https://numpy.org/)
* [scipy](https://scipy.org/)
* [IPython](https://ipython.org/)

NeXpy GUI
---------
The GUI is built using PyQt. The 
[qtpy package](https://github.com/spyder-ide/qtpy) is used to import whatever 
PyQt library is installed, whether PyQt5, PyQt6, PySide2, or PySide6.

The GUI embeds an [IPython shell](http://ipython.org/) and
[Matplotlib plotting pane](http://matplotlib.sourceforge.net), within a Qt
GUI based on the Jupyter QtConsole with an in-process kernel. 

Least-squares fitting of 1D data uses the
[LMFIT package](https://lmfit.github.io/lmfit-py/).
          
* [qtpy](https://github.com/spyder-ide/qtpy)
* [qtconsole](https://qtconsole.readthedocs.io/)
* [IPython](https://ipython.org/)
* [matplotlib](https://matplotlib.sourceforge.net/)
* [lmfit](https://lmfit.github.io/lmfit-py/)
* [pylatexenc](https://pylatexenc.readthedocs.io/)
* [pillow](https://pillow.readthedocs.io/)
* [ansi2html](https://pypi.org/project/ansi2html/)

Additional Packages
-------------------
Importers may require additional libraries to read the imported files in their 
native format, e.g., [spec2nexus](http://spec2nexus.readthedocs.org/) for 
reading SPEC files or [FabIO](https://github.com/silx-kit/fabio) for reading
TIFF and CBF images.

A 2D smoothing option is available in the list of interpolations in the signal 
tab if [astropy](<http://www.astropy.org>) is installed. It is labelled 
'convolve' and provides, by default, a 2-pixel Gaussian smoothing of the data. 
The number of pixels can be changed in the shell by setting `plotview.smooth`.

The following packages are recommended.

* TIFF/CBF file imports: [fabio](https://github.com/silx-kit/fabio)
* SPEC file imports: [spec2nexus](http://spec2nexus.readthedocs.org/)
* Gaussian smoothing: [astropy](http://www.astropy.org)

To run with the GUI
===================
To run from the installed location, add the $prefix/bin directory to your path
if you installed outside the python installation, and then run:

```
    $ nexpy [-r]
```
The `-r` option restores all files loaded in the previous session.

User Support
============
Consult the [NeXpy documentation](http://nexpy.github.io/nexpy) for details 
of both the Python command-line API and how to use the NeXpy GUI. If you have 
any general questions concerning the use of NeXpy, please address 
them to the 
[NeXus Mailing List](http://download.nexusformat.org/doc/html/mailinglist.html). 
If you discover any bugs, please submit a 
[Github issue](https://github.com/nexpy/nexpy/issues), preferably with relevant 
tracebacks.
