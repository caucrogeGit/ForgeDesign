"""Masqueur commun de Debug Center (FD-DEBUG-006) : dernier composant sensible,
familles composées, Authorization préfixé, Cookie historique, mot de passe d'URL
syntaxique, faux positifs, idempotence, lignes, complexité et modèle public."""

import ast
import itertools
import statistics
import time
from pathlib import Path

import pytest
from test_debug_errors import encoded, journal
from test_web_recent_projects import project

from forge_design.forge import debug_redaction
from forge_design.forge.debug_errors import read_debug_errors
from forge_design.forge.debug_redaction import redact_debug_text
from forge_design.tools.debug_filters import DebugFilter, filter_debug_events
from forge_design.web.debug_detail import debug_event_url

M = "[masqué]"


def masked(value: str) -> str:
    result = redact_debug_text(value)
    assert redact_debug_text(result) == result, value
    return result


@pytest.mark.parametrize(
    "key",
    [
        "password",
        "PASSWORD",
        "db_password",
        "DB_PASSWORD",
        "MYSQL_PASSWORD",
        "DATABASE_PASSWORD",
        "SMTP_PASSWORD",
        "mysql-password",
        "fooDB_PASSWORD",
        "--password",
        "passwd",
        "DB_PWD",
        "app.secret",
        "APP_SECRET",
        "JWT_SECRET",
        "client_secret",
        "secret_key",
        "SECRET_KEY",
        "api_token",
        "API_TOKEN",
        "GITHUB_TOKEN",
        "AUTH_TOKEN",
        "SERVICE_TOKEN",
        "access_token",
        "refresh_token",
        "api_key",
        "apikey",
        "X-Api-Key",
        "service_api_key",
        "OPENAI_API_KEY",
        "STRIPE_API_KEY",
        "PRIVATE_KEY",
        "JWT_PRIVATE_KEY",
        "SERVICE-PRIVATE-KEY",
        "app.private.key",
    ],
)
@pytest.mark.parametrize("separator", ["=", ": ", " = ", ":"])
def test_last_component_is_sensitive(key: str, separator: str) -> None:
    assert masked(f"{key}{separator}VerySecret123") == f"{key}{separator}{M}"


@pytest.mark.parametrize(
    "text",
    [
        "password_policy=strict",
        "token_count=3",
        "tokenizer=bpe",
        "secretary=Alice",
        "monkey=banana",
        "api_keys_count=4",
        "API_KEY_STATUS=ok",
        "DB_PASSWORD_EXTRA=x",
        "PRIVATE_KEY_PATH=/etc/key.pem",
        "PRIVATE_KEY_FILE=key.pem",
        "Authorization_Mode=strict",
        "AuthorizationCount=3",
        "mytoken=x",
        "key=value",
        "password policy",
        "token count: 3",
        "session_cookie=abc, user=roger",
        "https://example.org",
        "https://roger@example.org",
        "https://example.org:8443/path?page=2",
        "scheme://user:@host",
        "tokenizer failed café 😀",
    ],
)
def test_ordinary_text_is_preserved(text: str) -> None:
    assert masked(text) == text


def test_quoted_and_unfinished_values() -> None:
    assert masked('DB_PASSWORD="secret word" ok') == f"DB_PASSWORD={M} ok"
    assert masked("DB_PASSWORD='secret word' ok") == f"DB_PASSWORD={M} ok"
    assert masked('"DB_PASSWORD": "secret word"}') == f'"DB_PASSWORD": {M}}}'
    # Idempotence : la ponctuation qui suivait une valeur citée n'est pas absorbée
    # au passage suivant (défaut antérieur à FD-DEBUG-006).
    assert masked('(password="secret word")') == f"(password={M})"
    assert masked('API_TOKEN="unfinished secret\nsuite') == f"API_TOKEN={M}\nsuite"
    assert masked("API_TOKEN='unfinished secret\r\nsuite") == f"API_TOKEN={M}\r\nsuite"


