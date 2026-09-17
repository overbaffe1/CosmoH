import numpy as np

from cosmofire.providers import FIRMS_RENAME, firms_area_csv, nbr


def test_firms_rename_and_normalise(tmp_path):
    csv = tmp_path / "firms.csv"
    csv.write_text(
        "latitude,longitude,acq_date,acq_time,bright_ti4,frp,confidence,daynight,satellite,instrument\n"
        "56.01,92.87,2026-09-17,0712,347.1,18.4,h,D,Terra,MODIS\n",
        encoding="utf-8",
    )
    df = firms_area_csv("http://example.invalid/x.csv", cache=csv)
    assert list(df["lat"])[0] == 56.01
    assert df["acq_time"].iloc[0] == "0712"
    assert df["brightness"].iloc[0] == 347.1
    assert set(FIRMS_RENAME.values()) & set(df.columns)


def test_nbr_handles_zero_denominator():
    out = nbr(np.array([0.0, 0.4]), np.array([0.0, 0.2]))
    assert out[0] == 0.0
    assert abs(out[1] - 1 / 3) < 1e-6
