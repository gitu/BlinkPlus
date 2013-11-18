#!/usr/bin/python

import time
import random
import serial

from led_ring import *


indexer = [8, 3, 9, 2, 10, 1, 11, 0, 12, 15, 13, 14, 7, 4, 6, 5, ]


class Job():
    def __init__(self, name, color, is_building):
        self.name = name
        self.color = color
        self.is_building = is_building


class View():
    def __init__(self):
        self.jobs = []

    def submit(self):
        colors = []
        for color in range(16):
            colors.append("000000")
        fades = []
        for fade in range(16):
            fades.append(0)
        i = 0
        for job in self.jobs:
            colors[indexer[i]] = job.color
            fades[indexer[i]] = 200 if job.is_building else 0
            i += 1
        led_ring.gamma_off()
        led_ring.set_colors(colors)
        led_ring.set_fade(fades)


def gen_random_view(size):
    fresh_view = View()
    building_states = [True, False, False]
    colors = ["FF0000", "FFFF00", "00FF00", "00FF00"]
    for x in range(size):
        fresh_view.jobs.append(Job(name="x" + str(x),
                                   color=random.choice(colors),
                                   is_building=random.choice(building_states)))
    return fresh_view


r = lambda: random.randint(0, 255)
rc = lambda: binascii.hexlify(chr(r()) + chr(r()) + chr(r()))

c = ["00FF00", "FFFF00", "FF0000", "000000", "000000", "000000", "000000",
     "00FF00", "00FF00", "00FF00", "00FF00", "00FF00", "000000", "000000",
     "888888", "00FF00"]

device = {
    "CO3": '\x00\x13\xa2\x00\x40\xb0\xa1\xad',
    "EP1": '\x00\x13\xa2\x00\x40\xac\xc4\x90',
    "EP2": '\x00\x13\xa2\x00\x40\xab\x97\x64'

}


class InitializedObserver():
    def __init__(self, led, brightness):
        self.brightness = brightness
        self.led = led

    def send_init_frames(self):
        self.led.set_green()
        self.led.fade_off()
        self.led.gamma_off()
        self.led.rotate_off()
        self.led.set_brightness(self.brightness)

    def receive_frame(self, frame):
        if "rf_data" in frame and frame["rf_data"] == b'\x01\x00':
            self.send_init_frames()


xbee_serial = serial.Serial('COM9', 9600)
try:
    led_ring = LedRing(xbee_serial, b'\xff\xfe', device["EP2"])
    observer = InitializedObserver(led_ring, 30)
    led_ring.frame_consumer.attach(observer)

    while 1:
        try:

            led_ring.fade_off()
            if 1:
                led_ring.set_brightness(50)
                view = gen_random_view(10)
                view.submit()
                time.sleep(20)
        except TransmitError, e:
            print "Transmit Error: " + e.msg
            raw_input("Press Enter to continue...")
        except Timeout, e:
            print "Reached Timeout: " + e.msg
            raw_input("Press Enter to continue...")
finally:
    xbee_serial.close()
