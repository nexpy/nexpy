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
    from the shell. By default, these are given a standard name of 'w1', 'w2', 
    *etc*, but they may be renamced by right-clicking on the group.
    
**2) Plot Pane**
    This contains plots produced by (a) the Data\:Plot Data menu item, which 
    operates on the NeXus data selected in the tree, (b) right-clicking on NeXus 
    data in the tree, or (c) using NeXus data Plot methods from the shell. If an 
    NXdata, NXmonitor, or NXlog group is plotted, the rank, dimensions, and 
    plotting axes are determined automatically. If the rank of the data is 
    greater than two, a two-dimensional slice is extracted from the data. The 
    GUI allows the selection of alternative slices using one of the axis panels
    (see below). If an NXfield is selected, the independent axis can be chosed 
    from other NXfields in the same group. At the moment, this only works for 
    one-dimensional NXfields. 

**3) Shell Pane**
    This is an iPython shell, with NeXpy already imported (as * so no prefixes 
    are necessary), along with Numpy (as np) and Pylab (as plt). Any assignments 
    to items in the tree pane are automatically reflected in the tree pane, and 
    new NXroot, NXentry, or NXdata objects can be added to the tree from the 
    iPython shell. The NeXus data plot methods from the shell to plot into the 
    plot pane, and Matplotlib commands can be used to modify the plot 
    characteristics. The shell has enhanced features such as autocompletion of
    NeXus attributes and tooltips of module docstrings when you open the module
    parentheses.
    
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

Adding NeXus Data to the Tree Pane
----------------------------------
NXroot groups that are displayed in the tree pane are all children of a group
of class NXtree, known as 'tree'. If you create a NeXus group dynamically in the 
iPython shell, it can be added to the tree pane using the tree's add method::

 >>> a=NXroot()
 >>> a.entry = NXentry()
 >>> tree.add(a)

If the group is not an NXroot group, the data will be wrapped automatically in 
an NXroot group and given a default name that doesn't conflict with existing 
tree nodes, *e.g.*, w4.

.. note:: The NXroot class is still considered to be the root of the NeXus tree.
          The NXtree group is only used by the GUI and cannot be saved to a 
          file.

Plotting NeXus Data
-------------------
NXdata, NXmonitor, and NXlog data can be plotted by selecting a group on the 
tree and choosing "Plot Data" from the Data menu or by right-clicking on the 
group. Below the plot pane, a series of tabs allow manipulation of the plot
limits and parameters.

**Signal Tab**

    .. image:: /images/signal-tab.png
       :align: center
       :width: 75%

    The signal tab contains text boxes and sliders to adjust the intensity 
    limits, a checkbox to plot the intensity on a log scale, and a dropdown menu
    to select a color palette.
    
    .. note:: For a one-dimensional plot, there is no signal tab. The intensity
              is adjusted using the y-tab.

**X/Y Tab**

    .. image:: /images/x-tab.png
       :align: center
       :width: 75%

    The x and y-tabs contains text boxes and sliders to adjust the axis limits 
    and a dropdown menu to select the axis to be plotted along x and y, 
    respectively. The names correspond to the axis names in the NXdata group.
    
    .. note:: In the above image, the name of the axis happened to be x, but
              this would not generally be true.

**Z Tab**

    .. image:: /images/z-tab.png
       :align: center
       :width: 75%

    If the data rank is three or more, the 2D plot *vs* x and y is a projection 
    along the remaining axes. The z-tab sets the limits for those projections.
    It contains a dropdown menu for selecting the axis to be summed over and
    two text boxes for selecting the projection limits. If you click the 'lock'
    checkbox, the projection width is fixed allowing successive images along the
    z-axis to be plotted by clicking the text-box arrows. 
    
    .. warning:: There may be a bug in PySide, which causes multiple steps to 
                 occur for each arrow click. You can avoid this by selecting the 
                 'maximum' text-box and using the terminal arrow keys.
    
    When stepping through the z-values, the 'Autoscale' checkbox determines 
    whether the plot automatically scales the signal to the maximum intensity of
    the slice. 
    
    If you use the text-box arrows or the terminal arrow keys to change the 
    z-limits, the new slice is automatically plotted. If you change the limits
    by editing the text-boxes, then click the 'Replot' button to force a replot.

**Projection Tab**

    .. image:: /images/projection-tab.png
       :align: center
       :width: 75%

    The projection tab allows the data to be projected along one or two
    dimensions. The limits are set by the x, y, and z-tabs, while the projection
    axes are selected using the dropdown boxes. For a one-dimensional 
    projection, select 'None' from the y box. The projections may be plotted in
    a separate window, using the 'Plot' button or saved to a scratch NXdata 
    group within 'w0' on the tree.
    
    .. image:: /images/projection.png
       :align: center
       :width: 75%

**Options Tab**

    .. image:: /images/options-tab.png
       :align: center
       :width: 75%

    The options tab provides the standard Matplotlib toolbar. The 'Home' button
    restores all plotting limits to their defaults. The 'arrow' buttons cycle
    through previous plots. The 'zoom' button allows rectangles to be dragged 
    over the plot to define new plotting limits. The 'options' button allows the 
    Matplotlib plotting parameters (markers, colors, *etc*.) to be changed. The 
    'Save' button saves the figure to a PNG file. The final button adds the 
    plotted data to the tree pane, as an NXdata group in 'w0'.
       
Fitting NeXus Data
-------------------
It is possible to fit one-dimensional data using the non-linear least-squares fitting 
package, `lmfit-py <http://newville.github.io/lmfit-py>`_, by selecting a group on the tree 
and choosing "Fit Data" from the Data menu or by right-clicking on the group. This opens
a dialog window that allows multiple functions to be combined, with the option of fixing
or limiting parameters. 

.. image:: /images/nexpy-fits.png
   :align: center
   :width: 90%

The fit can be plotted, along with the constituent functions, in the main plotting window
and the fitting parameters displayed in a message window. The original data, the fitted 
data, constituent functions, and the parameters can all be saved to an NXentry group in 
in the Tree Pane for subsequent plotting, refitting, or saving to a NeXus file. The group
is an NXentry group, with name 'f1', 'f2', etc., stored in the default scratch NXroot 
group, w0. If you choose to fit this entry again, it will load the functions and 
parameters from the saved fit.
