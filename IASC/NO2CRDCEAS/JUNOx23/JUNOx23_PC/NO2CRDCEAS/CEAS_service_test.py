##########################################################################################
# This is the companion script for the NO2 CRD/CEAS instrument. The "service" consists on
# listening to rs232 calls from the main sscript in the MIC1816 and running the CEAS in
# different measurement schemes.
#
# Created by Mixtli Campos on 02.06.2023
#
##########################################################################################

########## General packages
import serial, os, sys
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import datetime as dt
import numpy as np
from time import sleep
from matplotlib.dates import DateFormatter

########## Local
import configurations as conf
import andorfunctions as andor
import CESfunctionsJUNOx23 as cf

########## pyAndorSDK2 is a proprietary package from the ANDOR SDK
from pyAndorSDK2 import atmcd
from pyAndorSDK2 import atmcd_codes as codes
from pyAndorSDK2 import atmcd_errors as errors

############################## Measurement functions #####################################
def ceas_blank(meastype,accums,exposure,shots):
    '''
    This function executes the blank measurements.
    meastype = ['b','z']
    '''
    global measurements
    exptime = float(exposure)                      # Exposure time in seconds
    blnk_shots = int(shots)                      # Number of background shots
                                            # (for averaging in analysis)
    acqMode = conf.acqMode        
                                            # Acquisition mode
                                            # e.g. SINGLE_SCAN, ACCUMULATE
                                            # check codes for more
    accum_number = int(accums)                   # Number of accumulations (if needed)
    accum_cycle = exptime + conf.delay      # Exp + Delay = Cycle time
                                            # (only for internal trigger)
    readMode = conf.readMode                # Read mode
    trigMode = conf.trigMode                # Trigger Mode
    ### Path for saving data
    savepath = conf.savepath
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
    ### Prepare the camera
    xpixels = andor.prepare_camera(sdk,acqMode,readMode,trigMode,
        accum_number,accum_cycle,exptime)

    ### Calculating the wavelengths with the calibration factors from configuration file
    wavelengths = cf.andor_calibrator(xpixels,*conf.calfactors)
    
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

        ### Plotting
        ax1.set_ylim([min(arr)-10,max(arr)+10])
        line.set_ydata(arr)
    
        ### Making arrays
        counts = np.copy(arr).reshape(len(arr),1)
        measurements = np.concatenate((measurements,counts),axis=1)

        return line,

    # call animation
    ani = animation.FuncAnimation(fig,animate,init_func=init_func,frames=blnk_shots, 
                              repeat = False,
                              interval=1,blit=True,cache_frame_data=False)
    plt.show()

    t1 = dt.datetime.now()                  # End time

    #print("Seconds elapsed: ",(t1-t0).total_seconds()) #testing for total elapsed time
    # we generate a name to save the background
    blank_archive = "I" + meastype + t1.strftime("%y%m%d%H%M") +".txt"
    
    if meastype == 'b':
        measname = 'background'
    else:
        measname = 'zero'

    np.save(measname, measurements)     # for use by other functions
    
    np.savetxt(path_file + blank_archive, measurements)    # for further analysis

