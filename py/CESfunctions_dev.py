import numpy as np
import glob
import scipy.signal as scs
import datetime as dt
import pandas as pd

def andor_calibrator(lenght,calfactors):
    '''
    This function not built yet, similar as avantes_calibrator but for the andor CCD
    '''

def avantes_aggregator(filepath,fileout):
    """ Aggregates Avantes ASCII 2D spectra, takes the log folder (avantes generated) and
    the name (with path) of the output npy """
    files = glob.glob(filepath+'*.TXT')
    #print(files)
    for ii,filename in enumerate(files):
        counts = []
        if ii==0:
            wavelength = []
            with open(filename) as file:
                lineas=file.readlines()
                lineas=lineas[8:-2]
            for line in lineas:
                lines=line.split(';')
                wavelength.append(float(lines[0]))
                counts.append(float(lines[1]))
            spectra=np.concatenate((np.array(wavelength,ndmin=2).T,np.array(counts,
                ndmin=2).T),axis=1)
        else:
            with open(filename) as file:
                lineas=file.readlines()
                lineas=lineas[8:-2]
            for line in lineas:
                lines=line.split(';')
                counts.append(float(lines[1]))
            spectra=np.concatenate((spectra,np.array(counts,ndmin=2).T),axis=1)
    np.save(fileout,spectra)

def avantes_calibrator(length,intercept,c1,c2,c3):
    """Takes the length of ha spectrum (i.e. number of pixels)
    and the calibration factors, generates corrected wavelengths
    as a pixels x 1 array"""
    waves = []
    for i in range(length):def avantes_calibrator(length,intercept,c1,c2,c3):
    """Takes the length of ha spectrum (i.e. number of pixels)
    and the calibration factors, generates corrected wavelengths
    as a pixels x 1 array"""
    waves = []
    for i in range(length):
        pixel = i+1
        wv= intercept+c1*pixel+c2*pow(pixel,2)+c3*pow(pixel,3)
        waves.append(wv)
    return np.array(waves).reshape(len(waves),1)

        pixel = i+1
        wv= intercept+c1*pixel+c2*pow(pixel,2)+c3*pow(pixel,3)
        waves.append(wv)
    return np.array(waves).reshape(len(waves),1)

def spectra_accumulator(npyin,samples,verbose=0):
    """ Accumulates a number of samples from the single spectrum npy matrix """
    ceaspec = np.load(npyin)
    cols=len(ceaspec[0,:])

    fromcol = 1
    tocol = fromcol + samples
    accum=np.copy(ceaspec[:,0]).reshape(len(ceaspec[:,0]),1)

    while tocol<=cols:
        #print(fromcol,tocol)
        suma=np.sum(ceaspec[:,fromcol:tocol],axis=1,keepdims=1)
        accum=np.concatenate((accum,suma),axis=1)
        tocol=tocol+samples
        fromcol=fromcol+samples
    if verbose==1:
        print(accum.shape)
    return accum

def spectra_average(spectra,samples,verbose=0):
    """ Averages a number of samples from an array of spectra """
    ceaspec = np.copy(spectra)
    cols=len(ceaspec[0,:])

    fromcol = 1
    tocol = fromcol + samples
    accum=np.copy(ceaspec[:,0]).reshape(len(ceaspec[:,0]),1)

    while tocol<=cols:
        #print(fromcol,tocol)
        avg=np.average(ceaspec[:,fromcol:tocol],axis=1).reshape(len(ceaspec[:,0]),1)
        accum=np.concatenate((accum,avg),axis=1)
        tocol=tocol+samples
        fromcol=fromcol+samples
    if verbose==1:
        print(accum.shape)
    return accum

def segment_indices(spectrum,minwave,maxwave):
    """Takes a spectrum and returns the indices of the wavelength range
    Is it useful? Might save some writing"""
    index=np.nonzero((spectrum[:,0]<=maxwave) & (spectrum[:,0]>=minwave))
    indexmin=index[0][0]
    indexmax=index[0][-1]+1
    return indexmin,indexmax

def ref_interpolate(reference,spectrum):
    """Takes a reference and a spectrum and interpolates the reference to the spectrum"""
    ref=np.load(reference)
    wave=spectrum[:,0]
    inter=np.interp(wave,ref[:,0],ref[:,1])
    wavel=np.copy(wave).reshape(len(wave),1)
    interp=np.copy(inter).reshape(len(inter),1)
    ref_interpolated=np.concatenate((wavel,interp),axis=1)
    return ref_interpolated

