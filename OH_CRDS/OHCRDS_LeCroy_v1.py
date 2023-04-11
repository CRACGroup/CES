#########################################################################################
# This program uses pyvisa to interface with a LeCroy Waverunner and with the SCANMATE 
# dye laser to grab an average of n sweeps and change wavelength.
# Fits Ring-Downs and shows fit and residuals
# Saves data to a text file
#
# Written by: Mixtli Campos on 21/03/2023
#
########################## IMPORT #######################################################

from pyvisa import constants,ResourceManager
from time import sleep
from scipy.optimize import least_squares
import numpy as np
import datetime as dt
import matplotlib.pyplot as plt
import matplotlib.animation as animation

######################### END IMPORT ####################################################

########################## PARAMETERS ###################################################

# Instument parameters
size = 4                        # the size of the HEX chunks to process the waveform
                                # depends on the precision, 2 for BYTE, 4 for WORD
                                # check COMM_FORMAT command for LeCroy instruments

scanmatevi = 'ASRL1::INSTR'     # pyvisa name for INSTR at serial COM1 
lecroyvi = 'GPIB5::1::INSTR'    # pyvisa name for INSTR at GPIB channel 1
                                # you can check them by the list.resources() method
                                # check pyvisa DOCS for further info

cycles = 10000                  # number of meas cycles before switching wavelength
wavemeas = 307.921              # wavelength for tau_sample
waveblank = 308                 # wavelength for tau_0

# Plot parameters
plot_limit_upper = .5           
plot_limit_lower = -1
res_plot_limit=.25

# Fitting parameters
len_offset = 300                # Length of baseline offset for logarithm fitting
start_fit = 600
end_fit = 5000
x0 = np.array([0,2,-50000])     # x0 for least_squares()

# Cycle parameters
sweeps = 30
runtime = 1.1 * (sweeps/10)

######################### END OF PARAMETERS #############################################

######################## FUNCTIONS ######################################################

def getFloat(res):
    '''
    Gets a splitted string response to a query and converts what it can to a float
    '''
    for ele in res:
        try:
            number=float(ele)
        except:
            pass
    return number

def getInt(res):
    '''
    Gets a splitted string response to a query and converts what it can to an integer
    '''
    for ele in res:
        try:
            number=int(ele)
        except:
            pass
    return number

def getChunks(hexes,size,vertgain,vertoff):
    '''
    Converts the waveform HEX DAT1 string to values by chunking the string,
    converting each chunk into HEX, then into big endian signed integers, and 
    then using the equation from the manual 
    V = Vertical Gain * INT + Vertical offset
    '''
    chunks = [hexes[i:i+size] for i in range(0,len(hexes),size)]
    #print(chunks)
    vals = []
    for ele in chunks:
        hhex = bytes.fromhex(ele)
        hint = int.from_bytes(hhex,byteorder='big',signed=True)
        #print(hint)
        vals.append(vertgain*hint+vertoff)
    return vals

def getWaveformParams(visa):
    '''
    Gets needed waveform parameters from a series of queries that are converted
    to integer or float depending on the parameters
    '''
    counts = getInt(visa.query('TA:INSPECT? \"WAVE_ARRAY_COUNT\"').split())
    print('Counts:',counts)

    vertgain = getFloat(visa.query('TA:INSPECT? \"VERTICAL_GAIN\"').split())
    print('Vertical gain:',vertgain)
    
    vertoff = getFloat(visa.query('TA:INSPECT? \"VERTICAL_OFFSET\"').split())
    print('Vertical offset:',vertoff)
    
    horint = getFloat(visa.query('TA:INSPECT? \"HORIZ_INTERVAL\"').split())
    print('Horizontal interval:',horint)
    
    horoff = getFloat(visa.query('TA:INSPECT? \"HORIZ_OFFSET\"').split())
    print('Horizontal offset:',horoff)

    return counts,vertgain,vertoff,horint,horoff

