"""Apply a captured six-slot plan through the existing inventory service."""
from war3_artifact_plan import ArtifactPlan


def apply_artifact_plan(trainer, plan):
    if type(plan) is not ArtifactPlan:
        raise TypeError('Expected an immutable ArtifactPlan')
    trainer.add_abilities_to_selected_unit(('AInv',))
    return trainer.replace_selected_inventory_items(plan.replacements)
