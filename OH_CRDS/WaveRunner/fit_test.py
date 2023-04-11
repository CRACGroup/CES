import numpy as np
from scipy.optimize import least_squares
import matplotlib.pyplot as plt

waveform = np.load('.\\testdata\\waveform.npy')
times = np.linspace(-5e-6,45e-6,5002)

ts = times[600:-1]
ys = waveform[600:]

def fun(x,t,y):
    return x[0] + x[1]*np.exp(x[2]*t)-y

def gendata(t,a,b,c):
    y=a+b*np.exp(t*c)
    return y

x0 = np.array([0,2,-5])

res_log = least_squares(fun,x0,ftol=1e-12,xtol=1e-12,gtol=1e-12,
                        loss='cauchy',f_scale=0.1,args=(ts,ys))

print(res_log)

ttest = np.linspace(0,45e-6,150)
y_log = gendata(ttest,*res_log.x)

plt.plot(times[:-1],waveform,'-k',alpha=0.75)
plt.plot(ttest,y_log,'-r')
plt.show()
