import os
import os
from pylablib.devices import HighFinesse
from evaluation import WavemeterEvaluation
import numpy as np
import matplotlib.pyplot as pyplot
import time



########Parameters############
#instrument parameter
channel = 1
source_type = "hene_633"
n_air_vac =0.99972338

#plot parameter


#cycle parameter
scan_time = 20000000 #mseconds
expo = 100 #mseconds


##########end of parameter#########
#connection to the wavemeter
app_folder = r"C:\Program Files (x86)\HighFinesse\Wavelength Meter WS6 3914"
dll_path = os.path.join(app_folder, "Projects", "64") 
app_path = os.path.join(app_folder, "wlm_ws6.exe")
wm = HighFinesse.WLM(3914, dll_path=dll_path, app_path=app_path)

#calibrate the wavemeter
#wm.calibrate(source_type, channel)

#evaluate freuqency
freq = wm.get_frequency()
freq_thz = freq * 10**-12
if (freq != None):
  print ("The frequency of the laser is" + " " + str(freq_thz) + " " + "THz") 

#evaluate wavelength
wavel = wm.get_wavelength()*n_air_vac
wavel_nm = wavel * 10**9

if (wavel_nm !=None):
  print ("The wavelength of the laser in air is" + " " + str(wavel_nm) + " " + "nm")

#np array of frequencys and wavelengths with time stamps
"""
numsteps = input("number of data points:")
timesteps = input("time step size: ")
dt = float(timesteps)
numstep = int(numsteps)
scan_times = []
times = np.zeros(numstep)
time_1 = 0.0
for i in range(numstep):
  times[i] = time_1
  scan_times.append(time_1)
  time_1 += dt

"""
num = scan_time/expo
scan_times = np.linspace(0, scan_time, int(num))
frequencys = []
wavelengths = []
for a in range(len(scan_times)):
  inst_wavel = wm.get_wavelength()*n_air_vac
  wavelengths.append(inst_wavel * 10**9)
  inst_freq = wm.get_frequency()
  frequencys.append(inst_freq * 10**-12)
  time.sleep(0.01) 

#writing the array into file
#get filename in command line
filename_w = input("Enter output filename for wavelenght: ")
filename_f = input("Enter output filename for frequency: ")

#save file to name
with open(filename_w, 'w') as f:
  f.write("wavelength(nm)\tscantime(s)\n")
  for w, i in zip(wavelengths, scan_times):
    f.write(f"{w:.6f}\t{i}\n")

print(f"wavelength data saved to {filename_w}")

with open(filename_f, 'w') as k:
  k.write("frequency(THz)\tscantime(s)\n")
  for w, i in zip(frequencys, scan_times):
    k.write(f"{w:.6f}\t{i}\n")

print(f"frequency data saved to {filename_f}")


#plot data
pyplot.title('flucuation of wavelength with time')
pyplot.xlabel('time(ms)')
pyplot.ylabel('wavelength(nm)')
pyplot.plot (scan_times, wavelengths)
pyplot.savefig("wavelength.svg", format="svg")
pyplot.close ()

pyplot.title('flucuation of frequency with time')
pyplot.xlabel('time(ms)')
pyplot.ylabel('frequency(THz)')
pyplot.plot (scan_times, frequencys)
pyplot.savefig("frequency.svg", format="svg")
pyplot.close()


wm.close()

