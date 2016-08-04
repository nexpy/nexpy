import numpy as np
from nexpy.gui.datadialogs import BaseDialog, GridParameters
from nexpy.gui.utils import report_error
from nexusformat.nexus import NeXusError


def show_dialog(parent=None):
    try:
        dialog = EnergyDialog()
        dialog.show()
    except NeXusError as error:
        report_error("Getting Incident Energy", error)
        

class EnergyDialog(BaseDialog):

    def __init__(self, parent=None):

        super(EnergyDialog, self).__init__(parent)

        self.select_entry()
        self.parameters = GridParameters()
        self.parameters.add('m1', self.entry['monitor1/distance'], 
                            'Monitor 1 Distance')
        self.parameters.add('m2', self.entry['monitor2/distance'], 
                            'Monitor 2 Distance')
        self.parameters.add('Ei', self.entry['instrument/monochromator/energy'], 
                            'Incident Energy')
        self.parameters.add('mod', self.entry['instrument/source/distance'], 
                            'Moderator Distance')
        action_buttons = self.action_buttons(('Get Ei', self.get_ei))
        self.set_layout(self.entry_layout, self.parameters.grid(), 
                        action_buttons, self.close_buttons(save=True))
        self.set_title('Get Incident Energy')

        self.m1 = self.entry['monitor1']
        self.m2 = self.entry['monitor2'] 

    @property
    def m1_distance(self):
        return self.parameters['m1'].value - self.moderator_distance

    @property
    def m2_distance(self):
        return self.parameters['m2'].value - self.moderator_distance

    @property
    def Ei(self):
        return self.parameters['Ei'].value

    @property
    def moderator_distance(self):
        return self.parameters['mod'].value

    def get_ei(self):
        t = 2286.26 * self.m1_distance / np.sqrt(self.Ei)
        m1_time = self.m1[t-200.0:t+200.0].moment()
        t = 2286.26 * self.m2_distance / np.sqrt(self.Ei)
        m2_time = self.m2[t-200.0:t+200.0].moment()
        self.parameters['Ei'].value = (2286.26 * (self.m2_distance - self.m1_distance) /
                                       (m2_time - m1_time))**2

    def accept(self):
        try:
            self.parameters['Ei'].save()
        except NeXusError as error:
            report_error("Getting Incident Energy", error)
        super(EnergyDialog, self).accept()
