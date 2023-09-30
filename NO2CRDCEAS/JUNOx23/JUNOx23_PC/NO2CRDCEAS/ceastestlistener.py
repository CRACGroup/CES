import serial
from time import sleep
ceascom = serial.Serial('COM2',19200)

while True:
    sleep(2)
    msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
    while msg_in == '':
        sleep(0.5)
        msg_in = ceascom.read(ceascom.in_waiting).decode('utf-8')
    
    print(msg_in)
    ceascom.write(b'k')
    sleep(10)
    ceascom.write(b'd')
ceascom.close()

