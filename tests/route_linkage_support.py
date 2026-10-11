"""Projet Forge synthétique couvrant les chaînes de routes (FD-ROUTES-021)."""

import json
from pathlib import Path

HOSTILE = "<script>alert(\"x\")</script> & 'é'"

ROUTES = f"""from mvc.controllers.users import Users
from mvc.controllers.absent import Absent
router = Router()
router.add("GET", "/users/{{id}}", Users.show, name={json.dumps(HOSTILE)}, public=True)
router.add("GET", "/users/{{id}}/edit", Users.edit)
router.add("GET", "/dyn", Users.dyn)
router.add("GET", "/mixed", Users.mixed)
router.add("GET", "/json", Users.json)
router.add("GET", "/gone", Users.gone)
router.add("GET", "/nomethod", Users.nope)
router.add("GET", "/absent", Absent.index)
router.add("GET", "/fn", home)
router.add("GET", "/unresolved", Other.index)
router.add("GET", "/dynamic", handlers["x"])
router.add("POST", "/orphan", Users.orphan)
"""

CONTROLLER = """class Users:
    def show(self):
        return BaseController.render("users/show.html")

    def edit(self, ok):
        if ok:
            return BaseController.render("users/edit.html")
        return BaseController.render("users/error.html")

    def dyn(self):
        return BaseController.render(template_name)

    def mixed(self, ok, other):
        if ok:
            return BaseController.render("users/show.html")
        if other:
            return BaseController.render("users/ghost.html")
        return BaseController.render(name)

    def json(self):
        return {"a": 1}

    def gone(self):
        return BaseController.render("users/missing.html")

    def orphan(self):
        return BaseController.render("users/orphan.html")
"""

# Ordre des routes de ROUTES (indices de RoutesResult.routes).
(
    SHOW,
    EDIT,
    DYN,
    MIXED,
    JSON,
    GONE,
    NOMETHOD,
    ABSENT,
    FN,
    UNRESOLVED,
    DYNAMIC,
    ORPHAN,
) = range(12)


def contract(views: Path, path: str, template: str, name: str) -> None:
    target = views / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"name": name, "template": "mvc/views/" + template, "context": {}})
    )


def chain_project(root: Path) -> Path:
    root.mkdir(parents=True)
    for name in ("app.py", "bootstrap.py", "config.py"):
        (root / name).write_text("raise AssertionError('never execute')")
    (root / "requirements.txt").write_text("forge-mvc==1.0.0rc9")
    (root / "mvc/routes").mkdir(parents=True)
    (root / "mvc/controllers").mkdir()
    (root / "mvc/routes/__init__.py").write_text(ROUTES)
    (root / "mvc/controllers/users.py").write_text(CONTROLLER)
    views = root / "mvc/views/users"
    views.mkdir(parents=True)
    for name in ("show", "edit", "error", "orphan"):
        (views / f"{name}.html").write_text(f"<p>{name}</p>")
    base = root / "mvc/views"
    contract(base, "users/show.view.json", "users/show.html", "users.show")
    contract(base, "users/edit.view.json", "users/edit.html", "users.edit")
    contract(base, "users/edit-bis.view.json", "users/edit.html", "users.edit.bis")
    (base / "users/broken.view.json").write_text("{")
    return root.resolve()
