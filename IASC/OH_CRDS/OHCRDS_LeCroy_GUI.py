import tkinter as tk
import sys
import time
from pyvisa import constants,ResourceManager
from time import sleep
from scipy.optimize import least_squares
import numpy as np
import datetime as dt
import subprocess
import threading as th

class App:
    """Define the application class."""
    def __init__(self,root=tk.Tk()):
        ### Initialising GUI
        self.root = root
        self.root.resizable(False, False)
        ### The following grid_columnconfigure statemets make all the columns to belong to the same group, will have the
        ### size of the largest widget
        #self.root.grid_columnconfigure(0, weight=1, uniform="fred")
        #self.root.grid_columnconfigure(1, weight=1, uniform="fred")
        #self.root.grid_columnconfigure(2, weight=1, uniform="fred")
        #self.root.grid_columnconfigure(3, weight=1, uniform="fred")
        #self.root.grid_columnconfigure(4, weight=1, uniform="fred")
        #self.root.grid_columnconfigure(5, weight=1, uniform="fred")
        #self.root.grid_columnconfigure(6, weight=1, uniform="fred")
        self.root.title('OH CRDS LeCroy')


        ########################## PARAMETERS ###################################################

        # Instument parameters
        self.size = 4                        # the size of the HEX chunks to process the waveform
                                        # depends on the precision, 2 for BYTE, 4 for WORD
                                        # check COMM_FORMAT command for LeCroy instruments

        self.scanmatevi = 'ASRL1::INSTR'     # pyvisa name for INSTR at serial COM1
        self.lecroyvi = 'GPIB0::5::INSTR'    # pyvisa name for INSTR at GPIB channel 1
                                        # you can check them by the list.resources() method
                                        # check pyvisa DOCS for further info

        self.cycles = 10000                  # number of meas cycles before switching wavelength
        self.wavemeas = 307.921              # wavelength for tau_sample
        self.waveblank = 308                 # wavelength for tau_0

        # Fitting parameters
        self.len_offset = 500                # Length of baseline offset for logarithm fitting
        self.start_fit = 3000
        self.end_fit = 8000
        self.x0 = np.array([0,2,-50000])     # x0 for least_squares()

        # Cycle parameters
        self.sweeps = 30
        self.runtime = 1.1 * (self.sweeps/10)
        self.taus=[]
        self.tstamp=[]
        self.run=False
        self.p=None
        self.my_thread = None
        ######################### END OF PARAMETERS #############################################
        ### Initialising dictionary for variables
        self.keyvars = {}

        ### Frame 1: Radiobuttons
        self.frame1 = tk.Frame(self.root)
        self.frame1.grid(row=1,column=0,columnspan=15,sticky='we')

        # Add windows where we are going to write the std output.
        self.console_text = tk.Text(self.root, state='disabled', height=15)
        self.console_text.grid(row=1,column=0,rowspan=10,columnspan=15,sticky='we')

        # We redirect sys.stdout -> TextRedirector
        self.redirect_sysstd()

        # We add a button to test our setup
        self.start_button = tk.Button(self.root, text="Start", command=self.start_acq)
        self.start_button.config(state=tk.NORMAL)
        self.start_button.grid(row=15,column=0)

        self.stop_button = tk.Button(self.root, text="Stop", command=self.stop_acq)
        self.stop_button.config(state=tk.DISABLED)
        self.stop_button.grid(row=15,column=2)

        #### Resource initialization and opening

        self.rm = ResourceManager()
        #print(self.rm.list_resources()) ### uncomment to look at the namess
        self.lecroy = self.rm.open_resource(self.lecroyvi)
        #self.scanmate = rm.open_resource(scanmatevi,
        #                            stop_bits = constants.StopBits.two,
        #                            read_termination = '\r',
        #                            write_termination = '\r')

        #### LeCroy setup
        #lecroy.write('DISP OFF')   # uncomment to stop display
        self.lecroy.write('COMM_HEADER OFF')
        self.lecroy.write('COMM_FORMAT OFF,WORD,HEX')
        self.lecroy.write('TA:DEF EQN,\'AVGS(C1)\',MAXPTS,100000,SWEEPS,%i' %self.sweeps)
        #lecroy.write('CLM M1')     # clear memory M1

        #### Good to go queries
        print('LECROY:',self.lecroy.query('ALST?')) # ALL STATUS just to make sure it works
        #print('SCANMATE:',scanmate.query('S?')) # STATUS to make sure it gets R

        #### Waveform info
        self.counts,self.vertgain,self.vertoff,self.horint,self.horoff = self.getWaveformParams()
        self.tdivs = np.arange(self.counts)*self.horint+self.horoff

    def redirect_sysstd(self):
        # We specify that sys.stdout point to TextRedirector
        sys.stdout = TextRedirector(self.console_text, "stdout")
        sys.stderr = TextRedirector(self.console_text, "stderr")

    def getFloat(self,res):
        '''
        Gets a splitted string response to a query and converts what it can to a float
        '''
        for ele in res:
            try:
                number=float(ele)
            except:
                pass
        return number

    def getInt(self,res):
        '''
        Gets a splitted string response to a query and converts what it can to an integer
        '''
        for ele in res:
            try:
                number=int(ele)
            except:
                pass
        return number

    def getChunks(self,hexes,size,vertgain,vertoff):
        '''
        Converts the waveform HEX DAT1 string to values by chunking the string,
        converting each chunk into HEX, then into big endian signed integers, and
        then using the equation from the manual
        V = Vertical Gain * INT + Vertical offset
        '''
        chunks = [hexes[i:i+size] for i in range(0,len(hexes),size)]
        #print(chunks)
        vals = []
        for ele in chunks:
            hhex = bytes.fromhex(ele)
            hint = int.from_bytes(hhex,byteorder='big',signed=True)
            #print(hint)
            vals.append(vertgain*hint+vertoff)
        return vals

    def getWaveformParams(self):
        '''
        Gets needed waveform parameters from a series of queries that are converted
        to integer or float depending on the parameters
        '''
        counts = self.getInt(self.lecroy.query('TA:INSPECT? \"WAVE_ARRAY_COUNT\"').split())
        print('Counts:',counts)

        vertgain = self.getFloat(self.lecroy.query('TA:INSPECT? \"VERTICAL_GAIN\"').split())
        print('Vertical gain:',vertgain)

        vertoff = self.getFloat(self.lecroy.query('TA:INSPECT? \"VERTICAL_OFFSET\"').split())
        print('Vertical offset:',vertoff)

        horint = self.getFloat(self.lecroy.query('TA:INSPECT? \"HORIZ_INTERVAL\"').split())
        print('Horizontal interval:',horint)

        horoff = self.getFloat(self.lecroy.query('TA:INSPECT? \"HORIZ_OFFSET\"').split())
        print('Horizontal offset:',horoff)

        return counts,vertgain,vertoff,horint,horoff

    def gendata(self,t,a,b,c):
        '''
        Generates the exponential fit
        '''
        return a+b*np.exp(t*c)

    def funct(self,x,t,y):
        '''
        Function to fit with optimize.least_squares
        '''
        return x[0] + x[1]*np.exp(x[2]*t)-y

    def run_acq(self):
        #### Begin measurements
        ## Moves to blank wavelength and sets check variable
        #scanmate.write('X=%.3f' %waveblank)
        #isblank = True
        # Initializes lists
        self.p = subprocess.Popen(["python","OHCRDS_plotter.py"])
        self.taus = []
        self.tstamp = []
        i=0
        waveforms = np.arange(self.counts)
        while self.run:
            ## Resets the trace, waits for ready
            ta = dt.datetime.now()
            self.lecroy.write('TA:FRST')
            tb = dt.datetime.now()
            sleep(self.runtime - (tb-ta).total_seconds())
            #waitReady(lecroy,0.01,timeout=3,verbose=0) ### Deprecated, problems with WaitReady()

            ## Main loop, stores to M1, resets trace, queries data, gets values,
            ## fits paraments, gets residuals, waits for ready
            ## sends wavelength change to scanmate after n cycles
            ## is presented as a function for the animation class

            print('RUN:',i+1)
            t1 = dt.datetime.now()
            self.lecroy.write('STO TA,M1')
            self.lecroy.write('TA:FRST')
            #lecroy.write('CLM M1')
            data = self.lecroy.query('M1:WF? DAT1').split()
            t2 = dt.datetime.now()
            print((t2-t1).total_seconds())
            values = self.getChunks(data[-1],self.size,self.vertgain,self.vertoff)
            waveform = np.array(values)#[:-1])
            waveforms = np.column_stack((waveforms,waveform))
            print(self.tdivs.shape,waveform.shape)

            # Prepare data for fitting
            ts=self.tdivs[self.start_fit:self.end_fit]
            ys=waveform[self.start_fit:self.end_fit]

            #### LEAST SQUARES

            # Levenberg - Marquardt
            #res_lsq = least_squares(fun,x0, method = 'lm', ftol=1e-12,xtol=1e-12,gtol=1e-12,
            #                       args=(ts,ys))

            # TRF
            res_log = least_squares(self.funct,self.x0, ftol=1e-12,xtol=1e-12,gtol=1e-12,
                                    loss = 'cauchy', f_scale=0.1, args=(ts,ys))

            # The results
            xs = res_log.x
            #### END OF LEAST SQUARES

            #### NATURAL LOG
            # Fit the baseline and get a function
            #coef = np.polyfit(tdivs[:len_offset+1],values[:len_offset+1],1)
            #poly1d_fn = np.poly1d(coef)
            # Remove the baseline
            #offset_values = values[:-1]-poly1d_fn(tdivs[:-1])
            # Take the log
            #logs = np.log(offset_values[start_fit:end_fit])
            # Fit the log
            #coef2 = np.polyfit(tdivs[start_fit:end_fit],logs,1)
            # The results
            #xs = (coef[1],np.exp(coef2[1]),coef2[0])
            #### END OF NATURAL LOG

            #print(xs)              # in case you want to see the fit parameters

            # Shows and saves tau to a list, timestamps to list as well
            tau = -1e6/xs[2]
            self.taus.append(tau)
            timenow = dt.datetime.now()
            stamp = timenow.strftime('%Y/%m/%d-%H:%M:%S')
            self.tstamp.append(stamp)
            print('TAU is: %.2f' %tau)

            # Builds the fit = non fitted waveform + generated data from params
            fita = waveform[:self.start_fit]
            fitb = self.gendata(self.tdivs[self.start_fit:],*xs)
            fit = np.concatenate((fita,fitb))

            np.save("ax1data", np.column_stack((self.tdivs,waveform)))
            np.save("ax1adata", np.column_stack((self.tdivs,fit)))
            np.save("ax2data", np.column_stack((self.tdivs,waveform-fit)))


            # wavelength change
            #if (i+1)% cycles == 0:
            #    if isblank:
            #        scanmate.write('X=%.3f' %wavemeas)
            #        isblank = False
            #    else:
            #        scanmate.write('X=%.3f' %waveblank)
            #        isblank = True
            # end

            # Total computing time in cycle, rest will be sleeping
            t3 = dt.datetime.now()
            print((t3-t1).total_seconds())
            sleep(self.runtime-(t3-t1).total_seconds())
            #waitReady(lecroy,0.01) ### Deprecated due to problems with WaitReady()

            # Total cycle time
            t4 = dt.datetime.now()
            print((t4-t1).total_seconds())
            i+=1
        t1 = dt.datetime.now()                  # End time
        #print("Seconds elapsed: ",(t1-t0).total_seconds())
        # Generates arrays to export to npy or txt
        taumat = np.array(self.taus)
        tstampmat = np.array(self.tstamp,dtype='U19')

        # Saves NPY files
        #np.save('taus.npy', taumat) ### The taus as npy
        np.save('W'+t1.strftime('%y%m%d%H%M')+'.npy',waveforms) ### The waveforms as npy
        #np.save('timestamps.npy',tstampmat) ### The timestamps as npy

        # Saves TXT file: [timestamp tau]
        np.savetxt("M" + t1.strftime('%y%m%d%H%M') + '.txt',np.column_stack((tstampmat,taumat)),fmt='%s')

        ### Some rough statistical data in case you want to know
        print('Average TAU: %.2f' %np.average(taumat))
        print('Stdev: %.2f' %np.std(taumat))


    def start_acq(self):
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        try:
            if self.my_thread.is_alive():
                print("Closing previous thread.")
                self.my_thread.join()
                print("Thread closed, starting acquisition.")
            else:
                print("Starting acquisition.")
        except:
            print("Starting acquisition.")
        self.run = True
        self.my_thread = th.Thread(target=self.run_acq)
        self.my_thread.start()

    def stop_acq(self):
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        try:
            self.p.terminate()
        except:
            print("No subprocess to terminate?")
        self.run=False


        print("Terminating acquisition.")
        self.my_thread.join(timeout=.1)

        #self.my_thread.join()
        #print("resetting thread")
        #self.my_thread = None
        #print(self.run)

class TextRedirector(object):
    def __init__(self, widget, tag):
        self.widget = widget
        self.tag = tag

    def write(self, text):
        self.widget.configure(state='normal') # Edit mode
        self.widget.insert(tk.END, text, (self.tag,)) # insert new text at the end of the widget
        self.widget.configure(state='disabled') # Static mode
        self.widget.see(tk.END) # Scroll down
        self.widget.update_idletasks() # Update the console

    def flush(self):
        pass

if __name__ == "__main__":
    app = App()
    app.root.mainloop()
