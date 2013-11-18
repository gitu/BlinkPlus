import binascii
import string
import itertools
import threading
import sys
import traceback
import struct

from xbee import ZigBee


class Timeout(Exception):
    def __init__(self, msg):
        self.msg = msg


class TransmitError(Exception):
    def __init__(self, msg):
        self.msg = msg


class FrameConsumer():
    def __init__(self):
        self._observers = []

    def attach(self, observer):
        if not observer in self._observers:
            self._observers.append(observer)

    def detach(self, observer):
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    #noinspection PyBroadException
    def receive_frame(self, frame):
        print "## received frame: "
        for x in frame:
            print "##  " + '{0: <16}'.format(x) + ": " + binascii.hexlify(frame[x])

        for observer in self._observers:
            try:
                observer.receive_frame(frame)
            except:
                print "swallowed exception"
                exc_type, exc_value, exc_traceback = sys.exc_info()
                print repr(traceback.format_exception(exc_type, exc_value,
                                                      exc_traceback))


class Waiter(threading.Thread):
    def __init__(self, observable, timeout):
        threading.Thread.__init__(self)
        self.timeout = timeout
        self.result = None
        self.exception = None
        self.observable = observable
        self.observable.attach(self)
        self.done = threading.Event()

    def detach(self):
        self.observable.detach(self)

    def run(self):
        if not self.done.wait(self.timeout):
            self.result = "ERR"
            self.exception = Timeout("Thread was waiting for " + str(self.timeout))
            self.detach()


class WaitForResponse(Waiter):
    def __init__(self, observable, timeout, frame_id):
        Waiter.__init__(self, observable, timeout)
        self.frame_id = frame_id
        self.response = None

    def receive_frame(self, frame):
        if "frame_id" in frame and frame["frame_id"] == chr(self.frame_id):
            self.done.set()
            print "found response"
            if frame["deliver_status"] == b'\x00':
                self.result = "OK"
            else:
                self.result = "ERR"
                self.exception = TransmitError(
                    "Received Deliver Status: " + binascii.hexlify(frame["deliver_status"]) + " for frame " + str(
                        self.frame_id))
            self.response = frame
            self.detach()


class WaitForConfirm(Waiter):
    def __init__(self, observable, timeout, expected_data):
        Waiter.__init__(self, observable, timeout)
        self.expected_data = expected_data
        self.confirm = None

    def receive_frame(self, frame):
        if "rf_data" in frame and frame["rf_data"] == self.expected_data:
            self.done.set()
            print "found confirm"
            self.result = "OK"
            self.confirm = frame
            self.detach()


class LedRing():
    commands = {
        "full": b'\x00',
        "color": b'\x01',
        "pos": b'\x02',
        "jump": b'\x03',
        "level": b'\x04',
        "level_red": b'\x05',
        "level_green": b'\x06',
        "level_blue": b'\x07',
        "red": b'\x08',
        "green": b'\x09',
        "blue": b'\x0a',
        "rot_left": b'\x0b',
        "rot_right": b'\x0c',
        "rot_off": b'\x0d',
        "set_fade": b'\x0e',
        "fade_off": b'\x0f',
        "brightness": b'\x10',
        "use_gamma": b'\x11',
        "gamma_off": b'\x12',
    }

    c_request = b'\x01'
    c_received_command = b'\x02'

    def __init__(self, serial, addr, addr_long):
        self.frame_consumer = FrameConsumer()
        self.xbee = ZigBee(serial, callback=self.frame_consumer.receive_frame, escaped=True)
        self.addr = addr
        self.addr_long = addr_long
        self.frame_cycle = itertools.cycle(range(1, 255))

    def _tx(self, command, data=None):
        cmd = self.commands[command]
        if not data is None:
            cmd = cmd + data

        frame_id = self.frame_cycle.next()
        print "## sending " + binascii.hexlify(cmd) + " len: " + str(len(cmd)) + " to node " + binascii.hexlify(
            self.addr_long)

        wait_response = WaitForResponse(self.frame_consumer, 60, frame_id)
        wait_confirm = WaitForConfirm(self.frame_consumer, 60, self.c_received_command + self.commands[command])

        wait_confirm.start()
        wait_response.start()

        self.xbee.tx(
            frame_id=chr(frame_id),
            dest_addr_long=self.addr_long,
            dest_addr=self.addr,
            data=cmd
        )

        wait_response.join(60)
        print "response " + str(wait_response.result)
        if wait_response.exception:
            raise wait_response.exception

        wait_confirm.join(60)
        print "confirm  " + str(wait_confirm.result)
        if wait_confirm.exception:
            raise wait_confirm.exception

    def rotate_counter_clockwise(self):
        self._tx("rot_right")

    def rotate_clockwise(self):
        self._tx("rot_left")

    def rotate_off(self):
        self._tx("rot_off")

    def set_red(self):
        self._tx("red")

    def set_green(self):
        self._tx("green")

    def set_blue(self):
        self._tx("blue")

    def set_level_red(self, level):
        self._tx("level_red", chr(level))

    def set_level_green(self, level):
        self._tx("level_green", chr(level))

    def set_level_blue(self, level):
        self._tx("level_blue", chr(level))

    def set_level_color(self, color, level):
        self._tx("level", binascii.unhexlify(binascii.hexlify(chr(level)) + color))

    def set_color(self, r, g, b):
        self._tx("color", chr(r) + chr(g) + chr(b))

    def set_position(self, pos):
        self._tx("pos", chr(pos))

    def set_jump(self, jump):
        self._tx("jump", chr(jump))

    def set_colors(self, colors):
        if len(colors) == 16:
            self._tx("full", binascii.unhexlify(string.join(colors, "")))
        else:
            print "length should be 16"

    def fade_off(self):
        self._tx("fade_off")

    def set_fade(self, fades):
        if len(fades) == 16:
            self._tx("set_fade", struct.pack('>16H', *fades))
        else:
            print "length should be 16"

    def use_gamma(self):
        self._tx("use_gamma")

    def gamma_off(self):
        self._tx("gamma_off")

    def set_brightness(self, brightness):
        self._tx("brightness", chr(brightness))