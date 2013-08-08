import numpy as np

function_name = 'Gaussian'
parameters = ['Integral', 'Sigma', 'Center']

factor = np.sqrt(2*np.pi)

def values(x, p):
    integral, sigma, center = p
    return integral * np.exp(-(x-center)**2/(2*sigma**2)) / (sigma * factor)

def guess(x, y):
    center = (x*y).sum()/y.sum()
    sigma = np.sqrt(((x-center)**2*y).sum()/y.sum())
    integral = y.max() * sigma * factor
    return integral, sigma, center
