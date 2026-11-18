"""
core/jsonc.py — JSON avec commentaires (fichiers de protocole et de commandes).

Les fichiers protocols/*.json et msgLibrary/**/Msg_*.json peuvent contenir des commentaires,
comme dans VS Code (format « JSON with Comments ») :

    {
      // commentaire jusqu'à la fin de la ligne
      "name": "Modbus RTU",      // aussi en fin de ligne
      /* commentaire
         sur plusieurs lignes */
      "byte_order": "big"
    }

Les commentaires sont remplacés par des espaces avant la lecture JSON : les numéros de
ligne des messages d'erreur restent justes. Un « // » à l'intérieur d'une chaîne
("http://...") n'est pas un commentaire. Même fonction en TypeScript : js/src/core/jsonc.ts.
"""
import json


def strip_comments(text):
    """Texte JSON sans ses commentaires // et /* */ (remplacés par des espaces)."""
    out = []
    i, n = 0, len(text)
    in_string = False
    while i < n:
        c = text[i]
        if in_string:
            out.append(c)
            if c == "\\" and i + 1 < n:         # caractère échappé : \" ne ferme pas la chaîne
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_string = False
            i += 1
        elif c == '"':
            in_string = True
            out.append(c)
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(" " * (end - i))
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = n if end < 0 else end + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:end]))
            i = end
        else:
            out.append(c)
            i += 1
    return "".join(out)


def loads(text):
    """json.loads acceptant les commentaires. Lève json.JSONDecodeError."""
    return json.loads(strip_comments(text))


def load_file(path):
    """Lit un fichier JSON (UTF-8, avec ou sans BOM), commentaires acceptés."""
    with open(path, encoding="utf-8-sig") as f:
        return loads(f.read())
