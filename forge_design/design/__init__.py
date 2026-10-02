"""Format design, validation et I/O explicites, sans génération de template."""

from forge_design.design.bindings import (
    DesignBindingIssue,
    DesignBindingResult,
    validate_design_bindings,
)
from forge_design.design.conditional_bindings import (
    ConditionalBindingIssue,
    ConditionalBindingResult,
    validate_conditional_bindings,
)
from forge_design.design.form_fields import (
    FormFieldIssue,
    FormFieldValidationResult,
    validate_form_fields,
)
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
    FieldDefinition,
    FieldInputType,
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
from forge_design.design.table_bindings import (
    SuggestedTableColumn,
    TableBindingInfo,
    TableBindingIssue,
    TableBindingResult,
    TableBindingStatus,
    TableColumnBindingInfo,
    suggest_table_columns,
    validate_table_bindings,
)

__all__ = [
    "ConditionalBindingIssue",
    "ConditionalBindingResult",
    "validate_conditional_bindings",
    "SuggestedTableColumn",
    "TableBindingInfo",
    "TableBindingIssue",
    "TableBindingResult",
    "TableBindingStatus",
    "TableColumnBindingInfo",
    "suggest_table_columns",
    "validate_table_bindings",
    "DesignBindingIssue",
    "DesignBindingResult",
    "validate_design_bindings",
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
    "FieldDefinition",
    "FieldInputType",
    "FormFieldIssue",
    "FormFieldValidationResult",
    "validate_form_fields",
    "ALLOWED_CHILDREN",
    "DesignNestingIssue",
    "DesignNestingResult",
    "can_contain",
    "validate_design_nesting",
]
