import numpy as np
import glob
import scipy.signal as scs

def avantes_aggregator(filepath,fileout):
    """ Aggregates Avantes ASCII 2D spectra, takes the log folder (avantes generated) and the name
    (with path) of the output npy """
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
            spectra=np.concatenate((np.array(wavelength,ndmin=2).T,np.array(counts,ndmin=2).T),axis=1)
        else:
            with open(filename) as file:
                lineas=file.readlines()
                lineas=lineas[8:-2]
            for line in lineas:
                lines=line.split(';')
                counts.append(float(lines[1]))
            spectra=np.concatenate((spectra,np.array(counts,ndmin=2).T),axis=1)
    np.save(fileout,spectra)

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
    """Calculates parametric function of wavelength, requires Reff. Savitzky-Golay parameters can be modified"""
    I_ratio=(I_0/I_sample)
    #print(I_ratio.shape)
    ref_reshape=np.copy(reference[:,1]).reshape(len(reference[:,1]),1)
    f_c=(((I_ratio-1)/distance)*(1-Reff))-ref_reshape*density
    f_c_sg=scs.savgol_filter(f_c[:,0], npoints, npoly)
    #print(I_ratio.shape,f_c.shape,f_c_sg.shape)
    return f_c_sg.reshape(len(f_c[:,0]),1)

def get_Reff(I_0,I_sample,reference,density,distance,npoints=19,npoly=3):
    """Calculates Reff, requires clean, calibrated sample (no f($\lambda)). Savitzky-Golay parameters can be modified"""
    I_ratio=(I_0/I_sample)
    Reff = 1-(((reference[:,1]*density)*distance)/(I_ratio-1)) 
    Reff_sg=scs.savgol_filter(Reff, npoints, npoly)
    return Reff_sg   

def fit_signal(extinction,reference):
    """Uses Singular Value Decomposition to fit a reference with a slope to the extinction spectrum (or extinction
    minus the parametric function of wavelength). Returns a,b,c,i.e., the coefficients of a+b*wavelength+c*$\sigma*"""
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
