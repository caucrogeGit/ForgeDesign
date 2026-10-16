"""Projets de qualification FD-ACCEPTANCE-001, tous jetables.

Usage : python build_projects.py <dossier-de-travail> <venv-forge>

<venv-forge> est un venv contenant forge-mvc, forge-mvc-sqlite et
forge-mvc-entities 1.0.0rc9 : son squelette sert de base, et il est copié dans
chaque projet exécutable (.venv réel). Aucun projet utilisateur n'est lu ni
écrit ; tout est créé sous <dossier-de-travail>/projects.

Projets :
  A          squelette Forge nominal (entité, route, contrôleur, template,
             contrat, design, migration, journal vide) : parcours lecture seule
  A-preview  copie de A réservée à la preview réelle (exécute le projet)
  A-bare     squelette nu : ni entité ni journal (états optionnels)
  A-no-bootstrap  copie statique de A sans bootstrap.py ni .venv : projet Forge
             valide pour forge-mvc 1.0.0rc9 (FD-FORGE-004), jamais exécuté
  B          gx8 enrichi : projet réaliste et volontairement problématique
             (routes et application lèvent si exécutées, noms hostiles)
  B-write    copie de B, seule cible des écritures (éditeur, modules)
  C          squelette importable avec défauts connus (§15)
  C-check    copie de C dont le contrôleur écrit une sentinelle (project:check)
  C-timeout  copie de C dont les routes impriment puis bloquent (délai, -u)
  D          projet volumineux (200 routes, 250 templates, 250 contrats,
             250 entités, 500 migrations, 2 000 événements)
  invalid/   dossier non Forge, fichier à la place d'un dossier
"""

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SKELETON_ITEMS = (
    "app.py",
    "bootstrap.py",
    "config.py",
    "env",
    "mvc",
    "optins",
    "static",
    "storage",
)
IGNORE = shutil.ignore_patterns("__pycache__")

# Valeurs synthétiques de test, jamais réelles : le masquage doit les cacher.
SECRET_EVENTS = [
    {
        "id": "evt-db SERVICE_TOKEN=TokAcc777",
        "level": "ERROR",
        "category": "database",
        "exception_type": "OperationalError",
        "message": "DB_PASSWORD=AccSecret123 connection refused",
        "hint": "could not connect to postgresql://roger:PgAcc456@10.0.0.2/db",
        "sql": "SELECT 1 -- OPENAI_API_KEY=KeyAcc888",
        "request": {
            "method": "GET",
            "path": "/login",
            "query": "db_password=QryAcc111&page=2",
            "post_keys": [],
            "headers": ["HTTP_AUTHORIZATION=Bearer AuthAcc999"],
        },
    },
    {
        "id": "dup",
        "level": "WARNING",
        "category": "runtime",
        "message": "premier doublon",
    },
    {"id": "dup", "level": "INFO", "category": "http", "message": "second doublon"},
    {
        "id": "ordinaire",
        "level": "CRITICAL",
        "category": "template",
        "message": "token_count=3 password_policy=strict tokenizer ready",
    },
]
SECRETS = (
    "AccSecret123",
    "TokAcc777",
    "PgAcc456",
    "KeyAcc888",
    "QryAcc111",
    "AuthAcc999",
)


def event(**values: object) -> dict[str, object]:
    base = {
        "schema_version": "1.0",
        "timestamp": "2026-10-14T10:00:00+00:00",
        "environment": "dev",
        "exception_type": "RuntimeError",
        "safe_for_display": False,
    }
    return base | values


def skeleton(venv: Path) -> Path:
    return next(venv.glob("lib/python*/site-packages/skeleton/data"))


def copy_venv(venv: Path, root: Path) -> None:
    shutil.copytree(venv, root / ".venv", symlinks=True)


def from_skeleton(root: Path, venv: Path) -> Path:
    source = skeleton(venv)
    root.mkdir(parents=True)
    for name in SKELETON_ITEMS:
        item = source / name
        if item.is_dir():
            shutil.copytree(item, root / name, ignore=IGNORE)
        else:
            shutil.copy2(item, root / name)
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9\n")
    shutil.copy2(root / "env/example", root / "env/dev")
    return root


