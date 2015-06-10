#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

"""
Module to read in a SPE or NXSPE file and convert it to NeXus.

Each importer needs to layout the GUI buttons necessary for defining the imported file 
and its attributes and a single module, get_data, which returns an NXroot or NXentry
object. This will be added to the NeXpy tree.
"""

import os
from nexpy.gui.pyqt import QtGui

import numpy as np
from nexusformat.nexus import *
from nexusformat.nexus.tree import convert_index, centers
from nexpy.gui.importdialog import BaseImportDialog

filetype = "SPE/NXSPE File"

class ImportDialog(BaseImportDialog):
    """Dialog to import neutron SPE data"""
 
    def __init__(self, parent=None):

        super(ImportDialog, self).__init__(parent)

        self.file_type = None

        layout = QtGui.QVBoxLayout()
        layout.addLayout(self.filebox())

        title_layout = QtGui.QHBoxLayout()
        title_label = QtGui.QLabel('Title')
        self.title_box = QtGui.QLineEdit()
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_box)
        layout.addLayout(title_layout)
        
        energy_layout = QtGui.QHBoxLayout()
        energy_label = QtGui.QLabel('Incident Energy')
        self.energy_box = QtGui.QLineEdit()
        self.energy_box.setFixedWidth(150)
        energy_layout.addWidget(energy_label)
        energy_layout.addWidget(self.energy_box)
        energy_layout.addStretch()
        layout.addLayout(energy_layout)

        step_layout = QtGui.QHBoxLayout()
        Q_label = QtGui.QLabel('dQ')
        self.Q_box = QtGui.QLineEdit()
        self.Q_box.setFixedWidth(75)
        E_label = QtGui.QLabel('dE')
        self.E_box = QtGui.QLineEdit()
        self.E_box.setFixedWidth(75)
        self.convert_box = QtGui.QCheckBox('Convert to S(Q,E)')
        self.convert_box.setChecked(False)
        step_layout.addWidget(self.convert_box)
        step_layout.addStretch()
        step_layout.addWidget(Q_label)
        step_layout.addWidget(self.Q_box)
        step_layout.addWidget(E_label)
        step_layout.addWidget(self.E_box)
        step_layout.addStretch()
        layout.addLayout(step_layout)

        layout.addWidget(self.close_buttons())

        self.setLayout(layout)
  
        self.setWindowTitle("Import "+str(filetype))

    def choose_file(self):
        """
        Opens a file dialog and sets the file text box to the chosen path.
        """
        dirname = self.get_default_directory(self.filename.text())
        filename = getOpenFileName(self, 'Open File', dirname)
        if os.path.exists(filename):    # avoids problems if <Cancel> was selected
            dirname = os.path.dirname(filename)
            self.filename.setText(str(filename))
            self.set_default_directory(dirname)

        root, ext = os.path.splitext(filename)
        if ext == '.nxspe':
            self.file_type = 'NXSPE'
            spe_file = nxload(filename)
            try:
                energy = spe_file.NXentry[0].NXcollection[0].fixed_energy
                self.energy_box.setText(str(energy))
            except:
                pass
        else:
            self.file_type = 'SPE'

    def get_title(self):
        title = self.title_box.text()
        if not title:
            title = self.get_filename()
        return title

    def get_energy(self):
        try:
            return float(self.energy_box.text())
        except:
            return None

    def get_dQ(self):
        try:
            return float(self.Q_box.text())
        except:
            return None

    def get_dE(self):
        try:
            return float(self.E_box.text())
        except:
            return None

    def get_data(self):
        self.import_file = self.get_filename()
        if self.file_type == 'NXSPE':
            entry = self.get_nxspe()
        else:
            entry = self.get_spe()

        Ei, dQ, dE = self.get_energy(), self.get_dQ(), self.get_dE()
        if Ei:
            if self.convert_box.isChecked() and dQ and dE:      
                entry.sqe = convert_QE(entry, dQ, dE)
        
        return entry

    def get_spe(self, phxfile=None):
        entry = NXentry()
        phi, omega, spw, errors = readspe(self.get_filename())
        if phxfile: 
            theta, phi, dtheta, dpsi = readphx(phxfile)
            phip, psi = angles(theta, phi)
            instrument = NXinstrument(NXdetector())
            instrument.detector.polar_angle = NXfield(theta, units="degrees")
            Ei = self.get_energy()
            if Ei and Ei>0.0:
                instrument.monochromator = NXmonochromator(NXfield(Ei, name="incident_energy", units="meV"))
            if phi.ptp() > 1.0: # i.e., the azimuthal angle is specified
                instrument.detector.azimuthal_angle = NXfield(phi, units="degrees")
                instrument.detector.rotation_angle = NXfield(phip, units="degrees")
                instrument.detector.tilt_angle = NXfield(psi, units="degrees")
                data = NXdata(NXfield(spw, name="intensity", long_name="Neutron Intensity"), 
                  (NXfield(np.arange(1,len(theta)+1), name="spectrum_index", 
                       long_name="Spectrum Index"), 
                   NXfield(omega, name="energy_transfer", units="meV", 
                       long_name="Energy Transfer")),
                   errors=NXfield(np.sqrt(errors), name="errors", long_name="Errors"))
                if np.median(dtheta) > 0.0 and np.median(dpsi) > 0.0:
                    data2D = rebin2D(spw, phip, psi, omega, np.median(dtheta), np.median(dpsi))
                    return NXentry(instrument, data, data2D=data2D)
                else:
                    return NXentry(instrument, data)
            else:
                phi = np.zeros(theta.size+1)
                phi[:-1] = theta - 0.5*dtheta
                phi[-1] = theta[-1] + 0.5*dtheta[-1]
                data = NXdata(NXfield(spw, name="intensity", 
                                  long_name="Neutron Intensity"), 
                  (NXfield(phi, name="polar_angle", long_name="Polar Angle", 
                       units="degrees"), 
                   NXfield(omega, name="energy_transfer", units="meV", 
                       long_name="Energy Transfer")),
                   errors=NXfield(np.sqrt(errors), name="errors", long_name="Errors"))
                return NXentry(instrument, data)
        else:
            Ei = self.get_energy()
            if Ei and Ei>0.0:
                entry = NXentry(NXinstrument(NXmonochromator(NXfield(Ei, name="incident_energy", units="meV"))))
            else:
                entry = NXentry()
            if phi.ptp() > 1.0:
                entry.data = NXdata(
                  NXfield(spw, name="intensity", long_name="Neutron Intensity"), 
                  (NXfield(phi, name="polar_angle", units="degrees", 
                       long_name="Polar Angle"), 
                   NXfield(omega, name="energy_transfer", units="meV", 
                       long_name="Energy Transfer")),
                   errors=NXfield(np.sqrt(errors), name="errors", long_name="Errors"))
            else:
                entry.data = NXdata(
                  NXfield(spw, name="intensity", long_name="Neutron Intensity"), 
                  (NXfield(np.arange(1,len(phi)+1), name="spectrum_index",  
                       long_name="Spectrum Index"), 
                   NXfield(omega, name="energy_transfer", units="meV", 
                       long_name="Energy Transfer")),
                   errors=NXfield(np.sqrt(errors), name="errors", long_name="Errors"))
            return entry

    def get_nxspe(self):
        spe_file = nxload(self.import_file)
        entry = NXentry()
        entry.title = self.get_title()
        Ei = self.get_energy()
        if Ei and Ei > 0.0:
            entry.instrument = NXinstrument()
            entry.instrument.monochromator = NXmonochromator(NXfield(Ei, name="incident_energy", units="meV"))
        entry.data = spe_file.NXentry[0].data
        entry.data.nxsignal = entry.data.data
        if 'energy' in entry.data.entries:
            entry.data.energy.rename('energy_transfer')
        entry.data.nxaxes = [entry.data.polar, entry.data.energy_transfer]
        if 'error' in entry.data.entries:
            entry.data.error.rename('errors')   
        return entry
        
