from __future__ import absolute_import
from . import get_ei, convert_qe

def plugin_menu():
    menu = 'Chopper'
    actions = []
    actions.append(('Get Incident Energy', get_ei.show_dialog))
    actions.append(('Convert to Q-E', convert_qe.show_dialog))
    return menu, actions
