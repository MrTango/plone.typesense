"""
TypesenseFilterBuilder — validated builder for Typesense filter_by strings.

Typesense filter syntax reference:
  - Exact match:    field:=value
  - Not equal:      field:!=value
  - Greater than:   field:>value
  - Less than:      field:<value
  - Range:          field:[min..max]
  - In list:        field:=[val1,val2,val3]
  - Not in list:    field:!=[val1,val2,val3]
  - AND:            field1:=val1 && field2:=val2
  - OR:             field1:=val1 || field2:=val2

This replaces ad-hoc string concatenation with a structured,
validated builder that is easier to test and maintain.
"""

from plone.typesense import log


class TypesenseFilterBuilder:
    """Build validated Typesense filter_by strings."""

    def __init__(self):
        self._conditions = []

    # -- public builder API --------------------------------------------------

    def equals(self, field, value):
        """field:=value or field:=[v1,v2] for lists."""
        self._conditions.append(self._format_match(field, "=", value))
        return self

    def not_equals(self, field, value):
        """field:!=value or field:!=[v1,v2] for lists."""
        self._conditions.append(self._format_match(field, "!=", value))
        return self

    def greater_than(self, field, value):
        """field:>value"""
        self._validate_field(field)
        self._conditions.append(f"{field}:>{self._escape(value)}")
        return self

    def greater_equal(self, field, value):
        """field:>=value"""
        self._validate_field(field)
        self._conditions.append(f"{field}:>={self._escape(value)}")
        return self

    def less_than(self, field, value):
        """field:<value"""
        self._validate_field(field)
        self._conditions.append(f"{field}:<{self._escape(value)}")
        return self

    def less_equal(self, field, value):
        """field:<=value"""
        self._validate_field(field)
        self._conditions.append(f"{field}:<={self._escape(value)}")
        return self

    def range(self, field, min_val, max_val):
        """field:[min..max]"""
        self._validate_field(field)
        self._conditions.append(
            f"{field}:[{self._escape(min_val)}..{self._escape(max_val)}]"
        )
        return self

    def raw(self, expression):
        """Add a raw, pre-built filter expression (escape hatch)."""
        if expression:
            self._conditions.append(str(expression))
        return self

    # -- output --------------------------------------------------------------

    def build(self, join="&&"):
        """Return the final filter_by string.

        Parameters
        ----------
        join : str
            The logical operator to join conditions.
            Defaults to ``&&`` (AND).  Use ``||`` for OR.
        """
        if not self._conditions:
            return ""
        joiner = f" {join.strip()} "
        return joiner.join(self._conditions)

    def __str__(self):
        return self.build()

    def __repr__(self):
        return f"TypesenseFilterBuilder(conditions={self._conditions!r})"

    def __bool__(self):
        return bool(self._conditions)

    def __len__(self):
        return len(self._conditions)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _validate_field(field):
        if not field or not isinstance(field, str):
            raise ValueError(f"Invalid field name: {field!r}")
        # Typesense field names must be alphanumeric, underscore, or dot
        for ch in field:
            if not (ch.isalnum() or ch in ("_", ".")):
                raise ValueError(
                    f"Invalid character {ch!r} in field name: {field!r}"
                )

    @staticmethod
    def _escape(value):
        """Convert a value to its Typesense string representation."""
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        # String values — always backtick-wrap for safety
        s = str(value)
        return f"`{s}`"

    def _format_match(self, field, operator, value):
        """Format an equality/inequality filter, handling lists."""
        self._validate_field(field)
        if isinstance(value, (list, tuple, set)):
            values = [self._escape(v) for v in value]
            joined = ", ".join(values)
            if operator == "!=":
                return f"{field}:!=[{joined}]"
            return f"{field}:[{joined}]"
        return f"{field}:{operator}{self._escape(value)}"
