Introduction
============
NeXpy provides a high-level python interface to NeXus data contained within a 
simple GUI. It is designed to provide an intuitive interactive toolbox allowing 
users both to access existing NeXus files and to create new NeXus-conforming 
data structures without expert knowledge of the file format.

See the [NeXpy documentation](http://nexpy.github.io/nexpy) for more details.

Installing and Running
======================
Released versions of NeXpy can be installed using either

```
    $ pip install nexpy
```

or

```
    $ easy_install nexpy 
```

If you have an Anaconda installation, use::

```
    $ conda install -c nexpy nexpy
```

The source code can be downloaded from the NeXpy Git repository:

```
    $ git clone https://github.com/nexpy/nexpy.git
```

To install in the standard Python location:

```
    $ python setup.py install
```

To install in an alternate location:

```
    $ python setup.py install --prefix=/path/to/installation/dir
```

As of v0.6.0, the Python API for reading and writing NeXus files is in a 
separate package, [nexusformat](https://github.com/nexpy/nexusformat), which 
is also available on [PyPI](https://pypi.python.org/pypi/nexusformat/) and 
will be automatically installed as a NeXpy dependency if you use pip. 

If the NeXpy GUI is not required, the package may be used in a regular Python
shell. It may be installed using:: 

```
    $ pip install nexusformat
```

or:: 

```
    $ easy_install nexusformat 
```

or::

```
    $ conda install -c nexpy nexusformat
```

The package can also be installed from the source code using the setup commands
described above. The source code is available either by downloading one of the 
[Github releases](https://github.com/nexpy/nexusformat/releases>) or by cloning 
the latest development version in the 
[NeXpy Git repository](https://github.com/nexpy/nexusformat>)::

```
    $ git clone https://github.com/nexpy/nexusformat.git
```

Prerequisites
=============
Python Command-Line API
-----------------------
The current version of NeXpy uses h5py to read and write NeXus files because
of its ability to handle large data files. There is therefore no dependency 
on the [NeXus C API](http://download.nexusformat.org/doc/html/napi.html). 
This also means that the current version cannot read and write HDF4 or XML 
NeXus files.

If you only intend to utilize the Python API from the command-line, the only 
other required library is [Numpy](http://numpy.scipy.org).

* [nexusformat](https://github.com/nexpy/nexusformat)
* [h5py](http://www.h5py.org)
* [numpy](http://numpy.scipy.org/)

NeXpy GUI
---------
The GUI is built using the PyQt. The latest version supports either 
PyQt4 or PySide, and should load whichever library it finds. Neither are 
listed as a dependency but one or other must be installed. PyQt4 is included
in the 
[Anaconda default distribution](https://store.continuum.io/cshop/anaconda/) 
while PySide is included in the 
[Enthought Python Distribution](http://www.enthought.com) or within Enthought's 
[Canopy Application](https://www.enthought.com/products/canopy/).

The GUI includes an [IPython shell](http://ipython.org/) and a 
[Matplotlib plotting pane](http://matplotlib.sourceforge.net). The IPython shell 
is embedded in the Qt GUI using an implementation based on the newly-released
Jupyter QtConsole, which has replaced the old IPython QtConsole.
          
* [jupyter](http://jupyter.org/)
* [IPython v4.0.0](http://ipython.org/)
* [matplotlib v1.4.0](http://matplotlib.sourceforge.net/)

Some people have reported that NeXpy crashes on launch on some Linux systems.
We believe that this may be due to both PyQt4 and PyQt5 being installed,
although that doesn't cause a problem on all systems. If NeXpy crashes on
launch, please try setting the environment variable QT_API to either 'pyqt',
for the PyQt4 library, or 'pyside', for the PySide library, depending on what
you have installed, e.g., in BASH, type ::

```
    $ export QT_API=pyqt
```
Additional Packages
-------------------
Additional functionality is provided by other external Python packages. 
Least-squares fitting requires Matt Newville's least-squares fitting package, 
[lmfit-py](http://newville.github.io/lmfit-py). Importers may also require 
libraries to read the imported files in their native format, e.g., 
[spec2nexus](http://spec2nexus.readthedocs.org/) for reading SPEC files. 

From v0.4.3, the log window is colorized if 
[ansi2html](https://pypi.python.org/pypi/ansi2html/) is installed.

The following packages are recommended.

* Least-squares fitting: [lmfit](http://newville.github.io/lmfit-py/)
* TIFF file imports: [tifffile](https://pypi.python.org/pypi/tifffile)
* CBF file imports: [pycbf](http://sourceforge.net/projects/cbflib/files/cbflib/pycbf/)
* SPEC file imports: [spec2nexus](http://spec2nexus.readthedocs.org/)
* Log file colorization: [ansi2html](https://pypi.python.org/pypi/ansi2html/)

To run with the GUI
===================

To run from the installed location, add the $prefix/bin directory to your path
(only if you installed outside the python installation), and then run:

```
    $ nexpy
```

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
