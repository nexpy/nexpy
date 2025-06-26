import numpy as np
from lmfit.model import Model


class PDFdecayModel(Model):
    r"""A model to describe the product of a decaying exponential and a
    Gaussian with three parameters: ``amplitude``, ``xi``, and ``sigma``

    .. math::

        f(x; A, \xi, \sigma) = A e^{[-{|x|}/\xi]} e^{[{-{x^2}/{{2\sigma}^2}}]}

    where the parameter ``amplitude`` corresponds to :math:`A`, ``xi`` to
    :math:`\xi`, and ``sigma`` to :math:`\sigma`.

    """

    def __init__(self, **kwargs):

        def pdfdecay(x, amplitude=1.0, xi=1.0, sigma=1.0):
            return amplitude * np.exp(-abs(x)/xi) * np.exp(-x**2/(2*sigma**2))

        super().__init__(pdfdecay, **kwargs)

    def guess(self, data, x=None, negative=False, **kwargs):
        """Estimate initial model parameter values from data."""
        sigma = np.sqrt(np.fabs((x**2*data).sum() / data.sum()))
        return self.make_params(amplitude=data.max(), xi=sigma, sigma=sigma)
