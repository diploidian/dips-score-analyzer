"""What you do for other players: which log events count, that live and replay agree, and the Benefactor trait."""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from dips_score.live import helping, titles  # noqa: E402
from dips_score.live.helping import Watch, figures  # noqa: E402
from dips_score.live.history import History  # noqa: E402
from dips_score.live.profile import profile  # noqa: E402
from dips_score.live.tracker import Tracker  # noqa: E402
from dips_score.live.traits import raw, scores  # noqa: E402
from dips_score.profile_view import build_profile  # noqa: E402
from dips_score.sources.combatlog import Event  # noqa: E402

T0 = datetime(2026, 11, 23, 12, 0, 0)
ME, A, B = "Player-1-ME", "Player-1-A", "Player-1-B"
STRANGER, MATE, RAIDER, HOSTILE = 0x518, 0x512, 0x514, 0x548


def ev(event, s=0.0, dst=A, flags=STRANGER, spell="Blessing of Might", **kw):
    return Event(T0 + timedelta(seconds=s), event, ME, "Me", 0x511, dst, "Other", flags, spell_name=spell, **kw)


def cast(s=0.0, **kw):
    return ev("SPELL_CAST_SUCCESS", s, **kw)


def buff(s=0.0, **kw):
    return ev("SPELL_AURA_APPLIED", s, aura_type="BUFF", **kw)


def acts(*events):
    w = Watch()
    return [a for e in events if (a := w.feed(e, ME))]


class Counts(unittest.TestCase):
    def test_a_buff_you_cast_on_them(self):
        (a,) = acts(cast(), buff(.1))
        self.assertEqual((a["kind"], a["spell"], a["group"], a["me"]), ("buff", "Blessing of Might", False, ME))
        self.assertNotIn("Other", str(a))                                       # never a name
        self.assertNotIn(A, str(a))
        self.assertEqual([acts(cast(flags=f), buff(flags=f))[0]["group"] for f in (MATE, RAIDER)], [True, True])

    def test_not_one_logged_again_or_radiating(self):
        self.assertEqual(acts(buff()), [])                                      # back into range: no cast
        self.assertEqual(acts(cast(), buff(1.6)), [])                           # long after it
        self.assertEqual(acts(cast(dst=B), buff(dst=A)), [])                    # cast on somebody else
        self.assertEqual(len(acts(cast(), buff(), buff(.5))), 1)                # one act per cast
        self.assertEqual(acts(cast(), ev("SPELL_AURA_APPLIED", aura_type="DEBUFF")), [])

    def test_a_refresh_of_a_buff_seen(self):
        again = ev("SPELL_AURA_REFRESH", 60.1)
        self.assertEqual(len(acts(cast(), buff(), cast(60), again)), 2)
        self.assertEqual(acts(cast(60), again), [])                             # could be a debuff

    def test_who_never_counts(self):
        self.assertEqual(acts(cast(flags=HOSTILE), buff(flags=HOSTILE)), [])
        self.assertEqual(acts(cast(dst=ME), buff(dst=ME)), [])
        self.assertEqual(acts(cast(dst="Pet-1"), buff(dst="Pet-1")), [])
        self.assertEqual(acts(ev("SPELL_RESURRECT", dst="Pet-1")), [])
        w = Watch()
        self.assertIsNone(w.feed(cast(), None))                                 # you are not known yet

    def test_heals_and_dispels(self):
        heal = lambda flags=STRANGER, **kw: acts(cast(flags=flags), ev("SPELL_HEAL", flags=flags, **kw))  # noqa: E731
        self.assertEqual([a["kind"] for a in heal(amount=100, overheal=40)], ["heal"])
        self.assertEqual(heal(amount=100, overheal=100), [])                    # healed nothing
        self.assertEqual(heal(MATE, amount=100), [])                            # Mercy has those
        self.assertEqual(acts(ev("SPELL_HEAL", amount=100)), [])                # splash, not cast on them
        self.assertEqual([a["kind"] for a in acts(cast(), ev("SPELL_DISPEL"))], ["dispel"])

    def test_revives(self):
        got = acts(ev("SPELL_RESURRECT"), ev("SPELL_RESURRECT", 9, flags=MATE))
        self.assertEqual([(a["kind"], a["group"]) for a in got], [("revive", False), ("revive", True)])


