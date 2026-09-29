"""Ouverture ancrée de dossiers sans suivre les liens."""

import os
from collections.abc import Generator
from contextlib import ExitStack, contextmanager
from pathlib import Path


@contextmanager
def open_directory(name: str, parent: int | None = None) -> Generator[int, None, None]:
    if parent is None:
        with ExitStack() as stack:
            parts = Path(name).absolute().parts
            descriptor = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, descriptor)
            for part in parts[1:]:
                if part == "..":
                    raise OSError("Racine non canonique.")
                descriptor = stack.enter_context(open_directory(part, descriptor))
            yield descriptor
        return
    descriptor = os.open(
        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
    )
    try:
        yield descriptor
    finally:
        os.close(descriptor)
