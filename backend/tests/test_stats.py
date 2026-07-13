import pytest

from app import stats

DRAWS = [
    {"concurso": 1, "data": "2024-01-01", "dezenas": [1, 2, 3, 4, 5, 6]},
    {"concurso": 2, "data": "2024-01-08", "dezenas": [1, 2, 3, 40, 50, 60]},
    {"concurso": 3, "data": "2024-01-15", "dezenas": [1, 10, 20, 30, 40, 59]},
]


def test_frequency_counts_and_window():
    r = stats.frequency(DRAWS)
    counts = {f["n"]: f["count"] for f in r["freq"]}
    assert counts[1] == 3
    assert counts[2] == 2
    assert counts[59] == 1
    assert counts[13] == 0
    assert r["hot"][0]["n"] == 1

    r2 = stats.frequency(DRAWS, window=1)  # só o concurso 3
    counts2 = {f["n"]: f["count"] for f in r2["freq"]}
    assert counts2[1] == 1 and counts2[2] == 0
    assert r2["draws_considered"] == 1


def test_current_delays():
    r = stats.current_delays(DRAWS)
    d = {x["n"]: x for x in r["delays"]}
    assert d[1]["delay"] == 0  # saiu no último
    assert d[5]["delay"] == 2 and d[5]["last_concurso"] == 1
    assert d[13]["delay"] == 3 and d[13]["last_concurso"] is None  # nunca saiu


def test_parity_theoretical_sums_to_100():
    r = stats.parity_distribution(DRAWS)
    assert abs(sum(row["theoretical_pct"] for row in r["rows"]) - 100) < 0.2
    # concurso 1 tem 3 pares (2,4,6); concursos 2 e 3 têm 4 pares cada
    by_evens = {row["evens"]: row["count"] for row in r["rows"]}
    assert by_evens[3] == 1
    assert by_evens[4] == 2


def test_sum_distribution():
    r = stats.sum_distribution(DRAWS)
    assert r["min"] == 21  # 1+2+3+4+5+6
    assert r["total_draws"] == 3
    assert sum(b["count"] for b in r["bins"]) == 3
    assert r["theoretical_mean"] == 183.0


def test_top_pairs():
    r = stats.top_pairs(DRAWS, limit=3)
    assert r["pairs"][0]["a"] == 1 and r["pairs"][0]["b"] == 2  # par (1,2) saiu 2x
    assert r["pairs"][0]["count"] == 2


def test_xray_uses_only_prior_history():
    r = stats.xray(DRAWS, 3)
    assert r["prior_draws"] == 2
    per_n = {x["n"]: x for x in r["dezenas"]}
    assert per_n[1]["freq_before"] == 2
    assert per_n[1]["freq_rank"] == 1
    assert per_n[10]["freq_before"] == 0
    assert per_n[40]["delay_before"] == 0  # saiu no concurso 2
    assert 0 <= r["hot6_matches"] <= 6
    with pytest.raises(ValueError):
        stats.xray(DRAWS, 99)
    with pytest.raises(ValueError):
        stats.xray(DRAWS, 1)
