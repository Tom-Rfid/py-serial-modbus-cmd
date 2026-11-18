"""
core/link_switch.py — Liaison série OU TCP, vue par l'interface comme une seule liaison.

    link = LinkSwitch(SerialLink(), TcpLink(), mode="serial")
    link.mode = "tcp"                   # seulement quand rien n'est connecté
    link.connect("192.168.1.10", 502)   # transmis à la liaison active
    link.events.get()                   # file d'événements de la liaison active

Les réglages communs (gap_ms, frame_end) s'appliquent aux deux liaisons.
"""
SERIAL, TCP = "serial", "tcp"
MODES = (SERIAL, TCP)
SHARED = ("gap_ms", "frame_end")        # réglages copiés sur les deux liaisons


class LinkSwitch:
    def __init__(self, serial_link, tcp_link, mode=SERIAL):
        object.__setattr__(self, "links", {SERIAL: serial_link, TCP: tcp_link})
        object.__setattr__(self, "_mode", mode if mode in MODES else SERIAL)

    @property
    def mode(self):
        return self._mode

    @mode.setter
    def mode(self, value):
        if value not in MODES:
            raise ValueError(f"liaison inconnue : {value}")
        if self.active.connected:
            raise ConnectionError("déconnecter avant de changer de liaison")
        object.__setattr__(self, "_mode", value)

    @property
    def active(self):
        return self.links[self._mode]

    def __getattr__(self, name):
        # Appelé seulement pour ce qui n'est pas défini ici : transmis à la liaison active
        return getattr(self.links[self._mode], name)

    def __setattr__(self, name, value):
        if name == "mode":
            LinkSwitch.mode.fset(self, value)               # passe par les vérifications ci-dessus
        elif name in SHARED:
            for link in self.links.values():
                setattr(link, name, value)
        else:
            setattr(self.active, name, value)
