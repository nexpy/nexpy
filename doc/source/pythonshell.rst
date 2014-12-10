*************************
Python Interface to NeXus
*************************
The Python interface to NeXus can be used within a standard Python or iPython 
shell:: 

 $ python
 Python 2.7.2 (default, Oct 11 2012, 20:14:37) 
 [GCC 4.2.1 Compatible Apple Clang 4.0 (tags/Apple/clang-418.0.60)] on darwin
 Type "help", "copyright", "credits" or "license" for more information.
 >>> from nexpy.api import nexus

.. note:: If you are creating NeXus groups, it is often more convenient to 
          import the data using ``from nexpy.api.nexus import *``. Since this 
          produces a name clash with the numpy 'load' module, 'nxload' has been
          defined as an alias for the NeXus 'load' module. 

Loading NeXus Data
==================
The entire tree structure of a NeXus file can be loaded by a single command::

 >>> a=nexus.load('sns/data/ARCS_7326_tof.nxs')

The assigned variable now contains the entire tree structure of the file, which 
can be displayed by printing the 'tree' property::

 >>> print a.tree
 root:NXroot
  @HDF5_Version = 1.8.2
  @NeXus_version = 4.2.1
  @file_name = ARCS_7326_tof.nxs
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

Individual data items are immediately available from the command-line::

 >>> print a.entry.run_number
 7326

Note that only the tree structure and the values of smaller data sets are read
from the file to avoid using up memory unnecessarily. In the above example, only
the types and dimensions of the larger data sets are displayed in the tree.
Data is loaded only when it is needed, for plotting or calculations, either as 
a complete array, if memory allows, or as a series of slabs (see below).

.. note:: The variable NX_MEMORY defines the maximum size in MB of data that 
          will be read from a file. If the NXfield is larger than NX_MEMORY, the
          data will have to be read as a series of slabs. The default value is
          500.

Load Options
------------
There is a second optional argument to the load module that defines the access
mode for the existing data. For example, the following opens the file in 
read/write mode::

 >>> a=nx.load('chopper.nxs', mode='rw')

The default mode is 'r', *i.e.*, readonly access.

.. warning:: If the file is opened in read/write mode, any changes are made 
             automatically to the file itself. In particular, any deletions of 
             file objects will be irreversible. Make sure you have a backup
             if you open a mission-critical file. In the :doc:`pythongui`, this 
             can be achieved using the 'Duplicate...' menu item.

Creating NeXus Data
===================
It is just as easy to create new NeXus data sets from scratch using numpy 
arrays. The following example shows the creation of a simple function, which is 
then saved to a file::
 
 >>> import numpy as np
 >>> x=y=np.linspace(0,2*np.pi,101)
 >>> X,Y=np.meshgrid(x,y)
 >>> z=np.sin(X)*np.sin(Y)
 >>> a=NXdata(z,[y,x])
 >>> a.save('function.nxs')

This file can then be loaded again::

 >>> b=nx.load('function.nxs')
 >>> print b.tree
 root:NXroot
  @HDF5_Version = 1.8.2
  @NeXus_version = 4.2.1
  @file_name = function.nxs
  @file_time = 2010-05-10T17:01:13+01:00
  entry:NXentry
    data:NXdata
      axis1 = float64(101)
      axis2 = float64(101)
      signal = float64(101x101)
        @axes = axis1:axis2
        @signal = 1

.. note:: The save() method automatically wraps any valid NeXus data in an 
          NXentry group, in order to produce a standard-compliant file. See
          `Saving NeXus Data`_ for more details.

NeXus Objects
=============
NeXus data is stored as a hierarchical tree structure, much like a computer file 
system. NeXus data structures consist of groups, with base class NXgroup, which 
can contain fields, with base class NXfield, and/or other groups.

NeXus Fields
------------
NeXus data values are stored in NeXus objects of class 'NXfield'. The NXfield
class wraps standard numpy arrays, scalars, and python strings so that
additional metadata (or attributes) and methods can be associated with them. 

There are three ways to create an NXfield.

* Direct assignment::

    >>> x = NXfield(np.linspace(0,2*np.pi,101), units='degree')

  The data value is given by the first positional argument, and may be a Python
  scalar or string, or a numpy array. In this method, keyword arguments can be
  used to define NXfield attributes.

