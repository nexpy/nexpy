Introduction
============
NeXpy provides a high-level python interface to NeXus data contained within a simple GUI. It is designed to provide an intuitive interactive toolbox allowing users both to access existing NeXus files and to create new NeXus-conforming data structures without expert knowledge of the file format.

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

The source code can be downloaded from the NeXpy Git repository:

```
    $ git clone http://github.com/nexpy/nexpy.git
```

To install in the standard Python location:

```
    $ python setup.py install
```

To install in an alternate location:

```
    $ python setup.py install --prefix=/path/to/installation/dir
```

Prerequisites
=============
The following libraries are used by the full installation of NeXpy. There is 
more details of the nature of these dependencies in the 
[NeXpy documentation](http://nexpy.github.io/nexpy).

* h5py                 http://www.h5py.org
* numpy,scipy          http://numpy.scipy.org
* iPython v1.1.0       http://ipython.org/
* PySide v1.1.0        http://www.pyside.org/
* matplotlib v1.1.0    http://matplotlib.sourceforge.net    (GUI only)
* lmfit                http://newville.github.io/lmfit-py (Fitting only)
* pycbf                http://www.bernstein-plus-sons.com/software/CBF/ (CBF reader only)
* spec2nexus           http://spec2nexus.readthedocs.org (SPEC reader only)

The following environment variable may need to be set
PYTHONPATH --> paths to ipython,numpy,scipy,matplotlib if installed in a 
nonstandard place

All of the above are included in the Enthought Python Distribution v7.3.

To run with the GUI
===================

To run from the installed location, add the $prefix/bin directory to your path
(only if you installed outside the python installation), and then run:

```
nexpy
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
