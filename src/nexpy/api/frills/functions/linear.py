#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
function_name = 'Linear'
parameters = ['Constant', 'Slope']

def values(x, p):
    constant, slope = p
    return constant + slope*x

def guess(x, y):
    slope = (y[-1]-y[0]) / (x[-1]-x[0])
    constant = y[0] - slope*x[0]
    return constant, slope