* Attribute assignment as the child of a NeXus group::

    >>> a.entry.sample.temperature=40.0

  The assigned values are automatically converted to an NXfield::

    >>> a.entry.sample.temperature
    NXfield(name=temperature,value=40.0)

* Dictionary assignment to the NeXus group::

    >>> a.entry.sample["temperature"]=40.0

  This is equivalent to the second method, but should be used if there is a 
  danger of a name clash with an NXfield method, *e.g.*, if the NXfield is 
  called 'plot'.
  
.. note:: When using the NeXpy GUI shell (see :doc:`pythongui`), it is possible 
          to use tab completion to check for possible name clashes with NXfield 
          methods. To avoid name clashes in scripts, use dictionary assignments.

The data in an NXfield can be of type integer, float, or character. The type is
normally inherited automatically from the data type of the Python object, 
although it is possible to define alternative (but compatible) datatypes. For 
example, a float64 array can be converted to float32 on assignment::

  >>> x=np.linspace(0,2*np.pi,101)
  >>> x.dtype
  dtype('float64')
  >>> a=NXfield(x,dtype='float32')
  >>> a.dtype
  dtype('float32')
  >>> b=NXfield('Some Text')
  >>> b.dtype, b.shape
  (dtype('S9'), ())

.. note:: Numeric dtypes can be defined either as a string, *e.g.*, 'int16', 
          'float32', or using the numpy dtypes, *e.g.*, np.int16, np.float32.

Similarly, the shape and dimension sizes of an integer or float array is 
inherited from the assigned numpy array. It is possible to initialize an NXfield
array without specifying the data values in advance, *e.g.*, if the data has to
be created in slabs::

  >>> a=NXfield(dtype=np.float32, shape=[2048,2048,2048])
  >>> a
  NXfield(dtype=float32,shape=(2048, 2048, 2048))

NeXus attributes
^^^^^^^^^^^^^^^^  
The NeXus standard allows additional attributes to be attached to NXfields to
contain metadata ::

 >>> a.entry.sample.temperature.units='K'

These have a class of NXattr. They can be defined using the 'attrs' dictionary 
if necessary to avoid name clashes::

 >>> a.entry.sample.temperature.attrs['units']='K'

Other common attributes include the 'signal' and 'axes' attributes used to 
define the plottable signal and independent axes, respectively, in a NXdata 
group.

When a NeXus tree is printed, the attributes are prefixed by '@'::

 >>> print a.entry.sample.tree
 sample:NXsample
   temperature = 40.0
     @units = K 

Slab Input/Output
^^^^^^^^^^^^^^^^^
If the size of the NXfield array is too large to be loaded into memory (as 
defined by NX_MEMORY), the data values should be read or written in as a series 
of slabs represented by NXfield slices::

 >>> for i in range(Ni):
         for j in range(Nj):
             value = root.NXentry[0].data.data[i,j,:]
             ...

.. note:: NXfield values are stored in its 'nxdata' attribute. For integers and
          floats, this will be a numpy array. If the values have not been 
          loaded, 'nxdata' is set to None.

Masked Arrays
^^^^^^^^^^^^^
Numpy has the ability to store arrays with masks to remove missing or invalid
data from computations of, *e.g.*, averages or maxima. Since Matplotlib is able 
to handle masked arrays and removes masked data from plots, this is a convenient 
way of preventing bad data from contaminating statistical analyses, while 
preserving all the data values, good and bad, *i.e.*, masks can be turned on and 
off. 

NeXpy uses the same syntax as Numpy for masking and unmasking data.

 >>> z = NXfield([1,2,3,4,5,6], name='z')
 >>> z[3:5] = np.ma.masked
 >>> z
 NXfield([1 2 3 -- -- 6])
 >>> z.mask
 array([False, False, False,  True,  True, False], dtype=bool)
 >>> z.mask[3] = np.ma.nomask
 >>> z
 NXfield([1 2 3 4 -- 6])
 
.. warning:: If you perform any operations on a masked array, those operations 
             are not performed on the masked values. It is not advisable
             to remove a mask if you have modified the unmasked values. 

If the NXfield does not have a parent group, the mask is stored within the field
as in Numpy arrays. However, if the NXfield has a parent group, the mask is 
stored in a separate NXfield that is generated automatically by the mask
assignment or whenever the masked NXfield is assigned to a group. The mask is
identified by the 'mask' attribute of the masked NXfield.

 >>> print NXlog(z).tree
 log:NXlog
 z = [1 2 3 4 -- 6]
  @mask = z_mask
 z_mask = [False False False False  True False]

