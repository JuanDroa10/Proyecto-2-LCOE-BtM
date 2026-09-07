from pathlib import Path

import certifi

from src import http_utils


def test_build_ca_bundle_creates_a_file_at_least_as_large_as_certifi_alone():
    path = http_utils.build_ca_bundle(force=True)
    assert path.exists()
    assert path.stat().st_size >= Path(certifi.where()).stat().st_size


def test_ensure_ca_trust_sets_expected_environment_variables(monkeypatch):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    bundle = http_utils.ensure_ca_trust()
    import os
    assert os.environ["SSL_CERT_FILE"] == str(bundle)
    assert os.environ["REQUESTS_CA_BUNDLE"] == str(bundle)


def test_get_session_can_reach_a_known_https_endpoint():
    session = http_utils.get_session()
    r = session.get(
        "https://re.jrc.ec.europa.eu/api/v5_3/seriescalc",
        params={"lat": 4.71, "lon": -74.07, "outputformat": "json",
                "startyear": 2020, "endyear": 2020},
        timeout=30,
    )
    assert r.status_code == 200
