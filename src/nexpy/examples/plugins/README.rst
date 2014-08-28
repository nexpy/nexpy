.. restructured text format

------------------------
About the example plugin
------------------------

This contains an example of a package that provides a plugin menu to NeXpy. If 
the package is copied to ~/.nexpy/plugins, a new menu item should appear in the 
main NeXpy menu. The two menu items are designed to operated on ``chopper.nxs``, 
which is included as an example file.

The requirement for a plugin is that a function ``plugin_menu`` initializes 
the submenu items in the package's ``__init__.py``. These would normally 
initiate dialog boxes that are defined within files in the package, although
they could also be imported from an external package.

**get_ei**

A simple GUI to calibrate the incident energy by determining the first moments
of two monitor peaks and computing the energy from the time difference. The
NeXus root must be selected and unlocked so that the calibrated energy can 
be saved to the NXmonochromator group.

**convert_qe**

A simple GUI to convert inelastic neutron scattering data in ``chopper.nxs`` 
from angular and time-of-flight coordinates into Q and energy transfer. After
choosing Q and energy bin sizes, the converted data can be plotted and/or
saved as a new NXdata group within the NeXus root.