The mask can then be saved to the NeXus file if required.

.. warning:: In principle, the NXfield containing the mask can be modified 
             manually, but it is recommended that modifications to the mask use
             the methods described above.
             
Masks can also be set using the Projection panel in the :doc:`pythongui`.

NeXus Groups
------------
NeXus groups are defined as subclasses of the NXgroup class, with the class name 
defining the type of information they contain, *e.g.*, the NXsample class 
contains metadata that define the measurement sample, such as its temperature or 
lattice parameters. The initialization parameters can be used to populate the 
group with other predefined NeXus objects, either groups or fields::

 >>> temperature = NXfield(40.0, units='K')
 >>> sample = NXsample(temperature=temperature)
 >>> print sample.tree
 sample:NXsample
   temperature = 40.0
     @units = K

In this example, it was necessary to use the keyword form to add the NXfield 
'temperature' since its name is otherwise undefined within the NXsample group. 
However, the name is set automatically if the NXfield is added as an attribute 
or dictionary assignment::

 >>> sample = NXsample()
 >>> sample.temperature=NXfield(40.0, units='K')
 sample:NXsample
   temperature = 40.0
     @units = K

The NeXus objects in a group (NXfields or NXgroups) can be accessed as  
dictionary items::

 >>> sample["temperature"] = 40.0
 >>> sample.keys()
 ['temperature']
 
.. note:: It is also possible to reference objects by their complete paths with
          respect to the root object, *e.g.*, root['/entry/sample/temperature'].

If a group is not created as another group attribute, its internal name defaults
to the class name without the 'NX' prefix. This can be useful in automatically
creating nested groups with minimal typing::

 >>> a=NXentry(NXsample(temperature=40.0),NXinstrument(NXdetector(distance=10.8)))
 >>> print a.tree
 entry:NXentry
   instrument:NXinstrument
     detector:NXdetector
       distance = 10.8
   sample:NXsample
     temperature = 40.0

.. seealso:: Existing NeXus objects can also be inserted directly into groups.
             See :mod:`nexpy.api.nexus.tree.NXgroup.insert`

NXdata Groups
^^^^^^^^^^^^^
NXdata groups contain data ready to be plotted. That means that the group should
consist of an NXfield containing the data and one or more NXfields containing
the axes. NeXus defines a method of associating axes with the appropriate
dimension, but NeXpy provides a simple constructor that implements this method
automatically. This was already demonstrated in the example above, reproduced
here::

 >>> import numpy as np
 >>> x=y=np.linspace(0,2*np.pi,101)
 >>> X,Y=np.meshgrid(x,y)
 >>> z=np.sin(X)*np.sin(Y)
 >>> a=NXdata(z,[y,x])

The first positional argument is an NXfield or numpy array containing the data,
while the second is a list containing the axes, again as NXfields or numpy
arrays. In this example, the names of the arrays have not been defined within an
NXfield so default names were assigned::

 >>> print a.tree
 data:NXdata
   axis1 = float64(101)
   axis2 = float64(101)
   signal = float64(101x101)
     @axes = axis1:axis2
     @signal = 1

.. note:: The plottable signal is identified by the NXfield with the 'signal'
          attribute set to 1. The 'signal' NXfield has an attribute, 'axes', 
          which defines the axes as a string of NXfield names delimited here by 
          a colon. White space or commas can also be used as delimiters. The
          NXdata constructor sets these attributes automatically.

.. warning:: Numpy stores arrays by default in C, or row-major, order, *i.e.*, 
             in the array 'signal(axis1,axis2)', axis2 is the fastest to vary. 
             In most image formats, *e.g.*, TIFF files, the x-axis is assumed
             to be the fastest varying axis, so we are adopting the same
             convention and plotting as 'signal(y,x)'. The :doc:`pythongui` 
             allows the x and y axes to be swapped.

Names can be assigned explicitly when creating the NXfield through the 'name' 
attribute::

 >>> phi=NXfield(np.linspace(0,2*np.pi,101), name='polar_angle')
 >>> data=NXfield(np.sin(phi), name='intensity')
 >>> a=NXdata(data,(phi))
 >>> print a.tree
 data:NXdata
   intensity = float64(101)
     @axes = polar_angle
     @signal = 1
   polar_angle = float64(101)

