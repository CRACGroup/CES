###################################################################################################
# DAQ POLLING SCRIPT FOR ADVANTECH MIC1816
# 
# This script uses the proprietary Advantech Python libraries that are installed in the MIC1816
# and included here as a modified script imported as ait
# 
# Not much development here as the DAQ's sampling rate is too low for CRDS, but this template
# allows for the use of the Advantech's DAQ to get Buffered Analog Inputs with a trigger signal
# as a delayed stop (i.e. it samples a buffer for a certain amount of points after the trigger and
# stops)
# Modified by Mixtli Campos on 30/03/2023

import sys
sys.path.append('.')
import matplotlib.pyplot as plt
import matplotlib.animation as animation

from AI_PollingOneBufferedAI_TDtp import AI_PollingOneBufferedAI_TDtp_dev as ait
from Automation.BDaq import *
from Automation.BDaq.WaveformAiCtrl import WaveformAiCtrl
from Automation.BDaq.BDaqApi import AdxEnumToString, BioFailed

# Configure the following parameters before running the demo
deviceDescription = "MIC-1816,BID#15"
profilePath = u"c:\\DAQPython\\MIC1816.xml"
startChannel = 0
channelCount = 1
sectionLength = 1024
sectionCount = 1

# user buffer size should be equal or greater than raw data buffer length, because data ready count
# is equal or more than smallest section of raw data buffer and up to raw data buffer length.
# users can set 'USER_BUFFER_SIZE' according to demand.
USER_BUFFER_SIZE = channelCount * sectionLength * sectionCount

# Set trigger parameters
triggerAction = TriggerAction.DelayToStop
triggerEdge = ActiveSignal.RisingEdge
triggerDelayCount = 475
triggerLevel = 0.1

# Set trigger1 parameters
trigger1Action = TriggerAction.DelayToStop
trigger1Edge = ActiveSignal.RisingEdge
trigger1DelayCount = 1000
trigger1Level = 2.0

# set which trigger be used for this demo, trigger0(0) or trigger1(1)
triggerUsed = 0

#####
fig = plt.figure()
ax1 = fig.add_subplot(111)
x_len = 100
xs = list(range(0,x_len))
ys = [0]*x_len
line, = ax1.plot(xs,ys,'-k')

def animate(i):
    scan = ait.AdvPollingOneBufferedAI_TDtp()
    dataset = scan[500:600]
    ax1.set_ylim([min(dataset)-.05,max(dataset)+.05])
    line.set_ydata(dataset)

    return line,

ani = animation.FuncAnimation(fig,animate,interval=1,blit=True,cache_frame_data=False)
plt.show()

#####