def test_authorization_with_prefix_masks_to_end_of_line() -> None:
    for key in ("Authorization", "Proxy-Authorization", "HTTP_AUTHORIZATION"):
        for separator in (": ", "="):
            line = f"{key}{separator}Basic dXNlcjpzZWNyZXQ= secret"
            assert masked(line + "\nnext") == f"{key}{separator}{M}\nnext"
    assert masked("X.Authorization: Bearer a.b.c") == f"X.Authorization: {M}"
    # Cookie et Set-Cookie : politique historique, inchangée.
    assert masked("Cookie: session=secret; other=x") == f"Cookie: {M}"
    assert masked("Set-Cookie: session=secret; Path=/") == f"Set-Cookie: {M}"


def test_query_strings() -> None:
    assert masked("?token=secret&foo=bar") == f"?token={M}&foo=bar"
    assert masked("?api_key=secret&foo=bar") == f"?api_key={M}&foo=bar"
    assert (
        masked("/p?db_password=secret&service_token=secret&page=2#frag")
        == f"/p?db_password={M}&service_token={M}&page=2#frag"
    )


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("mysql://u:p@h/db", f"mysql://u:{M}@h/db"),
        ("postgresql://u:p@h/db", f"postgresql://u:{M}@h/db"),
        ("redis://u:p@h", f"redis://u:{M}@h"),
        ("redis://:secret@host:6379/0", f"redis://:{M}@host:6379/0"),
        ("https://u:p@example.org", f"https://u:{M}@example.org"),
        ("MySQL://u:p@h", f"MySQL://u:{M}@h"),
        ("postgresql://user:p%40ss%3Aword@host/db", f"postgresql://user:{M}@host/db"),
        ("mysql://u:pa%2Fss@h/db", f"mysql://u:{M}@h/db"),
        (
            "postgresql://user:secret@[::1]:5432/db",
            f"postgresql://user:{M}@[::1]:5432/db",
        ),
        ("mysql://u:secret@h:3306/db?ssl=1", f"mysql://u:{M}@h:3306/db?ssl=1"),
        ("mysql://u:p@ss@h/db", f"mysql://u:{M}@h/db"),
        (
            "connection failed for mysql://user:secret@db.local/app",
            f"connection failed for mysql://user:{M}@db.local/app",
        ),
        (
            "could not connect to postgresql://roger:secret@10.0.0.2/db",
            f"could not connect to postgresql://roger:{M}@10.0.0.2/db",
        ),
        (
            "a mysql://u:secret@h/x, redis://v:secret@h2/ (https://w:secret@h3)",
            f"a mysql://u:{M}@h/x, redis://v:{M}@h2/ (https://w:{M}@h3)",
        ),
        ('{"url": "mysql://u:secret@h/db"}', f'{{"url": "mysql://u:{M}@h/db"}}'),
    ],
)
def test_url_credentials(text: str, expected: str) -> None:
    assert masked(text) == expected


def test_url_is_syntactic_without_decoding_or_repair() -> None:
    # « / » termine l'autorité : hors contrat, documenté.
    assert masked("mysql://u:pa/ss@h/db") == "mysql://u:pa/ss@h/db"


def test_several_families_on_one_line() -> None:
    line = (
        "DATABASE_PASSWORD=secret1 connection refused to mysql://roger:secret2@db/app "
        "API_TOKEN=secret3 Authorization: Bearer secret4"
    )
    result = masked(line)
    for secret in ("secret1", "secret2", "secret3", "secret4"):
        assert secret not in result
    assert result.startswith(f"DATABASE_PASSWORD={M} connection refused to mysql://")


def test_unicode_lines_and_controls_are_preserved() -> None:
    text = "café\r\nDB_PASSWORD=mötdepässe😀\rnext\nAPI_TOKEN=x\x00y\n\u2028fin"
    result = masked(text)
    # Politique de contrôles inchangée : NUL ne termine pas une valeur nue.
    assert result == f"café\r\nDB_PASSWORD={M}\rnext\nAPI_TOKEN={M}\n\u2028fin"
    assert result.count("\n") == text.count("\n")
    assert result.count("\r") == text.count("\r")


