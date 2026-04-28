from skidl import *


def build_power(nets):
    c1 = Part("Device", "C", ref="C1", value="10uF")
    c1.footprint = "Capacitor_SMD:C_0805_2012Metric"
    c1[1] += nets["SYS_3V3"]
    c1[2] += nets["GND"]
