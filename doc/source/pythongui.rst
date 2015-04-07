*******************************
Python Graphical User Interface
*******************************
A PyQT GUI has been created to make it easier to keep track of the loaded NeXus 
files and the results of any subsequent analysis. It is invoked from the command 
line by::

 > nexpy

.. note:: This assumes that the Python 'bin' directory is in your standard shell
          path.

.. image:: /images/nexpy-gui.png
   :align: center
   :width: 90%

The illustration shows the main features of the GUI:

**1) Tree Pane**
    This contains the tree structure of NeXus files opened in the File menu, 
    non-NeXus files that have been imported and converted into the NeXus format
    using one of the NeXus readers, and NXroot, NXentry, or NXdata groups added 
    from the shell. Various actions on the data can be performed by
    right-clicking a tree item, include plotting, renaming, fitting and 
    deleting the data.
    
**2) Plot Pane**
    This contains plots produced by (a) the Data\:Plot Data menu item, which 
    operates on the NeXus data selected in the tree, (b) right-clicking on NeXus 
    data in the tree, or (c) using NeXus data Plot methods from the shell. If an 
    NXdata, NXmonitor, or NXlog group is plotted, the rank, dimensions, and 
    plotting axes are determined automatically. If the rank of the data is 
    greater than two, a two-dimensional slice is extracted from the data. The 
    GUI allows the selection of alternative slices using one of the axis panels
    (see below). If an NXfield is selected, the axes can be chosen from other 
    NXfields in the same group. It is possible to open other plot windows and 
    switch between them using the Window menu or keyboard shortcuts (see below).

**3) Shell Pane**
    This is an iPython shell, with NeXpy already imported (as * so no prefixes 
    are necessary), along with Numpy (as np) and Pylab (as plt). Any assignments 
    to items in the tree pane are automatically reflected in the tree pane, and 
    new NXroot or NXentry objects can be added to the tree from the 
    iPython shell. NeXus data plots commands from the shell will appear in the 
    plot pane, and Matplotlib commands can be used to modify the plot 
    characteristics. The shell has enhanced features such as autocompletion of
    NeXus attributes and tooltips containing module docstrings when you open the 
    module parentheses.
    
**4) Axis Panels**
    The tabbed panels below the plot can be used to modify the plots. The 
    number of panels depends on the rank of the original data. The 'signal',
    'x' and 'y' panels have text boxes and sliders for adjusting the plotting
    limits. For rank two or more, a projection panel allows the plotting of 
    projections along different directions, using the current axis limits. For 
    ranks greater than two, a 'z' panel allows the other dimensions to be 
    varied. Finally, the 'options' panel provides access to the standard 
    Matplotlib tools for modifying the plots.

**5) Status Bar**
    The values and attributes of the currently selected item in the tree are
    displayed in the status bar.

**6) Tooltips**
    The NeXus tree structure of an item in the tree pane will be displayed as
    a tooltip when the cursor hovers over it.

NeXpy Menu Bar
--------------
File Menu
^^^^^^^^^
**New...**
    Creates a new workspace in the tree.

**Open**
    Opens a new NeXus file as read-only. It is possible unlock the file to 
    allow modifications to the file (see below).

    .. note:: It is possible to open a file in directly read/write mode using 
              the keyboard shortcut Alt-Shift-O (Cmd-Shift-O on a Mac). Note 
              that any changes to the file tree, using either the shell or GUI 
              commands, will be automatically updated in the file.

**Save as...**
    Saves the selected tree item to a new NeXus file. If the selected item is
    not a NXroot group, it will be wrapped in one to form a valid NeXus file.

    .. warning:: Saving a NeXus object embedded within a tree is not equivalent 
                 to saving the whole tree. Only the object and its children will 
                 be saved to a new file. 

**Duplicate...**
    Makes a copy of the NeXus file or tree, leaving the original untouched. 
    If any field in the original tree is too large to be stored in memory, its
    data is stored in an HDF5 memory-mapped file until the tree is saved to a 
    file. 

**Remove**
    Removes the root item from the tree.

    .. warning:: This will also remove the item with the same name from the 
                 shell. However, if it had previously been assigned to another
                 variable with a different name, that variable will not be 
                 deleted. 

**Lock file**
    Changes the file access mode to read-only. This will prevent further changes
    to the tree using either the GUI or the shell. Locked files are displayed
    with a padlock icon. 

