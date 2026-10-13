"""Masquage défensif de formes textuelles explicites, sans analyser le SQL.

Trois passes, dans cet ordre, chacune ne faisant que remplacer par le marqueur
(un texte déjà masqué reste identique : idempotence) :

1. en-têtes : ``…authorization`` (dernier composant, préfixe admis), ``cookie``
   et ``set-cookie`` (politique historique) masqués jusqu'à la fin de ligne ;
2. affectations ``clé=valeur`` / ``clé: valeur`` dont le **dernier composant**
   de la clé est sensible (``DB_PASSWORD``, ``SERVICE_TOKEN``, ``OPENAI_API_KEY``,
   ``JWT_PRIVATE_KEY``…), y compris dans une query ; ``PASSWORD_EXTRA`` ou
   ``token_count`` ne le sont pas ;
3. mot de passe d'une URL ``schéma://utilisateur:mot-de-passe@hôte``, reconnu
   syntaxiquement, sans décodage ni réparation d'URL.

Les mots-clés sont reconnus sans distinction de casse ASCII (``ſ``, ``ı`` ou le
signe kelvin n'en tiennent pas lieu). Chaque passe n'est tentée que si son indice
littéral figure dans le texte : résultat identique, coût réduit sur le texte
ordinaire. Ce n'est pas un détecteur de secrets : un secret isolé, une clé
inconnue ou une valeur encodée arbitrairement ne sont pas reconnus.
"""

import re

_MARK = "[masqué]"
# Début de composant : début du texte ou caractère non alphanumérique
# (« _ », « - », « . » compris). Lookbehind de largeur fixe.
_COMPONENT = r"(?<![^\W_])"
# Derniers composants sensibles ; ACCESS_TOKEN et REFRESH_TOKEN sont des *_TOKEN.
_SENSITIVE = (
    r"password|passwd|pwd|secret|token|api[_.-]?key|secret[_.-]?key|"
    r"private[_.-]?key|authorization"
)
_ASSIGNMENT = re.compile(
    rf"""(?i)((?:{_COMPONENT}(?a:{_SENSITIVE})|(?<![\w-])(?a:cookie|set-cookie))"""
    r"""["']?\s*[:=]\s*)"""
    # Le marqueur est une valeur atomique : une valeur citée déjà remplacée ne
    # doit pas, au passage suivant, absorber la ponctuation qui la suivait.
    # Une valeur citée inachevée reste sensible jusqu’à la fin de ligne.
    r"""(?:\[masqué\]|"(?:\\.|[^"\\\r\n])*"?|'(?:\\.|[^'\\\r\n])*'?|[^\s&,;"'<>]+)"""
)
_HEADER = re.compile(
    rf"""(?im)((?:{_COMPONENT}(?a:authorization)|(?<![\w-])(?a:cookie|set-cookie))"""
    r"""["']?\s*[:=]\s*)[^\r\n]+"""
)
# Schéma sans départ au milieu d'un mot ; mot de passe jusqu'au dernier « @ » de
# l'autorité (un « @ » non encodé reste masqué) ; « / ? # » ou un blanc la terminent.
_URL_PASSWORD = re.compile(
    r"""(?i)((?<![a-z0-9+.-])[a-z][a-z0-9+.-]*://[^\s/?#@:]*:)[^\s/?#]+(?=@)"""
)
# Indices nécessaires à toute correspondance de chaque passe (minuscules ASCII :
# les mots-clés étant ASCII, ``lower()`` ne peut pas en faire disparaître un).
_HEADER_HINTS = ("authorization", "cookie")
_ASSIGNMENT_HINTS = ("pass", "pwd", "secret", "token", "key", "authorization", "cookie")
_URL_HINT = "://"


def _mask(match: re.Match[str]) -> str:
    return match[1] + _MARK


def redact_debug_text(value: str) -> str:
    """Masquer les formes sensibles connues ; aucune garantie exhaustive."""
    lowered = value.lower()
    if any(hint in lowered for hint in _HEADER_HINTS):
        value = _HEADER.sub(_mask, value)
    if any(hint in lowered for hint in _ASSIGNMENT_HINTS):
        value = _ASSIGNMENT.sub(_mask, value)
    if _URL_HINT in value:
        value = _URL_PASSWORD.sub(_mask, value)
    return value
