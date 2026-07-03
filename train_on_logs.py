"""
train_on_logs.py  —  Fine-tune the RL agent on weekly game data.

Accepts ALL games (wins, losses, ties). Wins are weighted 3× in the
behavioral cloning loss so the model learns more strongly from what
worked. New question types (perfect_cube, harshad, product_digits, etc.)
are flagged in a separate report — these need a vocabulary expansion
before the model can act on them directly.

Usage (from gameapp/ folder)
------------------------------
    py -3.11 train_on_logs.py numdle_week_2026-06-29.json
    py -3.11 train_on_logs.py week1.json week2.json       # multiple weeks at once
    py -3.11 train_on_logs.py week.json --epochs 30 --wins-only

After training:
    py -3.11 precompute.py --next-week    # re-compute next week's AI scores
    # commit public/daily_data.json and push
"""

import os, sys, json, glob, argparse
from collections import Counter, defaultdict
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'number_guessing_rl'))

from environment.game_env import NumberGuessingEnv
from agent.rl_agent import RLAgent
import tensorflow as tf

NUMBER_RANGE  = (1, 1000)
MAX_QUESTIONS = 7
WIN_WEIGHT    = 3.0   # winning sessions count this many times in the loss


def parse_args():
    p = argparse.ArgumentParser(description='Train RL agent on weekly Numdle logs.')
    p.add_argument('logs',        nargs='+', help='JSON log files exported from the browser.')
    p.add_argument('--epochs',    type=int,  default=20,    help='BC training epochs (default 20)')
    p.add_argument('--batch',     type=int,  default=32,    help='Batch size (default 32)')
    p.add_argument('--wins-only', action='store_true',      help='Only train on sessions where human won')
    p.add_argument('--out',       type=str,  default=None,  help='Output weights path')
    p.add_argument('--report',    action='store_true',      help='Print question-type analysis and exit')
    return p.parse_args()


# ── Load & validate logs ───────────────────────────────────────────────────────
def load_logs(files, wins_only=False):
    sessions = []
    for path in files:
        with open(path) as f:
            raw = json.load(f)
        # accept {week_start, games:[...]} or a bare list
        if isinstance(raw, dict) and 'games' in raw:
            games = raw['games']
            print(f"  {path}: week {raw.get('week_start','?')} — {len(games)} games "
                  f"({raw.get('wins',0)}W/{raw.get('losses',0)}L/{raw.get('ties',0)}T)")
        elif isinstance(raw, list):
            games = raw
            print(f"  {path}: {len(games)} entries (raw list)")
        else:
            games = [raw]

        if wins_only:
            games = [g for g in games if g.get('outcome') == 'human_wins']
        sessions.extend(games)

    print(f"\nTotal sessions: {len(sessions)}")
    wins   = sum(1 for s in sessions if s.get('outcome')=='human_wins')
    losses = sum(1 for s in sessions if s.get('outcome')=='ai_wins')
    ties   = sum(1 for s in sessions if s.get('outcome')=='tie')
    print(f"  Human wins: {wins}   AI wins: {losses}   Ties: {ties}")
    return sessions


# ── Question-type analysis ─────────────────────────────────────────────────────
def analyse_questions(sessions):
    type_counts   = Counter()
    new_types     = Counter()
    win_types     = Counter()
    unknown_texts = []

    for s in sessions:
        is_win = s.get('outcome') == 'human_wins'
        for q in s.get('questions', []):
            qtype = q.get('type') or (q.get('parsed') or {}).get('type','?')
            vocab  = q.get('vocab_action', -1)
            type_counts[qtype] += 1
            if vocab == -1:
                new_types[qtype] += 1
                unknown_texts.append(q.get('text',''))
            if is_win:
                win_types[qtype] += 1

    print("\n── Question-type breakdown ──────────────────────────────")
    print(f"  {'Type':<20} {'Asked':>6}  {'New':>5}  {'In wins':>7}")
    for t, cnt in type_counts.most_common():
        print(f"  {t:<20} {cnt:>6}  {new_types.get(t,0):>5}  {win_types.get(t,0):>7}")

    if new_types:
        print(f"\n  ✦ NEW QUESTION TYPES (not in AI vocabulary — need future retraining):")
        for t, c in new_types.most_common():
            print(f"    {t}: {c} uses")
        print()
    return new_types


