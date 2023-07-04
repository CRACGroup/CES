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
def ceas_blank(fig,ax1,ax2,meastype,accums,exposure,shots):
    '''
    This function executes the blank measurements.
    meastype = ['b','z']
    '''
    global  meastime,meastime2,ppbs,mfca_ps,mfca_ts,flag, \
    path_file,xpixels,measures,tstamp,zerocheck,rcrds,ppbschocho

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
    if meastype == 'b':
        measname = 'background'
    else:
        measname = 'zero'
        measures = np.copy(wavelengths).reshape(len(wavelengths),1)
        meastime = []
        ppbs = [] 
        ppbschocho = []
        mfca_ps = []
        mfca_ts = []
        flag = []
        rcrds = []
        zerocheck = True
 
    ### Initialize plot
    #plt.ion()                       # Interactive plot
    #fig = plt.figure()              # Figure initialization
    #ax1 = fig.add_subplot(111)      # Axes 1 : Signal
    #xs = list(range(0,xpixels))     # x axis
    #ys = [0] * xpixels              # y axis
    #ax1.plot(xs,ys,'-k')            

    t0 = dt.datetime.now() # testing for total elapsed time

    ### Initialize measurement array
    measurements = np.copy(wavelengths).reshape(len(wavelengths),1)

    # Perform Acquisition loop as an interactive pyplot figure
    for i in range(blnk_shots):
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
        if meastype == 'b':
            ax1.cla()
            ax1.plot(wavelengths,arr,'-k')
            ax1.grid()
            fig.canvas.flush_events()
        else:
            ax2.cla()
            ax2.plot(wavelengths,arr,'-k')
            ax2.grid()
            fig.canvas.flush_events()

        ### Making arrays
        counts = np.copy(arr).reshape(len(arr),1)
        measurements = np.concatenate((measurements,counts),axis=1)

    t1 = dt.datetime.now()                  # End time
    #plt.close('all')

    print("Seconds elapsed: ",(t1-t0).total_seconds()) #testing for total elapsed time
    # we generate a name to save the background
    blank_archive = "I" + meastype + t1.strftime("%y%m%d%H%M") +".txt"
    
    
    np.save(measname, measurements)     # for use by other functions
    
    np.savetxt(path_file + blank_archive, measurements)    # for further analysis

