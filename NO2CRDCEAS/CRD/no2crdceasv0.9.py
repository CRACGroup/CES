##########################################################################################
# JUNOx23 - NO2 CRD/CEAS instrument program, designed to use a MIC1816 for "housekeeping"
# (valves, MFCs, shutters, ttl, &c.), measure CRD decay times, and manage the CEAS script
# from a sister PC with an Andor CCD DU-401-BV accesed by a CCI-001 card
#
# Written by Dr. Mixtli Campos in June 2023.
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
######################## CEAS loop block #################################################
def run_CEAS(accums,exposure,shots,meastype):
    '''
    This is a run of the CEAS measurements (background, zero, or sample)
    Sends instructions and waits properly for answers
    meastype = 'b' or 'z' or 'm'
    UNFINISHED AS OF 16.06.2023
    ''' 
    print('Switching valves for measurement:',meastype)
    if meastype == 'm':
        ret = instantDo.writeAny(dostartPort, doportCount, [sampleair])
    else:
        ret = instantDo.writeAny(dostartPort, doportCount, [zeroair])

    print('Sending instruction to CEAS PC...')
    msg_out = meastype +','+ accums + ',' + exposure + ',' + shots_bckg
    ceascom.write(bytes(msg_out,'utf-8'))
    time.sleep(ceasping)
    msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
    com_count = 0
                
    while (msg_in != 'k'):
        print('No response, retrying...')
        com_count += 1
        time.sleep(ceasping)
        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
        if com_count > 5:
            break
                    
    if com_count >5:
        print('No answer. Will exit CEAS mode.')
        return 'e'
    else:
        print('CEAS is now measuring.')
                
    back_max_time = int(accums)*int(shots)*float(exposure)
    max_com_counts = (back_max_time+60)/ceasping
    com_count = 0
                
    while msg_in != 'd':
        com_count += 1
        time.sleep(ceasping)
        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
        if msg_in == 'e':
            break
        elif com_count > max_com_counts:
            break

    if msg_in == 'e':
        print('Error from CEAS PC. Will exit CEAS mode.')
        return 'e'
    elif com_count > max_com_counts:
        print('CEAS PC gave no status. Will exit CEAS mode.')
        return 'e'
    else:
        print('Measurement complete.')
    return 'd'






######################## END of CEAS loop block ##########################################

def funct(x,t,y):
    return x[0]+x[1]*np.exp(x[2]*t)-y

def gendata(t,a,b,c):
    return a+b*np.exp(t*c)

def mfc_poll(mfc,mfccom):
    msg_out = mfc + '\r'
    mfccom.write(bytes(msg_out,'utf-8'))
    time.sleep(mfcping)
    msg_in = mfccom.read(mfccom.in_waiting).decode('utf-8')
    mfc_str = msg_in.split(' ')
    return mfc_str


######################## INITIALIZATION ##################################################
parent = 'c:\\JUNOx23_DAQ\\Data'
directory = dt.datetime.now().strftime('%Y%m%d')
path = os.path.join(parent,directory)
try:
    os.mkdir(path)
except:
    pass
path_file = path + '\\'

taus = []
meastime = []
flag = []
pPSI = []
tC = []
mfca_mf = []
mfcf_mf = []

########## Initialize COM ports
ceascom = serial.Serial('COM3',19200)
mfccom = serial.Serial('COM2',19200)
mfcping = 0.25       # buffer time for send/receive MFC
ceasping = 0.5      # buffer time for send/receive CEAS

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
shots_bckg = shots_zero = shots_meas = '10'
shots_bckg_crds = shots_zero_crds = shots_meas_crds = 10
cycles = cyclescrds = 2


