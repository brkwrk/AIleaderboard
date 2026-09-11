import leaderboard


def test_has_run() -> None:
    assert hasattr(leaderboard, "run")
    assert callable(leaderboard.run)