**Unlock file**
    Changes the file access mode to read/write. If the root tree item has been
    saved to a file, any subsequent changes will automatically update the file,
    including deleting items. 

    .. warning:: Any changes to an unlocked file will be immediate and 
                 irreversible. Make sure you have a backup if your file contains
                 critical data.

**Import**
    Imports data from other formats. Some importers are provided with the NeXpy
    distribution, but others will be loaded from the user's ~/.nexpy/readers 
    directory.
 
    .. seealso:: `Importing NeXus Data`_

**Print Shell**
    Prints the contents of the iPython shell.

Data Menu
^^^^^^^^^
**Plot Data**
    Plots the selected tree item in the plotting pane. If the selected item is
    not a valid NXdata, NXmonitor, or NXlog group, a plot dialog allows the 
    user to specify axes with compatible dimensions to plot the data against.

**Overplot Data**
    Overplots the selected tree item in the plotting pane. This only works on 
    one-dimensional data.

    .. note:: The new plot is overlaid on the original plot using the same axis
              limits. If some of the new data lies outside the original plotting 
              limits, the slider limits are increased to cover the expanded 
              range. 

**Plot RGB(A) Image**
    Plots the selected tree item as an RGB(A) image. In such images, the
    fastest varying dimension, which should be of size 3 or 4, contains the 
    RGB(A) values for each pixel. By convention, the first pixel is in the 
    upper-left corner, rather than the lower-left. 

**Add Data**
    Adds data to the selected tree item. If the selected item is a group, the
    added data can be a group or field. If the selected item is a field, the 
    added data must be a field attribute. 
    
    When adding a field, the Add Data dialog allows the name, value and data 
    type to be specified. A dropdown menu can be used to enter field names 
    that are defined by the NeXus standard, but the user is free to enter 
    alternative names. The value field can be any valid Python expression, 
    including numpy functions such as np.linspace().
    
    When adding a group, the Add Data dialog allows the name and class of the
    group to be specified. A dropdown menu display can be used to enter one of 
    the defined NeXus classes. Those above the dashed line are valid in the 
    context of the selected tree item, but any of the other classes can also be 
    selected.

    .. note:: If you click on the dropdown menus and hover over any item, a 
              tooltip gives a description of its use.

**Initialize Data**
    Adds a NeXus field to the selected tree item with the specified shape and
    data type, but without a predefined value. This is useful when creating 
    large arrays that have to be entered as slabs. The shape box must contain
    a single integer, for a one-dimensional array, or a tuple (or list) of
    integers, for a multidimensional array. As with the 'Add Data' dialog, 
    dropdown menus show the field names defined by the NeXus standard.
    
**Rename Data**
    Renames the selected tree item. If the item is a group, its class can also
    be changed. Dropdown menus provide a list of valid group classes or field
    names defined by the NeXus standard.

    .. warning:: This action will be automatically saved to the NeXus file if
                 it has been opened as read/write. 

**Copy Data**
    Copies the selected tree item to a copy buffer. 

**Paste Data**
    Pastes the copy buffer to the selected group. If the selected group is in a 
    file open with read/write access, all fields in the copy buffer are copied 
    to the file. If the selected group is not currently stored in a file and 
    any field in the copy buffer is too large to be stored in memory, its data 
    is copied to an HDF5 memory-mapped file using the h5py copy module.
    
**Paste As Link**
    Pastes a link to the copied node in the selected group. If the copied
    node and the selected group have different roots, the copied node is added
    to the group as an external link.
    
    .. note:: External links can only be modified through the parent file, which
              can be opened using the 'Show Link' menu item (see below).

    .. warning:: The file containing the external link is referenced using the 
                 file path to the parent file. If the files are moved without 
                 preserving their relative file paths, the link will be broken.

**Delete Data**
    Deletes the selected tree item.

    .. note:: If the item was assigned to another variable in the shell, that
              variable will not be deleted.

    .. warning:: If the NeXus tree was loaded from a file with read/write 
                 access, the data will be immediately deleted from the file. 
                 This action is irreversible, so ensure you have a backup.

**Show Link**
    Selects the field or group to which the selected item is linked, if it is
    an NXlink object, *i.e.*, shown with a link icon. If the link is external,
    the linked file is automatically opened and the linked object is selected.
 