def waitReady(visa,sleept,timeout=5,verbose=0):
    '''
    Polls INR register to check if the bits adding to 257 (end of Trace A collection)
    it ends when the bit is polled or after a timeout. The time and number of calls is
    shown
    --- NOTE 11.04.2023 ---
    If the triggering is not 'just right', the status bit change WON'T be detected
    This function has been deprecated because of this reason. -Mixtli
    '''
    d=0
    c=0
    visa.write('*CLS')
    out = []
    t1 = dt.datetime.now()
    while ((c!=257) or (c<8448)) and (d< timeout/sleept):
        output=visa.query('INR?').split()
        try:
            c=getInt(output)
        except:
            pass
        if d%100 ==0:
            ttemp = dt.datetime.now()
            print(d, (ttemp-t1).total_seconds())
        if verbose !=0:
            print(output)
        d+=1
        sleep(sleept)

    print(c,d)
    t2 = dt.datetime.now()
    print((t2-t1).total_seconds())

def gendata(t,a,b,c):
    '''
    Generates the exponential fit
    '''
    return a+b*np.exp(t*c)

def funct(x,t,y):
    '''
    Function to fit with optimize.least_squares
    '''
    return x[0] + x[1]*np.exp(x[2]*t)-y

############################ END OF FUNCTIONS ###########################################

#### Resource initialization and opening

rm = ResourceManager()
#print(rm.list_resources()) ### uncomment to look at the names
lecroy = rm.open_resource(lecroyvi)
scanmate = rm.open_resource(scanmatevi,
                            stop_bits = constants.StopBits.two,
                            read_termination = '\r',
                            write_termination = '\r')

#### LeCroy setup
#lecroy.write('DISP OFF')   # uncomment to stop display
lecroy.write('COMM_HEADER OFF')
lecroy.write('COMM_FORMAT OFF,WORD,HEX')
lecroy.write('TA:DEF EQN,\'AVGS(C1)\',MAXPTS,100000,SWEEPS,%i' %sweeps)
#lecroy.write('CLM M1')     # clear memory M1

#### Good to go queries
print('LECROY:',lecroy.query('ALST?')) # ALL STATUS just to make sure it works
print('SCANMATE:',scanmate.query('S?')) # STATUS to make sure it gets R 

#### Waveform info
counts,vertgain,vertoff,horint,horoff = getWaveformParams(lecroy)
tdivs = np.arange(counts)*horint+horoff

#### Plot initialization
fig = plt.figure(figsize=(8,8))
gs = fig.add_gridspec(3,1)
ax1 = fig.add_subplot(gs[:-1,:])
ax2 = fig.add_subplot(gs[-1,:])
#ax1.get_xaxis().set_visible(False)
ax1.set_ylim([plot_limit_lower,plot_limit_upper])
ax2.set_ylim([-res_plot_limit,res_plot_limit])
ys=[0]*counts
line, = ax1.plot(tdivs[:-1],ys[:-1],'-k')
line1, = ax1.plot(tdivs[:-1],ys[:-1],'-g')
line2, = ax2.plot(tdivs[:-1],ys[:-1],'-r')
ax1.grid()
ax2.grid()

#### Begin measurements
## Moves to blank wavelength and sets check variable
scanmate.write('X=%.3f' %waveblank)
isblank = True

# Initializes lists
taus = []
tstamp = []
waveform = np.arange(counts-1)

## Resets the trace, waits for ready
ta = dt.datetime.now()
lecroy.write('TA:FRST')
tb = dt.datetime.now()
sleep(runtime - (tb-ta).total_seconds())
#waitReady(lecroy,0.01,timeout=3,verbose=0) ### Deprecated, problems with WaitReady()

## Main loop, stores to M1, resets trace, queries data, gets values, 
## fits paraments, gets residuals, waits for ready
## sends wavelength change to scanmate after n cycles
## is presented as a function for the animation class