def ceas_measure(fig,ax3,ax4,meastype,accums,exposure,shots,mfca_p,mfca_t,trueref):
    '''
    This function executes the sample air measurements
    NEEDS WORK!
    '''
    global  meastime,meastime2,ppbs,mfca_ps,mfca_ts,flag, \
    path_file,xpixels,measures,tstamp,zerocheck,rcrds 

    ### Instrument 
    exptime = float(exposure)                      # Exposure time in seconds
    meas_shots = int(shots)                      # Number of measurement shots
    ### Signal analysis
    # Cavity parameters
    distance = conf.distance                    # Sample optical length

    # Resonance window  
    lower_wavelength=conf.lower_wavelength      # Starting wavelength of resonance window
    upper_wavelength=conf.upper_wavelength      # Ending wavelength of resonance window

    # Reference and background files
    back_filename = conf.back_filename
    no2_refname = conf.no2_refname
    zero_filename = conf.zero_filename

    # Start average from measure #
    start_avg = conf.start_avg
    
    # Reff : Either a number conf.Reff or a vector np.load(conf.Reff_matrix)
    Refff = conf.Reff
    #rfactor = float(trueref)/Refff[conf.scale_index]
    rfactor=1
    Reff = Refff.reshape(len(Refff),1)*rfactor

    # Dilution factor --> SET TO 1 for IASC
    dfactor = 1
    #dfactor = 1-(conf.n2flow/conf.tflow)

    ### Path for saving data
    #savepath = conf.savepath

    ### Reference and Background file loading for analisis             
    no2reference = np.load(no2_refname)
    background = np.load(back_filename)
    zeroair = np.load(zero_filename)

    ### Initialize plot

    t0 = dt.datetime.now() # testing for total elapsed time

    ### Initializing timestamp and concentration list, and measurement array

    # Perform Acquisition loop as interactive pyplot
    for i in range(meas_shots):
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
        minwave,maxwave = cf.segment_indices(no2reference,lower_wavelength,
                upper_wavelength)
        bckg = np.copy(background[minwave:maxwave,:])
        zero = np.copy(zeroair[minwave:maxwave,:])
        no2ref = np.copy(no2reference[minwave:maxwave,:])
        I_s = np.copy(counts[minwave:maxwave,:])
        I_b = np.average(bckg[:,1:],axis=1).reshape(len(bckg),1)
        I_not = np.average(zero[:,start_avg:],axis=1).reshape(len(zero),1)
        I_0 = np.subtract(I_not,I_b)
        I_sample = np.subtract(I_s,I_b)
        pres = float(mfca_p)
        tem = float(mfca_t)
        pPa = 6894.757293 * pres
        tK = 273.15 + tem
    
        ### This one does everything (see CESfunctionsJUNOx23.py)
        try:
            alpha,fl,a,b,ndensity1 = cf.fit_alg_1A_it(I_sample, I_0, Reff, distance, 
            no2ref,pPa,tK,parameters=1)
        except Exception as e:
            print("fit_alg_1A failed with exception:")
            print(e)
            continue
    
        ### The timestamp for this measurement is now
        #print('timenow')
        timenow = dt.datetime.now()
        meastime2.append(timenow)

        ### Add sample to measurements array and save individual sample datafile
        measures = np.concatenate((measures,counts.reshape(len(counts),1)),axis=1)
    
        #np.savetxt(path_file+'Im'+stamp+'.txt',measures[:,[0,-1]],fmt='%s')

        ### Populate ppbs and meastime arrays with currents sample, make/overwrite datafile
        conc = (ndensity1*1e15*1.380649e-23*tK/pPa)
        ppbs.append(conc)
        ppbs2.append(conc)
        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
        mfca_ps.append(pres)
        mfca_ts.append(tem)
        rcrds.append(float(trueref))
        flag.append(0)
       
        #print('saving')
        # We save all measurements in a numpy file
        np.save(path_file + "Ibzm" + timenow.strftime("%y%m%d%H%M%S"), 
                np.column_stack((background,zeroair,measures)))
        if not zerocheck:
            os.remove(path_file + "Ibzm" + tstamp.strftime("%y%m%d%H%M%S")+'.npy')

        # We save all concentrations in a datafile
        print(len(meastime),len(ppbs),len(mfca_ps),len(mfca_ts),len(rcrds),len(flag))
        np.savetxt(path_file + "M" + timenow.strftime('%y%m%d%H%M%S') + '.txt',
                np.column_stack((meastime,ppbs,mfca_ps,mfca_ts,rcrds,flag)), fmt='%s')
        if not zerocheck:
            os.remove(path_file + "M" + tstamp.strftime('%y%m%d%H%M%S') + '.txt')

        # Print calculated NO2 in ppb
        print('NO2 ppb: ', ppbs[-1])

        ### Plotting
        ax3.cla()
        ax4.cla()
        # Plot 1 : Axes 1
        #print('Getting first plot')
        #ax1.plot(bckg[:,0],(I_0/I_sample)-1,'-k')
        ax3.plot(bckg[:,0],alpha,'-k')
        ax3.plot(bckg[:,0],a+b*fl+no2ref[:,1]*ndensity1,'-g')
        
        #print('plotting')
        #print(meastime2)
        # Plot 2 : Axes 2
        #print('Getting second plot')
        ax4.plot(meastime2,ppbs2,'-b')
        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        ax3.grid()
        ax4.grid()
        fig.canvas.flush_events()
        
        zerocheck = False
        tstamp = timenow
        

    #plt.close('all')
    t1 = dt.datetime.now()                  # End time
    print("Seconds elapsed: ",(t1-t0).total_seconds())
    