.. note:: In the above example, the x-axis, 'phi', was defined as a tuple in the
          second positional argument of the NXdata call. It could also have been
          defined as a list. However, in the case of one-dimensional signals, it
          would also have been acceptable just to call NXdata(data, phi), 
          *i.e.*, without embedding the axis in a tuple or list. 

It is also possible to define the plottable signal and/or axes using the 
'nxsignal' and 'nxaxes' properties, respectively::

 >>> phi=np.linspace(0,2*np.pi,101)
 >>> a=NXdata()
 >>> a.nxsignal=NXfield(np.sin(phi), name='intensity')
 >>> a.nxaxes=NXfield(phi, name='polar_angle')
 >>> print a.tree
 data:NXdata
   intensity = float64(101)
     @axes = polar_angle
     @signal = 1
   polar_angle = float64(101)


NeXus Links
-----------
NeXus allows groups and fields to be assigned to multiple locations through the
use of links. These objects have the class NXlink and contain the attribute 
'target', which identifies the parent object. It is also possible to link to
fields in another NeXus file (see 'External Links' below).

For example, the polar angle and time-of-flight arrays may logically be stored 
with the detector information in a NXdetector group that is one of the 
NXinstrument subgroups::

 >>> print entry.instrument.tree
 instrument:NXinstrument
   detector:NXdetector
    distance = float32(128)
      @units = metre
    polar_angle = float32(128)
      @units = radian
    time_of_flight = float32(8252)
      @target = /entry/instrument/detector/time_of_flight
      @units = microsecond

However, they may also be needed as plotting axes in a NXdata group::

 >>> print entry.data.tree
 data:NXdata
   data = uint32(128x8251)
     @signal = 1
     @axes = polar_angle:time_of_flight
   polar_angle = float32(128)
     @target = /entry/instrument/detector/polar_angle
     @units = radian
   time_of_flight = float32(8252)
     @target = /entry/instrument/detector/time_of_flight
     @units = microsecond
 
Links allow the same data to be used in different contexts without using more
memory or disk space.  
     
In the Python API, the user who is only interested in accessing the data does
not need to worry if the object is parent or child. The data values and NeXus 
attributes of the parent to the NXlink object can be accessed directly through
the child object. The parent object can be referenced directly, if required,
using the 'nxlink' attribute::

 >>> entry.data.time_of_flight
 NXlink('/entry/instrument/detector/time_of_flight')
 >>> entry.data.time_of_flight.nxdata
 array([   500.,    502.,    504., ...,  16998.,  17000.,  17002.], dtype=float32) 
 >>> entry.data.time_of_flight.units
 'microsecond'
 >>> entry.data.time_of_flight.nxlink
 NXfield(dtype=float32,shape=(8252,))

.. note:: The absolute path of the data with respect to the root object of the 
          NeXus tree is given by the nxpath property::

           >>> entry.data.time_of_flight.nxpath
           '/entry/data/time_of_flight'
           >>> entry.data.time_of_flight.nxlink.nxpath
           '/entry/instrument/bank1/time_of_flight'

Creating a Link
^^^^^^^^^^^^^^^
Links can be created using the target object as the argument assigned
to another group::

 >>> print root.tree
 root:NXroot
   entry:NXentry
     data:NXdata
     instrument:NXinstrument
       detector:NXdetector
         polar_angle = float64(192)
           @units = radian
 >>> root.entry.data.polar_angle=NXlink(root.entry.instrument.detector.polar_angle)

However, since the link must have the same name as the parent object, it is 
safer to create links using the makelink method, which takes the parent object 
as an argument::

 >>> root.entry.data.makelink(root.entry.instrument.detector.polar_angle)
 >>> print root.tree
 root:NXroot
   entry:NXentry
     data:NXdata
       polar_angle = float64(192)
         @target = /entry/instrument/detector/polar_angle
         @units = radian
     instrument:NXinstrument
       detector:NXdetector
         polar_angle = float64(192)
           @target = /entry/instrument/detector/polar_angle
           @units = radian

.. note:: After creating the link, both the parent and target objects have an 
          additional attribute, 'target', showing the absolute path of the 
          parent.

.. seealso:: :mod:`nexpy.api.nexus.tree.NXgroup.makelink`

