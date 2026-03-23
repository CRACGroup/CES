#########################################################################################
# This script configures the Newton CCD plugged via USB                                 #
# to take FVB single scans or accumulations for real time trace gas                     #
# concentration analysis using SVD.                                                     #
# Also controls the Shamrock spectrograph to open the shutter                           #
# IMPORTANT. PLEASE MAKE SURE YOU KNOW ABOUT THE WARNING REGARDING COOLING BELOW -20C.  #
# YOU MUST LET IT COOL TO >-20C (PREFERABLY 0C) USING COOLEROFF() BEFORE USING SHUTDOWN #
# AND KEEP THIS IN MIND IF THERE IS AN EXCEPTION OR EXIT TO DESKTOP EVENT               #
#                                                                                       #
# NOTE: I have not found a way yet to make the WaitForAcquisition() function to wait    #
#       for a full accumulation event (only waits until single shot is done) so the     #
#       accumulation is done by the script this sums the individual wait overhead for   #
#       a total overhead of 50% for exposure times of 0.1                               #
#                                                                                       #
# Created by Mixtli Campos on 04/10/2023                                                #
# mcampos@ucc.ie                                                                        #
#########################################################################################

# Python packages
import os
import sys
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import datetime as dt
import numpy as np
from time import sleep

# Local
import configurations as conf
import andorfunctions as andor
#sys.path.append('..')
import CESfunctionsJUNOx23 as cf

# The pyAndorSDK2 is a proprietary package from the ANDOR SDK
from pyAndorSDK2 import atmcd
from pyAndorSpectrograph.spectrograph import ATSpectrograph
from pyAndorSDK2 import atmcd_codes as codes
from pyAndorSDK2 import atmcd_errors as errors

#########################################################################################
#####                       PARAMETER CONFIGURATION                                 #####
# These parameters can be changed manually or with a configuration file

### Instrument
temp = conf.temp                                    # Camera temperature
exptime = conf.exptime_blank                        # Exposure time in seconds
bckg_shots = conf.bckg_shots                        # Number of background shots
                                                    # (for averaging in analysis)
acqMode = conf.acqMode        
                                                    # Acquisition mode
                                                    # e.g. SINGLE_SCAN, ACCUMULATE
                                                    # check codes for more
accum_number = conf.accums                          # Number of accumulations (if needed)
accum_cycle = exptime + conf.delay                  # Exp + Delay = Cycle time
                                                    # (only for internal trigger)
readMode = conf.readMode                            # Read mode
trigMode = conf.trigMode                            # Trigger Mode

### Path for saving data
savepath = conf.savepath

#########################################################################################
##### Making a subdirectory for generated files %Y%m%d

directory = dt.datetime.now().strftime('%Y%m%d')
path = os.path.join(savepath,directory)   # path of the folder wherein to store data

# Tries to make a new folder with the current date, does nothing if folder already
# exists

try:
    os.mkdir(path)
except:
    pass

path_file = path + conf.folder_symbol   # full path to append filename when writing

#########################################################################################
#####               INSTRUMENT PREPARATION FOR SAMPLING                             #####
# Starts the instrument object and initializes it
# Stabilizes to the set temperature
# Configures acquisition parameters

sdk = atmcd()  # Load the atmcd library

ret = sdk.Initialize(r"c:\Program Files\Andor SDK\\")   # Initialize camera, path points
                                                        # to DETECTOR.INI
print("Function Initialize returned {}".format(ret))

if errors.Error_Codes.DRV_SUCCESS != ret:
    print("...Could not initialize camera with error {}, will exit".format(ret))
    sys.exit()

# Uncomment the following if you really want to see the serial number
#(ret, iSerialNumber) = sdk.GetCameraSerialNumber()
#print("Function GetCameraSerialNumber returned {} Serial No: {}".format(
#        ret, iSerialNumber))

# Configure the acquisition, lines outsourced to AndorFunctions.py
try:
    andor.prepare_temperature(sdk,temp)
except Exception as e:
    print('Will exit due to following error:',e)
    sys.exit()