def ceas_measure_2ref(fig,ax3,ax4,meastype,accums,exposure,shots,mfca_p,mfca_t,trueref):
    '''
    This function executes the sample air measurements
    NEEDS WORK!
    '''
    global  meastime,meastime2,ppbs,mfca_ps,mfca_ts,flag, \
    path_file,xpixels,measures,tstamp,zerocheck,rcrds,ppbschocho
 

    ### Instrument 
    exptime = float(exposure)                      # Exposure time in seconds
    meas_shots = int(shots)                      # Number of measurement shots
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
    zero_filename = conf.zero_filename

    # Start average from measure #
    start_avg = conf.start_avg
    
    # Reff : Either a number conf.Reff or a vector np.load(conf.Reff_matrix)
    Refff = conf.Reff
    #rfactor = float(trueref)/Refff[conf.scale_index]
    rfactor=1
    Reff = Refff.reshape(len(Refff),1)*rfactor

    # Dilution factor --> SET TO 1 for IASC
    dfactor = 1
    #dfactor = 1-(conf.n2flow/conf.tflow)

    ### Path for saving data
    #savepath = conf.savepath

    ### Reference and Background file loading for analisis             
    no2reference = np.load(no2_refname)
    chochoreference = np.load(chocho_refname)
    background = np.load(back_filename)
    zeroair = np.load(zero_filename)

    ### Initialize plot

    t0 = dt.datetime.now() # testing for total elapsed time

    ### Initializing timestamp and concentration list, and measurement array

    # Perform Acquisition loop as interactive pyplot
    for i in range(meas_shots):
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
        minwave,maxwave = cf.segment_indices(no2reference,lower_wavelength,
                upper_wavelength)
        bckg = np.copy(background[minwave:maxwave,:])
        zero = np.copy(zeroair[minwave:maxwave,:])
        no2ref = np.copy(no2reference[minwave:maxwave,:])
        chochoref = np.copy(chochoreference[minwave:maxwave,:])
        I_s = np.copy(counts[minwave:maxwave,:])
        I_b = np.average(bckg[:,1:],axis=1).reshape(len(bckg),1)
        I_not = np.average(zero[:,start_avg:],axis=1).reshape(len(zero),1)
        I_0 = np.subtract(I_not,I_b)
        I_sample = np.subtract(I_s,I_b)
        pres = float(mfca_p)
        tem = float(mfca_t)
        pPa = 6894.757293 * pres
        tK = 273.15 + tem
    
        ### This one does everything (see CESfunctionsJUNOx23.py)
        try:
            alpha,fl,a,b,ndensity1,ndensity2 = cf.fit_alg_1B_it(I_sample, I_0, Reff, distance, 
            no2ref,chochoref,pPa,tK,parameters=1)
        except Exception as e:
            print("fit_alg_1B_it failed with exception:")
            print(e)
            continue
    
        ### The timestamp for this measurement is now
        #print('timenow')
        timenow = dt.datetime.now()
        meastime2.append(timenow)

        ### Add sample to measurements array and save individual sample datafile
        measures = np.concatenate((measures,counts.reshape(len(counts),1)),axis=1)
    
        #np.savetxt(path_file+'Im'+stamp+'.txt',measures[:,[0,-1]],fmt='%s')

        ### Populate ppbs and meastime arrays with currents sample, make/overwrite datafile
        conc = (ndensity1*1e15*1.380649e-23*tK/pPa)
        conc2 = (ndensity2*1e15*1.380649e-23*tK/pPa) 
        ppbs.append(conc)
        ppbs2.append(conc)
        ppbschocho.append(conc2)
        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
        mfca_ps.append(pres)
        mfca_ts.append(tem)
        rcrds.append(float(trueref))
        flag.append(0)
       
        #print('saving')
        # We save all measurements in a numpy file
        np.save(path_file + "Ibzm" + timenow.strftime("%y%m%d%H%M%S"), 
                np.column_stack((background,zeroair,measures)))
        if not zerocheck:
            os.remove(path_file + "Ibzm" + tstamp.strftime("%y%m%d%H%M%S")+'.npy')

        # We save all concentrations in a datafile
        print(len(meastime),len(ppbs),len(ppbschocho),len(mfca_ps),len(mfca_ts),len(rcrds),len(flag))
        np.savetxt(path_file + "M" + timenow.strftime('%y%m%d%H%M%S') + '.txt',
                np.column_stack((meastime,ppbs,ppbschocho,mfca_ps,mfca_ts,rcrds,flag)), fmt='%s')
        if not zerocheck:
            os.remove(path_file + "M" + tstamp.strftime('%y%m%d%H%M%S') + '.txt')

        # Print calculated NO2 in ppb
        print('NO2 ppb: ', ppbs[-1])

        ### Plotting
        ax3.cla()
        ax4.cla()
        # Plot 1 : Axes 1
        #print('Getting first plot')
        #ax1.plot(bckg[:,0],(I_0/I_sample)-1,'-k')
        ax3.plot(bckg[:,0],alpha,'-k')
        ax3.plot(bckg[:,0],a+b*fl+no2ref[:,1]*ndensity1,'-g')
        
        #print('plotting')
        #print(meastime2)
        # Plot 2 : Axes 2
        #print('Getting second plot')
        ax4.plot(meastime2,ppbs2,'-b')
        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
        ax3.grid()
        ax4.grid()
        fig.canvas.flush_events()
        
        zerocheck = False
        tstamp = timenow
        

    #plt.close('all')
    t1 = dt.datetime.now()                  # End time
    print("Seconds elapsed: ",(t1-t0).total_seconds())    