class Figures(unittest.TestCase):
    def of(self, *events):
        return figures(acts(*events), T0 - timedelta(days=15), T0 + timedelta(days=3))

    def test_once_a_day(self):
        day = 86400
        got = self.of(cast(), buff(), cast(99), buff(99), cast(5, dst=B), buff(5, dst=B), cast(day), buff(day))
        self.assertEqual((got["strangers"], got["different"]), (3, 2))

    def test_group(self):
        got = self.of(cast(flags=MATE), buff(flags=MATE), ev("SPELL_RESURRECT", 9, flags=MATE), ev("SPELL_RESURRECT", 10))
        self.assertEqual(got, {"strangers": 0, "different": 0, "revives": 2, "group_buffs": 1})

    def test_window_and_unknown(self):
        a = acts(ev("SPELL_RESURRECT"))
        day = timedelta(days=1)
        self.assertEqual([figures(a, lo, hi)["revives"] for lo, hi in ((T0 - day, T0), (T0, T0 + day))], [1, 0])
        self.assertIsNone(figures([], T0 - day, T0))
        self.assertIsNone(figures(None, T0 - day, T0))


class Kept(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.paths = SimpleNamespace(data_dir=Path(tmp.name))

    def test_live_then_replay(self):
        h = History(self.paths)
        got = acts(cast(), buff(), ev("SPELL_RESURRECT", 5))
        h.add_acts(got)
        h.add_acts(got)
        again = History(self.paths)
        again.add_acts(got)
        self.assertEqual(h.help_file.read_text(encoding="utf-8").count("\n"), 2)
        self.assertEqual((again.helped(ME), again.helped(B)), (got, []))

    def test_a_broken_line(self):
        h = History(self.paths)
        h.add_acts(acts(ev("SPELL_RESURRECT")))
        with open(h.help_file, "a", encoding="utf-8") as fh:
            fh.write('[1]\n{"no": "id"}\n{"half')
        self.assertEqual(len(History(self.paths).acts), 1)

    def test_tracker_outside_fights(self):
        tr = Tracker()
        tr.feed(cast())
        tr.feed(buff(.1))
        self.assertIsNone(tr.fight)
        self.assertEqual([a["kind"] for a in tr.take_acts()], ["buff"])
        self.assertEqual(tr.take_acts(), [])


class Trait(unittest.TestCase):
    def given(self, strangers, revives=0, **kw):
        return {"main_role": "damage", "helping": {"strangers": strangers, "different": strangers, "revives": revives,
                                                   "group_buffs": 0} | kw}

    def test_score(self):
        self.assertEqual(raw([], self.given(36, 14))["Benefactor"], [(50, 50)])
        self.assertEqual(raw([], {})["Benefactor"], [(None, 0)])
        at = lambda n: scores([], self.given(n))["Benefactor"]  # noqa: E731
        self.assertIsNone(at(4))                                                # nothing to give: no score, not a low one
        self.assertEqual([at(n)["tier"] for n in (5, 39, 62, 86)], [0, 1, 2, 3])
        self.assertIsNone(scores([], self.given(0))["Benefactor"])

    def test_deeds(self):
        self.assertEqual(titles.deeds([], self.given(40, 14)), ["14 revives cast on the fallen", "40 different strangers helped"])
        self.assertEqual(titles.deeds([], self.given(3, 1)), [])
        self.assertEqual(titles.deeds([], {}), [])

    def test_page_row(self):
        start = datetime(2026, 11, 22, 12)
        fights = [{"me": ME, "me_name": "Me", "start": (start + timedelta(minutes=i)).isoformat(), "duration": 30,
                   "kind": "World", "result": "killed"} for i in range(12)]
        got = [a for i in range(6) for a in acts(cast(i, dst=f"{A}{i}"), buff(i, dst=f"{A}{i}"))]
        now = datetime(2026, 11, 24)
        v = build_profile(profile(fights, None, {}, [], now, None, got), [])
        row = next(r for _, rows in v.traits for r in rows if r.key == "Benefactor")
        self.assertEqual((row.name, row.value, row.next, row.ink),
                         ("Benefactor", "6", "6 strangers helped, 0 revives cast, 0 buffs for your group. "
                          "Kind at 39, you are at 6", "role-heal"))
        self.assertNotIn("Benefactor", [r.key for _, rows in build_profile(profile(fights, None, {}, [], now), []).traits
                                        for r in rows])


if __name__ == "__main__":
    unittest.main()