def convert_QE(entry, dQ, dE):
    """Convert S(phi,eps) to S(Q,eps)"""
    az = entry.data.azimuthal.nxdata[:]
    pol = entry.data.polar.nxdata[:]
    pol, en = centers(entry.data.nxsignal, entry.data.nxaxes)
    data = entry.data.data.nxdata[:]
    errors = entry.data.errors.nxdata[:]

    Ei = entry.instrument.monochromator.incident_energy.nxdata

    Q = np.zeros((len(pol), len(en)))
    E = np.zeros((len(pol), len(en)))

    for i in range(0,len(pol)):
        for j in range(0,len(en)):
            Q[i][j] = np.sqrt((2*Ei - en[j] - 2*np.sqrt(Ei*(Ei-en[j])) 
                               * np.cos(pol[i]*np.pi/180.0))/2.0721)
            E[i][j]=en[j]

    s = Q.shape
    Qin = Q.reshape(s[0]*s[1])
    Ein = E.reshape(s[0]*s[1])
    datain = data.reshape(s[0]*s[1])
    errorsin = errors.reshape(s[0]*s[1])

    qmin = Q.min()
    qmax = Q.max()
    emin = E.min()
    emax = E.max()
    NQ = int((qmax-qmin)/dQ) + 1
    NE = int((emax-emin)/dE) + 1
    Qb = np.linspace(qmin, qmax, NQ)
    Eb = np.linspace(emin, emax, NE)
    #histogram and normalize 
    norm, nbin = np.histogramdd((Ein,Qin), bins=(Eb,Qb))
    hist, hbin = np.histogramdd((Ein,Qin), bins=(Eb,Qb), weights=datain)
    histe, hbin = np.histogramdd((Ein,Qin), bins=(Eb,Qb), weights=errorsin*errorsin)
    histe = histe**0.5

    I = NXfield(hist/norm, name='S(Q,E)')
    err = histe/norm

    Qb = NXfield(Qb[:-1]+dQ/2., name='Q')
    Eb = NXfield(Eb[:-1]+dE/2., name='E')

    return NXdata(I, (Eb, Qb), errors=NXfield(err))