def ceas_measure(meastype,accums,exposure,shots):
    '''
    This function executes the sample air measurements
    NEEDS WORK!
    '''
    global measurements,meastime,meastime2,ppbs,ppbs2
    ### Instrument 
    exptime = float(exposure)                      # Exposure time in seconds
    meas_shots = int(shots)                      # Number of measurement shots
                                            # (for averaging in analysis)
    acqMode = conf.acqMode        
                                            # Acquisition mode
                                            # e.g. SINGLE_SCAN, ACCUMULATE
                                            # check codes for more
    accum_number = int(accums)                   # Number of accumulations (if needed)
    accum_cycle = exptime + conf.delay      # Exp + Delay = Cycle time
                                            # (only for internal trigger)
    readMode = conf.readMode                # Read mode
    trigMode = conf.trigMode                # Trigger Mode

    ### Signal analysis
    # Cavity parameters
    distance = conf.distance                    # Sample optical length

    # Resonance window  
    lower_wavelength=conf.lower_wavelength      # Starting wavelength of resonance window
    upper_wavelength=conf.upper_wavelength      # Ending wavelength of resonance window

    # Reference and background files
    back_filename = conf.back_filename
    no2_refname = conf.no2_refname
    chocho_refname = conf.chocho_refname

    # Reff : Either a number conf.Reff or a vector np.load(conf.Reff_matrix)
    Reff= conf.Reff

    # Dilution factor --> SET TO 1 for IASC
    dfactor = 1
    #dfactor = 1-(conf.n2flow/conf.tflow)

    ### Path for saving data
    savepath = conf.savepath

    ### Reference and Background file loading for analisis             
    no2reference = np.load(no2_refname)
    chochoref = np.load(chocho_refname)
    background = np.load(back_filename)
    
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
    ## Prepare the camera and wavelength vector
    xpixels = andor.prepare_camera(sdk,acqMode,readMode,trigMode,
            accum_number,accum_cycle,exptime)
    wavelengths = cf.andor_calibrator(xpixels,*conf.calfactors)

    ### Initialize plot
    fig = plt.figure()              # Figure initialization
    ax1 = fig.add_subplot(211)      # Axes 1 : Signal
    ax2 = fig.add_subplot(212)      # Axes 2 : Concentration 1
    ax3 = ax2.twinx()               # Axes 3 : Concentration 2

    # Initialize empty plots
    minwave,maxwave = cf.segment_indices(background[:,0:2],lower_wavelength,
                 upper_wavelength)
    ax1.set_ylim([0,500])
    ax2.set_ylim([0,50])
    ax3.set_ylim([0,50])
    xs = background[minwave:maxwave,0]
    #print(xs.shape)
    ys = [0] * xs
    #print(ys.shape)
    line, = ax1.plot(xs,ys,'-k')
    line1, = ax1.plot(xs,ys,'-g')
    line2, = ax2.plot(xs,ys,'-b')
    line3, = ax3.plot(xs,ys,'-r')

    #t0 = dt.datetime.now() # testing for total elapsed time

    ### Initializing timestamp and concentration list, and measurement array
    measurements = np.array(background[:,0]).reshape(len(background[:,0]),1)
    meastime = []
    meastime2 = []
    ppbs = []
    ppbs2 = []

    # Perform Acquisition loop as an animate function

    def init_func():
        return line, line1, line2, line3,

    def animate(i):
        global measurements,meastime,meastime2,ppbs,ppbs2
        # Perform Acquisition
        # Uncomment the print statements for verbosity
        print("Acquisition number",i)
    
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

        ### Calculating number density
        counts = np.copy(arr).reshape(len(arr),1)
        minwave,maxwave = cf.segment_indices(measurements[:,0:2],lower_wavelength,
                upper_wavelength)
        bckg = np.copy(background[minwave:maxwave,:])
        no2ref = np.copy(no2reference[minwave:maxwave,:])
        glyref = np.copy(chochoref[minwave:maxwave,:])
        I_sample = np.copy(counts[minwave:maxwave,:])
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
    
        np.savetxt(path_file+'Is'+stamp+'.txt',measurements[:,[0,-1]],fmt='%s')

        ### Populate ppbs and meastime arrays with currents sample, make/overwrite datafile
        ppbs.append((ndensity1/2.504e10)/dfactor)
        ppbs2.append((ndensity2/2.504e10)/dfactor)
        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
       
        np.savetxt(path_file+'Mtemp.txt',np.column_stack((meastime,ppbs,ppbs2)),fmt='%s')

        # Print calculated NO2 in ppb
        print('NO2 ppb: ', ppbs[-1], 'CHOCHO ppb: ', ppbs2[-1])

        ### Plotting
        # Plot 1 : Axes 1
        #print('Getting first plot')
        ax1.set_ylim([min(alpha),max(alpha)])
        line.set_ydata(alpha)
        line1.set_ydata(a+b*fl+no2ref[:,1]*ndensity1+glyref[:,1]*ndensity2)
    
        # Plot 2 : Axes 2
        #print('Getting second plot')
        if i!=0:
            ax2.set_xlim([min(meastime2),max(meastime2)])
            ax2.set_ylim([min(ppbs),max(ppbs)])
            ax3.set_ylim([min(ppbs2),max(ppbs2)])
        line2, = ax2.plot(meastime2,ppbs,'-b')
        line3, = ax3.plot(meastime2,ppbs2,'-r')
        ax2.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        #line2.set_ydata(ppbs)
        #line3.set_ydata(ppbs2)
    
        return line, line1, line2, line3,

    # call animation
    ani = animation.FuncAnimation(fig,animate,init_func=init_func,frames=meas_shots, 
                              repeat = False,
                              interval=1,blit=False,cache_frame_data=False)
    plt.show()

    t1 = dt.datetime.now()                  # End time
    #print("Seconds elapsed: ",(t1-t0).total_seconds())
    
    
    # We save all measurements in a numpy file
    np.save(path_file + "Im" + t1.strftime("%y%m%d%H%M"), measurements)

    # We save all concentrations in a datafile
    np.savetxt(path_file + "M" + t1.strftime('%y%m%d%H%M') + '.txt',
            np.column_stack((meastime,ppbs,ppbs2)), fmt='%s')


############################## End of Measurement functions ##############################

############################## CEAS and COM port initialization ##########################

measurements = None
meastime  = None
meastime2 = None
ppbs = None
ppbs2 = None

### Starting the communication port
ceascom = serial.Serial('COM2',19200)

### Instrument parameters
temp = conf.temp                                    # Camera temperature


### CCD initialization

sdk = atmcd()  # Load the atmcd library
ret = sdk.Initialize(r"c:\Program Files\Andor SDK\\")   # Initialize camera, path points
print("Function Initialize returned {}".format(ret))

if errors.Error_Codes.DRV_SUCCESS != ret:
    print("...Could not initialize camera with error {}, will exit".format(ret))
    sys.exit()

# Configure the acquisition, lines outsourced to AndorFunctions.py
try:
    andor.prepare_temperature(sdk,temp)
except Exception as e:
    print('Will exit due to following error:',e)
    sys.exit()


############################## Listener and operation ####################################
while True:
    msg_in = input('Input measurement code, q to quit:')
    if msg_in == 'q':
        break
    params = msg_in.split(',')
    if params[0] == 'm':
        ceas_measure(*tuple(params))

        #try:
        #    ceas_measure(*tuple(params))
        #except Exception as e:
        #    print('Error running measure')
        #    print(e)
        #    break
    else:
        ceas_blank(*tuple(params))
        #try:
        #    ceas_blank(*tuple(params))
        #except Exception as e:
        #    print('Error running blank')
        #    print(e)
        #    break

    
############################## SHUTDOWN ##################################################
andor.shutdown_camera(sdk)
ceascom.close()