def add_contacts(root: Path) -> None:
    """Route publique statique → contrôleur → template, contrat, design, entité."""
    routes = root / "mvc/routes/__init__.py"
    routes.write_text(
        routes.read_text(encoding="utf-8")
        + "\nfrom mvc.controllers.contacts_controller import ContactsController\n"
        + 'router.add("GET", "/contacts", ContactsController.index, public=True)\n'
    )
    (root / "mvc/controllers/contacts_controller.py").write_text(
        "from core.http.request import Request\n"
        "from core.http.response import Response\n"
        "from core.mvc.controller.base_controller import BaseController\n\n\n"
        "class ContactsController(BaseController):\n"
        "    @staticmethod\n"
        "    def index(request: Request) -> Response:\n"
        '        return BaseController.render("contacts/list.html", request=request)\n'
    )
    views = root / "mvc/views/contacts"
    views.mkdir(parents=True)
    (views / "list.html").write_text(
        '{% extends "layouts/base.html" %}\n{% block content %}\n'
        "<h1>Contacts</h1>\n<p>Liste des contacts.</p>\n{% endblock %}\n"
    )
    (views / "list.view.json").write_text(
        json.dumps(
            {
                "name": "contacts/list",
                "template": "mvc/views/contacts/list.html",
                "context": {
                    "page_title": {"type": "string"},
                    "contacts": {
                        "type": "list",
                        "entity": "Contact",
                        "fields": {"nom": "string", "email": "string"},
                    },
                },
            },
            indent=2,
        )
    )
    (views / "list.design.json").write_text(
        json.dumps(
            {
                "version": "0.1",
                "view": "contacts/list",
                "source_contract": "contacts/list.view.json",
                "root": {
                    "type": "page",
                    "children": [
                        {
                            "type": "section",
                            "props": {"class": "p-4"},
                            "children": [
                                {
                                    "type": "card",
                                    "children": [
                                        {"type": "title", "binding": "page_title"},
                                        {"type": "text"},
                                    ],
                                }
                            ],
                        },
                        {"type": "table", "binding": "contacts"},
                    ],
                },
            },
            indent=2,
        )
        + "\n"
    )
    entity = root / "mvc/entities/contact"
    entity.mkdir(parents=True)
    (entity / "contact.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "name": "Contact",
                "table": "contact",
                "fields": [
                    {
                        "name": "nom",
                        "type": "string",
                        "max_length": 120,
                        "required": True,
                    },
                    {
                        "name": "email",
                        "type": "string",
                        "max_length": 255,
                        "required": False,
                    },
                ],
                "options": {"timestamps": False, "soft_delete": False},
            }
        )
    )
    (root / "mvc/entities/relations.json").write_text(
        json.dumps({"schema_version": "1.0", "relations": []})
    )
    migrations = root / "mvc/migrations"
    migrations.mkdir()
    (migrations / "20260101120000_create_contact.sql").write_text(
        "CREATE TABLE contact (id INTEGER PRIMARY KEY, nom TEXT NOT NULL,"
        " email TEXT);\n"
    )


def project_a(root: Path, venv: Path) -> Path:
    from_skeleton(root, venv)
    add_contacts(root)
    (root / "storage/logs/errors.dev.jsonl").write_text("")
    copy_venv(venv, root)
    return root


def project_a_no_bootstrap(root: Path, venv: Path) -> Path:
    """A sans bootstrap.py (optionnel pour forge-mvc 1.0.0rc9, ADR-093) ni .venv."""
    from_skeleton(root, venv)
    add_contacts(root)
    (root / "storage/logs/errors.dev.jsonl").write_text("")
    (root / "bootstrap.py").unlink()
    return root


def project_b(root: Path, venv: Path) -> Path:
    shutil.copytree(FIXTURES / "gx8", root, symlinks=True)
    views = root / "mvc/views"
    (views / "base.view.json").write_text(
        json.dumps({"name": "base", "template": "mvc/views/base.html", "context": {}})
    )
    (views / "broken.view.json").write_text("{")
    (views / "contacts/list.view.json").write_text(
        json.dumps(
            {
                "name": "contacts/list",
                "template": "mvc/views/contacts/list.html",
                "context": {"contacts": {"type": "list", "fields": {"nom": "string"}}},
            }
        )
    )
    (views / "contacts/list.design.json").write_text(
        json.dumps(
            {
                "version": "0.1",
                "view": "contacts/list",
                "source_contract": "contacts/list.view.json",
                "root": {
                    "type": "page",
                    "children": [
                        {"type": "section", "children": [{"type": "text"}]},
                        {"type": "table", "binding": "contacts"},
                    ],
                },
            },
            indent=2,
        )
        + "\n"
    )
    migrations = root / "mvc/migrations"
    migrations.mkdir()
    (migrations / "20260101120000_init.sql").write_text("CREATE TABLE a (id INT);")
    (migrations / "20260102120000_contacts.sql").write_text("CREATE TABLE b (id INT);")
    (migrations / "v2_users.sql").write_text("CREATE TABLE c (id INT);")
    journal = root / "storage/logs/errors.dev.jsonl"
    journal.write_text(
        journal.read_text(encoding="utf-8")
        + "".join(json.dumps(event(**values)) + "\n" for values in SECRET_EVENTS)
        + "ligne JSON invalide\n"
    )
    (root / "env").mkdir()
    (root / "env/example").write_text("APP_NAME=gx8\nAPP_ROUTES_MODULE=mvc.routes\n")
    (root / "env/dev").write_text("DB_PASSWORD=AccSecret123\nAPI_TOKEN=TokAcc777\n")
    copy_venv(venv, root)
    return root