def readspe(spefile):
    """
    Read in an MSlice SPE file.
    
    The SPE files are ASCII files that contain a series of spectra as a
    function of angle and energy transfer.
    """
    f = open(spefile, 'r')
    lines = f.readlines()
    f.close()
    nphi, nomega = map(int, lines[0].split())
    i = 2
    phi = readaxisblock(lines, i, nphi+1)
    i = i + ((phi.size-1)/8) + 2
    omega = readaxisblock(lines, i, nomega+1)
    i = i + ((omega.size-1)/8) + 2
    spw = np.zeros((nphi,nomega), dtype=float)
    errors = np.zeros((nphi,nomega), dtype=float)
    blocksize = ((nomega-1)/8) + 1
    for j in range(nphi):
        spw[j] = readspeblock(lines, i, nomega)[0:nomega]
        i = i + blocksize + 1
        errors[j] = readspeblock(lines, i, nomega)[0:nomega]
        i = i + blocksize + 1
    return phi, omega, spw, errors

def readphx(phxfile):
    """
    Read in an MSlice PHX file returning the phi and theta arrays.
    """
    values = np.loadtxt(phxfile, skiprows=1, usecols=(2,3,4,5))
    return values[:,0], values[:,1], values[:,2], values[:3]

def readaxisblock(lines, start, size):
	nlines = ((size-1)/8) + 1
	try:
		return np.fromstring("".join(lines[start:start+nlines]), sep=" ")
	except ValueError:
		return np.fromstring("".join(lines[start:start+nlines-1]), sep=" ")

def readspeblock(lines, start, size):
	nlines = ((size-1)/8) + 1
	values = np.fromstring("".join(lines[start:start+nlines]), sep=" ")
	if values.size == size:
		return values.clip(0.0,1e8)    
	else:
		values = np.zeros(size)
		offset = 0
		for line in lines[start:start+nlines]:
			buffer = filter(lambda x: x.strip(), 
							[line[i:i+10] for i in range(0,80,10)])
			values[offset:offset+len(buffer)] = map(float, buffer)
			offset = offset + len(buffer)
		return values.clip(0.0,1e8)    

def angles(polar_angle, azimuthal_angle):
	theta = polar_angle*np.pi/180
	phi = azimuthal_angle*np.pi/180
	phip = np.arctan2(np.sin(theta)*np.cos(phi),np.cos(theta))
	psi = np.arctan(np.tan(phi)*np.sin(phip))
	return 180.*phip/np.pi,180.*psi/np.pi

def rebin2D(self, spw, phi, psi, omega, dphi, dpsi):
	rot = np.linspace(np.round(phi.min()-0.5*dphi,2),np.round(phi.max()+0.5*dphi,2),
					  np.round(phi.ptp()/dphi)).astype(np.float32)
	tilt = np.linspace(np.round(psi.min()-0.5*dpsi,2),np.round(psi.max()+0.5*dpsi,2),
					   np.round(psi.ptp()/dpsi)).astype(np.float32)
	en = 0.5*(omega[1:]+omega[:-1])
	data = NXfield(name='data', dtype='float32', shape=[rot.size-1,tilt.size-1,omega.size-1])
	rotation_angle = NXfield(rot, name='rotation_angle', units='degree')
	tilt_angle = NXfield(tilt, name='tilt_angle', units='degree')
	energy_transfer = NXfield(omega, name='energy_transfer', units='meV')
	pixels = np.array(zip(np.repeat(phi,en.size),np.repeat(psi,en.size),np.tile(en,phi.size)))
	hist, edges = np.histogramdd(pixels, [rot,tilt,omega], weights=spw.reshape(spw.size))
	return NXdata(NXfield(hist,name='intensity'), (rotation_angle, tilt_angle, energy_transfer))
