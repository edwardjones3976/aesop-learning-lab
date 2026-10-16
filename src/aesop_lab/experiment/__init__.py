"""Fixed, descriptive text-versus-diagram pilot protocol.

This module makes no claim that a condition improves learning. A local learner
can inspect assignments and observations, while a comparison remains
``insufficient_evidence`` until the predeclared outcome and sample rules pass.
"""

from .protocol import (
    PROTOCOL,
    Exposure,
    Protocol,
    analyze,
    assign_condition,
    qualifies_primary_outcome,
)

__all__ = [
    "PROTOCOL", "Exposure", "Protocol", "analyze", "assign_condition",
    "qualifies_primary_outcome",
]