**Set Signal**
    Sets the plottable signal either to the selected field or to any field 
    within the selected group. A dialog box allows the user to specify axes with 
    compatible dimensions to plot the data against.

    .. note:: The use of the 'Add Data' and 'Set Signal' menu items allows, in 
              principle, an entire NeXus data tree to be constructed using menu 
              calls. 

**Fit Data**
    Fits the selected tree item. This assumes that the selected item is a valid 
    NXdata group. The menu item triggers a dialog box, which allows functions
    to be chosen and parameters to be initialized before calling a 
    non-linear least-squares fitting module. 

    .. seealso:: See `Fitting NeXus Data`_.

Window Menu
^^^^^^^^^^^
**Show Log File**
    Opens a text window displaying the NeXpy log file(s). These files, which are
    stored in ``~/.nexpy/nexpy.log``, ``~/.nexpy/nexpy.log.1``, *etc*., 
    currently record operations on the tree items, as well as errors in the
    IPython shell.

    .. note:: If `ansi2html <https://github.com/ralphbean/ansi2html>`_ is 
              installed, tracebacks will be rendered in color. The log files
              contain ANSI markup, which is rendered in the terminal using 
              ``less -r``.

**Change Plot Limits**
    This gives a dialog box that allows the axis limits of the currently active
    plot to be changed. This is useful if you want to expand the limits beyond 
    the data values or if you want to narrow the limits to improve the 
    sensitivity of the sliders.

**Reset Plot Limits**
    This restores the limits to the original values. 

    .. note:: Right-clicking on the plot will also restore the original axis 
              limits.

**Show Projection Panel**
    Show the projection panel for the currently active plotting window. This is
    equivalent to clicking on 'Show Panel' in the projection tab (see below).

**New Plot Window**
    Opens a new NeXpy plotting window, consisting of a Matplotlib plot pane and 
    its associated axis panels. NeXpy plot commands will be directed to the 
    currently active window. Clicking on the plot pane makes it active. All 
    open windows are listed in the Window menu, along with their labels ('Main',
    'Figure 1', 'Figure 2', *etc*.). These are used to switch the focus for
    subsequent plots.

**Main, Figure 1, Figure 2...**
    These menu items set the selected plotting window to be active. As
    new windows are created, they are dynamically added to this list. 

Script Menu
^^^^^^^^^^^
**New Script**
    Opens a new script in an editable text window with syntax coloring. The 
    Python code can be run within the IPython console at any time using the 
    console namespace. That means that all the items on the NeXpy tree are also 
    accessible without further imports. 
    
    The scripts can be saved for future use from within NeXpy or from the 
    terminal command line. They can therefore be formatted as a Python 
    standalone script to be either run as ``python script.py`` or run in the 
    console (similar to the IPython 'run magic', *i.e.*, ``%run -i script.py``). 
    Script arguments can be entered in a separate text window at the bottom of 
    the window and accessed within the script in the 'sys.argv' list.

    .. note:: Script arguments are just text strings, so if the argument is a
              node on the tree, it must be referenced as a tree dictionary item,
              *e.g.*, ``nxtree[sys.argv[1]]``

    Scripts are saved, by default, in ``~/.nexpy/scripts``, and are 
    automatically added to the bottom of the Script Menu.

**Open Script**
    Opens an existing Python script file in an editable text window.

.. note:: The currently selected node in the NeXpy tree can be referenced in 
          the script as ``treeview.node``.

Other Menus
^^^^^^^^^^^
The Edit, View, Magic, and Help Menus currently consist of menu items 
provided by the iPython shell for their Qt Console. All the operations act on 
the shell text.

Adding NeXus Data to the Tree
-----------------------------
NXroot groups that are displayed in the tree pane are all children of a group
of class NXtree, known as 'tree'. If you create a NeXus group dynamically in the 
iPython shell, it can be added to the tree pane using the tree's add method::

 >>> a=NXroot()
 >>> a.entry = NXentry()
 >>> nxtree.add(a)

If the group is an NXroot group, it will have the name used in the shell.
If the group is not an NXroot group, the data will be wrapped automatically in 
an NXroot group and given a default name that doesn't conflict with existing 
tree nodes, *e.g.*, w4. 

.. note:: The NXroot class is still considered to be the root of the NeXus tree
          in shell commands. The NXtree group is only used by the GUI and cannot 
          be saved to a file.

.. warning:: In python, an object may be accessible within the shell with more
             than one name. NeXpy searches the shell dictionary for an object
             with the same ID as the added NeXus object and so may choose a 
             different name. The object in the tree can be renamed.

