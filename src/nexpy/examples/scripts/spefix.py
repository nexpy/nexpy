import numpy as np

from nexpy.api.frills.fit import Fit, Function, Parameter
from nexpy.api.frills.functions import gaussian, linear
from nexusformat.nexus import NXentry, NXdata

def fix_spe(spe_file):

    entry = NXentry()
    entry.title = spe_file.nxname
    entry.incident_energy = spe_file['data/NXSPE_info/fixed_energy']
    entry.data = spe_file.data.data
    entry.data.error.rename('errors')

    s = raw_input("Emin Emax Phimin Phimax dPhi: ")
    xmin, xmax, ymin, ymax, dy = [float(i) for i in s.split(' ')]    
    mfit(entry.data, xmin, xmax, ymin, ymax, dy)
    
    return entry

def mfit(data, xmin, xmax, ymin, ymax, dy):

    fs = [Function('Linear', linear), Function('Gaussian', gaussian)]
    x = np.linspace(xmin, xmax, 200)

    ylo, yhi = ymin, ymin+dy

    while yhi < ymax:

        slab = data[ylo:yhi,xmin:xmax]
        diff = slab.nxsignal.shape[0]
        cut = slab.sum([0])
        cut.plot()
    
        fit = Fit(cut, fs, use_errors=True)
    
        y = np.array(fit.y)
        for f in fs:
            f.guess_parameters(fit.x, y)
            y = y - f.function_values(fit.x)

        fit.fit_data()
    
        NXdata(fit.get_model(x), x).oplot('-')
    
        if raw_input('Keep? [y,N] ') == 'y':
            data[ylo:yhi,xmin:xmax] = slab - fit.get_model(f=fs[1]) / diff
        
        ylo = yhi
        yhi = ylo + dy
    
    return data

if __name__ == "__main__":
    nxtree.add(fix_spe(treeview.node))









