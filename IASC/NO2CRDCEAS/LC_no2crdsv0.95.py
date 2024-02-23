##########################################################################################
# NO2 CRD instrument program, designed to use a MIC1816 for "housekeeping"
# (valves, MFCs, shutters, ttl, &c.), and measure CRD decay times from a LeCroy osc.
#
# Written by Dr. Mixtli Campos in August 2023. Adapted from NO2CRDCEASv0.95.py
##########################################################################################

########## General libraries and appending path
import time,sys,serial,os
sys.path.append(u'C:\Advantech\DAQNavi\Examples\Python')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
import datetime as dt
from scipy.optimize import least_squares
from matplotlib.dates import DateFormatter
from pyvisa import ResourceManager

########## MIC1816 wrapper functions
##### Automation functions
from Automation.BDaq import *
from Automation.BDaq.BDaqApi import AdxEnumToString,BioFailed,AdxGetValueRangeInformation
##### Pulse width modulator
from Automation.BDaq.PwModulatorCtrl import PwModulatorCtrl 
##### Analog output
from Automation.BDaq.InstantAoCtrl import InstantAoCtrl
##### Digital output
from Automation.BDaq.InstantDoCtrl import InstantDoCtrl
##### Analog Buffer Input
from Automation.BDaq.WaveformAiCtrl import WaveformAiCtrl


############################## AI Polling function #######################################
def AdvPollingOneBufferedAI_TDtp():
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
######################## END of AI Polling function ######################################
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

######################## Housekeeping functions     ######################################
def mfc_poll(mfc,mfccom):
    msg_out = mfc + '\r'
    mfccom.write(bytes(msg_out,'utf-8'))
    time.sleep(mfcping)
    msg_in = mfccom.read(mfccom.in_waiting).decode('utf-8')
    mfc_str = msg_in.split(' ')
    return mfc_str


######################## INITIALIZATION ##################################################
parent = 'c:\\CRAC\\Data\\Instruments\\NO2_CRDS'
directory = dt.datetime.now().strftime('%Y%m%d')
path = os.path.join(parent,directory)
try:
    os.mkdir(path)
except:
    pass
path_file = path + '\\'

taus = []
meastime = []
meastime2 = []
flag = []
pPSI = []
tC = []
mfca_mf = []
mfcf_mf = []
Reff_scale = []
ppbs = []

########## Initialize COM2 (MFC) port
mfccom = serial.Serial('COM2',19200)
mfcping = 0.25       # buffer time for send/receive MFC

########## Initialize COM3 (LeCroy) as VI
## Cycle parameters
sweeps = 1000
runtime = 6 * (sweeps/1000) + 2
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

########## Initialize DAQ
##### Device description and profile
deviceDescription = "MIC-1816,BID#15"
profilePath = r"C:\Users\LSG-DAQ\Documents\DAQPython\MIC1816.xml"

##### Channel definitions
## Pulse width modulator (TTL for diode)
pulsehigh = 400e-6   # Pulse high time in seconds
pulselow = 600e-6   # Pulse low time in seconds
pwchannelStart = 0
pwchannelCount = 1

## Analog output 
aochannelStart = 0
aochannelCount = 2
voltage1 = 0.0          # Initial for pump
voltage2 = 0.0          # Initial for pmt

## Digital output
dostartPort = 0
doportCount = 1
number = 0              # Initial for valves
zeroair = 1             # normally closed
sampleclose = 2         # normally open
shutter = 4

## Buffered Analog Input
aistartChannel = 0
aichannelCount = 1
aisectionLength = 4000   # keep same as delaycount
aisectionCount = 1
USER_BUFFER_SIZE = aichannelCount * aisectionLength * aisectionCount
triggerAction = TriggerAction.DelayToStop
triggerEdge = ActiveSignal.RisingEdge
triggerDelayCount = 4000 # keep same as section length
triggerLevel = 1
x_end = 2500
x_start = 1950
x_len = x_end-x_start             # this is the number of points to display
y_lower = -.3
y_upper = 0
shots = 50                      # number of shots to average
len_offset = 100
start_fit = 2010
end_fit = 2150
x0 = np.array([.01,.2,-1])
timezero = (pulsehigh*5e6-x_start)*.2 
triggerUsed = 0

