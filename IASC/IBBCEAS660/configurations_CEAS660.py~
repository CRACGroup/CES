#########################################################################################
### This is the USER CONFIGURATION file
### Variables will be stored here to be called by main BBCEAS routines (blank and sample)
### Comment header has a short description of variables

import numpy as np

### Need to import the codes for the Andor Camera
from pyAndorSDK2 import atmcd_codes as codes

### Both Blank and Sample store data to a subdirectory, windows and linux system use 
### different symbols, "\\" for windows, "/" for linux
folder_symbol = "\\"
savepath = "C:\\CRAC\\Data\\Instruments\\NO3_IBBCEAS"


### The following are instrument configurations (used in both Blank and Sample)
# Acquisition mode (SINGLE_SCAN, ACCUMULATE ... check codes for more)
acqMode = codes.Acquisition_Mode.ACCUMULATE

# Read Mode
readMode = codes.Read_Mode.FULL_VERTICAL_BINNING

# Trigger Mode
trigMode = codes.Trigger_Mode.INTERNAL

# Wavelength calibration factors (we calculate wavelengths from pixels ourselves)
#FOR NO2 at 405 (JUNOx23)
#calfactors=(3.10322588e+02-3.3, 1.72905279e-01,
#            -1.48816626e-05,1.95619706e-09)
#FOR NO3 25/10/2023 SLIT OFF
#calfactors=(7.092125e+02,-1.173492e-01,
#            -1.805713e-05,6.237604e-09)
#NO3 slit ON 07/11/2023
calfactors=(7.090964e+02,-1.167403e-01,
            -1.903367e-05,6.759619e-09)

# Number of accumulations 
accums = 100

# Accumulation cycle delay (Exp + Delay = Cycle time)
delay = 0.05

# Exposure time. 
exptime_sample = .1
exptime_blank = .1

# Camera temperature
temp = -20

# Measurement to start average
start_avg = 2

# Number of backgrounds to take
bckg_shots = 10

### The following are signal analysis parameters (not used in Blank, only Sample)
# Distance, the optical length of the sample (this is a physcal cavity parameter)
distance = 500

# The resonance window, lower (start) and upper (end) wavelengths
lower_wavelength = 650
upper_wavelength = 672

# Reference and background filenames to load, they should be located in the local dir
back_filename = "background.npy"
ref1name = "NO3_IASC_CEAS660_650_672.npy"
ref2name = "NO2_IASC_CEAS660_650_672.npy"
ref3name = "H2O_IASC_CEAS660.npy" ### only for 650-672, sent through without shortening
#chocho_refname = "CHOCHO_JUNOx23.npy"
zero_filename = "zero.npy"
sigma_ray_filename = "sigma_ray_CEAS660.npy"

# Effective Reflectivity, check lab notebook on more information, can be a vector 
# to call using np.load, or it can be a constant
Reff = np.load('Reff_CEAS660.npy')
scale_index = 58

# Dilution factor, units are sccm
tflow = 5200
n2flow = 0 


