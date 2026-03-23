##### General libraries and appending path
import time,sys,subprocess,os
sys.path.append(u'C:\Advantech\DAQNavi\Examples\Python')

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import datetime as dt
from scipy.optimize import least_squares
from matplotlib.dates import DateFormatter
from pyvisa import ResourceManager

##### Automation functions
from Automation.BDaq import *
##### Pulse width modulator
from Automation.BDaq.PwModulatorCtrl import PwModulatorCtrl 
##### Analog output
from Automation.BDaq.InstantAoCtrl import InstantAoCtrl
##### Digital output
from Automation.BDaq.InstantDoCtrl import InstantDoCtrl
##### Analog Buffer Input
from Automation.BDaq.WaveformAiCtrl import WaveformAiCtrl

from Automation.BDaq.BDaqApi import AdxEnumToString, BioFailed, AdxGetValueRangeInformation

### Need to test if this is needed
###from Automation.BDaq.Utils import CreateArray

from CommonUtils import kbhit

############################## AI Polling function ##############################################
def AdvPollingOneBufferedAI_TDtpA():
    '''
    This is the triggered buffered analog input function that takes PMT signal at 5MS/s
    Comments have been removed but can be seen in the original from Automation or in the
    manual_control.py script
    '''
    ret = ErrorCode.Success
    wfAiCtrl = WaveformAiCtrl(deviceDescription)
    for _ in range(1):
        wfAiCtrl.loadProfile = profilePath   # Loads a profile to initialize the device
        wfAiCtrl.conversion.channelStart = aistartChannel
        wfAiCtrl.conversion.channelCount = aichannelCount
        wfAiCtrl.record.sectionCount = aisectionCount
        wfAiCtrl.record.sectionLength = aisectionLength
        trgCount = wfAiCtrl.features.triggerCount
        if triggerUsed == 0:
            if trgCount:
                wfAiCtrl.trigger[0].source = wfAiCtrl.features.getTriggerSources(0)[1]

                wfAiCtrl.trigger[0].action = triggerAction
                wfAiCtrl.trigger[0].delayCount = triggerDelayCount
                wfAiCtrl.trigger[0].edge = triggerEdge
                wfAiCtrl.trigger[0].level = triggerLevel
            else:
                print("The device can not supported trigger function!")
                break
        elif triggerUsed == 1:
            if trgCount > 1:
                wfAiCtrl.trigger[1].source = wfAiCtrl.features.getTriggerSources(1)[1]

                wfAiCtrl.trigger[1].action = trigger1Action
                wfAiCtrl.trigger[1].delayCount = trigger1DelayCount
                wfAiCtrl.trigger[1].edge = trigger1Edge
                wfAiCtrl.trigger[1].level = trigger1Level
            else:
                print("the trigger1 can not supported by the device!")
                break

        ret = wfAiCtrl.prepare()
        if BioFailed(ret):
            break

        ret = wfAiCtrl.start()
        if BioFailed(ret):
            break

        result = wfAiCtrl.getDataF64(USER_BUFFER_SIZE, -1)  
        # The timeout value is -1, meaning infinite waiting
        ret, returnedCount, data, = result[0], result[1], result[2]
        if BioFailed(ret):
            break

        delayCount = wfAiCtrl.trigger[triggerUsed].delayCount
        triggerPointIndex = returnedCount // aichannelCount - delayCount
        ret = wfAiCtrl.stop()

    wfAiCtrl.dispose()

    if BioFailed(ret):
        enumStr = AdxEnumToString("ErrorCode", ret.value, 256)
        print("Some error occurred. And the last error code is %#x. [%s]" % (ret.value, 
                                                                             enumStr))
    return data


