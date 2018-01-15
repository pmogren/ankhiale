#! /usr/bin/python
# -*- coding: utf-8 -*-

from __future__ import division # to calculate a float from integers
import smbus, time, sys, argparse, datetime, subprocess, os
import DS1621 as ds


def celsius_to_farenheit(degreesC):
    return 1.8 * degreesC + 32


def farenheit_to_celsius(degreesF):
    return (degreesF - 32) * 0.5555555


def play_sound(path):
    print "INFO: Playing sound file: {}".format(path)
    subprocess.call(['/usr/bin/mpg123', '-q', path])


def parse_args():
    parser = argparse.ArgumentParser(description="Dual thermostat and temperature alarm.")
    parser.add_argument("--configure", action="store_true",
                        help="Configure thermostats")
    parser.add_argument("--start", choices=["oneshot", "continuous"],
                        help="Activate thermostats for one-shot use or continuous use")
    parser.add_argument("--poll", type=int,
                        help="Read from thermostats repeatedly on this period, in seconds")
    parser.add_argument("--iterations", type=int,
                        help="Number of times to read thermostats. Defaults to unlimited if --poll is specified, otherwise 1.")
    parser.add_argument("--stop", action="store_true",
                        help="Deactivate continuous operation")
    parser.add_argument("--alarm", action="store_true",
                        help="Play alarm sound when temperature is out of desired range")
    parser.add_argument("--high-temp-sound", dest="highTempSound",
                        default="{}/alarm.mp3".format(os.path.dirname(os.path.realpath(__file__))),
                        help="Audio file for high temperature alarm")
    parser.add_argument("--low-temp-sound", dest="lowTempSound",
                        default="{}/alarm.mp3".format(os.path.dirname(os.path.realpath(__file__))),
                        help="Audio file for low temperature alarm")
    parser.add_argument("--min-temp", dest="minTemp", type=float, default=68.0,
                        help="Minimum temperature, in degrees Farenheit")
    parser.add_argument("--max-temp", dest="maxTemp", type=float, default=78.0,
                        help="Maximum temperature, in degrees Farenheit")
    parser.add_argument("--hysteresis", type=float, default=1,
                        help="Temperature change required before stopping heater/cooler connected to thermostat")
    return parser.parse_args()


def configure(args, i2cBus, Heater, Cooler):
    print "INFO: Configuring thermostats..."

    # First reading after startup is not usable, only wakes the devices up.
    ds.wake_up(i2cBus, Heater)
    ds.wake_up(i2cBus, Cooler)

    ##   Continuous mode is useful if you want to use the thermostat pin
    ##   with rapidly changing temperatures e.g. inside an enclosure

    ### In Continuous mode, you can set hysteresis in two ways.

    # upper and lower thermostat limits, decimals are rounded to the nearest .5 C
    ds.set_thermostat(i2cBus, Heater, farenheit_to_celsius(args.minTemp),
                    farenheit_to_celsius(args.minTemp + args.hysteresis))
    ds.set_thermostat(i2cBus, Cooler, farenheit_to_celsius(args.maxTemp - args.hysteresis),
                    farenheit_to_celsius(args.maxTemp))

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
    print heaterSettings.format(*map(celsius_to_farenheit, ds.get_thermostat(i2cBus, Heater)))

    #ds.read_config(i2cBus, Cooler)  # this output can be confusing
    coolerSettings = "\n\tCooler off: {} F\n\tCooler on: {} F"
    print coolerSettings.format(*map(celsius_to_farenheit, ds.get_thermostat(i2cBus, Cooler)))
    print


def main():
    if not len(sys.argv) > 1:
        parser.print_help()
        sys.exit(1)
    args = parse_args()

    # must instantiate the bus.
    # on RPi 256 MB version, it"s bus 0
    # on RPi 512 MB version, it"s bus 1
    i2cBus = smbus.SMBus(1)

    # sensorname at bus address. (per DS1621 address pins)
    Heater = 0x49
    Cooler = 0x4f

    if args.configure:
        configure(args, i2cBus, Heater, Cooler)
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
        #WARN: High-Resolution reading is buggy, sometimes very inaccurate (way off from low-res readings)
        heaterReading = celsius_to_farenheit(readFunc(i2cBus, Heater)[1])
        coolerReading = celsius_to_farenheit(readFunc(i2cBus, Cooler)[1])
        highTempAlarm = coolerReading > args.maxTemp
        lowTempAlarm = heaterReading < args.minTemp

        avgReading = (heaterReading + coolerReading) / 2
        print '{}"Timestamp": "{}", "HeaterTemp": {}, "CoolerTemp": {}, "AverageTemp": {}, "TempUnit": {}, "HighTempAlarm": {}, "LowTempAlarm": {}{}'.format(
            "{",
            datetime.datetime.now().isoformat(),
            heaterReading,
            coolerReading,
            avgReading,
            "F",
            highTempAlarm,
            lowTempAlarm,
            "}")

        if highTempAlarm and args.alarm:
            play_sound(args.highTempSound)
        if lowTempAlarm and args.alarm:
            play_sound(args.lowTempSound)

        i = i + 1
        if i < iterations and args.poll:
            time.sleep(args.poll)

    if args.stop:
        print "INFO: stopping continuous operation"
        ds.stop_conversion(i2cBus, Heater)
        ds.stop_conversion(i2cBus, Cooler)


if __name__ == "__main__":
    main()
