import serial
from time import sleep

rs232 = serial.Serial('COM1',19200)
n = True
while n:
    msg = rs232.read(rs232.in_waiting)
    
    while msg.decode("utf-8") == '':
        sleep(1)
        msg = rs232.read(rs232.in_waiting)
    print(msg.decode("utf-8"))
    string = input()
    rs232.write(bytes(string,"utf-8"))
    if string == 'q':
        n = False
    sleep(1)
    msg = rs232.read(rs232.in_waiting)
    while msg.decode("utf-8") == '':
        sleep(1)
        msg = rs232.read(rs232.in_waiting)
    rs232.write(b'r')
    print(msg.decode("utf-8"))
rs232.close()