def test_growth_is_bounded_by_the_marker_per_replacement() -> None:
    text = "pwd=x " * 1000
    result = masked(text)
    assert result.count(M) == 1000
    assert len(result) - len(text) == 1000 * (len(M) - 1)


def test_deterministic_combinations() -> None:
    """Combinaisons déterministes : préfixes, séparateurs, clés, affectations,
    valeurs, ponctuation ; tout secret masqué, tout texte ordinaire intact."""
    prefixes = ["", "DB", "my.app", "X-Service", "foo"]
    separators = ["_", "-", "."]
    sensitive = [
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
        "access_token",
        "api_key",
        "apikey",
        "api-key",
        "secret_key",
        "private_key",
        "private.key",
    ]
    ordinary = ["policy", "count", "status", "path", "EXTRA", "izer", "ary"]
    assignments = ["=", ": ", " = ", '": "']
    values = ["S3cr3tValue", '"S3cr3tValue word"', "'S3cr3tValue word'", '"S3cr3tValue']
    around = [("", ""), (" ", " ok"), ("?", "&page=2"), ("(", ")"), ("[", "]")]
    checked = 0
    for prefix, sep, key, assign, value, (left, right), upper in itertools.product(
        prefixes, separators, sensitive, assignments, values, around, (False, True)
    ):
        if assign.endswith('"') and value.startswith('"'):
            continue  # « ""valeur » : JSON mal formé, hors des formes reconnues
        name = (prefix + sep if prefix else "") + key
        name = name.upper() if upper else name
        text = f"{left}{name}{assign}{value}{right}"
        assert "S3cr3tValue" not in masked(text), text
        checked += 1
    for prefix, sep, key, suffix, assign in itertools.product(
        prefixes, separators, sensitive, ordinary, assignments
    ):
        glue = sep if suffix not in {"izer", "ary"} else ""
        text = f"{prefix}{sep if prefix else ''}{key}{glue}{suffix}{assign}plain"
        assert masked(text) == text, text
        checked += 1
    assert checked > 10_000