External Links
^^^^^^^^^^^^^^
It is also possible to link to a NeXus field that is stored in another file.
This is accomplished using a similar syntax to internal links.

 >>> root.entry.data.data = NXlink('/counts', 'external_counts.nxs')
 
In the case of external links, the first argument is the absolute path of the 
linked object within the external file, while the second argument is the 
absolute or relative file path of the external file.

.. note:: Only fields (*i.e.*, not groups) can currently be linked. This means
          that the external file does not have to be a NeXus-compliant file, 
          just a valid HDF5 file.

.. note:: Since the objects are stored in separate files, the names of the 
          parent and link objects can be different. 

.. warning:: The file containing the external link is referenced using the 
             file path to the parent file. If the files are moved without 
             preserving their relative file paths, the link will be broken.

Plotting NeXus Data
===================
NXdata, NXmonitor, and NXlog groups all have a plot method, which automatically 
determines what should be plotted::

 >>> data.plot()

.. image:: /images/simple-plot.png
   :align: center
   :width: 80%

Note that the plot method uses the NeXus attributes within the groups to
determine automatically which NXfield is the signal, what its rank and
dimensions are, and which NXfields define the plottable axes. The same command
will work for one-dimensional or two-dimensional data. Using the GUI (see next
section), you can plot higher-dimensional data as well.

If the data is one-dimensional, it is possible to overplot more than one data
set using 'over=True'. By default, each plot has a new color, but conventional
Matplotlib keywords can be used to change markers and colors::

 >>> data.plot(log=True)
 >>> data.plot('r-')
 >>> data.plot(over=True, log=True, color='r') 

Manipulating NeXus Data
=======================
Arithmetic Operations
---------------------
NXfield
^^^^^^^
NXfields usually consist of arrays of numeric data with associated metadata, the 
NeXus attributes (the exception is when they contain character strings). This 
makes them similar to numpy arrays, and this module allows the use of NXfields 
in numerical operations as if they were numpy ndarrays::

 >>> x = NXfield((1.0,2.0,3.0,4.0))
 >>> print x+1
 [ 2.  3.  4.  5.]
 >>> print 2*x
 [ 2.  4.  6.  8.]
 >>> print x/2
 [ 0.5  1.   1.5  2. ]
 >>> print x**2
 [  1.   4.   9.  16.]
 >>> x.reshape((2,2))
 NXfield([[ 1.  2.]
 [ 3.  4.]])
 >>> y = NXfield((0.5,1.5,2.5,3.5))
 >>> x+y
 NXfield(name=x,value=[ 1.5  3.5  5.5  7.5])
 >>> x*y
 NXfield(name=x,value=[  0.5   3.    7.5  14. ])
 >>> (x+y).shape
 (4,)
 >>> (x+y).dtype
 dtype('float64')

Such operations return valid NXfield objects containing the same attributes 
as the first NXobject in the expression. The 'reshape' and 'transpose' methods 
also return NXfield objects.

NXfields can be compared to other NXfields (this is a comparison of their numpy 
arrays)::

 >>> y=NXfield(np.array((1.5,2.5,3.5)),name='y')
 >>> x == y
 True

NXfields are technically not a sub-class of the ndarray class, but they are cast
as numpy arrays when required by numpy operations, returning either another 
NXfield or, in some cases, an ndarray that can easily be converted to an 
NXfield::

 >>> x = NXfield((1.0,2.0,3.0,4.0)) 
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
 >>> np.sin(x)
 array([ 0.84147098,  0.90929743,  0.14112001, -0.7568025 ])
 >>> np.sqrt(x)
 array([ 1.        ,  1.41421356,  1.73205081,  2.        ])
 >>> print NXdata(np.sin(x), (x)).tree
 data:NXdata
   signal = [ 0.84147098  0.90929743  0.14112001 -0.7568025 ]
     @axes = x
     @signal = 1
   x = [ 1.  2.  3.  4.]

