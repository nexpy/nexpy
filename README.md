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

Prerequisites
=============
The following libraries are used by the full installation of NeXpy. There is 
more details of the nature of these dependencies in the 
[NeXpy documentation](http://nexpy.github.io/nexpy).

* h5py                 http://www.h5py.org
* numpy,scipy          http://numpy.scipy.org
* jupyter              http://jupyter.org
* IPython v1.1.0       http://ipython.org
* matplotlib v1.2.0    http://matplotlib.sourceforge.net    (GUI only)
* lmfit                http://newville.github.io/lmfit-py (Fitting only)
* pycbf                http://www.bernstein-plus-sons.com/software/CBF/ (CBF reader only)
* spec2nexus           http://spec2nexus.readthedocs.org (SPEC reader only)

The GUI is built using the PyQt. The latest version supports either 
PyQt4/5 or PySide, and should load whichever library it finds. Neither are 
listed as a dependency but one or other must be installed. PyQt4 is included
in the 
[Anaconda default distribution](https://store.continuum.io/cshop/anaconda/) 
while PySide is included in the 
[Enthought Python Distribution](http://www.enthought.com>) or within Enthought's 
[Canopy Application](https://www.enthought.com/products/canopy/>).

The following environment variable may need to be set
PYTHONPATH --> paths to ipython,numpy,scipy,matplotlib if installed in a 
nonstandard place

PySide 1.1.0 on rpm systems
---------------------------

python-pyside v1.1.0 rpm has a bug in it where it does not supply the egg-info
that dist-utils looks for. There is a workaround mentioned in
https://github.com/nvbn/everpad/issues/401#issuecomment-35834335 which is to
spoof the system with a fake file in
`/usr/lib/python2.7/dist-packages/PySide-1.1.0-py2.7.egg-info`
or
`/usr/lib/python2.7/site-packages/PySide-1.1.0-py2.7.egg-info`
depending on which install location exists. It appears that v1.2.0 contains
the missing file.

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
