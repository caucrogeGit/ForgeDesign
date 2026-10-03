"""Limites de la ressource Circuit V0.1, plus strictes que le plafond spécialisé.

Le plafond en octets borne effectivement la ressource ; les plafonds de
collections bornent la validation (O(n)) et les futurs algorithmes (topologie,
routage) indépendamment du contenu des chaînes.
"""

# 4 Mio : un schéma de plusieurs milliers d'objets tient sous 1 Mio ; le plafond
# technique des ressources spécialisées (64 Mio) n'est pas un objectif Circuit.
MAX_CIRCUIT_RESOURCE_BYTES = 4 * 1024 * 1024

# Coordonnées et dimensions de page en unités de grille entières, positives.
MAX_CIRCUIT_PAGE_UNITS = 4096

MAX_CIRCUIT_COMPONENTS = 4096
MAX_CIRCUIT_CONNECTIONS = 8192
MAX_CIRCUIT_JUNCTIONS = 4096
MAX_CIRCUIT_ANNOTATIONS = 4096
# Points intermédiaires d'une route orthogonale : quelques coudes en pratique.
MAX_CIRCUIT_ROUTE_POINTS = 256
MAX_CIRCUIT_PROPERTIES = 64

MAX_CIRCUIT_TEXT_CHARS = 4096
MAX_CIRCUIT_ID_CHARS = 66  # préfixe « x_ » + jeton de 8 à 64 caractères
MAX_CIRCUIT_TYPE_CHARS = 64
MAX_CIRCUIT_TERMINAL_ID_CHARS = 64
MAX_CIRCUIT_REFERENCE_CHARS = 32
MAX_CIRCUIT_PROPERTY_KEY_CHARS = 64
MAX_CIRCUIT_PROPERTY_TEXT_CHARS = 256

# Entiers de propriétés représentables exactement en JavaScript (Graphic Core).
MAX_CIRCUIT_SAFE_INTEGER = 2**53 - 1
