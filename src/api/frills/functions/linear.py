import numpy as np

function_name = 'Linear'
parameters = ['Constant', 'Slope']

def values(x, p):
    constant, slope = p
    return constant + slope*x
