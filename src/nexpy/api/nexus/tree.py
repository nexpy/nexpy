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
from copy import copy, deepcopy
import os               #@UnusedImport

import numpy as np
import h5py as h5

#Memory in MB
NX_MEMORY = 2000

__all__ = ['NXFile', 'NXobject', 'NXfield', 'NXgroup', 'NXattr', 'nxclasses',
           'NX_MEMORY', 'setmemory', 'load', 'save', 'tree', 'centers',
           'NXlink', 'NXlinkfield', 'NXlinkgroup', 'SDS', 'NXlinkdata',
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
        self._path = ''

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
        return self

    def __exit__(self, *args):
        if self._file.id:
            self.close()

    def copy(self, *args, **kwds):
        self._file.copy(*args, **kwds)

    def close(self):
        self._file.close()

    def readfile(self):
        """
        Reads the NeXus file structure from the file and returns a tree of 
        NXobjects.

        Large datasets are not read until they are needed.
        """
        self.nxpath = '/'
        root = self._readgroup()
        root._group = None
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
            shape, dtype = self[self.nxpath].shape, self[self.nxpath].dtype
            if shape == (1,):
                shape = ()
            #Read in the data if it's not too large
            if np.prod(shape) < 1000:# i.e., less than 1k dims
                try:
                    value = self[self.nxpath][()]
                    if shape == ():
                        value = np.asscalar(value)
                except ValueError:
                    value = None
            else:
                value = None
            data = NXfield(value=value,name=name,dtype=dtype,shape=shape,attrs=attrs)
        data._saved = data._changed = True
        return data

    def _readchildren(self):
        children = {}
        for name, value in self[self.nxpath].items():
            self.nxpath = value.name
            if 'NX_class' in value.attrs:
                nxclass = value.attrs['NX_class']
            else:
                nxclass = None
            if isinstance(value, h5._hl.group.Group):
                children[name] = self._readgroup()
            else:
                children[name] = self._readdata(name)
        return children

    def _readgroup(self):
        """
        Reads the group with the current path and returns it as an NXgroup.
        """
        path = self[self.nxpath].name
        name = path.rsplit('/',1)[1]
        attrs = dict(self[self.nxpath].attrs)
        if 'NX_class' in attrs:
            nxclass = attrs['NX_class']
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
        group._saved = group._changed = True
        return group

    def writefile(self, tree):
        """
        Writes the NeXus file structure to a file.

        The file is assumed to start empty. Updating individual objects can be
        done using the h5py interface.
        """
        links = []
        self.nxpath = ""
        for entry in tree.entries.values():
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
        if hasattr(data, '_target'):
            return [(self.nxpath, data._target)]

        if data._uncopied_data:
            with data._uncopied_data.file as f:
                f.copy(data._uncopied_data.name, self[parent], self.nxpath)
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
        data._saved = True
        return []

    def _writegroup(self, group):
        """
        Writes the given group structure, including the data.

        NXlinks cannot be written until the linked group is created, so
        this routine returns the set of links that need to be written.
        Call writelinks on the list.
        """
        parent = '/' + self.nxpath.lstrip('/')
        self.nxpath = parent + '/' + group.nxname

        links = []
        if group.nxname not in self[parent]:
            self[parent].create_group(group.nxname)
        if group.nxclass and group.nxclass != 'NXgroup':
            self[self.nxpath].attrs['NX_class'] = group.nxclass
        self._writeattrs(group.attrs)
        if hasattr(group, '_target'):
            links += [(self.nxpath, group._target)]
        for child in group.entries.values():
            if child.nxclass == 'NXfield':
                links += self._writedata(child)
            elif hasattr(child,'_target'):
                links += [(self.nxpath+"/"+child.nxname,child._target)]
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
        for path,target in links:
            if path != target:
                # ignore self-links
                parent = "/".join(path.split("/")[:-1])
                self[parent]._id.link(target,path,h5.h5g.LINK_HARD)

    def copyfile(self, the_file):
        for entry in the_file['/']:
            the_file.copy(entry, self['/']) 
        self._setattrs()

    def _setattrs(self):
        from datetime import datetime
        self._file.attrs['file_name'] = self.filename
        self._file.attrs['file_time'] = datetime.now().isoformat()
        self._file.attrs['NeXus_version'] = '4.3.0'
        self._file.attrs['HDF5_Version'] = h5.version.hdf5_version
        self._file.attrs['h5py_version'] = h5.version.version

    @property
    def filename(self):
        """File name on disk"""
        return self._file.filename

    def _getfile(self):
        return self._file

    def _getattrs(self):
        return dict(self[self.nxpath].attrs)

    def _getpath(self):
        return self._path

    def _setpath(self, value):
        self._path = value

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
    import re
    sep=re.compile('[\[]*(\s*,*:*)+[\]]*')
    return filter(lambda x: len(x)>0, sep.split(axes))


class AttrDict(dict):

    """
    A dictionary class to assign all attributes to the NXattr class.
    """

    def __setitem__(self, key, value):
        if isinstance(value, NXattr):
            dict.__setitem__(self, key, value)
        else:
            dict.__setitem__(self, key, NXattr(value))


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
            self = value
        elif isinstance(value, NXobject):
            raise NeXusError("A data attribute cannot be a NXfield or NXgroup")
        else:
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
    _filename = None
    _mode = None
    _memfile = None
    _uncopied_data = None
    _saved = False
    _changed = True

    def __str__(self):
        return "%s:%s"%(self.nxclass,self.nxname)

    def __repr__(self):
        return "NXobject('%s','%s')"%(self.nxclass,self.nxname)

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
                txt3 = u" = " + unicode(str(self.attrs[k].nxdata))
            except UnicodeDecodeError, err:
                # this is a wild assumption to read non-compliant strings from Soleil
                txt3 = u" = " + unicode(str(self.attrs[k].nxdata), "ISO-8859-1")
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
        entries = self.entries
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
        if False: yield

    def dir(self,attrs=False,recursive=False):
        """
        Prints the object directory.

        The directory is a list of NeXus objects within this object, either
        NeXus groups or NXfields. If 'attrs' is True, NXfield attributes are
        displayed. If 'recursive' is True, the contents of child groups are
        also displayed.
        """
        print self._str_tree(attrs=attrs,recursive=recursive)

    @property
    def tree(self):
        """
        Returns the directory tree as a string.

        The tree contains all child objects of this object and their children.
        It invokes the 'dir' method with both 'attrs' and 'recursive' set
        to True.
        """
        return self._str_tree(attrs=True,recursive=True)

    def rename(self, name):
        if self.nxfilemode == 'r':
            raise NeXusError("NeXus file is readonly")
        path = self.nxpath
        self.nxname = name           
        if self.nxfilemode == 'rw':
            with self.nxfile as f:
                f[self.nxpath] = f[path]
                del f[path]
            self._saved = True

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
            for node in root.walk():
                node._saved = True
            return root
        else:
            raise NeXusError("No output file specified")

    @property
    def saved(self):
        """
        Property: Returns True if the object has been saved to a file.
        """
        return self._saved

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

    def _getname(self):
        return self._name

    def _setname(self, value):
        if self.nxgroup:
            self.nxgroup._entries[value] = self.nxgroup._entries[self._name]
            del self.nxgroup._entries[self._name]
        self._name = str(value)
        self._saved = False
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

    def _getfile(self):
        _root = self.nxroot
        if self._filename:
            return NXFile(self._filename,_root._mode)
        elif self.nxroot._filename:
            return NXFile(self.nxroot._filename, _root._mode)
        else:
            return None

    def _getfilename(self):
        return self.nxroot._filename

    def _getfilemode(self):
        return self.nxroot._mode

    def _getattrs(self):
        return self._attrs

    nxclass = property(_getclass, doc="Property: Class of NeXus object")
    nxname = property(_getname, _setname, doc="Property: Name of NeXus object")
    nxgroup = property(_getgroup, doc="Property: Parent group of NeXus object")
    nxpath = property(_getpath, doc="Property: Path to NeXus object")
    nxfile = property(_getfile, doc="Property: File handle of NeXus object's tree")
    nxfilename = property(_getfilename, doc="Property: Filename of NeXus object")
    nxfilemode = property(_getfilemode, doc="Property: File mode of root object")
    nxroot = property(_getroot, doc="Property: Root group of NeXus object's tree")
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
        self._name = name.replace(' ','_')
        self._group = group
        self._dtype = dtype
        if dtype:
            if dtype == 'char':
                dtype = 'S'
            try:
                self._dtype = np.dtype(dtype)
            except:
                raise NeXusError("Invalid data type: %s" % dtype)
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
        self._attrs = AttrDict()
        self._setattrs(attrs)
        if 'units' in attrs:
            units = attrs['units']  # TODO: unused variable
        else:
            units = None            # TODO: unused variable
        del attrs
        self._saved = False
        self._masked = False
        self._filename = None
        self._memfile = None
        self._setdata(value)
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
            return object.__getattr__(name)
        elif name in _npattrs:
            return self.nxdata.__getattribute__(name)
        elif name in self.attrs:
            return self.attrs[name].nxdata
        raise KeyError(name+" not in "+self.nxname)

    def __setattr__(self, name, value):
        """
        Adds an attribute to the NXfield 'attrs' dictionary unless the attribute
        name starts with 'nx' or '_', or unless it is one of the standard Python
        attributes for the NXfield class.
        """
        if name.startswith('_') or name.startswith('nx') or \
           name == 'mask' or name == 'shape' or name == 'dtype':
            object.__setattr__(self, name, value)
            return
        if isinstance(value, NXattr):
            self._attrs[name] = value
        else:
            self._attrs[name] = NXattr(value)
        if self.nxfilemode == 'rw':
            with self.nxfile as f:
                f.nxpath = self.nxpath
                f._writeattrs(self.attrs)
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
            raise NeXusError("File opened as readonly")
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
            result = f[self.nxpath][idx]
            if 'mask' in self.attrs:
                try:
                    mask = self.nxgroup[self.attrs['mask'].nxdata]
                    result = np.ma.array(result, mask=f[mask.nxpath][idx])
                except KeyError:
                    pass
        return result

    def _put_filedata(self, idx, value):
        with self.nxfile as f:
            if isinstance(value, np.ma.MaskedArray):
                if self.mask is None:
                    self._create_mask()
                f[self.nxpath][idx] = value.data
                f[self.mask.nxpath][idx] = value.mask
            else:
                f[self.nxpath][idx] = value

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
        self._memfile = NXFile(tempfile.mktemp(suffix='.nxs'),
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
                mask_name = self.attrs['mask'].nxdata
                if mask_name in self.nxgroup.entries:
                    return mask_name
            mask_name = '%s_mask' % self.nxname
            self.nxgroup[mask_name] = NXfield(shape=self._shape, dtype=np.bool, 
                                              fillvalue=False)
            self.attrs['mask'] = mask_name
            self.mask.update()
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
        self.update()

    def _get_uncopied_data(self):
        with self._uncopied_data.file as f:
            if self.nxfilemode == 'rw':
                f.copy(self._uncopied_data.name, self.nxpath)
            else:
                self._create_memfile()
                f.copy(self._uncopied_data.name, self._memfile, 'data')
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
        dpcpy._saved = False
        dpcpy._memfile = None
        dpcpy._uncopied_data = None
        if obj._value is not None:
            dpcpy._value = copy(obj._value)
        elif obj._memfile:
            dpcpy._memfile = obj._memfile
        elif obj.nxfilemode:
            dpcpy._uncopied_data = obj.nxfile[obj.nxpath]
        for k, v in obj.attrs.items():
            dpcpy.attrs[k] = copy(v)
        if 'target' in dpcpy.attrs:
            del dpcpy.attrs['target']
        return dpcpy

    def update(self):
        """
        Writes the NXfield, including attributes, to the NeXus file.
        """
        if self.nxfilemode == 'rw':
            with self.nxfile as f:
                f.nxpath = self.nxgroup.nxpath
                f._writedata(self)
            self._saved = True

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
                return ''.join(self._value)
            else:
                return str(self._value)
        return ""

    def _str_value(self,indent=0):
        v = str(self)
        if '\n' in v:
            v = '\n'.join([(" "*indent)+s for s in v.split('\n')])
        return v

    def _str_tree(self,indent=0,attrs=False,recursive=False):
        dims = 'x'.join([str(n) for n in self.shape])
        s = str(self)
        if '\n' in s or s == "":
            s = "%s(%s)"%(self.dtype, dims)
        v=[" "*indent + "%s = %s"%(self.nxname, s)]
        if attrs and self.attrs: v.append(self._str_attrs(indent=indent+2))
        return "\n".join(v)

    def walk(self):
        yield self

    def _getaxes(self):
        """
        Returns a list of NXfields containing axes.

        Only works if the NXfield has the 'axes' attribute
        """
        try:
            return [getattr(self.nxgroup,name) for name in _readaxes(self.axes)]
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
                elif self._memfile:
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
        if value is not None:
            self._value, self._dtype, self._shape = \
                _getvalue(value, self._dtype, self._shape)
            self._saved = False
            self.update()

    def _getmask(self):
        """
        Returns the NXfield's mask as an array

        Only works if the NXfield is in a group and has the 'mask' attribute set
        or if the NXfield array is defined as a masked array.
        """
        if 'mask' in self.attrs:
            if self.nxgroup:
                try:
                    return self.nxgroup[self.attrs['mask'].nxdata]
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
                mask_name = self.attrs['mask'].nxdata
                if mask_name in self.nxgroup.entries:
                    self.nxgroup[mask_name][()] = value
            else:
                del self.attrs['mask']
        elif self._value is None:
            if self._memfile:
                self._create_memmask()
                self._memfile['mask'][()] = value
        if self._value is not None:
            self._value = np.ma.array(self._value.data, mask=value)

    def _getdtype(self):
        return self._dtype

    def _setdtype(self, value):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file is locked')
        self._dtype = np.dtype(value)
        if self._value is not None:
            self._value = np.asarray(self._value, dtype=self._dtype)
        self._saved = False
        self.update()
        self.set_changed()

    def _getshape(self):
        return self._shape

    def _setshape(self, value):
        if self.nxfilemode == 'r':
            raise NeXusError('NeXus file is locked')
        if self._value is not None:
            if self._value.size != np.prod(value):
                raise ValueError('Total size of new array must be unchanged')
            self._value.shape = tuple(value)
        self._shape = tuple(value)
        self._saved = False
        self.update()
        self.set_changed()

    def _getndim(self):
        return len(self.shape)

    def _getsize(self):
        return len(self)

    nxdata = property(_getdata, _setdata, doc="Property: The data values")
    nxaxes = property(_getaxes, doc="Property: The plotting axes")
    mask = property(_getmask, _setmask, doc="Property: The data mask")
    dtype = property(_getdtype, _setdtype, 
                     doc="Property: Data type of NeXus field")
    shape = property(_getshape, _setshape, doc="Property: Shape of NeXus field")
    ndim = property(_getndim, doc="Property: No. of dimensions of NeXus field")
    size = property(_getsize, doc="Property: Size of NeXus field")

    def plot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             zmin=None, zmax=None, **opts):
        """
        Plot data if the signal and axes attributes are defined.

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

        Raises NeXusError if the data could not be plotted.
        """

        from nexpy.gui.plotview import plotview

        # Check there is a plottable signal
        if 'signal' in self.attrs.keys() and 'axes' in self.attrs.keys():
            axes = [getattr(self.nxgroup, name) 
                    for name in _readaxes(self.axes)]
            data = NXdata(self, axes, title=self.nxpath)
        else:
            raise NeXusError('No plottable signal defined')

        # Plot with the available plotter
        plotview.plot.plot(data, fmt, xmin, xmax, ymin, ymax, zmin, zmax, **opts)
    
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
            self._name = opts["name"].replace(' ','_')
            del opts["name"]
        self._entries = {}
        if "entries" in opts.keys():
            for k,v in opts["entries"].items():
                self._entries[k] = v
            del opts["entries"]
        self._attrs = AttrDict()
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
        return sorted(dir(super(self.__class__, self))+self.entries.keys())

    def __repr__(self):
        return "%s('%s')" % (self.__class__.__name__,self.nxname)

    def _str_value(self,indent=0):
        return ""

    def walk(self):
        yield self
        for node in self.entries.values():
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
            return self.attrs[key].nxdata
        raise KeyError(key+" not in "+self.nxclass+":"+self.nxname)

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
            self._attrs[name] = value
            self.set_changed()
            if self.nxfilemode == 'rw':
                with self.nxfile as f:
                    f.nxpath = self.nxpath
                    f._writeattrs(self.attrs)
        else:
            self[name] = value

    def __getitem__(self, idx):
        """
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
        if isinstance(idx, NXattr):
            idx = idx.nxdata
        if isinstance(idx, basestring): #i.e., requesting a dictionary value
            return self._entries[idx]

        if not self.nxsignal:
            raise NeXusError("No plottable signal")
        if not hasattr(self,"nxclass"):
            raise NeXusError("Indexing not allowed for groups of unknown class")
        if isinstance(idx, int) or isinstance(idx, slice):
            axes = self.nxaxes
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
            axes = self.nxaxes
            for ind in idx:
                ind = convert_index(ind, axes[i])
                axes[i] = axes[i][ind]
                slices.append(ind)
                i = i + 1
            result = NXdata(self.nxsignal.__getitem__(tuple(slices)), axes)
            if self.nxerrors: result.errors = self.errors.__getitem__(tuple(slices))
        if self.nxtitle:
            result.title = self.nxtitle
        result = simplify_axes(result)
        return result

    def __setitem__(self, key, value):
        """
        Adds or modifies an item in the NeXus group.
        """
        if self.nxfilemode == 'r':
            raise NeXusError("NeXus file is readonly")
        elif key in self.entries and isinstance(self._entries[key], NXlink):
            raise NeXusError("Cannot assign values to an NXlink object")
        if isinstance(value, NXroot):
            raise NeXusError("Cannot assign an NXroot group to another group")
        elif isinstance(value, NXlink) and self.nxroot == value.nxroot:
            self._entries[key] = copy(value)
        elif isinstance(value, NXobject):
            if value.nxgroup:
                memo = {}
                value = deepcopy(value, memo)
            value._group = self
            value._name = key
            self._entries[key] = value
        elif key in self.entries:
            self._entries[key]._setdata(value)
        else:
            self._entries[key] = NXfield(value=value, name=key, group=self)
        if isinstance(self._entries[key], NXfield):
            field = self._entries[key]
            if not field._value is None:
                if isinstance(field._value, np.ma.MaskedArray):
                    mask_name = field._create_mask()
                    self[mask_name] = field._value.mask
            elif field._memfile is not None:
                if 'mask' in field._memfile:
                    mask_name = field._create_mask()
                    self[mask_name]._create_memfile()
                    field._memfile.copy('mask', self[mask_name]._memfile, 'data')
                    del field._memfile['mask']
        self.update()
    
    def __delitem__(self, key):
        if isinstance(key, basestring): #i.e., deleting a NeXus object
            if self.nxfilemode == 'rw':
                with self.nxfile as f:
                    if 'mask' in self._entries[key].attrs:
                        del f[self._entries[key].mask.nxpath]
                    del f[self._entries[key].nxpath]
            if 'mask' in self._entries[key].attrs:
                del self._entries[self._entries[key].mask.nxname]
            del self._entries[key]
            self.set_changed()

    def __deepcopy__(self, memo):
        if isinstance(self, NXlink):
            obj = self.nxlink
        else:
            obj = self
        dpcpy = obj.__class__()       
        memo[id(self)] = dpcpy
        dpcpy._changed = True
        dpcpy._saved = False
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
                f.nxpath = self.nxgroup.nxpath
                links = f._writegroup(self)
                f._writelinks(links)
        elif self.nxfilemode is None:
            for node in self.walk():
                if isinstance(node, NXfield) and node._uncopied_data:
                    node._get_uncopied_data()
        self.set_changed()

    def keys(self):
        """
        Returns the names of NeXus objects in the group.
        """
        return self._entries.keys()

    def values(self):
        """
        Returns the values of NeXus objects in the group.
        """
        return self._entries.values()

    def items(self):
        """
        Returns a list of the NeXus objects in the group as (key,value) pairs.
        """
        return self._entries.items()

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
                    self._entries[target.nxname] = NXlink(target=target, group=self)
                    self.update()
                else:
                    raise NeXusError("Link target must be an NXobject")
            else:
                raise NeXusError("Cannot link an object to a group with a different root")
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
            slab[slab_axis] = convert_index(slab[slab_axis],self.nxaxes[slab_axis])
            if isinstance(slab[slab_axis], int):
                slab.pop(slab_axis)
                projection_axes.pop(projection_axes.index(slab_axis))
                for i in range(len(projection_axes)):
                    if projection_axes[i] > slab_axis:
                        projection_axes[i] -= 1
        if projection_axes:
            result = result.sum(projection_axes)
        if len(axes) > 1 and axes[0] > axes[1]:
            result.nxsignal = result.nxsignal.transpose()
            if result.nxerrors:
                result["errors"] = result["errors"].transpose()            
            result.nxaxes = result.nxaxes[::-1]            
        return result        

    def component(self, nxclass):
        """
        Finds all child objects that have a particular class.
        """
        return [E for _name,E in self.entries.items() if E.nxclass==nxclass]

    def signals(self):
        """
        Returns a dictionary of NXfield's containing signal data.

        The key is the value of the signal attribute.
        """
        signals = {}
        for obj in self.entries.values():
            if 'signal' in obj.attrs:
                signals[obj.attrs['signal'].nxdata] = obj
        return signals

    def _signal(self):
        """
        Returns the NXfield containing the signal data.
        """
        for obj in self.entries.values():
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
        if current_signal:
            current_signal.signal = NXattr(2)
            if 'axes' not in signal.attrs and 'axes' in current_signal.attrs:
                signal.axes = current_signal.axes
        self.entries[signal.nxname] = signal
        self.entries[signal.nxname].signal = NXattr(1)
        return self.entries[signal.nxname]

    def _axes(self):
        """
        Returns a list of NXfields containing the axes.
        """
        try:
            return [getattr(self,name) for name in _readaxes(self.nxsignal.axes)]
        except (KeyError, AttributeError):
            axes = {}
            for entry in self._entries:
                if 'axis' in self[entry].attrs:
                    axes[self[entry].axis] = self[entry]
            if axes:
                return [axes[key] for key in sorted(axes.keys())]
            else:
                return None

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
        self.nxsignal.axes = NXattr(":".join([axis.nxname for axis in axes]))

    def _errors(self):
        """
        Returns the NXfield containing the signal errors.
        """
        try:
            return self.entries['errors']
        except KeyError:
            return None

    def _set_errors(self, errors):
        """
        Setter for the errors.
        
        The argument should be a valid NXfield.
        """
        self.entries['errors'] = errors
        return self.entries['errors']

    def _title(self):
        """
        Returns the title as a string.

        If there is no title attribute in the string, the parent
        NXentry group in the group's path is searched.
        """
        if 'title' in self.entries:
            return str(self.title)
        elif self.nxgroup and 'title' in self.nxgroup.entries:
            return str(self.nxgroup.title)
        else:
            return self.nxpath

    def _getentries(self):
        return self._entries

    nxsignal = property(_signal, _set_signal, "Property: Signal NXfield within group")
    nxaxes = property(_axes, _set_axes, "Property: List of axes within group")
    nxerrors = property(_errors, _set_errors, "Property: Errors NXfield within group")
    nxtitle = property(_title, "Property: Title for group plot")
    entries = property(_getentries,doc="Property: NeXus objects within group")

    def plot(self, fmt='', xmin=None, xmax=None, ymin=None, ymax=None,
             zmin=None, zmax=None, **opts):
        """
        Plot data contained within the group.

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

        Raises NeXusError if the data could not be plotted.
        """

        from nexpy.gui.plotview import plotview

        data = self
        if self.nxclass == "NXroot":
            try:
                data = data.NXdata[0]
            except:
                data = data.NXentry[0]
        if data.nxclass == "NXentry":
            if data.NXdata:
                data = data.NXdata[0]
            elif data.NXmonitor:
                data = data.NXmonitor[0]
            elif data.NXlog:
                data = data.NXlog[0]
            else:
                raise NeXusError('No NXdata group found')

        # Check there is a plottable signal
        if not data.nxsignal:
            raise NeXusError('No plottable signal defined')

        # Plot with the available plotter
        plotview.plot.plot(data, fmt, xmin, xmax, ymin, ymax, zmin, zmax, **opts)
    
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

class NXlink(NXobject):

    """
    Class for NeXus linked objects.

    The real object will be accessible by following the link attribute.
    """

    _class = "NXlink"

    def __init__(self, target=None, name='link', group=None):
        self._group = group
        self._class = "NXlink"
        if isinstance(target, NXobject):
            self._name = target.nxname
            self._target = self.nxlink.attrs["target"] = target.nxpath
            if target.nxclass == "NXlink":
                raise NeXusError("Cannot link to another NXlink object")
            elif target.nxclass == "NXfield":
                self.__class__ = NXlinkfield
            else:
                self.__class__ = NXlinkgroup
        else:
            self._name = name
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
        return "NXlink('%s')"%(self._target)

    def __str__(self):
        return str(self.nxlink)

    def _str_tree(self, indent=0, attrs=False, recursive=False):
        if self.nxlink:
            return self.nxlink._str_tree(indent, attrs, recursive)
        else:
            return " "*indent+self.nxname+' -> '+self._target

    def _getlink(self):
        link = self.nxroot
        if link:
            try:
                for level in self._target[1:].split('/'):
                    link = link.entries[level]
                return link
            except AttributeError:
                return None
        else:
            return None

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
        return self.nxlink.entries

    entries = property(_getentries,doc="Dictionary of NeXus objects within group")


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
            self._mode = 'r'

    def unlock(self):
        """Make the tree modifiable"""
        if self._filename:
            self._mode = 'rw'


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
        result = NXentry(entries=self.entries, attrs=self.attrs)
        try:
            names = [group.nxname for group in self.component("NXdata")]
            for name in names:
                if isinstance(other.entries[name], NXdata):
                    result.entries[name] = self.entries[name] + other.entries[name]
                else:
                    raise KeyError
            names = [group.nxname for group in self.component("NXmonitor")]
            for name in names:
                if isinstance(other.entries[name], NXmonitor):
                    result.entries[name] = self.entries[name] + other.entries[name]
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
                if isinstance(other.entries[name], NXdata):
                    result.entries[name] = self.entries[name] - other.entries[name]
                else:
                    raise KeyError
            names = [group.nxname for group in self.component("NXmonitor")]
            for name in names:
                if isinstance(other.entries[name], NXmonitor):
                    result.entries[name] = self.entries[name] - other.entries[name]
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

    def __init__(self, signal=None, axes=None, *items, **opts):
        self._class = "NXdata"
        NXgroup.__init__(self, *items, **opts)
        if signal is not None:
            if isinstance(signal,NXfield):
                if signal.nxname == "unknown": signal.nxname = "signal"
                self[signal.nxname] = signal
                self[signal.nxname].signal = 1
                signalname = signal.nxname
            else:
                self["signal"] = signal
                self["signal"].signal = 1
                signalname = "signal"
            if axes is not None:
                if not isinstance(axes,tuple) and not isinstance(axes,list):
                    axes = [axes]
                axisnames = {}
                i = 0
                for axis in axes:
                    i = i + 1
                    if isinstance(axis,NXfield):
                        if axis._name == "unknown": axis._name = "axis%s" % i
                        self[axis.nxname] = axis
                        axisnames[i] = axis.nxname
                    else:
                        axisname = "axis%s" % i
                        self[axisname] = axis
                        axisnames[i] = axisname
                self[signalname].axes = ":".join(axisnames.values())

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
                result.entries[self.nxsignal.nxname] = self.nxsignal + other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = np.sqrt(self.errors.nxdata**2+other.errors.nxdata**2)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot add two arbitrary groups")
        else:
            result.entries[self.nxsignal.nxname] = self.nxsignal + other
            result.entries[self.nxsignal.nxname].nxname = self.nxsignal.nxname
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
                result.entries[self.nxsignal.nxname] = self.nxsignal - other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = np.sqrt(self.errors.nxdata**2+other.errors.nxdata**2)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot subtract two arbitrary groups")
        else:
            result.entries[self.nxsignal.nxname] = self.nxsignal - other
            result.entries[self.nxsignal.nxname].nxname = self.nxsignal.nxname
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
                result.entries[self.nxsignal.nxname] = self.nxsignal * other.nxsignal
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = np.sqrt((self.errors.nxdata*other.nxsignal.nxdata)**2+
                                                (other.errors.nxdata*self.nxsignal.nxdata)**2)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot multiply two arbitrary groups")
        else:
            result.entries[self.nxsignal.nxname] = self.nxsignal * other
            result.entries[self.nxsignal.nxname].nxname = self.nxsignal.nxname
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
                # error here, signal and othersignal not defined here
                #result.entries[self.nxsignal.nxname] = signal / othersignal
                result.entries[self.nxsignal.nxname] = self.nxsignal / other.nxsignal
                resultvalues = result.entries[self.nxsignal.nxname].nxdata
                if self.nxerrors:
                    if other.nxerrors:
                        result.errors = (np.sqrt(self.errors.nxdata**2 +
                                         (resultvalues*other.errors.nxdata)**2)
                                         / other.nxsignal)
                    else:
                        result.errors = self.errors
                return result
        elif isinstance(other, NXgroup):
            raise NeXusError("Cannot divide two arbitrary groups")
        else:
            result.entries[self.nxsignal.nxname] = self.nxsignal / other
            result.entries[self.nxsignal.nxname].nxname = self.nxsignal.nxname
            if self.nxerrors: result.errors = self.errors / other
            return result


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
        axis = [self.time]      # TODO: unused variable
        title = NXfield("%s Log" % self.value.nxname.upper())
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
        (isinstance(idx.start, float) or isinstance(idx.stop, float)):
        if idx.start is not None:
            start = axis.index(idx.start)
        else:
            start = 0
        if idx.stop is not None:
            stop = axis.index(idx.stop,max=True) + 1
        else:
            stop = axis.size - 1
        if stop <= start+1:
            idx = start
        else:
            idx = slice(start, stop)
    elif isinstance(idx, slice):
        if idx.start is not None and idx.stop is not None:
            if idx.stop == idx.start or idx.stop == idx.start + 1:
                idx = idx.start
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
        if data.nxerrors._value:
            data.nxerrors._value.shape = shape
    axes = []
    for axis in data.nxaxes:
        if len(axis) > 1: axes.append(axis)
    data.nxsignal.axes = ":".join([axis.nxname for axis in axes])
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
    file = NXFile(filename, mode)
    tree = file.readfile()
    file.close()
    return tree

#Definition for when there are name clashes with Numpy
nxload = load
__all__.append('nxload')

def save(filename, group, format='w'):
    """
    Writes a NeXus file from a tree of objects.
    """
    if group.nxclass == "NXroot":
        tree = group
    elif group.nxclass == "NXentry":
        tree = NXroot(group)
    else:
        tree = NXroot(NXentry(group))
    file_object = NXFile(filename, format)
    file_object.writefile(tree)
    file_object.close()

def tree(filename):
    """
    Reads and summarize the named NeXus file.
    """
    nxfile = load(filename)
    print nxfile.tree

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