Plotting NeXus Data
-------------------
NXdata, NXmonitor, and NXlog data can be plotted by selecting a group on the 
tree and choosing "Plot Data" from the Data menu or by double-clicking the item 
on the tree (or right-clicking for over-plots). Below the plot pane, a series of 
tabs allow manipulation of the plot limits and parameters.

**Signal Tab**

    .. image:: /images/signal-tab.png
       :align: center
       :width: 75%

    The signal tab contains text boxes and sliders to adjust the intensity 
    limits, a checkbox to plot the intensity on a log scale, and a dropdown menu
    to select a color palette.
    
    .. note:: For a one-dimensional plot, there is no signal tab. The intensity
              is adjusted using the y-tab. There is also no signal tab for an 
              RGB(A) image, since the colors are defined by the RGB(A) values.

**X/Y Tab**

    .. image:: /images/x-tab.png
       :align: center
       :width: 75%

    The x and y-tabs contains text boxes and sliders to adjust the axis limits 
    and a dropdown menu to select the axis to be plotted along x and y, 
    respectively. The names correspond to the axis names in the NXdata group. 
    A checkbox allows the direction of the axes to be flipped.
    
    .. warning:: Flipping the axis directions does not flip the direction of the 
                 sliders.

**Z Tab**

    .. image:: /images/z-tab.png
       :align: center
       :width: 75%

    If the data rank is three or more, the 2D plot *vs* x and y is a projection 
    along the remaining axes. The z-tab sets the limits for those projections.
    It contains a dropdown menu for selecting the axis to be summed over and
    two text boxes for selecting the projection limits. When the data are first
    plotted, only the top slice if plotted, *i.e.*, all the z-axis limits are 
    set to their minimum value.
    
    When 'Lock' is checked, the difference between the limits of the selected 
    z-axis is fixed. This allows successive images along the z-axis to be 
    plotted by clicking the text-box arrows in increments of the difference 
    between the two limits. If you use the text-box arrows or the terminal arrow 
    keys to change the z-limits when they are locked together, the new plot is 
    updated automatically. Otherwise, the data is only replotted when you force
    a replot using the toolbar (see below).

    .. note:: Make sure that the value of both limit boxes is entered, *e.g.*, 
              by pressing return after editing their values, before clicking on 
              the 'lock' checkbox. 
        
    When stepping through the z-values, the 'Autoscale' checkbox determines 
    whether the plot automatically scales the signal to the maximum intensity of
    the slice or is set to the current signal limits.     
    
    .. note:: When 'Autoscale' is checked, it is not possible to adjust the 
              limits in the Signal Tab.

    .. image:: /images/z-toolbar.png
       :align: right
    
    The toolbar on the right provides further controls for replotting data as 
    a function of z. The first button on the left forces a replot, *e.g.*, when 
    you have changed z-axis limits or turned on auto-scaling. The other buttons 
    are for stepping through the z-values automatically, with 'back', 'pause', 
    and 'forward' controls. The default speed is one frame per second, but after 
    the first click on the play button, subsequent clicks will reduce the frame 
    interval by a factor two.     

**Projection Tab**

    .. image:: /images/projection-tab.png
       :align: center
       :width: 75%

    The projection tab allows the data to be projected along one or two
    dimensions. The limits are set by the x, y, and z-tabs, while the projection
    axes are selected using the dropdown boxes. For a one-dimensional 
    projection, select 'None' from the y box. The projections may be plotted in
    a separate window, using the 'Plot' button or saved to a scratch NXdata 
    group within 'w0' on the tree. A checkbox allows the overplotting of 
    one-dimensional projections.
    
    .. image:: /images/projection.png
       :align: center
       :width: 75%

    The projection tab also contains a button to open a separate projection 
    panel that can be used instead of the tabbed interface. This interface is
    more convenient when making a systematic exploration of different 
    projections limits and provides pixel accuracy in computing projections.
    The x and y limits of the plot are displayed as a dashed rectangle.  

.. image:: /images/projection-panel.png
   :align: center
   :width: 90%

.. note:: The projection panel can also be used to mask and unmask data within 
          the dashed rectangle. See :doc:`pythonshell` for descriptions of
          masked arrays.
   