def get_fl(I_0,I_sample,reference,density,Reff,distance,npoints=17,npoly=3):
    """Calculates parametric function of wavelength, requires Reff. 
    Savitzky-Golay parameters can be modified"""
    I_ratio=(I_0/I_sample)
    #print(I_ratio.shape)
    ref_reshape=np.copy(reference[:,1]).reshape(len(reference[:,1]),1)
    f_c=(((I_ratio-1)/distance)*(1-Reff))-ref_reshape*density
    f_c_sg=scs.savgol_filter(f_c[:,0], npoints, npoly)
    #print(I_ratio.shape,f_c.shape,f_c_sg.shape)
    return f_c_sg.reshape(len(f_c[:,0]),1)

def get_Reff(I_0,I_sample,reference,density,distance,npoints=19,npoly=3):
    """Calculates Reff, requires clean, calibrated sample (no f($\lambda)). 
    Savitzky-Golay parameters can be modified"""
    I_ratio=(I_0/I_sample)
    Reff = 1-(((reference[:,1]*density)*distance)/(I_ratio-1)) 
    Reff_sg=scs.savgol_filter(Reff, npoints, npoly)
    return Reff_sg   

def fit_signal(extinction,reference):
    """Uses Singular Value Decomposition to fit a reference with a slope to the 
    extinction spectrum (or extinction minus the parametric function of wavelength). 
    Returns a,b,c,i.e., the coefficients of a+b*wavelength+c*$\sigma$"""
    #print(extinction.shape)
    ext=np.copy(extinction).reshape(len(extinction),1)
    ones = np.ones((len(extinction),1))
    ref = np.copy(reference)
    svdmat=np.concatenate((ones,ref),axis=1)
    U, S, Vt = np.linalg.svd(svdmat,full_matrices=False)
    x_hat = Vt.T @ np.linalg.inv(np.diag(S)) @ U.T @ ext
    a=x_hat[0,0]
    b=x_hat[1,0]
    c=x_hat[2,0]
    return a,b,c

def extinction(I_sample, I_0, Reff, distance):
    """Calculates extinction spectrum"""
    I_ratio=(I_0/I_sample)
    #print(I_ratio.shape)
    return (1/distance)*(I_ratio-1)*(1-Reff)

def recursive_fit(I_sample,I_0,Reff,distance,reference,verbose=1):
    """Calculates number density from signal according to the scheme:
    Extinction -> SVD -> f(wavelegnth) -> Extinction - f(wavelength) -> SVD"""
    alpha = extinction(I_sample,I_0,Reff,distance)
    #print(alpha.shape)
    a,b,c = fit_signal(alpha,reference)
    density = c
    f_l_sg= get_fl(I_0,I_sample,reference,density,Reff,distance)
    #print(f_l_sg.shape)
    alpha = alpha - f_l_sg
    #print(alpha.shape)
    a,b,c = fit_signal(alpha,reference)
    if verbose == 1:
        print("First N: ",density," Second N: ",c)
    return c

def recursive_fit_2ref(I_sample,I_0,Reff,distance,reference1,reference2,verbose=1):
    """Calculates number density from signal according to the scheme:
    Extinction -> SVD -> f(wavelegnth) -> Extinction - f(wavelength) -> SVD
    uses two reference spectra to fit"""
    alpha = extinction(I_sample,I_0,Reff,distance)
    #print(alpha.shape)
    a,b,c,d = fit_signal_2ref(alpha,reference1,reference2)
    density1 = c
    density2 = d
    f_l_sg= get_fl_2ref(I_0,I_sample,reference1,reference2,density1,density2,Reff,
            distance)
    #print(f_l_sg.shape)
    alpha = alpha - f_l_sg
    #print(alpha.shape)
    a,b,c,d = fit_signal_2ref(alpha,reference1,reference2)
    if verbose == 1:
        print("First N1: ",density1," Second N1: ",c)
        print("First N2: ",density2," Second N2: ",d)
    return c,d

