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

fig = plt.figure(figsize=(15,6))
gs = fig.add_gridspec(3,3)
ax1 = fig.add_subplot(gs[:-1,0])
ax2 = fig.add_subplit(gs[-1,0])
ax3 = fig.add_subplot(gs[:-1,1])
ax4 = fig.add_subplot(gs[-1,-1])
ax5 = fig.add_subplot(gs[:-1,2])
ax6 = fig.add_subplot(gs[-1,2])

x=np.arange(1024)
y=[0]*x

line1, = ax1.plot(x,y)
line1a, = ax1.plot(x,y)
line2, = ax2.plot(x,y)
line3, = ax3.plot(x,y)
line3a, = ax3.plot(x,y)
line4, = ax4.plot(x,y)
line5, = ax5.plot(x,y)
line6, = ax6.plot(x,y)

def init_func():
    return line1, line1a, line2, line3, line3a, line4, line5, line6,

def animate(i):
    try:
        ax5data = np.load("ax5data.npy")
        ax5.clear()
        line5, = ax5.plot(ax5data[:,0],ax5data[:,1],'-k')
        ax5.set_title('Background')
        ax5.grid()
    except:
        ax5.clear()
        line5, = ax5.plot(x,y)
        pass

    try:
        ax1data = np.load("ax1data.npy")
        ax1adata = np.load("ax1adata.npy")
        ax2data = np.load("ax2data.npy")
        ax6data = np.load("ax6data.npy",allow_pickle=True)
        ax1.clear()
        ax2.clear()
        ax6.clear()
        line1, = ax1.plot(ax1data[:,0],ax1data[:,1],'-k')
        line1a, = ax1.plot(ax1adata[:,0],ax1adata[:,1],'-g')
        line2, = ax2.plot(ax2data[:,0],ax2data[:,1],'-r')
        line6, = ax6.plot(ax6data[:,0],ax6data[:,1],'-b')
        ax1.set_title('Zero')
        ax2.set_xlabel('$\mu$s')
        ax6.set_xlabel('Time')
        ax6.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        ax1.grid()
        ax2.grid()
        ax6.grid()

    except:
        ax1.clear()
        ax2.clear()
        ax6.clear()
        line1, = ax1.plot(x,y)
        line1a, = ax1.plot(x,y)
        line2, = ax2.plot(x,y)
        line6, = ax6.plot(x,y)
        pass

    try:
        ax3data = np.load("ax3data.npy")
        ax3adata = np.load("ax3adata.npy")
        ax4data = np.load("ax4data.npy")
        ax6data = np.load("ax6data.npy",allow_pickle=True)
        ax3.clear()
        ax4.clear()
        ax6.clear()
        line3, = ax3.plot(ax2data[:,0],ax2data[:,1],'-k')
        line3a, = ax3.plot(ax3adata[:,0],ax3adata[:,1],'-g')
        line4, = ax4.plot(ax4data[:,0],ax4data[:,1],'-r')
        line6, = ax6.plot(ax6data[:,0],ax6data[:,1],'-b')
        ax3.set_title('Measurement')
        ax4.set_xlabel('$\mu$s')
        ax6.set_xlabel('Time')
        ax6.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        ax3.grid()
        ax4.grid()
        ax6.grid()

    except:
        ax3.clear()
        ax4.clear()
        ax6.clear()
        line3, = ax3.plot(x,y)
        line3a, = ax3.plot(x,y)
        line4, = ax4.plot(x,y)
        line6, = ax6.plot(x,y)
        pass

    return line1, line1a, line2, line3, line3a, line4, line5, line6,

ani = animation.FuncAnimation(fig,animate,init_func=init_func,
        interval=1000,blit=False,cache_frame_data=False)
plt.show()

#with open('endme', 'w') as f:
#    f.write('EndMe!')
