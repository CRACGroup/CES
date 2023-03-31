from pyvisa import ResourceManager,constants
from time import sleep

rm = ResourceManager()
print(rm.list_resources())
name = 'ASRL1::INSTR'
scanmate = rm.open_resource(name,
                            stop_bits = constants.StopBits.two,
                            read_termination = '\r',
                            write_termination = '\r')

print(scanmate.query('S?'))
blank = 308
meas = 307.921

isblank = False
for i in range(6):
    if isblank:
        scanmate.write('X=%.3f' %meas)
        isblank = False
    else:
        scanmate.write('X=%.3f' %blank)
        isblank = True
    sleep(5)
    

scanmate.close()
