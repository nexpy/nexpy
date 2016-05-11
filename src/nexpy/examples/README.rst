.. restructured text format

------------------------------
About these example data files
------------------------------

These files are examples of various data files that may be read by **NeXpy**, 
either directly through the Open file dialog or indirectly by one or more of the 
file import handlers.  Either they demonstrate or test features of NeXpy or the 
:class:`Tree` interface.

==================  ==========  ===================================
file                type        description
==================  ==========  ===================================
writer_1_3.hdf5     NeXus HDF5  1-D NeXus User Manual example
chopper.nxs         NeXus HDF5  2-D time-of-flight neutron chopper 
                                spectrometer
scan101.nxs         NeXus HDF5  2-D example, includes 
                                non-NeXus components and
                                non-UTF8 characters
2-column.txt        ASCII text  1-D data example
3-column.txt        ASCII text  1-D data example with uncertainties
APS_spec_data.dat   SPEC scans  1-D scans (ascan & uascan),
                                and lots of metadata and comments
33bm_spec.dat       SPEC scans  1-D & 2-D scans (includes 
                                hklscan & hklmesh)
33id_spec.dat       SPEC scans  1-D & 2-D scans (includes 
                                mesh & Escan scans & MCA data)
==================  ==========  ===================================