########## Initialize operation
###### PWM Enable
pulseWidth = PulseWidth(pulsehigh, pulselow)
pmModulatorCtrl = PwModulatorCtrl(deviceDescription)
pmModulatorCtrl.loadProfile = profilePath   # Load a profile to initialize the device
channelCountMax = pmModulatorCtrl.features.channelCountMax
pmModulatorCtrl.channelStart = pwchannelStart
pmModulatorCtrl.channelCount = pwchannelCount
for i in range(pwchannelStart, pwchannelStart + pwchannelCount):
    pmModulatorCtrl.channels[i % channelCountMax].pulseWidth = pulseWidth
pmModulatorCtrl.enabled = True
statusPWM = 'PWM is ON.'

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

##### MFC initialization, A and F
##### Alicat MFCs finalize commands with <CR>
mfccom.write(b'a\r')
time.sleep(mfcping)
statusMFCA = mfccom.read(mfccom.in_waiting).decode('utf-8')
time.sleep(mfcping)
mfccom.write(b'f\r')
time.sleep(mfcping)
statusMFCF = mfccom.read(mfccom.in_waiting).decode('utf-8')

##### Initialize dummy scenario 
accums = exposure = '1'
shots_bckg = shots_zero = shots_meas =10
shots_bckg_crds = shots_zero_crds = shots_meas_crds = 10
cycles = cyclescrds = 2


