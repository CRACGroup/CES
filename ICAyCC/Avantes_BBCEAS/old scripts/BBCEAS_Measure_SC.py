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

### Instrument
accums = conf.accums                    # Accumulations
checkrate = conf.checkrate              # Query freq. to check if ready (calls per itime)
samples = conf.samples                  # Number of accumulated measurements
itime = conf.itime                      # Integration time in ms
averages = conf.averages                # Number of integrations to average 

### Signal analysis
# Cavity parameters
distance = conf.distance                # Sample optical length

# Resonance window 
lower_wavelength=conf.lower_wavelength  # Starting wavelength of resonance window
upper_wavelength=conf.upper_wavelength  # Ending wavelength of resonance window

# Reference and background files
back_filename = conf.back_filename
no2_refname = conf.no2_refname
chocho_refname = conf.chocho_refname

# Reff : Either number or np.load(Reff_matrix)
Reff= conf.Reff

#########################################################################################
### Reference and Background file loading for analisis                                ###
no2reference = np.load(no2_refname)
chochoref = np.load(chocho_refname)
background = np.load(back_filename)

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
wavelengths = []
ret = av.AVS_GetLambda(handle,wavelengths)
for pixel in range(pixels):
    wavelengths.append(ret[pixel])
    
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
ax1 = fig.add_subplot(211)      # Axes 1 : Signal
ax2 = fig.add_subplot(212)      # Axes 2 : Concentration NO2
ax3 = ax2.twinx()               # Axes 3 : Concentration CHOCHO

t0=dt.datetime.now()            # Start time

# Initializing timestamp and concentration list, and measurement array
measurements = np.array(wavelengths).reshape(len(wavelengths),1)
meastime = np.zeros(samples,dtype='U19')
meastime2 = []
ppbs = np.zeros(samples)
ppbs2 = np.zeros(samples)
area = np.zeros(samples)

for n in range(samples):        # Sample loop
    print("Measurement number: ", n+1)
    counts = np.zeros(len(wavelengths))

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
        spectra = np.array(ret[1][0:len(wavelengths)])
        counts = np.add(counts,spectra) 
    
    ### Calculating number density
    sample = np.copy(counts.reshape(len(counts),1))
    minwave,maxwave = cf.segment_indices(measurements[:,0:2],lower_wavelength,
            upper_wavelength)
    bckg = np.copy(background[minwave:maxwave,:])
    no2ref = np.copy(no2reference[minwave:maxwave,:])
    glyref = np.copy(chochoref[minwave:maxwave,:])
    I_sample = np.copy(sample[minwave:maxwave,:])
    I_0 = np.average(bckg[:,1:],axis=1).reshape(len(bckg),1)
    
    ### This one does everything (see recursive_fit_2ref function in CESfunctions.py)
    alpha,fl,a,b,ndensity1, ndensity2 = cf.fit_alg_1(I_sample, I_0, Reff, distance, 
            no2ref,glyref,parameters=1)
    
    ### The timestamp for this measurement is now
    timenow = dt.datetime.now()
    stamp = timenow.strftime('%y%m%d%H%M%S')
    meastime2.append(timenow)

    ### Add sample to measurements array and save individual sample datafile
    measurements = np.concatenate((measurements,counts.reshape(len(counts),1)),axis=1)
    
    np.savetxt(path_file+'Is'+stamp+'.txt',measurements[:,[0,n+1]],fmt='%s')

    ### Populate ppbs and meastime arrays with currents sample, make/overwrite datafile
    ppbs[n] = ndensity1/2.5e10
    ppbs2[n] = ndensity2/2.5e10
    meastime[n] = timenow.strftime('%Y/%m/%d-%H:%M:%S')
    area[n] = np.trapz(counts[minwave:maxwave+1])
       
    np.savetxt(path_file+'Mtemp.txt',np.column_stack((meastime[:n+1],ppbs[:n+1],
        ppbs2[:n+1],area[:n+1])), fmt='%s')

    # Print calculated NO2 in ppb
    print('NO2 ppb: ', ppbs[n], 'CHOCHO ppb: ', ppbs2[n])
          
    ### Plotting
    ax1.cla()
    ax2.cla()
    ax3.cla()
    ax1.plot(wavelengths[minwave:maxwave],alpha,'-k')
    ax1.plot(wavelengths[minwave:maxwave],a+b*fl+no2ref[:,1]*ndensity1+glyref[:,1]*ndensity2,'-b')
    ax2.plot(meastime2[:n+1],ppbs[:n+1],'-g')
    ax3.plot(meastime2[:n+1],ppbs2[:n+1],'-b',alpha=0.5)
    ax2.xaxis.set_major_formatter(DateFormatter("%H:%M"))
    fig.canvas.draw()
    fig.canvas.flush_events()
   

t1=dt.datetime.now()            # End time

# We save all measurements in a numpy file
np.save(path_file + "Isamples" + t1.strftime("%y%m%d%H%M"), measurements)

# We save all concentrations in a datafile
np.savetxt(path_file + "M" + t1.strftime('%y%m%d%H%M') + '.txt',
        np.column_stack((meastime,ppbs,ppbs2,area)), fmt='%s')


print("Seconds elapsed: ",(t1-t0).total_seconds())
print("Shape of measurements array: ",measurements.shape)
print("EOF")
