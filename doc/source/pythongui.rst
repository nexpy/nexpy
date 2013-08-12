*******************************
Python Graphical User Interface
*******************************
A PyQT GUI has been created to make it easier to keep track of the loaded NeXus files and
the results of any subsequent analysis. It is invoked from the command line by::

 > nexpy

.. image:: /images/nexpy-gui.png

The GUI contains three main panes:

**Tree Pane**
    This contains the tree structure of NeXus files opened in the File menu and/or any 
    NXroot and NXentry groups created within the shell.
    
**Plot Pane**
    Any NXdata or NXmonitor group can be plotted in this pane by right-clicking on the 
    relevant node in the tree.

**Shell Pane**
    This is an iPython shell, with NeXpy already imported (as * so no prefixes are 
    necessary), along with Numpy (as np) and Pylab (as plt). Any assignments to items in 
    the tree pane are automatically reflected in the tree pane, and new NXroot, NXentry, 
    or NXdata objects can be added to the tree from the iPython shell. The NeXus data
    plot methods from the shell to plot into the plot pane, and Matplotlib commands can
    be used to modify the plot characteristics. 

There are a number of useful features available when running NeXpy within the GUI shell. 

#. Data can be loaded with the File\:Open menu item using a standard file browser window.
#. All current NeXus data trees are easy to inspect in the pane on the upper left side. 
   Hovering over a data item produces a tooltip containing a list of all the item's children. 
#. Newly created group can be added to the tree at any time.
#. Any changes to data sets in the scripting window will be reflected within the tree 
   pane.
#. NXdata and NXmonitor plots can be displayed by right-clicking and choosing 'Plot Data'.
#. Any one-dimensional array can be plotted against any other one-dimensional array in the
   same group.
#. One-dimensional NXdata and NXmonitor data can be fit to a flexible combination of
   model functions using non-linear least-squares methods by right-clicking and choosing 
   'Fit Data'.
#. Axis limits are set by a series of slider bars.
#. The scripting shell provides convenient autocompletion, and automatically displays 
   function docstrings as a tooltip when you open the function parentheses.

Adding NeXus Data to the Tree View
----------------------------------
If you create a NeXus group dynamically in the iPython shell, it can be added to the tree 
view using the tree's add method::

 >>> a=NXroot()
 >>> a.entry = NXentry()
 >>> tree.add(a)

If the group is not an NXroot group, the data will be wrapped automatically in an NXroot 
group and given a default name that doesn't conflict with existing tree nodes, *e.g.*, 
w4.

Plotting NeXus Data
-------------------
NXdata, NXmonitor, and NXlog data can be plotted by right-clicking on the group within 
the tree. The plot pane contains a toolbar to change axis or signal intensity limits. 
The slider provides a graphical way of setting minimum and/or maximum values or they can 
be typed into the text boxes.

.. image:: /images/axis-limits-bar.png

There are two checkboxes:

**Lock**
    If the maximum and/or minimum values are not set to the limits, then this checkbox 
    locks the difference between the two. This checkbox disables setting of the minimum 
    value. You can step through the z-values with automatic replots by selecting the 
    maximum box and using the keyboard up and down arrows or by clicking the box arrows.
**Autoscale**
    When stepping through the z-values, this checkbox determines whether the plot should 
    change the color scale.
