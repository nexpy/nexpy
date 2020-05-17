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

function_name = 'Gaussian'
parameters = ['Integral', 'Sigma', 'Center']

factor = np.sqrt(2*np.pi)

def values(x, p):
    integral, sigma, center = p
    return integral * np.exp(-(x-center)**2/(2*sigma**2)) / (sigma * factor)

def guess(x, y):
    center = (x*y).sum()/y.sum()
    sigma = np.sqrt(np.fabs(((x-center)**2*y).sum()/y.sum()))
    integral = y.max() * sigma * factor
    return integral, sigma, center
