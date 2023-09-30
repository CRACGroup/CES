##########################################################################################
# JUNOx23 - NO2 CRD/CEAS instrument program, designed to use a MIC1816 for "housekeeping"
# (valves, MFCs, shutters, ttl, &c.), measure CRD decay times, and manage the CEAS script
# from a sister PC with an Andor CCD DU-401-BV accesed by a CCI-001 card
#
# Written by Dr. Mixtli Campos in June 2023.
##########################################################################################

########## General libraries and appending path
import time,sys,serial
sys.path.append(u'C:\Advantech\DAQNavi\Examples\Python')
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

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
    UNFINISHED AS OF 06.06.2023
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
######################## INITIALIZATION ##################################################

########## Initialize COM ports
ceascom = serial.Serial('COM3',19200)
mfccom = serial.Serial('COM2',19200)
mfcping = 0.5       # buffer time for send/receive MFC
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
x_end = 2450
x_start = 1950
x_len = x_end-x_start             # this is the number of points to display
y_lower = -.3
y_upper = 0
shots = 50              # number of shots to average
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
cycles = cyclescrds = 2


####################################### OPERATION ########################################
mainloop = True
controlloop = False
ceasloop = False
crdsloop = False
while mainloop:
    print("\nSystem status is:")
    print(statusPWM,statusAOPump,statusAOPMT,statusDO)
    print("\nA - Set scenario. B - Start CRDS. C - Start CEAS." +
          " D - Manual Control. E - Shutdown\n")
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
                    cycles = 1
                    cyclescrds = 1
                case 'b':
                    print('case b')
                    # d
                case 'c':
                    print('case c')
                    # d
                case 'z':
                    msgz1 = 'Input conditions '
                    msgz2 = '(Accums,Exposure,#Background,#Zero,#Meas,#Cycles,#CyclesCRDS):'
                    msgz=msgz1+msgz2
                    conditions = input(msgz)
                    params = conditions.split(',')
                    accums = params[0]
                    exposure = params[1]
                    shots_bckg = params[2]
                    shots_zero = params[3]
                    shots_meas = params[4]
                    cycles = int(params[5])
                    cyclescrds = int(params[6])
                    print('Custom conditions:',accums,exposure,shots_bckg,shots_zero,
                          shots_meas,cycles,cyclescrds)
                case _:
                    print('Invalid option, try again...')
        case 'b':
            confirmcrds = input('Please confirm CRDS mode (Y/N)')
            if confirmcrds.lower() == 'y':
                crdsloop = True
            else:
                print('Exiting CRDS mode.')
            pmModulatorCtrl.enabled = True
            statusPWM = 'PWM is ON.'

            while crdsloop:
                print('Switching valves for background measurement (Shutter ON):')
                ret = instantDo.writeAny(dostartPort, doportCount, 
                                         [shutter+zeroair+sampleclose])
                statusDO = 'DO set to ' + f'{shutter+zeroair+sampleclose:08b}'
                time.sleep(1)
                #input('Press any key to collect background.')

                fig = plt.figure()
                ax1 = fig.add_subplot(111)
                ax1.set_ylim([y_lower,y_upper])
                ax1.set_xlabel('$\mu$s')
                ax1.set_ylabel('Voltage')
                xs = [x*.2 for x in range(0,x_len)]
                ys = [0]*x_len
                line, = ax1.plot(xs,ys,'-k')
            
                def animate(i):
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
                    #scan = AdvPollingOneBufferedAI_TDtp()    
                    #dataset = scan[:x_len]
                    line.set_ydata(dataset)
                    #print(c)
                    return line,

                ani = animation.FuncAnimation(fig,animate,interval=1,blit=True,
                                          cache_frame_data=False)
                plt.show()

                print('Background collected.')
                
                for i in range(cyclescrds):
                    print('Switching valves for zero measurement (Shutter OFF).')
                    ret = instantDo.writeAny(dostartPort, doportCount, 
                                             [zeroair+sampleclose])
                    statusDO = 'DO set to ' + f'{zeroair+sampleclose:08b}'
                    time.sleep(1)
                    fig = plt.figure()
                    ax1 = fig.add_subplot(111)
                    ax1.set_ylim([y_lower,y_upper])
                    ax1.set_xlabel('$\mu$s')
                    ax1.set_ylabel('Voltage')
                    xs = [x*.2 for x in range(0,x_len)]
                    ys = [0]*x_len
                    line, = ax1.plot(xs,ys,'-k')
            
                    def animate(i):
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
                        #scan = AdvPollingOneBufferedAI_TDtp()    
                        #dataset = scan[:x_len]
                        line.set_ydata(dataset)
                        #print(c)
                        return line,

                    ani = animation.FuncAnimation(fig,animate,interval=1,blit=True,
                                          cache_frame_data=False)
                    plt.show()

                    print('Switching valves for sample measurement.')
                    number=0
                    ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'
                    time.sleep(1)
                    fig = plt.figure()
                    ax1 = fig.add_subplot(111)
                    ax1.set_ylim([y_lower,y_upper])
                    ax1.set_xlabel('$\mu$s')
                    ax1.set_ylabel('Voltage')
                    xs = [x*.2 for x in range(0,x_len)]
                    ys = [0]*x_len
                    line, = ax1.plot(xs,ys,'-k')
            
                    def animate(i):
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
                        #savename = 'dataset%i' % i
                        #np.save(savename,dataset)
                        #scan = AdvPollingOneBufferedAI_TDtp()    
                        #dataset = scan[:x_len]
                        line.set_ydata(dataset)
                        #print(c)
                        return line,

                    ani = animation.FuncAnimation(fig,animate,interval=1,blit=True,
                                          cache_frame_data=False)
                    plt.show()

                crdsloop = False
        case 'c':
            confirm = input('Please confirm CEAS mode (Y/N):')
            if confirm.lower() == 'y':
                ceasloop = True
            else:
                print('Exiting CEAS mode.')
            pmModulatorCtrl.enabled = False
            statusPWM = 'PWM is OFF.'

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
                
                back_max_time = int(accums)*int(shots_bckg)*float(exposure)
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
                
                    back_max_time = int(accums)*int(shots_zero)*float(exposure)
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
                        print('Switching valves for sample measurement.')
                        time.sleep(1)

                    ret = instantDo.writeAny(dostartPort, doportCount, [number])
                    statusDO = 'DO set to ' + f'{number:08b}'
                    print('Sending instruction to CEAS PC...')
                    msg_out = 'm' + ',' + accums + ',' + exposure + ',' + shots_meas
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
                
                    back_max_time = int(accums)*int(shots_zero)*float(exposure)
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


