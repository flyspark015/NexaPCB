from skidl import *


def build_connectors(nets):
    j1 = Part("Connector_Generic", "Conn_01x06", ref="J1", value="UART")
    j1.footprint = "Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical"
    j1[1] += nets["SYS_3V3"]
    j1[2] += nets["GND"]
    j1[3] += nets["UART_TX"]
    j1[4] += nets["UART_RX"]
