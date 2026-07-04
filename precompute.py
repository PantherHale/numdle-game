"""
precompute.py  —  Generate public/daily_data.json with the AI's pre-computed guesses.

Run this ONCE locally, commit the JSON, and Vercel serves it statically.
After training on new human data, re-run this to update the AI's scores.

Usage
-----
    py -3.11 precompute.py                  # full range 2025-01-01 → 2028-12-31
    py -3.11 precompute.py --week           # current Mon–Sun only (fast, for weekly updates)
    py -3.11 precompute.py --next-week      # next Mon–Sun (run on Sunday after training)
    py -3.11 precompute.py --start 2026-07-01 --end 2026-12-31   # custom range

After training on winner logs:
    py -3.11 train_on_logs.py week_2026-06-29.json
    py -3.11 precompute.py --week           # re-run for next week with improved AI
"""

import os, sys, json, random, glob, argparse
from datetime import date, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'number_guessing_rl'))

from environment.game_env import NumberGuessingEnv
from agent.rl_agent import RLAgent

NUMBER_RANGE  = (1, 1000)
MAX_QUESTIONS = 7


def get_monday(ref: date) -> date:
    dow = ref.weekday()   # Mon=0 … Sun=6
    return ref - timedelta(days=dow)


def parse_args():
    p = argparse.ArgumentParser(description="Pre-compute AI guesses for Numdle.")
    g = p.add_mutually_exclusive_group()
    g.add_argument('--week',      action='store_true', help='Current Mon–Sun')
    g.add_argument('--next-week', action='store_true', help='Next Mon–Sun (use --weeks N for more)')
    p.add_argument('--weeks', type=int, default=1,    help='Weeks to cover in --next-week mode (default 1)')
    p.add_argument('--start', type=str, default='2025-01-01', help='Start date (YYYY-MM-DD)')
    p.add_argument('--end',   type=str, default='2028-12-31', help='End date (YYYY-MM-DD)')
    return p.parse_args()


def load_agent():
    _here = os.path.dirname(os.path.abspath(__file__))
    checkpoint_dir = os.path.join(_here, 'checkpoints_7q')
    if not os.path.isdir(checkpoint_dir):
        checkpoint_dir = os.path.join(_here, '..', 'number_guessing_rl', 'checkpoints_7q')
    checkpoints    = glob.glob(os.path.join(checkpoint_dir, '*.weights.h5'))

    env   = NumberGuessingEnv(number_range=NUMBER_RANGE, max_questions=MAX_QUESTIONS)
    agent = RLAgent(state_size=26, action_size=env.question_space.size(), epsilon=0.0)

    # Priority: human fine-tuned > best known checkpoint (ep40000) > latest
    fine_tuned = os.path.join(checkpoint_dir, 'human_finetuned.weights.h5')
    best_known = os.path.join(checkpoint_dir, 'ep40000.weights.h5')
    if os.path.exists(fine_tuned):
        agent.load(fine_tuned)
        print(f"Loaded fine-tuned weights: {fine_tuned}")
    elif os.path.exists(best_known):
        agent.load(best_known)
        print(f"Loaded best checkpoint: {best_known}")
    elif checkpoints:
        latest = max(checkpoints, key=os.path.getmtime)
        agent.load(latest)
        print(f"Loaded checkpoint: {latest}")
    else:
        print("WARNING: no checkpoint found — AI will behave randomly.")

    return env, agent


def run_ai(env, agent, secret):
    state = env.reset()
    env.secret_number        = secret
    env.remaining_candidates = list(range(NUMBER_RANGE[0], NUMBER_RANGE[1]+1))
    state = env.get_state()

    questions, done, info = [], False, {}
    while not done:
        action = agent.select_action(state, forbidden=env.get_forbidden_actions())
        q      = env.question_space.decode_action(action)
        ans    = env.answer_question(q)
        questions.append({'question': env.question_space.describe(action), 'answer': str(ans)})
        state, _, done, info = env.step(action)

    guess = info['guess']
    return {'guess': guess, 'distance': abs(guess - secret), 'questions': questions}


