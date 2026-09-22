"""Unit tests for the analysis layer. Hand-built data, no network."""
import pytest

from fpl import analysis as an


def pick(element, captain=False, vice=False):
    return {"element": element, "is_captain": captain, "is_vice_captain": vice}


def squad(ids, captain, vice):
    return [pick(i, i == captain, i == vice) for i in ids]


def entry(points, hit=0, bench=0, transfers=0):
    return {
        "points": points,
        "event_transfers_cost": hit,
        "points_on_bench": bench,
        "event_transfers": transfers,
    }


MANAGERS = [(1, "Alpha", "Ann"), (2, "Beta", "Ben"), (3, "Gamma", "Gita")]

PICKS = [
    {"entry_history": entry(70, hit=4), "active_chip": None,
     "picks": squad(list(range(101, 116)), captain=101, vice=102)},
    {"entry_history": entry(68), "active_chip": "bboost",
     "picks": squad(list(range(101, 113)) + [201, 202, 203], captain=101, vice=103)},
    {"entry_history": entry(50), "active_chip": None,
     "picks": squad([101] + list(range(301, 315)), captain=301, vice=101)},
]

POINTS = {101: 12, 102: 2, 301: 9, 201: 15, 202: 1, 203: 0}


class TestWeeklyTable:
    def test_sorts_by_points_net_of_hits(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        # Alpha scored 70 gross but took a -4 hit, so Beta's 68 wins the week.
        assert [r["team"] for r in rows] == ["Beta", "Alpha", "Gamma"]
        assert rows[0]["points"] == 68
        assert rows[1]["points"] == 66
        assert rows[1]["gross"] == 70

    def test_assigns_place(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        assert [r["place"] for r in rows] == [1, 2, 3]

    def test_captain_points_are_doubled(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        alpha = next(r for r in rows if r["team"] == "Alpha")
        assert alpha["captain"] == 101
        assert alpha["captain_points"] == 24  # 12 doubled

    def test_captain_missing_from_live_data_scores_zero(self):
        rows = an.weekly_table(MANAGERS, PICKS, {})
        assert all(r["captain_points"] == 0 for r in rows)

    def test_records_chip(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        beta = next(r for r in rows if r["team"] == "Beta")
        assert beta["chip"] == "bboost"

    def test_starters_are_first_eleven_only(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        alpha = next(r for r in rows if r["team"] == "Alpha")
        assert len(alpha["starters"]) == 11
        assert len(alpha["squad"]) == 15
        assert 112 not in alpha["starters"]  # 12th pick is benched


class TestOwnership:
    def test_counts_only_starters_by_default(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        counts = an.ownership(rows)
        assert counts[101] == 3          # everyone starts 101
        assert counts.get(201, 0) == 0   # bench-boost bench players do not count

    def test_can_count_full_squads(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        counts = an.ownership(rows, starters_only=False)
        assert counts[201] == 1


class TestDifferentials:
    def test_finds_players_only_i_own(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        mine, theirs = an.differentials(rows, entry_id=3)
        assert 101 not in mine        # shared with everyone
        assert 301 in mine            # only Gamma has it
        assert all(p not in mine for p in (102, 103))

    def test_theirs_excludes_anything_in_my_squad(self):
        rows = an.weekly_table(MANAGERS, PICKS, POINTS)
        mine, theirs = an.differentials(rows, entry_id=3)
        gamma = next(r for r in rows if r["team"] == "Gamma")
        assert not set(theirs) & set(gamma["squad"])


class TestSeason:
    HISTORIES = [
        {"current": [
            {"event": 1, "points": 60, "event_transfers_cost": 0, "total_points": 60, "overall_rank": 5},
            {"event": 2, "points": 50, "event_transfers_cost": 8, "total_points": 102, "overall_rank": 9},
        ]},
        {"current": [
            {"event": 1, "points": 55, "event_transfers_cost": 0, "total_points": 55, "overall_rank": 7},
            {"event": 2, "points": 70, "event_transfers_cost": 0, "total_points": 125, "overall_rank": 2},
        ]},
        {"current": [
            {"event": 1, "points": 40, "event_transfers_cost": 0, "total_points": 40, "overall_rank": 20},
            {"event": 2, "points": 45, "event_transfers_cost": 0, "total_points": 85, "overall_rank": 18},
        ]},
    ]

    def test_winner_per_gameweek(self):
        season = an.season_table(MANAGERS, self.HISTORIES)
        assert season[1][0]["team"] == "Alpha"
        assert season[2][0]["team"] == "Beta"

    def test_hit_applied_to_weekly_score(self):
        season = an.season_table(MANAGERS, self.HISTORIES)
        alpha_gw2 = next(r for r in season[2] if r["team"] == "Alpha")
        assert alpha_gw2["points"] == 42  # 50 minus an -8 hit

    def test_weekly_wins_tally(self):
        season = an.season_table(MANAGERS, self.HISTORIES)
        assert an.weekly_wins(season) == {"Alpha": 1, "Beta": 1}

    def test_league_position_uses_cumulative_total(self):
        season = an.season_table(MANAGERS, self.HISTORIES)
        pos = an.league_position_by_gw(season)
        assert pos[1][1] == 1   # Alpha led after GW1
        assert pos[2][2] == 1   # Beta overtook by GW2
        assert pos[1][2] == 2

    def test_position_keyed_by_entry_so_duplicate_team_names_do_not_collide(self):
        managers = [(1, "Same Name", "Ann"), (2, "Same Name", "Ben")]
        histories = [
            {"current": [{"event": 1, "points": 70, "event_transfers_cost": 0,
                          "total_points": 70, "overall_rank": 1}]},
            {"current": [{"event": 1, "points": 40, "event_transfers_cost": 0,
                          "total_points": 40, "overall_rank": 2}]},
        ]
        pos = an.league_position_by_gw(an.season_table(managers, histories))
        assert pos[1][1] == 1 and pos[2][1] == 2

    def test_late_joiner_has_no_entry_before_they_arrived(self):
        managers = [(1, "Alpha", "Ann"), (9, "Late", "Lee")]
        histories = [
            {"current": [
                {"event": 1, "points": 50, "event_transfers_cost": 0, "total_points": 50, "overall_rank": 1},
                {"event": 2, "points": 50, "event_transfers_cost": 0, "total_points": 100, "overall_rank": 1}]},
            {"current": [
                {"event": 2, "points": 60, "event_transfers_cost": 0, "total_points": 60, "overall_rank": 2}]},
        ]
        pos = an.league_position_by_gw(an.season_table(managers, histories))
        assert 1 not in pos[9]      # nothing before they joined
        assert pos[9][2] == 2


class TestFixtureDifficulty:
    FIXTURES = [
        {"event": 6, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4},
        {"event": 7, "team_h": 2, "team_a": 1, "team_h_difficulty": 3, "team_a_difficulty": 3},
        {"event": 9, "team_h": 1, "team_a": 2, "team_h_difficulty": 5, "team_a_difficulty": 1},
        {"event": None, "team_h": 1, "team_a": 2, "team_h_difficulty": 1, "team_a_difficulty": 1},
    ]

    def test_averages_within_horizon_only(self):
        fdr = an.fixture_difficulty(self.FIXTURES, from_gw=6, horizon=2)
        assert fdr[1] == pytest.approx(2.5)   # GW6 easy(2) + GW7 away(3)
        assert fdr[2] == pytest.approx(3.5)

    def test_ignores_unscheduled_fixtures(self):
        fdr = an.fixture_difficulty(self.FIXTURES, from_gw=6, horizon=10)
        assert fdr[1] == pytest.approx((2 + 3 + 5) / 3)

    def test_team_with_no_fixture_is_absent(self):
        fdr = an.fixture_difficulty(self.FIXTURES, from_gw=20, horizon=3)
        assert fdr == {}


class TestNormalise:
    def test_scales_to_unit_range(self):
        assert an._normalise([0, 5, 10]) == [0.0, 0.5, 1.0]

    def test_flat_input_is_neutral(self):
        # A stat every player shares must not swing the ranking either way.
        assert an._normalise([7, 7, 7]) == [0.5, 0.5, 0.5]


class TestAvailability:
    def test_injured_player_excluded(self):
        assert not an.is_available({"status": "i", "chance_of_playing_next_round": None})

    def test_doubtful_player_excluded(self):
        assert not an.is_available({"status": "a", "chance_of_playing_next_round": 50})

    def test_fit_player_included(self):
        assert an.is_available({"status": "a", "chance_of_playing_next_round": None})
        assert an.is_available({"status": "a", "chance_of_playing_next_round": 100})


def player(pid, name, team, etype, **over):
    base = {
        "id": pid, "web_name": name, "team": team, "element_type": etype,
        "status": "a", "chance_of_playing_next_round": None, "minutes": 900,
        "form": "5.0", "points_per_game": "5.0",
        "expected_goal_involvements_per_90": "0.50",
        "now_cost": 70, "total_points": 50, "selected_by_percent": "10.0",
    }
    base.update(over)
    return base


BOOT = {
    "teams": [
        {"id": 1, "short_name": "ARS"},
        {"id": 2, "short_name": "BUR"},
    ],
    "element_types": [
        {"id": 1, "singular_name_short": "GKP"},
        {"id": 4, "singular_name_short": "FWD"},
    ],
    "elements": [
        player(1, "Star", 1, 4, form="9.0", expected_goal_involvements_per_90="1.10"),
        player(2, "Steady", 1, 4, form="4.0"),
        player(3, "Injured", 1, 4, form="9.9", status="i"),
        player(4, "Doubtful", 1, 4, form="9.9", chance_of_playing_next_round=25),
        player(5, "Benchwarmer", 1, 4, form="9.9", minutes=30),
        player(6, "Keeper", 1, 1, form="6.0", expected_goal_involvements_per_90="0.00"),
        player(7, "NoFixture", 3, 4, form="9.9"),
    ],
}

FIX = [
    {"event": 6, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4},
    {"event": 7, "team_h": 1, "team_a": 2, "team_h_difficulty": 2, "team_a_difficulty": 4},
]


class TestRankPlayers:
    def result(self, **kw):
        return an.rank_players(BOOT, FIX, from_gw=6, horizon=2, **kw)

    def test_best_form_and_xgi_ranks_first(self):
        assert self.result()["FWD"][0]["name"] == "Star"

    def test_excludes_injured_and_doubtful(self):
        names = [p["name"] for p in self.result()["FWD"]]
        assert "Injured" not in names
        assert "Doubtful" not in names

    def test_excludes_players_short_of_minutes(self):
        assert "Benchwarmer" not in [p["name"] for p in self.result()["FWD"]]

    def test_excludes_teams_with_no_fixture_in_window(self):
        # A blank gameweek means there is nothing to recommend.
        assert "NoFixture" not in [p["name"] for p in self.result()["FWD"]]

    def test_ranks_within_position(self):
        # The keeper has zero xGI but still appears, because GKPs are
        # only ever compared against other GKPs.
        assert [p["name"] for p in self.result()["GKP"]] == ["Keeper"]

    def test_reports_fixture_difficulty(self):
        assert self.result()["FWD"][0]["fdr"] == 2.0

    def test_top_limits_results(self):
        assert len(self.result(top=1)["FWD"]) == 1
