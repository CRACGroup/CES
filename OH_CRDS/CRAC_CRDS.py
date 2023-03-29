import serial
import datetime as dt
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from time import sleep

def getFloat(fromserial):
    for ele in fromserial:
        try:
            number=float(ele)
        except:
            pass
    return number

def getInt(fromserial):
    for ele in fromserial:
        try:
            number=int(ele)
        except:
            pass
    return number

def getChunks(hexes, size,vertgain,vertoff):
    chunks = [hexes[i:i+size] for i in range(0,len(hexes),size)]
    #print(chunks)
    vals =[]
    for ele in chunks:
        hhex = bytes.fromhex(ele)
        hint = int.from_bytes(hhex,byteorder='big',signed=True)
        vals.append(vertgain*hint+vertoff)
    return vals

def getWaveformParams(serialobject):
    flushAll(serialobject)
    serialobject.write(b'TA:INSPECT? \"WAVE_ARRAY_COUNT\"\r')
    counts= getInt(serialobject.read_until(expected=b'\n\r').decode('utf-8').split())
    print('Counts:',counts)

    flushAll(serialobject)
    serialobject.write(b'TA:INSPECT? \"VERTICAL_GAIN\"\r')
    vertgain = getFloat(serialobject.read_until(expected=b'\n\r').decode('utf-8').split())
    print('Vertical gain:',vertgain)
    
    flushAll(serialobject)
    serialobject.write(b'TA:INSPECT? \"VERTICAL_OFFSET\"\r')
    vertoff = getFloat(serialobject.read_until(expected=b'\n\r').decode('utf-8').split())
    print('Vertical offset',vertoff)

    flushAll(serialobject)
    serialobject.write(b'TA:INSPECT? \"HORIZ_INTERVAL\"\r')
    horint = getFloat(serialobject.read_until(expected=b'\n\r').decode('utf-8').split())
    print('Horizontal interval:',horint)

    flushAll(serialobject)
    serialobject.write(b'TA:INSPECT? \"HORIZ_OFFSET\"\r')
    horoff = getFloat(serialobject.read_until(expected=b'\n\r').decode('utf-8').split())
    print('Horizontal offset:',horoff)
    return counts,vertgain,vertoff,horint,horoff
    
def flushAll(serialobject):
    serialobject.flushInput()
    serialobject.flushOutput()

def waitReady(sleept,timeout=5,verbose=0):
    t1 = dt.datetime.now()
    d=0
    c=0
    lecroy.write(b'*CLS\r')
    out = []
    while (c!=257) and (d< timeout/sleept):
        #flushAll(lecroy)
        lecroy.write(b'INR?\r')
        output=lecroy.read_until(expected=b'\n\r').decode('utf-8').split()
        if verbose != 0:
            out.append(output)
        try:
            c=getInt(output)
        except:
            pass
    
        d +=1
        sleep(sleept)
    
    print(c,d)
    t2 = dt.datetime.now()
    print((t2-t1).total_seconds())
    if verbose !=0:
        print(out)

lecroy = serial.Serial('COM2',115200,timeout=10)
scanmate = serial.Serial('COM1',9600,stopbits = serial.STOPBITS_TWO,timeout=2)

lecroy.write(b'DISP OFF\r')
lecroy.write(b'COMM_HEADER OFF\r')
lecroy.write(b'COMM_FORMAT OFF,WORD,HEX\r')
flushAll(lecroy)
lecroy.write(b'ALST?\r')
lecroy.read_until(expected=b'\n\r')

size = 4 ### word= 2 bytes=4 hex, 1 byte=2 hex 
counts,vertgain,vertoff,horint,horoff=getWaveformParams(lecroy)
tdivs=np.arange(counts)*horint+horoff


fig = plt.figure()
ax1 = fig.add_subplot(111)
ax1.set_ylim([-.2,.2])
ys=[0]*counts
line, = ax1.plot(tdivs,ys,'-k')


lecroy.write(b'TA:FRST\r')
waitReady(.001)

def animate(i):
    #print('Run:',i+2)
    t1 = dt.datetime.now()
    #lecroy.write(b'COMM_HEADER OFF\r')
    #lecroy.write(b'COMM_FORMAT OFF,BYTE,HEX\r')
    lecroy.write(b'STO TA,M1\r')
    lecroy.write(b'TA:FRST\r')
    flushAll(lecroy)
    lecroy.write(b'M1:WF? DAT1\r')
    data=lecroy.read_until(expected=b'\n\r').decode('utf-8').split()
    t2 = dt.datetime.now()
    print((t2-t1).total_seconds())
    #print(data[-1])
    values = np.asarray(getChunks(data[-1],size,vertgain,vertoff))
    line.set_ydata(values)
    t3 = dt.datetime.now()
    print((t3-t1).total_seconds())
    waitReady(.001)
    t4 = dt.datetime.now()
    print((t4-t1).total_seconds())
    return line,

ani = animation.FuncAnimation(fig,animate,interval=1,blit=True,cache_frame_data=False)
plt.show()

lecroy.close()
scanmate.close()