**Options Tab**

    .. image:: /images/options-tab.png
       :align: center
       :width: 90%

    The options tab provides the standard Matplotlib toolbar. You can view with the addition
    of one extra button. From left to right, the buttons are:
    
    * **Home** - restores all plotting limits to their original values. 
    * **Arrows** - cycles through the limits of previous plots.
    * **Pan** - enables panning mode (disabling zoom mode).
    * **Zoom** - enables zoom mode (disabling pan mode).
    * **Aspect** - toggles between setting the aspect ratio automatically 
      to fill the available space or setting the x and y scales to be equal. 
      This is only valid if the units of the x and y axes are identical.
    * **Subplot** - configures the spacing around the plot. 
    * **Save** - saves plot to PNG file.
    * **Add** - adds plotted data to the tree pane as an NXdata group within the
      scratch workspace 'w0'.
    * **Edit** - allows marker and line formatting to be modified.

    On the far right of the toolbar, the data and axis values are dynamically 
    updated to the values under the current mouse location.

    .. seealso:: See the `Matplotlib documentation  
                 <http://matplotlib.org/users/navigation_toolbar.html>`_ for
                 more detailed descriptions of the standard toolbar, including 
                 keyboard shortcuts. The 'Aspect' and 'Add' buttons are unique
                 to NeXpy.

    .. note:: The aspect ratio of a plot can also be set from the IPython shell.
              See below.

**Command Line Options**

    It is possible to modify some of the plotting features from the IPython 
    shell. The current plotting pane, the default Matplotlib axis instance, and
    the current image are exposed as ``plotview``, ``plotview.ax``, and
    ``plotview.image``, respectively. 
    
    .. note:: Before making any changes, make sure that you have selected the
              right plotting pane, either by selecting it in the Window menu or
              using one of the keyboard shortcuts, which are displayed in the 
              menu, *e.g.*, <Ctrl>+2 (⌘+2 on a Mac) to select Figure 2.

* Set Aspect Ratio::

    >>> plotview.aspect = <aspect>

  ``<aspect>`` can be any of the values allowed by the `Matplotlib set_aspect 
  <http://matplotlib.org/api/axes_api.html#matplotlib.axes.Axes.set_aspect>`_
  function, *i.e.*, 'auto', 'equal', or the numerical value of the 
  ratio between the height and the width (if the units are identical). The 
  'Aspect' button (see above) toggles between 'auto' and 'equal'.

* Set Offsets::

    >>> plotview.offsets = <True|False>

  If the range of an axis is much smaller than the absolute values, the axis
  labels can overlap. Setting this option will determine whether Matplotlib 
  converts the axis labels to differences from a fixed offset value or not. 
  The default is ``False``.

* Select Color Map::

    >>> plotview.cmap = <cmap>

  This allows the color map of the currently displayed image to be changed.
  This can be useful if the map is not available in the Signal Tab. See the
  `Matplotlib documentation 
  <http://matplotlib.org/api/pyplot_api.html#matplotlib.pyplot.set_cmap>`_
  for more details.    

* Draw Shapes::

    >>> plotview.vline(<x>, <ymin>, <ymax>)
    >>> plotview.hline(<y>, <xmin>, <xmax>)
    >>> plotview.vlines(<x-array>, <ymin>, <ymax>)
    >>> plotview.hlines(<y-array>, <xmin>, <xmax>)
    >>> plotview.crosshairs(<x>, <y>)
    >>> plotview.rectangle(<x>, <y>, <dx>, <dy>)
    >>> plotview.circle(<x>, <y>, <radius>)
    >>> plotview.ellipse(<x>, <y>, <dx>, <dy>)

  These functions draw graphical primitives on the plot using the axis 
  coordinates. In the case of the lines, the complete range of the plot will
  be used if the minimum and maximum values are omitted. The rectangle 
  coordinates represent the lower left-hand corner but the circle and ellipse
  coordinates represent the shape center.

  .. note:: Since the arguments are in the units of the axes, the circle will
            only be truly circular if the x and y units are the same, and the
            aspect ratio of the plot is equal.

  All of the functions will accept additional keyword arguments used in 
  drawing Matplotlib shapes, *e.g.*, to change the edge and fill colors, line 
  properties, *etc*. See the `Matplotlib documentation 
  <http://matplotlib.org/api/patches_api.html#matplotlib.patches.Polygon>`_
  for more details.

Fitting NeXus Data
------------------
It is possible to fit one-dimensional data using the non-linear least-squares 
fitting package, `lmfit-py <http://newville.github.io/lmfit-py>`_, by selecting 
a group on the tree and choosing "Fit Data" from the Data menu or by 
right-clicking on the group. This opens a dialog window that allows multiple 
functions to be combined, with the option of fixing or limiting parameters. 

