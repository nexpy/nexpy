import numpy as np

function_name = 'Gaussian'
parameters = ['Height', 'Sigma', 'Center']

def values(x, p):
    height, sigma, center = p
    return height * np.exp(-(x-center)**2/(2*sigma**2))
