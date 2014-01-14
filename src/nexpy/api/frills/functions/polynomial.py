#!/usr/bin/env python 
# -*- coding: utf-8 -*-

#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------
function_name = 'Polynomial'
parameters = ['P0', 'P1', 'P2', 'P3', 'P4']

def values(x, p):
    p0, p1, p2, p3, p4 = p
    return p0 + x*(p1 + x*(p2 + x*(p3 + x*p4)))

def guess(x, y):
    slope = (y[-1]-y[0]) / (x[-1]-x[0])
    constant = y[0] - slope*x[0]
    return constant, slope, 0.0, 0.0, 0.0
