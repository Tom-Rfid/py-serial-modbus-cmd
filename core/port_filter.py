"""
core/port_filter.py — Filtre de la liste des ports série (sans dépendance à pyserial).

    DEFAULT_PORT_FILTER : adaptateurs gardés par la case « FTDI » si edition.json ne donne pas
                          sa propre liste (clé "ports" → "filter", voir core/edition.py)
    enabled_ids()       : couples (VID, PID) des adaptateurs actifs d'une liste
    Reconnaissance des ports Bluetooth : utilisée par core/serial_link.py (PortInfo.is_bluetooth)
"""

# Filtre des ports par défaut (edition.json peut le remplacer, clé "ports" : voir core/edition.py) :
# adaptateurs FTDI, identifiant USB du fabricant (VID) et des puces (PID)
FTDI_VID = 0x0403
DEFAULT_PORT_FILTER = [
    {"name": "FT232R / FT245R", "vid": FTDI_VID, "pid": 0x6001, "enabled": True},
    {"name": "FT2232", "vid": FTDI_VID, "pid": 0x6010, "enabled": True},
    {"name": "FT4232", "vid": FTDI_VID, "pid": 0x6011, "enabled": True},
    {"name": "FT232H", "vid": FTDI_VID, "pid": 0x6014, "enabled": True},
    {"name": "FT-X (FT230X, FT231X…)", "vid": FTDI_VID, "pid": 0x6015, "enabled": True},
]

# Ports Bluetooth (série sur Bluetooth) : reconnus par leur identifiant matériel ou leur nom
BLUETOOTH_HINTS = ("BTHENUM", "BLUETOOTH")       # Windows : BTHENUM\{…} ; « Lien série … Bluetooth »
BLUETOOTH_DEVICES = ("/dev/rfcomm", "/dev/cu.Bluetooth", "/dev/tty.Bluetooth")    # Linux, macOS


def enabled_ids(port_filter):
    """Couples (VID, PID) des adaptateurs actifs ("enabled") d'un filtre ; VID / PID en
    nombre ou en texte hexa ("0x0403")."""
    ids = set()
    for item in port_filter or []:
        if item.get("enabled", True):
            try:
                ids.add((int(str(item["vid"]), 0), int(str(item["pid"]), 0)))
            except (KeyError, ValueError):
                continue                        # entrée incomplète : ignorée
    return ids
