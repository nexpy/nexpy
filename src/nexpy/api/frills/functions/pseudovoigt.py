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
parameters = ['Integral', 'Gamma', 'Sigma', 'Center']

integral_factor = np.sqrt(2*np.pi)
sigma_factor = np.sqrt(2*np.log(2))

def values(x, p):
    integral, gamma, sigma, center = p
    GammaG = sigma_factor * sigma
    GammaL = 2 * gamma
    FWHM = (GammaG**5 + 
            2.69269 * GammaG**4 * GammaL + 
            2.42843 * GammaG**3 * GammaL**2 + 
            4.47163 * GammaG**2 + GammaL**3 +
            0.07842 * GammaG**4 * GammaL +
            GammaL**5)**(0.2)
    ratio = GammaL / FWHM
    fraction = 1.36603 * ratio - 0.47719 * ratio**2 + 0.11116 * ratio**3
    return integral * ((1-fraction)*gauss(x, center, sigma) +
                       fraction*lorentz(x, center, gamma))

def guess(x, y):
    center = (x*y).sum()/y.sum()
    gamma = np.sqrt(abs(((x-center)**2*y).sum()/y.sum())) / 2.0
    sigma = gamma
    integral = y.max() * np.pi * gamma
    return integral, gamma, sigma, center

def gauss(x, center, sigma):
    return np.exp(-(x-center)**2/(2*sigma**2)) / (sigma * integral_factor)

def lorentz(x, center, gamma):
    return (gamma / np.pi) / ((x - center) ** 2 + gamma ** 2)