####################################### OPERATION ########################################
mainloop = True
controlloop = False
lccrdsloop = False
crdsloop = False
while mainloop:
    print("\nSystem status is:")
    print(statusPWM,statusAOPump,statusAOPMT,statusDO)
    print("\nA - Set scenario. B - Start DAQ-CRDS. C - Start LC-CRDS.",
          "D - Manual Control. X - Shutdown\n")
    option = input("Please choose action: ")
    #print(option.lower())
    match option.lower():
        case 'a':
            scenario = input('Please set scenario or Z to input custom:')
            match scenario.lower():
                case 'a':
                    print('Scenario A chosen.')
                    # Must be strings
                    accums = '1' 
                    exposure = '5' 
                    shots_bckg = 15
                    shots_zero = 15
                    shots_meas = 300
                    shots_bckg_crds = 15
                    shots_zero_crds = 15
                    shots_meas_crds = 300
                    cycles = 10
                    cyclescrds = 10
                case 'b':
                    print('Scenario B chosen')
                    accums = '1' 
                    exposure = '5' 
                    shots_bckg = 15
                    shots_zero = 15
                    shots_meas = 300
                    shots_bckg_crds = 15
                    shots_zero_crds = 15
                    shots_meas_crds = 300
                    cycles = 5
                    cyclescrds = 5
                    # d
                case 'c':
                    print('Scenario C chosen')
                    accums = '1' 
                    exposure = '5' 
                    shots_bckg = 15
                    shots_zero = 15
                    shots_meas = 300
                    shots_bckg_crds = 15
                    shots_zero_crds = 15
                    shots_meas_crds = 300
                    cycles = 3
                    cyclescrds = 3

                    # d
                case 'z':
                    msgz1 = 'Input conditions '
                    msgz2 = '(Accums,Exposure,#B-CEAS,#Z-CEAS,#M-CEAS,'+ \
                            '#B-CRDS,#Z-CRDS,#M-CRDS,#Cycles,#CyclesCRDS):'
                    msgz=msgz1+msgz2
                    conditions = input(msgz)
                    params = conditions.split(',')
                    accums = params[0]
                    exposure = params[1]
                    shots_bckg = int(params[2])
                    shots_zero = int(params[3])
                    shots_meas = int(params[4])
                    shots_bckg_crds = int(params[5])
                    shots_zero_crds = int(params[6])
                    shots_meas_crds = int(params[7])
                    cycles = int(params[8])
                    cyclescrds = int(params[9])
                    print('Custom conditions:',accums,exposure,shots_bckg,shots_zero,
                          shots_meas,shots_bckg_crds,shots_zero_crds,shots_meas_crds,
                          cycles,cyclescrds)
                case _:
                    print('Invalid option, try again...')
        case 'b':
            plt.close()
            confirmcrds = input('Please confirm DAQ-CRDS mode (Y/N)')
            if confirmcrds.lower() == 'y':
                crdsloop = True
            else:
                print('Exiting CRDS mode.')
            #pmModulatorCtrl.enabled = True
            #statusPWM = 'PWM is ON.'

            while crdsloop:
                print('Switching valves for background measurement (Shutter ON):')
                ret = instantDo.writeAny(dostartPort, doportCount, 
                                         [shutter+zeroair+sampleclose])
                statusDO = 'DO set to ' + f'{shutter+zeroair+sampleclose:08b}'
                time.sleep(1)
                #input('Press any key to collect background.')
                plt.ion()
                fig = plt.figure(figsize=(15,6))
                gs = fig.add_gridspec(3,3)
                ax1 = fig.add_subplot(gs[:-1,0])
                ax1a = fig.add_subplot(gs[-1,0])
                ax2 = fig.add_subplot(gs[:-1,1])
                ax2a = fig.add_subplot(gs[-1,1])
                ax3 = fig.add_subplot(gs[:-1,2])
                ax4 = fig.add_subplot(gs[-1,2])
                #ax1.set_ylim([0.06,-y_lower])
                #ax2.set_ylim([-.05,.05])
                ax1a.set_xlabel('$\mu$s')
                ax2a.set_xlabel('$\mu$s')
                ax4.set_xlabel('Time')
                ax1.set_ylabel('Voltage')
                
                xs = np.array([x*.2 for x in range(0,x_len)])-timezero
                ys = [0]*x_len
                
                #ax1.plot(xs,ys,'-k')
                #ax1.plot(xs,ys,'-g')
                #ax2.plot(xs,ys,'-r')
                ax1.grid()
                ax1a.grid()
                ax2.grid()
                ax2a.grid()
                ax3.grid()
                ax4.grid()


                measurements = np.array(ys).reshape(len(ys),1)
                for n in range(shots_bckg_crds):
                    data = np.zeros(triggerDelayCount)
                    c = 0
                    for i in range(shots):
                        scan = AdvPollingOneBufferedAI_TDtp()
                        try:
                            data = np.add(data,scan)
                        except:
                            #print('error when polling')
                            c+=1
                            pass

                    dataset = data[x_start:x_end]/(shots-c)
                    ######
                    # This is the background, so here we should average the 
                    # dataset vector to obtain the background voltage
                    #
                    ######
                    bckg_crds = np.average(dataset)
                    measurements = np.concatenate((measurements, 
                                                   dataset.reshape(len(dataset),1)),
                                                  axis=1)
                    #scan = AdvPollingOneBufferedAI_TDtp()    
                    #dataset = scan[:x_len]
                    ax3.cla()
                    ax3.plot(xs,dataset,'-k')
                    ax3.grid()
                    #fig.canvas.draw()
                    fig.canvas.flush_events()
                    #print(c)
                t1 = dt.datetime.now()
                np.save(path_file+'Cb'+t1.strftime('%y%m%d%H%M'),measurements)
                
                print('Background collected.')

                for m in range(cyclescrds):
                    print('Switching valves for zero measurement (Shutter OFF).')
                    ret = instantDo.writeAny(dostartPort, doportCount, 
                                             [zeroair+sampleclose])
                    statusDO = 'DO set to ' + f'{zeroair+sampleclose:08b}'
                    time.sleep(5)
                    ys = [0]*x_len
                    taus_zero = []
                    pres_zero = []
                    tem_zero = []
                    measurements = np.array(ys).reshape(len(ys),1)
            
                    for n in range(shots_zero_crds):
                        data = np.zeros(triggerDelayCount)
                        c = 0
                        for i in range(shots):
                            scan = AdvPollingOneBufferedAI_TDtp()
                            try:
                                data = np.add(data,scan)
                            except:
                                #print('error when polling')
                                c+=1
                                pass

                        dataset = data[x_start:x_end]/(shots-c)
                        measurements = np.concatenate((measurements, 
                                                       dataset.reshape(len(dataset),1)),
                                                        axis=1)
                        #scan = AdvPollingOneBufferedAI_TDtp()    
                        #dataset = scan[:x_len]
                        #savename = 'dataset%i' % i
                        #np.save(savename,dataset)
                        xfit = xs[start_fit-x_start:]
                        yfit = -dataset[start_fit-x_start:]
                        ##################TRF
                        res_log = least_squares(funct,x0,ftol=1e-12,xtol=1e-12,gtol=1e-12,
                                            loss='cauchy',f_scale=0.1,args=(xfit,yfit))
                        xres=res_log.x
                        ##################
                        ##################NaturalLOG
                        #coef = np.polyfit(xs[-len_offset:],dataset[-len_offset:],1)
                        #poly1d_fn = np.poly1d(coef)
                        #offset_values = dataset[:-1]-poly1d_fn(xs[:-1])-bckg_crds
                        #logs = np.log(-offset_values[start_fit-x_start:end_fit-x_start])
                        #coef2 = np.polyfit(xs[start_fit-x_start:end_fit-x_start],logs,1)
                        #xres = (-coef[1],np.exp(coef2[1]),coef2[0])
                        ###########################
                
                        fita = dataset[:start_fit-x_start]
                        fitb = -gendata(xs[start_fit-x_start:],*xres)
                        fit = np.concatenate((fita,fitb))

                        #scan = AdvPollingOneBufferedAI_TDtp()    
                        #dataset = scan[:x_len]
                        #print('sending to line')
                        #line.set_ydata(dataset)
                        #line2.set_ydata(fit)
                        #line3.set_ydata(dataset-fit)
                
                        #line.set_ydata(np.log(-dataset))
                        #line2.set_ydata(np.log(-fit))
                        #ax1.set_ylim([np.min(np.log(-dataset)),np.max(np.log(-dataset))])
                        mfca_poll = mfc_poll('a',mfccom)
                        mfcf_poll = mfc_poll('f',mfccom)
                        pres = float(mfca_poll[1])
                        tem = float(mfca_poll[2])
                        mfca_mfl = float(mfca_poll[4])
                        mfcf_mfl = float(mfcf_poll[4])
                        tau=-1/xres[2]
                        ppbs.append(0)
                        taus.append(tau)
                        taus_zero.append(tau)
                        flag.append(0)
                        pPSI.append(pres)
                        pres_zero.append(pres)
                        tC.append(tem)
                        tem_zero.append(tem)
                        mfca_mf.append(mfca_mfl)
                        mfcf_mf.append(mfcf_mfl)
                        timenow = dt.datetime.now()
                        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
                        meastime2.append(timenow)
                        print('TAU is: %.2f' %tau)
                        
                        ax1.cla()
                        ax1a.cla()
                        ax4.cla()
                        ax1.plot(xs,dataset,'-k')
                        ax1.plot(xs,fit,'-g')
                        ax1a.plot(xs,dataset-fit,'-r')
                        ax4.plot(meastime2,ppbs,'-b')
                        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
                        ax1.grid()
                        ax1a.grid()
                        ax4.grid()
                        #fig.canvas.draw()
                        fig.canvas.flush_events()
                        #print(c)
                    
                    t1 = dt.datetime.now()
                    taus_zero_mat = np.array(taus_zero)
                    pres_zero_mat = np.array(pres_zero)
                    tem_zero_mat = np.array(tem_zero)
                    taus_zero_avg = np.average(taus_zero_mat[8:])
                    pres_zero_avg = np.average(pres_zero_mat[8:])
                    tem_zero_avg = np.average(tem_zero_mat[8:])
                    Reff_scale.append(1-(47/(taus_zero_avg*29979.2458)))
                    np.save(path_file+'Cz'+t1.strftime('%y%m%d%H%M'),measurements)
                    np.savetxt(path_file + 'MCtemp.txt',
                                np.column_stack((meastime,ppbs,taus,pPSI,tC,mfca_mf,
                                                 mfcf_mf,flag)), fmt='%s')
                    np.savetxt(path_file+'Reff_scale.txt',Reff_scale,fmt='%s')
                    
                    #plt.close('all')
                    #plt.ioff()


                    print('Switching valves for sample measurement.')
                    number=0
                    ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'
                    time.sleep(5)
                    
                    ys = [0]*x_len
                    measurements = np.array(ys).reshape(len(ys),1)
                    
                    for n in range(shots_meas_crds):
                        data = np.zeros(triggerDelayCount)
                        c = 0
                        for i in range(shots):
                            scan = AdvPollingOneBufferedAI_TDtp()
                            try:
                                data = np.add(data,scan)
                            except:
                                #print('error when polling')
                                c+=1
                                pass

                        dataset = data[x_start:x_end]/(shots-c)
                        measurements = np.concatenate((measurements, 
                                                       dataset.reshape(len(dataset),1)),
                                                        axis=1)
                        #scan = AdvPollingOneBufferedAI_TDtp()    
                        #dataset = scan[:x_len]
                        #savename = 'dataset%i' % i
                        #np.save(savename,dataset)
                        xfit = xs[start_fit-x_start:]
                        yfit = -dataset[start_fit-x_start:]
                        ##################TRF
                        res_log = least_squares(funct,x0,ftol=1e-12,xtol=1e-12,gtol=1e-12,
                                            loss='cauchy',f_scale=0.1,args=(xfit,yfit))
                        xres=res_log.x
                        ##################
                        ##################NaturalLOG
                        #coef = np.polyfit(xs[-len_offset:],dataset[-len_offset:],1)
                        #poly1d_fn = np.poly1d(coef)
                        #offset_values = dataset[:-1]-poly1d_fn(xs[:-1])-bckg_crds
                        #logs = np.log(-offset_values[start_fit-x_start:end_fit-x_start])
                        #coef2 = np.polyfit(xs[start_fit-x_start:end_fit-x_start],logs,1)
                        #xres = (-coef[1],np.exp(coef2[1]),coef2[0])
                        ###########################
                
                        fita = dataset[:start_fit-x_start]
                        fitb = -gendata(xs[start_fit-x_start:],*xres)
                        fit = np.concatenate((fita,fitb))

                        #scan = AdvPollingOneBufferedAI_TDtp()    
                        #dataset = scan[:x_len]
                        #print('sending to line')
                        #line.set_ydata(dataset)
                        #line2.set_ydata(fit)
                        #line3.set_ydata(dataset-fit)
                
                        #line.set_ydata(np.log(-dataset))
                        #line2.set_ydata(np.log(-fit))
                        #ax1.set_ylim([np.min(np.log(-dataset)),np.max(np.log(-dataset))])

                        tau=-1/xres[2]
                        mfca_poll = mfc_poll('a',mfccom)
                        mfcf_poll = mfc_poll('f',mfccom)
                        pres = float(mfca_poll[1])
                        tem = float(mfca_poll[2])
                        mfca_mfl = float(mfca_poll[4])
                        mfcf_mfl = float(mfcf_poll[4])
                        ext = (1.064/29979.2458)*((1/tau)-(1/taus_zero_avg))
                        pPa = 6894.757293 * pres
                        tK = 273.15 + tem
                        pzPa = 6894.757293 * pres_zero_avg
                        tzK = 273.15 + tem_zero_avg
                        delta_ext = (1.5765e-26/1.38066e-17)*((pPa/tK)-(pzPa/tzK))
                        print(delta_ext)
                        print(ext)
                        ppb = ((ext-delta_ext)/6.308459e-19)*(1e15*1.380649e-23*tK/pPa)
                        ppbs.append(ppb)
                        pPSI.append(pres)
                        tC.append(tem)
                        taus.append(tau)
                        flag.append(0)
                        mfca_mf.append(mfca_mfl)
                        mfcf_mf.append(mfcf_mfl)
                        timenow = dt.datetime.now()
                        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
                        meastime2.append(timenow)
                        print('TAU is: %.2f' %tau)
                        
                        ax2.cla()
                        ax2a.cla()
                        ax4.cla()
                        ax2.plot(xs,dataset,'-k')
                        ax2.plot(xs,fit,'-g')
                        ax2a.plot(xs,dataset-fit,'-r')
                        ax4.plot(meastime2,ppbs,'-b')
                        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
                        ax2.grid()
                        ax2a.grid()
                        ax4.grid()
                        #fig.canvas.draw()
                        fig.canvas.flush_events()
                        
                    t1 = dt.datetime.now()
                    np.save(path_file+'Cm'+t1.strftime('%y%m%d%H%M'),measurements)
                    np.savetxt(path_file + 'MCtemp.txt',
                                np.column_stack((meastime,ppbs,taus,pPSI,tC,
                                                 mfca_mf,mfcf_mf,flag)), fmt='%s')
                    
                    #plt.close('all')
                    #plt.ioff()
                
                t1 = dt.datetime.now()
                np.savetxt(path_file + "MC" + t1.strftime('%y%m%d%H%M') + '.txt',
                            np.column_stack((meastime,ppbs,taus,pPSI,tC,
                                             mfca_mf,mfcf_mf,flag)), fmt='%s')

                crdsloop = False
        case 'c':
            plt.close()
            confirmcrds = input('Please confirm LC-CRDS mode (Y/N)')
            if confirmcrds.lower() == 'y':
                lccrdsloop = True
            else:
                print('Exiting CRDS mode.')
            #pmModulatorCtrl.enabled = True
            #statusPWM = 'PWM is ON.'

            while lccrdsloop:
                print('Switching valves for background measurement (Shutter ON):')
                ret = instantDo.writeAny(dostartPort, doportCount, 
                                         [shutter+zeroair+sampleclose])
                statusDO = 'DO set to ' + f'{shutter+zeroair+sampleclose:08b}'
                time.sleep(1)
                #input('Press any key to collect background.')
                plt.ion()
                fig = plt.figure(figsize=(15,6))
                gs = fig.add_gridspec(3,3)
                ax1 = fig.add_subplot(gs[:-1,0])
                ax1a = fig.add_subplot(gs[-1,0])
                ax2 = fig.add_subplot(gs[:-1,1])
                ax2a = fig.add_subplot(gs[-1,1])
                ax3 = fig.add_subplot(gs[:-1,2])
                ax4 = fig.add_subplot(gs[-1,2])
                #ax1.set_ylim([0.06,-y_lower])
                #ax2.set_ylim([-.05,.05])
                ax1a.set_xlabel('$\mu$s')
                ax2a.set_xlabel('$\mu$s')
                ax4.set_xlabel('Time')
                ax1.set_ylabel('Voltage')
                
                xs = tdivs[:-1]
                ys = [0]*(counts-1)
                
                #ax1.plot(xs,ys,'-k')
                #ax1.plot(xs,ys,'-g')
                #ax2.plot(xs,ys,'-r')
                ax1.grid()
                ax1a.grid()
                ax2.grid()
                ax2a.grid()
                ax3.grid()
                ax4.grid()

                ## Resets the trace, waits for ready
                ta = dt.datetime.now()
                lecroy.write('TA:FRST')
                tb = dt.datetime.now()
                time.sleep(runtime - (tb-ta).total_seconds())
                measurements = np.array(ys).reshape(len(ys),1)

                for n in range(shots_bckg):
                    t1 = dt.datetime.now()
                    lecroy.write('STO TA,M1')
                    lecroy.write('TA:FRST')
                    #lecroy.write('CLM M1')
                    data = lecroy.query('M1:WF? DAT1').split()
                    t2 = dt.datetime.now()
                    print((t2-t1).total_seconds())
                    values = getChunks(data[-1],size,vertgain,vertoff)
                    waveform = np.array(values[:-1])


                    ######
                    # This is the background, so here we should average the 
                    # dataset vector to obtain the background voltage
                    #
                    ######
                    bckg_crds_lc = np.average(waveform)
                    measurements = np.concatenate((measurements, 
                                                   waveform.reshape(len(waveform),1)),
                                                  axis=1)
                    ax3.cla()
                    ax3.plot(xs,waveform,'-k')
                    ax3.grid()
                    #fig.canvas.draw()
                    fig.canvas.flush_events()
                    # Total computing time in cycle, rest will be sleeping
                    t3 = dt.datetime.now()
                    print((t3-t1).total_seconds())
                    time.sleep(runtime-(t3-t1).total_seconds())

                ts1 = dt.datetime.now()
                np.save(path_file+'LCb'+ts1.strftime('%y%m%d%H%M'),measurements)
                
                print('Background collected.')

                for m in range(cycles):
                    print('Switching valves for zero measurement (Shutter OFF).')
                    ret = instantDo.writeAny(dostartPort, doportCount, 
                                             [zeroair+sampleclose])
                    statusDO = 'DO set to ' + f'{zeroair+sampleclose:08b}'
                    time.sleep(5)
                    ys = [0]*(counts-1)
                    taus_zero = []
                    pres_zero = []
                    tem_zero = []
                    
                    ta = dt.datetime.now()
                    lecroy.write('TA:FRST')
                    tb = dt.datetime.now()
                    time.sleep(runtime - (tb-ta).total_seconds())

                    measurements = np.array(ys).reshape(len(ys),1)
            
                    for n in range(shots_zero):
                        t1 = dt.datetime.now()
                        lecroy.write('STO TA,M1')
                        lecroy.write('TA:FRST')
                        #lecroy.write('CLM M1')
                        data = lecroy.query('M1:WF? DAT1').split()
                        t2 = dt.datetime.now()
                        print((t2-t1).total_seconds())
                        values = getChunks(data[-1],size,vertgain,vertoff)
                        waveform = np.array(values[:-1])

                        measurements = np.concatenate((measurements, 
                                                       waveform.reshape(len(waveform),1)),
                                                        axis=1)
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

                        mfca_poll = mfc_poll('a',mfccom)
                        mfcf_poll = mfc_poll('f',mfccom)
                        pres = float(mfca_poll[1])
                        tem = float(mfca_poll[2])
                        mfca_mfl = float(mfca_poll[4])
                        mfcf_mfl = float(mfcf_poll[4])
                        tau=-1e6/xres[2]
                        ppbs.append(0)
                        taus.append(tau)
                        taus_zero.append(tau)
                        flag.append(0)
                        pPSI.append(pres)
                        pres_zero.append(pres)
                        tC.append(tem)
                        tem_zero.append(tem)
                        mfca_mf.append(mfca_mfl)
                        mfcf_mf.append(mfcf_mfl)
                        timenow = dt.datetime.now()
                        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
                        meastime2.append(timenow)
                        print('TAU is: %.2f' %tau)
                        
                        ax1.cla()
                        ax1a.cla()
                        ax4.cla()
                        ax1.plot(xs,waveform,'-k')
                        ax1.plot(xs,fit,'-g')
                        ax1a.plot(xs,waveform-fit,'-r')
                        ax4.plot(meastime2,ppbs,'-b')
                        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
                        ax1.grid()
                        ax1a.grid()
                        ax4.grid()
                        #fig.canvas.draw()
                        fig.canvas.flush_events()
                        #print(c)
                        # Total computing time in cycle, rest will be sleeping
                        t3 = dt.datetime.now()
                        print((t3-t1).total_seconds())
                        time.sleep(runtime-(t3-t1).total_seconds())

                    
                    ts1 = dt.datetime.now()
                    taus_zero_mat = np.array(taus_zero)
                    pres_zero_mat = np.array(pres_zero)
                    tem_zero_mat = np.array(tem_zero)
                    taus_zero_avg = np.average(taus_zero_mat[8:])
                    pres_zero_avg = np.average(pres_zero_mat[8:])
                    tem_zero_avg = np.average(tem_zero_mat[8:])
                    Reff_scale.append(1-(47/(taus_zero_avg*29979.2458)))
                    np.save(path_file+'LCz'+ts1.strftime('%y%m%d%H%M'),measurements)
                    np.savetxt(path_file + 'MCtemp.txt',
                                np.column_stack((meastime,ppbs,taus,pPSI,tC,mfca_mf,
                                                 mfcf_mf,flag)), fmt='%s')
                    np.savetxt(path_file+'Reff_scale.txt',Reff_scale,fmt='%s')
                    
                    #plt.close('all')
                    #plt.ioff()


                    print('Switching valves for sample measurement.')
                    number=0
                    ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'
                    time.sleep(5)
                    
                    ys = [0]*(counts-1)
                    measurements = np.array(ys).reshape(len(ys),1)
                    
                    for n in range(shots_meas):
                        t1 = dt.datetime.now()
                        lecroy.write('STO TA,M1')
                        lecroy.write('TA:FRST')
                        #lecroy.write('CLM M1')
                        data = lecroy.query('M1:WF? DAT1').split()
                        t2 = dt.datetime.now()
                        print((t2-t1).total_seconds())
                        values = getChunks(data[-1],size,vertgain,vertoff)
                        waveform = np.array(values[:-1])

                        measurements = np.concatenate((measurements, 
                                                       waveform.reshape(len(waveform),1)),
                                                        axis=1)
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
 
                        tau=-1e6/xres[2]
                        mfca_poll = mfc_poll('a',mfccom)
                        mfcf_poll = mfc_poll('f',mfccom)
                        pres = float(mfca_poll[1])
                        tem = float(mfca_poll[2])
                        mfca_mfl = float(mfca_poll[4])
                        mfcf_mfl = float(mfcf_poll[4])
                        ext = (1.064/29979.2458)*((1/tau)-(1/taus_zero_avg))
                        pPa = 6894.757293 * pres
                        tK = 273.15 + tem
                        pzPa = 6894.757293 * pres_zero_avg
                        tzK = 273.15 + tem_zero_avg
                        delta_ext = (1.5765e-26/1.38066e-17)*((pPa/tK)-(pzPa/tzK))
                        #print(delta_ext)
                        #print(ext)
                        ppb = ((ext-delta_ext)/6.308459e-19)*(1e15*1.380649e-23*tK/pPa)
                        ppbs.append(ppb)
                        pPSI.append(pres)
                        tC.append(tem)
                        taus.append(tau)
                        flag.append(0)
                        mfca_mf.append(mfca_mfl)
                        mfcf_mf.append(mfcf_mfl)
                        timenow = dt.datetime.now()
                        meastime.append(timenow.strftime('%Y/%m/%d-%H:%M:%S'))
                        meastime2.append(timenow)
                        print('TAU is: %.2f' %tau)
                        print('NO2 ppb: %.2f' %ppb)
                        
                        ax2.cla()
                        ax2a.cla()
                        ax4.cla()
                        ax2.plot(xs,waveform,'-k')
                        ax2.plot(xs,fit,'-g')
                        ax2a.plot(xs,waveform-fit,'-r')
                        ax4.plot(meastime2,ppbs,'-b')
                        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
                        ax2.grid()
                        ax2a.grid()
                        ax4.grid()
                        #fig.canvas.draw()
                        fig.canvas.flush_events()
                        # Total computing time in cycle, rest will be sleeping
                        t3 = dt.datetime.now()
                        print((t3-t1).total_seconds())
                        time.sleep(runtime-(t3-t1).total_seconds())
                        
                    ts1 = dt.datetime.now()
                    np.save(path_file+'LCm'+ts1.strftime('%y%m%d%H%M'),measurements)
                    np.savetxt(path_file + 'MCtemp.txt',
                                np.column_stack((meastime,ppbs,taus,pPSI,tC,
                                                 mfca_mf,mfcf_mf,flag)), fmt='%s')
                    
                    #plt.close('all')
                    #plt.ioff()
                
                t1 = dt.datetime.now()
                np.savetxt(path_file + "MC" + t1.strftime('%y%m%d%H%M') + '.txt',
                            np.column_stack((meastime,ppbs,taus,pPSI,tC,
                                             mfca_mf,mfcf_mf,flag)), fmt='%s')

                lccrdsloop = False

            
        case 'd':
            controlloop = True
            while controlloop:
                print("\nSystem status is:")
                print(statusPWM,statusAOPump,statusAOPMT,statusDO)
                print("\nA - Switch PWN ON/OFF. B - Pump Voltage. C - PMT Voltage." + 
                      " D - Change DO. E - MFC. F - Exit\n")
                option2 = input("Please choose action: ")
                #print(option.lower())
                match option2.lower():
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
                                ret = instantAo.writeAny(aochannelStart, aochannelCount, 
                                                         None,[voltage1,voltage2])
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
                                ret = instantAo.writeAny(aochannelStart, aochannelCount, 
                                                         None,[voltage1,voltage2])
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
                                ret = instantDo.writeAny(dostartPort, doportCount, 
                                                         [number])
                                statusDO = 'DO set to ' + f'{number:08b}'
                            else:
                                print("Wrong number, try again...")
                        except:
                            print('Something happened, are you ok?')
                        print(statusDO)
                    case 'e':
                        operation = input('Press A for setpoint, B to poll:')
                        match operation.lower():
                            case 'a':
                                whichMFC = input('Which MFC (A/F):')
                                if whichMFC.lower() == 'a':
                                    setpoint = input('Type new setpoint:')
                                    mfcmsg = 'as'+setpoint+'\r'
                                    mfccom.write(bytes(mfcmsg,'utf-8'))
                                elif whichMFC.lower() == 'f':
                                    setpoint = input('Type new setpoint:')
                                    mfcmsg = 'fs'+setpoint+'\r'
                                    mfccom.write(bytes(mfcmsg,'utf-8'))
                                else:
                                    print('Invalid option, try again...')
                            case 'b':
                                mfccom.write(b'a\r')
                                time.sleep(mfcping)
                                statusMFCA = mfccom.read(
                                        mfccom.in_waiting).decode('utf-8')
                                time.sleep(mfcping)
                                mfccom.write(b'f\r')
                                time.sleep(mfcping)
                                statusMFCF = mfccom.read(
                                        mfccom.in_waiting).decode('utf-8')
                                print('MFCA status:')
                                print(statusMFCA)
                                print('MFCF status:')
                                print(statusMFCF)
                            case _:
                                print('Invalid option, try again...')
                    case 'f':
                        controlloop = False
                        print("Exiting Manual Control. Bye")
                    case _:
                        print("Invalid option, try again...")                    
        case 'x':
            mainloop = False
            print('Will shutdown. Bye')
        case _:
            print("Invalid option, try again...")


####################################### SHUTDOWN #########################################
##### Close COM ports
lecroy.close()
mfccom.close()

##### Analog output disable
ret = instantAo.writeAny(aochannelStart, aochannelCount, None,[0,0])
instantAo.dispose()

##### Digital output disable
ret = instantDo.writeAny(dostartPort, doportCount, [0])
instantDo.dispose()

##### PWM Disable
pmModulatorCtrl.enabled = False
pmModulatorCtrl.dispose()