# ── Build weighted training pairs ─────────────────────────────────────────────
def build_pairs(sessions, env):
    pairs   = []  # (state_array, action_id, weight)
    skipped = 0

    for session in sessions:
        secret    = session.get('secret')
        outcome   = session.get('outcome', 'ai_wins')
        weight    = WIN_WEIGHT if outcome == 'human_wins' else 1.0
        questions = session.get('questions', [])

        if secret is None:
            skipped += 1
            continue

        env.reset()
        env.secret_number        = secret
        env.remaining_candidates = list(range(NUMBER_RANGE[0], NUMBER_RANGE[1]+1))

        for q_entry in questions:
            action = q_entry.get('vocab_action', -1)
            if action < 0 or action >= env.question_space.size():
                # skip new question types — they have no vocab action yet
                # but we still need to advance the env state
                # We'll use parity (action 56) as a neutral filler step
                try: env.step(56)
                except Exception: pass
                skipped += 1
                continue

            state = env.get_state().copy()
            pairs.append((state, int(action), weight))

            try:
                env.step(int(action))
            except Exception:
                break

    print(f"\nBuilt {len(pairs)} training pairs  ({skipped} skipped — new types or missing data)")
    return pairs


# ── Behavioral cloning with sample weights ────────────────────────────────────
def behavioral_cloning(agent, pairs, epochs=20, batch_size=32):
    if not pairs:
        print("No usable training pairs — nothing to train on.")
        return

    states  = np.array([p[0] for p in pairs], dtype=np.float32)
    actions = np.array([p[1] for p in pairs], dtype=np.int32)
    weights = np.array([p[2] for p in pairs], dtype=np.float32)
    weights /= weights.mean()   # normalise so average weight = 1

    targets = np.zeros((len(pairs), agent.action_size), dtype=np.float32)
    for i, a in enumerate(actions):
        targets[i, a] = 1.0

    model = agent.model
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
        loss='categorical_crossentropy',
        metrics=['accuracy'],
        weighted_metrics=['accuracy'],
    )

    print(f"\nBehavioral cloning: {len(pairs)} pairs  epochs={epochs}  batch={batch_size}")
    print(f"  Win-session weight={WIN_WEIGHT}×  loss-session weight=1×")
    model.fit(states, targets, sample_weight=weights,
              epochs=epochs, batch_size=batch_size, verbose=1, shuffle=True)

    agent.update_target_network()

    # Restore MSE compile for future RL training
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=agent.lr, clipnorm=1.0),
        loss='mse',
    )


# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    args = parse_args()

    print("Loading logs…")
    sessions = load_logs(args.logs, wins_only=args.wins_only)
    if not sessions:
        print("No sessions found. Check the JSON files."); sys.exit(1)

    new_types = analyse_questions(sessions)
    if args.report:
        print("(--report mode: analysis only, no training)")
        return

    # ── Set up agent ──────────────────────────────────────────────────────────
    env = NumberGuessingEnv(number_range=NUMBER_RANGE, max_questions=MAX_QUESTIONS)

    checkpoint_dir = os.path.join('..', 'number_guessing_rl', 'checkpoints_7q')
    checkpoints    = glob.glob(os.path.join(checkpoint_dir, '*.weights.h5'))

    agent = RLAgent(state_size=26, action_size=env.question_space.size(), epsilon=0.0)

    fine_tuned = os.path.join(checkpoint_dir, 'human_finetuned.weights.h5')
    if os.path.exists(fine_tuned):
        agent.load(fine_tuned)
        print(f"\nBase weights: {fine_tuned} (previously fine-tuned)")
    elif checkpoints:
        latest = max(checkpoints, key=os.path.getmtime)
        agent.load(latest)
        print(f"\nBase weights: {latest}")
    else:
        print("\nWARNING: no existing checkpoint — training from scratch.")

    # ── Train ─────────────────────────────────────────────────────────────────
    pairs = build_pairs(sessions, env)
    behavioral_cloning(agent, pairs, epochs=args.epochs, batch_size=args.batch)

    # ── Save ──────────────────────────────────────────────────────────────────
    os.makedirs(checkpoint_dir, exist_ok=True)
    out_path = args.out or fine_tuned
    agent.save(out_path)

    print(f"\n✓ Saved fine-tuned weights → {out_path}")

    if new_types:
        print(f"\n  NOTE — {sum(new_types.values())} questions used NEW types "
              f"({', '.join(new_types.keys())}) that the current vocabulary doesn't cover.")
        print("  To include these, expand NumberGuessingEnv.question_space and retrain from scratch.")

    print("\nNext steps:")
    print("  py -3.11 precompute.py --next-week    ← update next week's AI scores")
    print("  commit + push public/daily_data.json  ← live on the site")


if __name__ == '__main__':
    main()
