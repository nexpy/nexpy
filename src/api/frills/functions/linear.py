import numpy as np

function_name = 'Linear'
parameters = ['Constant', 'Slope']

def values(x, p):
    constant, slope = p
    return constant + slope*x

def guess(x, y):
    slope = (y[-1]-y[0]) / (x[-1]-x[0])
    constant = y[0] - slope*x[0]
    return constant, slope
