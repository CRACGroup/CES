#########################################################################################
### This is the USER CONFIGURATION file
### Variables will be stored here to be called by main BBCEAS routines (blank and sample)
### Comment header has a short description of variables

### Both Blank and Sample store data to a subdirectory, windows and linux system use 
### different symbols, "\\" for windows, "/" for linux
folder_symbol = "\\"



### The following are instrument configurations (used in both Blank and Sample)
# Number of accumulations (sum of spectra to increase S/N)
accums = 50

# Integration time. Roughly, accums * itime = total sampling time
itime = 200

# Number of integrations to average (normally, should not need changing)
averages = 1

# Number of samples to take (e.g. 30 for blank, 999999 for a long sampling event)
samples_blank = 30
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
no2_refname = "NO2_AvSc_corr.npy"
chocho_refname = "CHOCHO_AvSc_corr.npy"

# Effective Reflectivity, check lab notebook on more information, can be a vector 
# to call using np.load, or it can be a constant
Reff = 0.99945

