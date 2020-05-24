import numpy as np

from lmfit.model import Model

class OrderParameterModel(Model):
    r"""A model to describe the temperature dependence of an order parameter
    with three Parameters: ``amplitude``, ``Tc``, and ``beta``.

    .. math::

        f(x; A, Tc, \beta) = A ((Tc - x[x<Tc])/ Tc)^\beta

    where the parameter ``amplitude`` corresponds to :math:`A`, ``Tc`` to 
    :math:`Tc`, and ``beta`` to :math:`\beta`. 

    """
    def __init__(self, **kwargs):

        def op(x, amplitude=1.0, Tc=100.0, beta=0.5):
            v = np.zeros(x.shape)
            v[x<Tc] = amplitude * ((Tc - x[x<Tc])/ Tc)**beta
            v[x>=Tc] = 0.0
            return v

        super().__init__(op, **kwargs)

    def guess(self, data, x=None, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        return self.make_params(amplitude=data.max(), Tc=x.mean(), beta=0.33)
