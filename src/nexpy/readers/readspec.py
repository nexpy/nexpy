# -----------------------------------------------------------------------------
# Copyright (c) 2013-2021, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
# -----------------------------------------------------------------------------
"""
Module to read in a SPEC file and convert it to NeXus.
"""
from pathlib import Path

import numpy as np
from nexpy.gui.importdialog import NXImportDialog
from nexpy.gui.pyqt import QtWidgets, getOpenFileName
from nexpy.gui.widgets import NXLabel, NXLineEdit
from nexusformat.nexus.tree import (NeXusError, NXdata, NXentry, NXfield,
                                    NXlog, NXroot)

filetype = "SPEC File"


class ImportDialog(NXImportDialog):
    """Dialog to import SPEC Scans."""

    def __init__(self, parent=None):

        super().__init__(parent=parent)

        try:
            import spec2nexus
        except ImportError:
            raise NeXusError("Please install the 'spec2nexus' module")

        self.accepted = False
        self.import_file = None     # must set in self.get_data()
        self.spec = None

        # progress bar is updated via calls to pdate_progress()
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setVisible(False)

        status_layout = QtWidgets.QHBoxLayout()
        status_layout.addWidget(self.progress_bar)
        status_layout.addStretch()
        status_layout.addWidget(self.close_buttons())

        self.layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(self.filebox())
        self.layout.addLayout(self.scanbox())
        self.layout.addLayout(status_layout)
        self.setLayout(self.layout)

        self.setWindowTitle("Import "+str(filetype))

    def scanbox(self):
        """Create widgets for specifying scan range to import."""
        scanminlabel = NXLabel("Min. Scan")
        self.scanmin = NXLineEdit(width=100, align='right')
        scanmaxlabel = NXLabel("Max. Scan")
        self.scanmax = NXLineEdit(width=100, align='right')

        scanbox = QtWidgets.QHBoxLayout()
        scanbox.addWidget(scanminlabel)
        scanbox.addWidget(self.scanmin)
        scanbox.addWidget(scanmaxlabel)
        scanbox.addWidget(self.scanmax)
        return scanbox

    def get_scan_numbers(self):
        return sorted([int(s) for s in self.spec.getScanNumbers()])

    def choose_file(self):
        """Opens file dialog, set file text box to the chosen path."""
        from spec2nexus.spec import SpecDataFile
        dirname = self.get_default_directory(self.filename.text())
        filename = getOpenFileName(self, 'Open file', dirname)
        if Path(filename).exists():
            self.filename.setText(str(filename))
            self.spec = SpecDataFile(self.get_filename())
            self.set_default_directory(Path(filename).parent)
            all_scans = self.get_scan_numbers()
            scan_min = all_scans[0]
            self.scanmin.setText(str(scan_min))
            scan_max = all_scans[-1]
            self.scanmax.setText(str(scan_max))

    def get_data(self):
        """Read the data and return :class:`NXroot` or :class:`NXentry`."""
        self.import_file = self.get_filename()
        if not Path(self.import_file).exists():
            return None
        if self.spec is None:
            return None
        scan_min = int(self.scanmin.text())
        scan_max = int(self.scanmax.text())
        all_scans = self.get_scan_numbers()
        scans = [s for s in all_scans if scan_min <= s <= scan_max]
        self.spec.progress_bar = self.progress_bar
        self.spec.update_progress = self.update_progress
        return Parser(self.spec).toTree(scans)


