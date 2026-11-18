"""
core/framing.py — Découpage des octets reçus en trames (liaison série ou TCP).

Deux règles, appliquées ensemble :
    - silence : une trame est finie quand rien n'est arrivé depuis plus de `gap_ms`
    - fin de trame : si `frame_end` est donné (Modbus ASCII : b"\\r\\n"), la trame est
      finie dès que ce délimiteur arrive, sans attendre le silence

    octets : 3A 30 31 … 0D 0A 3A 30 32 … 0D 0A        (deux trames collées)
    trames : [3A 30 31 … 0D 0A] [3A 30 32 … 0D 0A]    (coupées au délimiteur)

    splitter = FrameSplitter(gap_ms=20, frame_end=b"\\r\\n")
    frames = splitter.feed(octets, time.monotonic())   # trames terminées par le délimiteur
    frames = splitter.tick(time.monotonic())           # trame terminée par le silence
"""


class FrameSplitter:
    def __init__(self, gap_ms=20.0, frame_end=None):
        self.gap_ms = gap_ms
        self.frame_end = frame_end          # bytes, ou None
        self.buf = bytearray()              # octets de la trame en cours
        self.last = 0.0                     # instant du dernier octet reçu (secondes)

    def tick(self, now):
        """Silence plus long que gap_ms depuis le dernier octet : la trame en cours est finie."""
        if self.buf and (now - self.last) * 1000 > self.gap_ms:
            return [self.flush()]
        return []

    def feed(self, data, now):
        """Ajoute des octets reçus ; retourne les trames terminées (silence avant, ou délimiteur)."""
        frames = self.tick(now)
        if not data:
            return frames
        self.buf += data
        self.last = now
        if self.frame_end:
            frames += self._split_on_end()
        return frames

    def _split_on_end(self):
        frames = []
        end = bytes(self.frame_end)
        index = self.buf.find(end)
        while index >= 0:
            cut = index + len(end)
            frames.append(bytes(self.buf[:cut]))
            del self.buf[:cut]
            index = self.buf.find(end)
        return frames

    def flush(self):
        """Trame en cours (même incomplète), et remise à zéro."""
        frame = bytes(self.buf)
        self.buf.clear()
        return frame
