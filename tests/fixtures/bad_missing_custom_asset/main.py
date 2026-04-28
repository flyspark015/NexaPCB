from skidl import *

VCC = Net("VCC")
GND = Net("GND")

J1 = Part("Connector_Generic", "Conn_01x02", ref="J1", value="MISSING_CUSTOM")
J1.footprint = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
J1.fields["CUSTOM_SYMBOL"] = "/missing/demo.kicad_sym"
J1.fields["CUSTOM_SYMBOL_NAME"] = "DEMO_CONN"
J1.fields["CUSTOM_FOOTPRINT"] = "/missing/demo.kicad_mod"
J1.fields["CUSTOM_MODEL"] = "/missing/demo.step"
J1[1] += VCC
J1[2] += GND

ERC()
generate_netlist(file_="bad_missing_custom_asset.net")
generate_xml(file_="bad_missing_custom_asset.xml")
