import numpy as np

function_name = 'Lorenzian'
parameters = ['Integral', 'Gamma', 'Center']

def values(x, p):
    integral, gamma, center = p
    return integral * (gamma/np.pi) / ((x-center)**2 + gamma**2)
