from cosmorisk.providers import ENDPOINTS, OfflineError, fetch_endpoint


def test_swpc_endpoints_declared_and_offline_is_explicit():
    assert {"kp", "dst", "protons", "xrays", "f107"} <= set(ENDPOINTS)
    try:
        fetch_endpoint("kp")
    except OfflineError as exc:
        assert "SWPC" in str(exc)
