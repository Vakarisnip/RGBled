from time import sleep
import board
import digitalio
red = digitalio.DigitalInOut(board.GP15)
red.direction = digitalio.Direction.OUTPUT
green = digitalio.DigitalInOut(board.GP14)
green.direction = digitalio.Direction.OUTPUT
blue = digitalio.DigitalInOut(board.GP13)
blue.direction = digitalio.Direction.OUTPUT
red.value = False
green.value = False
blue.value = False
print("hello world, from github (CircuitPython)")
while True:
    blue.value = False
    red.value = True
    sleep(0.5)
    green.value = True
    sleep(0.5)
    red.value = False
    sleep(0.5)
    blue.value = True
    sleep(0.5)
    green.value = False
    sleep(0.5)
    red.value = True
    sleep(0.5)
