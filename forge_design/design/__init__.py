"""Format design, validation et I/O explicites, sans génération de template."""

from forge_design.design.io import (
    DesignIssue,
    DesignReadResult,
    DesignRevision,
    DesignWriteConflictError,
    DesignWriteError,
    DesignWriteResult,
    InvalidDesignForWriteError,
    design_source,
    read_design,
    write_design,
)
from forge_design.design.models import (
    DesignFile,
    DesignNode,
    DesignNodeType,
    PageRoot,
    PropValue,
    TableColumn,
)
from forge_design.design.nesting import (
    ALLOWED_CHILDREN,
    DesignNestingIssue,
    DesignNestingResult,
    can_contain,
    validate_design_nesting,
)

__all__ = [
    "DesignIssue",
    "DesignReadResult",
    "DesignRevision",
    "DesignWriteConflictError",
    "DesignWriteError",
    "DesignWriteResult",
    "InvalidDesignForWriteError",
    "design_source",
    "read_design",
    "write_design",
    "DesignFile",
    "DesignNode",
    "DesignNodeType",
    "PageRoot",
    "PropValue",
    "TableColumn",
    "ALLOWED_CHILDREN",
    "DesignNestingIssue",
    "DesignNestingResult",
    "can_contain",
    "validate_design_nesting",
]
