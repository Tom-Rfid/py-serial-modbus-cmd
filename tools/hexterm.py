"""
tools/hexterm.py — Mini terminal série en hexa, en ligne de commande.

Alternative légère à l'interface graphique, pour un test rapide.

Usage :
    python tools/hexterm.py            liste les ports disponibles
    python tools/hexterm.py COM3       ouvre COM3 à 115200 bauds (8N1)
    python tools/hexterm.py COM3 9600  autre vitesse

Une fois connecté :
    - taper des octets en hexa (AA 55 01 0D, AA55010D ou 0xAA,0x55) puis Entrée
    - les octets reçus s'affichent en continu, préfixés par <<
    - taper q puis Entrée pour quitter (ou Ctrl+C)

Ne dépend que de pyserial (pas de core/) : le fichier peut être copié seul.
"""
import sys
import threading

import serial
from serial.tools import list_ports


def reader(ser):
    """Thread de lecture : affiche les octets reçus tant que le port est ouvert."""
    while ser.is_open:
        try:
            # Lit tout ce qui est disponible, ou attend au plus `timeout` un octet
            data = ser.read(ser.in_waiting or 1)
        except serial.SerialException:
            break                   # port fermé ou débranché
        if data:
            # \r revient en début de ligne pour ne pas mélanger avec la saisie en cours,
            # puis on réaffiche l'invite ">> "
            print(f"\r<< {data.hex(' ').upper()}\n>> ", end="", flush=True)


def main():
    # Sans argument : liste les ports et quitte
    if len(sys.argv) < 2:
        print("Ports disponibles :")
        for p in list_ports.comports():
            print(f"  {p.device}  -  {p.description}")
        print("\nUsage : python hexterm.py COM3 [baud]")
        return

    port = sys.argv[1]
    baud = int(sys.argv[2]) if len(sys.argv) > 2 else 115200

    # 8 bits, sans parité, 1 bit de stop, sans contrôle de flux (valeurs par défaut de pyserial)
    ser = serial.Serial(port, baud, timeout=0.1)
    print(f"Ouvert : {port} @ {baud} bauds. Tape q pour quitter.")
    # daemon=True : le thread s'arrête avec le programme
    threading.Thread(target=reader, args=(ser,), daemon=True).start()

    try:
        while True:
            line = input(">> ").strip()
            if line.lower() == "q":
                break
            if not line:
                continue
            try:
                # Accepte "AA 55", "AA55" et "0xAA,0x55"
                payload = bytes.fromhex(line.replace("0x", "").replace(",", " "))
            except ValueError:
                print("Hexa invalide, ex : AA 55 01 0D")
                continue
            ser.write(payload)
            print(f"   envoyé : {payload.hex(' ').upper()} ({len(payload)} octets)")
    except KeyboardInterrupt:       # Ctrl+C
        pass
    finally:
        ser.close()


if __name__ == "__main__":
    main()
