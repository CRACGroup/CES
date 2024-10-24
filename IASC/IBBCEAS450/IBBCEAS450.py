#########################################################################################
# IBBCEAS code developed for Andor detection systems                                    #
#                                                                                       #
# NOTE: Make sure you understand the how andor cameras handle cooling, all exits without#
#       proper setting to CoolerOFF run the risk of damaging the camera!!!              #
#                                                                                       #
# Created by Mixtli Campos on 27/10/2023                                                #
#########################################################################################
#########################################################################################
# PREVIOUS HEADER                                                                       #
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
#
# Python packages
import os
import subprocess
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import datetime as dt
import numpy as np
from time import sleep
from matplotlib.dates import DateFormatter

# Local
import configurations_CEAS450 as conf
import andorfunctions as andor
import CESfunctionsIASC as cf

# The pyAndorSDK2 is a proprietary package from the ANDOR SDK
from pyAndorSDK2 import atmcd
from pyAndorSDK2 import atmcd_codes as codes
from pyAndorSDK2 import atmcd_errors as errors

#########################################################################################
#####                       PARAMETER CONFIGURATION                                 #####
# These parameters can be changed manually or with a configuration file

### Instrument 
temp = conf.temp                                    # Camera temperature
exptime = conf.exptime_sample                       # Exposure time in seconds
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

### Signal analysis
# Cavity parameters
distance = conf.distance                    # Sample optical length

# Resonance window 
lower_wavelength=conf.lower_wavelength      # Starting wavelength of resonance window
upper_wavelength=conf.upper_wavelength      # Ending wavelength of resonance window

# Reference and background files
back_filename = conf.back_filename
ref1name = conf.ref1name
ref2name = conf.ref2name
#ref3name = conf.ref3name
sigma_ray_filename = conf.sigma_ray_filename

# Start average from measure #
start_avg = conf.start_avg

# Reff : Either a number or a vector (in the configurations file)
Reff = conf.Reff
#Reff = Reff.reshape(len(Reff),1) 

# Dilution factor --> SET TO 1 for IASC
dfactor = 1
#dfactor = 1-(conf.n2flow/conf.tflow)

### Path for saving data
savepath = conf.savepath

#########################################################################################
### Reference and Background file loading for analisis                                ###

reference1 = np.load(ref1name)
reference2 = np.load(ref2name)
#reference3 = np.load(ref3name)
sigma_ray_long = np.load(sigma_ray_filename)

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
except:
    sys.exit()

xpixels = andor.prepare_camera(sdk,acqMode,readMode,trigMode,
                               1,accum_cycle,exptime)
                               #accum_number,accum_cycle,exptime)
wavelengths = cf.andor_calibrator(xpixels,*conf.calfactors)
#wref = np.load("NO2_IASC_CEAS450.npy")
#wavelengths = wref[:,0].reshape(xpixels,1)
#########################################################################################
def run_background(sdk,xpixels,accum_number,measurements,path_file):
    for j in range(bckg_shots):
        print("Background number",j)
        counts = np.zeros(xpixels)

        for k in range(accum_number):
            arr = andor.take_measurement(sdk,xpixels)
            counts = counts + arr

        np.save("ax1data",np.column_stack((np.arange(1,xpixels+1,1),counts)))

        counts = counts.reshape(len(counts),1)
        measurements = np.concatenate((measurements,counts),axis=1)
    t1=dt.datetime.now()    
    blank_archive = "Ib" + t1.strftime("%y%m%d%H%M") +".txt"
    np.save("background", measurements)     # for use by BBCEAS_Measure
    np.savetxt(path_file + blank_archive, measurements) #for archiving (further analysis)


