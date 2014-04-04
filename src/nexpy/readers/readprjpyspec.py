#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

'''Module to read in a SPEC file and convert it to NeXus.'''

from PySide import QtCore, QtGui    #@UnusedImport

import numpy as np                  #@UnusedImport
import os                           #@UnusedImport
from nexpy.api.nexus import *       #@UnusedWildImport
from nexpy.gui.importdialog import BaseImportDialog

filetype = "SPEC File (prjPySpec)"


class ImportDialog(BaseImportDialog):
    """Dialog to import SPEC Scans"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)

        self.accepted = False
        from nexpy.gui.consoleapp import _mainwindow
        self.default_directory = _mainwindow.default_directory
        self.import_file = None     # must set in self.get_data()
        self.spec = None

        # TODO: how is this updated?
        self.progress_bar = QtGui.QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout = QtGui.QHBoxLayout()
        status_layout.addWidget(self.progress_bar)
        status_layout.addStretch()
        status_layout.addWidget(self.buttonbox())

        self.layout = QtGui.QVBoxLayout()
        self.layout.addLayout(self.filebox())
        self.layout.addLayout(self.scanbox())
        self.layout.addLayout(status_layout)
        self.setLayout(self.layout)

        self.setWindowTitle("Import "+str(filetype))
 
    def scanbox(self):
        '''create widgets for specifying scan range to import'''
        scanminlabel = QtGui.QLabel("Min. Scan")
        self.scanmin = QtGui.QLineEdit()
        self.scanmin.setFixedWidth(100)
        self.scanmin.setAlignment(QtCore.Qt.AlignRight)
        scanmaxlabel = QtGui.QLabel("Max. Scan")
        self.scanmax = QtGui.QLineEdit()
        self.scanmax.setFixedWidth(100)
        self.scanmax.setAlignment(QtCore.Qt.AlignRight)

        scanbox = QtGui.QHBoxLayout()
        scanbox.addWidget(scanminlabel)
        scanbox.addWidget(self.scanmin)
        scanbox.addWidget(scanmaxlabel)
        scanbox.addWidget(self.scanmax)
        return scanbox

    def choose_file(self):
        '''
        Opens file dialog, set file text box to the chosen path
        '''
        import pkg_resources
        pkg_resources.require("spec2nexus>=2014.0320.6")
        from spec2nexus.prjPySpec import SpecDataFile

        dirname = self.get_default_directory(self.filename.text())
        filename, _ = QtGui.QFileDialog.getOpenFileName(self, 'Open file', dirname)
        if os.path.exists(filename):
            self.filename.setText(str(filename))
            self.spec = SpecDataFile(self.get_filename())
            self.set_default_directory(os.path.dirname(filename))
            scan_min = self.spec.getMinScanNumber()
            self.scanmin.setText(str(scan_min))
            scan_max = self.spec.getMaxScanNumber()
            self.scanmax.setText(str(scan_max))

    def get_data(self):
        '''read the data and return either :class:`NXroot` or :class:`NXentry`'''
        self.import_file = self.get_filename()
        if not os.path.exists(self.import_file):
            return None
        if self.spec is None:
            return None
        scan_min = int(self.scanmin.text())
        scan_max = int(self.scanmax.text())
        all_scans = self.spec.getScanNumbers()
        scans = [s for s in all_scans if scan_min <= s <= scan_max]
        return Parser(self.spec).toTree(scans)


class Parser(object):
    '''parse the spec data file object'''
    
    def __init__(self, spec_data = None):
        ''':param obj spec_data: instance of :class:`spec2nexus.prjPySpec.SpecDataFile`'''
        self.SPECfile = spec_data
    
    def openFile(self, filename):
        '''open the SPEC file and get its data'''
        from spec2nexus.prjPySpec import SpecDataFile
        if os.path.exists(filename):
            self.SPECfile = SpecDataFile(filename)
    
    def toTree(self, scan_list=[]):
        '''
        convert scans from chosen SPEC file into NXroot object and structure
        
        called from nexpy.readers.readspec.ImportDialog.get_data__prjPySpec() after clicking <Ok> in dialog
        
        Each scan in the range from self.scanmin to self.scanmax (inclusive)
        will be converted to a NXentry.  Scan data will go in a NXdata where 
        the signal=1 is the last column and the corresponding axes= is the first column.
        
        :param [int] scanlist
        :raises: ValueError is Min or Max scan number are not given properly
        '''
        import spec2nexus
        from spec2nexus import utils
        # check that scan_list is valid
        if len(scan_list) == 0:
            return None
        
        if self.SPECfile is None:
            return None

        complete_scan_list = self.SPECfile.scans.keys()
        for key in scan_list:
            if key not in complete_scan_list:
                msg = 'scan ' + str(key) + ' was not found'
                raise ValueError, msg
        
        root = NXroot()

        root.attrs['prjPySpec_version'] = spec2nexus.__version__
        header0 = self.SPECfile.headers[0]
        root.attrs['SPEC_file'] = self.SPECfile.fileName
        root.attrs['SPEC_epoch'] = header0.epoch
        root.attrs['SPEC_date'] = utils.iso8601(header0.date)
        root.attrs['SPEC_comments'] = '\n'.join(header0.comments)
        try:
            c = header0.comments[0]
            user = c[c.find('User = '):].split('=')[1].strip()
            root.attrs['SPEC_user'] = user
        except:
            pass
        root.attrs['SPEC_num_headers'] = len(self.SPECfile.headers)

        for key in scan_list:
            scan = self.SPECfile.getScan(key)
            entry = NXentry()
            entry.title = str(scan)
            entry.date = utils.iso8601(scan.date)  
            entry.command = scan.scanCmd 
            entry.scan_number = NXfield(scan.scanNum)
            entry.comments = '\n'.join(scan.comments)
            entry.data = self.scan_NXdata(scan)            # store the scan data
            entry.positioners = self.metadata_NXlog(scan.positioner, 
                                                    'SPEC positioners (#P & #O lines)')
            if len(scan.metadata) > 0:
                entry.metadata = self.metadata_NXlog(scan.metadata, 
                                                     'SPEC metadata (UNICAT-style #H & #V lines)')

            if len(scan.G) > 0:
                entry.G = NXlog()
                desc = "SPEC geometry arrays, meanings defined by SPEC diffractometer support"
                # e.g.: SPECD/four.mac
                # http://certif.com/spec_manual/fourc_4_9.html
                entry.G.attrs['description'] = desc
                for item, value in scan.G.items():
                    entry.G[item] = NXfield(map(float, value.split()))
            if scan.T != '':
                entry['counting_basis'] = NXfield('SPEC scan with constant counting time')
                entry['T'] = NXfield(float(scan.T))
                entry['T'].units = 'seconds'
                entry['T'].description = 'SPEC scan with constant counting time'
            elif scan.M != '':
                entry['counting_basis'] = NXfield('SPEC scan with constant monitor count')
                entry['M'] = NXfield(float(scan.M))
                entry['M'].units = 'counts'
                entry['M'].description = 'SPEC scan with constant monitor count'
            if scan.Q != '':
                entry['Q'] = NXfield(map(float,scan.Q.split()))
                entry['Q'].description = 'hkl at start of scan'

            root['scan_' + str(key)] = entry
        return root
    
    def scan_NXdata(self, scan):
        '''
        return the scan data in an NXdata object
        '''
        nxdata = NXdata()
        nxdata.attrs['description'] = 'SPEC scan data'
        
        scan_type = scan.scanCmd.split()[0]
        if scan_type in ('mesh', 'hklmesh'):
            # hklmesh  H 1.9 2.1 100  K 1.9 2.1 100  -800000
            self.parser_mesh(nxdata, scan)
        elif scan_type in ('hscan', 'kscan', 'lscan', 'hklscan'):
            # hklscan  1.00133 1.00133  1.00133 1.00133  2.85 3.05  200 -400000
            h_0, h_N, k_0, k_N, l_0, l_N = scan.scanCmd.split()[1:7]
            if   h_0 != h_N: axis = 'H'
            elif k_0 != k_N: axis = 'K'
            elif l_0 != l_N: axis = 'L'
            self.parser_1D_columns(nxdata, scan)
            nxdata.nxaxes = nxdata[axis]
        else:
            self.parser_1D_columns(nxdata, scan)

        # these locations suggested to NIAC, easier to parse than attached to dataset!
        nxdata.attrs['signal'] = nxdata.nxsignal.nxname         
        nxdata.attrs['axes'] = ':'.join([obj.nxname for obj in nxdata.nxaxes])
        
        return nxdata
    
    def parser_1D_columns(self, nxdata, scan):
        '''generic data parser for 1-D column data'''
        from spec2nexus import utils
        for column in scan.L:
            clean_name = utils.sanitize_name(nxdata, column)
            nxdata[clean_name] = NXfield(scan.data[column])
            nxdata[clean_name].original_name = column

        signal = utils.sanitize_name(nxdata, scan.column_last)      # primary Y axis
        axis = utils.sanitize_name(nxdata, scan.column_first)       # primary X axis
        nxdata.nxsignal = nxdata[signal]
        nxdata.nxaxes = nxdata[axis]
        
        self.parser_mca_spectra(nxdata, scan, axis)
    
    def parser_mca_spectra(self, nxdata, scan, primary_axis_label):
        '''parse for optional MCA spectra'''
        if '_mca_' in scan.data:        # check for it
            nxdata.mca__spectrum_ = NXfield(scan.data['_mca_'])
            nxdata.mca__spectrum_channel = NXfield(range(1, len(scan.data['_mca_'][0])+1))
            nxdata.mca__spectrum_channel.units = 'channel'
            axes = (primary_axis_label, 'mca__spectrum_channel')
            nxdata.mca__spectrum_.axes = ':'.join( axes )
    
    def parser_mesh(self, nxdata, scan):
        '''data parser for 2-D mesh and hklmesh'''
        # 2-D parser: http://www.certif.com/spec_help/mesh.html
        # mesh motor1 start1 end1 intervals1 motor2 start2 end2 intervals2 time
        # 2-D parser: http://www.certif.com/spec_help/hklmesh.html
        #  hklmesh Q1 start1 end1 intervals1 Q2 start2 end2 intervals2 time
        # mesh:    nexpy/examples/33id_spec.dat  scan 22
        # hklmesh: nexpy/examples/33bm_spec.dat  scan 17
        from spec2nexus import utils
        label1, start1, end1, intervals1, label2, start2, end2, intervals2, time = scan.scanCmd.split()[1:]
        if label1 not in scan.data:
            label1 = scan.L[0]      # mnemonic v. name
        if label2 not in scan.data:
            label2 = scan.L[1]      # mnemonic v. name
        axis1 = scan.data.get(label1)
        axis2 = scan.data.get(label2)
        intervals1, intervals2 = map(int, (intervals1, intervals2))
        start1, end1, start2, end2, time = map(float, (start1, end1, start2, end2, time))
        if len(axis1) < intervals1:     # stopped scan before second row started
            self.parser_1D_columns(nxdata, scan)        # fallback support
        else:
            axis1 = axis1[0:intervals1+1]
            axis2 = [axis2[row] for row in range(len(axis2)) if row % (intervals1+1) == 0]

            column_labels = scan.L
            column_labels.remove(label1)    # special handling
            column_labels.remove(label2)    # special handling
            if scan.scanCmd.startswith('hkl'):
                # find the reciprocal space axis held constant
                label3 = [key for key in ('H', 'K', 'L') if key not in (label1, label2)][0]
                axis3 = scan.data.get(label3)[0]
                nxdata[label3] = NXfield(axis3)
                column_labels.remove(label3)    # already handled

            nxdata[label1] = NXfield(axis1)    # 1-D array
            nxdata[label2] = NXfield(axis2)    # 1-D array

            # build 2-D data objects (do not build label1, label2, [or label3] as 2-D objects)
            data_shape = [len(axis1), len(axis2)]
            for label in column_labels:
                axis = np.array( scan.data.get(label) )
                clean_name = utils.sanitize_name(nxdata, label)
                nxdata[clean_name] = NXfield(utils.reshape_data(axis, data_shape))
                nxdata[clean_name].original_name = label

            signal_axis_label = utils.sanitize_name(nxdata, scan.column_last)
            nxdata.nxsignal = nxdata[signal_axis_label]
            nxdata.nxaxes = [nxdata[label1], nxdata[label2]]

        if '_mca_' in scan.data:    # 3-D array
            # TODO: ?merge with parser_mca_spectra()?
            num_channels = len(scan.data['_mca_'][0])
            data_shape.append(num_channels)
            mca = np.array(scan.data['_mca_'])
            nxdata.mca__spectrum_ = NXfield(utils.reshape_data(mca, data_shape))
            nxdata.mca__spectrum_channel = NXfield(range(1, num_channels+1))
            nxdata.mca__spectrum_channel.units = 'channel'
            axes = (label1, label2, 'mca__spectrum_channel')
            nxdata.mca__spectrum_.axes = ':'.join( axes )
    
    def metadata_NXlog(self, spec_metadata, description):
        '''
        return the specific metadata in an NXlog object
        '''
        from spec2nexus import utils
        nxlog = NXlog()
        nxlog.attrs['description'] = description
        for subkey, value in spec_metadata.items():
            clean_name = utils.sanitize_name(nxlog, subkey)
            nxlog[clean_name] = NXfield(value)
            nxlog[clean_name].original_name = subkey
        return nxlog
