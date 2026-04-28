from skidl import *
from power import build_power
from mcu import build_mcu
from connectors import build_connectors

nets = {
    "SYS_3V3": Net("SYS_3V3"),
    "GND": Net("GND"),
    "UART_TX": Net("UART_TX"),
    "UART_RX": Net("UART_RX"),
}

build_power(nets)
build_mcu(nets)
build_connectors(nets)

ERC()
generate_netlist(file_="modular_esp32.net")
generate_xml(file_="modular_esp32.xml")
