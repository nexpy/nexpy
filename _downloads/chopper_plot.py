phi=np.linspace(5.,95.,10)
chopper.entry.data[phi[0]:phi[0]+10].sum(0).plot(xmin=1900,xmax=2600)
for i in range(10):
    (chopper.entry.data[phi[i]:phi[i]+10].sum(0)+500*i).oplot()

