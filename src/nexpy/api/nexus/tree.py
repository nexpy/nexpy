#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Author: Paul Kienzle, Ray Osborn
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
The `nexus.tree` modules are designed to accomplish two goals:

    1. To provide convenient access to existing data contained in NeXus files.
    2. To enable new NeXus data to be created and manipulated interactively.

These goals are achieved by mapping hierarchical NeXus data structures directly
into python objects, which either represent NeXus groups or NeXus fields.
Entries in a group are referenced much like fields in a class are referenced in
python. The entire data hierarchy can be referenced at any time, whether the
NeXus data has been loaded in from an existing NeXus file or created dynamically
within the python session. This provides a natural scripting interface to NeXus 
data.

Example 1: Loading a NeXus file
-------------------------------
The following commands loads NeXus data from a file, displays (some of) the
contents as a tree, and then accesses individual data items.

    >>> from nexpy.api import nexus as nx
    >>> a=nx.load('sns/data/ARCS_7326.nxs')
    >>> print a.tree
    root:NXroot
      @HDF5_Version = 1.8.2
      @NeXus_version = 4.2.1
      @file_name = ARCS_7326.nxs
      @file_time = 2010-05-05T01:59:25-05:00
      entry:NXentry
        data:NXdata
          data = float32(631x461x4x825)
            @axes = rotation_angle:tilt_angle:sample_angle:time_of_flight
            @signal = 1
          rotation_angle = float32(632)
            @units = degree
          sample_angle = [ 210.  215.  220.  225.  230.]
            @units = degree
          tilt_angle = float32(462)
            @units = degree
          time_of_flight = float32(826)
            @units = microsecond
        run_number = 7326
        sample:NXsample
          pulse_time = 2854.94747365
            @units = microsecond
    .
    .
    .
    >>> a.entry.run_number
    NXfield(7326)

So the tree returned from :func:`load()` has an entry for each group, field and
attribute.  You can traverse the hierarchy using the names of the groups.  For
example, tree.entry.instrument.detector.distance is an example of a field
containing the distance to each pixel in the detector. Entries can also be
referenced by NXclass name, such as ``tree.NXentry[0].instrument``. Since there may
be multiple entries of the same NeXus class, the ``NXclass`` attribute returns a
(possibly empty) list.

The :func:`load()` and :func:`save()` functions are implemented using the class
`nexus.tree.NXFile`, a subclass of :class:`h5py.File`.

Example 2: Creating a NeXus file dynamically
--------------------------------------------
The second example shows how to create NeXus data dynamically and saves it to a
file. The data are first created as Numpy arrays

    >>> import numpy as np
    >>> x=y=np.linspace(0,2*np.pi,101)
    >>> X,Y=np.meshgrid(y,x)
    >>> z=np.sin(X)*np.sin(Y)

Then, a NeXus data group is created and the data inserted to produce a
NeXus-compliant structure that can be saved to a file.

    >>> root=nx.NXroot(NXentry())
    >>> print root.tree
    root:NXroot
      entry:NXentry
    >>> root.entry.data=nx.NXdata(z,[x,y])

Additional metadata can be inserted before saving the data to a file.

    >>> root.entry.sample=nx.NXsample()
    >>> root.entry.sample.temperature = 40.0
    >>> root.entry.sample.temperature.units = 'K'
    >>> root.save('example.nxs')

:class:`NXfield` objects have much of the functionality of Numpy arrays. They may be used
in simple arithmetic expressions with other NXfields, Numpy arrays or scalar
values and will be cast as ndarray objects if used as arguments in Numpy
modules.

    >>> x=nx.NXfield(np.linspace(0,10.0,11))
    >>> x
    NXfield([  0.   1.   2. ...,   8.   9.  10.])
    >>> x + 10
    NXfield([ 10.  11.  12. ...,  18.  19.  20.])
    >>> np.sin(x)
    array([ 0.        ,  0.84147098,  0.90929743, ...,  0.98935825,
        0.41211849, -0.54402111])

If the arithmetic operation is assigned to a NeXus group attribute, it will be
automatically cast as a valid :class:`NXfield` object with the type and shape determined
by the Numpy array type and shape.

    >>> entry.data.result = np.sin(x)
    >>> entry.data.result
    NXfield([ 0.          0.84147098  0.90929743 ...,  0.98935825  0.41211849
     -0.54402111])
    >>> entry.data.result.dtype, entry.data.result.shape
    (dtype('float64'), (11,))

NeXus Objects
-------------
Properties of the entry in the tree are referenced by attributes that depend
on the object type, different nx attributes may be available.

Objects (:class:`NXobject`) have attributes shared by both groups and fields::
    * nxname   object name
    * nxclass  object class for groups, 'NXfield' for fields
    * nxgroup  group containing the entry, or None for the root
    * attrs    dictionary of NeXus attributes for the object

Groups (:class:`NXgroup`) have attributes for accessing children::
    * entries  dictionary of entries within the group
    * component('nxclass')  return group entries of a particular class
    * dir()    print the list of entries in the group
    * tree     return the list of entries and subentries in the group
    * plot()   plot signal and axes for the group, if available

Fields (:class:`NXfield`) have attributes for accessing data:
    * shape    dimensions of data in the field
    * dtype    data type
    * nxdata   data in the field

Linked fields or groups (:class:`NXlink`) have attributes for accessing the link::
    * nxlink   reference to the linked field or group

NeXus attributes (:class:`NXattr`) have a type and a value only::
    * dtype    attribute type
    * nxdata   attribute data

There is a subclass of :class:`NXgroup` for each group class defined by the NeXus standard,
so it is possible to create an :class:`NXgroup` of NeXus :class:`NXsample` directly using:

    >>> sample = NXsample()

The default group name will be the class name following the 'NX', so the above
group will have an nxname of 'sample'. However, this is overridden by the
attribute name when it is assigned as a group attribute, e.g.,

    >>> entry.sample1 = NXsample()
    >>> entry.sample1.nxname
    sample1

You can traverse the tree by component class instead of component name. Since
there may be multiple components of the same class in one group you will need to
specify which one to use.  For example::

    tree.NXentry[0].NXinstrument[0].NXdetector[0].distance

references the first detector of the first instrument of the first entry.
Unfortunately, there is no guarantee regarding the order of the entries, and it
may vary from call to call, so this is mainly useful in iterative searches.


Unit Conversion
---------------
Data can be stored in the NeXus file in a variety of units, depending on which
facility is storing the file.  This makes life difficult for reduction and
analysis programs which must know the units they are working with.  Our solution
to this problem is to allow the reader to retrieve data from the file in
particular units.  For example, if detector distance is stored in the file using
millimeters you can retrieve them in meters using::

    entry.instrument.detector.distance.convert('m')

See `nexus.unit` for more details on the unit formats supported.

Reading and Writing Slabs
-------------------------
If the size of the :class:`NXfield` array is too large to be loaded into memory (as 
defined by NX_MEMORY), the data values should be read or written in as a series 
of slabs represented by :class:`NXfield` slices::

 >>> for i in range(Ni):
         for j in range(Nj):
             value = root.NXentry[0].data.data[i,j,:]
             ...


Plotting NeXus data
-------------------
There is a :meth:`plot()` method for groups that automatically looks for 'signal' and
'axes' attributes within the group in order to determine what to plot. These are
defined by the 'nxsignal' and 'nxaxes' properties of the group. This means that
the method will determine whether the plot should be one- or two- dimensional.
For higher than two dimensions, only the top slice is plotted by default.

The plot method accepts as arguments the standard matplotlib.pyplot.plot format 
strings to customize one-dimensional plots, axis and scale limits, and will
transmit keyword arguments to the matplotlib plotting methods.

    >>> a=nx.load('chopper.nxs')
    >>> a.entry.monitor1.plot()
    >>> a.entry.monitor2.plot('r+', xmax=2600)
    
It is possible to plot over the existing figure with the :meth:`oplot()` method and to
plot with logarithmic intensity scales with the :meth:`logplot()` method. The x- and
y-axes can also be rendered logarithmically using the `logx` and `logy` keywords.

Although the :meth:`plot()` method uses matplotlib by default to plot the data, you can replace
this with your own plotter by setting `nexus.NXgroup._plotter` to your own plotter
class.  The plotter class has one method::

    plot(signal, axes, entry, title, format, **opts)

