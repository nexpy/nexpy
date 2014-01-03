#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Copyright (c) 2013, NeXpy Development Team.
#
# Distributed under the terms of the Modified BSD License.
#
# The full license is in the file COPYING, distributed with this software.
#-----------------------------------------------------------------------------

import os, getopt, glob, re, sys, timeit
import numpy as np
from nexpy.api.nexus import *
from nexpy.readers.tifffile import tifffile as TIFF

def get_prefixes(directory):
    prefixes = []
    for file in os.listdir(directory):
        f=file.split(os.path.extsep)[0]
        match = re.match('(.*?)([0-9]+)$', f)
        if match:
            prefixes.append(match.group(1).strip('-').strip('_'))
    return set(prefixes)

def get_files(directory, prefix, extension):
    if not extension.startswith('.'):
        extension = '.'+extension
    filenames = glob.glob(os.path.join(directory, prefix+'*'+extension))
    return sorted(filenames,key=natural_sort)

def open_nexus_file(directory, prefix, filenames):
    v0 = TIFF.imread(filenames[0])
    x = NXfield(range(v0.shape[1]), dtype=np.uint16, name='x')
    y = NXfield(range(v0.shape[0]), dtype=np.uint16, name='y')
    z = NXfield(range(1,len(filenames)+1), dtype=np.uint16, name='z')
    v = NXfield(name='v',shape=(len(filenames),v0.shape[0],v0.shape[1]),
                dtype=v0.dtype)
    data = NXdata(v, (z,y,x))
    nexus_file = os.path.join(directory, prefix+'.nxs')
    nexus_root = NXroot(NXentry(data)).save(nexus_file)
    return nexus_root

def write_data(nexus_root, filenames):
    for i in range(len(filenames)):
        nexus_root.entry.data.v[i,:,:] = TIFF.imread(filenames[i])

def natural_sort(key):
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r'(\d+)', key)]    


if __name__=="__main__":
    try:
        opts, args = getopt.getopt(sys.argv[1:],"hd:e:p:",["directory=","ext=","prefix="])
    except getopt.GetoptError:
        print 'merge_tiffs -d <directory> -e <extension> -p <prefix>'
        sys.exit(2)
    directory = './'
    extension = 'tif'
    prefix = None
    first = None
    last = None
    for opt, arg in opts:
        if opt == '-h':
            print 'merge_tiffs -d <directory> -e <extension> -p <prefix>'
            sys.exit()
        elif opt in ('-p', '--prefix'):
            prefix = arg
        elif opt in ('-d', '--directory'):
            directory = arg
        elif opt in ('-e', '--extension'):
            extension = arg
        elif opt == '-f':
            first = arg
        elif opt == '-l':
            last = arg
    if prefix:
        prefixes = [prefix]
    else:
        prefixes = get_prefixes(directory)
    for prefix in prefixes:
        filenames = get_files(directory, prefix, extension)
        nexus_root = open_nexus_file(directory, prefix, filenames)
        tic=timeit.default_timer()
        write_data(nexus_root, filenames)
        toc=timeit.default_timer()
        print toc-tic, 'seconds for', '%s.nxs' % prefix 
