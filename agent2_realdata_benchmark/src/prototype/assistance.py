"""Illustrative local assistance resource.

Not supervisor-approved educational content.
Not an estimate of an intervention's learning effect.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class AssistanceResource:
    resource_id: str
    concept_id: str
    resource_type: str
    title: str
    body: str


DEMO_SUMMARY = AssistanceResource(
    resource_id="loss_aversion_summary_v1",
    concept_id="loss_aversion",
    resource_type="concept_summary",
    title="Optional concept summary",
    body=(
        "Loss aversion describes a tendency for losses to "
        "feel more impactful than gains of similar size. "
        "It is a behavioral tendency, not a universal rule. "
        "Consider how a person might react differently to "
        "losing €10 and gaining €10."
    ),
)
