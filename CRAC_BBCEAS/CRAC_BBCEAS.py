#########################################################################################
# This script configures the DV401 CCD plugged via the CCI-001 PCI Card                 #
# to take FVB single scans or accumulations for real time trace gas                     #
# concentration analysis using SVD.                                                     #
#                                                                                       #
# IMPORTANT. PLEASE MAKE SURE YOU KNOW ABOUT THE WARNING REGARDING COOLING BELOW -20C.  #
# YOU MUST LET IT COOL TO >-20C (PREFERABLY 0C) USING COOLEROFF() BEFORE USING SHUTDOWN #
# AND KEEP THIS IN MIND IF THERE IS AN EXCEPTION OR EXIT TO DESKTOP EVENT               #
#                                                                                       #
# Created by Mixtli Campos on 22/2/2023                                                 #
# mcampos@ucc.ie                                                                        #
#########################################################################################

import sys
import matplotlib.pyplot as plt
import datetime as dt
from time import sleep

# The pyAndorSDK2 is a proprietary package from the ANDOR SDK
from pyAndorSDK2 import atmcd
from pyAndorSDK2 import atmcd_codes as codes
from pyAndorSDK2 import atmcd_errors as errors

#########################################################################################
#####                       PARAMETER CONFIGURATION                                 #####
# These parameters can be changed manually for now, later I will make a
# configuration file (maybe)

temp = -10                                          # Camera temperature
exptime = 1                                         # Exposure time in seconds
shots = 5                                           # Number of acquisitions
acqMode = codes.Acquisition_Mode.SINGLE_SCAN        
                                                    # Acquisition mode
                                                    # e.g. SINGLE_SCAN, ACCUMULATE
                                                    # check codes for more
accum_number = 3                                    # Number of accumulations (if needed)
accum_cycle = exptime + .5                          # Exp + Delay = Cycle time
                                                    # (only for internal trigger)
readMode = codes.Read_Mode.FULL_VERTICAL_BINNING    # Read mode
trigMode = codes.Trigger_Mode.INTERNAL              # Trigger Mode

#########################################################################################

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

# Configure the acquisition
ret = sdk.SetTemperature(temp)
print("Function SetTemperature returned {} Set Temperature: {}".format(ret, temp))

ret = sdk.CoolerON()
print("Function CoolerON returned {}".format(ret))

#### BEGIN Temperature stabilization
print('Waiting for temperature to stabilize:')
s = True
p = 1
while s:
    sleep(15)
    (ret, temperature) = sdk.GetTemperature()
    print("...Current temperature is {}C".format(temperature))
    if ret == errors.Error_Codes.DRV_TEMP_STABILIZED:
        print('...Temperature stabilized')
        s = False
    if p > 20:
        print('...Instrument did not stabilize')
        if (temperature <= (temp+5)) and (temperature >= (temp-5)):
            print("......Temperature ({}C) is close to set temp, will continue".format(
                temperature))
            s = False
        else:
            print("......Temperature ({}C) is outside Set Temp +-5C, will exit".format(
                temperature))
            print("......Will run CoolerOFF for a bit for safety")
            ret = sdk.CoolerOFF()
            print("......Function CoolerOFF returned {}".format(ret))
            sleep(120)
            ret = sdk.ShutDown()
            print("......Function ShutDown returned {}".format(ret))
            sys.exit()
    p += 1
#### END Temperature stabilization

ret = sdk.SetAcquisitionMode(acqMode)
print("Function SetAcquisitionMode returned {}".format(ret))

#### BEGIN Set Number and Cycles for ACCUMULATION MODE
if acqMode == codes.Acquisition_Mode.ACCUMULATE:
    ret = sdk.SetNumberAccumulations(accum_number)
    print("Function SetNumberAccumulations returned {}".format(ret))
    
    ret = sdk.SetAccumulationCycleTime(accum_cycle)
    print("Function SetAccumulationCycleTime returned {}".format(ret))
#### END Set Number and Cycles for ACCUMULATION MODE

ret = sdk.SetReadMode(readMode)
print("Function SetReadMode returned {}".format(ret))

ret = sdk.SetTriggerMode(trigMode)
print("Function SetTriggerMode returned {}".format(ret))

(ret, xpixels, ypixels) = sdk.GetDetector()
print("Function GetDetector returned {} xpixels = {} ypixels = {}".format(
    ret, xpixels, ypixels))

ret = sdk.SetExposureTime(exptime)
print("Function SetExposureTime returned {} time = {}s".format(ret,exptime))

(ret, fminExposure, fAccumulate, fKinetic) = sdk.GetAcquisitionTimings()
print("Function GetAcquisitionTimings returned",
      "{} exposure = {} accumulate = {} kinetic = {}".format(ret, fminExposure, 
                                                             fAccumulate, fKinetic))

ret = sdk.PrepareAcquisition()
print("Function PrepareAcquisition returned {}".format(ret))

#########################################################################################

#########################################################################################
#####                                   SAMPLING                                    #####
# Initializes an interactive plot
# Performs an acquisition loop
# Analyzes data
# Plots

### initialize interactive plot
plt.ion()                       # Interactive plot
fig = plt.figure()              # Figure initialization
ax1 = fig.add_subplot(111)      # Axes 1 : Signal
t0 = dt.datetime.now()
# Perform Acquisition loop
for n in range(shots):
    # Perform Acquisition
    # Uncomment the print statemets for verbosity
    print("Acquisition number",n+1)
    ret = sdk.StartAcquisition()
    #print("Function StartAcquisition returned {}".format(ret))

    ret = sdk.WaitForAcquisition()
    #print("Function WaitForAcquisition returned {}".format(ret))

    imageSize = xpixels
    (ret, arr, validfirst, validlast) = sdk.GetImages16(1, 1, imageSize)
    #print("Function GetImages16 returned {} first pixel = {} size = {}".format(
    #    ret, arr[0], imageSize))
    
    ### Plotting
    ax1.cla()
    ax1.plot(arr,'-k')
    fig.canvas.draw()
    fig.canvas.flush_events()

t1 = dt.datetime.now()
print("Seconds elapsed: ",(t1-t0).total_seconds())

#########################################################################################

#########################################################################################
#####                               SHUTTING DOWN                                   #####
# This part will prepare the camera for shutting down
# "Clears" the status
# Let's the camera reach around 0C
# Shuts down camera object to free the resource

(ret, status) = sdk.GetStatus()
print("Function GetStatus returned {} with status {}".format(ret,status))

while status == errors.Error_Codes.DRV_ACQUIRING:
    print("...Device still acquiring, will wait a bit")
    sleep(5)
    (ret, status) = sdk.GetStatus()
    print("Function GetStatus returned {} with status {}".format(ret,status))

#### BEGIN Returning to OC for shutdown so that it doesn't go beyond specs 
ret = sdk.CoolerOFF()
print("Function CoolerOFF returned {}".format(ret))

s = True
print('Waiting for temperature to reach 0 C')
while s:
    sleep(15)
    (ret, temperature) = sdk.GetTemperature()
    if temperature >=0:
        s = False
#### END Returning to 0C for shutdown

ret = sdk.ShutDown()
print("Function ShutDown returned {}".format(ret))

#########################################################################################

print('bye')
