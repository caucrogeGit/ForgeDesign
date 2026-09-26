"""Contrôle d'origine des actions locales modifiant l'état runtime."""

import re

from core.http.request import Request


def is_local_action(request: Request) -> bool:
    """Refuser les origines absentes ou étrangères avant toute mutation.

    Alternative sans session au CSRF Forge : contrôle navigateur uniquement,
    pas authentification des clients locaux capables de forger leurs en-têtes.
    """
    host = request.header("Host", "")
    return (
        re.fullmatch(r"127\.0\.0\.1(?::[0-9]{1,5})?", host) is not None
        and request.header("Origin") == f"http://{host}"
        and request.header("Sec-Fetch-Site") in (None, "same-origin")
    )