def test_pure_str_function_without_side_effects() -> None:
    tree = ast.parse(Path(debug_redaction.__file__).read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert imports == {"re"}
    assert not any(isinstance(node, ast.ImportFrom) for node in ast.walk(tree))
    assert redact_debug_text("DB_PASSWORD=x") == redact_debug_text("DB_PASSWORD=x")


def _median(text: str) -> float:
    durations: list[float] = []
    for _ in range(3):
        started = time.perf_counter()
        redact_debug_text(text)
        durations.append(time.perf_counter() - started)
    return max(statistics.median(durations), 1e-4)


@pytest.mark.parametrize(
    "unit",
    [
        "lorem ipsum dolor ",
        "DB_PASSWORD=x API_TOKEN=y ",
        "mysql://u:p@h/db ",
        "A_",
        ":",
        "@",
        "a://",
        "x://u:" + "a:" * 64,
        "password" + " " * 64,
        "Proxy-Authorization",
        '"',
        # Indices présents : chaque passe est réellement tentée.
        "A_" * 64 + "TOKEN ",
        "key" + ":" * 64,
        "token" + "@" * 64 + "://",
        "Proxy-Authorization" * 32 + " x://",
        "abcdefghij" * 64 + "://",
    ],
)
def test_no_catastrophic_growth(unit: str) -> None:
    """Garde grossier : ×4 sur l'entrée ne doit pas coûter ×16 (les mesures fines
    figurent dans le rapport, pas dans un seuil absolu)."""
    small = (unit * (16 * 1024 // len(unit) + 1))[: 16 * 1024]
    large = (unit * (64 * 1024 // len(unit) + 1))[: 64 * 1024]
    assert _median(large) / _median(small) < 16


def test_public_model_search_and_links_never_expose_values(tmp_path: Path) -> None:
    root = project(tmp_path / "project")
    secrets = ["VerySecret123", "Secret2", "Secret3", "Secret4", "Secret5", "Secret6"]
    path = journal(
        root,
        encoded(
            id="evt DB_PASSWORD=VerySecret123",
            message="DB_PASSWORD=VerySecret123 connection refused",
            hint="see mysql://roger:Secret2@db.local/app",
            sql="SELECT 1 -- SERVICE_TOKEN=Secret3",
            route="/login?db_password=Secret4",
            request={
                "method": "GET",
                "path": "/x",
                "query": "OPENAI_API_KEY=Secret5&page=2",
                "post_keys": [],
                "headers": ["HTTP_AUTHORIZATION=Bearer Secret6"],
            },
        ),
    )
    source = path.read_bytes()
    result = read_debug_errors(root)
    (item,) = result.events
    public = repr(result) + str(debug_event_url(item))
    for secret in secrets:
        assert secret not in public
        view = filter_debug_events(result, DebugFilter(query=secret))
        assert view.events == ()
    assert item.message == f"DB_PASSWORD={M} connection refused"
    assert (
        item.request is not None and item.request.query == f"OPENAI_API_KEY={M}&page=2"
    )
    assert filter_debug_events(result, DebugFilter(query="connection")).events
    # Le journal source reste inchangé.
    assert path.read_bytes() == source


def _without_prefilter(value: str) -> str:
    """Les trois passes appliquées sans leurs indices préalables."""
    mask = debug_redaction._mask  # pyright: ignore[reportPrivateUsage]
    value = debug_redaction._HEADER.sub(mask, value)  # pyright: ignore[reportPrivateUsage]
    value = debug_redaction._ASSIGNMENT.sub(mask, value)  # pyright: ignore[reportPrivateUsage]
    return debug_redaction._URL_PASSWORD.sub(mask, value)  # pyright: ignore[reportPrivateUsage]


def test_prefilter_never_changes_the_result() -> None:
    keys = ["password", "passwd", "pwd", "secret", "token", "api_key", "apikey"]
    keys += ["secret.key", "private-key", "authorization", "cookie", "set-cookie"]
    # Homoglyphes que ``re`` en casse insensible Unicode rapprocherait de l'ASCII.
    variants = ["", "\u0130", "\u0131", "\u017f", "\u212a", "É"]
    texts = [
        f"{prefix}{key.replace(letter, odd) if odd else key.upper()}{assign}v{tail}"
        for key in keys
        for letter in "iskI"
        for odd in variants
        for prefix in ("", "DB_", "Proxy-", "é")
        for assign in ("=", ": ")
        for tail in ("", " mysql://u:p@h/db", "\nCookie: a=b")
    ]
    texts += ["lorem ipsum", "MySQL://u:p@h", "x://u:p@h Authorization: x"]
    for text in texts:
        assert redact_debug_text(text) == _without_prefilter(text), text


def test_keywords_are_ascii_case_insensitive() -> None:
    assert masked("PassWord=x") == f"PassWord={M}"
    # « ſ », « ı » ou le signe kelvin ne remplacent pas une lettre ASCII.
    for text in ("pa\u017f\u017fword=x", "\u0131token=x", "api_\u212aey=x"):
        assert masked(text) == text


@pytest.mark.parametrize("run", ["a", "Proxy-Authorization-", "a.b+c-"])
def test_no_quadratic_scheme_scan_on_a_single_long_run(run: str) -> None:
    """Un schéma d'URL ne démarre qu'en début de mot : une seule longue suite de
    caractères de schéma suivie de « :// » reste linéaire (×8 sur l'entrée)."""
    small = (run * (2048 // len(run) + 1))[:2048] + "://u:"
    large = (run * (16384 // len(run) + 1))[:16384] + "://u:"
    assert _median(large) / _median(small) < 32
