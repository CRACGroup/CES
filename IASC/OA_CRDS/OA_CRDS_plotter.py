#########################################################################################
# Plotter companion to the IBBCEAS scripts, meant to run as a subprocess
# so that the FuncAnimation() GUI takeover does not freeze the system while
# waiting for the camera bring the arrays.
#
#
#
#
#

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from time import sleep
from matplotlib.dates import DateFormatter

fig = plt.figure(figsize=(6,6))
gs = fig.add_gridspec(3,1)
ax1 = fig.add_subplot(gs[:-1,:])
ax2 = fig.add_subplot(gs[-1,:])

x=np.arange(550)
y=[0]*x

line1, = ax1.plot(x,y)
line2, = ax1.plot(x,y)
line3, = ax2.plot(x,y)
def init_func():
    return line1, line2, line3,

def animate(i):
    try:
        ax1data = np.load("ax1data.npy")
        ax1adata= np.load("ax1adata.npy")
        ax1.clear()
        line1, = ax1.plot(ax1data[:,0],ax1data[:,1],'-k')
        line2, = ax1.plot(ax1adata[:,0],ax1adata[:,1],'-g')
        ax2data = np.load("ax2data.npy")
        ax2.clear()
        line3, = ax2.plot(ax2data[:,0],ax2data[:,1],'-r')
        ax1.set_ylabel('Voltage')
        ax2.set_xlabel('$\mu$s')
        ax2.set_ylabel('Residual')
        ax1.grid()
        ax2.grid()
    except:
        ax1.clear()
        line1, = ax1.plot(x,y)
        line2, = ax1.plot(x,y)
        ax2.clear()
        line3, = ax2.plot(x,y)
        pass

    return line1, line2, line3,

ani = animation.FuncAnimation(fig,animate,init_func=init_func,
        interval=1000,blit=False,cache_frame_data=False)
plt.show()

with open('endme', 'w') as f:
    f.write('EndMe!')
