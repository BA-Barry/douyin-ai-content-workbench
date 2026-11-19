from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")


@unittest.skipUnless(os.name == "nt" and POWERSHELL, "Windows PowerShell is required")
class WorkbenchLauncherTests(unittest.TestCase):
    """Exercise the launcher with mocked process creation; never start a server."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="launcher_", dir=ROOT / "workspace")
        self.project = Path(self.temp.name) / "中文 project with spaces"
        (self.project / "workbench").mkdir(parents=True)
        (self.project / "config").mkdir()
        (self.project / "envs/content/Scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "workbench/open-workbench.ps1", self.project / "workbench/open-workbench.ps1")
        (self.project / "config/project-env.ps1").write_text("# test environment\n", encoding="ascii")
        (self.project / "workbench/server.py").touch()
        (self.project / "envs/content/Scripts/python.exe").touch()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_script(self, code: str) -> subprocess.CompletedProcess[str]:
        encoded = base64.b64encode(code.encode("utf-16-le")).decode("ascii")
        return subprocess.run(
            [POWERSHELL, "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
        )

    def launch(self, response: str, *, port: int = 65431, offline: bool = False) -> subprocess.CompletedProcess[str]:
        project_literal = str(self.project).replace("'", "''")
        return self.run_script(f"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new()
$testRoot = '{project_literal}'
$global:launcherProbeCalls = 0
$global:launcherStarts = @()
function Invoke-RestMethod {{
    param($Uri, $TimeoutSec)
    $global:launcherProbeCalls += 1
    {response}
}}
function Start-Process {{
    param($FilePath, $ArgumentList, $WorkingDirectory, $WindowStyle,
          $RedirectStandardOutput, $RedirectStandardError, [switch]$PassThru)
    $global:launcherStarts += [pscustomobject]@{{file=$FilePath; arguments=$ArgumentList;
        workingDirectory=$WorkingDirectory; windowStyle=$WindowStyle;
        stdout=$RedirectStandardOutput; stderr=$RedirectStandardError}}
    if ($PassThru) {{ return [pscustomobject]@{{Id=999999; HasExited=$false}} }}
}}
try {{
    & (Join-Path $testRoot 'workbench/open-workbench.ps1') -NoBrowser -Port {port} {'-Offline' if offline else ''}
    'RESULT:' + (ConvertTo-Json -InputObject @($global:launcherStarts) -Depth 5 -Compress)
}} catch {{
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}}
""")

    def test_all_entrypoints_are_ascii_and_parse_on_windows_powershell(self) -> None:
        names = ("open-workbench.ps1", "start-workbench.ps1", "start-workbench-offline.ps1")
        for name in names:
            path = ROOT / "workbench" / name
            path.read_bytes().decode("ascii")
            literal = str(path).replace("'", "''")
            result = self.run_script(f"$e=$null; $t=$null; [void][Management.Automation.Language.Parser]::ParseFile('{literal}',[ref]$t,[ref]$e); if ($e.Count) {{$e | Out-String | Write-Output; exit 1}}")
            self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        command = (ROOT / "workbench/打开工作台.cmd").read_bytes().decode("ascii")
        self.assertIn('"%~dp0open-workbench.ps1"', command)
        self.assertIn("if errorlevel 1", command)

    def test_matching_existing_project_is_reused_without_launch_or_browser(self) -> None:
        result = self.launch("return @{status='ok'; root=$testRoot; mode='local'}")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("RESULT:[]", result.stdout)
        self.assertFalse((self.project / "workspace").exists())

    def test_another_project_is_never_reused(self) -> None:
        result = self.launch("return @{status='ok'; root='G:\\unrelated-project'; mode='local'}")
        self.assertEqual(1, result.returncode)
        self.assertIn("another application or project", result.stderr)
        self.assertFalse((self.project / "workspace").exists())

    def test_offline_request_does_not_reuse_online_service(self) -> None:
        result = self.launch("return @{status='ok'; root=$testRoot; mode='local'}", offline=True)
        self.assertEqual(1, result.returncode)
        self.assertIn("requested 'offline'", result.stderr)

    def test_background_command_quotes_paths_and_logs_on_project_drive(self) -> None:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        result = self.launch("if ($global:launcherProbeCalls -eq 1) { throw 'not started' }; return @{status='ok'; root=$testRoot; mode='offline'}", port=port, offline=True)
        self.assertEqual(0, result.returncode, result.stderr + result.stdout)
        records = json.loads(next(line[7:] for line in result.stdout.splitlines() if line.startswith("RESULT:")))
        self.assertEqual(1, len(records))
        command = records[0]
        self.assertEqual("Hidden", command["windowStyle"])
        self.assertEqual("-u", command["arguments"][0])
        self.assertEqual('"' + str(self.project / "workbench/server.py") + '"', command["arguments"][1])
        self.assertIn("--offline", command["arguments"])
        self.assertTrue(Path(command["stdout"]).is_relative_to(self.project))
        self.assertTrue(Path(command["stderr"]).is_relative_to(self.project))

    def test_unhealthy_occupied_port_fails_without_launching(self) -> None:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            result = self.launch("throw 'health unavailable'", port=listener.getsockname()[1])
        self.assertEqual(1, result.returncode)
        self.assertIn("is occupied", result.stderr)
        self.assertIn("Nothing was stopped", result.stderr)
        self.assertFalse((self.project / "workspace").exists())


if __name__ == "__main__":
    unittest.main()
