import numpy as np
from nexpy.gui.datadialogs import GridParameters, NXDialog
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError, NXdata, NXfield
from nexusformat.nexus.tree import centers


def show_dialog():
    try:
        dialog = ConvertDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Converting to (Q,E)", error)


class ConvertDialog(NXDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.select_entry()
        self.parameters = GridParameters()
        self.parameters.add(
            'Ei', self.entry['instrument/monochromator/energy'],
            'Incident Energy')
        self.parameters.add('dQ', self.round(np.sqrt(self.Ei/2)/50), 'Q Step')
        self.parameters.add('dE', self.round(self.Ei/50), 'Energy Step')
        self.set_layout(self.entry_layout,
                        self.parameters.grid(),
                        self.action_buttons(('Plot', self.plot_data),
                                            ('Save', self.save_data)),
                        self.close_buttons())
        self.setWindowTitle('Converting to (Q,E)')

    @property
    def Ei(self):
        return self.parameters['Ei'].value

    @property
    def dQ(self):
        return self.parameters['dQ'].value

    @property
    def dE(self):
        return self.parameters['dE'].value

    def read_parameters(self):
        self.L1 = - self.entry['sample/distance']
        self.L2 = self.entry['instrument/detector/distance'].average()
        self.m1 = self.entry['monitor1']
        self.t_m1 = self.m1.moment()
        self.d_m1 = self.entry['monitor1/distance']

    def convert_tof(self, tof):
        ki = np.sqrt(self.Ei / 2.0721)
        ts = self.t_m1 + 1588.254 * (self.L1 - self.d_m1) / ki
        kf = 1588.254 * self.L2 / (tof - ts)
        eps = self.Ei - 2.0721*kf**2
        return eps

    def convert_QE(self):
        """Convert S(phi,eps) to S(Q,eps)"""

        self.read_parameters()

        Ei = self.Ei
        dQ = self.dQ
        dE = self.dE

        signal = self.entry['data'].nxsignal
        pol = centers(self.entry['data/polar_angle'], signal.shape[0])
        tof = centers(self.entry['data/time_of_flight'], signal.shape[1])
        en = self.convert_tof(tof)

        idx_max = min(np.where(np.abs(en-0.75*Ei) < 0.1)[0])

        en = en[:idx_max]

        data = signal.nxdata[:, :idx_max]
        if self.entry['data'].nxerrors:
            errors = self.entry['data'].nxerrors.nxdata[:]

        Q = np.zeros((len(pol), len(en)))
        E = np.zeros((len(pol), len(en)))

        for i in range(0, len(pol)):
            p = pol[i]
            Q[i, :] = np.array(np.sqrt((2*Ei - en - 2*np.sqrt(Ei*(Ei-en))
                                       * np.cos(p*np.pi/180.0))/2.0721))
            E[i, :] = np.array(en)

        s = Q.shape
        Qin = Q.reshape(s[0]*s[1])
        Ein = E.reshape(s[0]*s[1])
        datain = data.reshape(s[0]*s[1])
        if self.entry['data'].nxerrors:
            errorsin = errors.reshape(s[0]*s[1])

        qmin = Q.min()
        qmax = Q.max()
        emin = E.min()
        emax = E.max()
        NQ = int((qmax-qmin)/dQ) + 1
        NE = int((emax-emin)/dE) + 1
        Qb = np.linspace(qmin, qmax, NQ)
        Eb = np.linspace(emin, emax, NE)
        # histogram and normalize
        norm, nbin = np.histogramdd((Ein, Qin), bins=(Eb, Qb))
        hist, hbin = np.histogramdd((Ein, Qin), bins=(Eb, Qb), weights=datain)
        if self.entry['data'].nxerrors:
            histe, hbin = np.histogramdd((Ein, Qin), bins=(Eb, Qb),
                                         weights=errorsin * errorsin)
            histe = histe**0.5
            err = histe/norm

        Ib = NXfield(hist/norm, name='S(Q,E)')

        Qb = NXfield(Qb[:-1]+dQ/2., name='Q')
        Eb = NXfield(Eb[:-1]+dE/2., name='E')

        result = NXdata(Ib, (Eb, Qb))
        if self.entry.data.nxerrors:
            result.errors = NXfield(err)
        return result

    def round(self, x, prec=2, base=.05):
        return round(base * round(float(x)/base), prec)

    def plot_data(self):
        self.convert_QE().plot()

    def save_data(self):
        self.entry['sqe'] = self.convert_QE()
