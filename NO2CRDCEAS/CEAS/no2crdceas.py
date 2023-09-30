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



