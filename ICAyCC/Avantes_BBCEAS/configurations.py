#########################################################################################
### This is the USER CONFIGURATION file
### Variables will be stored here to be called by main BBCEAS routines (blank and sample)
### Comment header has a short description of variables

### Both Blank and Sample store data to a subdirectory, windows and linux system use 
### different symbols, "\\" for windows, "/" for linux
folder_symbol = "\\"



### The following are instrument configurations (used in both Blank and Sample)
# Wavelength calibration factors (we calculate wavelengths from pixels ourselves)
calfactors=(2.47080093383789e2,
        1.69589176774025e-1,
        -3.51128119291388e-6,
        -1.37265324107183e-10)

# Number of accumulations (sum of spectra to increase S/N)
accums = 50

# Integration time. Roughly, accums * itime = total sampling time
itime = 200

# Number of integrations to average (normally, should not need changing)
averages = 1

# Number of samples to take (e.g. 30 for blank, 999999 for a long sampling event)
samples_blank = 5
samples = 5

# How many times it will query the instrument to make see if ready (calls per itime)
checkrate = 10



### The following are signal analysis parameters (not used in Blank, only Sample)
# Distance, the optical length of the sample (this is a physcal cavity parameter)
distance = 70

# The resonance window, lower (start) and upper (end) wavelengths
lower_wavelength = 445
upper_wavelength = 459

# Reference and background filenames to load, they should be located in the local dir
back_filename = "background.npy"
no2_refname = "NO2_AvSC.npy"
chocho_refname = "CHOCHO_AvSC.npy"

# Effective Reflectivity, check lab notebook on more information, can be a vector 
# to call using np.load, or it can be a constant
Reff = 0.99945

# Dilution factor, units are sccm
tflow = 5200
n2flow = 150


