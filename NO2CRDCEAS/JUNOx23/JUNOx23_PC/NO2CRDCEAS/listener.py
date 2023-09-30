import serial
from time import sleep
rs232 = serial.Serial('COM2',19200)
n=True
while n:
    rs232.write(b'Input 2 numbers separated by a comma (q to quit):')
    sleep(2)
    msg = rs232.read(rs232.in_waiting)

    while msg.decode("utf-8") == '':
        sleep(1)
        msg = rs232.read(rs232.in_waiting)

    if msg.decode("utf-8").lower() == 'q':
        rs232.write(b'Goodbye')
        n = False
    else:
        numbers = msg.decode("utf-8").split(',')
        op = int(numbers[0])*int(numbers[1])
        string = "%i times %i equals %i\r" %(int(numbers[0]),int(numbers[1]),op)
        rs232.write(bytes(string,"utf-8"))
    msg = rs232.read(rs232.in_waiting) 
    while msg.decode("utf-8") != 'r':
        sleep(1)
        msg = rs232.read(rs232.in_waiting)
rs232.close()