def project_b_write(root: Path, b: Path) -> Path:
    shutil.copytree(b, root, symlinks=True)
    (root / "mvc/circuit").mkdir()
    shutil.copy2(
        FIXTURES / "modules/demo.circuit.json", root / "mvc/circuit/demo.circuit.json"
    )
    (root / "mvc/flowchart").mkdir()
    shutil.copy2(
        FIXTURES / "modules/simple.flow.json", root / "mvc/flowchart/simple.flow.json"
    )
    return root


def project_c(root: Path, venv: Path) -> Path:
    from_skeleton(root, venv)
    add_contacts(root)
    views = root / "mvc/views"
    routes = root / "mvc/routes/__init__.py"
    routes.write_text(
        routes.read_text(encoding="utf-8")
        + "from mvc.controllers.defects_controller import DefectsController\n"
        + 'router.add("GET", "/absent", DefectsController.absent, public=True)\n'
        + 'router.add("GET", "/items/<int:item_id>", DefectsController.item,'
        + " public=True)\n"
        + 'router.add("GET", "/dynamic", DefectsController.dynamic, public=True)\n'
        + 'router.add("GET", "/broken", DefectsController.broken, public=True)\n'
    )
    (root / "mvc/controllers/defects_controller.py").write_text(
        "from core.mvc.controller.base_controller import BaseController\n\n\n"
        "def chosen() -> str:\n    return 'items/show.html'\n\n\n"
        "class DefectsController(BaseController):\n"
        "    @staticmethod\n"
        "    def absent(request):\n"
        '        return BaseController.render("missing/page.html", request=request)\n'
        "    @staticmethod\n"
        "    def item(request):\n"
        '        return BaseController.render("items/show.html", request=request)\n'
        "    @staticmethod\n"
        "    def dynamic(request):\n"
        "        return BaseController.render(chosen(), request=request)\n"
        "    @staticmethod\n"
        "    def broken(request):\n"
        '        return BaseController.render("broken/jinja.html", request=request)\n'
    )
    (views / "items").mkdir()
    (views / "items/show.html").write_text(
        '{% extends "layouts/base.html" %}{% block content %}'
        "<p>{{ item_id }}</p><p>&lt;script&gt; brut : <script>alert(1)</script></p>"
        "{% endblock %}\n"
    )
    (views / "broken").mkdir()
    (views / "broken/jinja.html").write_text("{% if user %}\n<p>{{ user.name }</p>\n")
    (views / "broken/jinja.view.json").write_text("{ invalide")
    (views / "items/show.view.json").write_text(
        json.dumps({"name": "items/show", "template": "mvc/views/items/show.html"})
    )
    (views / "items/second.view.json").write_text(
        json.dumps(
            {
                "name": "items/second",
                "template": "mvc/views/items/show.html",
                "context": {},
            }
        )
    )
    (views / "orphan.view.json").write_text(
        json.dumps(
            {"name": "orphan", "template": "mvc/views/absent.html", "context": {}}
        )
    )
    (root / "mvc/entities/relations.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "relations": [
                    {
                        "type": "many_to_one",
                        "from": "Contact",
                        "to": "Inexistante",
                        "name": "fantome",
                        "foreign_key": "fantome_id",
                        "on_delete": "restrict",
                    }
                ],
            }
        )
    )
    (root / "mvc/migrations/v2_mal_nommee.sql").write_text("SELECT 1;\n")
    (root / "storage/logs/errors.dev.jsonl").write_text(
        json.dumps(
            event(id="c-1", level="ERROR", category="routing", message="route absente")
        )
        + "\n{pas du json\n"
        + json.dumps(
            event(id="c-2", level="WARNING", category="template", message="Jinja")
        )
        + "\n"
    )
    copy_venv(venv, root)
    return root


