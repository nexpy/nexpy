import numpy as np

from lmfit.model import Model

class CriticalExponentModel(Model):
    r"""A model to describe the power-law temperature dependence of a
    property above a phase transition with three Parameters: ``amplitude``, 
    ``Tc``, and ``nu``.

    .. math::

        f(x; A, Tc, \nu) = A ((Tc - x[x>Tc])/ Tc)^\nu

    where the parameter ``amplitude`` corresponds to :math:`A`, ``Tc`` to 
    :math:`Tc`, and ``nu`` to :math:`\nu`. 

    """
    def __init__(self, **kwargs):

        def op(x, amplitude=1.0, Tc=100.0, nu=0.5):
            v = np.zeros(x.shape)
            v[x>Tc] = amplitude * ((x[x>Tc] - Tc)/ Tc)**nu
            v[x<=Tc] = 0.0
            return v

        super().__init__(op, **kwargs)

    def guess(self, data, x=None, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        return self.make_params(amplitude=data.max(), Tc=x.min(), nu=0.5)
