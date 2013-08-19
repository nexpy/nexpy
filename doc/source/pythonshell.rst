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
          import the data using ``from nexpy.api.nexus import \*``. Since this 
          produces a name clash with the Numpy 'load' module, 'nxload' has been
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

Creating NeXus Data
===================
It is just as easy to create new NeXus data sets from scratch using Numpy 
arrays. The following example shows the creation of a simple function, which is 
then saved to a file::
 
 >>> import numpy as np
 >>> x=y=np.linspace(0,2*np.pi,101)
 >>> X,Y=np.meshgrid(x,y)
 >>> z=np.sin(X)*np.sin(Y)
 >>> a=NXdata(z,[x,y])
 >>> a.save('function.nxs')

This file can then be loaded again::

 >>> b=nexus.load('function.nxs')
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

Note that the save() method automatically wraps any valid NeXus data in an 
NXentry group, in order to produce a standard-compliant file.

NeXus Objects
=============
NeXus data is stored as a hierarchical tree structure, much like a computer file 
system. NeXus data structures consist of groups, with base class NXgroup, which 
can contain fields, with base class NXfield, and/or other groups.

NeXus Fields
------------
NeXus data values are stored in NeXus objects of class 'NXfield'. The NXfield
class wraps standard Numpy arrays, scalars, and python strings so that
additional metadata (or attributes) and methods can be associated with them. 

There are three ways to create an NXfield.

* Direct assignment::

    >>> x = NXfield(np.linspace(0,2*np.pi,101), units='degree')

  The data value is given by the first positional argument, and may be a Python
  scalar or string, or a Numpy array. In this method, keyword arguments can be
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
  
.. note:: To avoid name clashes with NXfield methods, dictionary assignment 
          is the safest method to use in scripts.

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
  ('char', (9,))

.. note:: Numeric dtypes can be defined either as a string, *e.g.*, 'int16', 
          'float32', or using the Numpy dtypes, *e.g.*, np.int16, np.float32.

Similarly, the shape and dimension sizes of an integer or float array is 
inherited from the assigned Numpy array. It is possible to initialize an NXfield
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
of slabs using the get and put methods, respectively::

 >>> with root.NXentry[0].data.data as slab:
         Ni,Nj,Nk = slab.shape
         size = [1,1,Nk]
         for i in range(Ni):
             for j in range(Nj):
                 value = slab.get([i,j,0],size)

.. note:: NXfield values are stored in its 'nxdata' attribute. For integers and
          floats, this will be a Numpy array. If the values have not been 
          loaded, 'nxdata' is set to None.

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
 >>> X,Y=np.meshgrid(y,x)
 >>> z=np.sin(X)*np.sin(Y)
 >>> a=NXdata(z,[x,y])

The first positional argument is an NXfield or Numpy array containing the data,
while the second is a list containing the axes, again as NXfields or Numpy
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
          attribute set to 1. The signal NXfield defines the axes to be plotted 
          against as a string of NXfield names delimited here by a colon. White 
          space or commas can also be used as delimiters. 

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

Plotting NeXus Data
===================
NXdata, NXmonitor, and NXlog groups all have a plot method, which automatically 
determines what should be plotted::

 >>> data.plot()

.. image:: /images/simple-plot.png

Note that the plot method uses the NeXus attributes within the groups to
determine automatically which NXfield is the signal, what its rank and
dimensions are, and which NXfields define the plottable axes. The same command
will work for one-dimensional or two-dimensional data. Using the GUI (see next
section), you can plot higher-dimensional data as well.

If the data is one-dimensional, it is possible to overplot more than one data
set using 'over=True'. By default, each plot has a new color, but conventional
Matplotlib keywords can be used to change markers and colors::

 >>> data.plot(log=True)
 >>> data.plot(over=True, log=True, color='r') 

Manipulating NeXus Data
=======================
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
by one, the data can be summed along that axis using the nxsum() method. This
employs the Numpy array sum() method::

 >>> x=y=NXfield(np.linspace(0,2*np.pi,41))
 >>> X,Y=np.meshgrid(x,y)
 >>> a=NXdata(np.sin(X)*np.sin(Y), (x,y))
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
by one, the data can be summed along that axis using the nxsum() method. This
employs the Numpy array sum() method::

 >>> x=y=NXfield(np.linspace(0,2*np.pi,41))
 >>> X,Y=np.meshgrid(x,y)
 >>> a=NXdata(np.sin(X)*np.sin(Y), (x,y))
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

Arithmetic Operations
---------------------
NXfield
^^^^^^^
Arithmetic operations can be applied to NXfield objects in much the same way as
scalars or Numpy arrays that they contain. This includes addition, subtraction,
multiplication and division, either with other NXfield objects or to scalar
numbers or Numpy arrays::

 >>> x=NXfield(array((1.5,2.5,3.5),name='x')
 >>> x
 NXfield(name=x,value=[ 1.5  2.5  3.5])
 >>> x+1
 NXfield(name=x,value=[ 2.5  3.5  4.5])
 >>> 2*x
 NXfield(name=x,value=[ 3.  5.  7.])
 >>> x+x
 NXfield(name=x,value=[ 3.  5.  7.])
 >>> x-x
 NXfield(name=x,value=[ 0.  0.  0.])
 >>> x/x
 NXfield(name=x,value=[ 1.  1.  1.])

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