NXdata
^^^^^^
Similar operations can also be performed on whole NXdata groups. If two NXdata
groups are to be added, the rank and dimension sizes of the main signal array
must match (although the names could be different)::

 >>> y=NXfield(np.sin(x),name='y')
 >>> y
 NXfield(name=y,value=[ 0.99749499  0.59847214 -0.35078323])
 >>> a=NXdata(y,x)
 >>> print a.tree
 data:NXdata
   x = [ 1.5  2.5  3.5]
   y = [ 0.99749499  0.59847214 -0.35078323]
     @axes = x
     @signal = 1
 >>> print (a+1).tree
 data:NXdata
  x = [ 1.5  2.5  3.5]
  y = [ 1.99749499  1.59847214  0.64921677]
    @axes = x
    @signal = 1
 >>> print (2*a).tree
 data:NXdata
   x = [ 1.5  2.5  3.5]
   y = [ 1.99498997  1.19694429 -0.70156646]
     @axes = x
     @signal = 1
 >>> print (a+a).tree
 data:NXdata
   x = [ 1.5  2.5  3.5]
   y = [ 1.99498997  1.19694429 -0.70156646]
     @axes = x
     @signal = 1
 >>> print (a-a).tree
 data:NXdata
   x = [ 1.5  2.5  3.5]
   y = [ 0.  0.  0.]
     @axes = x
     @signal = 1
 >>> print (a/2).tree
 data:NXdata
   x = [ 1.5  2.5  3.5]
   y = [ 0.49874749  0.29923607 -0.17539161]
     @axes = x
     @signal = 1

If data errors are included in the NXdata group (with an additional array named 
'errors'), then the errors are propagated according to the operand::

 >>> print a.tree
 data:NXdata
   errors = [ 0.99874671  0.77360981  0.59226956]
   x = [ 1.5  2.5  3.5]
   y = [ 0.99749499  0.59847214  0.35078323]
     @axes = x
     @signal = 1
 >>> print (a+a).tree
 data:NXdata
   errors = [ 1.41244114  1.09404949  0.83759564]
   x = [ 1.5  2.5  3.5]
   y = [ 1.99498997  1.19694429  0.70156646]
     @axes = x
     @signal = 1

Some statistical operations can be performed on the NXdata group.

NXdata.sum(axis=None):
    Returns the sum of the NXdata signal data. If the axis is not specifed, the
    total is returned. Otherwise, it is summed along the specified axis. The 
    result is a new NXdata group containing a copy of all the metadata contained 
    in the original NXdata group::

     >>> x=np.linspace(0, 3., 4)
     >>> y=np.linspace(0, 2., 3)
     >>> X,Y=np.meshgrid(x,y)
     >>> a=NXdata(X*Y,(y,x))
     >>> print a.tree
     data:NXdata
       axis1 = [ 0.  1.  2.  3.]
       axis2 = [ 0.  1.  2.]
       signal = float64(3x4)
         @axes = axis1:axis2
         @signal = 1
     >>> a.nxsignal
     NXfield([[ 0.  0.  0.  0.]
      [ 0.  1.  2.  3.]
      [ 0.  2.  4.  6.]])
     >>> a.sum()
     18.0
     >>> a.sum(0).nxsignal
     NXfield([ 0.  3.  6.  9.])
     >>> a.sum(1).nxsignal
     NXfield([  0.   6.  12.])   

NXdata.moment(order=1):
    Returns an NXfield containing the first moment of the NXdata group assuming 
    the signal is one-dimensional. Currently, only the first moment has been 
    defined::
    
     >>> x=np.linspace(0, 10., 11)
     >>> y=np.exp(-(x-3)**2)
     >>> a=NXdata(y,x)
     >>> a.moment()
     3.0000002539776141


Slicing
-------
NXfield
^^^^^^^
A slice of an NXfield can be obtained using the usual python indexing syntax::

 >>> x=NXfield(np.linspace(0,2*np.pi,101))
 >>> print x[0:51]
 [ 0.          0.06283185  0.12566371 ...,  3.01592895  3.0787608 3.14159265]

If either of the indices are floats, then the limits are set by the values 
themselves (assuming the array is monotonic)::

 >>> print x[0.5:1.5]
 [ 0.50265482  0.56548668  0.62831853 ...,  1.38230077  1.44513262 1.50796447]

NXdata
^^^^^^
It is also possible to slice whole NXdata groups. In this case, the slicing
works on the multidimensional NXfield, but the full NXdata group is returned
with both the signal data and the associated axes limited by the slice
parameters. If either of the limits along any one axis is a float, the limits
are set by the values of the axis::

 >>> a=NXdata(np.sin(x),x)
 >>> a[1.5:2.5].x
 NXfield(name=x,value=[ 1.57079633  1.72787596  1.88495559 ...,  2.19911486  2.35619449])

