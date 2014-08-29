from PySide import QtGui
import numpy as np
from nexpy.gui.datadialogs import BaseDialog
from nexpy.gui.mainwindow import report_error
from nexpy.api.nexus import NeXusError


def show_dialog(parent=None):
    try:
        dialog = EnergyDialog(parent)
        dialog.show()
    except NeXusError as error:
        report_error("Getting Incident Energy", error)
        

class EnergyDialog(BaseDialog):

    def __init__(self, parent=None):
        super(EnergyDialog, self).__init__(parent)
        node = self.get_node()
        self.root = node.nxroot
        if self.root.nxfilemode == 'r':
            raise NeXusError('NeXus file opened as readonly')
        layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        grid.setSpacing(10)
        self.m1_box = QtGui.QLineEdit()
        self.m2_box = QtGui.QLineEdit()
        self.ei_box = QtGui.QLineEdit()
        self.mod_box = QtGui.QLineEdit()
        grid.addWidget(QtGui.QLabel('Monitor 1 Distance:'), 0, 0)
        grid.addWidget(QtGui.QLabel('Monitor 2 Distance:'), 1, 0)
        grid.addWidget(QtGui.QLabel('Incident Energy:'), 2, 0)
        grid.addWidget(QtGui.QLabel('Moderator Distance:'), 3, 0)
        grid.addWidget(self.m1_box, 0, 1)
        grid.addWidget(self.m2_box, 1, 1)
        grid.addWidget(self.ei_box, 2, 1)
        grid.addWidget(self.mod_box, 3, 1)
        layout.addLayout(grid)
        get_button = QtGui.QPushButton('Get Ei')
        get_button.clicked.connect(self.get_ei)
        layout.addWidget(get_button)
        layout.addWidget(self.buttonbox(save=True))
        self.setLayout(layout)
        self.setWindowTitle('Get Incident Energy')

        self.m1 = self.root['entry/monitor1']
        self.m2 = self.root['entry/monitor2'] 
        self.m1_box.setText(str(self.read_parameter(self.root,
                            'entry/monitor1/distance')))
        self.m2_box.setText(str(self.read_parameter(self.root,
                            'entry/monitor2/distance')))
        self.ei_box.setText(str(self.read_parameter(self.root,
                            'entry/instrument/monochromator/energy')))
        self.mod_box.setText(str(self.read_parameter(self.root,
                             'entry/instrument/source/distance')))

    @property
    def m1_distance(self):
        return np.float32(self.m1_box.text()) - self.moderator_distance

    @property
    def m2_distance(self):
        return np.float32(self.m2_box.text()) - self.moderator_distance

    @property
    def Ei(self):
        return np.float32(self.ei_box.text())

    @property
    def moderator_distance(self):
        return np.float32(self.mod_box.text())

    def get_ei(self):
        t = 2286.26 * self.m1_distance / np.sqrt(self.Ei)
        m1_time = self.m1[t-200.0:t+200.0].moment()
        t = 2286.26 * self.m2_distance / np.sqrt(self.Ei)
        m2_time = self.m2[t-200.0:t+200.0].moment()
        self.ei_box.setText(str((2286.26 * (self.m2_distance - self.m1_distance) /
                                   (m2_time - m1_time))**2))

    def accept(self):
        try:
            self.root['entry/instrument/monochromator/energy'] = self.Ei
        except NeXusError as error:
            report_error("Getting Incident Energy", error)
        super(EnergyDialog, self).accept()
