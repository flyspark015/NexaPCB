from __future__ import annotations

from pathlib import Path

from nexapcb.utils.fs import write_text


EXAMPLES = {
    "rc_filter": {
        "main.py": """from skidl import *\nVCC=Net('VCC'); OUT=Net('OUT'); GND=Net('GND')\nR1=Part('Device','R',ref='R1',value='1k'); R1.footprint='Resistor_SMD:R_0603_1608Metric'; R1.fields['LCSC']='C25804'\nC1=Part('Device','C',ref='C1',value='100nF'); C1.footprint='Capacitor_SMD:C_0603_1608Metric'; C1.fields['LCSC']='C1525'\nR1[1]+=VCC; R1[2]+=OUT; C1[1]+=OUT; C1[2]+=GND\nERC(); generate_netlist(file_='rc_filter.net'); generate_xml(file_='rc_filter.xml')\n""",
    },
    "esp32_led_button": {
        "main.py": """from skidl import *\nV3=Net('SYS_3V3'); GND=Net('GND'); LED=Net('LED'); EN=Net('ESP_EN'); BOOT=Net('ESP_BOOT')\nU1=Part('Connector_Generic','Conn_01x04',ref='U1',value='ESP32_PLACEHOLDER'); U1.footprint='RF_Module:ESP32-S3-WROOM-1'\nR1=Part('Device','R',ref='R1',value='330'); R1.footprint='Resistor_SMD:R_0603_1608Metric'; R1.fields['LCSC']='C25804'\nD1=Part('Device','LED',ref='D1',value='RED'); D1.footprint='LED_SMD:LED_0603_1608Metric'\nSW1=Part('Switch','SW_Push',ref='SW1',value='BOOT'); SW1.footprint='Button_Switch_SMD:SW_SPST_TL3342'\nU1[1]+=V3; U1[2]+=GND; U1[3]+=BOOT; U1[4]+=EN; R1[1]+=V3; R1[2]+=LED; D1['A']+=LED; D1['K']+=GND; SW1[1]+=BOOT; SW1[2]+=GND\nERC(); generate_netlist(file_='esp32_led_button.net'); generate_xml(file_='esp32_led_button.xml')\n""",
    },
    "modular_esp32": {
        "README.md": "Run main.py as the project entry. It imports power.py, mcu.py, and connectors.py.\n",
        "parts.py": """from skidl import *\ndef r(ref,val):\n p=Part('Device','R',ref=ref,value=val); p.footprint='Resistor_SMD:R_0603_1608Metric'; return p\n""",
        "power.py": """from skidl import *\ndef build_power(n):\n C1=Part('Device','C',ref='C1',value='10uF'); C1.footprint='Capacitor_SMD:C_0805_2012Metric'; C1[1]+=n['SYS_3V3']; C1[2]+=n['GND']\n""",
        "mcu.py": """from skidl import *\ndef build_mcu(n):\n U1=Part('RF_Module','ESP32-S3-WROOM-1',ref='U1',value='ESP32-S3-WROOM-1-N16R8'); U1.footprint='RF_Module:ESP32-S3-WROOM-1'; U1['3V3']+=n['SYS_3V3']; U1['GND']+=n['GND']; U1['TXD0']+=n['UART_TX']; U1['RXD0']+=n['UART_RX']\n""",
        "connectors.py": """from skidl import *\ndef build_connectors(n):\n J1=Part('Connector_Generic','Conn_01x06',ref='J1',value='UART'); J1.footprint='Connector_PinHeader_2.54mm:PinHeader_1x06_P2.54mm_Vertical'; J1[1]+=n['SYS_3V3']; J1[2]+=n['GND']; J1[3]+=n['UART_TX']; J1[4]+=n['UART_RX']\n""",
        "main.py": """from skidl import *\nfrom power import build_power\nfrom mcu import build_mcu\nfrom connectors import build_connectors\nn={'SYS_3V3':Net('SYS_3V3'),'GND':Net('GND'),'UART_TX':Net('UART_TX'),'UART_RX':Net('UART_RX')}\nbuild_power(n); build_mcu(n); build_connectors(n)\nERC(); generate_netlist(file_='modular_esp32.net'); generate_xml(file_='modular_esp32.xml')\n""",
    },
    "custom_part_demo": {
        "main.py": """from skidl import *\nVCC=Net('VCC'); GND=Net('GND')\nJ1=Part('Connector_Generic','Conn_01x02',ref='J1',value='CUSTOM_CONN'); J1.footprint='Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical';\nJ1.fields['CUSTOM_SYMBOL']='__CUSTOM_SYMBOL__'\nJ1.fields['CUSTOM_SYMBOL_NAME']='DEMO_CONN'\nJ1.fields['CUSTOM_FOOTPRINT']='__CUSTOM_FOOTPRINT__'\nJ1.fields['CUSTOM_MODEL']='__CUSTOM_MODEL__'\nJ1[1]+=VCC; J1[2]+=GND\nERC(); generate_netlist(file_='custom_part_demo.net'); generate_xml(file_='custom_part_demo.xml')\n""",
        "../custom_assets/symbols/demo.kicad_sym": "(kicad_symbol_lib (version 20211014) (generator nexapcb))\n",
        "../custom_assets/footprints/demo.kicad_mod": "(footprint \"demo\" (version 20221018) (generator nexapcb))\n",
        "../custom_assets/3d_models/demo.step": "ISO-10303-21;\nEND-ISO-10303-21;\n",
    },
}


def list_examples() -> list[str]:
    return sorted(EXAMPLES)


def create_example(name: str, output: str | Path) -> Path:
    if name not in EXAMPLES:
        raise ValueError(f"Unknown example: {name}")
    out = Path(output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    for rel, content in EXAMPLES[name].items():
        if name == "custom_part_demo" and rel == "main.py":
            content = (
                content.replace("__CUSTOM_SYMBOL__", str((out.parent / "custom_assets" / "symbols" / "demo.kicad_sym").resolve()))
                .replace("__CUSTOM_FOOTPRINT__", str((out.parent / "custom_assets" / "footprints" / "demo.kicad_mod").resolve()))
                .replace("__CUSTOM_MODEL__", str((out.parent / "custom_assets" / "3d_models" / "demo.step").resolve()))
            )
        write_text(out / rel, content)
    return out
