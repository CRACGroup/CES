#########################################################################################
# This script initializes the camera and takes 

from pyAndorSDK2 import atmcd, atmcd_codes, atmcd_errors
import sys
import matplotlib.pyplot as plt
import datetime as dt
from time import sleep


temp = -10
sdk = atmcd()  # Load the atmcd library
codes = atmcd_codes
ret = sdk.Initialize(r"c:\Program Files\Andor SDK\\")  # Initialize camera
print("Function Initialize returned {}".format(ret))

if atmcd_errors.Error_Codes.DRV_SUCCESS != ret:
    print('Could not initialize camera, will exit')
    sys.exit()

(ret, iSerialNumber) = sdk.GetCameraSerialNumber()
print("Function GetCameraSerialNumber returned {} Serial No: {}".format(
        ret, iSerialNumber))

# Configure the acquisition
ret = sdk.SetTemperature(temp)
print("Function SetTemperature returned {} Set Temperature: {}".format(ret, temp))

ret = sdk.CoolerON()
print("Function CoolerON returned {}".format(ret))

print('Waiting for temperature to stabilize...')
n = True
while n:
    sleep(15)
    (ret, temperature) = sdk.GetTemperature()
    if ret == atmcd_errors.Error_Codes.DRV_TEMP_STABILIZED:
        print('Temperature stabilized')
        n = False

ret = sdk.SetAcquisitionMode(codes.Acquisition_Mode.SINGLE_SCAN)
print("Function SetAcquisitionMode returned {} mode = Single Scan".format(ret))

ret = sdk.SetReadMode(codes.Read_Mode.FULL_VERTICAL_BINNING)
print("Function SetReadMode returned {} mode = FVB".format(ret))

ret = sdk.SetTriggerMode(codes.Trigger_Mode.INTERNAL)
print("Function SetTriggerMode returned {} mode = Internal".format(ret))

(ret, xpixels, ypixels) = sdk.GetDetector()
print("Function GetDetector returned {} xpixels = {} ypixels = {}".format(
    ret, xpixels, ypixels))

ret = sdk.SetExposureTime(1)
print("Function SetExposureTime returned {} time = 1s".format(ret))

(ret, fminExposure, fAccumulate, fKinetic) = sdk.GetAcquisitionTimings()
print("Function GetAcquisitionTimings returned",
      "{} exposure = {} accumulate = {} kinetic = {}".format(ret, fminExposure, 
                                                             fAccumulate, fKinetic))

ret = sdk.PrepareAcquisition()
print("Function PrepareAcquisition returned {}".format(ret))


### initialize interactive plot
plt.ion()                       # Interactive plot
fig = plt.figure()              # Figure initialization
ax1 = fig.add_subplot(111)      # Axes 1 : Signal
shots = 5
t0 = dt.datetime.now()
# Perform Acquisition loop
for n in range(shots):
    # Perform Acquisition
    ret = sdk.StartAcquisition()
    print("Function StartAcquisition returned {}".format(ret))

    ret = sdk.WaitForAcquisition()
    print("Function WaitForAcquisition returned {}".format(ret))

    imageSize = xpixels
    (ret, arr, validfirst, validlast) = sdk.GetImages16(1, 1, imageSize)
    print("Function GetImages16 returned {} first pixel = {} size = {}".format(
        ret, arr[0], imageSize))
    
    ### Plotting
    ax1.cla()
    ax1.plot(arr,'-k')
    fig.canvas.draw()
    fig.canvas.flush_events()
t1 = dt.datetime.now()
print("Seconds elapsed: ",(t1-t0).total_seconds())

(ret, status) = sdk.GetStatus()
print("Function GetStatus returned {} with status {}".format(ret,status))

ret = sdk.CoolerOFF()
print("Function CoolerOFF returned {}".format(ret))

n = True
print('Waiting for temperature to reach 0 C')
while n:
    sleep(15)
    (ret, temperature) = sdk.GetTemperature()
    if temperature >=0:
        n = False

ret = sdk.ShutDown()
print("Function ShutDown returned {}".format(ret))
print('bye')
