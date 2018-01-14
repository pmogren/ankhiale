#! /usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import division # to calculate a float from integers
import smbus, time, sys, argparse, datetime, subprocess
import DS1621 as ds


def CelsiusToFarenheit(degreesC):
    return 1.8 * degreesC + 32

def play_sound(path):
    subprocess.call(['/usr/bin/mpg123', '-q', path])

parser = argparse.ArgumentParser(description="Dual thermostat and temperature alarm.")
parser.add_argument("--configure", action="store_true", help="Configure thermostats")
parser.add_argument("--start", choices=["oneshot", "continuous"],
                    help="Activate thermostats for one-shot use or continuous use")
parser.add_argument("--poll", type=int, help="Read from thermostats periodically, in seconds")
parser.add_argument("--iterations", type=int, help="Number of times to read thermostats. Defaults to unlimited if --poll is specified, otherwise 1.")
parser.add_argument("--stop", action="store_true", help="Deactivate continuous operation")
parser.add_argument("--high-alarm-sound", metavar="highAlarmSound",
                    default="{}/alarm.mp3".format(os.path.dirname(os.path.realpath(__file__))),
                    help="Audio file for high temperature alarm")
parser.add_argument("--low-alarm-sound", metavar="lowAlarmSound",
                    default="{}/alarm.mp3".format(os.path.dirname(os.path.realpath(__file__))),
                    help="Audio file for low temperature alarm")

args = parser.parse_args()
if not len(sys.argv) > 1:
    parser.print_help()
    sys.exit(1)

# must instantiate the bus.
# on RPi 256 MB version, it"s bus 0
# on RPi 512 MB version, it"s bus 1
i2cBus = smbus.SMBus(1)

# sensorname at bus address. (per DS1621 address pins)
Heater = 0x49
Cooler = 0x4f

if args.configure:
    print "INFO: Configuring thermostats..."

    # First reading after startup is not usable, only wakes the devices up.
    ds.wake_up(i2cBus, Heater)
    ds.wake_up(i2cBus, Cooler)

    ##   Continuous mode is useful if you want to use the thermostat pin
    ##   with rapidly changing temperatures e.g. inside an enclosure

    ### In Continuous mode, you can set hysteresis in two ways.

    # upper and lower thermostat limits, decimals are rounded to the nearest .5 C
    ds.set_thermostat(i2cBus, Heater, 19.7, 20.2)
    ds.set_thermostat(i2cBus, Cooler, 25.3, 25.8)

    ### Alternatively, set upper limit and hysteresis delta, default = .5 C
    # ds.set_thermohyst(i2c_0, Room, 19)

    # set thermostat pin active Cooler
    ds.set_thermoLOW(i2cBus, Heater, LOW=False)
    # set thermostat pin active Heater
    ds.set_thermoLOW(i2cBus, Cooler, LOW=True)

    # print settings
    #ds.read_config(i2cBus, Heater)  # this output can be confusing
    heaterSettings = "\n\tHeater on: {} F\n\tHeater off: {} F"
    #get_thermostat returns low_therm, hi_therm
    print heaterSettings.format(*map(CelsiusToFarenheit, ds.get_thermostat(i2cBus, Heater)))

    #ds.read_config(i2cBus, Cooler)  # this output can be confusing
    coolerSettings = "\n\tCooler off: {} F\n\tCooler on: {} F"
    print coolerSettings.format(*map(CelsiusToFarenheit, ds.get_thermostat(i2cBus, Cooler)))
    print
else:
    print "WARN: assuming thermostats are already configured"


readFunc = ds.read_degreesC_continous # misspelled in library
if args.start == "continuous":
    print "INFO: activating thermostats for continuous operation..."
    # set continuous measurement mode and start converting
    ds.set_mode(i2cBus, Heater, "Continuous")
    ds.set_mode(i2cBus, Cooler, "Continuous")
    # allow some wake-up time
    time.sleep(0.6)
elif args.start == "oneshot":
    readFunc = ds.read_degreesC_all_oneshot
else:
    print "WARN: assuming thermostats already operating continuously"


iterations = 1
if args.poll:
    iterations = sys.maxsize
if args.iterations != None:
    iterations = args.iterations

i = 0
while i < iterations:
    #readFunc returns an array: [degreesC_byte, degreesC_word, degreesC_HR]
    #WARN: Cooler Resolution reading is buggy, sometimes very inaccurate (way off from low-res readings)
    heaterReading = readFunc(i2cBus, Heater)[1]
    coolerReading = readFunc(i2cBus, Cooler)[1]
    avgReading = (heaterReading + coolerReading) / 2
    print '{}"Timestamp": "{}", "HeaterTemp": {}, "CoolerTemp": {}, "AverageTemp": {}, "TempUnit": "F"{}'.format(
        "{", datetime.datetime.now().isoformat(),
        CelsiusToFarenheit(heaterReading),
        CelsiusToFarenheit(coolerReading),
        CelsiusToFarenheit(avgReading), "}")
    i = i + 1
    if i < iterations and args.poll:
        time.sleep(args.poll)


if args.stop:
    print "INFO: stopping continuous operation"
    ds.stop_conversion(i2cBus, Heater)
    ds.stop_conversion(i2cBus, Cooler)
