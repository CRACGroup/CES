##### General libraries and appending path
import time,sys
sys.path.append(u'C:\Advantech\DAQNavi\Examples\Python')

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

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





##### Device description and profile
deviceDescription = "MIC-1816,BID#15"
profilePath = r"C:\Users\LSG-DAQ\Documents\DAQPython\MIC1816.xml"

##### Channel definitions
## Pulse width modulator (TTL for diode)
pulsehigh = 10e-6
pulselow = 990e-6
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
aisectionLength = 200
aisectionCount = 1

# user buffer size should be equal or greater than raw data buffer length, because data ready count
# is equal or more than smallest section of raw data buffer and up to raw data buffer length.
# users can set 'USER_BUFFER_SIZE' according to demand.
USER_BUFFER_SIZE = aichannelCount * aisectionLength * aisectionCount

# Set trigger parameters
triggerAction = TriggerAction.DelayToStop
triggerEdge = ActiveSignal.RisingEdge
triggerDelayCount = 200
triggerLevel = 1
x_len = 100
shots = 50

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
            fig = plt.figure()
            ax1 = fig.add_subplot(111)
            ax1.set_ylim([-.5,5.5])
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

                dataset = data[:x_len]/(shots-c)
                #scan = AdvPollingOneBufferedAI_TDtp()    
                #dataset = scan[:x_len]
                line.set_ydata(dataset)
                #print(c)
                return line,

            ani = animation.FuncAnimation(fig,animate,interval=1,blit=True,cache_frame_data=False)
            plt.show()

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

