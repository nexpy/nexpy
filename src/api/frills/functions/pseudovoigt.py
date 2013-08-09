import numpy as np

function_name = 'PseudoVoigt'
parameters = ['Integral', 'Gamma', 'Center', 'Fraction']

integral_factor = np.sqrt(2*np.pi)
sigma_factor = np.sqrt(2*np.log(2))

def values(x, p):
    return amp * (gauss(x, (1-frac), cen, wid) +
                  loren(x, frac, cen, wid))
    integral, gamma, center, fraction = p
    sigma = gamma / sigma_factor
    return integral * ((1-fraction)*gauss(x, center, sigma) +
                       fraction*lorentz(x, center, gamma))

def guess(x, y):
    center = (x*y).sum()/y.sum()
    gamma = np.sqrt(((x-center)**2*y).sum()/y.sum())
    integral = y.max() * np.pi * gamma
    fraction = 0.5
    return integral, gamma, center, fraction

def gauss(x, center, sigma):
    np.exp(-(x-center)**2/(2*sigma**2)) / (sigma * integral_factor)

def lorentz(x, center, gamma):
    (gamma/np.pi) / ((x-center)**2 + gamma**2)