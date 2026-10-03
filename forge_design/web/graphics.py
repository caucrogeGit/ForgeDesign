"""Transport commun d'une GraphicScene vers le Graphic Core navigateur.

Générique : aucun vocabulaire de client (Route Explorer, Entity Explorer). Les
adaptateurs métier construisent la scène ; ce module ne fait que la sérialiser.
"""

import json
from typing import Any

from markupsafe import Markup

_ESCAPES = (
    ("&", "\\u0026"),
    ("<", "\\u003c"),
    (">", "\\u003e"),
    ("\u2028", "\\u2028"),
    ("\u2029", "\\u2029"),
)


def scene_json_payload(scene: dict[str, Any]) -> Markup:
    """JSON pour un <script type="application/json" data-graphic-scene> inerte.

    <, >, &, U+2028 et U+2029 sont échappés en \\uXXXX : aucun texte de projet
    ne peut fermer le bloc (</script>) ni être interprété ; JSON.parse restitue
    le texte exact.
    """
    text = json.dumps(scene, ensure_ascii=False, separators=(",", ":"))
    for character, escape in _ESCAPES:
        text = text.replace(character, escape)
    return Markup(text)
