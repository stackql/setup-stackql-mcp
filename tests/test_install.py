import hashlib
import contextlib
import json
import os
import sys
import tempfile
import unittest
import zipfile
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import install


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("install.Path.home", return_value=Path(tempfile.gettempdir())))
        self.enterContext(patch("install.log"))
        self.enterContext(contextlib.redirect_stdout(StringIO()))

    def test_native_bundle_installation(self):
        cases = [
            ("Windows", "ARM64", "windows-arm64", "stackql.exe"),
            ("Windows", "X64", "windows-x64", "stackql.exe"),
            ("Linux", "ARM64", "linux-arm64", "stackql"),
            ("Linux", "X64", "linux-x64", "stackql"),
            ("macOS", "ARM64", "darwin-universal", "stackql"),
        ]
        for runner_os, arch, key, binary in cases:
            for version in ("latest", "v0.12.778"):
                with self.subTest(os=runner_os, arch=arch, version=version):
                    data = BytesIO()
                    with zipfile.ZipFile(data, "w") as bundle:
                        bundle.writestr(f"server/{binary}", b"native-binary")
                    payload = data.getvalue()
                    checksum = hashlib.sha256(payload).hexdigest().encode()
                    with tempfile.TemporaryDirectory() as tmp:
                        base = Path(tmp)
                        env = {
                            "RUNNER_OS": runner_os, "RUNNER_ARCH": arch,
                            "RUNNER_TEMP": tmp, "STACKQL_SETUP_VERSION": version,
                            "GITHUB_OUTPUT": str(base / "output"),
                            "GITHUB_ENV": str(base / "env"),
                            "GITHUB_PATH": str(base / "path"),
                        }
                        with patch.dict(os.environ, env, clear=True), \
                             patch("install.platform.machine", return_value="AMD64"), \
                             patch("install.fetch", side_effect=[payload, checksum]) as fetch:
                            install.main()
                        url = f"{install.RELEASE_BASE}/{version.lstrip('v')}/stackql-mcp-{key}.mcpb"
                        self.assertEqual([call.args[0] for call in fetch.call_args_list], [url, url + ".sha256"])
                        bin_path = base / "stackql-mcp-bin" / binary
                        self.assertEqual(bin_path.read_bytes(), b"native-binary")
                        config = json.loads((base / "stackql-mcp-config.json").read_text())
                        self.assertEqual(config["mcpServers"]["stackql"]["command"], str(bin_path))
                        self.assertIn(f"binary-path={bin_path}", (base / "output").read_text())
                        self.assertIn(f"STACKQL_MCP_BIN={bin_path}", (base / "env").read_text())
                        self.assertEqual((base / "path").read_text().strip(), str(bin_path.parent))

    def test_local_arm64_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            bundle_path = Path(tmp) / "local.mcpb"
            with zipfile.ZipFile(bundle_path, "w") as bundle:
                bundle.writestr("server/stackql.exe", b"arm64-binary")
            with patch.dict(os.environ, {
                "RUNNER_OS": "Windows", "RUNNER_ARCH": "ARM64",
                "RUNNER_TEMP": tmp, "STACKQL_SETUP_BUNDLE": str(bundle_path),
            }, clear=True), patch("install.fetch") as fetch:
                install.main()
            fetch.assert_not_called()
            self.assertEqual((Path(tmp) / "stackql-mcp-bin/stackql.exe").read_bytes(), b"arm64-binary")

    def test_arm64_checksum_mismatch_prevents_extraction(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {
                "RUNNER_OS": "Windows", "RUNNER_ARCH": "ARM64", "RUNNER_TEMP": tmp,
            }, clear=True), patch("install.fetch", side_effect=[b"bad bundle", b"0000"]):
                with self.assertRaises(SystemExit):
                    install.main()
            self.assertFalse((Path(tmp) / "stackql-mcp-bin").exists())

    def test_native_detection_without_runner_variables(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("install.sys.platform", "win32"), \
             patch("install.platform.machine", return_value="ARM64"):
            self.assertEqual(install.platform_key(), "windows-arm64")


if __name__ == "__main__":
    unittest.main()