.. image:: /images/nexpy-fits.png
   :align: center
   :width: 90%

The fit can be plotted, along with the constituent functions, in the main
plotting window and the fitting parameters displayed in a message window. 

The original data, the fitted data, constituent functions, and the parameters
can all be saved to an NXentry group in the Tree Pane for subsequent plotting, 
refitting, or saving to a NeXus file. The group is an NXentry group, with name 
'f1', 'f2', etc., stored in the default scratch NXroot group, w0. If you choose 
to fit this entry again, it will load the functions and parameters from the 
saved fit.

Defining a function
^^^^^^^^^^^^^^^^^^^
User-defined functions can be added to their private functions directory in 
``~/.nexpy/functions``. The file must define the name of the function, a list of 
parameter names, and provide two modules to return the function values and 
starting parameters, respectively. 

As an example, here is the complete Gaussian function::

 import numpy as np

 function_name = 'Gaussian'
 parameters = ['Integral', 'Sigma', 'Center']

 factor = np.sqrt(2*np.pi)

 def values(x, p):
     integral, sigma, center = p
     return integral * np.exp(-(x-center)**2/(2*sigma**2)) / (sigma * factor)

 def guess(x, y):
     center = (x*y).sum()/y.sum()
     sigma = np.sqrt(abs(((x-center)**2*y).sum()/y.sum()))
     integral = y.max() * sigma * factor
     return integral, sigma, center

NeXpy uses the function's 'guess' module to produce starting parameters
automatically when the function is loaded. When each function is added to the 
model, the estimated y-values produced by that function will be subtracted from 
the data before the next function estimate. It is useful therefore to choose the
order of adding functions carefully. For example, if a peak is sitting on a 
sloping background, the background function should be loaded first since it is
estimated from the first and last data points. This guess will be subtracted
before estimating the peak parameters. Obviously, the more functions that are 
added, the less reliable the guesses will be. Starting parameters will have to 
be entered manually before the fit in those cases.

.. note:: If it is not possible to estimate starting parameters, just return
          values that do not trigger an exception. 

Importing NeXus Data
--------------------
NeXpy can import data stored in a number of other formats, including SPEC files,
TIFF images, and text files, using the File:Import menus. If a file format is 
not currently supported, the user can write their own. The following is an 
example of a module that reads the original format and returns NeXus data::

 def get_data(filename):
     from libtiff import TIFF
     im = TIFF.open(filename)
     z = im.read_image()
     y = range(z.shape[0])     
     x = range(z.shape[1])
     return NXentry(NXdata(z,(y,x)))

This could be run in the shell pane and then added to the tree using::

 >>> nxtree.add(get_data('image.tif'))

Existing Readers
^^^^^^^^^^^^^^^^
NeXpy is currently distributed with readers for the following format:

**TIFF Images**

This reader will import most TIFF images, including those with floating
point pixels.

**CBF Files**

This reader will read files stored in the `Crystallographic Binary Format 
<http://www.iucr.org/resources/cif/software/cbflib>`_, using the PyCBF library. 
Header information is stored in a NXnote.

**Image Stack**

This reader will read a stack of images, currently either TIFF or CBF, into a
three-dimensional NXdata group. The image stack must be stored in separate files 
in a single directory, that are grouped with a common prefix followed by an 
integer defining the stack sequence.

**Text Files**

This reader will read ASCII data stored in two or three columns, containing the
x and y values, and, optionally, errors. One or more header lines can be skipped.
A more flexible text importer, allowing the selection of data from multiple 
columns, is under development.

**SPEC Files**

This reader will read multiple SPEC scans from a single SPEC log file, creating
a separate NXentry for each scan. All the columns in each scan are read into 
the NXdata group, with the default signal defined by the last column. Mesh scans
are converted to multi-dimensional data, with axes defined by the scan command.
It is possible to plot different columns once the scans are imported.

**SPE/NXSPE Files**

This will read both the ASCII and binary (HDF5) versions of the neutron 
time-of-flight SPE intermediate format into standard-conforming NeXus files. 
The data is stored as S(phi,E), but, if the incident energy and (Q,E) bins are 
also defined, the data will will also be converted into S(Q,E). The current
version does not read the ASCII PHX files used to define instrumental 
parameters, but there are plans to add that in the future.

