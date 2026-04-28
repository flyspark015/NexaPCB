from skidl import *

CTRL = Net("CTRL")
OUT = Net("OUT")
GND = Net("GND")

Q1 = Part("Transistor_BJT", "Q_NPN_BEC", ref="Q1", value="MMBT3904")
Q1.footprint = "Package_TO_SOT_SMD:SOT-23"
Q1["B"] += CTRL
Q1["C"] += OUT
Q1["E"] += GND

ERC()
generate_netlist(file_="bad_pin_pad_mismatch.net")
generate_xml(file_="bad_pin_pad_mismatch.xml")
