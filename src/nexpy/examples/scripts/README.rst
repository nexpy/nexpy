.. restructured text format

---------------------------
About these example scripts
---------------------------

These files are examples of scripts that can be run from the script editor
within NeXpy. If they are copied to ~/.nexpy/scripts, they can be opened 
directly from the Scripts Menu.

**chopper_plot.py**

A simple script to plot a sequence of cuts, displaced along the y-axis. It
assumes that ``chopper.nxs``, which is one of the example files, has been 
loaded.

**spefix.py**

This is a more elaborate script that shows how a sequence of cuts in a 
two-dimensional data set can be automatically fitted to a simple function (a
Gaussian and a Linear function) and then subtracted from the two-dimensional
data and stored in a new workspace that is added to the tree. This uses the 
Fit class that is normally accessed through the GUI Data Menu.