def fit_signal_2ref(extinction,reference1,reference2):
    """Uses Singular Value Decomposition to fit two references with a slope to the 
    extinction spectrum (or extinction minus the parametric function of wavelength). 
    Returns a,b,c,d,i.e., the coefficients of a+b*wavelength+c*$\sigma$+d*$\sigma$
    uses to reference spectra"""
    #print(extinction.shape)
    ext=np.copy(extinction).reshape(len(extinction),1)
    ones = np.ones((len(extinction),1))
    ref1 = np.copy(reference1)
    ref2 = np.copy(reference2[:,1].reshape(len(reference2[:,1]),1))
    svdmat=np.concatenate((ones,ref1,ref2),axis=1)
    U, S, Vt = np.linalg.svd(svdmat,full_matrices=False)
    x_hat = Vt.T @ np.linalg.inv(np.diag(S)) @ U.T @ ext
    a=x_hat[0,0]
    b=x_hat[1,0]
    c=x_hat[2,0]
    d=x_hat[3,0]
    return a,b,c,d

def get_fl_2ref(I_0,I_sample,reference1,reference2,density1,density2,Reff,distance,
        npoints=17,npoly=3):
    """Calculates parametric function of wavelength, requires Reff. 
    Savitzky-Golay parameters can be modified
    this should be used with the 2ref functions"""
    I_ratio=(I_0/I_sample)
    #print(I_ratio.shape)
    ref1_reshape=np.copy(reference1[:,1]).reshape(len(reference1[:,1]),1)
    ref2_reshape=np.copy(reference2[:,1]).reshape(len(reference2[:,1]),1)
    f_c=(((I_ratio-1)/distance)*(1-Reff))-ref1_reshape*density1-ref2_reshape*density2
    f_c_sg=scs.savgol_filter(f_c[:,0], npoints, npoly)
    #print(I_ratio.shape,f_c.shape,f_c_sg.shape)
    return f_c_sg.reshape(len(f_c[:,0]),1)

def get_fl_broad(alpha,reference1,reference2,density1,density2,npoints=51,npoly=8):
    """Calculates parametric function of wavelength, this one requires the extinction
    to be already calculated as an imput, but is broader and much simpler
    This is also for two references but to be used with new fit_signal_w_fl function"""
    ref1_reshape=np.copy(reference1[:,1]).reshape(len(reference1[:,1]),1)
    ref2_reshape=np.copy(reference2[:,1]).reshape(len(reference2[:,1]),1)
    residual = alpha - ref1_reshape*density1-ref2_reshape*density2
    fl = scs.savgol_filter(residual[:,0],npoints,npoly)
    return fl

def fit_signal_w_fl(extinction,f_l,reference1,reference2):
    """Uses Singular Value Decomposition to fit two references with a parametric function
    f($\lambda$). Returns a,b,c,d, i.e. the coefficients of 
    a + b*f($\lambda$) + c*Ref1 + d*Ref2
    This incorporates the parametric function to the matrix, to avoid overfitting, a broad
    parametric function should be used, e.g. the one obtained from get_fl_broad"""
    ext = np.copy(extinction).reshape(len(extinction),1)
    flam = np.copy(f_l).reshape(len(f_l),1)
    ones = np.ones((len(extinction),1))
    ref1 = np.copy(reference1[:,1].reshape(len(reference1[:,1]),1))
    ref2 = np.copy(reference2[:,1].reshape(len(reference2[:,1]),1))
    svdmat=np.concatenate((ones,flam,ref1,ref2),axis=1)
    U, S, Vt = np.linalg.svd(svdmat,full_matrices=False)
    x_hat = Vt.T @ np.linalg.inv(np.diag(S)) @ U.T @ ext
    a=x_hat[0,0]
    b=x_hat[1,0]
    c=x_hat[2,0]
    d=x_hat[3,0]
    return a,b,c,d

def fit_alg_1(I_sample,I_0,Reff,distance,reference1,reference2,verbose=1,parameters=0,choice=2):
    """Fitting algorithm 1:
    Calculates the extinction, fits two references using SVD, then obtains a 
    parametric function, recalculates the original extinction with the two
    references and the parametric function
    Developed to try to clean the glyoxal area of the signal as much as possible."""
    alpha = extinction(I_sample,I_0,Reff,distance)
    a,b,c,d = fit_signal_2ref(alpha,reference1,reference2)
    density1 = c
    density2 = d
    if c<0 and d<0:
        c = 0
        d = 0
    elif c < 0:
        c = 0
    elif d < 0:
        d = 0
    alpha = alpha.reshape(len(alpha),1)
    fl = get_fl_broad(alpha,reference1,reference2,c,d,npoints=51,npoly=8)
    a,b,c,d = fit_signal_w_fl(alpha,fl,reference1,reference2)

    if verbose == 1:
        print("First N1: ",density1/2.5e10," Second N1: ",c/2.5e10)
        print("First N2: ",density2/2.5e10," Second N2: ",d/2.5e10)
    
    if choice == 1:
        if parameters == 1:
            return alpha,fl,a,b,density1,density2
        else:
            return density1,density2

    if choice == 2:
        if parameters == 1:
            return alpha,fl,a,b,c,d
        else:
            return c,d

