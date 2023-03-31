#########################################################################################
# This program uses pyvisa to interface with a LeCroy Waverunner and with the SCANMATE 
# dye laser to grab an average of n sweeps and change wavelength.
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

size = 4                        # the size of the HEX chunks to process the waveform
                                # depends on the precision, 2 for BYTE, 4 for WORD

scanmatevi = 'ASRL1::INSTR'     # pyvisa name for INSTR at serial COM1 
lecroyvi = 'GPIB5::1::INSTR'    # pyvisa name for INSTR at GPIB channel 1
                                # you can check them by the list.resources() method below

cycles = 10000                  # number of meas cycles before switching wavelength
wavemeas = 307.921              # wavelength for tau_sample
waveblank = 308                 # wavelength for tau_0

plot_limit_upper = .5            # y axis will go from value_lower to value_upper
plot_limit_lower = -1
res_plot_limit=.25
len_offset = 300
start_fit = 600
end_fit = 2250
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

def fun(x,y,t):
    return x[0] + x[1] * np.exp(x[2]*t) - y

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

taus = []
tstamp = []
waveform = np.arange(counts-1)


## Resets the trace, waits for ready
ta = dt.datetime.now()
lecroy.write('TA:FRST')
tb = dt.datetime.now()
sleep(runtime - (tb-ta).total_seconds())
#waitReady(lecroy,0.01,timeout=3,verbose=0)

## Main loop, stores to M1, resets trace, queries data, gets values, waits for ready
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
     
    coef = np.polyfit(tdivs[:len_offset+1],values[:len_offset+1],1)
    poly1d_fn = np.poly1d(coef)
    offset_values = values[:-1]-poly1d_fn(tdivs[:-1])
    #print(coef) 
    waveform = values[:-1]
    #### LEAST SQUARES
    #x0 = [0,offset_values[start_fit],-5]
    #print(x0) 
    # Levenberg - Marquardt
    #res_lsq = least_squares(fun,x0, method = 'lm',
    #                       ftol=1e-12,xtol=1e-12,gtol=1e-12,
    #                       args=(tdivs[551:-1],offset_values[551:]))

    # TRF
    #res_lsq = least_squares(fun,x0,
    #                      ftol=1e-12,xtol=1e-12,gtol=1e-12,
    #                      loss = 'cauchy', f_scale=0.1,
    #                      args=(tdivs[551:-1],offset_values[551:]))
    
    #xs = res_lsq.x
    #### END OF LEAST SQUARES
    
    #### NATURAL LOG
    logs = np.log(offset_values[start_fit:end_fit])
    coef2 = np.polyfit(tdivs[start_fit:end_fit],logs,1)
    #print(coef2)
    xs = [0,np.exp(coef2[1]),coef2[0]]
    #### END OF NATURAL LOG

    #print(xs)
    tau = -1e6/xs[2]
    taus.append(tau)
    timenow = dt.datetime.now()
    stamp = timenow.strftime('%Y/%m/%d-%H:%M:%S')
    tstamp.append(stamp)
    print('TAU is: %.2f' %tau)
    
    fita = offset_values[:start_fit]
    fitb = xs[0]+xs[1]*np.exp(xs[2]*tdivs[start_fit:-1]) 
    fit = np.concatenate((fita,fitb))
    
    line1.set_ydata(fit+poly1d_fn(tdivs[:-1]))
    #print(len(values),offset_values.shape,fita.shape,fitb.shape,fit.shape)
    line2.set_ydata(offset_values-fit)
    
    # wavelength change
    if (i+1)% cycles == 0:
        if isblank:
            scanmate.write('X=%.3f' %wavemeas)
            isblank = False
        else:
            scanmate.write('X=%.3f' %waveblank)
            isblank = True
    # end 
    
    t3 = dt.datetime.now()
    print((t3-t1).total_seconds())
    sleep(runtime-(t3-t1).total_seconds())
    #waitReady(lecroy,0.01)
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
taumat = np.array(taus)
tstampmat = np.array(tstamp,dtype='U19')
np.save('taus.npy', taumat)
np.save('waveform.npy',waveform)
np.save('timestamps.npy',tstampmat)
np.savetxt('testdata.txt',np.column_stack((tstampmat,taumat)),fmt='%s')
print('Average TAU: %.2f' %np.average(taumat))
print('Stdev: %.2f' %np.std(taumat))



#### Close resources
lecroy.close()
scanmate.close()
