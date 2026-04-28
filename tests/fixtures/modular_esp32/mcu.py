from skidl import *


def build_mcu(nets):
    u1 = Part("RF_Module", "ESP32-S3-WROOM-1", ref="U1", value="ESP32-S3-WROOM-1-N16R8")
    u1.footprint = "RF_Module:ESP32-S3-WROOM-1"
    u1["3V3"] += nets["SYS_3V3"]
    u1["GND"] += nets["GND"]
    u1["TXD0"] += nets["UART_TX"]
    u1["RXD0"] += nets["UART_RX"]
