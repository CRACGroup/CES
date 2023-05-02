#########################################################################################
### This is the USER CONFIGURATION file
### Variables will be stored here to be called by main BBCEAS routines (blank and sample)
### Comment header has a short description of variables

### Need to import the codes for the Andor Camera
from pyAndorSDK2 import atmcd_codes as codes

### Both Blank and Sample store data to a subdirectory, windows and linux system use 
### different symbols, "\\" for windows, "/" for linux
folder_symbol = "\\"
savepath = "C:\\CRAC\\Data\\Instruments\\CEAS"


### The following are instrument configurations (used in both Blank and Sample)
# Acquisition mode (SINGLE_SCAN, ACCUMULATE ... check codes for more)
acqMode = codes.Acquisition_Mode.SINGLE_SCAN

# Read Mode
readMode = codes.Read_Mode.FULL_VERTICAL_BINNING

# Trigger Mode
trigMode = codes.Trigger_Mode.INTERNAL

# Wavelength calibration factors (we calculate wavelengths from pixels ourselves)
calfactors=(2.47080093383789e2,
        1.69589176774025e-1,
        -3.51128119291388e-6,
        -1.37265324107183e-10)

# Number of accumulations 
accums = 3

# Accumulation cycle delay (Exp + Delay = Cycle time)
delay = 0.5

# Exposure time. 
exptime_sample = 5
exptime_blank = 1

# Camera temperature
temp = -10

# Number of backgrounds to take
bckg_shots = 10

### The following are signal analysis parameters (not used in Blank, only Sample)
# Distance, the optical length of the sample (this is a physcal cavity parameter)
distance = 70

# The resonance window, lower (start) and upper (end) wavelengths
lower_wavelength = 300
upper_wavelength = 400

# Reference and background filenames to load, they should be located in the local dir
back_filename = "background.npy"
no2_refname = "NO2_AvSC.npy"
chocho_refname = "CHOCHO_AvSC.npy"

# Effective Reflectivity, check lab notebook on more information, can be a vector 
# to call using np.load, or it can be a constant
Reff = 0.99945

# Dilution factor, units are sccm
tflow = 5200
n2flow = 0 


