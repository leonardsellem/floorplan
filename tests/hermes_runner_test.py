"""The plugin's Python half, run the way Hermes runs it: `register(ctx)` on a real package import.

Covers exactly what LS-3918 asks for: one registered skill, one registered `floorplan` CLI command, and a
model-free probe that names this install (protocol, profile, the installed skill folder) with nothing secret.

    python3 -m unittest discover -s tests -p 'hermes_runner_test.py'
"""
import argparse
import importlib
import importlib.util
import io
import json
import platform
import sys
import types
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class FakeContext:
    """The registration surface this plugin uses, and nothing else: skills, CLI commands, the manifest."""

    manifest = types.SimpleNamespace(name="floorplan", version="9.9.9-test")
    profile_name = "throwaway-profile"

    def __init__(self):
        self.skills = []
        self.cli_commands = []

    def register_skill(self, name, path, description=""):
        self.skills.append({"name": name, "path": Path(path), "description": description})

    def register_cli_command(self, name, help, setup_fn, handler_fn=None, description=""):
        self.cli_commands.append({"name": name, "help": help, "setup_fn": setup_fn,
                                  "handler_fn": handler_fn, "description": description})


def load_plugin():
    """Import the plugin the way hermes_cli.plugins_loader does: as `hermes_plugins.<key>`, a package."""
    parent = "hermes_plugins"
    if parent not in sys.modules:
        package = types.ModuleType(parent)
        package.__path__ = []
        sys.modules[parent] = package
    name = parent + ".floorplan"
    spec = importlib.util.spec_from_file_location(
        name, REPO / "__init__.py", submodule_search_locations=[str(REPO)])
    module = importlib.util.module_from_spec(spec)
    module.__package__, module.__path__ = name, [str(REPO)]
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class PluginTest(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.ctx = FakeContext()
        self.plugin.register(self.ctx)
        self.runner = importlib.import_module("hermes_plugins.floorplan.hermes.runner")

    def command(self, argv):
        """The CLI parser Hermes builds from this plugin, and the handler it runs for `hermes floorplan …`."""
        self.assertEqual([c["name"] for c in self.ctx.cli_commands], ["floorplan"])
        entry = self.ctx.cli_commands[0]
        parser = argparse.ArgumentParser(prog="hermes floorplan")
        entry["setup_fn"](parser)
        parser.set_defaults(func=entry["handler_fn"])
        args = parser.parse_args(argv)
        out = io.StringIO()
        with redirect_stdout(out):
            code = args.func(args)
        return code, out.getvalue()

    def test_registers_one_skill_and_one_cli_command(self):
        self.assertEqual([s["name"] for s in self.ctx.skills], ["floorplan"])
        self.assertEqual(self.ctx.skills[0]["path"], REPO / "skills" / "floorplan" / "SKILL.md")
        self.assertTrue(self.ctx.skills[0]["description"])
        self.assertEqual(len(self.ctx.cli_commands), 1)
        self.assertTrue(callable(self.ctx.cli_commands[0]["handler_fn"]))

    def test_probe_names_this_install_without_a_model(self):
        code, out = self.command(["probe"])
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["plugin"], "floorplan")
        self.assertEqual(payload["plugin_version"], "9.9.9-test")
        self.assertEqual(payload["protocol"], 1)
        self.assertEqual(payload["profile"], "throwaway-profile")
        self.assertEqual(payload["skill"], "floorplan:floorplan")
        self.assertEqual(payload["skill_dir"], str((REPO / "skills" / "floorplan").resolve()))
        self.assertEqual(payload["commands"], ["floorplan"])
        self.assertEqual(payload["ask"], "unavailable")
        self.assertEqual(payload["python"]["implementation"], platform.python_implementation())
        self.assertTrue(payload["os"]["system"])

    def test_probe_prints_no_credential_or_machine_setting(self):
        _, out = self.command(["probe"])
        payload = json.loads(out)
        forbidden = ("token", "secret", "password", "credential", "api_key", "auth")
        self.assertEqual([k for k in payload if any(word in k.lower() for word in forbidden)], [])
        self.assertEqual([k for k in payload["python"] if any(word in k.lower() for word in forbidden)], [])

    def test_ask_is_unavailable_until_ls_3919(self):
        code, out = self.command(["ask"])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(out)["ask"], "unavailable")

    def test_a_skill_path_outside_the_installed_plugin_is_refused(self):
        with self.assertRaises(ValueError):
            self.runner.probe_payload(profile="throwaway-profile", plugin_version="9.9.9-test",
                                      skill_path=Path("/etc/hostname"))


if __name__ == "__main__":
    unittest.main()
