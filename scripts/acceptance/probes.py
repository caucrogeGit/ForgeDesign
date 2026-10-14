"""Sondes hors navigateur de FD-ACCEPTANCE-001 (bibliothèque standard seule).

  python probes.py snapshot <racine> <sortie.json>
  python probes.py diff <avant.json> <après.json> [chemin-relatif-attendu ...]
  python probes.py listen <pid>
  python probes.py hostguard <port>
  python probes.py tree <pid>
  python probes.py strays <dossier>
  python probes.py rss <pid>
  python probes.py perf <port> <projet> [répétitions]
  python probes.py runtime <port> <projet> [répétitions]
  python probes.py endurance <port> <pid> <projet>
  python probes.py wheel <roue.whl> <dépôt>

Chaque commande imprime une ligne JSON et sort en 1 si une attente échoue.
"""

import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
import zipfile
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode


def out(value: object, ok: bool = True) -> None:
    print(json.dumps(value, ensure_ascii=False))
    sys.exit(0 if ok else 1)


# ── Instantanés ──────────────────────────────────────────────────────────────


def snapshot(root: Path) -> dict[str, list[object]]:
    """Chemin relatif → [type, taille, mtime_ns, sha256] ; .venv exclu."""
    result: dict[str, list[object]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d != ".venv")
        base = Path(dirpath)
        for name in dirnames:
            result[str((base / name).relative_to(root))] = ["d", 0, 0, ""]
        for name in sorted(filenames):
            path = base / name
            stat = path.lstat()
            digest = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
            )
            result[str(path.relative_to(root))] = [
                "f",
                stat.st_size,
                stat.st_mtime_ns,
                digest,
            ]
    return result


def diff(
    before: dict[str, list[object]], after: dict[str, list[object]], allowed: set[str]
):
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(
        k
        for k in set(before) & set(after)
        if before[k][3] != after[k][3] or before[k][1] != after[k][1]
    )
    touched = sorted(
        k
        for k in set(before) & set(after)
        if before[k][2] != after[k][2] and k not in changed and before[k][0] == "f"
    )
    unexpected = [k for k in added + removed + changed if k not in allowed]
    suspicious = [
        k
        for k in added
        if ("__pycache__" in k or ".forge-design" in k) and k not in allowed
    ]
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "mtime_only": touched,
        "unexpected": unexpected,
        "suspicious": suspicious,
    }


# ── Processus et réseau ──────────────────────────────────────────────────────


def children(pid: int) -> list[int]:
    """Descendants de pid (par ppid), récursivement."""
    parents: dict[int, list[int]] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            fields = Path(f"/proc/{entry}/stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue
        parents.setdefault(int(fields[1]), []).append(int(entry))
    found, stack = [], [pid]
    while stack:
        for child in parents.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def cmdline(pid: int) -> str:
    try:
        return (
            Path(f"/proc/{pid}/cmdline")
            .read_bytes()
            .replace(b"\0", b" ")
            .decode()[:200]
        )
    except OSError:
        return ""


def listening(pids: set[int]) -> list[str]:
    text = subprocess.run(["ss", "-ltnpH"], capture_output=True, text=True).stdout
    found = []
    for line in text.splitlines():
        if any(f"pid={pid}," in line for pid in pids):
            found.append(line.split()[3])
    return found


def ancestors() -> set[int]:
    """La sonde et ses ancêtres (orchestrateur, shell) : jamais des restes."""
    found, pid = set(), os.getpid()
    while pid > 1:
        found.add(pid)
        try:
            pid = int(
                Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1]
            )
        except OSError:
            break
    return found


def strays(folder: Path) -> list[str]:
    """Processus dont le dossier courant ou la ligne de commande vise <dossier>."""
    found = []
    target = str(folder.resolve())
    mine = ancestors()
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) in mine:
            continue
        try:
            cwd = os.readlink(f"/proc/{entry}/cwd")
        except OSError:
            cwd = ""
        line = cmdline(int(entry))
        if cwd.startswith(target) or (target in line and "probes.py" not in line):
            found.append(f"{entry} {line}")
    return found