def project_c_check(root: Path, c: Path) -> Path:
    shutil.copytree(c, root, symlinks=True)
    controller = root / "mvc/controllers/contacts_controller.py"
    controller.write_text(
        controller.read_text(encoding="utf-8")
        + "\n# Effet de bord contrôlé : écrit par le code applicatif importé.\n"
        + "import pathlib as _pathlib\n"
        + "_pathlib.Path(__file__).resolve().parents[2].joinpath('CONTROLLER_IMPORTED')"
        + ".write_text('écrit par le code applicatif\\n')\n"
        + "print('DB_PASSWORD=AccSecret123 depuis le contrôleur')\n"
    )
    return root


def project_c_timeout(root: Path, c: Path) -> Path:
    shutil.copytree(c, root, symlinks=True)
    routes = root / "mvc/routes/__init__.py"
    routes.write_text(
        routes.read_text(encoding="utf-8")
        + "\nimport sys as _sys, threading as _threading, time as _time\n"
        + "print('AVANT TIMEOUT')\nprint('SERVICE_TOKEN=TokAcc777 avant blocage')\n"
        + "print('SANS-LF', end='')\n"
        + "_threading.Thread(target=_time.sleep, args=(60,)).start()\n"
    )
    return root


ENTITY = {
    "schema_version": "1.0",
    "name": "E",
    "table": "e",
    "fields": [
        {"name": "title", "type": "string", "max_length": 255, "required": True}
    ],
    "options": {"timestamps": False, "soft_delete": False},
}


def project_d(root: Path) -> Path:
    root.mkdir(parents=True)
    for name in ("app.py", "bootstrap.py", "config.py"):
        (root / name).write_text("raise AssertionError('jamais exécuté')\n")
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9\n")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "mvc/controllers").mkdir()
    views = root / "mvc/views"
    views.mkdir()
    lines = ["from mvc.controllers.pages import Pages", "router = Router()"]
    methods = []
    for index in range(200):
        methods.append(
            f'    def p{index}(self): return BaseController.render("t{index}.html")'
        )
        lines.append(f'router.add("GET", "/p{index}", Pages.p{index}, public=True)')
    (root / "mvc/controllers/pages.py").write_text(
        "class Pages:\n" + "\n".join(methods) + "\n"
    )
    (root / "mvc/routes/__init__.py").write_text("\n".join(lines) + "\n")
    for index in range(250):
        (views / f"t{index}.html").write_text(f"<p>{index}</p>")
        (views / f"t{index}.view.json").write_text(
            json.dumps(
                {
                    "name": f"t{index}",
                    "template": f"mvc/views/t{index}.html",
                    "context": {},
                }
            )
        )
        directory = root / f"mvc/entities/e{index}"
        directory.mkdir(parents=True)
        (directory / f"e{index}.json").write_text(
            json.dumps(ENTITY | {"name": f"E{index}", "table": f"e{index}"})
        )
    logs = root / "storage/logs"
    logs.mkdir(parents=True)
    (logs / "errors.dev.jsonl").write_text(
        "".join(
            json.dumps(
                event(id=f"e{i}", level="ERROR", category="runtime", message="boom")
            )
            + "\n"
            for i in range(2000)
        )
    )
    (root / "mvc/migrations").mkdir()
    for index in range(500):
        name = f"2026010{index // 100}12{index % 100:04d}_m{index}.sql"
        (root / "mvc/migrations" / name).write_text("SELECT 1;")
    return root


def invalid(root: Path) -> None:
    (root / "not-forge").mkdir(parents=True)
    (root / "not-forge/README.md").write_text("Pas un projet Forge.\n")
    (root / "a-file").write_text("fichier à la place d'un dossier\n")


def main() -> None:
    work, venv = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    projects = work / "projects"
    if projects.exists():
        shutil.rmtree(projects)
    projects.mkdir(parents=True)
    a = project_a(projects / "A", venv)
    shutil.copytree(a, projects / "A-preview", symlinks=True)
    from_skeleton(projects / "A-bare", venv)
    project_a_no_bootstrap(projects / "A-no-bootstrap", venv)
    b = project_b(projects / "B", venv)
    project_b_write(projects / "B-write", b)
    c = project_c(projects / "C", venv)
    project_c_check(projects / "C-check", c)
    project_c_timeout(projects / "C-timeout", c)
    project_d(projects / "D")
    invalid(projects / "invalid")
    (work / "secrets.json").write_text(json.dumps(list(SECRETS)))
    print(projects)


if __name__ == "__main__":
    main()
