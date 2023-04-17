.. restructured text format

------------------------
About the example plugin
------------------------
This contains an example of a package, ``chopper_plugin`` that provides a
plugin menu to NeXpy. The entire directory can be copied to another location
to form the template of another plugin, which should be given a unique name.

The package has an example ``pyproject.toml`` file, which defines the name
of the package and an entry point labelled ``nexpy.readers``, which 
allows NeXpy to discover the plugin when the package has been installed, 
using ``python -m pip install .``.

Alternatively, the ``chopper`` sub-directory could be installed either
locally or within the installed NeXpy package using the ``Install Plugin...``
dialog. However, installing the plugin as an external package with an 
entry point is now the preferred method for making the plugin discoverable.

In this example, a menu item, 'Chopper', is added to the top-level NeXpy
menu, with two sub-menu items designed to operated on ``chopper.nxs``,
which is included as an example file. When loaded, select the ``chopper``
root in the NeXpy tree before clicking on either menu item.

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