Defining a Reader
^^^^^^^^^^^^^^^^^
With a little knowledge of PyQt, it is possible to add a reader to the 
File:Import menu using the existing samples as a guide in the nexpy.readers
directory. User-defined import dialogs can be added to their private readers 
directory in ``~/.nexpy/readers``.

Here is an example of an import dialog::

 """
 Module to read in a TIFF file and convert it to NeXus.

 Each importer needs to layout the GUI buttons necessary for defining the 
 imported file and its attributes and a single module, get_data, which returns 
 an NXroot or NXentry object. This will be added to the NeXpy tree.

 Two GUI elements are provided for convenience:

     ImportDialog.filebox: Contains a "Choose File" button and a text box. Both 
                           can be used to set the path to the imported file. 
                           This can be retrieved as a string using 
                           self.get_filename().
     ImportDialog.buttonbox: Contains a "Cancel" and "OK" button to close the 
                             dialog. This should be placed at the bottom of all 
                             import dialogs.
 """

 from PySide import QtCore, QtGui

 import numpy as np
 from nexpy.api.nexus import *
 from nexpy.gui.importdialog import BaseImportDialog

 filetype = "TIFF Image" #Defines the Import Menu label

 class ImportDialog(BaseImportDialog):
     """Dialog to import a TIFF image"""
 
     def __init__(self, parent=None):

         super(ImportDialog, self).__init__(parent)
        
         layout = QtGui.QVBoxLayout()
         layout.addLayout(self.filebox())
         layout.addWidget(self.buttonbox())
         self.setLayout(layout)
  
         self.setWindowTitle("Import "+str(filetype))
 
     def get_data(self):
         from libtiff import TIFF
         im = TIFF.open(self.get_filename())
         z = NXfield(im.read_image(), name='z')
         y = NXfield(range(z.shape[0]), name='y')      
         x = NXfield(range(z.shape[1]), name='x')
         return NXentry(NXdata(z,(y,x)))

.. seealso:: See :class:`nexpy.gui.importdialog.BaseImportDialog` and its parent
             :class:`nexpy.gui.importdialog.BaseDialog` for other
             pre-defined methods.

NeXpy Plugins
-------------
It is possible to customize NeXpy by adding new menus to the main menu bar 
with sub-menus that open dialog boxes for operations that are specific to a 
particular domain. These will be automatically loaded from either the 
``nexpy.plugins`` directory within the installed NeXpy distribution or from the
users' ``~/.nexpy/plugins`` directory.

The new menu should be defined as a Python package, *i.e.*, by creating a 
sub-directory within the plugins directory that contains ``__init__.py`` to 
define the menu actions.

There is an example package, ``chopper``, in the ``nexpy.examples`` directory,
to show how plugins can work. It adds a top-level menu item, ``chopper``, that
has a couple of menu items to perform data analysis on the example file, 
``chopper.nxs``, which is distributed with NeXpy.

Here is the ``__init__.py`` file::

 from PySide import QtGui
 import get_ei, convert_qe

 def plugin_menu(parent):
     menu = QtGui.QMenu('Chopper')
     menu.addAction(QtGui.QAction('Get Incident Energy', parent, 
                    triggered=get_ei.show_dialog))
     menu.addAction(QtGui.QAction('Convert to Q-E', parent, 
                    triggered=convert_qe.show_dialog))
     return menu

The QAction calls define the menu text and the function that gets called when it
is selected. In the example, they are contained within the package as two files,
``get_ei.py`` and ``convert_qe.py``, but they could also be in a separately 
installed package in the Python path.

These files should open a dialog box and perform the required operations, after
which the results can either be saved to a new NeXus file or saved as 
modifications to an existing tree item. 

For example, ``get_ei.py`` reads the monitor spectra contained within the 
currently selected node on the tree, which should have been previously loaded. 
It then calculates the difference between the peak positions of the two spectra,
calculates the incident energy, which is updated in both the dialog box and, if
the ``Save`` button is pressed, in the loaded NeXus tree, ready for subsequent
analysis.

Obviously, some knowledge of PySide is necessary, although the example below 
shows all the essential elements required in most cases: a grid to define a set 
of parameters, functions to read those parameters from the PySide text boxes
(here, they are decorated with ``@property``, which means that the function can
be called without an argument), a couple of buttons to activate different parts 
of the analysis, and finally the functions themselves. 

