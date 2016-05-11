x=np.linspace(0,2.*np.pi,101)
y=x
X,Y=np.meshgrid(x,y)
z=np.sin(X)*np.sin(Y)

entry=NXentry()
entry.data=NXdata(z,(y,x))
print(entry.tree)
entry.plot()
nxtree.example=NXroot(entry)