where signal is the field containing the data, axes are the fields listing the
signal sample points, entry is file/path within the file to the data group and
title is the title of the group or the parent :class:`NXentry`, if available.
"""

from __future__ import with_statement
import os
from copy import copy, deepcopy

import numpy as np
import h5py as h5

#Memory in MB
NX_MEMORY = 2000

__all__ = ['NXFile', 'NXobject', 'NXfield', 'NXgroup', 'NXattr', 'nxclasses',
           'NX_MEMORY', 'setmemory', 'load', 'save', 'tree', 'centers', 'SDS', 
           'NXlink', 'NXlinkfield', 'NXlinkgroup', 'NXlinkdata', 'NXlinkexternal',
           'NeXusError']

#List of defined base classes (later added to __all__)
nxclasses = [ 'NXroot', 'NXentry', 'NXsubentry', 'NXdata', 'NXmonitor', 'NXlog', 
              'NXsample', 'NXinstrument', 'NXaperture', 'NXattenuator', 'NXbeam', 
              'NXbeam_stop', 'NXbending_magnet', 'NXcapillary', 'NXcharacterization', 
              'NXcollection', 'NXcollimator', 'NXcrystal', 'NXdetector', 
              'NXdetector_group', 'NXdisk_chopper', 'NXenvironment', 'NXevent_data', 
              'NXfermi_chopper', 'NXfilter', 'NXflipper', 'NXgeometry', 'NXguide', 
              'NXinsertion_device', 'NXmirror', 'NXmoderator', 'NXmonochromator', 
              'NXnote', 'NXorientation', 'NXparameters', 'NXpolarizer', 
              'NXpositioner', 'NXprocess', 'NXsensor', 'NXshape', 'NXsource', 
              'NXsubentry', 'NXtranslation', 'NXuser', 'NXvelocity_selector', 
              'NXxraylens']

np.set_printoptions(threshold=5)


class NeXusError(Exception):
    """NeXus Error"""
    pass


class NXFile(object):

    """
    Structure-based interface to the NeXus file API.

    Usage::

      file = NXFile(filename, ['r','rw','w'])
        - open the NeXus file
      root = file.readfile()
        - read the structure of the NeXus file.  This returns a NeXus tree.
      file.writefile(root)
        - write a NeXus tree to the file.

    Example::

      nx = NXFile('REF_L_1346.nxs','r')
      tree = nx.readfile()
      for entry in tree.NXentry:
          process(entry)
      copy = NXFile('modified.nxs','w')
      copy.writefile(tree)

    Note that the large datasets are not loaded immediately.  Instead, the
    when the data set is requested, the file is reopened, the data read, and
    the file closed again.  open/close are available for when we want to
    read/write slabs without the overhead of moving the file cursor each time.
    The :class:`NXdata` objects in the returned tree hold the object values.
    """

    def __init__(self, name, mode=None, **kwds):
        """
        Creates an h5py File object for reading and writing.
        """
        if mode == 'w4' or mode == 'wx':
            raise NeXusError('Only HDF5 files supported')
        elif mode == 'w' or mode == 'w-' or mode == 'w5':
            if mode == 'w5':
                mode = 'w'
            self._file = h5.File(name, mode, **kwds)
            self._mode = 'rw'
        else:
            if mode == 'rw':
                mode = 'r+'
            self._file = h5.File(name, mode, **kwds)
            if mode == 'rw' or mode == 'r+':
                self._mode = 'rw'
            else:
                self._mode = 'r'   
        self._filename = self._file.filename                             
        self._path = ''

    def __repr__(self):
        return '<NXFile "%s" (mode %s)>' % (os.path.basename(self._filename),
                                                 self._mode)

    def __getitem__(self, key):
        """Returns an object from the NeXus file."""
        return self._file[key]

    def __setitem__(self, key, value):
        """Sets an object value in the NeXus file."""
        self._file[key] = value

    def __delitem__(self, name):
        """ Delete an item from a group. """
        del self._file[name]

    def __enter__(self):
        return self.open()

    def __exit__(self, *args):
        self._file.close()

    def get(self, *args, **kwds):
        return self._file.get(*args, **kwds)

    def copy(self, *args, **kwds):
        self._file.copy(*args, **kwds)

    def open(self, **kwds):
        if not self._file.id:
            if self._mode == 'rw':
                self._file = h5.File(self._filename, 'r+', **kwds)
            else:
                self._file = h5.File(self._filename, self._mode, **kwds)
            self.nxpath = '/'
        return self

    def close(self):
        if self._file.id:
            self._file.close()

    def readfile(self):
        """
        Reads the NeXus file structure from the file and returns a tree of 
        NXobjects.

        Large datasets are not read until they are needed.
        """
        self.nxpath = '/'
        root = self._readgroup('root')
        root._group = None
        root._file = self
        root._filename = self.filename
        root._mode = self._mode
        return root

    def _readdata(self, name):
        """
        Reads a data object and returns it as an NXfield or NXlink.
        """
        # Finally some data, but don't read it if it is big
        # Instead record the location, type and size
        attrs = self._getattrs()
        if 'target' in attrs and attrs['target'] != self.nxpath:
            data = NXlinkfield(target=attrs['target'], name=name)
        else:
            value, shape, dtype, attrs = self.readvalues(attrs=attrs)
            if self._isexternal():
                external_link = self.get(self.nxpath, getlink=True)
                _target, _file = external_link.path, external_link.filename
                data = NXlink(value=value, name=name, dtype=dtype, shape=shape,
                              attrs=attrs, target=_target, file=_file)
            else:
                data = NXfield(value=value, name=name, dtype=dtype, shape=shape,
                               attrs=attrs)
        return data

    def _readnxclass(self, obj):        # see issue #33
        nxclass = obj.attrs.get('NX_class', None)
        if isinstance(nxclass, np.ndarray): # attribute reported as DATATYPE SIMPLE
            nxclass = nxclass[0]            # convert as if DATATYPE SCALAR
        return nxclass

    def _readchildren(self):
        children = {}
        parent_path = self.nxpath
        for name, value in self[parent_path].items():
            self.nxpath = parent_path + '/' + name
            if isinstance(value, h5.Group):
                children[name] = self._readgroup(name)
            else:
                children[name] = self._readdata(name)
        return children

    def _readgroup(self, name):
        """
        Reads the group with the current path and returns it as an NXgroup.
        """
        attrs = dict(self[self.nxpath].attrs)
        nxclass = self._readnxclass(self[self.nxpath])
        if nxclass is not None:
            del attrs['NX_class']
        elif self.nxpath == '/':
            nxclass = 'NXroot'
        else:
            nxclass = 'NXgroup'
        if 'target' in attrs and attrs['target'] != self.nxpath:
            # This is a linked group; don't try to load it.
            group = NXlinkgroup(target=attrs['target'], name=name)
        else:
            children = self._readchildren()
            group = NXgroup(nxclass=nxclass,name=name,attrs=attrs,entries=children)
            # Build chain back structure
            for obj in children.values():
                obj._group = group
        group._changed = True
        return group

    def writefile(self, tree):
        """
        Writes the NeXus file structure to a file.

        The file is assumed to start empty. Updating individual objects can be
        done using the h5py interface.
        """
        links = []
        self.nxpath = ""
        for entry in tree.values():
            links += self._writegroup(entry)
        self._writelinks(links)
        if len(tree.attrs) > 0:
            self._writeattrs(tree.attrs)
        self._setattrs()

    def _writeattrs(self, attrs):
        """
        Writes the attributes for the group/data with the current path.

        If no group or data object is open, the file attributes are returned.
        """
        for name, value in attrs.iteritems():
            self[self.nxpath].attrs[name] = value.nxdata

    def _writedata(self, data):
        """
        Writes the given data to a file.

        NXlinks cannot be written until the linked group is created, so
        this routine returns the set of links that need to be written.
        Call writelinks on the list.
        """

        parent = '/' + self.nxpath.lstrip('/')
        self.nxpath = parent + '/' + data.nxname

        # If the data is linked then
        if data._target is not None:
            if data._filename is not None:
                self.linkexternal(data)
                return []
            else:
                return [(self.nxpath, data._target)]

        if data._uncopied_data:
            _file, _path = data._uncopied_data
            with _file as f:
                f.copy(_path, self[parent], self.nxpath)
            data._uncopied_data = None
        elif data._memfile:
            data._memfile.copy('data', self[parent], self.nxpath)
            data._memfile = None
        elif data.nxfilemode and data.nxfile.filename != self.filename:
            data.nxfile.copy(data.nxpath, self[parent])
        else:
            if data.nxname not in self[parent]:
                if np.prod(data.shape) > 10000:
                    if not data._chunks:
                        data._chunks = True
                    if not data._compression:
                        data._compression = 'gzip'
                self[parent].create_dataset(data.nxname, 
                                            dtype=data.dtype, shape=data.shape,
                                            compression=data._compression,
                                            chunks=data._chunks,
                                            maxshape=data._maxshape,
                                            fillvalue = data._fillvalue)
            try:
                value = data.nxdata
                if value is not None:
                    self[self.nxpath][()] = value 
            except NeXusError:
                pass  
        self._writeattrs(data.attrs)
        self.nxpath = parent
        return []

    def _writegroup(self, group):
        """
        Writes the given group structure, including the data.

        NXlinks cannot be written until the linked group is created, so
        this routine returns the set of links that need to be written.
        Call writelinks on the list.
        """
        if group.nxpath != '' and group.nxpath != '/':
            parent = '/' + self.nxpath.lstrip('/')
            self.nxpath = parent + '/' + group.nxname
            if group.nxname not in self[parent]:
                self[parent].create_group(group.nxname)
            if group.nxclass and group.nxclass != 'NXgroup':
                self[self.nxpath].attrs['NX_class'] = group.nxclass
        else:
            parent = self.nxpath = '/'

        links = []
        self._writeattrs(group.attrs)
        if group._target is not None:
            links += [(self.nxpath, group._target)]
        for child in group.values():
            if child.nxclass == 'NXfield':
                links += self._writedata(child)
            elif child._target is not None:
                links += [(self.nxpath+"/"+child.nxname, child._target)]
            else:
                links += self._writegroup(child)
        self.nxpath = parent
        return links

    def _writelinks(self, links):
        """
        Creates links within the NeXus file.

        These are defined by the set of pairs returned by _writegroup.
        """
        # link sources to targets
        for path, target in links:
            if path != target:
                # ignore self-links
                if path not in self['/']:
                    parent = "/".join(path.split("/")[:-1])
                    self[parent]._id.link(target, path, h5.h5g.LINK_HARD)

    def readvalues(self, attrs=None):
        shape, dtype = self[self.nxpath].shape, self[self.nxpath].dtype
        if shape == (1,):
            shape = ()
        #Read in the data if it's not too large
        if np.prod(shape) < 1000:# i.e., less than 1k dims
            try:
                value = self.readvalue(self.nxpath)
                #Variable length strings are returned from h5py with dtype 'O'
                if h5.check_dtype(vlen=self[self.nxpath].dtype) in (str, unicode):
                    value = np.string_(value)
                    dtype = value.dtype
                if shape == ():
                    value = np.asscalar(value)
            except ValueError:
                value = None
        else:
            value = None
        if attrs is None:
            attrs = self._getattrs()
        return value, shape, dtype, attrs

    def readvalue(self, path, idx=()):
        return self[path][idx]

    def writevalue(self, path, value, idx=()):
        self[path][idx] = value

    def copyfile(self, the_file):
        for entry in the_file['/']:
            the_file.copy(entry, self['/']) 
        self._setattrs()

    def linkexternal(self, link):
        if os.path.isabs(link.nxfilename):
            link.nxfilename = os.path.relpath(link.nxfilename, 
                                              os.path.dirname(self.filename))
        if self._isexternal():
            current_link = self.get(self.nxpath, getlink=True)
            if current_link.filename == link.nxfilename and \
               current_link.path == link.nxtarget:
               return
            else:
                del self[self.nxpath]
        self[self.nxpath] = h5.ExternalLink(link.nxfilename, link.nxtarget)

    def _isexternal(self):
        return self.get(self.nxpath, getclass=True, getlink=True) == h5.ExternalLink

    def _setattrs(self):
        from datetime import datetime
        self._file.attrs['file_name'] = self.filename
        self._file.attrs['file_time'] = datetime.now().isoformat()
        self._file.attrs['HDF5_Version'] = h5.version.hdf5_version
        self._file.attrs['h5py_version'] = h5.version.version

    def update(self, item, path=None):
        if path is not None:
            self.nxpath = path
        else:
            self.nxpath = item.nxgroup.nxpath
        if isinstance(item, AttrDict):
            self._writeattrs(item)
        elif isinstance(item, NXlinkfield) or isinstance(item, NXlinkgroup):
            self._writelinks([(item.nxpath, item._target)])
        elif isinstance(item, NXfield):
            self._writedata(item)
        elif isinstance(item, NXgroup):
            links = self._writegroup(item)
            self._writelinks(links)

    def rename(self, old_path, new_path):
        self._file['/'].move(old_path, new_path)

    @property
    def filename(self):
        """File name on disk"""
        return self._file.filename

    def _getfile(self):
        return self._file

    def _getattrs(self):
        return dict(self[self.nxpath].attrs)

    def _getpath(self):
        return self._path.replace('//','/')

    def _setpath(self, value):
        self._path = value.replace('//','/')

    file = property(_getfile, doc="Property: File object of NeXus file")
    attrs = property(_getattrs, doc="Property: File object attributes")
    nxpath = property(_getpath, _setpath, doc="Property: Path to NeXus object")


def _getvalue(value, dtype=None, shape=None):
    """
    Returns a Numpy variable, dtype and shape based on the input Python value
    
    If the value is a masked array, the returned value is only returned as a 
    masked array if some of the elements are masked.

    If 'dtype' and/or 'shape' are specified as input arguments, the value is 
    converted to the given dtype and/or reshaped to the given shape. Otherwise, 
    the dtype and shape are determined from the value.
    """
    if isinstance(value, basestring):
        if value == '':
            value = ' '
        _value = np.string_(value)
    elif not isinstance(value, np.ndarray):
        _value = np.asarray(value)
    else:
        if isinstance(value, np.ma.MaskedArray):
            if value.count() < value.size:
                _value = value
            else:
                _value = np.asarray(value)
        else:
            _value = value
    if dtype is not None:
        if isinstance(dtype, basestring) and dtype == 'char':
            dtype = np.string_
        elif isinstance(value, np.bool_) and dtype != np.bool_:
            raise NeXusError("Cannot assign a Boolean value to a non-Boolean NXobject")
        _value = _value.astype(dtype)
    _dtype = _value.dtype
    if shape:
        try:
            _value = _value.reshape(shape)
        except ValueError:
            raise NeXusError("The shape of the assigned value is incompatible with the NXobject")
        _shape = tuple(shape)
    else:
        _shape = _value.shape
    return _value, _dtype, _shape


def _readaxes(axes):
    """
    Returns a list of axis names stored in the 'axes' attribute.

    The delimiter separating each axis can be white space, a comma, or a colon.
    """
    if axes.shape == ():
        axes = str(axes)
        import re
        sep=re.compile('[\[]*(\s*,*:*)+[\]]*')
        return filter(lambda x: len(x)>0, sep.split(axes))
    else:
        return list(axes)


class AttrDict(dict):

    """
    A dictionary class to assign all attributes to the NXattr class.
    """

    def __init__(self, parent=None):
        super(AttrDict, self).__init__()
        self.parent = parent

    def __getitem__(self, key):
        return super(AttrDict, self).__getitem__(key).nxdata

    def __setitem__(self, key, value):
        if isinstance(value, NXattr):
            super(AttrDict, self).__setitem__(key, value)
        else:
            super(AttrDict, self).__setitem__(key, NXattr(value))
        try:
            if self.parent.nxfilemode == 'rw':
                with self.parent.nxfile as f:
                    f.update(self, self.parent.nxpath)
        except Exception:
            pass

    def __delitem__(self, key):
        super(AttrDict, self).__delitem__(key)
        try:
            if self.parent.nxfilemode == 'rw':
                with self.parent.nxfile as f:
                    f.nxpath = self.parent.nxpath
                    del f[f.nxpath].attrs[key]
        except Exception:
            pass


class NXattr(object):

    """
    Class for NeXus attributes of a NXfield or NXgroup object.

    This class is only used for NeXus attributes that are stored in a
    NeXus file and helps to distinguish them from Python attributes.
    There are two Python attributes for each NeXus attribute.

    **Python Attributes**

    nxdata : string, Numpy scalar, or Numpy ndarray
        The value of the NeXus attribute.
    dtype : string
        The data type of the NeXus attribute. This is set to 'char' for
        a string attribute or the string of the corresponding Numpy data type
        for a numeric attribute.

    **NeXus Attributes**

    NeXus attributes are stored in the 'attrs' dictionary of the parent object,
    NXfield or NXgroup, but can often be referenced or assigned using the
    attribute name as if it were an object attribute.

    For example, after assigning the NXfield, the following three attribute
    assignments are all equivalent::

        >>> entry.sample.temperature = NXfield(40.0)
        >>> entry.sample.temperature.attrs['units'] = 'K'
        >>> entry.sample.temperature.units = NXattr('K')
        >>> entry.sample.temperature.units = 'K'

    The fourth version above is only allowed for NXfield attributes and is
    not allowed if the attribute has the same name as one of the following
    internally defined attributes, i.e.,

    ['entries', 'attrs', 'dtype','shape']

    or if the attribute name begins with 'nx' or '_'. It is only possible to
    reference attributes with one of the proscribed names using the 'attrs'
    dictionary.

    """

    def __init__(self, value=None, dtype=None):
        if isinstance(value, NXattr):
            value = value.nxdata
        elif isinstance(value, NXfield):
            if value.shape == ():
                value = value.nxdata
            else:
                raise NeXusError("A data attribute cannot be a NXfield or NXgroup")
        elif isinstance(value, NXgroup):
            raise NeXusError("A data attribute cannot be a NXgroup")
        self._value, self._dtype, _ = _getvalue(value, dtype)

    def __str__(self):
        return str(self.nxdata)

    def __repr__(self):
        if self.dtype.type == np.string_:
            return "NXattr('%s')"%self.nxdata
        else:
            return "NXattr(%s)"%self.nxdata

    def __eq__(self, other):
        """
        Returns true if the value of the attribute is the same as the other.
        """
        if isinstance(other, NXattr):
            return self.nxdata == other.nxdata
        else:
            return self.nxdata == other

    def _getdata(self):
        """
        Returns the attribute value.
        """
        if isinstance(self._value, np.string_):
            return self._value
        else:
            return self._value[()]

    def _getdtype(self):
        return self._dtype

    nxdata = property(_getdata,doc="Property: The attribute values")
    dtype = property(_getdtype, "Property: Data type of NeXus attribute")

_npattrs = filter(lambda x: not x.startswith('_'), np.ndarray.__dict__.keys())

class NXobject(object):

    """
    Abstract base class for elements in NeXus files.

    The object has a subclass of NXfield, NXgroup, or one of the NXgroup
    subclasses. Child nodes should be accessible directly as object attributes.
    Constructors for NXobject objects are defined by either the NXfield or
    NXgroup classes.

    **Python Attributes**

    nxclass : string
        The class of the NXobject. NXobjects can have class NXfield, NXgroup, or
        be one of the NXgroup subclasses.
    nxname : string
        The name of the NXobject. Since it is possible to reference the same
        Python object multiple times, this is not necessarily the same as the
        object name. However, if the object is part of a NeXus tree, this will
        be the attribute name within the tree.
    nxgroup : NXgroup
        The parent group containing this object within a NeXus tree. If the
        object is not part of any NeXus tree, it will be set to None.
    nxpath : string
        The path to this object with respect to the root of the NeXus tree. For
        NeXus data read from a file, this will be a group of class NXroot, but
        if the NeXus tree was defined interactively, it can be any valid
        NXgroup.
    nxroot : NXgroup
        The root object of the NeXus tree containing this object. For
        NeXus data read from a file, this will be a group of class NXroot, but
        if the NeXus tree was defined interactively, it can be any valid
        NXgroup.
    nxfile : NXFile
        The file handle of the root object of the NeXus tree containing this
        object.
    nxfilename : string
        The file name of NeXus object's tree file handle.
    attrs : dict
        A dictionary of the NeXus object's attributes.

    **Methods**

    dir(self, attrs=False, recursive=False):
        Print the group directory.

        The directory is a list of NeXus objects within this group, either NeXus
        groups or NXfield data. If 'attrs' is True, NXfield attributes are
        displayed. If 'recursive' is True, the contents of child groups are also
        displayed.

    tree:
        Return the object's tree as a string.

        It invokes the 'dir' method with both 'attrs' and 'recursive'
        set to True. Note that this is defined as a property attribute and
        does not require parentheses.

    save(self, filename, format='w')
        Save the NeXus group into a file

        The object is wrapped in an NXroot group (with name 'root') and an
        NXentry group (with name 'entry'), if necessary, in order to produce
        a valid NeXus file.

    """

    _class = "unknown"
    _name = "unknown"
    _group = None
    _file = None
    _filename = None
    _mode = None
    _target = None
    _memfile = None
    _uncopied_data = None
    _changed = True

    def __getstate__(self):
        result = self.__dict__.copy()
        hidden_keys = [key for key in result.keys() if key.startswith('_')]
        needed_keys = ['_class', '_name', '_group', '_entries', '_attrs', 
                       '_filename', '_mode', '_target', '_dtype', '_shape', 
                       '_value']
        for key in hidden_keys:
            if key not in needed_keys:
                del result[key]
        return result

    def __setstate__(self, dict):
        self.__dict__ = dict

    def __str__(self):
        return "%s:%s"%(self.nxclass,self.nxname)

    def __repr__(self):
        return "NXobject('%s','%s')"%(self.nxclass,self.nxname)

    def __contains__(self):
        return None

    def _setattrs(self, attrs):
        for k,v in attrs.items():
            self._attrs[k] = v

    def _str_name(self,indent=0):
        if self.nxclass == 'NXfield':
            return " "*indent+self.nxname
        else:
            return " "*indent+self.nxname+':'+self.nxclass

    def _str_value(self,indent=0):
        return ""

    def _str_attrs(self,indent=0):
        names = self.attrs.keys()
        names.sort()
        result = []
        for k in names:
            txt1, txt2, txt3 = ('', '', '') # only useful in source-level debugging
            txt1 = u" "*indent
            txt2 = u"@" + unicode(k)
            try:
                txt3 = u" = " + unicode(str(self.attrs[k]))
            except UnicodeDecodeError, err:
                # this is a wild assumption to read non-compliant strings from Soleil
                txt3 = u" = " + unicode(str(self.attrs[k]), "ISO-8859-1")
            txt = txt1 + txt2 + txt3
            result.append(txt)
        return "\n".join(result)

    def _str_tree(self,indent=0,attrs=False,recursive=False):
        """
        Prints the current object and children (if any).
        """
        result = [self._str_name(indent=indent)]
        if attrs and self.attrs:
            result.append(self._str_attrs(indent=indent+2))
        # Print children
        entries = self._entries
        if entries:
            names = entries.keys()
            names.sort()
            if recursive:
                for k in names:
                    result.append(entries[k]._str_tree(indent=indent+2,
                                                       attrs=attrs, recursive=True))
            else:
                for k in names:
                    result.append(entries[k]._str_name(indent=indent+2))
        return "\n".join(result)

    def walk(self):
        if False: 
            yield

    def dir(self, attrs=False, recursive=False):
        """
        Prints the object directory.

        The directory is a list of NeXus objects within this object, either
        NeXus groups or NXfields. If 'attrs' is True, NXfield attributes are
        displayed. If 'recursive' is True, the contents of child groups are
        also displayed.
        """
        print self._str_tree(attrs=attrs, recursive=recursive)

    @property
    def tree(self):
        """
        Returns the directory tree as a string.

        The tree contains all child objects of this object and their children.
        It invokes the 'dir' method with both 'attrs' and 'recursive' set
        to True.
        """
        return self._str_tree(attrs=True, recursive=True)

    def rename(self, name):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        if self.nxgroup is not None:
            axes = self.nxgroup.nxaxes
        path = self.nxpath
        self.nxname = name
        if self.nxgroup is not None:
            if self is self.nxgroup.nxsignal:
                self.nxgroup.nxsignal = self
            elif axes is not None:
                if [x for x in axes if x is self]:
                    self.nxgroup.nxaxes = axes
        if self.nxfilemode == 'rw':
            with self.nxfile as f:
                f.rename(path, self.nxpath)

    def save(self, filename=None, mode='w'):
        """
        Saves the NeXus object to a data file.
        
        If the object is an NXroot group, this can be used to save the whole
        NeXus tree. If the tree was read from a file and the file was opened as
        read only, then a file name must be specified. Otherwise, the tree is
        saved to the original file. 
        
        An error is raised if the object is an NXroot group from an external 
        file that has been opened as readonly and no file name is specified.

        If the object is not an NXroot, group, a filename must be specified. The
        saved NeXus object is wrapped in an NXroot group (with name 'root') and 
        an NXentry group (with name 'entry'), if necessary, in order to produce 
        a valid NeXus file. Only the children of the object will be saved. This 
        capability allows parts of a NeXus tree to be saved for later use, e.g., 
        to store an NXsample group to be added to another file at a later time. 
        
        **Example**

        >>> data = NXdata(sin(x), x)
        >>> data.save('file.nxs')
        >>> print data.nxroot.tree
        root:NXroot
          @HDF5_Version = 1.8.2
          @NeXus_version = 4.2.1
          @file_name = file.nxs
          @file_time = 2012-01-20T13:14:49-06:00
          entry:NXentry
            data:NXdata
              axis1 = float64(101)
              signal = float64(101)
                @axes = axis1
                @signal = 1              
        >>> root.entry.data.axis1.units = 'meV'
        >>> root.save()
        """
        if filename:
            if self.nxclass == "NXroot":
                root = self
            elif self.nxclass == "NXentry":
                root = NXroot(self)
            else:
                root = NXroot(NXentry(self))
            nx_file = NXFile(filename, mode)
            nx_file.writefile(root)
            root._filename = nx_file.file.filename
            root._setattrs(nx_file._getattrs())
            root._mode = nx_file._mode
            nx_file.close()
            return root
        else:
            raise NeXusError("No output file specified")

    def update(self):
        if self.nxfilemode == 'rw':
            with self.nxfile as f:
                f.update(self)
        self.set_changed()

    @property
    def changed(self):
        """
        Property: Returns True if the object has been changed.
        
        This property is for use by external scripts that need to track
        which NeXus objects have been changed.
        """
        return self._changed
    
    def set_changed(self):
        """
        Sets an object's change status to changed.
        """
        self._changed = True
        if self.nxgroup:
            self.nxgroup.set_changed()
            
    def set_unchanged(self, recursive=False):
        """
        Sets an object's change status to unchanged.
        """
        if recursive:
            for node in self.walk():
                node._changed = False
        else:
            self._changed = False
    
    def _getclass(self):
        return self._class

    def _setclass(self, class_):
        if isinstance(class_, basestring):
            class_ = globals()[class_]
        if issubclass(class_, NXobject):
            self.__class__ = class_
            self._class = self.__class__.__name__
            self.update()                   

    def _getname(self):
        return self._name

    def _setname(self, value):
        if self.nxgroup:
            self.nxgroup._entries[value] = self.nxgroup._entries[self._name]
            del self.nxgroup._entries[self._name]
        self._name = str(value)
        self.set_changed()                       

    def _getgroup(self):
        return self._group

    def _getpath(self):
        if self.nxgroup is None:
            return ""
        elif self.nxclass == 'NXroot':
            return "/"
        elif isinstance(self.nxgroup, NXroot):
            return "/" + self.nxname
        else:
            group_path = self.nxgroup._getpath()
            if group_path:
                return group_path+"/"+self.nxname
            else:
                return self.nxname

    def _getroot(self):
        if self.nxgroup is None or isinstance(self, NXroot):
            return self
        elif isinstance(self._group, NXroot):
            return self._group
        else:
            return self._group._getroot()

    def _getentry(self):
        if self.nxgroup is None or isinstance(self, NXentry):
            return self
        elif isinstance(self._group, NXentry):
            return self._group
        else:
            return self._group._getentry()

    def _getfile(self):
        if self._file:
            return self._file.open()
        _root = self.nxroot
        if _root._file:
            return _root._file.open()
        elif _root._filename:
            return NXFile(_root._filename, _root._mode)
        else:
            return None

    def _getfilename(self):
        if self.nxroot._filename:
            return self.nxroot._filename
        else:
            return ''

    def _getfilemode(self):
        return self.nxroot._mode

    def _gettarget(self):
        return self._target

    def _getattrs(self):
        return self._attrs

    nxclass = property(_getclass, _setclass, doc="Property: Class of NeXus object")
    nxname = property(_getname, _setname, doc="Property: Name of NeXus object")
    nxgroup = property(_getgroup, doc="Property: Parent group of NeXus object")
    nxpath = property(_getpath, doc="Property: Path to NeXus object")
    nxfile = property(_getfile, doc="Property: File handle of NeXus object's tree")
    nxfilename = property(_getfilename, doc="Property: Filename of NeXus object")
    nxfilemode = property(_getfilemode, doc="Property: File mode of root object")
    nxroot = property(_getroot, doc="Property: Root group of NeXus object's tree")
    nxentry = property(_getentry, doc="Property: Parent NXentry of NeXus object")
    nxtarget = property(_gettarget, doc="Property: Target of NeXus object")
    attrs = property(_getattrs, doc="Property: NeXus attributes for an object")


class NXfield(NXobject):

    """
    A NeXus data field.

    This is a subclass of NXobject that contains scalar, array, or string data
    and associated NeXus attributes.

    **Input Parameters**

    value : scalar value, Numpy array, or string
        The numerical or string value of the NXfield, which is directly
        accessible as the NXfield attribute 'nxdata'.
    name : string
        The name of the NXfield, which is directly accessible as the NXfield
        attribute 'name'. If the NXfield is initialized as the attribute of a
        parent object, the name is automatically set to the name of this
        attribute.
    dtype : string
        The data type of the NXfield value, which is directly accessible as the
        NXfield attribute 'dtype'. Valid input types correspond to standard
        Numpy data types, using names defined by the NeXus API, i.e.,
        'float32' 'float64'
        'int8' 'int16' 'int32' 'int64'
        'uint8' 'uint16' 'uint32' 'uint64'
        'char'
        If the data type is not specified, then it is determined automatically
        by the data type of the 'value' parameter.
    shape : list of ints
        The dimensions of the NXfield data, which is accessible as the NXfield
        attribute 'shape'. This corresponds to the shape of the Numpy array.
        Scalars (numeric or string) are stored as Numpy zero-rank arrays,
        for which shape=[].
    attrs : dict
        A dictionary containing NXfield attributes. The dictionary values should
        all have class NXattr.
    file : filename
        The file from which the NXfield has been read.
    path : string
        The path to this object with respect to the root of the NeXus tree,
        using the convention for unix file paths.
    group : NXgroup or subclass of NXgroup
        The parent NeXus object. If the NXfield is initialized as the attribute
        of a parent group, this attribute is automatically set to the parent group.

    **Python Attributes**

    nxclass : 'NXfield'
        The class of the NXobject.
    nxname : string
        The name of the NXfield. Since it is possible to reference the same
        Python object multiple times, this is not necessarily the same as the
        object name. However, if the field is part of a NeXus tree, this will
        be the attribute name within the tree.
    nxgroup : NXgroup
        The parent group containing this field within a NeXus tree. If the
        field is not part of any NeXus tree, it will be set to None.
    dtype : string or Numpy dtype
        The data type of the NXfield value. If the NXfield has been initialized
        but the data values have not been read in or defined, this is a string.
        Otherwise, it is set to the equivalent Numpy dtype.
    shape : list or tuple of ints
        The dimensions of the NXfield data. If the NXfield has been initialized
        but the data values have not been read in or defined, this is a list of
        ints. Otherwise, it is set to the equivalent Numpy shape, which is a
        tuple. Scalars (numeric or string) are stored as Numpy zero-rank arrays,
        for which shape=().
    attrs : dict
        A dictionary of all the NeXus attributes associated with the field.
        These are objects with class NXattr.
    nxdata : scalar, Numpy array or string
        The data value of the NXfield. This is normally initialized using the
        'value' parameter (see above). If the NeXus data is contained
        in a file and the size of the NXfield array is too large to be stored
        in memory, the value is not read in until this attribute is directly
        accessed. Even then, if there is insufficient memory, a value of None
        will be returned. In this case, the NXfield array should be read as a
        series of smaller slabs using 'get'.
    nxdata_as('units') : scalar value or Numpy array
        If the NXfield 'units' attribute has been set, the data values, stored
        in 'nxdata', are returned after conversion to the specified units.
    nxpath : string
        The path to this object with respect to the root of the NeXus tree. For
        NeXus data read from a file, this will be a group of class NXroot, but
        if the NeXus tree was defined interactively, it can be any valid
        NXgroup.
    nxroot : NXgroup
        The root object of the NeXus tree containing this object. For
        NeXus data read from a file, this will be a group of class NXroot, but
        if the NeXus tree was defined interactively, it can be any valid
        NXgroup.

    **NeXus Attributes**

    NeXus attributes are stored in the 'attrs' dictionary of the NXfield, but
    can usually be assigned or referenced as if they are Python attributes, as
    long as the attribute name is not the same as one of those listed above.
    This is to simplify typing in an interactive session and should not cause
    any problems because there is no name clash with attributes so far defined
    within the NeXus standard. When writing modules, it is recommended that the
    attributes always be referenced using the 'attrs' dictionary if there is
    any doubt.

    1) Assigning a NeXus attribute

       In the example below, after assigning the NXfield, the following three
       NeXus attribute assignments are all equivalent:

        >>> entry.sample.temperature = NXfield(40.0)
        >>> entry.sample.temperature.attrs['units'] = 'K'
        >>> entry.sample.temperature.units = NXattr('K')
        >>> entry.sample.temperature.units = 'K'

    2) Referencing a NeXus attribute

       If the name of the NeXus attribute is not the same as any of the Python
       attributes listed above, or one of the methods listed below, or any of the
       attributes defined for Numpy arrays, they can be referenced as if they were
       a Python attribute of the NXfield. However, it is only possible to reference
       attributes with one of the proscribed names using the 'attrs' dictionary.

        >>> entry.sample.temperature.tree = 10.0
        >>> entry.sample.temperature.tree
        temperature = 40.0
          @tree = 10.0
          @units = K
        >>> entry.sample.temperature.attrs['tree']
        NXattr(10.0)

    **Numerical Operations on NXfields**

    NXfields usually consist of arrays of numeric data with associated
    meta-data, the NeXus attributes. The exception is when they contain
    character strings. This makes them similar to Numpy arrays, and this module
    allows the use of NXfields in numerical operations in the same way as Numpy
    ndarrays. NXfields are technically not a sub-class of the ndarray class, but
    most Numpy operations work on NXfields, returning either another NXfield or,
    in some cases, an ndarray that can easily be converted to an NXfield.

        >>> x = NXfield((1.0,2.0,3.0,4.0))
        >>> print x+1
        [ 2.  3.  4.  5.]
        >>> print 2*x
        [ 2.  4.  6.  8.]
        >>> print x/2
        [ 0.5  1.   1.5  2. ]
        >>> print x**2
        [  1.   4.   9.  16.]
        >>> print x.reshape((2,2))
        [[ 1.  2.]
         [ 3.  4.]]
        >>> y = NXfield((0.5,1.5,2.5,3.5))
        >>> x+y
        NXfield(name=x,value=[ 1.5  3.5  5.5  7.5])
        >>> x*y
        NXfield(name=x,value=[  0.5   3.    7.5  14. ])
        >>> (x+y).shape
        (4,)
        >>> (x+y).dtype
        dtype('float64')

    All these operations return valid NXfield objects containing the same
    attributes as the first NXobject in the expression. The 'reshape' and
    'transpose' methods also return NXfield objects.

    It is possible to use the standard slice syntax.

        >>> x=NXfield(np.linspace(0,10,11))
        >>> x
        NXfield([  0.   1.   2. ...,   8.   9.  10.])
        >>> x[2:5]
        NXfield([ 2.  3.  4.])

    In addition, it is possible to use floating point numbers as the slice
    indices. If one of the indices is not integer, both indices are used to
    extract elements in the array with values between the two index values.

        >>> x=NXfield(np.linspace(0,100.,11))
        >>> x
        NXfield([   0.   10.   20. ...,   80.   90.  100.])
        >>> x[20.:50.]
        NXfield([ 20.  30.  40.  50.])

    The standard Numpy ndarray attributes and methods will also work with
    NXfields, but will return scalars or Numpy arrays.

        >>> x.size
        4
        >>> x.sum()
        10.0
        >>> x.max()
        4.0
        >>> x.mean()
        2.5
        >>> x.var()
        1.25
        >>> x.reshape((2,2)).sum(1)
        array([ 3.,  7.])

    Finally, NXfields are cast as ndarrays for operations that require them.
    The returned value will be the same as for the equivalent ndarray
    operation, e.g.,

    >>> np.sin(x)
    array([ 0.84147098,  0.90929743,  0.14112001, -0.7568025 ])
    >>> np.sqrt(x)
    array([ 1.        ,  1.41421356,  1.73205081,  2.        ])

    **Methods**

    dir(self, attrs=False):
        Print the NXfield specification.

        This outputs the name, dimensions and data type of the NXfield.
        If 'attrs' is True, NXfield attributes are displayed.

    tree:
        Returns the NXfield's tree.

        It invokes the 'dir' method with both 'attrs' and 'recursive'
        set to True. Note that this is defined as a property attribute and
        does not require parentheses.


    save(self, filename, format='w5')
        Save the NXfield into a file wrapped in a NXroot group and NXentry group
        with default names. This is equivalent to

        >>> NXroot(NXentry(NXfield(...))).save(filename)

    **Examples**

    >>> x = NXfield(np.linspace(0,2*np.pi,101), units='degree')
    >>> phi = x.nxdata_as(units='radian')
    >>> y = NXfield(np.sin(phi))
    >>> # Read a Ni x Nj x Nk array one vector at a time
    >>> with root.NXentry[0].data.data as slab:
            Ni,Nj,Nk = slab.shape
            size = [1,1,Nk]
            for i in range(Ni):
                for j in range(Nj):
                    value = slab.get([i,j,0],size)

    """

    def __init__(self, value=None, name='field', dtype=None, shape=(), group=None,
                 attrs=None, **attr):
        self._class = 'NXfield'
        self._value = value
        self._name = name
        self._group = group
        self._dtype = dtype
        if dtype:
            if dtype == 'char':
                dtype = 'S'
            try:
                self._dtype = np.dtype(dtype)
            except Exception:
                raise NeXusError("Invalid data type: %s" % dtype)
        if isinstance(shape, int):
            shape = [shape]
        self._shape = tuple(shape)
        # Append extra keywords to the attribute list
        if not attrs:
            attrs = {}
        # Store h5py attributes as private variables
        if 'maxshape' in attr:
            self._maxshape = attr['maxshape']
            del attr['maxshape']
        else:
            self._maxshape = None
        if 'compression' in attr:
            self._compression = attr['compression']
            del attr['compression']
        else:
            self._compression = None
        if 'chunks' in attr:
            self._chunks = attr['chunks']
            del attr['chunks']
        else:
            self._chunks = None
        if 'fillvalue' in attr:
            self._fillvalue = attr['fillvalue']
            del attr['fillvalue']
        else:
            self._fillvalue = None
        for key in attr.keys():
            attrs[key] = attr[key]
        # Convert NeXus attributes to python attributes
        self._attrs = AttrDict(self)
        self._setattrs(attrs)
        del attrs
        self._masked = False
        self._filename = None
        self._memfile = None
        if value is not None:
            self._value, self._dtype, self._shape = \
                _getvalue(value, self._dtype, self._shape)
        self.set_changed()

    def __repr__(self):
        if self._value is not None:
            if self.dtype.type == np.string_:
                return "NXfield('%s')" % str(self)
            else:
                return "NXfield(%s)" % self._str_value()
        else:
            return "NXfield(dtype=%s,shape=%s)" % (self.dtype,self.shape)

    def __getattr__(self, name):
        """
        Enables standard numpy ndarray attributes if not otherwise defined.
        """
        name = name
        if name.startswith(u'_'):
            return object.__getattribute__(self, name)
        elif name in _npattrs:
            return object.__getattribute__(self.nxdata, name)
        elif name in self.attrs:
            return self.attrs[name]
        raise KeyError(name+" not in "+self.nxname)

    def __setattr__(self, name, value):
        """
        Adds an attribute to the NXfield 'attrs' dictionary unless the attribute
        name starts with 'nx' or '_', or unless it is one of the standard Python
        attributes for the NXfield class.
        """
        if name.startswith('_') or name.startswith('nx') or \
           name == 'mask' or name == 'shape' or name == 'dtype':
            if isinstance(value, NXfield):
                value = value.nxdata
            object.__setattr__(self, name, value)
            return
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        self._attrs[name] = value
        self.set_changed()

    def __delattr__(self, name):
        """
        Deletes an attribute in the NXfield 'attrs' dictionary.
        """
        if name in self.attrs:
            del self.attrs[name]
        self.set_changed()

    def __getitem__(self, idx):
        """
        Returns a slice from the NXfield.

        In most cases, the slice values are applied to the NXfield nxdata array
        and returned within an NXfield object with the same metadata. However,
        if the array is one-dimensional and the index start and stop values
        are real, the nxdata array is returned with values between those limits.
        This is to allow axis arrays to be limited by their actual value. This
        real-space slicing should only be used on monotonically increasing (or
        decreasing) one-dimensional arrays.
        """
        idx = convert_index(idx,self)
        if len(self) == 1:
            result = self
        elif self._value is None:
            if self._uncopied_data:
                self._get_uncopied_data()
            if self.nxfilemode:
                result = self._get_filedata(idx)
            elif self._memfile:
                result = self._get_memdata(idx)
                mask = self.mask
                if not mask is None:
                    if isinstance(mask, NXfield):
                        mask = mask[idx].nxdata
                    else:
                        mask = mask[idx]
                    if isinstance(result, np.ma.MaskedArray):
                        result = result.data
                    result = np.ma.array(result, mask=mask)
            else:
                raise NeXusError('Data not available either in file or in memory')
        else:
            result = self.nxdata.__getitem__(idx)
        return NXfield(result, name=self.nxname, attrs=self.attrs)

    def __setitem__(self, idx, value):
        """
        Assigns a slice to the NXfield.
        """
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        if value is np.ma.masked:
            self._mask_data(idx)
        else:
            if isinstance(value, np.bool_) and self.dtype != np.bool_:
                raise NeXusError('Cannot set a Boolean value to a non-Boolean data type')
            if self._value is not None:
                self._value[idx] = value
            if self.nxfilemode == 'rw':
                self._put_filedata(idx, value)
            elif self._value is None:
                self._put_memdata(idx, value)
        self.set_changed()

    def _get_filedata(self, idx=()):
        with self.nxfile as f:
            result = f.readvalue(self.nxpath, idx=idx)
            if 'mask' in self.attrs:
                try:
                    mask = self.nxgroup[self.attrs['mask']]
                    result = np.ma.array(result, 
                                         mask=f.readvalue(mask.nxpath, idx=idx))
                except KeyError:
                    pass
        return result

    def _put_filedata(self, idx, value):
        with self.nxfile as f:
            if isinstance(value, np.ma.MaskedArray):
                if self.mask is None:
                    self._create_mask()
                f.writevalue(self.nxpath, value.data, idx=idx)
                f.writevalue(self.mask.nxpath, value.mask, idx=idx)
            else:
                f.writevalue(self.nxpath, value, idx=idx)

    def _get_memdata(self, idx=()):
        result = self._memfile['data'][idx]
        if 'mask' in self._memfile:
            result = np.ma.array(result, mask=self._memfile['mask'][idx])
        return result
    
    def _put_memdata(self, idx, value):
        if self._memfile is None:
            self._create_memfile()
        if 'data' not in self._memfile:
            self._create_memdata()
        self._memfile['data'][idx] = value
        if isinstance(value, np.ma.MaskedArray):
            if 'mask' not in self._memfile:
                self._create_memmask()
            self._memfile['mask'][idx] = value.mask
    
    def _create_memfile(self):
        """
        Creates an HDF5 memory-mapped file to store the data
        """
        import tempfile
        self._memfile = h5.File(tempfile.mktemp(suffix='.nxs'),
                               driver='core', backing_store=False).file

    def _create_memdata(self):
        """
        Creates an HDF5 memory-mapped dataset to store the data
        """
        if self._shape is not None and self._dtype is not None:
            if self._memfile is None:
                self._create_memfile()
            self._memfile.create_dataset('data', shape=self._shape, 
                                         dtype=self._dtype, 
                                         compression='gzip', chunks=True)
        else:
            raise NeXusError('Cannot allocate to field before setting shape and dtype')       

    def _create_memmask(self):
        """
        Creates an HDF5 memory-mapped dataset to store the data mask
        """
        if self._shape is not None:
            if self._memfile is None:
                self._create_memfile()
            self._memfile.create_dataset('mask', shape=self._shape, 
                                         dtype=np.bool, 
                                         compression='gzip', chunks=True)
        else:
            raise NeXusError('Cannot allocate mask before setting shape')       

    def _create_mask(self):
        """
        Create a data mask field if none exists
        """
        if self.nxgroup:
            if 'mask' in self.attrs:
                mask_name = self.attrs['mask']
                if mask_name in self.nxgroup:
                    return mask_name
            mask_name = '%s_mask' % self.nxname
            self.nxgroup[mask_name] = NXfield(shape=self._shape, dtype=np.bool, 
                                              fillvalue=False)
            self.attrs['mask'] = mask_name
            return mask_name
        return None      

    def _mask_data(self, idx=()):
        """
        Add a data mask covering the specified indices
        """
        mask_name = self._create_mask()
        if mask_name:
            self.nxgroup[mask_name][idx] = True
        elif self._memfile:
            if 'mask' not in self._memfile:
                self._create_memmask()
            self._memfile['mask'][idx] = True
        if self._value is not None:
            if not isinstance(self._value, np.ma.MaskedArray):
                self._value = np.ma.array(self._value)
            self._value[idx] = np.ma.masked

    def _get_uncopied_data(self):
        _file, _path = self._uncopied_data
        with _file as f:
            if self.nxfilemode == 'rw':
                f.copy(_path, self.nxpath)
            else:
                self._create_memfile()
                f.copy(_path, self._memfile, 'data')
        self._uncopied_data = None

    def __deepcopy__(self, memo):
        if isinstance(self, NXlink):
            obj = self.nxlink
        else:
            obj = self
        dpcpy = obj.__class__()
        memo[id(self)] = dpcpy
        dpcpy._name = copy(obj.nxname)
        dpcpy._dtype = copy(obj.dtype)
        dpcpy._shape = copy(obj.shape)
        dpcpy._changed = True
        dpcpy._memfile = None
        dpcpy._uncopied_data = None
        if obj._value is not None:
            dpcpy._value = copy(obj._value)
        elif obj._memfile:
            dpcpy._memfile = obj._memfile
        elif obj.nxfilemode:
            dpcpy._uncopied_data = (obj.nxfile, obj.nxpath)
        for k, v in obj.attrs.items():
            dpcpy.attrs[k] = copy(v)
        if 'target' in dpcpy.attrs:
            del dpcpy.attrs['target']
        return dpcpy

    def __len__(self):
        """
        Returns the length of the NXfield data.
        """
        return int(np.prod(self.shape))

    def index(self, value, max=False):
        """
        Returns the index of the NXfield array that is greater than or equal to 
        the value.

        If max, then return the index that is less than or equal to the value.
        This should only be used on one-dimensional monotonically increasing 
        arrays.
        """
        if max:
            idx = np.max(len(self.nxdata)-len(self.nxdata[self.nxdata>value])-1,0)
            try:
                diff = value - self.nxdata[idx]
                step = self.nxdata[idx+1] - self.nxdata[idx]
                if diff/step > 0.01:
                    idx = idx + 1
            except IndexError:
                pass
            return idx
        else:
            idx = len(self.nxdata[self.nxdata<value])
            try:
                diff = value - self.nxdata[idx-1]
                step = self.nxdata[idx] - self.nxdata[idx-1]
                if diff/step < 0.99:
                    idx = idx - 1
            except IndexError:
                pass
            return idx

    def __array__(self):
        """
        Casts the NXfield as an array when it is expected by numpy
        """
        return self.nxdata

    def __array_wrap__(self, value):
        """
        Transforms the array resulting from a ufunc to an NXfield
        """
        return NXfield(value, name=self.nxname)

    def __int__(self):
        """
        Casts a scalar field as an integer
        """
        return int(self.nxdata)

    def __long__(self):
        """
        Casts a scalar field as a long integer
        """
        return long(self.nxdata)

    def __float__(self):
        """
        Casts a scalar field as floating point number
        """
        return float(self.nxdata)

    def __complex__(self):
        """
        Casts a scalar field as a complex number
        """
        return complex(self.nxdata)

    def __neg__(self):
        """
        Returns the negative value of a scalar field
        """
        return -self.nxdata

    def __abs__(self):
        """
        Returns the absolute value of a scalar field
        """
        return abs(self.nxdata)

    def __eq__(self, other):
        """
        Returns true if the values of the NXfield are the same.
        """
        if isinstance(other, NXfield):
            if isinstance(self.nxdata, np.ndarray) and isinstance(other.nxdata, np.ndarray):
                return all(self.nxdata == other.nxdata)
            else:
                return self.nxdata == other.nxdata
        else:
            return False

    def __ne__(self, other):
        """
        Returns true if the values of the NXfield are not the same.
        """
        if isinstance(other, NXfield):
            if isinstance(self.nxdata, np.ndarray) and isinstance(other.nxdata, np.ndarray):
                return any(self.nxdata != other.nxdata)
            else:
                return self.nxdata != other.nxdata
        else:
            return True

    def __lt__(self, other):
        """
        Returns true if self.nxdata < other[.nxdata]
        """
        if isinstance(other, NXfield):
            return self.nxdata < other.nxdata
        else:
            return self.nxdata < other

    def __le__(self, other):
        """
        Returns true if self.nxdata <= other[.nxdata]
        """
        if isinstance(other, NXfield):
            return self.nxdata <= other.nxdata
        else:
            return self.nxdata <= other

    def __gt__(self, other):
        """
        Returns true if self.nxdata > other[.nxdata]
        """
        if isinstance(other, NXfield):
            return self.nxdata > other.nxdata
        else:
            return self.nxdata > other

    def __ge__(self, other):
        """
        Returns true if self.nxdata >= other[.nxdata]
        """
        if isinstance(other, NXfield):
            return self.nxdata >= other.nxdata
        else:
            return self.nxdata >= other

    def __add__(self, other):
        """
        Returns the sum of the NXfield and another NXfield or number.
        """
        if isinstance(other, NXfield):
            return NXfield(value=self.nxdata+other.nxdata, name=self.nxname,
                           attrs=self.attrs)
        else:
            return NXfield(value=self.nxdata+other, name=self.nxname,
                           attrs=self.attrs)
 
    def __radd__(self, other):
        """
        Returns the sum of the NXfield and another NXfield or number.

        This variant makes __add__ commutative.
        """
        return self.__add__(other)

    def __sub__(self, other):
        """
        Returns the NXfield with the subtraction of another NXfield or number.
        """
        if isinstance(other, NXfield):
            return NXfield(value=self.nxdata-other.nxdata, name=self.nxname,
                           attrs=self.attrs)
        else:
            return NXfield(value=self.nxdata-other, name=self.nxname,
                           attrs=self.attrs)

    def __mul__(self, other):
        """
        Returns the product of the NXfield and another NXfield or number.
        """
        if isinstance(other, NXfield):
            return NXfield(value=self.nxdata*other.nxdata, name=self.nxname,
                           attrs=self.attrs)
        else:
            return NXfield(value=self.nxdata*other, name=self.nxname,
                          attrs=self.attrs)

    def __rmul__(self, other):
        """
        Returns the product of the NXfield and another NXfield or number.

        This variant makes __mul__ commutative.
        """
        return self.__mul__(other)

    def __div__(self, other):
        """
        Returns the NXfield divided by another NXfield or number.
        """
        if isinstance(other, NXfield):
            return NXfield(value=self.nxdata/other.nxdata, name=self.nxname,
                           attrs=self.attrs)
        else:
            return NXfield(value=self.nxdata/other, name=self.nxname,
                           attrs=self.attrs)

    def __rdiv__(self, other):
        """
        Returns the inverse of the NXfield divided by another NXfield or number.
        """
        if isinstance(other, NXfield):
            return NXfield(value=other.nxdata/self.nxdata, name=self.nxname,
                           attrs=self.attrs)
        else:
            return NXfield(value=other/self.nxdata, name=self.nxname,
                           attrs=self.attrs)

    def __pow__(self, power):
        """
        Returns the NXfield raised to the specified power.
        """
        return NXfield(value=pow(self.nxdata,power), name=self.nxname,
                       attrs=self.attrs)

    def min(self, axis=None):
        """
        Returns the minimum value of the array ignoring NaNs
        """
        return np.nanmin(self.nxdata, axis) 

    def max(self, axis=None):
        """
        Returns the maximum value of the array ignoring NaNs
        """
        return np.nanmax(self.nxdata, axis) 

    def reshape(self, shape):
        """
        Returns an NXfield with the specified shape.
        """
        return NXfield(value=self.nxdata, name=self.nxname, shape=shape,
                       attrs=self.attrs)

    def transpose(self):
        """
        Returns an NXfield containing the transpose of the data array.
        """
        return NXfield(value=self.nxdata.transpose(), name=self.nxname,
                       attrs=self.attrs)

    @property
    def T(self):
        return self.transpose()

    def centers(self):
        """
        Returns an NXfield with the centers of a single axis
        assuming it contains bin boundaries.
        """
        return NXfield((self.nxdata[:-1]+self.nxdata[1:])/2,
                        name=self.nxname,attrs=self.attrs)

    def add(self, data, offset):
        """
        Adds a slab into the data array.
        """
        idx = tuple(slice(i,i+j) for i,j in zip(offset,data.shape))
        if isinstance(data, NXfield):
            self[idx] += data.nxdata.astype(self.dtype)
        else:
            self[idx] += data.astype(self.dtype)

    def convert(self, units=""):
        """
        Returns the data in the requested units.
        """
        try:
            import units
        except ImportError:
            raise NeXusError("No conversion utility available")
        if self._value is not None:
            return self._converter(self._value,units)
        else:
            return None

    def __str__(self):
        """
        If value is loaded, return the value as a string.  If value is
        not loaded, return the empty string.  Only the first view values
        for large arrays will be printed.
        """
        if self._value is not None:
            if self.dtype.kind == 'S' and self.shape <> ():
                return '\n'.join([t for t in self._value.flatten()])
            else:
                return str(self._value)
        return ""

    def _str_value(self,indent=0):
        v = str(self)
        if '\n' in v:
            v = '\n'.join([(" "*indent)+s for s in v.split('\n')])
        return v

    def _str_tree(self, indent=0, attrs=False, recursive=False):
        dims = 'x'.join([str(n) for n in self.shape])
        s = unicode(str(self), 'utf-8')
        if '\n' in s or s == "":
            s = "%s(%s)" % (self.dtype, dims)
        elif len(s) > 80:
            s = s[0:77]+'...'
        try:
            v=[" "*indent + "%s = %s"%(self.nxname, s)]
        except Exception:
            v=[" "*indent + self.nxname]
        if attrs and self.attrs:
            v.append(self._str_attrs(indent=indent+2))
        return "\n".join(v)

    def walk(self):
        yield self

    def _getaxes(self):
        """
        Returns a list of NXfields containing axes.

        Only works if the NXfield has the 'axes' attribute
        """
        try:
            return [getattr(self.nxgroup,name) 
                    for name in _readaxes(self.attrs['axes'])]
        except KeyError:
            return None

    def _getdata(self):
        """
        Returns the data if it is not larger than NX_MEMORY.
        """
        if self._value is None:
            if np.prod(self.shape) * np.dtype(self.dtype).itemsize <= NX_MEMORY*1024*1024:
                if self.nxfilemode:
                    self._value = self._get_filedata()
                elif self._uncopied_data:
                    self._get_uncopied_data()
                if self._memfile:
                    self._value = self._get_memdata()
                    self._memfile = None
                if self._value is not None:
                    self._value.shape = self._shape
            else:
                raise NeXusError('Data size larger than NX_MEMORY=%s MB' % NX_MEMORY)
        if not self.mask is None:
            try:
                if isinstance(self.mask, NXfield):
                    mask = self.mask.nxdata
                if isinstance(self._value, np.ma.MaskedArray):
                    self._value = np.ma.array(self._value.data, mask=mask)
                else:
                    self._value = np.ma.array(self._value, mask=mask)
            except Exception:
                pass
        return self._value

    def _setdata(self, value):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file is locked')
        else:
            self._value, self._dtype, self._shape = \
                _getvalue(value, self._dtype, self._shape)
            self.update()

    def _title(self):
        """
        Returns the title as a string.

        If there is no title attribute in the parent group, the group's path is 
        returned.
        """
        parent = self.nxgroup
        if parent:
            if 'title' in parent:
                return str(parent.title)
            elif parent.nxgroup and 'title' in parent.nxgroup:
                return str(parent.nxgroup.title)        
        else:
            if self.nxroot.nxname != '' and self.nxroot.nxname != 'root':
                return (self.nxroot.nxname + '/' + self.nxpath.lstrip('/')).rstrip('/')
            else:
                return self.nxfilename + ':' + self.nxpath

    def _getmask(self):
        """
        Returns the NXfield's mask as an array

        Only works if the NXfield is in a group and has the 'mask' attribute set
        or if the NXfield array is defined as a masked array.
        """
        if 'mask' in self.attrs:
            if self.nxgroup:
                try:
                    return self.nxgroup[self.attrs['mask']]
                except KeyError:
                    pass
            del self.attrs['mask']
        if self._value is None and self._memfile:
            if 'mask' in self._memfile:
                return self._memfile['mask']      
        if self._value is not None and isinstance(self._value, 
                                                  np.ma.MaskedArray):
            return self._value.mask
        return None

    def _setmask(self, value):
        if 'mask' in self.attrs:
            if self.nxgroup:
                mask_name = self.attrs['mask']
                if mask_name in self.nxgroup:
                    self.nxgroup[mask_name][()] = value
            else:
                del self.attrs['mask']
        elif self._value is None:
            if self._memfile:
                self._create_memmask()
                self._memfile['mask'][()] = value
        if self._value is not None:
            self._value = np.ma.array(self._value, mask=value)

    def _getdtype(self):
        return self._dtype

    def _setdtype(self, value):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file is locked')
        elif self.nxfilemode == 'rw':
            raise NeXusError('Cannot change the dtype of a field already stored in a file')
        self._dtype = np.dtype(value)
        if self._value is not None:
            self._value = np.asarray(self._value, dtype=self._dtype)

    def _getshape(self):
        return self._shape

    def _setshape(self, value):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file is locked')
        elif self.nxfilemode == 'rw':
            raise NeXusError('Cannot change the shape of a field already stored in a file')
        if self._value is not None:
            if self._value.size != np.prod(value):
                raise ValueError('Total size of new array must be unchanged')
            self._value.shape = tuple(value)
        self._shape = tuple(value)

    def _getndim(self):
        return len(self.shape)

    def _getsize(self):
        return len(self)

    nxdata = property(_getdata, _setdata, doc="Property: The data values")
    nxaxes = property(_getaxes, doc="Property: The plotting axes")
    nxtitle = property(_title, "Property: Title for group plot")
    mask = property(_getmask, _setmask, doc="Property: The data mask")
    dtype = property(_getdtype, _setdtype, 
                     doc="Property: Data type of NeXus field")
    shape = property(_getshape, _setshape, doc="Property: Shape of NeXus field")
    ndim = property(_getndim, doc="Property: No. of dimensions of NeXus field")
    size = property(_getsize, doc="Property: Size of NeXus field")

    @property
    def plot_shape(self):     
        _shape = list(self.shape)
        while 1 in _shape:
            _shape.remove(1)
        return _shape

    @property
    def plot_rank(self):
        return len(self.plot_shape)

    def is_plottable(self):
        if self.plot_rank > 0:
            return True
        else:
            return False

    def plot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             zmin=None, zmax=None, **opts):
        """
        Plot data if the signal attribute is defined.

        The format argument is used to set the color and type of the
        markers or lines for one-dimensional plots, using the standard 
        Mtplotlib syntax. The default is set to blue circles. All 
        keyword arguments accepted by matplotlib.pyplot.plot can be
        used to customize the plot.
        
        In addition to the matplotlib keyword arguments, the following
        are defined::
        
            log = True     - plot the intensity on a log scale
            logy = True    - plot the y-axis on a log scale
            logx = True    - plot the x-axis on a log scale
            over = True    - plot on the current figure
            image = True   - plot as an RGB(A) image

        Raises NeXusError if the data could not be plotted.
        """

        from nexpy.gui.plotview import plotview

        if self.is_plottable():
            if 'axes' in self.attrs.keys():
                axes = [getattr(self.nxgroup, name) 
                        for name in _readaxes(self.attrs['axes'])]
                data = NXdata(self, axes, title=self.nxtitle)
            else:
                data = NXdata(self, title=self.nxtitle)
            plotview.plot(data, fmt, xmin, xmax, ymin, ymax, zmin, zmax, **opts)
        else:
            raise NeXusError('NXfield not plottable')
    
    def oplot(self, fmt='', **opts):
        """
        Plots the data contained within the group over the current figure.
        """
        self.plot(fmt=fmt, over=True, **opts)

    def logplot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
                zmin=None, zmax=None, **opts):
        """
        Plots the data intensity contained within the group on a log scale.
        """
        self.plot(fmt=fmt, log=True,
                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
                  zmin=zmin, zmax=zmax, **opts)

    def implot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
                zmin=None, zmax=None, **opts):
        """
        Plots the data intensity as an RGB(A) image.
        """
        if self.plot_rank > 2 and (self.shape[-1] == 3 or self.shape[-1] == 4):
            self.plot(fmt=fmt, image=True,
                      xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
                      zmin=zmin, zmax=zmax, **opts)
        else:
            raise NeXusError('Invalid shape for RGB(A) image')

SDS = NXfield # For backward compatibility


class NXgroup(NXobject):

    """
    A NeXus group object.

    This is a subclass of NXobject and is the base class for the specific
    NeXus group classes, e.g., NXentry, NXsample, NXdata.

    **Parameters**

    The NXgroup parameters consist of a list of positional and/or keyword
    arguments.

    Positional Arguments: 
        These must be valid NeXus objects, either an NXfield or a NeXus group. 
        These are added without modification as children of this group.

    Keyword Arguments: 
        Apart from a list of special keywords shown below, keyword arguments are
        used to add children to the group using the keywords as attribute names. 
        The values can either be valid NXfields or NXgroups, in which case the 
        'name' attribute is changed to the keyword, or they can be numerical or 
        string data, which are converted to NXfield objects.

    Special Keyword Arguments:

        name : string
            The name of the NXgroup, which is directly accessible as the NXgroup
            attribute 'name'. If the NXgroup is initialized as the attribute of
            a parent group, the name is automatically set to the name of this
            attribute. If 'nxclass' is specified and has the usual prefix 'NX',
            the default name is the class name without this prefix.
        nxclass : string
            The class of the NXgroup.
        entries : dict
            A dictionary containing a list of group entries. This is an
            alternative way of adding group entries to the use of keyword
            arguments.
        file : filename
            The file from which the NXfield has been read.
        path : string
            The path to this object with respect to the root of the NeXus tree,
            using the convention for unix file paths.
        group : NXobject (NXgroup or subclass of NXgroup)
            The parent NeXus group, which is accessible as the group attribute
            'group'. If the group is initialized as the attribute of
            a parent group, this is set to the parent group.

    **Python Attributes**

    nxclass : string
        The class of the NXobject.
    nxname : string
        The name of the NXfield.
    entries : dictionary
        A dictionary of all the NeXus objects contained within an NXgroup.
    attrs : dictionary
        A dictionary of all the NeXus attributes, i.e., attribute with class NXattr.
    entries : dictionary
        A dictionary of all the NeXus objects contained within the group.
    attrs : dictionary
        A dictionary of all the group's NeXus attributes, which all have the
        class NXattr.
    nxpath : string
        The path to this object with respect to the root of the NeXus tree. For
        NeXus data read from a file, this will be a group of class NXroot, but
        if the NeXus tree was defined interactively, it can be any valid
        NXgroup.
    nxroot : NXgroup
        The root object of the NeXus tree containing this object. For
        NeXus data read from a file, this will be a group of class NXroot, but
        if the NeXus tree was defined interactively, it can be any valid
        NXgroup.

    **NeXus Group Entries**

    Just as in a NeXus file, NeXus groups can contain either data or other
    groups, represented by NXfield and NXgroup objects respectively. To
    distinguish them from regular Python attributes, all NeXus objects are
    stored in the 'entries' dictionary of the NXgroup. However, they can usually
    be assigned or referenced as if they are Python attributes, i.e., using the
    dictionary name directly as the group attribute name, as long as this name
    is not the same as one of the Python attributes defined above or as one of
    the NXfield Python attributes.

    1) Assigning a NeXus object to a NeXus group

        In the example below, after assigning the NXgroup, the following three
        NeXus object assignments to entry.sample are all equivalent:

        >>> entry.sample = NXsample()
        >>> entry.sample['temperature'] = NXfield(40.0)
        >>> entry.sample.temperature = NXfield(40.0)
        >>> entry.sample.temperature = 40.0
        >>> entry.sample.temperature
        NXfield(40.0)

        If the assigned value is not a valid NXobject, then it is cast as an NXfield
        with a type determined from the Python data type.

        >>> entry.sample.temperature = 40.0
        >>> entry.sample.temperature
        NXfield(40.0)
        >>> entry.data.data.x=np.linspace(0,10,11).astype('float32')
        >>> entry.data.data.x
        NXfield([  0.   1.   2. ...,   8.   9.  10.])

    2) Referencing a NeXus object in a NeXus group

        If the name of the NeXus object is not the same as any of the Python
        attributes listed above, or the methods listed below, they can be referenced
        as if they were a Python attribute of the NXgroup. However, it is only possible
        to reference attributes with one of the proscribed names using the group
        dictionary, i.e.,

        >>> entry.sample.tree = 100.0
        >>> print entry.sample.tree
        sample:NXsample
          tree = 100.0
        >>> entry.sample['tree']
        NXfield(100.0)

        For this reason, it is recommended to use the group dictionary to reference
        all group objects within Python scripts.

    **NeXus Attributes**

    NeXus attributes are not currently used much with NXgroups, except for the
    root group, which has a number of global attributes to store the file name,
    file creation time, and NeXus and HDF version numbers. However, the
    mechanism described for NXfields works here as well. All NeXus attributes
    are stored in the 'attrs' dictionary of the NXgroup, but can be referenced
    as if they are Python attributes as long as there is no name clash.

        >>> entry.sample.temperature = 40.0
        >>> entry.sample.attrs['tree'] = 10.0
        >>> print entry.sample.tree
        sample:NXsample
          @tree = 10.0
          temperature = 40.0
        >>> entry.sample.attrs['tree']
        NXattr(10.0)

    **Methods**

    insert(self, NXobject, name='unknown'):
        Insert a valid NXobject (NXfield or NXgroup) into the group.

        If NXobject has a 'name' attribute and the 'name' keyword is not given,
        then the object is inserted with the NXobject name.

    makelink(self, NXobject):
        Add the NXobject to the group entries as a link (NXlink).

    dir(self, attrs=False, recursive=False):
        Print the group directory.

        The directory is a list of NeXus objects within this group, either NeXus
        groups or NXfield data. If 'attrs' is True, NXfield attributes are
        displayed. If 'recursive' is True, the contents of child groups are also
        displayed.

    tree:
        Returns the group tree.

        It invokes the 'dir' method with both 'attrs' and 'recursive'
        set to True.

    save(self, filename, format='w5')
        Save the NeXus group into a file

        The object is wrapped in an NXroot group (with name 'root') and an
        NXentry group (with name 'entry'), if necessary, in order to produce
        a valid NeXus file.

    **Examples**

    >>> x = NXfield(np.linspace(0,2*np.pi,101), units='degree')
    >>> entry = NXgroup(x, name='entry', nxclass='NXentry')
    >>> entry.sample = NXgroup(temperature=NXfield(40.0,units='K'),
                               nxclass='NXsample')
    >>> print entry.sample.tree
    sample:NXsample
      temperature = 40.0
        @units = K

    Note: All the currently defined NeXus classes are defined as subclasses of 
    the NXgroup class. It is recommended that these are used directly, so that 
    the above examples become:

    >>> entry = NXentry(x)
    >>> entry.sample = NXsample(temperature=NXfield(40.0,units='K'))

    or

    >>> entry.sample.temperature = 40.0
    >>> entry.sample.temperature.units='K'

    """

    def __init__(self, *items, **opts):
        if "name" in opts.keys():
            self._name = opts["name"]
            del opts["name"]
        self._entries = {}
        if "entries" in opts.keys():
            for k,v in opts["entries"].items():
                self._entries[k] = v
            del opts["entries"]
        self._attrs = AttrDict(self)
        if "attrs" in opts.keys():
            self._setattrs(opts["attrs"])
            del opts["attrs"]
        if "nxclass" in opts.keys():
            self._class = opts["nxclass"]
            del opts["nxclass"]
        if "group" in opts.keys():
            self._group = opts["group"]
            del opts["group"]
        for k,v in opts.items():
            setattr(self, k, v)
        if self.nxclass.startswith("NX"):
            if self.nxname == "unknown" or self.nxname == "": 
                self._name = self.nxclass[2:]
            try: # If one exists, set the class to a valid NXgroup subclass
                self.__class__ = globals()[self.nxclass]
            except KeyError:
                pass
        for item in items:
            try:
                setattr(self, item.nxname, item)
            except AttributeError:
                raise NeXusError("Non-keyword arguments must be valid NXobjects")
        self.set_changed()

#    def __cmp__(self, other):
#        """Sort groups by their distances or names."""
#        try:
#            return cmp(self.distance, other.distance)
#        except KeyError:
#            return cmp(self.nxname, other.nxname)

    def __dir__(self):
        return sorted(dir(super(self.__class__, self))+self.keys())

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__,self.nxname)

    def _str_value(self,indent=0):
        return ""

    def walk(self):
        yield self
        for node in self.values():
            for child in node.walk():
                yield child

    def __getattr__(self, key):
        """
        Provides direct access to groups via nxclass name.
        """
        if key.startswith(u'NX'):
            return self.component(key)
        elif key in self._entries:
            return self._entries[key]
        elif key in self.attrs:
            return self.attrs[key]
        raise NeXusError(key+" not in "+self.nxclass+":"+self.nxname)

    def __setattr__(self, name, value):
        """
        Sets an attribute as an object or regular Python attribute.

        It is assumed that attributes starting with 'nx' or '_' are regular
        Python attributes. All other attributes are converted to valid NXobjects,
        with class NXfield, NXgroup, or a sub-class of NXgroup, depending on the
        assigned value.

        The internal value of the attribute name, i.e., 'name', is set to the
        attribute name used in the assignment.  The parent group of the
        attribute, i.e., 'group', is set to the parent group of the attribute.

        If the assigned value is a numerical (scalar or array) or string object,
        it is converted to an object of class NXfield, whose attribute, 'nxdata',
        is set to the assigned value.
        """
        if name.startswith('_') or name.startswith('nx'):
            object.__setattr__(self, name, value)
        elif isinstance(value, NXattr):
            if self.nxfilemode == 'r':
                raise NeXusError('NeXus file opened as readonly')
            self._attrs[name] = value
        else:
            self[name] = value

    def __delattr__(self, name):
        if name in self._entries:
            raise NeXusError('Members can only be deleted using the group dictionary')
        else:
            object.__delattr__(self, name)

    def __getitem__(self, key):
        """
        Returns an entry in the group.
        """
        if isinstance(key, basestring):
            if '/' in key:
                if key.startswith('/'):
                    return self.nxroot[key[1:]]
                names = [name for name in key.split('/') if name]
                node = self
                for name in names:
                    if name in node:
                        node = node._entries[name]
                    else:
                        raise NeXusError('Invalid path')
                return node
            else:
                return self._entries[key]
        else:
            raise NeXusError("Invalid index")

    def __setitem__(self, key, value):
        """
        Adds or modifies an item in the NeXus group.
        """
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        if isinstance(key, basestring):
            group = self
            if '/' in key:
                names = [name for name in key.split('/') if name]
                key = names.pop()
                for name in names:
                    if name in group:
                        group = group[name]
                    else:
                        raise NeXusError('Invalid path')
            if key in group and isinstance(group._entries[key], NXlink):
                raise NeXusError("Cannot assign values to an NXlink object")
            if isinstance(value, NXroot):
                raise NeXusError("Cannot assign an NXroot group to another group")
            elif isinstance(value, NXlinkexternal):
                value._group = group
                value._name = key
                group._entries[key] = value
            elif isinstance(value, NXlink) and group.nxroot is value.nxroot:
                group._entries[key] = copy(value)
            elif isinstance(value, NXlink) and key != value.nxname:
                raise NeXusError("Cannot change the name of a linked object")
            elif isinstance(value, NXobject):
                if value.nxgroup:
                    memo = {}
                    value = deepcopy(value, memo)
                value._group = group
                value._name = key
                group._entries[key] = value
            elif key in group:
                group._entries[key]._setdata(value)
            else:
                group._entries[key] = NXfield(value=value, name=key, group=group)
            if isinstance(group._entries[key], NXfield):
                field = group._entries[key]
                if not field._value is None:
                    if isinstance(field._value, np.ma.MaskedArray):
                        mask_name = field._create_mask()
                        group[mask_name] = field._value.mask
                elif field._memfile is not None:
                    if 'mask' in field._memfile:
                        mask_name = field._create_mask()
                        group[mask_name]._create_memfile()
                        field._memfile.copy('mask', group[mask_name]._memfile, 'data')
                        del field._memfile['mask']
            group._entries[key].update()
        else:
            raise NeXusError('Invalid key')

    def __delitem__(self, key):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        if isinstance(key, basestring): #i.e., deleting a NeXus object
            group = self
            if '/' in key:
                names = [name for name in key.split('/') if name]
                key = names.pop()
                for name in names:
                    if name in group:
                        group = group[name]
                    else:
                        raise NeXusError('Invalid path')
            if key not in group:
                raise NeXusError(key+" not in "+group.nxpath)
            if group.nxfilemode == 'rw':
                with group.nxfile as f:
                    if 'mask' in group._entries[key].attrs:
                        del f[group._entries[key].mask.nxpath]
                    del f[group._entries[key].nxpath]
            if 'mask' in group._entries[key].attrs:
                del group._entries[group._entries[key].mask.nxname]
            del group._entries[key]
            group.set_changed()

    def __contains__(self, key):
        """
        Implements 'k in d' test
        """
        return key in self._entries

    def __iter__(self):
        """
        Implements key iteration
        """
        return self._entries.__iter__()

    def __len__(self):
        """
        Returns the number of entries in the group
        """
        return len(self._entries)

    def __eq__(self, other):
        """
        Compares the _entries dictionaries
        """
        if other == None: return False
        return self._entries == other._entries

    def __deepcopy__(self, memo):
        if isinstance(self, NXlink):
            obj = self.nxlink
        else:
            obj = self
        dpcpy = obj.__class__()
        dpcpy._name = obj._name
        memo[id(self)] = dpcpy
        dpcpy._changed = True
        for k,v in obj.items():
            dpcpy._entries[k] = deepcopy(v, memo)
            dpcpy._entries[k]._group = dpcpy
        for k, v in obj.attrs.items():
            dpcpy.attrs[k] = copy(v)
        if 'target' in dpcpy.attrs:
            del dpcpy.attrs['target']
        return dpcpy

    def update(self):
        """
        Updates the NXgroup, including its children, to the NeXus file.
        """
        if self.nxfilemode == 'rw':
            with self.nxfile as f:
                f.update(self)
        elif self.nxfilemode is None:
            for node in self.walk():
                if isinstance(node, NXfield) and node._uncopied_data:
                    node._get_uncopied_data()
        self.set_changed()

    def get(self, name, default=None):
        """
        Retrieves the group entry, or return default if it doesn't exist
        """
        try:
            return self._entries[name]
        except KeyError:
            return default
            
    def keys(self):
        """
        Returns the names of NeXus objects in the group.
        """
        return self._entries.keys()

    def iterkeys(self):
        """ 
        Get an iterator over group object names
        """
        return iter(self._entries)

    def values(self):
        """
        Returns the values of NeXus objects in the group.
        """
        return self._entries.values()

    def itervalues(self):
        """
        Get an iterator over group objects
        """
        for key in self._entries:
            yield self._entries.get(key)

    def items(self):
        """
        Returns a list of the NeXus objects in the group as (key,value) pairs.
        """
        return self._entries.items()

    def iteritems(self):
        """
        Get an iterator over (name, object) pairs
        """
        for key in self._entries:
            yield (key, self._entries.get(key))

    def has_key(self, name):
        """
        Returns true if the NeXus object with the specified name is in the group.
        """
        return self._entries.has_key(name)

    def insert(self, value, name='unknown'):
        """
        Adds an attribute to the group.

        If it is not a valid NeXus object (NXfield or NXgroup), the attribute
        is converted to an NXfield.
        """
        if isinstance(value, NXobject):
            if name == 'unknown': 
                name = value.nxname
            if name in self._entries:
                raise NeXusError("'%s' already exists in group" % name)
            self[name] = value
        else:
            self[name] = NXfield(value=value, name=name, group=self)

    def makelink(self, target):
        """
        Creates a linked NXobject within the group.

        The argument is the parent object. All attributes are inherited from the 
        parent object including the name.
        
        The root of the target and child's group must be the same.
        """
        if isinstance(self.nxroot, NXroot):
            if self.nxroot == target.nxroot:
                if isinstance(target, NXobject):
                    if target.nxname in self:
                        raise NeXusError("Object with the same name already exists in '%s'" % self.nxpath)
                    self[target.nxname] = NXlink(target=target)
                else:
                    raise NeXusError("Link target must be an NXobject")
            else:
                self[target.nxname] = NXlink(target=target.nxpath, file=target.nxfilename)
        else:
            raise NeXusError("The group must have a root object of class NXroot")                

    def sum(self, axis=None):
        """
        Returns the sum of the NXdata group using the Numpy sum method
        on the NXdata signal. The sum is over a single axis or a tuple of axes
        using the Numpy sum method.

        The result contains a copy of all the metadata contained in
        the NXdata group.
        """
        if not self.nxsignal:
            raise NeXusError("No signal to sum")
        if not hasattr(self,"nxclass"):
            raise NeXusError("Summing not allowed for groups of unknown class")
        if axis is None:
            return self.nxsignal.sum()
        else:
            if isinstance(axis, int):
                axis = [axis]
            axis = tuple(axis)
            signal = NXfield(self.nxsignal.sum(axis), name=self.nxsignal.nxname,
                             attrs=self.nxsignal.attrs)
            axes = self.nxaxes
            averages = []
            for ax in axis:
                summedaxis = axes.pop(ax)
                summedaxis.minimum = summedaxis.nxdata[0]
                summedaxis.maximum = summedaxis.nxdata[-1]
                averages.append(NXfield(
                                0.5*(summedaxis.nxdata[0]+summedaxis.nxdata[-1]), 
                                name=summedaxis.nxname,attrs=summedaxis.attrs))
            result = NXdata(signal, axes)
            for average in averages:
                result.insert(average)
            if self.nxerrors:
                errors = np.sqrt((self.nxerrors.nxdata**2).sum(axis))
                result.errors = NXfield(errors, name="errors")
            if self.nxtitle:
                result.title = self.nxtitle
            return result

    def moment(self, order=1):
        """
        Returns an NXfield containing the moments of the NXdata group
        assuming the signal is one-dimensional.

        Currently, only the first moment has been defined. Eventually, the
        order of the moment will be defined by the 'order' parameter.
        """
        if not self.nxsignal:
            raise NeXusError("No signal to calculate")
        elif len(self.nxsignal.shape) > 1:
            raise NeXusError("Operation only possible on one-dimensional signals")
        elif order > 1:
            raise NeXusError("Higher moments not yet implemented")
        if not hasattr(self,"nxclass"):
            raise NeXusError("Operation not allowed for groups of unknown class")
        return (centers(self.nxsignal,self.nxaxes)*self.nxsignal).sum() \
                /self.nxsignal.sum()

    def project(self, axes, limits):
        """
        Projects the data along a specified 1D axis or 2D axes summing over the
        limits, which are specified as tuples for each dimension.
        
        This assumes that the data is at least two-dimensional.
        """
        if not isinstance(axes, list):
            axes = [axes]
        if len(limits) < len(self.nxsignal.shape):
            raise NeXusError("Too few limits specified")
        elif len(axes) > 2:
            raise NeXusError("Projections to more than two dimensions not supported")
        projection_axes =  [x for x in range(len(limits)) if x not in axes]
        projection_axes.sort(reverse=True)
        slab = [slice(_min, _max) for _min, _max in limits]
        result = self[slab]
        slab_axes = list(projection_axes)
        for slab_axis in slab_axes:
            slab[slab_axis] = convert_index(slab[slab_axis],
                                            self.nxaxes[slab_axis])
            if isinstance(slab[slab_axis], int):
                slab.pop(slab_axis)
                projection_axes.pop(projection_axes.index(slab_axis))
                for i in range(len(projection_axes)):
                    if projection_axes[i] > slab_axis:
                        projection_axes[i] -= 1
        if projection_axes:
            result = result.sum(projection_axes)
        if len(axes) > 1 and axes[0] > axes[1]:
            result[result.nxsignal.nxname] = result.nxsignal.transpose()
            if result.nxerrors:
                result[result.nxerrors.nxname] = result.nxerrors.transpose()
            result.nxaxes = result.nxaxes[::-1]            
        return result        

    def is_plottable(self):
        plottable = False
        for entry in self:
            if self[entry].is_plottable():
                plottable = True
        return plottable        

    @property
    def plottable_data(self):
        """
        Returns the first NXdata group within the group's tree.
        """
        data = self
        if self.nxclass == "NXroot":
            try:
                data = data.NXdata[0]
            except Exception:
                if data.NXentry:
                    data = data.NXentry[0]
                else:
                    return None
        if data.nxclass == "NXentry":
            if data.NXdata:
                data = data.NXdata[0]
            elif data.NXmonitor:
                data = data.NXmonitor[0]
            elif data.NXlog:
                data = data.NXlog[0]
            else:
                return None
        return data

    def plot(self, **opts):
        """
        Plot data contained within the group.
        """
        if self.plottable_data:
            self.plottable_data.plot(**opts)
    
    def oplot(self, **opts):
        """
        Plots the data contained within the group over the current figure.
        """
        if self.plottable_data:
            self.plottable_data.oplot(**opts)

    def logplot(self, **opts):
        """
        Plots the data intensity contained within the group on a log scale.
        """
        if self.plottable_data:
            self.plottable_data.logplot(**opts)

    def implot(self, **opts):
        """
        Plots the data intensity as an RGB(A) image.
        """
        if self.plottable_data:
            self.plottable_data.implot(**opts)

    def component(self, nxclass):
        """
        Finds all child objects that have a particular class.
        """
        return [E for _name,E in self.items() if E.nxclass==nxclass]

    def signals(self):
        """
        Returns a dictionary of NXfield's containing signal data.

        The key is the value of the signal attribute.
        """
        signals = {}
        for obj in self.values():
            if 'signal' in obj.attrs:
                signals[obj.attrs['signal']] = obj
        return signals

    def _title(self):
        """
        Returns the title as a string.

        If there is no title field in the group or its parent group, the group's
        path is returned.
        """
        if 'title' in self:
            return str(self.title)
        elif self.nxgroup and 'title' in self.nxgroup:
            return str(self.nxgroup.title)
        else:
            if self.nxroot.nxname != '' and self.nxroot.nxname != 'root':
                return (self.nxroot.nxname + '/' + self.nxpath.lstrip('/')).rstrip('/')
            else:
                return self.nxfilename + ':' + self.nxpath

    def _getentries(self):
        return self._entries

    nxsignal = None
    nxaxes = None
    nxerrors = None
    nxtitle = property(_title, "Property: Group title")
    entries = property(_getentries,doc="Property: NeXus objects within group")

class NXlink(NXobject):

    """
    Class for NeXus linked objects.

    The real object will be accessible by following the link attribute.
    """

    _class = "NXlink"

    def __init__(self, target=None, name=None, file=None, **opts):
        self._class = "NXlink"
        if isinstance(target, NXobject):
            self._name = target.nxname
            self._target = target.attrs["target"] = target.nxpath
            if target.nxclass == "NXlink":
                raise NeXusError("Cannot link to another NXlink object")
            elif target.nxclass == "NXfield":
                self.__class__ = NXlinkfield
            else:
                self.__class__ = NXlinkgroup
        else:
            if file:
                self.__class__ = NXlinkexternal
                NXlinkexternal.__init__(self, name=name, target=target, 
                                        file=file, **opts)
            else:
                if name:
                    self._name = name
                else:
                    self._name = target.rsplit('/', 1)[1]
                self._target = target

    def __getattr__(self, key):
        try:
            try:
                return self.nxlink.__dict__[key]
            except KeyError:
                return self.nxlink.__getattr__(key)
        except KeyError:
            raise KeyError((key+" not in %s" % self._target))

    def __setattr__(self, name, value):
        if name.startswith('_')  or name.startswith('nx'):
            object.__setattr__(self, name, value)
        elif self.nxlink:
            self.nxlink.__setattr__(name, value)

    def __repr__(self):
        return "NXlink('%s')" % (self._target)

    def __str__(self):
        return str(self.nxlink)

    def _str_tree(self, indent=0, attrs=False, recursive=False):
        if self.nxlink:
            return self.nxlink._str_tree(indent, attrs, recursive)
        else:
            return " "*indent+self.nxname+' -> '+self._target

    def rename(self, name):
        raise NeXusError("Cannot rename a linked object")

    def _getlink(self):
        return self.nxroot[self._target]

    def _getattrs(self):
        return self.nxlink.attrs

    nxlink = property(_getlink, "Linked object")
    attrs = property(_getattrs,doc="NeXus attributes for object")


class NXlinkfield(NXlink, NXfield):

    """
    Class for a NeXus linked field.

    The real field will be accessible by following the link attribute.
    """
    pass

NXlinkdata = NXlinkfield # For backward compatibility

class NXlinkgroup(NXlink, NXgroup):

    """
    Class for a NeXus linked group.

    The real group will be accessible by following the link attribute.
    """

    def _getentries(self):
        return self.nxlink._entries

    entries = property(_getentries,doc="Dictionary of NeXus objects within group")

class NXlinkexternal(NXlink, NXfield):

    """
    Class for a link to a field in an external file.

    Since the field is stored in another file, the field names don't have to be 
    the same. There is no need to redirect requests for linked attributes, since 
    they are handled automatically by h5py. Currently, external fields are 
    read-only.
    """
    def __init__(self, name=None, target=None, file=None, **opts):               
        NXfield.__init__(self, **opts)
        if name:
            self._name = name
        if target:
            self._target = target
        self._filename = file
        self._mode = 'r'
        if 'value' not in opts:
            try:
                self.readvalues()
            except NeXusError:
                pass
        
    def __repr__(self):
        if self._value is not None:
            if self.dtype.type == np.string_:
                return "NXlink('%s', file='%s')" % (str(self), self._filename)
            else:
                return "NXlink(%s, file='%s')" % \
                    (NXfield._str_value(self), self._filename)
        else:
            return "NXlink(target='%s', file='%s')" % (self._target, self._filename)

    def __getattr__(self, key):
        return NXfield.__getattr__(self, key)

    def __setattr__(self, name, value):
        if name.startswith('_') or name.startswith('nx'):
            object.__setattr__(self, name, value)
        else:
            raise NeXusError("Cannot currently assign attributes to an external link")

    def __setitem__(self, key, value):
        raise NeXusError("Cannot currently assign slabs to an external link")

    def __str__(self):
        if self._value is not None:
            return str(NXfield.__str__(self))
        else:
            return repr(self)

    def _str_tree(self, indent=0, attrs=False, recursive=False):
        if self._value is not None:
            return NXfield._str_tree(self, indent, attrs, recursive)
        else:
            return " " * indent + "%s = %s" % (self.nxname, repr(self))

    def readvalues(self):
        if os.path.exists(self.nxfilename):
            with self.nxfile as f:
                f.nxpath = self._target
                self._value, self._shape, self._dtype, self._attrs = f.readvalues()
        else:
            raise NeXusError("External link '%s' does not exist" % 
                              os.path.abspath(self.nxfilename))

    def update(self):
        if self.nxroot.nxfile and self.nxroot.nxfilename != self.nxfilename:
            with self.nxroot.nxfile as f:
                f.nxpath = self.nxpath
                f.linkexternal(self)
        self.set_changed()

    def _getlink(self):
        return self

    def _getdata(self):
        if self._value is None:
            self.readvalues()
        return self._value

    def _getdtype(self):
        if self._dtype is None:
            self.readvalues()
        return self._dtype

    def _getshape(self):
        if self._dtype is None:
            self.readvalues()
        return self._shape

    def _getattrs(self):
        return self._attrs

    def _getpath(self):
        return self._target

    def _getfile(self):
        return NXFile(self.nxfilename, self.nxfilemode).open()

    def _getfilename(self):
        if os.path.isabs(self._filename) or self.nxroot is self:
            return self._filename
        else:
            return os.path.join(os.path.dirname(self.nxroot.nxfilename),
                                self._filename)
 
    def _setfilename(self, name):
        self._filename = name

    def _getfilemode(self):
        return 'r'

    nxlink = property(_getlink, doc="Linked object")
    nxdata = property(_getdata, doc="Property: The data values")
    dtype = property(_getdtype, doc="Property: Data type of NeXus field")
    shape = property(_getshape, doc="Property: Shape of NeXus field")
    attrs = property(_getattrs,doc="NeXus attributes for object")
    nxpath = property(_getpath, doc="Property: Path to NeXus object")
    nxfile = property(_getfile, doc="Property: File handle of NeXus link")
    nxfilename = property(_getfilename, _setfilename, doc="Property: Filename of external link")
    nxfilemode = property(_getfilemode, doc="Property: File mode of external link")


class NXroot(NXgroup):

    """
    NXroot group. This is a subclass of the NXgroup class.

    This group has additional methods to lock or unlock the tree.

    See the NXgroup documentation for more details.
    """

    def __init__(self, *items, **opts):
        self._class = "NXroot"
        NXgroup.__init__(self, *items, **opts)

    def rename(self, name):
        self.nxname = name        

    def lock(self):
        """Make the tree readonly"""
        if self._filename:
            self._mode = self._file._mode = 'r'

    def unlock(self):
        """Make the tree modifiable"""
        if self._filename:
            self._mode = self._file._mode = 'rw'


class NXentry(NXgroup):

    """
    NXentry group. This is a subclass of the NXgroup class.

    Each NXdata and NXmonitor object of the same name will be added
    together, raising an NeXusError if any of the groups do not exist
    in both NXentry groups or if any of the NXdata additions fail.
    The resulting NXentry group contains a copy of all the other metadata
    contained in the first group. Note that other extensible data, such
    as the run duration, are not currently added together.

    See the NXgroup documentation for more details.
    """

    def __init__(self, *items, **opts):
        self._class = "NXentry"
        NXgroup.__init__(self, *items, **opts)

    def __add__(self, other):
        """
        Adds two NXentry objects
        """
        result = NXentry(entries=self._entries, attrs=self.attrs)
        try:
            names = [group.nxname for group in self.component("NXdata")]
            for name in names:
                if isinstance(other[name], NXdata):
                    result[name] = self[name] + other[name]
                else:
                    raise KeyError
            names = [group.nxname for group in self.component("NXmonitor")]
            for name in names:
                if isinstance(other[name], NXmonitor):
                    result[name] = self[name] + other[name]
                else:
                    raise KeyError
            return result
        except KeyError:
            raise NeXusError("Inconsistency between two NXentry groups")

    def __sub__(self, other):
        """
        Subtracts two NXentry objects
        """
        result = NXentry(entries=self.entries, attrs=self.attrs)
        try:
            names = [group.nxname for group in self.component("NXdata")]
            for name in names:
                if isinstance(other[name], NXdata):
                    result[name] = self[name] - other[name]
                else:
                    raise KeyError
            names = [group.nxname for group in self.component("NXmonitor")]
            for name in names:
                if isinstance(other[name], NXmonitor):
                    result[name] = self[name] - other[name]
                else:
                    raise KeyError
            return result
        except KeyError:
            raise NeXusError("Inconsistency between two NXentry groups")


class NXsubentry(NXentry):

    """
    NXsubentry group. This is a subclass of the NXsubentry class.

    See the NXgroup documentation for more details.
    """

    def __init__(self, *items, **opts):
        self._class = "NXsubentry"
        NXgroup.__init__(self, *items, **opts)


class NXdata(NXgroup):

    """
    NXdata group. This is a subclass of the NXgroup class.

    The constructor assumes that the first argument contains the signal and
    the second contains either the axis, for one-dimensional data, or a list
    of axes, for multidimensional data. These arguments can either be NXfield
    objects or Numpy arrays, which are converted to NXfield objects with default
    names. Alternatively, the signal and axes NXfields can be defined using the
    'nxsignal' and 'nxaxes' properties. See the examples below.
    
    Various arithmetic operations (addition, subtraction, multiplication,
    and division) have been defined for combining NXdata groups with other
    NXdata groups, Numpy arrays, or constants, raising a NeXusError if the
    shapes don't match. Data errors are propagated in quadrature if
    they are defined, i.e., if the 'nexerrors' attribute is not None,

    **Python Attributes**

    nxsignal : property
        The NXfield containing the attribute 'signal' with value 1
    nxaxes : property
        A list of NXfields containing the signal axes
    nxerrors : property
        The NXfield containing the errors

    **Examples**

    There are three methods of creating valid NXdata groups with the
    signal and axes NXfields defined according to the NeXus standard.
    
    1) Create the NXdata group with Numpy arrays that will be assigned
       default names.
       
       >>> x = np.linspace(0, 2*np.pi, 101)
       >>> line = NXdata(sin(x), x)
       data:NXdata
         signal = float64(101)
           @axes = x
           @signal = 1
         axis1 = float64(101)
      
    2) Create the NXdata group with NXfields that have their internal
       names already assigned.

       >>> x = NXfield(linspace(0,2*pi,101), name='x')
       >>> y = NXfield(linspace(0,2*pi,101), name='y')    
       >>> X, Y = np.meshgrid(x, y)
       >>> z = NXfield(sin(X) * sin(Y), name='z')
       >>> entry = NXentry()
       >>> entry.grid = NXdata(z, (x, y))
       >>> grid.tree()
       entry:NXentry
         grid:NXdata
           x = float64(101)
           y = float64(101)
           z = float64(101x101)
             @axes = x:y
             @signal = 1

    3) Create the NXdata group with keyword arguments defining the names 
       and set the signal and axes using the nxsignal and nxaxes properties.

       >>> x = linspace(0,2*pi,101)
       >>> y = linspace(0,2*pi,101)  
       >>> X, Y = np.meshgrid(x, y)
       >>> z = sin(X) * sin(Y)
       >>> entry = NXentry()
       >>> entry.grid = NXdata(z=sin(X)*sin(Y), x=x, y=y)
       >>> entry.grid.nxsignal = entry.grid.z
       >>> entry.grid.nxaxes = [entry.grid.x,entry.grid.y]
       >>> grid.tree()
       entry:NXentry
         grid:NXdata
           x = float64(101)
           y = float64(101)
           z = float64(101x101)
             @axes = x:y
             @signal = 1
    """

    def __init__(self, signal=None, axes=None, errors=None, *items, **opts):
        self._class = "NXdata"
        NXgroup.__init__(self, *items, **opts)
        if axes is not None:
            if not isinstance(axes, tuple) and not isinstance(axes, list):
                axes = [axes]
            axis_names = {}
            i = 0
            for axis in axes:
                i += 1
                if isinstance(axis, NXfield):
                    if axis._name == "unknown": 
                        axis._name = "axis%s" % i
                    self[axis.nxname] = axis
                    axis_names[i] = axis.nxname
                else:
                    axis_name = "axis%s" % i
                    self[axis_name] = axis
                    axis_names[i] = axis_name
            self.attrs["axes"] = ":".join(axis_names.values())
        if signal is not None:
            if isinstance(signal, NXfield):
                if signal.nxname == "unknown" or signal.nxname in self:
                    signal.nxname = "signal"
                self[signal.nxname] = signal
                signal_name = signal.nxname
            else:
                self["signal"] = signal
                self["signal"].signal = 1
                signal_name = "signal"
            self.attrs["signal"] = signal_name
        if errors is not None:
            self["errors"] = errors

    def __getitem__(self, key):
        """
        Returns an entry in the group if the key is a string.
        
        or
        
        Returns a slice from the NXgroup nxsignal attribute (if it exists) as
        a new NXdata group, if the index is a slice object.

        In most cases, the slice values are applied to the NXfield nxdata array
        and returned within an NXfield object with the same metadata. However,
        if the array is one-dimensional and the index start and stop values
        are real, the nxdata array is returned with values between the limits
        set by those axis values.

        This is to allow axis arrays to be limited by their actual value. This
        real-space slicing should only be used on monotonically increasing (or
        decreasing) one-dimensional arrays.
        """
        if isinstance(key, basestring): #i.e., requesting a dictionary value
            return NXgroup.__getitem__(self, key)
        elif self.nxsignal:
            idx = key
            axes = self.nxaxes
            if isinstance(idx, int) or isinstance(idx, slice):
                idx = convert_index(idx, axes[0])
                axes[0] = axes[0][idx]
                result = NXdata(self.nxsignal[idx], axes)
                if self.nxsignal.mask:
                    result[self.nxsignal.mask.nxname] = self.nxsignal.mask
                if self.nxerrors: 
                    result.errors = self.errors[idx]
            else:
                i = 0
                slices = []
                for ind in idx:
                    ind = convert_index(ind, axes[i])
                    axes[i] = axes[i][ind]
                    slices.append(ind)
                    i = i + 1
                result = NXdata(self.nxsignal[tuple(slices)], axes)
                if self.nxerrors: 
                    result.errors = self.errors[tuple(slices)]
            if self.nxtitle:
                result.title = self.nxtitle
            result = simplify_axes(result)
            return result
        else:
            raise NeXusError("No signal specified")

    def __setitem__(self, idx, value):
        if isinstance(idx, basestring):
            NXgroup.__setitem__(self, idx, value)
        elif self.nxsignal:
            if isinstance(idx, int) or isinstance(idx, slice):
                axes = self.nxaxes
                idx = convert_index(idx, axes[0])
                self.nxsignal[idx] = value
            else:
                i = 0
                slices = []
                axes = self.nxaxes
                for ind in idx:
                    ind = convert_index(ind, axes[i])
                    axes[i] = axes[i][ind]
                    slices.append(ind)
                    i = i + 1
                self.nxsignal[tuple(slices)] = value
        else:
            raise NeXusError('Invalid index')

    def __add__(self, other):
        """
        Adds the NXdata group to another NXdata group or to a number. Only the 
        signal data is affected.

        The result contains a copy of all the metadata contained in
        the first NXdata group. The module checks that the dimensions are
        compatible, but does not check that the NXfield names or values are
        identical. This is so that spelling variations or rounding errors
        do not make the operation fail. However, it is up to the user to
        ensure that the results make sense.
        """
        result = NXdata(entries=self.entries, attrs=self.attrs)
        if isinstance(other, NXdata):
            if self.nxsignal and self.nxsignal.shape == other.nxsignal.shape:
                result[self.nxsignal.nxname] = self.nxsignal + other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = np.sqrt(self.errors**2 + other.errors**2)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot add two arbitrary groups")
        else:
            result[self.nxsignal.nxname] = self.nxsignal + other
            return result

    def __sub__(self, other):
        """
        Subtracts a NXdata group or a number from the NXdata group. Only the 
        signal data is affected.

        The result contains a copy of all the metadata contained in
        the first NXdata group. The module checks that the dimensions are
        compatible, but does not check that the NXfield names or values are
        identical. This is so that spelling variations or rounding errors
        do not make the operation fail. However, it is up to the user to
        ensure that the results make sense.
        """
        result = NXdata(entries=self.entries, attrs=self.attrs)
        if isinstance(other, NXdata):
            if self.nxsignal and self.nxsignal.shape == other.nxsignal.shape:
                result[self.nxsignal.nxname] = self.nxsignal - other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = np.sqrt(self.errors**2 + other.errors**2)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot subtract two arbitrary groups")
        else:
            result[self.nxsignal.nxname] = self.nxsignal - other
            return result

    def __mul__(self, other):
        """
        Multiplies the NXdata group with a NXdata group or a number. Only the 
        signal data is affected.

        The result contains a copy of all the metadata contained in
        the first NXdata group. The module checks that the dimensions are
        compatible, but does not check that the NXfield names or values are
        identical. This is so that spelling variations or rounding errors
        do not make the operation fail. However, it is up to the user to
        ensure that the results make sense.
        """
        result = NXdata(entries=self.entries, attrs=self.attrs)
        if isinstance(other, NXdata):

            # error here signal not defined in this scope
            #if self.nxsignal and signal.shape == other.nxsignal.shape:
            if self.nxsignal and self.nxsignal.shape == other.nxsignal.shape:
                result[self.nxsignal.nxname] = self.nxsignal * other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = np.sqrt(
                            (self.errors * other.nxsignal)**2 +
                            (other.errors * self.nxsignal)**2)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot multiply two arbitrary groups")
        else:
            result[self.nxsignal.nxname] = self.nxsignal * other
            if self.nxerrors:
                result.errors = self.errors * other
            return result

    def __rmul__(self, other):
        """
        Multiplies the NXdata group with a NXdata group or a number.

        This variant makes __mul__ commutative.
        """
        return self.__mul__(other)

    def __div__(self, other):
        """
        Divides the NXdata group by a NXdata group or a number. Only the signal 
        data is affected.

        The result contains a copy of all the metadata contained in
        the first NXdata group. The module checks that the dimensions are
        compatible, but does not check that the NXfield names or values are
        identical. This is so that spelling variations or rounding errors
        do not make the operation fail. However, it is up to the user to
        ensure that the results make sense.
        """
        result = NXdata(entries=self.entries, attrs=self.attrs)
        if isinstance(other, NXdata):
            if self.nxsignal and self.nxsignal.shape == other.nxsignal.shape:
                result[self.nxsignal.nxname] = self.nxsignal / other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = (np.sqrt(self.errors**2 +
                            (result[self.nxsignal.nxname] * other.errors)**2)
                                         / other.nxsignal)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot divide two arbitrary groups")
        else:
            result[self.nxsignal.nxname] = self.nxsignal / other
            if self.nxerrors: 
                result.errors = self.errors / other
            return result

    def plot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             zmin=None, zmax=None, **opts):
        """
        Plot data contained within the group.

        The format argument is used to set the color and type of the
        markers or lines for one-dimensional plots, using the standard 
        Matplotlib syntax. The default is set to blue circles. All 
        keyword arguments accepted by matplotlib.pyplot.plot can be
        used to customize the plot.
        
        In addition to the matplotlib keyword arguments, the following
        are defined::
        
            log = True     - plot the intensity on a log scale
            logy = True    - plot the y-axis on a log scale
            logx = True    - plot the x-axis on a log scale
            over = True    - plot on the current figure
            image = True   - plot as an RGB(A) image

        Raises NeXusError if the data could not be plotted.
        """

        try:
            from nexpy.gui.plotview import plotview
            if plotview is None:
                raise ImportError
        except ImportError:
            from nexusformat.nexus.plot import plotview
            
        # Check there is a plottable signal
        if self.nxsignal is None:
            raise NeXusError('No plotting signal defined')

        # Plot with the available plotter
        plotview.plot(self, fmt, xmin, xmax, ymin, ymax, zmin, zmax, **opts)
    
    def oplot(self, fmt='', **opts):
        """
        Plots the data contained within the group over the current figure.
        """
        self.plot(fmt=fmt, over=True, **opts)

    def logplot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
                zmin=None, zmax=None, **opts):
        """
        Plots the data intensity contained within the group on a log scale.
        """
        self.plot(fmt=fmt, log=True,
                  xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
                  zmin=zmin, zmax=zmax, **opts)

    def implot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
                zmin=None, zmax=None, **opts):
        """
        Plots the data intensity as an image.
        """
        if (self.nxsignal.plot_rank > 2 and 
            (self.nxsignal.shape[-1] == 3 or self.nxsignal.shape[-1] == 4)):
            self.plot(fmt=fmt, image=True,
                      xmin=xmin, xmax=xmax, ymin=ymin, ymax=ymax,
                      zmin=zmin, zmax=zmax, **opts)
        else:
            raise NeXusError('Invalid shape for RGB(A) image')

    def _signal(self):
        """
        Returns the NXfield containing the signal data.
        """
        if 'signal' in self.attrs:
            if self.attrs['signal'] in self:
                return self[self.attrs['signal']]
        for obj in self.values():
            if 'signal' in obj.attrs and str(obj.signal) == '1':
                if isinstance(self[obj.nxname],NXlink):
                    return self[obj.nxname].nxlink
                else:
                    return self[obj.nxname]
        return None
    
    def _set_signal(self, signal):
        """
        Setter for the signal attribute.
        
        The argument should be a valid NXfield within the group.
        """
        current_signal = self._signal()
        if current_signal is not None and current_signal is not signal:
            if 'signal' in current_signal.attrs:
                del current_signal.attrs['signal']
        self.attrs['signal'] = signal.nxname
        if signal.nxname not in self:
            self[signal.nxname] = signal
        return self[signal.nxname]

    def _axes(self):
        """
        Returns a list of NXfields containing the axes.
        """
        try:
            if 'axes' in self.attrs:
                axes = _readaxes(self.attrs['axes'])
            elif self.nxsignal is not None and 'axes' in self.nxsignal.attrs:
                axes = _readaxes(self.nxsignal.attrs['axes'])
            return [getattr(self, name) for name in axes]
        except (KeyError, AttributeError, UnboundLocalError):
            axes = {}
            for entry in self:
                if 'axis' in self[entry].attrs:
                    axis = self[entry].axis
                    if axis not in axes:
                        axes[axis] = self[entry]
                    else:
                        return None
            if axes:
                return [axes[key] for key in sorted(axes.keys())]
            else:
                return [NXfield(np.arange(self.nxsignal.shape[i]), 
                        name='Axis%s'%i) for i in range(self.nxsignal.ndim)]

    def _set_axes(self, axes):
        """
        Setter for the signal attribute.
        
        The argument should be a list of valid NXfields within the group.
        """
        if not isinstance(axes, list):
            axes = [axes]
        for axis in axes:
            if axis.nxname not in self.keys():
                self.insert(axis)
        axes_attr = ":".join([axis.nxname for axis in axes])
        if 'signal' in self.attrs:
            self.attrs['axes'] = axes_attr
        self.nxsignal.attrs['axes'] = axes_attr

    def _errors(self):
        """
        Returns the NXfield containing the signal errors.
        """
        try:
            return self['errors']
        except KeyError:
            return None

    def _set_errors(self, errors):
        """
        Setter for the errors.
        
        The argument should be a valid NXfield.
        """
        self._entries['errors'] = errors
        return self._entries['errors']

    nxsignal = property(_signal, _set_signal, "Property: Signal field within group")
    nxaxes = property(_axes, _set_axes, "Property: List of axes within group")
    nxerrors = property(_errors, _set_errors, "Property: Errors field within group")


class NXmonitor(NXdata):

    """
    NXmonitor group. This is a subclass of the NXdata class.

    See the NXdata and NXgroup documentation for more details.
    """

    def __init__(self, signal=None, axes=(), *items, **opts):
        NXdata.__init__(self, signal=signal, axes=axes, *items, **opts)
        self._class = "NXmonitor"
        if "name" not in opts.keys():
            self._name = "monitor"


class NXlog(NXgroup):

    """
    NXlog group. This is a subclass of the NXgroup class.

    See the NXgroup documentation for more details.
    """

    def __init__(self, *items, **opts):
        self._class = "NXlog"
        NXgroup.__init__(self, *items, **opts)

    def plot(self, **opts):
        """
        Plots the logged values against the elapsed time. Valid Matplotlib 
        parameters, specifying markers, colors, etc, can be specified using the 
        'opts' dictionary.
        """
        title = NXfield("%s Log" % self.nxname)
        if 'start' in self.time.attrs:
            title = title + ' - starting at ' + self.time.attrs['start']
        NXdata(self.value, self.time, title=title).plot(**opts)


#-------------------------------------------------------------------------
#Add remaining base classes as subclasses of NXgroup and append to __all__

for _class in nxclasses:
    if _class not in globals():
        docstring = """
                    %s group. This is a subclass of the NXgroup class.

                    See the NXgroup documentation for more details.
                    """ % _class
        globals()[_class]=type(_class, (NXgroup,),
                               {'_class':_class,'__doc__':docstring})
    __all__.append(_class)

#-------------------------------------------------------------------------

def convert_index(idx, axis):
    """
    Converts floating point limits to a valid array index.
    
    This is for one-dimensional axes only. If the index is a tuple of slices, 
    i.e., for two or more dimensional data, the index is returned unchanged.
    """
    if len(axis) == 1:
        idx = 0
    elif isinstance(idx, slice) and \
            (idx.start is None or isinstance(idx.start, int)) and \
            (idx.stop is None or isinstance(idx.stop, int)):
        if idx.start is not None and idx.stop is not None:
            if idx.stop == idx.start or idx.stop == idx.start + 1:
                idx = idx.start
    elif isinstance(idx, slice):
        if isinstance(idx.start, NXfield) and isinstance(idx.stop, NXfield):
            idx = slice(idx.start.nxdata, idx.stop.nxdata)
        if idx.start is None:
            start = None
        else:
            start = axis.index(idx.start)
        if idx.stop is None:
            stop = None
        else:
            stop = axis.index(idx.stop,max=True) + 1
        if start is None or stop is None:
            idx = slice(start, stop)
        elif stop <= start+1:
            idx = start
        else:
            idx = slice(start, stop)
    elif isinstance(idx, float):
        idx = axis.index(idx)
    return idx

def simplify_axes(data):
    shape = list(data.nxsignal.shape)
    while 1 in shape: 
        shape.remove(1)
    data.nxsignal._shape = shape
    if data.nxsignal._value is not None:
        data.nxsignal._value.shape = shape
    if data.nxerrors is not None:
        data.nxerrors._shape = shape
        if data.nxerrors._value is not None:
            data.nxerrors._value.shape = shape
    axes = []
    for axis in data.nxaxes:
        if len(axis) > 1: 
            axes.append(axis)
    data.nxaxes = axes
    return data

def centers(signal, axes):
    """
    Returns the centers of the axes.

    This works regardless if the axes contain bin boundaries or centers.
    """
    def findc(axis, dimlen):
        if axis.shape[0] == dimlen+1:
            return (axis.nxdata[:-1] + axis.nxdata[1:])/2
        else:
            assert axis.shape[0] == dimlen
            return axis.nxdata
    return [findc(a,signal.shape[i]) for i,a in enumerate(axes)]

def setmemory(value):
    """
    Sets the memory limit for data arrays (in MB).
    """
    global NX_MEMORY
    NX_MEMORY = value

# File level operations
def load(filename, mode='r'):
    """
    Reads a NeXus file returning a tree of objects.

    This is aliased to 'nxload' because of potential name clashes with Numpy
    """
    with NXFile(filename, mode) as f:
        tree = f.readfile()
    return tree

#Definition for when there are name clashes with Numpy
nxload = load
__all__.append('nxload')

def save(filename, group, mode='w'):
    """
    Writes a NeXus file from a tree of objects.
    """
    if group.nxclass == "NXroot":
        tree = group
    elif group.nxclass == "NXentry":
        tree = NXroot(group)
    else:
        tree = NXroot(NXentry(group))
    with NXFile(filename, mode) as f:
        f = NXFile(filename, mode)
        f.writefile(tree)
        f.close()

def tree(filename):
    """
    Reads and summarize the named NeXus file.
    """
    root = load(filename)
    print root.tree

def demo(argv):
    """
    Processes a list of command line commands.

    'argv' should contain program name, command, arguments, where command is one
    of the following:
        copy fromfile.nxs tofile.nxs
        ls f1.nxs f2.nxs ...
    """
    if len(argv) > 1:
        op = argv[1]
    else:
        op = 'help'
    if op == 'ls':
        for f in argv[2:]: dir(f)
    elif op == 'copy' and len(argv)==4:
        tree = load(argv[2])
        save(argv[3], tree)
    elif op == 'plot' and len(argv)==4:
        tree = load(argv[2])
        for entry in argv[3].split('.'):
            tree = getattr(tree,entry)
        tree.plot()
        tree._plotter.show()

    else:
        usage = """
usage: %s cmd [args]
    copy fromfile.nxs tofile.nxs
    ls *.nxs
    plot file.nxs entry.data
        """%(argv[0],)
        print usage


if __name__ == "__main__":
    import sys
    demo(sys.argv)