class Parser:
    """Parse the spec data file object."""

    def __init__(self, spec_data=None):
        """Instance of :class:`spec2nexus.prjPySpec.SpecDataFile`"""
        self.SPECfile = spec_data
        self.progress_bar = spec_data.progress_bar
        self.update_progress = spec_data.update_progress

    def openFile(self, filename):
        """Open the SPEC file and get its data."""
        from spec2nexus.spec import SpecDataFile
        if Path(filename).exists():
            self.SPECfile = SpecDataFile(filename)

    def toTree(self, scan_list=[]):
        """Convert scans from SPEC file into NXroot object and structure.

        Called from nexpy.readers.readspec.ImportDialog.get_data__prjPySpec()
        after clicking <Ok> in dialog.

        Each scan in the range from self.scanmin to self.scanmax (inclusive)
        will be converted to a NXentry.  Scan data will go in a NXdata where
        the signal=1 is the last column and the corresponding axes= is the
        first column.

        :param [int] scanlist
        :raises: ValueError is Min or Max scan number are not given properly
        """
        import spec2nexus
        from spec2nexus import utils

        # check that scan_list is valid
        if len(scan_list) == 0:
            return None

        if self.SPECfile is None:
            return None

        complete_scan_list = list(self.SPECfile.scans)
        for key in [str(s) for s in scan_list]:
            if key not in complete_scan_list:
                msg = 'scan ' + str(key) + ' was not found'
                raise ValueError(msg)

        root = NXroot()

        root.attrs['spec2nexus'] = str(spec2nexus.__version__)
        header0 = self.SPECfile.headers[0]
        root.attrs['SPEC_file'] = self.SPECfile.fileName
        root.attrs['SPEC_epoch'] = header0.epoch
        root.attrs['SPEC_date'] = utils.iso8601(header0.date)
        root.attrs['SPEC_comments'] = '\n'.join(header0.comments)
        try:
            c = header0.comments[0]
            user = c[c.find('User = '):].split('=')[1].strip()
            root.attrs['SPEC_user'] = user
        except Exception:
            pass
        root.attrs['SPEC_num_headers'] = len(self.SPECfile.headers)

        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(scan_list[0], scan_list[-1])
        for key in [str(s) for s in scan_list]:
            scan = self.SPECfile.getScan(key)
            scan.interpret()
            entry = NXentry()
            entry.title = str(scan)
            entry.date = utils.iso8601(scan.date)
            entry.command = scan.scanCmd
            entry.scan_number = NXfield(scan.scanNum)
            entry.comments = '\n'.join(scan.comments)
            entry.data = self.scan_NXdata(
                scan)            # store the scan data
            entry.positioners = self.metadata_NXlog(
                scan.positioner, 'SPEC positioners (#P & #O lines)')
            if hasattr(scan, 'metadata') and len(scan.metadata) > 0:
                entry.metadata = self.metadata_NXlog(
                    scan.metadata,
                    'SPEC metadata (UNICAT-style #H & #V lines)')

            if len(scan.G) > 0:
                entry.G = NXlog()
                desc = "SPEC geometry arrays, defined by SPEC diffractometer"
                # e.g.: SPECD/four.mac
                # http://certif.com/spec_manual/fourc_4_9.html
                entry.G.attrs['description'] = desc
                for item, value in scan.G.items():
                    entry.G[item] = NXfield(list(map(float, value.split())))
            if scan.T != '':
                entry['counting_basis'] = NXfield(
                    'SPEC scan with constant counting time')
                entry['T'] = NXfield(float(scan.T))
                entry['T'].units = 's'
                entry['T'].description = 'Scan with constant counting time'
            elif scan.M != '':
                entry['counting_basis'] = NXfield(
                    'SPEC scan with constant monitor count')
                entry['M'] = NXfield(float(scan.M))
                entry['M'].units = 'counts'
                entry['M'].description = 'Scan with constant monitor count'
            if scan.Q != '':
                entry['Q'] = NXfield(list(map(float, scan.Q)))
                entry['Q'].description = 'hkl at start of scan'

            root['scan_' + str(key)] = entry

            self.progress_bar.setValue(int(key))
            self.update_progress()

        return root

    def scan_NXdata(self, scan):
        """Return the scan data in an NXdata object."""

        nxdata = NXdata()

        if len(scan.data) == 0:       # what if no data?
            # since no data available, provide trivial, fake data
            # keeping the NXdata base class compliant with the NeXus standard
            nxdata.attrs['description'] = 'SPEC scan has no data'
            nxdata['noSpecData_y'] = NXfield([0, 0])   # primary Y axis
            nxdata['noSpecData_x'] = NXfield([0, 0])   # primary X axis
            nxdata.nxsignal = nxdata['noSpecData_y']
            nxdata.nxaxes = [nxdata['noSpecData_x'], ]
            return nxdata

        nxdata.attrs['description'] = 'SPEC scan data'

        scan_type = scan.scanCmd.split()[0]
        if scan_type in ('mesh', 'hklmesh'):
            # hklmesh  H 1.9 2.1 100  K 1.9 2.1 100  -800000
            self.parser_mesh(nxdata, scan)
        elif scan_type in ('hscan', 'kscan', 'lscan', 'hklscan'):
            # hklscan  1.00133 1.00133  1.00133 1.00133  2.85 3.05  200 -400000
            h_0, h_N, k_0, k_N, l_0, l_N = scan.scanCmd.split()[1:7]
            if h_0 != h_N:
                axis = 'H'
            elif k_0 != k_N:
                axis = 'K'
            elif l_0 != l_N:
                axis = 'L'
            else:
                axis = 'H'
            self.parser_1D_columns(nxdata, scan)
            nxdata.nxaxes = nxdata[axis]
        else:
            self.parser_1D_columns(nxdata, scan)

        return nxdata

    def parser_1D_columns(self, nxdata, scan):
        """Generic data parser for 1-D column data."""
        from spec2nexus import utils
        for column in scan.L:
            if column in scan.data:
                clean_name = utils.sanitize_name(nxdata, column)
                nxdata[clean_name] = NXfield(scan.data[column])
                nxdata[clean_name].original_name = column

        signal = utils.sanitize_name(
            nxdata, scan.column_last)  # primary Y axis
        axis = utils.sanitize_name(
            nxdata, scan.column_first)  # primary X axis
        nxdata.nxsignal = nxdata[signal]
        nxdata.nxaxes = nxdata[axis]

        self.parser_mca_spectra(nxdata, scan, axis)

    def parser_mca_spectra(self, nxdata, scan, primary_axis_label):
        """Parse for optional MCA spectra."""
        if '_mca_' in scan.data:        # check for it
            for mca_key, mca_data in scan.data['_mca_'].items():
                key = "__" + mca_key
                nxdata[key] = NXfield(mca_data)
                nxdata[key].units = "counts"
                ch_key = key + "_channel"
                nxdata[ch_key] = NXfield(range(1, len(mca_data[0])+1))
                nxdata[ch_key].units = 'channel'
                axes = (primary_axis_label, ch_key)
                nxdata[key].axes = ':'.join(axes)

    def parser_mesh(self, nxdata, scan):
        """Data parser for 2-D mesh and hklmesh."""
        # 2-D parser: http://www.certif.com/spec_help/mesh.html
        # mesh motor1 start1 end1 intervals1 motor2 start2 end2 intervals2 time
        # 2-D parser: http://www.certif.com/spec_help/hklmesh.html
        #  hklmesh Q1 start1 end1 intervals1 Q2 start2 end2 intervals2 time
        # mesh:    nexpy/examples/33id_spec.dat  scan 22  (MCA gives 3-D data)
        # hklmesh: nexpy/examples/33bm_spec.dat  scan 17  (no MCA data)
        from spec2nexus import utils
        (label1, start1, end1, intervals1, label2, start2, end2,
         intervals2, time) = scan.scanCmd.split()[1:]
        if label1 not in scan.data:
            label1 = scan.L[0]      # mnemonic v. name
        if label2 not in scan.data:
            label2 = scan.L[1]      # mnemonic v. name
        axis1 = scan.data.get(label1)
        axis2 = scan.data.get(label2)
        intervals1, intervals2 = int(intervals1), int(intervals2)
        start1, end1 = float(start1), float(end1)
        start2, end2 = float(start2), float(end2)
        time = float(time)
        if len(axis1) < intervals1:  # stopped scan before second row started
            self.parser_1D_columns(nxdata, scan)        # fallback support
            # TODO: what about the MCA data in this case?
        else:
            axis1 = axis1[0:intervals1+1]
            axis2 = [axis2[row]
                     for row in range(len(axis2)) if row % (intervals1+1) == 0]

            column_labels = scan.L
            column_labels.remove(label1)    # special handling
            column_labels.remove(label2)    # special handling
            if scan.scanCmd.startswith('hkl'):
                # find the reciprocal space axis held constant
                label3 = [
                    key for key in ('H', 'K', 'L')
                    if key not in (label1, label2)][0]
                axis3 = scan.data.get(label3)[0]
                nxdata[label3] = NXfield(axis3)
                column_labels.remove(label3)    # already handled

            nxdata[label1] = NXfield(axis1)    # 1-D array
            nxdata[label2] = NXfield(axis2)    # 1-D array

            # build 2-D data objects
            data_shape = [len(axis2), len(axis1)]
            for label in column_labels:
                axis = np.array(scan.data.get(label))
                clean_name = utils.sanitize_name(nxdata, label)
                nxdata[clean_name] = NXfield(
                    utils.reshape_data(axis, data_shape))
                nxdata[clean_name].original_name = label

            signal_axis_label = utils.sanitize_name(nxdata, scan.column_last)
            nxdata.nxsignal = nxdata[signal_axis_label]
            nxdata.nxaxes = [nxdata[label2], nxdata[label1]]

        if '_mca_' in scan.data:    # 3-D array
            # TODO: ?merge with parser_mca_spectra()?
            for mca_key, mca_data in scan.data['_mca_'].items():
                key = "__" + mca_key

                spectra_lengths = list(map(len, mca_data))
                num_channels = max(spectra_lengths)
                if num_channels != min(spectra_lengths):
                    msg = 'MCA spectra have different lengths'
                    msg += ' in scan #' + str(scan.scanNum)
                    msg += ' in file ' + str(scan.specFile)
                    raise ValueError(msg)

                data_shape += [num_channels, ]
                mca = np.array(mca_data)
                nxdata[key] = NXfield(utils.reshape_data(mca, data_shape))
                nxdata[key].units = "counts"

                try:
                    # use MCA channel numbers as known at time of scan
                    chan1 = scan.MCA['first_saved']
                    chanN = scan.MCA['last_saved']
                    channel_range = range(chan1, chanN+1)
                except Exception:
                    # basic indices
                    channel_range = range(1, num_channels+1)

                ch_key = key + "_channel"
                nxdata[ch_key] = NXfield(channel_range)
                nxdata[ch_key].units = 'channel'
                axes = (label1, label2, ch_key)
                nxdata[key].axes = ':'.join(axes)

    def metadata_NXlog(self, spec_metadata, description):
        """Return the specific metadata in an NXlog object."""
        from spec2nexus import utils
        nxlog = NXlog()
        nxlog.attrs['description'] = description
        for subkey, value in spec_metadata.items():
            clean_name = utils.sanitize_name(nxlog, subkey)
            nxlog[clean_name] = NXfield(value)
            nxlog[clean_name].original_name = subkey
        return nxlog
