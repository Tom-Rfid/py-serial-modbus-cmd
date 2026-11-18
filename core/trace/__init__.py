"""
core/trace — Trace des échanges : enregistrement, relecture, analyse, comparaison.

Rôle
    - TraceRecorder : enregistre chaque trame TX / RX avec son horodatage dans
      un fichier CSV, au fil de l'eau (rien n'est perdu si le programme s'arrête)
    - load_trace()  : relit un fichier de trace
    - save_trace()  : réécrit une trace (après modification dans l'onglet Replay)
    - exchanges()   : regroupe la trace en échanges « une requête TX -> ses réponses RX »
    - analyze()     : statistiques de temps (durée, écarts entre envois, latences de réponse)
    - replay_delays(): délais à respecter pour rejouer les TX (temps d'origine, vitesse, délai fixe)
    - compare()     : compare une réponse reçue à la réponse enregistrée, octet par octet
    - judge_exchange(): verdict d'un échange rejoué, avec timeout de réponse
    - TraceDocument : trace ouverte dans l'onglet Replay (modification, enregistrement, renommage)

Organisation : events.py, recorder.py, files.py, analysis.py, compare.py, document.py

Format du fichier (CSV, séparateur « ; », lisible dans Excel) :

    t_ms;delta_ms;dir;len;hex;label
    0.0;0.0;TX;8;01 03 00 00 00 02 C4 0B;Lire consigne et mode #0x01
    41.7;41.7;RX;10;53 00 00 01 00 A0 60 01 7E 80;

    t_ms     : temps depuis le début de l'enregistrement (ms)
    delta_ms : temps depuis la ligne précédente (ms), pour lecture humaine
    dir      : TX (envoyé) ou RX (reçu)
    len      : nombre d'octets
    hex      : les octets
    label    : nom du message envoyé (TX), facultatif

Seules les colonnes dir et hex sont indispensables à la relecture ; t_ms est
utilisée pour rejouer avec les temps d'origine. Les lignes qui commencent
par « # » sont des commentaires. Ce paquet ne dépend pas de l'interface.
"""
from .analysis import Analysis, Exchange, analyze, exchanges, replay_delays
from .compare import DEFAULT_TIMEOUT_MS, compare, compare_responses, judge_exchange
from .document import TraceDocument
from .events import FIELDS, TraceEvent
from .files import load_trace, save_trace
from .recorder import TraceRecorder

__all__ = ["Analysis", "Exchange", "analyze", "exchanges", "replay_delays", "DEFAULT_TIMEOUT_MS", "compare",
           "compare_responses", "judge_exchange", "TraceDocument", "FIELDS", "TraceEvent", "load_trace",
           "save_trace", "TraceRecorder"]
