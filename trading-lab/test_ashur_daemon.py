"""Offline regression tests for ASHUR's Enzonic ledger publisher."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import dulwich.client
from dulwich import porcelain
from dulwich.contrib.paramiko_vendor import ParamikoSSHVendor

MODULE_PATH = Path(__file__).with_name("ashur_daemon.py")
SPEC = importlib.util.spec_from_file_location("ashur_daemon_under_test", MODULE_PATH)
daemon = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(daemon)


def test_paramiko_vendor_is_the_actual_dulwich_default(monkeypatch):
    captured = {}

    def fake_push(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return SimpleNamespace(ref_status=None)

    monkeypatch.setattr(porcelain, "push", fake_push)
    daemon._push_with_paramiko(Path("/tmp/ashur-test-key"))

    assert dulwich.client.get_ssh_vendor is ParamikoSSHVendor
    assert captured["kwargs"]["username"] == "git"
    assert captured["kwargs"]["key_filename"] == "/tmp/ashur-test-key"
    assert "vendor" not in captured["kwargs"]


def test_openssh_fallback_is_skipped_for_unmapped_container_uid(monkeypatch):
    def missing_user(_uid):
        raise KeyError("uid not present in passwd database")

    monkeypatch.setattr(daemon.pwd, "getpwuid", missing_user)
    assert daemon._push_with_openssh_if_uid_resolves() is False


if __name__ == "__main__":
    import unittest
    unittest.main()
