"""Warcraft III 3.0 stat-detail abilities and trainer-facing fields."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StatDetailSpec:
    key: str
    label: str
    base_class: str
    value_field: str
    flat_field: str | None = None
    flat_value: bool | None = None
    scale: float = 1.0
    baseline: float = 0.0
    controller: str = ""


STAT_DETAIL_SPECS = (
    StatDetailSpec("critical_chance", "致命一击几率%", "AIxr", "Ocr1", scale=1.0, controller="AIxr"),
    StatDetailSpec("critical_damage", "暴击伤害%", "AIxr", "Ixr2", scale=1.0, baseline=150.0, controller="AIxr"),
    StatDetailSpec("spell_critical_chance", "法术暴击几率%", "AIsc", "Ocr1", scale=1.0, controller="AIsc"),
    StatDetailSpec("spell_critical_damage", "法术暴击伤害%", "AIsc", "Ixr2", scale=1.0, baseline=150.0, controller="AIsc"),
    StatDetailSpec("ability_speed_flat", "技能速度", "AIcr", "Icr1", "Icr2", True, controller="Ardr"),
    StatDetailSpec("ability_speed_percent", "技能速度%", "AIcr", "Icr1", "Icr2", False, 100.0, controller="AIcr"),
    StatDetailSpec("ability_amp_flat", "技能增强", "AIap", "Isa1", "Isa2", True, controller="AADu"),
    StatDetailSpec("ability_amp_percent", "技能增强%", "AIap", "Isa1", "Isa2", False, 100.0, controller="AIap"),
    StatDetailSpec("lifesteal_percent", "生命窃取%", "AIvx", "Ivam", scale=100.0, controller="AIvx"),
    StatDetailSpec("ability_vamp_flat", "技能汲取", "AIsv", "Isv1", "Isv2", True, controller="AIsv"),
    StatDetailSpec("ability_vamp_percent", "技能汲取%", "AIsv", "Isv1", "Isv2", False, 100.0, controller="AGsv"),
    StatDetailSpec("resolve_flat", "斗志", "AIlv", "Ilv1", "Ilv2", True, controller="AIlv"),
    StatDetailSpec("resolve_percent", "斗志%", "AIlv", "Ilv1", "Ilv2", False, 100.0, controller="BT5b"),
    StatDetailSpec("magic_resistance_percent", "魔法抗性%", "AIss", "isr2", scale=100.0, controller="AIss"),
)

STAT_DETAIL_BY_KEY = {spec.key: spec for spec in STAT_DETAIL_SPECS}
