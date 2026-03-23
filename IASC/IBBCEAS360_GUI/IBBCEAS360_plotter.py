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

fig = plt.figure(figsize=(8,6))
gs = fig.add_gridspec(2,2)
ax1 = fig.add_subplot(gs[0,0])
ax2 = fig.add_subplot(gs[0,1])
ax3 = fig.add_subplot(gs[1,:])
ax4 = ax3.twinx()

x=np.arange(1024)
y=[0]*x

line1, = ax1.plot(x,y)
line2, = ax2.plot(x,y)
line3, = ax2.plot(x,y)
line4, = ax3.plot(x,y)
line5, = ax4.plot(x,y)

def init_func():
    return line1, line2, line3, line4, line5,

def animate(i):
    try:
        ax1data = np.load("ax1data.npy")
        ax1.clear()
        line1, = ax1.plot(ax1data[:,0],ax1data[:,1],'-k')
        ax1.set_title('Zero')
    except:
        ax1.clear()
        line1, = ax1.plot(x,y)
        pass
   
    try:
        ax2data = np.load("ax2data.npy")
        ax2adata= np.load("ax2adata.npy")
        ax3data = np.load("ax3data.npy",allow_pickle=True)
        ax4data = np.load("ax4data.npy",allow_pickle=True)
        ax2.clear()
        line2, = ax2.plot(ax2data[:,0],ax2data[:,1],'-k')
        line3, = ax2.plot(ax2adata[:,0],ax2adata[:,1],'-r')
        ax3.clear()
        ax4.clear()
        line4, = ax3.plot(ax3data[:,0],ax3data[:,1],'-b')
        line5, = ax4.plot(ax4data[:,0],ax4data[:,1],'-g')
        ax3.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        ax4.spines['right'].set_color('green')
        ax4.tick_params(axis='y', colors='green')
        ax2.set_title('extinction')
        ax3.set_xlabel('Time [hr:min]')
        ax3.set_ylabel('NO$_2$ [ppbv]')
        ax4.yaxis.set_label_position('right')
        ax4.yaxis.label.set_color('green')
        ax4.set_ylabel('HONO [ppbv]')


    except:
        ax2.clear()
        line2, = ax2.plot(x,y)
        line3, = ax2.plot(x,y)
        ax3.clear()
        ax4.clear()
        line4, = ax3.plot(x,y)
        line5, = ax4.plot(x,y)
        pass

    return line1, line2, line3, line4, line5,

ani = animation.FuncAnimation(fig,animate,init_func=init_func,
        interval=1000,blit=False,cache_frame_data=False)
plt.show()

with open('endme', 'w') as f:
    f.write('EndMe!')