def AdvPollingOneBufferedAI_TDtp():
    ret = ErrorCode.Success

    # Step 1: Create a 'WaveformAiCtrl' for buffered AI function
    # Select a device by device number pr device description and specify the access mode.
    # In this example we use ModeWrite mode so that we can use fully control the device,
    # including configuring, sampling, etc
    wfAiCtrl = WaveformAiCtrl(deviceDescription)
    for _ in range(1):
        wfAiCtrl.loadProfile = profilePath   # Loads a profile to initialize the device

        # Step 2: Set necessary parameters
        # get the Conversion instance and set the start channel and scan channel number
        wfAiCtrl.conversion.channelStart = aistartChannel
        wfAiCtrl.conversion.channelCount = aichannelCount

        # Set record count and section length
        # This sectionCount is nonzero value, which means 'One Buffered' Mode
        wfAiCtrl.record.sectionCount = aisectionCount
        wfAiCtrl.record.sectionLength = aisectionLength

        # Step 3: Trigger parameters setting
        trgCount = wfAiCtrl.features.triggerCount
        # for trigger0
        if triggerUsed == 0:
            if trgCount:
                #################################################################
                # The different kinds of devices have different trigger source. The details see manual.
                # In this example, we use the DemoDevice and set 'AI channel 0' as the default trigger source
                wfAiCtrl.trigger[0].source = wfAiCtrl.features.getTriggerSources(0)[1] # To DemoDevice, the 1 means 'AI channel 0'

                wfAiCtrl.trigger[0].action = triggerAction
                wfAiCtrl.trigger[0].delayCount = triggerDelayCount
                wfAiCtrl.trigger[0].edge = triggerEdge
                wfAiCtrl.trigger[0].level = triggerLevel
            else:
                print("The device can not supported trigger function!")
                break
        elif triggerUsed == 1:
            if trgCount > 1:
                wfAiCtrl.trigger[1].source = wfAiCtrl.features.getTriggerSources(1)[1]

                wfAiCtrl.trigger[1].action = trigger1Action
                wfAiCtrl.trigger[1].delayCount = trigger1DelayCount
                wfAiCtrl.trigger[1].edge = trigger1Edge
                wfAiCtrl.trigger[1].level = trigger1Level
            else:
                print("the trigger1 can not supported by the device!")
                break

        # Step 4: The operation has been started
        #print("Polling finite acquisition is in progress!")
        ret = wfAiCtrl.prepare()
        if BioFailed(ret):
            break

        ret = wfAiCtrl.start()
        if BioFailed(ret):
            break

        # Step 5: GetDate with Polling Style
        result = wfAiCtrl.getDataF64(USER_BUFFER_SIZE, -1)  # The timeout value is -1, meaning infinite waiting
        ret, returnedCount, data, = result[0], result[1], result[2]
        if BioFailed(ret):
            break

        #if ret == ErrorCode.Success or ret == ErrorCode.WarningFuncStopped:
            #print("The first sample each channel are:")
            #for i in range(channelCount):
                #print("channel %d: %s" % (i + startChannel, data[i]))

        delayCount = wfAiCtrl.trigger[triggerUsed].delayCount
        triggerPointIndex = returnedCount // aichannelCount - delayCount
        #print("trigger point each channel: %d" % triggerPointIndex)
        #print("Acquisition has completed!")
        #plt.plot(data[500:700])
        #plt.show()
        # Step 6: stop the operation if it is running
        ret = wfAiCtrl.stop()

    # Step 7: close device, release any allocated resource before quit
    wfAiCtrl.dispose()

    # If something wrong in this execution, print the error code on screen for tracking
    if BioFailed(ret):
        enumStr = AdxEnumToString("ErrorCode", ret.value, 256)
        print("Some error occurred. And the last error code is %#x. [%s]" % (ret.value, enumStr))
    return data
####################################################################################################
######################## CRDS analysis and LeCroy functions ##############################
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
        vals.append(vertgain*hint-vertoff)
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

def funct(x,t,y):
    return x[0]+x[1]*np.exp(x[2]*t)-y

def gendata(t,a,b,c):
    return a+b*np.exp(t*c)
########## Initialize COM3 (LeCroy) as VI
## Cycle parameters
sweeps = 1000
runtime = 6 * (sweeps/1000) + 4
size=4

## Start and configure LeCroy VI
rm = ResourceManager()
lecroy = rm.open_resource('ASRL3::INSTR',
                          baud_rate=112500,
                            #stop_bits = constants.StopBits.two,
                            read_termination = 'fin',
                            write_termination = '\r',
                         )
lecroy.write("CORS EO,\'fin\'")
lecroy.write('CHDR OFF')
lecroy.write('COMM_FORMAT OFF,WORD,HEX')
lecroy.write('TA:DEF EQN,\'AVGS(C1)\',MAXPTS,100000,SWEEPS,%i' %sweeps)
lecroy.write('ACAL OFF')

## dirty way to flush the buffer
for i in range(1000):
    try:
        tempmes = lecroy.read()
    except:
        print("LC COM3 Buffer clear")
        break

## Waveform info
counts,vertgain,vertoff,horint,horoff = getWaveformParams(lecroy)
tdivs = np.arange(counts)*horint+horoff

# Fitting parameters
lc_len_offset = 300                # Length of baseline offset for logarithm fitting
lc_start_fit = 600
lc_end_fit = 5000
lc_x0 = np.array([0,2,-50000])     # x0 for least_squares()

