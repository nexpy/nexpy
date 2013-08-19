import numpy as np

function_name = 'Lorentzian'
parameters = ['Integral', 'Gamma', 'Center']

def values(x, p):
    integral, gamma, center = p
    return integral * (gamma/np.pi) / ((x-center)**2 + gamma**2)

def guess(x, y):
    center = (x*y).sum()/y.sum()
    gamma = np.sqrt(abs(((x-center)**2*y).sum()/y.sum()))
    integral = y.max() * np.pi * gamma
    return integral, gamma, center
