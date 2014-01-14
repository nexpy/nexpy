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

function_name = 'Lorentzian'
parameters = ['Integral', 'Gamma', 'Center']

def values(x, p):
    integral, gamma, center = p
    return integral * (gamma/np.pi) / ((x-center)**2 + gamma**2)

def guess(x, y):
    center = (x*y).sum()/y.sum()
    gamma = np.sqrt(np.fabs(((x-center)**2*y).sum()/y.sum()))
    integral = y.max() * np.pi * gamma
    return integral, gamma, center