##### Device description and profile
deviceDescription = "MIC-1816,BID#15"
profilePath = r"C:\Users\LSG-DAQ\Documents\DAQPython\MIC1816.xml"

##### Channel definitions
## Pulse width modulator (TTL for diode)
pulsehigh = 1e-3
pulselow = 1e-3
pwchannelStart = 0
pwchannelCount = 1

## Analog output 
aochannelStart = 0
aochannelCount = 2
voltage1 = 0.0
voltage2 = 0.0

## Digital output
dostartPort = 0
doportCount = 1
number = 0

## Buffered Analog Input
aistartChannel = 0
aichannelCount = 1
aisectionLength = 1950
aisectionCount = 1

# user buffer size should be equal or greater than raw data buffer length, because data ready count
# is equal or more than smallest section of raw data buffer and up to raw data buffer length.
# users can set 'USER_BUFFER_SIZE' according to demand.
USER_BUFFER_SIZE = aichannelCount * aisectionLength * aisectionCount

# Set trigger parameters
triggerAction = TriggerAction.DelayToStop
triggerEdge = ActiveSignal.RisingEdge
triggerDelayCount = 1950
triggerLevel = 1
x_end = 1500
x_start = 950
x_len = x_end-x_start             # this is the number of points to display
y_lower = -.5
y_upper = 0
shots = 50
len_offset = 100
start_fit = 1010
end_fit = 1150
x0 = np.array([.01,.2,-1])
timezero = (pulsehigh*5e6-x_start)*.2


# Set trigger1 parameters
trigger1Action = TriggerAction.DelayToStop
trigger1Edge = ActiveSignal.RisingEdge
trigger1DelayCount = 1000
trigger1Level = 2.0

# set which trigger be used for this demo, trigger0(0) or trigger1(1)
triggerUsed = 0


################ OPERATION ##########
###### PWM Enable
pulseWidth = PulseWidth(pulsehigh, pulselow)
# Step 1: Create a 'PmModulatorCtrl' for PWMOutput function
pmModulatorCtrl = PwModulatorCtrl(deviceDescription)
pmModulatorCtrl.loadProfile = profilePath   # Load a profile to initialize the device
# get channel max num for PWMOutput
channelCountMax = pmModulatorCtrl.features.channelCountMax
# set start channel num and channel count for PWMOutput
pmModulatorCtrl.channelStart = pwchannelStart
pmModulatorCtrl.channelCount = pwchannelCount
# set pulseWidth value
for i in range(pwchannelStart, pwchannelStart + pwchannelCount):
    pmModulatorCtrl.channels[i % channelCountMax].pulseWidth = pulseWidth
# Step 4: start PWMOutput
pmModulatorCtrl.enabled = False
statusPWM = 'PWM is OFF.'

##### Analog output Enable
instantAo = InstantAoCtrl(deviceDescription)
instantAo.loadProfile = profilePath
ret = instantAo.writeAny(aochannelStart, aochannelCount, None,[voltage1,voltage2])
statusAOPump = 'Pump AO is set to %.2f V.' %voltage1
statusAOPMT = 'PMT AO is set to %.2f V.' %voltage2

##### Digital output Enable
instantDo = InstantDoCtrl(deviceDescription)
instantDo.loadProfile = profilePath
ret = instantDo.writeAny(dostartPort, doportCount, [number])
statusDO = 'DO set to ' + f'{number:08b}'

n = True
 
