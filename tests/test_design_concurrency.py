"""FD-EDITOR-008 : concurrence réelle, protocoles Web/API et stockage cible."""

import json
import multiprocessing
import os
import tempfile
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from test_web_editor import (
    DESIGN,
    design_file,
    displayed_revision,
    make_root,
    request,
    serving,
)

from forge_design.design.io import DesignWriteConflictError, read_design, write_design
from forge_design.design.locking import filesystem_type
from forge_design.design.models import DesignFile


@pytest.fixture(params=["tmpfs", "ext4"])
def local_project(request: pytest.FixtureRequest, tmp_path: Path) -> Iterator[Path]:
    fs = str(request.param)
    base = (
        Path("/tmp")
        if fs == "tmpfs"
        else Path(
            os.environ.get(
                "FD_EDITOR_008_EXT4_ROOT",
                str(Path(__file__).parents[1] / "tmp/fd-editor-008-tests"),
            )
        )
    )
    base.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="race-", dir=base) as folder:
        root = make_root(Path(folder))
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            assert filesystem_type(fd) == fs, "Le test doit réellement qualifier ce FS"
        finally:
            os.close(fd)
        yield root


def competitor(
    root_text: str, mode: str, marker: str, barrier: Any, results: Any
) -> None:
    root = Path(root_text)
    try:
        if mode == "web":
            # Chaque exécutant possède son application et son vrai serveur HTTP.
            with serving(root, root.parent / marker) as app:
                revision = displayed_revision(app)
                barrier.wait(15)
                status, html, headers = request(
                    app,
                    "/editor/action",
                    {
                        "design": DESIGN,
                        "revision": revision,
                        "action": "props",
                        "path": "0",
                        "props": json.dumps({"class": marker}),
                    },
                )
                if status == 409:
                    assert headers["Cache-Control"] == "no-store"
                    assert 'name="path" value=""' in html
                    assert "Recharger l’éditeur" in html
                    assert "depuis l’affichage" in html
                results.put((os.getpid(), status, marker))
        else:
            read = read_design(root, DESIGN)
            assert read.design is not None
            data = read.design.model_dump(exclude_unset=True)
            data["root"]["children"][0]["props"] = {"class": marker}
            changed = DesignFile.model_validate(data)
            barrier.wait(15)
            try:
                write_design(root, DESIGN, changed, expected_revision=read.revision)
                status = 303
            except DesignWriteConflictError:
                status = 409
            results.put((os.getpid(), status, marker))
    except BaseException as error:
        results.put((os.getpid(), repr(error), marker))


@pytest.mark.parametrize(
    "trial", range(int(os.environ.get("FD_EDITOR_008_TRIALS", "1")))
)
@pytest.mark.parametrize("pair", [("web", "web"), ("api", "api"), ("web", "api")])
@pytest.mark.parametrize("execution", ["threads", "processes"])
def test_shared_revision_one_publication(
    local_project: Path, pair: tuple[str, str], execution: str, trial: int
) -> None:
    import queue

    barrier: Any
    results: Any
    factory: Any
    if execution == "processes":
        ctx = multiprocessing.get_context("spawn")
        barrier, results = ctx.Barrier(2), ctx.Queue()
        factory = ctx.Process
    else:
        barrier, results = threading.Barrier(2), queue.Queue[Any]()
        factory = threading.Thread
    jobs = [
        factory(
            target=competitor, args=(str(local_project), mode, marker, barrier, results)
        )
        for mode, marker in zip(pair, ("race-a", "race-b"), strict=True)
    ]
    for job in jobs:
        job.start()
    for job in jobs:
        job.join(30)
    assert not any(job.is_alive() for job in jobs)
    observed = [results.get(timeout=3) for _ in jobs]
    if execution == "processes":
        assert len({row[0] for row in observed}) == 2
        results.close()
        results.join_thread()
    assert sorted(row[1] for row in observed if isinstance(row[1], int)) == [
        303,
        409,
    ], observed
    winner = next(row[2] for row in observed if row[1] == 303)
    data = json.loads(design_file(local_project).read_text())
    assert data["root"]["children"][0]["props"] == {"class": winner}
    assert len(list((local_project / ".forge-design/locks").iterdir())) == 1