.. seealso:: See :class:`nexpy.gui.importdialog.BaseDialog` for a list of
             pre-defined dialog methods if the dialog uses it as the parent
             class. In the example below, BaseDialog defines the function, 
             ``get_node``, which returns the node currently selected in the
             tree.

Here is the code::

 from PySide import QtGui
 import numpy as np
 from nexpy.gui.datadialogs import BaseDialog
 from nexpy.gui.mainwindow import report_error
 from nexpy.api.nexus import NeXusError


 def show_dialog(parent=None):
    try:
        dialog = EnergyDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Getting Incident Energy", error)
        

 class EnergyDialog(BaseDialog):

    def __init__(self, parent=None):
        super(EnergyDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        if self.root.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.m1_box = QtGui.QLineEdit()
        self.m2_box = QtGui.QLineEdit()
        self.ei_box = QtGui.QLineEdit()
        self.mod_box = QtGui.QLineEdit()
        grid.addWidget(QtGui.QLabel('Monitor 1 Distance:'), 0, 0)
        grid.addWidget(QtGui.QLabel('Monitor 2 Distance:'), 1, 0)
        grid.addWidget(QtGui.QLabel('Incident Energy:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Moderator Distance:'), 3, 0)
        grid.addWidget(self.m1_box, 0, 1)
        grid.addWidget(self.m2_box, 1, 1)
        grid.addWidget(self.ei_box, 2, 1)
        grid.addWidget(self.mod_box, 3, 1)
        layout.addLayout(grid)
        get_button = QtGui.QPushButton('Get Ei')
        get_button.clicked.connect(self.get_ei)
        layout.addWidget(get_button)
        layout.addWidget(self.buttonbox(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Get Incident Energy')

        self.m1 = self.root['entry/monitor1']
        self.m2 = self.root['entry/monitor2'] 
        self.m1_box.setText(str(self.read_parameter(self.root,
                            'entry/monitor1/distance')))
        self.m2_box.setText(str(self.read_parameter(self.root,
                            'entry/monitor2/distance')))
        self.ei_box.setText(str(self.read_parameter(self.root,
                            'entry/instrument/monochromator/energy')))
        self.mod_box.setText(str(self.read_parameter(self.root,
                             'entry/instrument/source/distance')))

    @property
    def m1_distance(self):
        return np.float32(self.m1_box.text()) - self.moderator_distance

    @property
    def m2_distance(self):
        return np.float32(self.m2_box.text()) - self.moderator_distance

    @property
    def Ei(self):
        return np.float32(self.ei_box.text())

    @property
    def moderator_distance(self):
        return np.float32(self.mod_box.text())

    def get_ei(self):
        t = 2286.26 * self.m1_distance / np.sqrt(self.Ei)
        m1_time = self.m1[t-200.0:t+200.0].moment()
        t = 2286.26 * self.m2_distance / np.sqrt(self.Ei)
        m2_time = self.m2[t-200.0:t+200.0].moment()
        self.ei_box.setText(str((2286.26 * (self.m2_distance - self.m1_distance) /
                                   (m2_time - m1_time))**2))

    def accept(self):
        try:
            self.root['entry/instrument/monochromator/energy'] = self.Ei
        except NeXusError as error:
            report_error("Getting Incident Energy", error)
        super(EnergyDialog, self).accept()
 
Configuring NeXpy
-----------------
The NeXpy shell imports the following NeXus classes::

 import nexpy
 import nexpy.api.nexus as nx
 from nexpy.api.nexus import NXFile, NXgroup, NXfield, NXattr, NXlink

along with all the currently defined NeXus group classes (NXentry, NXdata, 
NXsample, *etc*). 

For convenience, the NeXpy shell also imports a number of other modules that are 
commonly used::

 import sys
 import os
 import h5py as h5
 import numpy as np
 import numpy.ma as ma
 import scipy as sp
 import matplotlib as mpl
 from matplotlib import pylab, mlab, pyplot
 plt = pyplot

If you require a different set of imports or prefer alternative abbreviations,
you can replace the default startup script with your own by placing the 
required code in ~/.nexpy/config.py.

The console can be configured using the `IPython configuration system 
<http://ipython.org/ipython-doc/stable/interactive/tutorial.html#configuration>`_.
For example, if you don't want a blank line between each input line, edit 
~/.ipython/profile_default/ipython_qtconsole_config.py and set::

 c.IPythonWidget.input_sep = '' 