############################## End of Measurement functions ##############################

############################## CEAS and COM port initialization ##########################

### Starting the communication port
ceascom = serial.Serial('COM1',19200)

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

plt.ion()
fig = plt.figure(figsize=(15,6))
gs = fig.add_gridspec(3,3)
ax1 = fig.add_subplot(gs[:-1,0])
ax2 = fig.add_subplot(gs[:-1,1])
ax3 = fig.add_subplot(gs[:-1,2])
ax4 = fig.add_subplot(gs[-1,:])
ax4.set_xlabel('Time')
#ax1.set_ylabel('Voltage')
ax1.grid()
ax2.grid()
ax3.grid()
ax4.grid()

meastime = []
meastime2 = []
ppbs = []
ppbs2 = []
ppbschocho = []
mfca_ps = []
mfca_ts = []
flag = []
rcrds = []
refs = 2
path_file = None
xpixels = None
measures = None
zerocheck=False
tstamp = dt.datetime.now()


############################## Listener and operation ####################################
while True:
    try:
        sleep(2)
        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
        while msg_in == '':
            sleep(0.5)
            msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
    
        ceascom.write(b'k')
    
        params = msg_in.split(',')

        if params[0] == 'm':
            #ceas_measure(*tuple(params))
            try:
                if refs == 1:
                    ceas_measure(fig,ax3,ax4,*tuple(params))
                elif refs == 2:
                    ceas_measure_2ref(fig,ax3,ax4,*tuple(params))
            except Exception as e:
                print('Error running measure')
                print(e)
                ceascom.write(b'e')
                continue
        else:
            #ceas_blank(*tuple(params))
            try:
                ceas_blank(fig,ax1,ax2,*tuple(params))
            except Exception as e:
                print('Error running blank')
                print(e)
                ceascom.write(b'e')
                continue

        ceascom.write(b'd')
    except KeyboardInterrupt:
        print("Loop stopped by keyboard.")
        choice = input('R - Reload conf file. C - Change temp, M - Method. Otherwise will end:')
        if choice.lower() == 'r':
            import configurations as conf
            continue
        elif choice.lower() == 'c':
            newtemp = input('Set new camera temperature:')
            try:
                andor.prepare_temperature(sdk,int(newtemp))
            except Exception as e:
                print('Will exit due to following error:',e)
                break
        elif choice.lower() == 'm':
            method = input('Chose function refs (1 or 2):')
            refs = int(method)
            continue
        else:
            break
    except Exception as e:
        print('Loop ended by exception:')
        print(e)

############################## SHUTDOWN ##################################################
t1 = dt.datetime.now()
#np.save(path_file + "Im" + t1.strftime("%y%m%d%H%M"), measures)
#np.savetxt(path_file + "M" + t1.strftime('%y%m%d%H%M') + '.txt',
#            np.column_stack((meastime,ppbs,mfca_ps,mfca_ts,flag)), fmt='%s')

andor.shutdown_camera(sdk)
ceascom.close()
plt.close()