def animate(i):
    global isblank, tau, tstamp, waveform
    print('RUN:',i+1)
    t1 = dt.datetime.now()
    lecroy.write('STO TA,M1')
    lecroy.write('TA:FRST')
    #lecroy.write('CLM M1')
    data = lecroy.query('M1:WF? DAT1').split()
    t2 = dt.datetime.now()
    print((t2-t1).total_seconds())
    values = getChunks(data[-1],size,vertgain,vertoff)
    line.set_ydata(values[:-1])
    waveform = np.array(values[:-1])
    
    # Prepare data for fitting
    ts=tdivs[start_fit:end_fit]
    ys=waveform[start_fit:end_fit]
    
    #### LEAST SQUARES
    
    # Levenberg - Marquardt
    #res_lsq = least_squares(fun,x0, method = 'lm', ftol=1e-12,xtol=1e-12,gtol=1e-12,
    #                       args=(ts,ys))

    # TRF
    res_log = least_squares(funct,x0, ftol=1e-12,xtol=1e-12,gtol=1e-12,
                            loss = 'cauchy', f_scale=0.1, args=(ts,ys))
    
    # The results
    xs = res_log.x
    #### END OF LEAST SQUARES
    
    #### NATURAL LOG
    # Fit the baseline and get a function
    #coef = np.polyfit(tdivs[:len_offset+1],values[:len_offset+1],1)
    #poly1d_fn = np.poly1d(coef)
    # Remove the baseline
    #offset_values = values[:-1]-poly1d_fn(tdivs[:-1])
    # Take the log
    #logs = np.log(offset_values[start_fit:end_fit])
    # Fit the log
    #coef2 = np.polyfit(tdivs[start_fit:end_fit],logs,1)
    # The results
    #xs = (coef[1],np.exp(coef2[1]),coef2[0])
    #### END OF NATURAL LOG

    #print(xs)              # in case you want to see the fit parameters
    
    # Shows and saves tau to a list, timestamps to list as well
    tau = -1e6/xs[2]
    taus.append(tau)
    timenow = dt.datetime.now()
    stamp = timenow.strftime('%Y/%m/%d-%H:%M:%S')
    tstamp.append(stamp)
    print('TAU is: %.2f' %tau)
    
    # Builds the fit = non fitted waveform + generated data from params
    fita = waveform[:start_fit]
    fitb = gendata(tdivs[start_fit:-1],*xs)
    fit = np.concatenate((fita,fitb))
    
    # Plot fit
    line1.set_ydata(fit)
    # Plot residuals
    line2.set_ydata(waveform-fit)
    
    # wavelength change
    if (i+1)% cycles == 0:
        if isblank:
            scanmate.write('X=%.3f' %wavemeas)
            isblank = False
        else:
            scanmate.write('X=%.3f' %waveblank)
            isblank = True
    # end 
    
    # Total computing time in cycle, rest will be sleeping
    t3 = dt.datetime.now()
    print((t3-t1).total_seconds())
    sleep(runtime-(t3-t1).total_seconds())
    #waitReady(lecroy,0.01) ### Deprecated due to problems with WaitReady()
    
    # Total cycle time
    t4 = dt.datetime.now()
    print((t4-t1).total_seconds())
    
    return line, line1, line2,

## The call for the function that acts instead of a loop
ani = animation.FuncAnimation(fig,animate,interval=1,
                              blit=True,
                              cache_frame_data=False)
plt.show()
####

#### Some outputs for testing
#print(len(values),data)
#print(values)

# Generates arrays to export to npy or txt
taumat = np.array(taus)
tstampmat = np.array(tstamp,dtype='U19')

# Saves NPY files
#np.save('taus.npy', taumat) ### The taus as npy
#np.save('waveform.npy',waveform) ### The last waveform as npy
#np.save('timestamps.npy',tstampmat) ### The timestamps as npy

# Saves TXT file: [timestamp tau]
np.savetxt('testdata.txt',np.column_stack((tstampmat,taumat)),fmt='%s')

### Some rough statistical data in case you want to know
print('Average TAU: %.2f' %np.average(taumat))
print('Stdev: %.2f' %np.std(taumat))


#### Close resources
lecroy.close()
scanmate.close()
