"""`hermes floorplan …`: the model-free probe, and the ask that LS-3919 owns.

The probe is the one thing LS-3919 and local health checks need: which plugin, which protocol, which
profile, and where the skill this install registered actually lives. It answers from the running process
only — no model call, no network, no credential, and no path the repository can supply.
"""
from __future__ import annotations

import json
import platform
import sys
from pathlib import Path

PLUGIN = "floorplan"
SKILL_NAME = "floorplan"
PROTOCOL = 1  # the CLI/probe contract; LS-3919's `ask` extends it rather than replacing it
PLUGIN_ROOT = Path(__file__).resolve().parents[1]


def skill_dir(skill_path) -> Path:
    """The folder of the SKILL.md this plugin registered, refusing anything outside the install."""
    directory = Path(skill_path).resolve().parent
    if not directory.is_relative_to(PLUGIN_ROOT):
        raise ValueError("skill_outside_plugin")
    return directory


def probe_payload(*, profile: str, plugin_version: str = "", skill_path=None) -> dict:
    """What this install is. Safe to print: names and versions, never a secret or a setting."""
    return {
        "plugin": PLUGIN,
        "plugin_version": plugin_version,
        "protocol": PROTOCOL,
        "profile": profile,
        "skill": f"{PLUGIN}:{SKILL_NAME}",
        "skill_dir": str(skill_dir(skill_path)),
        "commands": [PLUGIN],
        "python": {"implementation": platform.python_implementation(), "version": platform.python_version()},
        "os": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "ask": "unavailable",
    }


def setup_cli(parser) -> None:
    """`hermes floorplan probe` and `hermes floorplan ask`."""
    commands = parser.add_subparsers(dest="floorplan_command", required=True)
    commands.add_parser("probe", help="Print what this Floorplan install registered (no model calls)")
    commands.add_parser("ask", help="Ask the map a question (unavailable until LS-3919)")


def probe(args, *, profile: str, plugin_version: str = "", skill_path=None) -> int:
    """One handler for both subcommands: JSON on stdout, 0 for probe, 1 for the not-yet ask."""
    if getattr(args, "floorplan_command", None) == "ask":
        print(json.dumps({"plugin": PLUGIN, "ask": "unavailable",
                          "reason": "Asking the map from Hermes lands in LS-3919."}, sort_keys=True))
        return 1
    try:
        payload = probe_payload(profile=profile, plugin_version=plugin_version, skill_path=skill_path)
    except ValueError as exc:
        print(json.dumps({"plugin": PLUGIN, "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # `python3 -m hermes.runner` is not a supported entry point
    sys.exit("run `hermes floorplan probe` instead")
