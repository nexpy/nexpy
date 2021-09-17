import numpy as np

from lmfit.lineshapes import thermal_distribution
from lmfit.model import Model

class BoseFactorModel(Model):
    r"""A model to describe the Bose temperature factor with one Parameter: 
    ``T``.

    .. math::

        f(x; T) = (x / (1 - exp[-x/kT]))

    assuming that x is defined as energy loss. This function should be used
    to multiply symmetric functions to produce a composite model that obeys 
    detailed balance, e.g., when multiplying a Lorentzian, the model returns 
    the correct form for quasi-elastic neutron scattering in both energy gain 
    and energy loss:
    
        .. math::

        f(\omega; T) = (n(\omega)+1) * \omega\ * L(\omega)

    """

    valid_forms = ('meV', 'THz', 'K')

    def __init__(self, form='meV', **kwargs):

        if form == 'meV':
            kB = 0.08617
        elif form == 'THz':
            kB = 0.02084
        else:
            kB = 1.0

        def bose(x, T=30.0):
            kT = kB * T
            return np.where(np.isclose(x, 0.0), kT, 
                            -x * thermal_distribution(x, kt=-kT))

        super().__init__(bose, **kwargs)
