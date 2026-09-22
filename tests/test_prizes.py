"""Tests for the GME prize sheet."""
from fpl import prizes as pz


def row(entry, team, points, gross=None):
    return {"entry": entry, "team": team, "points": points,
            "gross": gross if gross is not None else points}


SEASON = {
    1: [row(1, "Alpha", 60), row(2, "Beta", 60), row(3, "Gamma", 40)],
    2: [row(1, "Alpha", 117), row(2, "Beta", 80), row(3, "Gamma", 70)],
}

GAMEWEEKS = {
    "1": {"rows": [row(1, "Alpha", 60), row(2, "Beta", 60), row(3, "Gamma", 40, gross=48)]},
    "2": {"rows": [row(1, "Alpha", 117), row(2, "Beta", 80), row(3, "Gamma", 70)]},
}

STANDINGS = [
    {"rank": 1, "entry": 1, "team": "Alpha"},
    {"rank": 2, "entry": 2, "team": "Beta"},
    {"rank": 3, "entry": 3, "team": "Gamma"},
]


class TestWeeklyPrize:
    def test_regular_gameweek(self):
        assert pz.weekly_prize(1) == 7_000
        assert pz.weekly_prize(37) == 7_000

    def test_final_gameweek_is_the_bonus_round(self):
        assert pz.weekly_prize(38) == 11_000

    def test_weekly_pots_total_the_advertised_amount(self):
        assert sum(pz.weekly_prize(g) for g in range(1, 39)) == 270_000

    def test_all_prize_lines_sum_to_the_pool(self):
        total = (270_000 + sum(pz.SPECIALS.values())
                 + pz.CHAMPION + pz.RUNNER_UP)
        assert total == pz.POOL == 500_000


class TestWeeklyResults:
    def test_a_tie_is_flagged_and_split(self):
        weeks = pz.weekly_results(SEASON)
        gw1 = weeks[0]
        assert gw1["tied"] is True
        assert {w["team"] for w in gw1["winners"]} == {"Alpha", "Beta"}
        assert gw1["each"] == 3_500

    def test_outright_winner_takes_the_pot(self):
        gw2 = pz.weekly_results(SEASON)[1]
        assert gw2["tied"] is False
        assert gw2["each"] == 7_000


class TestExtremes:
    def test_highest_uses_net_score(self):
        assert pz.standings_extremes(GAMEWEEKS)["highest"]["points"] == 117

    def test_lowest_uses_gross_because_hits_are_excluded(self):
        # Gamma netted 40 but scored 48 before an -8 hit. The prize sheet
        # excludes the hit, so 48 is the number that counts.
        low = pz.standings_extremes(GAMEWEEKS)["lowest"]
        assert low["points"] == 48
        assert low["team"] == "Gamma"

    def test_exact_111_is_empty_until_someone_hits_it(self):
        assert pz.standings_extremes(GAMEWEEKS)["exact111"] == []

    def test_exact_111_is_detected(self):
        gws = {"1": {"rows": [row(9, "Delta", 111)]}}
        hits = pz.standings_extremes(gws)["exact111"]
        assert len(hits) == 1 and hits[0]["team"] == "Delta"


class TestLedger:
    def setup_method(self):
        self.led = pz.ledger(SEASON, GAMEWEEKS, STANDINGS)

    def test_banked_money_comes_from_weekly_wins_only(self):
        alpha = next(r for r in self.led["rows"] if r["team"] == "Alpha")
        # 3,500 from the shared GW1 plus 7,000 for winning GW2 outright.
        assert alpha["banked"] == 10_500

    def test_provisional_includes_podium_and_specials(self):
        alpha = next(r for r in self.led["rows"] if r["team"] == "Alpha")
        assert alpha["provisional"] == pz.CHAMPION + pz.SPECIALS["highest"]

    def test_net_subtracts_the_entry_fee(self):
        gamma = next(r for r in self.led["rows"] if r["team"] == "Gamma")
        assert gamma["net"] == gamma["projected"] - pz.ENTRY

    def test_rows_sorted_by_projected_winnings(self):
        got = [r["projected"] for r in self.led["rows"]]
        assert got == sorted(got, reverse=True)

    def test_remaining_weekly_money_excludes_played_gameweeks(self):
        assert self.led["weeklyRemaining"] == 270_000 - 14_000
