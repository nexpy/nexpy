from . import convert_qe, get_ei


def plugin_menu():
    menu = 'Chopper'
    actions = []
    actions.append(('Get Incident Energy', get_ei.show_dialog))
    actions.append(('Convert to Q-E', convert_qe.show_dialog))
    return menu, actions
