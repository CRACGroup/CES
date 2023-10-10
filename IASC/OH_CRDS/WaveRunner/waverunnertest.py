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

cycles = 100                    # number of meas cycles before switching wavelength
wavemeas = 307.921              # wavelength for tau_sample
waveblank = 308                 # wavelength for tau_0

plot_limit_upper = .5            # y axis will go from value_lower to value_upper
plot_limit_lower = -1
res_plot_limit=.25
len_offset = 300
start_fit = 600
end_fit = 3000 
runtime = 2.2

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

#lecroy.write('CLM M1')     # clear memory M1

print(lecroy.query('TA:DEF?'))
lecroy.write('TA:DEF EQN, \'AVGS(C1)\',MAXPTS,100000,SWEEPS,30')
lecroy.write('TA:FRST')

lecroy.close()
scanmate.close()