while n:
    print("\nSystem status is:")
    print(statusPWM,statusAOPump,statusAOPMT,statusDO)
    print("\nA - Switch PWN ON/OFF. B - Pump Voltage. C - PMT Voltage. D - Change DO. E - CRDS. F - Shutdown\n")
    option = input("Please choose action: ")
    #print(option.lower())
    match option.lower():
        case 'a':
            if pmModulatorCtrl.enabled:
                pmModulatorCtrl.enabled = False
                statusPWM = 'PWM is OFF.'
            else:
                pmModulatorCtrl.enabled = True
                statusPWM = 'PWM is ON.'
            print(statusPWM)
        case 'b':
            voltagestr = input("Please input new voltage:")
            try:
                voltage1 = float(voltagestr)
                if (voltage1 >= 0) and (voltage1 <= 10):
                    ret = instantAo.writeAny(aochannelStart, aochannelCount, None,[voltage1,voltage2])
                    statusAOPump = 'Pump AO is set to %.2f V.' %voltage1
                else:
                    print("Wrong number, try again ...")
            except:
                print("Something happened, are you ok?")
            print(statusAOPump)
        case 'c':
            voltagestr = input("Please input new voltage:")
            try:
                voltage2 = float(voltagestr)
                if (voltage2 >= 0) and (voltage2 <= 1):
                    ret = instantAo.writeAny(aochannelStart, aochannelCount, None,[voltage1,voltage2])
                    statusAOPMT = 'PMT AO is set to %.2f V.' %voltage2
                else:
                    print("Wrong number, try again ...")
            except:
                print("Something happened, are you ok?")
            print(statusAOPMT)
        case 'd':
            numberstr = input("Please input new DO number:")
            try:
                number = int(numberstr)
                if (number >= 0) and (number < 256):
                    ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'
                else:
                    print("Wrong number, try again...")
            except:
                print('Something happened, are you ok?')
            print(statusDO)
        case 'e':
            taus = []
            xs = tdivs[:-1]
            ys = [0]*(counts-1)            
            #print('Defining function')
            pid = subprocess.Popen(["python","manual_control_plotter.py"]).pid

            ## Resets the trace, waits for ready
            ta = dt.datetime.now()
            lecroy.write('TA:FRST')
            tb = dt.datetime.now()
            time.sleep(runtime - (tb-ta).total_seconds())

            while True:
                try:
                    with open('endme','r') as f:
                        read=f.read()
                    os.remove("endme")
                    break

                except:
                    pass
    
                t1 = dt.datetime.now()
                lecroy.write('STO TA,M1')
                lecroy.write('TA:FRST')
                #lecroy.write('CLM M1')
                data = lecroy.query('M1:WF? DAT1').split()
                t2 = dt.datetime.now()
                print((t2-t1).total_seconds())
                values = getChunks(data[-1],size,vertgain,vertoff)
                waveform = np.array(values[:-1])

                xfit = xs[lc_start_fit:lc_end_fit]
                yfit = waveform[lc_start_fit:lc_end_fit]
                ##################TRF
                res_log = least_squares(funct,lc_x0,ftol=1e-12,xtol=1e-12,gtol=1e-12,
                                            loss='cauchy',f_scale=0.1,args=(xfit,yfit))
                xres=res_log.x
                ##################
                ##################NaturalLOG
                #### NEED TO REVIEW THIS ONE
                #coef = np.polyfit(xs[-lc_len_offset:],waveform[-lc_len_offset:],1)
                #poly1d_fn = np.poly1d(coef)
                #offset_values = waveform[:-1]-poly1d_fn(xs[:-1])-bckg_crds_lc
                #logs = np.log(-offset_values[lc_start_fit:lc_end_fit])
                #coef2 = np.polyfit(xs[start_fit-x_start:end_fit-x_start],logs,1)
                #xres = (-coef[1],np.exp(coef2[1]),coef2[0])
                ###########################
                
                fita = waveform[:lc_start_fit]
                fitb = gendata(xs[lc_start_fit:],*xres)
                fit = np.concatenate((fita,fitb))
                #print(xres)
                #scan = AdvPollingOneBufferedAI_TDtp()    
                #dataset = scan[:x_len]
                #print('sending to line')
                np.save("ax1data",np.column_stack((xs,waveform)))
                np.save("ax1adata",np.column_stack((xs,fit)))
                np.save("ax2data",np.column_stack((xs,waveform-fit)))
                
                #line.set_ydata(np.log(-dataset))
                #line2.set_ydata(np.log(-fit))
                #ax1.set_ylim([np.min(np.log(-dataset)),np.max(np.log(-dataset))])

                tau=-1e6/xres[2]
                taus.append(tau)
                print('TAU is: %.2f' %tau)
                #print(tau)
                # Total computing time in cycle, rest will be sleeping
                t3 = dt.datetime.now()
                print((t3-t1).total_seconds())
                time.sleep(runtime-(t3-t1).total_seconds())

                #print(c)

            taumat = np.array(taus)
            timenow = dt.datetime.now()
            np.save('tau'+timenow.strftime('%y%m%d%H%M'),taumat)

            print('Average TAU: %.2f' %np.average(taumat))
            print('Stdev: %.2f' %np.std(taumat))

        case 'f':
            n = False
            print("Will shutdown. Bye")
        case _:
            print("Invalid option, try again...")

#print("Any key to quit !")
#while not kbhit():
#    time.sleep(1)

############################# SHUTDOWN ###########################
##### Analog output disable
ret = instantAo.writeAny(aochannelStart, aochannelCount, None,[0,0])
instantAo.dispose()

##### Digital output disable
ret = instantDo.writeAny(dostartPort, doportCount, [0])
instantDo.dispose()

##### PWM Disable
pmModulatorCtrl.enabled = False
pmModulatorCtrl.dispose()