def fit_alg_2(I_sample,I_0,Reff,distance,reference1,reference2,verbose=1,parameters=0,choice=2):
    """Fitting algorithm 2:
    Calculates the extinction, fits one references using SVD, then obtains a 
    parametric function, fits the second reference
    Developed to try to clean the glyoxal area of the signal as much as possible."""
    alpha = extinction(I_sample,I_0,Reff,distance)
    a,b,c = fit_signal(alpha,reference1)
    d=0
    
    if c<0:
        c=0

    residual = alpha[:,0]-c*reference1[:,1]
    residual = residual.reshape(len(residual),1)
    fl = get_fl_broad(residual,reference1,reference2,0,0,npoints=51,npoly=8)
    residual = residual[:,0]-fl
    a,b,d = fit_signal(residual,reference2)
    ndensity1 = c
    ndensity2 = d
    a,b,c,d = fit_signal_w_fl(alpha,fl,ndensity1*reference1,ndensity2*reference2)
    
    if verbose == 1:
            print("First N1: ",ndensity1/2.5e10," Second N1: ",c*ndensity1/2.5e10)
            print("First N2: ",ndensity2/2.5e10," Second N2: ",d*ndensity2/2.5e10)
    
    if choice == 1:
        if parameters == 1:
            return alpha,fl,a,b,ndensity1,ndensity2
        else:
            return ndensity1,ndensity2

    if choice == 2:
        if parameters == 1:
            return alpha,fl,a,b,c*ndensity1,d*ndensity2
        else:
            return c*ndensity1,d*ndensity2

def Mfile_read(mfilename):
    """This function reads a measurements text file (Mfile) and generates lists of the
    data. Mfile must be 2, 3 or 4 columns, we should not need more.
    Requires the filename.
    Returns 4 lists corresponding to 4 columns, excess columns are empty lists."""
    
    with open(mfilename) as f:
        lines = f.readlines()

    data = []

    for line in lines:
        a = line.strip('\n')
        data.append(a.split(' '))

    col1 = []
    col2 = []
    col3 = []
    col4 = []
    for ele in data:
        col1.append(dt.datetime.strptime(ele[0],'%Y/%m/%d-%H:%M:%S'))
        col2.append(float(ele[1]))
        
        try:
            col4.append(float(ele[3]))
            col3.append(float(ele[2]))
        except:
            try:
                col3.append(float(ele[2]))
            except:
                pass

    return col1,col2,col3,col4

def RAMA_read(ramafilename):
    """ This function takes a RAMA file and filters NO2 data, then corrects the timestamp
    of that data, it sorts 24h as 0h of the same day, RAMA might be referring to the 
    next day, however, so this function might need some fixing later
    Requires the filename
    Returns two lists, one for the dates and one for the ppbs"""

    df = pd.read_csv(ramafilename)
    df2 = df[df.Parametro == "NO2"]
    dates = []
    
    for ele in df2.Date:
        try:
            dates.append(dt.datetime.strptime(ele,'%Y-%m-%d %H:%M'))
        except:
            try:
                ele2=ele.replace('24','00',1)
                dates.append(dt.datetime.strptime(ele2,'%Y-%m-%d %H:%M')+
                        dt.timedelta(days=1))
            except: 
                ele2=ele.replace('24','00',2)
                ele3=ele2.replace('00','24',1)
                dates.append(dt.datetime.strptime(ele3, '%Y-%m-%d %H:%M')+
                        dt.timedelta(days=1))

    ppbs = []
    for ele in df2.RawValue:
        ppbs.append(ele)

    return dates,ppbs


def Isamples_builder(filelist):
    """Makes a Isamples numpy file if there was a problem when running
    BBCEAS_Measure and the Isamples file was not automatically generated
    Takes the generated individual spectra txt files and returns an
    Isamples numpy file"""
    for ele in filelist:
        spectra=np.loadtxt(ele)
        try:
            isamples=np.concatenate((isamples,spectra[:,1].reshape(len(spectra[:,1]),1)),axis=1)
        except:
            isamples=np.copy(spectra)
    np.save("Isamples_generated",isamples)
    print("Filelist size: ",len(filelist),"Isamples shape: ", isamples.shape)
