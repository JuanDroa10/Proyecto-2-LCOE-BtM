"""Shared HTTP session setup.

See the Task 5 docstring in the implementation plan for why this exists:
this environment's outbound HTTPS traffic is intercepted by a corporate
TLS-inspecting proxy whose CA is trusted by the OS but not by Python's
bundled certifi trust store.
"""
import os
import subprocess
from pathlib import Path

import certifi
import requests

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CA_BUNDLE_PATH = _DATA_DIR / "ca_bundle.pem"


def build_ca_bundle(force: bool = False) -> Path:
    """Combine certifi's CA bundle with extra roots trusted by the OS keychain.

    Safe to call repeatedly: corporate proxy intermediate certs can rotate on
    a short cycle, so re-running this regenerates the bundle from whatever
    the keychain currently trusts.
    """
    if CA_BUNDLE_PATH.exists() and not force:
        return CA_BUNDLE_PATH
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    base = Path(certifi.where()).read_bytes()
    extra = b""
    try:
        extra = subprocess.run(
            ["security", "find-certificate", "-a", "-p", "/Library/Keychains/System.keychain"],
            capture_output=True, check=True, timeout=15,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass  # not on macOS, or keychain unavailable — fall back to certifi alone
    CA_BUNDLE_PATH.write_bytes(base + b"\n" + extra)
    return CA_BUNDLE_PATH


def ensure_ca_trust() -> Path:
    """Point the standard OpenSSL/requests env vars at the combined bundle.

    Needed for libraries (e.g. aiohttp, used internally by pydataxm) that
    build their own SSL context from SSL_CERT_FILE rather than accepting an
    explicit `verify=` argument.
    """
    bundle = build_ca_bundle()
    os.environ["SSL_CERT_FILE"] = str(bundle)
    os.environ["REQUESTS_CA_BUNDLE"] = str(bundle)
    return bundle


def get_session() -> requests.Session:
    bundle = ensure_ca_trust()
    session = requests.Session()
    session.verify = str(bundle)
    return session