Unless the slice reduces one of the axes to a single item, the rank of the data
remains the same. To project data along one of the axes, and so reduce the rank
by one, the data can be summed along that axis using the sum() method::

 >>> x=y=NXfield(np.linspace(0,2*np.pi,41))
 >>> X,Y=np.meshgrid(x,y)
 >>> a=NXdata(np.sin(X)*np.sin(Y), (y,x))
 >>> print a.tree
 data:NXdata
   axis1 = float64(41)
   axis2 = float64(41)
   signal = float64(41x41)
     @axes = axis1:axis2
     @signal = 1
 >>> print a.sum(0).tree
 data:NXdata
   axis2 = float64(41)
   signal = float64(41)
     @axes = axis2
     @long_name = Integral from 0.0 to 6.28318530718 
     @signal = 1

It is also possible to slice whole NXdata groups. In this case, the slicing
works on the multidimensional NXfield, but the full NXdata group is returned
with both the signal data and the associated axes limited by the slice
parameters. If either of the limits along any one axis is a float, the limits
are set by the values of the axis::

 >>> a=NXdata(np.sin(x),x)
 >>> a[1.5:2.5].x
 NXfield(name=x,value=[ 1.57079633  1.72787596  1.88495559 ...,  2.19911486  2.35619449])

Unless the slice reduces one of the axes to a single item, the rank of the data
remains the same. To project data along one of the axes, and so reduce the rank
by one, the data can be summed along that axis using the sum() method. This
employs the numpy array sum() method::

 >>> x=y=NXfield(np.linspace(0,2*np.pi,41))
 >>> X,Y=np.meshgrid(x,y)
 >>> a=NXdata(np.sin(X)*np.sin(Y), (y,x))
 >>> print a.tree
 data:NXdata
   axis1 = float64(41)
   axis2 = float64(41)
   signal = float64(41x41)
     @axes = axis1:axis2
     @signal = 1
 >>> print a.sum(0).tree
 data:NXdata
   axis2 = float64(41)
   signal = float64(41)
     @axes = axis2
     @long_name = Integral from 0.0 to 6.28318530718 
     @signal = 1

NXdata.project(axes, limits):
    The project() method projects the data along a specified 1D axis or 2D axes 
    summing over the limits, which are specified as a list of tuples for each 
    dimension. If the axis is not to be limited, then specify the limit as 
    *None*. The data should be at least two-dimensional and the values are 
    assumed to be floating point. 

    >>> x=np.linspace(0, 3., 4)
    >>> y=np.linspace(0, 2., 3)
    >>> X,Y=np.meshgrid(x,y)
    >>> a=NXdata(X*Y,(y,x))
    >>> print a.tree
    data:NXdata
      axis1 = [ 0.  1.  2.]
      axis2 = [ 0.  1.  2.  3.]
      signal = float64(3x4)
        @axes = axis1:axis2
        @signal = 1
    >>> print a.signal
    [[ 0.  0.  0.  0.]
     [ 0.  1.  2.  3.]
     [ 0.  2.  4.  6.]]
    >>> print a.project([0],[(None,None),(0.5,2.5)]).tree
    data:NXdata
      axis1 = [ 0.  1.  2.]
      axis2 = 1.5
        @maximum = 2.0
        @minimum = 1.0
      signal = [ 0.  3.  6.]
        @axes = axis1
        @signal = 1

    The :doc:`pythongui` provides a menu-based approach to simplify the plotting 
    of data projections.

Saving NeXus Data
=================
Every NeXus object, whether it is a group or a field, has a save() method as 
illustrated in `Creating NeXus Data`_.::

 >>> root.save(filename='example.nxs')

NXroot Groups
-------------
If the NeXus object is a NXroot group, the save() method saves the whole NeXus 
tree. The filename can only be omitted if the tree is being saved to a file that 
was loaded with read/write access. In this case, the format argument is ignored.
If the tree was loaded with readonly access, any modifications must be saved to
a new file specified by the filename argument.

Other Objects
-------------
If the object is not a NXroot group, a new file will be created containing the
selected object and its children. A filename *must* be specified. Saving 
non-NXroot data allows parts of a NeXus tree to be saved for later use, *e.g.*, 
to store an NXsample group that will be added to other files. The saved NeXus 
object is wrapped in an NXroot group and an NXentry group (with name 'entry'), 
if necessary, in order to produce a valid NeXus file.
     