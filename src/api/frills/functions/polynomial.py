import numpy as np

function_name = 'Polynomial'
parameters = ['P0', 'P1', 'P2', 'P3', 'P4']

def values(x, p):
    p0, p1, p2, p3, p4 = p
    return p0 + p1*x + p2*x**2 + p3*x**3 + p4*x**5
