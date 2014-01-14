#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
import numpy as np

function_name = 'PseudoVoigt'
parameters = ['Integral', 'Gamma', 'Center', 'Fraction']

integral_factor = np.sqrt(2*np.pi)
sigma_factor = np.sqrt(2*np.log(2))

def values(x, p):
    integral, gamma, center, fraction = p
    sigma = gamma / sigma_factor
    return integral * ((1-fraction)*gauss(x, center, sigma) +
                       fraction*lorentz(x, center, gamma))

def guess(x, y):
    center = (x*y).sum()/y.sum()
    gamma = np.sqrt(abs(((x-center)**2*y).sum()/y.sum()))
    integral = y.max() * np.pi * gamma
    fraction = 0.5
    return integral, gamma, center, fraction

def gauss(x, center, sigma):
    return np.exp(-(x-center)**2/(2*sigma**2)) / (sigma * integral_factor)

def lorentz(x, center, gamma):
    return (gamma / np.pi) / ((x - center) ** 2 + gamma ** 2)