####################################### OPERATION ########################################
mainloop = True
controlloop = False
ceasloop = False
crdsloop = False
while mainloop:
    print("\nSystem status is:")
    print(statusPWM,statusAOPump,statusAOPMT,statusDO)
    print("\nA - Set scenario. B - Start CRDS. C - Start CEAS.",
          "D - Manual Control. E - Manual CRDS. F - Manual CEAS. X - Shutdown\n")
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
                    shots_bckg = '10' 
                    shots_zero = '10'
                    shots_meas = '20'
                    shots_bckg_crds = 10
                    shots_zero_crds = 10
                    shots_meas_crds = 10
                    cycles = 1
                    cyclescrds = 1
                case 'b':
                    print('Scenario B chosen')
                    accums = '1' 
                    exposure = '10' 
                    shots_bckg = '5' 
                    shots_zero = '6'
                    shots_meas = '30'
                    shots_bckg_crds = 10
                    shots_zero_crds = 10
                    shots_meas_crds = 10
                    cycles = 1
                    cyclescrds = 4
                    # d
                case 'c':
                    print('case c')
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
                    shots_bckg = params[2]
                    shots_zero = params[3]
                    shots_meas = params[4]
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
            confirmcrds = input('Please confirm CRDS mode (Y/N)')
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
                    measurements = np.concatenate((measurements, dataset.reshape(len(dataset),1)),
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
                        taus.append(tau)
                        flag.append(-999)
                        pPSI.append(pres)
                        tC.append(tem)
                        mfca_mf.append(mfca_mfl)
                        mfcf_mf.append(mfcf_mfl)
                        meastime.append(dt.datetime.now())
                        print('TAU is: %.2f' %tau)
                        
                        ax1.cla()
                        ax1a.cla()
                        ax4.cla()
                        ax1.plot(xs,dataset,'-k')
                        ax1.plot(xs,fit,'-g')
                        ax1a.plot(xs,dataset-fit,'-r')
                        ax4.plot(meastime,taus,'-b')
                        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
                        ax1.grid()
                        ax1a.grid()
                        ax4.grid()
                        #fig.canvas.draw()
                        fig.canvas.flush_events()
                        #print(c)
                    
                    t1 = dt.datetime.now()
                    np.save(path_file+'Cz'+t1.strftime('%y%m%d%H%M'),measurements)
                    np.savetxt(path_file + 'MCtemp.txt',
                                np.column_stack((meastime,taus,pPSI,tC,mfca_mf,mfcf_mf,flag)), fmt='%s')
                    
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
                        mfca_mf = float(mfca_poll[4])
                        mfcf_mf = float(mfcf_poll[4])
                        pPSI.append(pres)
                        tC.append(tem)
                        taus.append(tau)
                        flag.append(0)
                        mfca_mf.append(mfca_mfl)
                        mfcf_mf.append(mfcf_mfl)
                        meastime.append(dt.datetime.now())
                        print('TAU is: %.2f' %tau)
                        
                        ax2.cla()
                        ax2a.cla()
                        ax4.cla()
                        ax2.plot(xs,dataset,'-k')
                        ax2.plot(xs,fit,'-g')
                        ax2a.plot(xs,dataset-fit,'-r')
                        ax4.plot(meastime,taus,'-b')
                        ax4.xaxis.set_major_formatter(DateFormatter('%H:%M'))
                        ax2.grid()
                        ax2a.grid()
                        ax4.grid()
                        #fig.canvas.draw()
                        fig.canvas.flush_events()
                        
                    t1 = dt.datetime.now()
                    np.save(path_file+'Cm'+t1.strftime('%y%m%d%H%M'),measurements)
                    np.savetxt(path_file + 'MCtemp.txt',
                                np.column_stack((meastime,taus,pPSI,tC,mfca_mf,mfcf_mf,flag)), fmt='%s')
                    
                    #plt.close('all')
                    #plt.ioff()
                
                t1 = dt.datetime.now()
                np.savetxt(path_file + "MC" + t1.strftime('%y%m%d%H%M') + '.txt',
                            np.column_stack((meastime,taus,pPSI,tC,mfca_mf,mfcf_mf,flag)), fmt='%s')

                crdsloop = False
        case 'c':
            confirm = input('Please confirm CEAS mode (Y/N):')
            if confirm.lower() == 'y':
                ceasloop = True
            else:
                print('Exiting CEAS mode.')
            #pmModulatorCtrl.enabled = False
            #statusPWM = 'PWM is OFF.'

            while ceasloop:
                ####### This block repeats thrice and could be a function
                #run_CEAS(accums,exposure,shots,meastype)

                print('Switching valves for background measurement (Shutter ON):')
                ret = instantDo.writeAny(dostartPort, doportCount,
                                         [shutter+zeroair+sampleclose])
                statusDO = 'DO set to ' + f'{shutter+zeroair+sampleclose:08b}'
                time.sleep(1)
                #input('Press any key to collect background.')
                

                print('Sending instruction to CEAS PC...')
                msg_out = 'b' + ',' + accums + ',' + exposure + ',' + shots_bckg
                ceascom.write(bytes(msg_out,'utf-8'))
                time.sleep(ceasping)
                msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                com_count = 0
                
                while msg_in != 'k':
                    print('No response, retrying...')
                    com_count += 1
                    time.sleep(ceasping*2)
                    msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                    if com_count > 5/ceasping:
                        break
                    
                if com_count > 5/ceasping:
                    print('No answer. Will exit CEAS mode.')
                    break
                else:
                    print('CEAS is now obtaining a background.')
                
                back_max_time = int(accums)*int(shots_bckg)*float(exposure)*1.05
                max_com_counts = (back_max_time+60)/ceasping
                com_count = 0
                
                while msg_in != 'd':
                    com_count += 1
                    time.sleep(ceasping*2)
                    msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                    if msg_in == 'e':
                        break
                    elif com_count > max_com_counts:
                        break

                if msg_in == 'e':
                    print('Error from CEAS PC. Will exit CEAS mode.')
                    break
                elif com_count > max_com_counts:
                    print('CEAS PC gave no status. Will exit CEAS mode.')
                    break
                else:
                    print('CEAS finished measuring a background.')
                    #input('Press any key to continue...')
                ######## End of block


                for i in range(cycles):
                    print('Switching valves for zero measurement (Shutter OFF).')
                    ret = instantDo.writeAny(dostartPort, doportCount, 
                                             [zeroair+sampleclose])
                    statusDO = 'DO set to ' + f'{zeroair+sampleclose:08b}'
                    time.sleep(1)

                    print('Sending instruction to CEAS PC...')
                    ###### this message requires the flow information (....unlesss????XD)
                    msg_out = 'z' + ',' + accums + ',' + exposure + ',' + shots_zero
                    ceascom.write(bytes(msg_out,'utf-8'))
                    time.sleep(ceasping)
                    msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                    com_count = 0
                
                    while (msg_in != 'k'):
                        print('No response, retrying...')
                        com_count += 1
                        time.sleep(ceasping*2)
                        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                        if com_count > 5/ceasping:
                            break
                    
                    if com_count >5/ceasping:
                        print('No answer. Will exit CEAS mode.')
                        break
                    else:
                        print('CEAS is now measuring zero air.')
                
                    zero_max_time = int(accums)*int(shots_zero)*float(exposure)*1.05
                    max_com_counts = (zero_max_time+60)/ceasping
                    com_count = 0
                
                    while msg_in != 'd':
                        com_count += 1
                        time.sleep(ceasping*2)
                        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                        if msg_in == 'e':
                            break
                        elif com_count > max_com_counts:
                            break

                    if msg_in == 'e':
                        print('Error from CEAS PC. Will exit CEAS mode.')
                        break
                    elif com_count > max_com_counts:
                        print('CEAS PC gave no status. Will exit CEAS mode.')
                        break
                    else:
                        print('Switching valves for sample measurement.')
                        time.sleep(1)

                    ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'
                    print('Sending instruction to CEAS PC...')
                    
                    mfca_poll = mfc_poll('a',mfccom)
                    mfcadata = ','+mfca_poll[1] +','+mfca_poll[2]
                    msg_out = 'm' + ',' + accums + ',' + exposure + ',' + shots_meas + mfcadata
                    ceascom.write(bytes(msg_out,'utf-8'))
                    time.sleep(ceasping)
                    msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                    com_count = 0
                
                    while (msg_in != 'k'):
                        print('No response, retrying...')
                        com_count += 1
                        time.sleep(ceasping)
                        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                        if com_count > 5:
                            break
                    
                    if com_count >5:
                        print('No answer. Will exit CEAS mode.')
                        break
                    else:
                        print('CEAS is now measuring sample air.')
                
                    meas_max_time = int(accums)*int(shots_meas)*float(exposure)*1.05
                    max_com_counts = (meas_max_time+60)/ceasping
                    com_count = 0
                
                    while msg_in != 'd':
                        com_count += 1
                        time.sleep(ceasping)
                        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
                        if msg_in == 'e':
                            break
                        elif com_count > max_com_counts:
                            break

                    if msg_in == 'e':
                        print('Error from CEAS PC. Will exit CEAS mode.')
                        break
                    elif com_count > max_com_counts:
                        print('CEAS PC gave no status. Will exit CEAS mode.')
                        break
                    else:
                        print('End of CEAS sample measurement.')
                        number = 0
                        ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'

                ceasloop = False
            
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
        case 'e':
            mode = input('Please input CRDS mode (type,shots):')
            params_crds = mode.split(',')
        case 'f':
            mode = input('Please input CEAS mode:')
            params_ceas = mode.split(',')
        case 'x':
            mainloop = False
            print('Will shutdown. Bye')
        case _:
            print("Invalid option, try again...")


####################################### SHUTDOWN #########################################
##### Close COM ports
ceascom.close()
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