# We are manually summing the individual scans so there is 1 instead of accum_number,
# accum_number will be used for the loop inside the animate function
xpixels = andor.prepare_camera(sdk,acqMode,readMode,trigMode,
                               1,accum_cycle,exptime)
                               #accum_number,accum_cycle,exptime)

# Initializing the spectrograph to open shutter
#Load libraries
spc = ATSpectrograph()

#Initialize libraries
shm = spc.Initialize("")
print("Function Initialize returned {}".format(
    spc.GetFunctionReturnDescription(shm, 64)[1]))

shm = spc.SetShutter(0,1)
print("Function SetShutter returned: {}".format(
            spc.GetFunctionReturnDescription(shm, 64)[1],))

#########################################################################################
### Calculating the wavelengths with the calibration factors from configuration file  ###

#wavelengths = cf.andor_calibrator(xpixels,*conf.calfactors)

## NOTE: For spectrographs that are already in wavelengths (i.e. no calfactors)
##       we will take the wavelengths right from a reference spectrum (already offset)
ref_waves = np.load("HONO_IASC.npy")
wavelengths = np.copy(ref_waves[:,0]) 


#########################################################################################
#####                                   SAMPLING                                    #####
# Initializes an interactive plot
# Performs an acquisition loop
# Analyzes data
# Plots

### Initialize plot
fig = plt.figure()              # Figure initialization
ax1 = fig.add_subplot(111)      # Axes 1 : Signal
ax1.set_ylim([0,500])           # Set some limits for blank plot
xs = list(range(0,xpixels))     # x axis
ys = [0] * xpixels              # y axis
line, = ax1.plot(xs,ys,'-k')    # unpacked line object for axes 1

#t0 = dt.datetime.now() # testing for total elapsed time

### Initialize measurement array
measurements = np.copy(wavelengths).reshape(len(wavelengths),1)

# Perform Acquisition loop as an animate function
def init_func():
    return line,

def animate(i):
    global measurements
    # Perform Acquisition
    # Uncomment the print statements for verbosity
    print("Acquisition number",i)
    
    counts = np.zeros(xpixels)
    for j in range(accum_number):
        ret = sdk.StartAcquisition()
        #print("Function StartAcquisition returned {}".format(ret))
    
        #tt1=dt.datetime.now() # for testing wait delay 
    
        ret = sdk.WaitForAcquisition()
        #print("Function WaitForAcquisition returned {}".format(ret))
    
        #tt2=dt.datetime.now() # for testing wait delay
        #print((tt2-tt1).total_seconds())

        (ret, arr, validfirst, validlast) = sdk.GetImages16(1, 1, xpixels)
        #print("Function GetImages16 returned {} first pixel = {} size = {}".format(
        #    ret, arr[0], xpixels))
        #print(arr.shape)
        counts = counts + arr

    ### Plotting
    ax1.set_ylim([min(counts)-10,max(counts)+10])
    line.set_ydata(counts)
    
    ### Making arrays
    counts = counts.reshape(len(counts),1)
    measurements = np.concatenate((measurements,counts),axis=1)

    return line,

# call animation
ani = animation.FuncAnimation(fig,animate,init_func=init_func,frames=bckg_shots, 
                              repeat = False,
                              interval=1,blit=True,cache_frame_data=False)
plt.show()

t1 = dt.datetime.now()                  # End time

#print("Seconds elapsed: ",(t1-t0).total_seconds()) #testing for total elapsed time

# we generate a name to save the background 
blank_archive = "Ib" + t1.strftime("%y%m%d%H%M") +".txt"

np.save("background", measurements)     # for use by BBCEAS_Measure
np.savetxt(path_file + blank_archive, measurements)    # for archiving (further analysis)

#########################################################################################

#########################################################################################
#####                               SHUTTING DOWN                                   #####
# This part will prepare the camera for shutting down
# "Clears" the status
# Let's the camera reach around 0C
# Shuts down camera object to free the resource
# Lines outsourced to AndorFunctions.py

andor.shutdown_camera(sdk)
shm = spc.Close()
print("Function Close returned {}".format(
        spc.GetFunctionReturnDescription(shm, 64)[1]))
#########################################################################################
print('Shape of measurements array:',measurements.shape)
print('bye')