def compute_range(env, agent, start: date, end: date, existing: dict) -> dict:
    data    = dict(existing)
    current = start
    total   = (end - start).days + 1
    done    = 0

    print(f"Computing {total} days ({start} to {end})...")

    while current <= end:
        iso    = current.isoformat()
        rng    = random.Random(current.toordinal())
        secret = rng.randint(*NUMBER_RANGE)

        ai = run_ai(env, agent, secret)
        data[iso] = {'s': secret, 'ag': ai['guess'], 'ad': ai['distance'], 'aq': ai['questions']}

        done += 1
        if done % 50 == 0 or current == end:
            print(f"  {done}/{total}  {iso}  secret={secret}  ai_guess={ai['guess']}  off_by={ai['distance']}")

        current += timedelta(days=1)

    return data


def weekly_summary(data: dict, week_dates: list[str]) -> dict:
    """Build a brief summary dict for one week — shown in the site's weekly board."""
    days = []
    for iso in week_dates:
        entry = data.get(iso)
        days.append({
            'date':        iso,
            'secret':      entry['s']  if entry else None,
            'ai_guess':    entry['ag'] if entry else None,
            'ai_distance': entry['ad'] if entry else None,
        })
    return {'week_start': week_dates[0], 'week_end': week_dates[-1], 'days': days}


def main():
    args = parse_args()

    today = date.today()
    if args.week:
        monday = get_monday(today)
        start  = monday
        end    = monday + timedelta(days=20)   # current week + 2 weeks buffer
        print(f"Mode: current week + 2-week buffer  ({start} – {end})")
    elif args.next_week:
        monday = get_monday(today) + timedelta(days=7)
        start  = monday
        end    = monday + timedelta(days=7 * args.weeks - 1)
        print(f"Mode: next {args.weeks} week(s)  ({start} – {end})")
    else:
        start = date.fromisoformat(args.start)
        end   = date.fromisoformat(args.end)
        print(f"Mode: full range  ({start} – {end})")

    os.makedirs('public', exist_ok=True)
    out_path = os.path.join('public', 'daily_data.json')

    # Load existing data so we don't lose previously computed days
    existing = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing days from {out_path}")

    env, agent = load_agent()
    data = compute_range(env, agent, start, end, existing)

    # Embed weekly summaries for the next 8 weeks (used optionally by the site)
    summaries = {}
    probe = get_monday(today)
    for _ in range(8):
        wdates = [(probe + timedelta(days=i)).isoformat() for i in range(7)]
        summaries[wdates[0]] = weekly_summary(data, wdates)
        probe += timedelta(days=7)
    data['__weekly_summaries__'] = summaries

    with open(out_path, 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    kb = os.path.getsize(out_path) / 1024
    print(f"\nDone. Wrote {len(data)-1} days + weekly summaries to {out_path}  ({kb:.0f} KB)")

    # Write AI game log to logs/ so PythonAnywhere leaderboard can read it
    log_dir  = 'logs'
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, 'ai_game_log.json')
    existing_log = {}
    if os.path.exists(log_path):
        with open(log_path, encoding='utf-8') as f:
            existing_log = json.load(f)
    for iso, v in data.items():
        if iso.startswith('__') or not isinstance(v, dict) or 'ad' not in v:
            continue
        existing_log[iso] = {
            'secret':      v['s'],
            'ai_guess':    v['ag'],
            'ai_distance': v['ad'],
        }
    with open(log_path, 'w', encoding='utf-8') as f:
        json.dump(existing_log, f, indent=2, sort_keys=True)
    print(f"AI game log updated: {log_path}  ({len(existing_log)} days total)")

    # Print this week's AI performance preview
    print("\n--- This week's AI preview ---")
    monday = get_monday(today)
    for i in range(7):
        d   = (monday + timedelta(days=i)).isoformat()
        e   = data.get(d)
        tag = ' ◀ today' if d == today.isoformat() else ''
        if e:
            print(f"  {d}  secret={e['s']:<5} ai_guess={e['ag']:<5} off_by={e['ad']}{tag}")
        else:
            print(f"  {d}  (no data){tag}")
    print()
    print("Next: commit public/daily_data.json and push to your host.")


if __name__ == '__main__':
    main()
