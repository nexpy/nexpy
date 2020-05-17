import numpy as np

from lmfit.model import Model

class OrderParameterModel(Model):
    """A model to describe the temperature dependence of an order parameter
    with three Parameters: ``op``, ``Tc``, and ``beta``.
    """
    def __init__(self, **kwargs):

        def op(x, op=1.0, Tc=100.0, beta=0.33):
            beta = 2. * beta
            v = np.zeros(x.shape)
            v[x<Tc] = op * ((Tc - x[x<Tc])/ Tc)**beta
            v[x>=Tc] = 0.0
            return v

        super().__init__(op, **kwargs)

    def guess(self, data, x=None, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        return self.make_params(op=data.max(), Tc=x.mean(), beta=0.33)
