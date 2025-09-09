.. NeXpy documentation master file, created by
   sphinx-quickstart on Sun Aug 11 13:18:51 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

.. image:: /images/nexpy-logo.png

NeXpy: A Python GUI to analyze NeXus data
=========================================

NeXpy provides a high-level Python interface to HDF5 files,
particularly those stored as `NeXus data
<http://www.nexusformat.org/>`__, within a simple GUI. It is designed to
provide an intuitive interactive toolbox allowing users both to access
existing NeXus files and to create new NeXus-conforming data structures
without expert knowledge of the file format.

.. image:: /images/scan-panel.png
   :align: center
   :width: 90%

This documentation describes two packages.

**NeXpy**
  `NeXpy <https://github.com/nexpy/nexpy>`__ provides the GUI
  interface for loading, inspecting, plotting, and manipulating NeXus
  data, with an embedded IPython shell and script editor.

  .. image:: https://img.shields.io/pypi/v/nexpy.svg
     :target: https://pypi.python.org/pypi/nexpy

  .. image:: https://img.shields.io/conda/vn/conda-forge/nexpy
     :target: https://anaconda.org/conda-forge/nexpy

**nexusformat**
  The API for reading, modifying, and writing NeXus data is provided by
  the `nexusformat <https://github.com/nexpy/nexusformat>`__ package,
  which utilizes `h5py <http://www.h5py.org/>`__ for loading and saving
  the data in HDF5 files.

  .. image:: https://img.shields.io/pypi/v/nexusformat.svg
     :target: https://pypi.python.org/pypi/nexusformat

  .. image:: https://img.shields.io/conda/vn/conda-forge/nexusformat
     :target: https://anaconda.org/conda-forge/nexusformat

----

.. toctree::
   :maxdepth: 2

   includeme
   pythonshell
   pythongui
   readers
   examples
   treeapi

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

