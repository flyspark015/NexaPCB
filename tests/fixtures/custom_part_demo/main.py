from skidl import *
from pathlib import Path

ROOT = Path(__file__).resolve().parent

VCC = Net("VCC")
GND = Net("GND")

J1 = Part("Connector_Generic", "Conn_01x02", ref="J1", value="CUSTOM_CONN")
J1.footprint = "Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical"
J1.fields["CUSTOM_SYMBOL"] = str((ROOT / "custom_assets" / "symbols" / "demo.kicad_sym").resolve())
J1.fields["CUSTOM_SYMBOL_NAME"] = "DEMO_CONN"
J1.fields["CUSTOM_FOOTPRINT"] = str((ROOT / "custom_assets" / "footprints" / "demo.kicad_mod").resolve())
J1.fields["CUSTOM_MODEL"] = str((ROOT / "custom_assets" / "3d_models" / "demo.step").resolve())
J1[1] += VCC
J1[2] += GND

ERC()
generate_netlist(file_="custom_part_demo.net")
generate_xml(file_="custom_part_demo.xml")
