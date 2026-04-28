from skidl import *

VCC = Net("VCC")
GND = Net("GND")

J1 = Part("Connector_Generic", "Conn_01x03", ref="J1", value="BAD_CONN")
J1.footprint = "Connector_PinHeader_2.54mm:PinHeader_1x03_P2.54mm_Vertical"
J1[1] += VCC
J1[2] += GND

ERC()
generate_netlist(file_="bad_unconnected_pins.net")
generate_xml(file_="bad_unconnected_pins.xml")
