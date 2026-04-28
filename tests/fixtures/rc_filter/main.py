from skidl import *

VCC = Net("VCC")
OUT = Net("OUT")
GND = Net("GND")

R1 = Part("Device", "R", ref="R1", value="1k")
R1.footprint = "Resistor_SMD:R_0603_1608Metric"
R1.fields["LCSC"] = "C25804"

C1 = Part("Device", "C", ref="C1", value="100nF")
C1.footprint = "Capacitor_SMD:C_0603_1608Metric"
C1.fields["LCSC"] = "C1525"

R1[1] += VCC
R1[2] += OUT
C1[1] += OUT
C1[2] += GND

ERC()
generate_netlist(file_="rc_filter.net")
generate_xml(file_="rc_filter.xml")
