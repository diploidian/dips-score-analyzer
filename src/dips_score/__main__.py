"""dips-score

    python -m dips_score              the window (follows new runs as the game saves them)
    python -m dips_score runs         list the saved runs
    python -m dips_score report [N]   scorecard for run N (default: the latest) in the terminal
"""
from __future__ import annotations

import argparse
import sys

from . import analysis, removed
from .config import paths as get_paths
from .scoring.classes import load_upkeep
from .scoring.score import ROLES, load_weights


def _fmt_time(s: float) -> str:
    s = int(s)
    return f"{s // 60}:{s % 60:02d}"


def cmd_runs(p) -> int:
    saved, runs = analysis.load_saved(p)
    if not runs:
        print("No dips-Score runs found under", p.accounts)
        return 1
    print(f"{saved}\n")
    for i, r in enumerate(runs, 1):
        print(f"{i:3}  {r.start_time:%Y-%m-%d %H:%M}  {r.zone:<28} {r.kind:<8} "
              f"{len(r.segments)} seg  {r.line_count:6} lines")
    return 0


def _fight_detail(fr, role: str) -> str:
    if role == "healer":
        h = fr.healer
        resp = f"{h.median_response:.1f}s" if h.median_response is not None else "-"
        dead = f"  {len(h.deaths)} died" if h.deaths else ""
        return f"response {resp}, {len(h.judged)} dips, {h.missed} missed{dead}"
    if role == "tank" and fr.tank:
        t = fr.tank
        pick = f"{t.median_pickup:.1f}s" if t.median_pickup is not None else "-"
        return f"pickup {pick}, {len(t.judged)} lost, {t.missed} missed"
    out = f"busy {fr.metrics.uptime:.0%}"
    if fr.damage:
        out += f", damage {fr.damage[1]:.0%} of even"
    if fr.interrupts and fr.interrupts.used and fr.interrupts.judged:
        j = fr.interrupts.judged
        out += f", interrupted {len(j) - fr.interrupts.missed}/{len(j)}"
    if fr.cooldowns and fr.cooldowns.lost_share:
        out += f", cooldowns lost {fr.cooldowns.lost_share:.0%}"
    return out


def cmd_report(p, n: int | None, role: str) -> int:
    _, runs = analysis.load_saved(p)
    if not runs:
        print("No dips-Score runs found under", p.accounts)
        return 1
    run = runs[(n or len(runs)) - 1]
    a = analysis.analyze(run, p, role)
    rd, m, card = a.data, a.metrics, a.card
    print(f"\n{run.zone}  -  {run.start_time:%Y-%m-%d %H:%M}  -  {_fmt_time(rd.duration)} long, "
          f"{_fmt_time(m.combat_time)} in combat over {len(rd.fights)} fights")
    if not rd.has_combat_log:
        print("  (no combat log covers this run: damage, healing and health aren't known)")
    elif not rd.has_advanced:
        print("  (advanced logging was off: health and mana aren't known)")
    for i, s in enumerate(rd.sync, 1):
        print(f"  sync, segment {i}: {s.describe()}")
    if card.empty:
        print(f"\n  Not scored: {card.note}.\n")
        return 0
    print(f"\n  SCORE  {card.total:.0f}  ({card.grade})  as {card.role}\n")
    for c in card.categories:
        bar = "#" * round(c.score / 10) + "." * (10 - round(c.score / 10))
        weight = "info" if c.info_only else f"x{c.weight:g}"
        print(f"  {c.name:<12} {weight:>4} {bar} {'-' if c.unavailable else f'{c.score:3.0f}':>3}   {c.summary}")
    if card.bonus:
        print(f"  {'Hybrid bonus':<12}      +{card.bonus:.1f}          {card.bonus_note}")
    if m.has_log:
        print(f"\n  output: {m.damage:,} damage ({m.dps:.0f}/s), {m.healing:,} healing ({m.hps:.0f}/s, "
              f"{m.overheal_share:.0%} overheal incl. passive), {m.kills} killing blows, {m.damage_taken:,} damage taken")
    if m.median_first_press is not None:
        print(f"  first press after a pull: median {m.median_first_press:.2f}s")
    if card.tips:
        print("\n  work on:")
        for t in card.tips:
            print("   -", t)
    print("\n  fights:")
    for fr in a.fights:
        f = fr.fight
        kill = "" if f.killed is None else (" (killed)" if f.killed else " (wipe)")
        print(f"   {_fmt_time(f.start):>6}  {f.label + kill:<32} {f.duration:5.0f}s  score {fr.card.total:3.0f} "
              f"({fr.card.grade})  " + _fight_detail(fr, a.role))
    print()
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dips-score", description="Scores dungeon runs recorded by dips-Score.")
    ap.add_argument("--wow", help="the WoW folder with WTF and Logs in it (default: the _forever_ install)")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("runs", help="list saved runs")
    rp = sub.add_parser("report", help="print a run's scorecard")
    rp.add_argument("n", nargs="?", type=int, help="run number from `runs` (default: latest)")
    rp.add_argument("--role", choices=list(ROLES), default=None,
                    help="what to judge you as (default: your role in the group, else healer)")
    sub.add_parser("gui", help="open the window (default)")
    sub.add_parser("live", help="just the after-fight overlay, from the system tray")
    sub.add_parser("replay", help="sum up the fights in your old combat logs (for the Fights page)")
    args = ap.parse_args(argv)
    p = get_paths(args.wow)
    load_weights(p.weights_file)
    load_upkeep(p.classes_file)
    removed.load(p.removed_file)      # runs, report and replay skip what you deleted, as the window does
    if args.cmd == "runs":
        return cmd_runs(p)
    if args.cmd == "report":
        return cmd_report(p, args.n, args.role)
    if args.cmd == "replay":
        from .live.history import replay
        from .sources import combatlog
        added, again = replay(p, combatlog.find_logs(p.logs))
        print(f"Added {added} fights, refreshed {again}.")
        return 0
    if args.cmd == "live":
        from .ui.live_ui import run_tray
        return run_tray(p)
    from .ui.app import run_app
    return run_app(p)


if __name__ == "__main__":
    sys.exit(main())
