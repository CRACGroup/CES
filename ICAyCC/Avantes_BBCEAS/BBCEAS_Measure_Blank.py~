import os
import time
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import scipy.signal as scs
from matplotlib.dates import DateFormatter
import configurations as conf
import CESfunctions as cf
import avaspec as av

#########################################################################################
### USER CONFIGURATION (from configuration file)                                      ###

accums = conf.accums                    # Accumulations
checkrate = conf.checkrate              # Query freq. to check if ready (calls per itime)
samples = conf.samples_blank            # Number of accumulated measurements
itime = conf.itime                      # Integration time in ms
averages = conf.averages                # Number of integrations to average 

#########################################################################################
### Making a subdirectory for generated files %Y%m%d                                  ###

parent = '.'
directory = dt.datetime.now().strftime('%Y%m%d')
path = os.path.join(parent,directory)   # path of the folder wherein to store data

# Tries to make a new folder with the current date, does nothing if folder already
# exists

try:
    os.mkdir(path)
except:
    pass

path_file = path + conf.folder_symbol   # full path to append filename when writing

#########################################################################################
### Instrument initialization                                                         ###

av.AVS_Init(0) 

ret = av.AVS_GetNrOfDevices()
req = 75*ret
a_pList = av.AvsIdentityType * ret 
retn=av.AVS_GetList(req,req,a_pList)
handle = av.AVS_Activate(retn[1])

config = av.DeviceConfigType
ret = av.AVS_GetParameter(handle, 63484, 63484, config)
pixels = ret[1].m_Detector_m_NrPixels

#########################################################################################
### Calculating the wavelengths with the calibration factors from configuration file  ###

wavelengths = cf.avantes_calibrator(pixels,*conf.calfactors)

#########################################################################################
### Configurations                                                                    ###

measconfig = av.MeasConfigType 
measconfig.m_StartPixel = 0 
measconfig.m_StopPixel = pixels - 1 
measconfig.m_IntegrationTime = itime 
measconfig.m_IntegrationDelay = 0 
measconfig.m_NrAverages = averages 
measconfig.m_CorDynDark_m_Enable = 0 
measconfig.m_CorDynDark_m_ForgetPercentage = 100 
measconfig.m_Smoothing_m_SmoothPix = 0 
measconfig.m_Smoothing_m_SmoothModel = 0 
measconfig.m_SaturationDetection = 0 
measconfig.m_Trigger_m_Mode = 0 
measconfig.m_Trigger_m_Source = 0 
measconfig.m_Trigger_m_SourceType = 0 
measconfig.m_Control_m_StrobeControl = 0 
measconfig.m_Control_m_LaserDelay = 0 
measconfig.m_Control_m_LaserWidth = 0 
measconfig.m_Control_m_LaserWaveLength = 0.0 
measconfig.m_Control_m_StoreToRam = 0

#########################################################################################
### Instrument Preparation for Measurements                                           ###

av.AVS_PrepareMeasure(handle, measconfig)
scans = 1                       # Number of scans (only last is recorded)

#########################################################################################
### LOOPS for accumulations and sample logging                                        ###

plt.ion()                       # Interactive plot
fig = plt.figure()              # Figure initialization
ax1 = fig.add_subplot(111)      # Axes 1: Signal

t0=dt.datetime.now()            # Start time

# Initializing measurements array
measurements = np.copy(wavelengths)

for n in range(samples):        # Sample loop
    print("Measurement number: ", n+1)
    counts = np.zeros(pixels)

    for i in range(accums):     # Accumulations loop
        #print(i+1)
        av.AVS_Measure(handle, 0, scans)

        ### Query instrument ready
        dataready = False
        while not dataready:
            time.sleep(measconfig.m_IntegrationTime/(checkrate*1000))
            dataready = av.AVS_PollScan(handle)

        ### Get data and accumulate
        timestamp = 0
        spectraldata = []
        ret = av.AVS_GetScopeData(handle, timestamp, spectraldata)
        timestamp = ret[0]
        spectra = np.array(ret[1][0:pixels])
        counts = np.add(counts,spectra) 
    
    ### Plotting
    ax1.cla()
    ax1.plot(wavelengths[:,0],counts)
    fig.canvas.draw()
    fig.canvas.flush_events()

    ### Measurements array
    measurements = np.concatenate((measurements,counts.reshape(len(counts),1)),axis=1)

t1=dt.datetime.now()            # End time

# we generate a name to save the background 
blank_archive = "Ib" + t1.strftime("%y%m%d%H%M") +".txt"

np.save("background", measurements)     # for use by BBCEAS_Measure
np.savetxt(path_file + blank_archive, measurements)    # for archiving (further analysis)

print("Seconds elapsed: ",(t1-t0).total_seconds())
print("Shape of measurements array: ",measurements.shape)
print("EOF")