def run_sample(back_filename,xpixels,accum_number,sdk,reference1,reference2,#reference3,
        sigma_ray_long,distance,measurements):
    background = np.load(back_filename)
    meastime = []
    meastime2 = []
    ppbs = []
    ppbs2 = []
    #ppbs3 = []
    l=1
    while True:
        try:
            with open('endme','r') as f:
                read=f.read()
            os.remove("endme")
            t1 = dt.datetime.now()                  # End time
            #print("Seconds elapsed: ",(t1-t0).total_seconds())

            # We save all measurements in a numpy file
            np.save(path_file + "Imeas" + t1.strftime("%y%m%d%H%M"), measurements)

            # We save all concentrations in a datafile
            np.savetxt(path_file + "M" + t1.strftime('%y%m%d%H%M') + '.txt',
            np.column_stack((meastime,ppbs,ppbs2)), fmt='%s')
            break

        except:
            pass

        print("Acquisition number",l)
        counts = np.zeros(xpixels)
        for j in range(accum_number):
            arr = andor.take_measurement(sdk,xpixels)
            counts = counts + arr

        ### Calculating number density
        counts = counts.reshape(len(counts),1)
        minwave,maxwave = cf.segment_indices(background,lower_wavelength,
            upper_wavelength)
        bckg = np.copy(background[minwave:maxwave,:])
        ref1 = np.copy(reference1) ### homemade spectrum, 2 cols
        ref2 = np.copy(reference2[minwave:maxwave,:])
        #ref3 = np.copy(np.column_stack((ref1[:,0],reference3))) ### homemade spectrum, only extinction (1 col)
        sigma_ray = np.copy(sigma_ray_long[minwave:maxwave]).reshape(len(sigma_ray_long[minwave:maxwave]),1)
        #print(no3ref.shape,no2ref.shape,h2oref.shape)
        I_sample = np.copy(counts[minwave:maxwave,:])
        I_0 = np.average(bckg[:,start_avg:],axis=1).reshape(len(bckg),1)
        pPa = 101335
        tK = 293.15
        
        ### This one does everything (see recursive_fit_2ref function in CESfunctions.py)
        try:
            alpha,fl,a,b,ndensity1,ndensity2 = cf.fit_alg_1B_it(I_sample, I_0, Reff,
                    distance,ref1,ref2,pPa,tK,sigma_ray,parameters=1)
        except Exception as e:
            print("fit_alg_1B_it failed with exception:")
            print(e)
            pass
        
        ### The timestamp for this measurement is now
        timenow = dt.datetime.now()
        stamp = timenow.strftime('%y%m%d%H%M%S')
        meastime2.append(timenow)

        ### Add sample to measurements array and save individual sample datafile
        measurements = np.concatenate((measurements,counts.reshape(len(counts),1)),
                axis=1)
    
        np.savetxt(path_file+'Im'+stamp+'.txt',measurements[:,[0,-1]],fmt='%s')

        ### Populate ppbs and meastime arrays with current sample
        ###make/overwrite datafile
        conc = (ndensity1*1e15*1.380649e-23*tK/pPa)
        conc2 = (ndensity2*1e15*1.380649e-23*tK/pPa)
        #conc3 = (ndensity2*1e15*1.380649e-23*tK/pPa)
        ppbs.append(conc)
        ppbs2.append(conc2)
        #ppbs3.append(conc3)
        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
       
        np.savetxt(path_file+'Mtemp.txt',np.column_stack((meastime,ppbs,ppbs2)),fmt='%s')

        # Print calculated ppb
        print('NO2 ppb: ', ppbs[-1])
        print('GLY ppb: ', ppbs2[-1])
        #print('H2O ppb: ', ppbs3[-1])

        wavt = np.copy(ref1[:,0]).reshape(len(ref1[:,0]),1)
        np.save("ax2data", np.concatenate((wavt,alpha),axis=1))
        np.save("ax2adata", np.column_stack((ref1[:,0],
            a+b*fl+ref1[:,1]*ndensity1+ref2[:,1]*ndensity2)))
        np.save("ax3data", np.column_stack((meastime2,ppbs)))
        np.save("ax4data", np.column_stack((meastime2,ppbs2)))
        l+=1

#########################################################################################
#####                                   SAMPLING                                    #####
# Call plotter
# Continue with runtime, if plotter closed go back to choice


while True:
    try:
        choice = input("Type option: (F)ull run, (M)easurement only, (E)xit: ")

        if choice.lower() == 'f':
            pid = subprocess.Popen(["python","IBBCEAS450_plotter.py"]).pid
            print('Full run. Will take background, then sample.')
            measurements = np.copy(wavelengths)
            run_background(sdk,xpixels,accum_number,measurements,path_file)
        
            print("Finished background, will proceed to sample.")
            measurements = np.copy(wavelengths)
            run_sample(back_filename,xpixels,accum_number,sdk,reference1,reference2,#reference3,
                        sigma_ray_long,distance,measurements)
           
        #elif choice.lower() == b:
        elif choice.lower() == 'm':
            pid = subprocess.Popen(["python","IBBCEAS450_plotter.py"]).pid
            print("Will proceed to sample.")
            measurements = np.copy(wavelengths)
            run_sample(back_filename,xpixels,accum_number,sdk,reference1,reference2,#reference3,
                        sigma_ray_long,distance,measurements)

        elif choice.lower() == 'e':
            print("Will exit.")
            break

        else:
            continue
    except Exception as e:
        print("Program failed with exception",e)
        continue


#########################################################################################

#########################################################################################
#####                               SHUTTING DOWN                                   #####
# This part will prepare the camera for shutting down
# "Clears" the status
# Let's the camera reach around 0C
# Shuts down camera object to free the resource
# Lines outsourced to AndorFunctions.py

andor.shutdown_camera(sdk)

#########################################################################################
print('Shape of measurements array:',measurements.shape)
print('bye')