def rss(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


# ── HTTP ─────────────────────────────────────────────────────────────────────


def request(
    port: int,
    method: str,
    path: str,
    body: str = "",
    headers: dict[str, str] | None = None,
    timeout: float = 60,
) -> tuple[int, str]:
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        base = {"Host": f"127.0.0.1:{port}"}
        if method == "POST":
            base |= {
                "Origin": f"http://127.0.0.1:{port}",
                "Sec-Fetch-Site": "same-origin",
                "Content-Type": "application/x-www-form-urlencoded",
            }
        connection.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
        for key, value in (base | (headers or {})).items():
            if value is not None:
                connection.putheader(key, value)
        data = body.encode()
        connection.putheader("Content-Length", str(len(data)))
        connection.endheaders(data)
        response = connection.getresponse()
        return response.status, response.read().decode("utf-8", "replace")
    finally:
        connection.close()


def open_project(port: int, project: Path) -> int:
    return request(port, "POST", "/inspector", urlencode({"path": str(project)}))[0]


def hostguard(port: int) -> dict[str, object]:
    checks = {
        "host_valid": request(port, "GET", "/")[0],
        "host_localhost": request(
            port, "GET", "/", headers={"Host": f"localhost:{port}"}
        )[0],
        "host_foreign": request(port, "GET", "/", headers={"Host": "evil.example"})[0],
        "host_rebinding": request(
            port, "GET", "/", headers={"Host": f"evil.example:{port}"}
        )[0],
        "post_foreign_origin": request(
            port, "POST", "/project/close", headers={"Origin": "http://evil.example"}
        )[0],
        "post_no_origin": request(
            port, "POST", "/project/close", headers={"Origin": None}
        )[0],
        "post_cross_site": request(
            port, "POST", "/project/close", headers={"Sec-Fetch-Site": "cross-site"}
        )[0],
    }
    return checks


# ── Mesures ─────────────────────────────────────────────────────────────────

PAGES = ("/inspector", "/routes", "/entities", "/templates", "/debug")


def perf(port: int, project: Path, runs: int) -> dict[str, object]:
    started = time.perf_counter()
    status = open_project(port, project)
    opened = time.perf_counter() - started
    result: dict[str, object] = {"open_status": status, "open_ms": round(opened * 1000)}
    for page in PAGES:
        durations, codes = [], set()
        for _ in range(runs):
            t = time.perf_counter()
            code, _ = request(port, "GET", page)
            durations.append(time.perf_counter() - t)
            codes.add(code)
        result[page] = {
            "codes": sorted(codes),
            "median_ms": round(statistics.median(durations) * 1000, 1),
            "max_ms": round(max(durations) * 1000, 1),
        }
    return result


COMMANDS = {
    "doctor": "/debug/forge-diagnostic",
    "audit": "/debug/forge-audit",
    "check": "/debug/forge-project-check",
}


def runtime(port: int, project: Path, runs: int) -> dict[str, object]:
    open_project(port, project)
    result: dict[str, object] = {}
    for name, path in COMMANDS.items():
        durations, codes = [], set()
        for _ in range(runs):
            t = time.perf_counter()
            code, _ = request(port, "POST", path)
            durations.append(time.perf_counter() - t)
            codes.add(code)
        result[name] = {
            "codes": sorted(codes),
            "median_ms": round(statistics.median(durations) * 1000, 1),
            "max_ms": round(max(durations) * 1000, 1),
        }
    return result


MODULE_PAGES = (
    "/modules/flowchart/resource?type=flowchart&path=mvc%2Fflowchart%2Fsimple.flow.json",
    "/modules/circuit/resource?type=schematic&path=mvc%2Fcircuit%2Fdemo.circuit.json",
    "/modules/circuit/",
    "/modules/flowchart/",
)


def endurance(port: int, pid: int, project: Path) -> dict[str, object]:
    open_project(port, project)
    pages = PAGES + (MODULE_PAGES if (project / "mvc/flowchart").exists() else ())
    for page in pages:  # préchauffage
        request(port, "GET", page)
    before = rss(pid)
    for _ in range(20):
        for page in pages:
            request(port, "GET", page)
    after_pages = rss(pid)
    for _ in range(10):
        for path in COMMANDS.values():
            request(port, "POST", path)
    after_runtime = rss(pid)
    return {
        "rss_kib_before": before,
        "pages_per_round": len(pages),
        "rss_kib_after_20_rounds": after_pages,
        "rss_kib_after_30_commands": after_runtime,
        "growth_kib": after_runtime - before,
        "children_after": [cmdline(p) for p in children(pid)],
    }


# ── Roue ─────────────────────────────────────────────────────────────────────

REQUIRED = (
    "forge_design/py.typed",
    "forge_design/real_preview/child_bootstrap.py",
)


def expected_resources(repo: Path) -> list[str]:
    """Chaque gabarit, fichier statique et schéma du dépôt doit être dans la roue."""
    package = repo / "forge_design"
    found = [*package.glob("web/templates/*.html"), *package.glob("**/*.schema.json")]
    found += [p for p in (package / "web/static").rglob("*") if p.is_file()]
    return sorted(
        str(p.relative_to(repo)) for p in found if "__pycache__" not in p.parts
    )


FORBIDDEN = (
    "tests/",
    "docs/",
    "scripts/",
    "rapports",
    "fixtures",
    "__pycache__",
    ".pyc",
    "forge_design_circuit",
    "forge_design_flowchart",
    "env/dev",
    ".venv",
)


def wheel(path: Path, repo: Path) -> dict[str, object]:
    names = zipfile.ZipFile(path).namelist()
    required = [*REQUIRED, *expected_resources(repo)]
    missing = [r for r in required if r not in names]
    forbidden = sorted({f for f in FORBIDDEN for n in names if f in n})
    kinds: dict[str, int] = {}
    for name in names:
        kinds[Path(name).suffix or "(aucune)"] = (
            kinds.get(Path(name).suffix or "(aucune)", 0) + 1
        )
    return {
        "files": len(names),
        "resources_checked": len(required),
        "kinds": kinds,
        "missing": missing,
        "forbidden": forbidden,
    }


def main() -> None:
    command, *args = sys.argv[1:]
    if command == "snapshot":
        Path(args[1]).write_text(json.dumps(snapshot(Path(args[0]))))
        out({"snapshot": args[1]})
    elif command == "diff":
        before = json.loads(Path(args[0]).read_text())
        after = json.loads(Path(args[1]).read_text())
        value = diff(before, after, set(args[2:]))
        out(value, not value["unexpected"] and not value["suspicious"])
    elif command == "listen":
        pid = int(args[0])
        addresses = listening({pid, *children(pid)})
        bad = [a for a in addresses if not a.startswith("127.0.0.1:")]
        out({"listening": addresses, "not_loopback": bad}, bool(addresses) and not bad)
    elif command == "hostguard":
        value = hostguard(int(args[0]))
        ok = (
            value["host_valid"] == 200
            and value["host_foreign"] >= 400
            and value["host_rebinding"] >= 400
            and value["post_foreign_origin"] == 403
            and value["post_no_origin"] == 403
            and value["post_cross_site"] == 403
        )
        out(value, ok)
    elif command == "tree":
        pid = int(args[0])
        out({"children": [f"{p} {cmdline(p)}" for p in children(pid)]})
    elif command == "strays":
        found = strays(Path(args[0]))
        out({"strays": found}, not found)
    elif command == "rss":
        out({"rss_kib": rss(int(args[0]))})
    elif command == "perf":
        out(perf(int(args[0]), Path(args[1]), int(args[2]) if len(args) > 2 else 7))
    elif command == "runtime":
        out(runtime(int(args[0]), Path(args[1]), int(args[2]) if len(args) > 2 else 5))
    elif command == "endurance":
        value = endurance(int(args[0]), int(args[1]), Path(args[2]))
        out(value, not value["children_after"])
    elif command == "wheel":
        value = wheel(Path(args[0]), Path(args[1]))
        out(value, not value["missing"] and not value["forbidden"])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
