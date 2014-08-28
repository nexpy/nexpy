from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.api.nexus import NXfield, NXdata, NeXusError
from nexpy.api.nexus.tree import centers


def show_dialog(parent=None):
    try:
        dialog = ConvertDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Converting to (Q,E)", error)
        

class ConvertDialog(BaseDialog):

    def __init__(self, parent=None):
        super(ConvertDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        if self.root.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.ei_box = QtGui.QLineEdit()
        self.dq_box = QtGui.QLineEdit()
        self.de_box = QtGui.QLineEdit()
        
        grid.addWidget(QtGui.QLabel('Incident Energy:'), 0, 0)
        grid.addWidget(QtGui.QLabel('Q Step:'), 1, 0)
        grid.addWidget(QtGui.QLabel('Energy Step:'), 2, 0)
        grid.addWidget(self.ei_box, 0, 1)
        grid.addWidget(self.dq_box, 1, 1)
        grid.addWidget(self.de_box, 2, 1)
        layout.addLayout(grid)
        button_layout = QtGui.QHBoxLayout()
        self.plot_button = QtGui.QPushButton('Plot')
        self.plot_button.clicked.connect(self.plot_data)
        self.save_button = QtGui.QPushButton('Save')
        self.save_button.clicked.connect(self.save_data)
        button_layout.addWidget(self.plot_button)
        button_layout.addWidget(self.save_button)
        layout.addLayout(button_layout)
        layout.addWidget(self.buttonbox())
        self.setLayout(layout)
        self.setWindowTitle('Converting to (Q,E)')

        self.ei_box.setText(str(self.read_parameter(self.root,
                            'entry/instrument/monochromator/energy')))
        self.dq_box.setText('0.5') #Currently hard-coded, but should be based on
        self.de_box.setText('2.0') #the angular range and incident energy.

    @property
    def Ei(self):
        return np.float32(self.ei_box.text())

    @property
    def dQ(self):
        return np.float32(self.dq_box.text())

    @property
    def dE(self):
        return np.float32(self.de_box.text())

    def read_parameters(self):
        self.L1 = - self.read_parameter(self.root, 'entry/sample/distance')
        self.L2 = np.mean(self.root['entry/instrument/detector/distance'])
        self.m1 = self.root['entry/monitor1']
        self.t_m1 = self.m1.moment()
        self.d_m1 = self.read_parameter(self.root, 'entry/monitor1/distance')

    def convert_tof(self, tof):
        ki = np.sqrt(self.Ei / 2.0721)
        ts = self.t_m1 + 1588.254 * (self.L1 - self.d_m1) / ki
        kf = 1588.254 * self.L2 / (tof - ts)
        eps = self.Ei - 2.0721*kf**2
        return eps

    def convert_QE(self):
        """Convert S(phi,eps) to S(Q,eps)"""

        self.read_parameters()

        entry = self.root['entry']
        Ei = self.Ei
        dQ = self.dQ
        dE = self.dE

        pol, tof = centers(entry.data.nxsignal, entry.data.nxaxes)
        en = self.convert_tof(tof)

        idx_max = min(np.where(np.abs(en-0.75*Ei)<0.1)[0])

        en = en[:idx_max]

        data = entry.data.nxsignal.nxdata[:,:idx_max]
        if entry.data.nxerrors:
            errors = entry.data.nxerrors.nxdata[:]

        Q = np.zeros((len(pol), len(en)))
        E = np.zeros((len(pol), len(en)))

        for i in range(0,len(pol)):
            for j in range(0,len(en)):
                Q[i,j] = np.sqrt((2*Ei - en[j] - 2*np.sqrt(Ei*(Ei-en[j])) 
                                   * np.cos(pol[i]*np.pi/180.0))/2.0721)
                E[i,j]=en[j]

        s = Q.shape
        Qin = Q.reshape(s[0]*s[1])
        Ein = E.reshape(s[0]*s[1])
        datain = data.reshape(s[0]*s[1])
        if entry.data.nxerrors:
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
        if entry.data.nxerrors:
            histe, hbin = np.histogramdd((Ein,Qin), bins=(Eb,Qb), weights=errorsin*errorsin)
            histe = histe**0.5
            err = histe/norm

        I = NXfield(hist/norm, name='S(Q,E)')

        Qb = NXfield(Qb[:-1]+dQ/2., name='Q')
        Eb = NXfield(Eb[:-1]+dE/2., name='E')

        result = NXdata(I, (Eb, Qb))
        if entry.data.nxerrors:
            result.errors = NXfield(err)
        return result

    def plot_data(self):
        self.convert_QE().plot()

    def save_data(self):
        self.root['entry/sqe'] = self.convert_QE()