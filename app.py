"""
app.py — Numdle server with auth, leaderboard, and stats tracking.
"""
import json, os, sqlite3, hashlib, secrets
from datetime import date, timedelta, datetime
from flask import Flask, send_from_directory, jsonify, request, abort

app = Flask(__name__)

@app.after_request
def add_cors(response):
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, X-Auth-Token'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    return response

@app.route('/api/<path:path>', methods=['OPTIONS'])
def options_handler(path):
    return '', 204
PUBLIC  = os.path.join(os.path.dirname(__file__), 'public')
LOG_DIR      = os.path.join(os.path.dirname(__file__), 'logs')
WINS_DIR     = os.path.join(LOG_DIR, 'player_wins')
DB_PATH      = os.path.join(os.path.dirname(__file__), 'numdle.db')
os.makedirs(LOG_DIR,  exist_ok=True)
os.makedirs(WINS_DIR, exist_ok=True)

# ── Database ───────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    with get_db() as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                created_at    TEXT    NOT NULL,
                last_login    TEXT
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token      TEXT    PRIMARY KEY,
                user_id    INTEGER NOT NULL REFERENCES users(id),
                expires_at TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS game_records (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id          INTEGER REFERENCES users(id),
                date             TEXT    NOT NULL,
                outcome          TEXT    NOT NULL,
                human_distance   INTEGER,
                ai_distance      INTEGER,
                optimal_distance INTEGER,
                questions_asked  INTEGER,
                has_unique_qs    INTEGER DEFAULT 0,
                played_at        TEXT    NOT NULL
            );
        ''')
        # Safe column migration for existing DBs
        cols = [r[1] for r in db.execute("PRAGMA table_info(game_records)").fetchall()]
        if 'optimal_distance' not in cols:
            db.execute("ALTER TABLE game_records ADD COLUMN optimal_distance INTEGER")

init_db()

# ── Auth helpers ───────────────────────────────────────────────────────────────

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def make_token(user_id):
    token   = secrets.token_hex(32)
    expires = (datetime.utcnow() + timedelta(days=36500)).isoformat()  # ~100 years
    with get_db() as db:
        db.execute('INSERT INTO sessions (token,user_id,expires_at) VALUES (?,?,?)',
                   (token, user_id, expires))
    return token

def auth_user(token=None):
    """Validate token, return user dict or None. Sessions never expire."""
    if not token:
        token = request.headers.get('X-Auth-Token') or request.args.get('token')
    if not token:
        return None
    now = datetime.utcnow().isoformat()
    with get_db() as db:
        row = db.execute(
            'SELECT u.id, u.username FROM sessions s '
            'JOIN users u ON s.user_id=u.id '
            'WHERE s.token=? AND s.expires_at>?', (token, now)
        ).fetchone()
    if not row:
        return None
    return dict(row)

def is_suspicious(user_id):
    """True if user won with <5 questions four times in a row (cheating heuristic)."""
    with get_db() as db:
        rows = db.execute(
            'SELECT outcome, questions_asked FROM game_records '
            'WHERE user_id=? ORDER BY played_at DESC LIMIT 4', (user_id,)
        ).fetchall()
    if len(rows) < 4:
        return False
    return all(r['outcome'] == 'human_wins' and r['questions_asked'] < 5 for r in rows)

# ── Static files ───────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(PUBLIC, 'index.html')

@app.route('/<path:path>')
def serve_static(path):
    resp = send_from_directory(PUBLIC, path)
    if path.endswith(('.js', '.css')):
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
        resp.headers['Pragma']        = 'no-cache'
    return resp

# ── Auth endpoints ─────────────────────────────────────────────────────────────

@app.route('/api/signup', methods=['POST'])
def signup():
    d        = request.get_json(force=True, silent=True) or {}
    username = (d.get('username') or '').strip()
    password = (d.get('password') or '').strip()

    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if len(username) < 2 or len(username) > 20:
        return jsonify({'error': 'Username must be 2–20 characters'}), 400
    if not username.replace('_','').replace('-','').isalnum():
        return jsonify({'error': 'Only letters, numbers, - and _ allowed'}), 400
    if len(password) < 4:
        return jsonify({'error': 'Password must be at least 4 characters'}), 400

    now = datetime.utcnow().isoformat()
    try:
        with get_db() as db:
            db.execute(
                'INSERT INTO users (username,password_hash,created_at,last_login) VALUES (?,?,?,?)',
                (username, hash_pw(password), now, now)
            )
            user_id = db.execute('SELECT id FROM users WHERE username=?', (username,)).fetchone()['id']
    except sqlite3.IntegrityError:
        return jsonify({'error': 'That username is already taken'}), 409

    resp = jsonify({'ok': True, 'token': make_token(user_id), 'username': username})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/login', methods=['POST'])
def login():
    d        = request.get_json(force=True, silent=True) or {}
    username = (d.get('username') or '').strip()
    password = (d.get('password') or '').strip()

    with get_db() as db:
        user = db.execute(
            'SELECT id, username FROM users WHERE username=? AND password_hash=?',
            (username, hash_pw(password))
        ).fetchone()

    if not user:
        return jsonify({'error': 'Incorrect username or password'}), 401

    with get_db() as db:
        db.execute('UPDATE users SET last_login=? WHERE id=?',
                   (datetime.utcnow().isoformat(), user['id']))

    resp = jsonify({'ok': True, 'token': make_token(user['id']), 'username': user['username']})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


@app.route('/api/me')
def me_route():
    user = auth_user()
    if not user:
        return jsonify({'logged_in': False})
    return jsonify({'logged_in': True, **user})


@app.route('/api/logout', methods=['POST'])
def logout():
    d     = request.get_json(force=True, silent=True) or {}
    token = request.headers.get('X-Auth-Token') or request.args.get('token') or d.get('token')
    if token:
        with get_db() as db:
            db.execute('DELETE FROM sessions WHERE token=?', (token,))
    return jsonify({'ok': True})


@app.route('/api/change-password', methods=['POST'])
def change_password():
    user = auth_user()
    if not user:
        resp = jsonify({'error': 'Not logged in'}); resp.headers['Access-Control-Allow-Origin']='*'; return resp, 401
    d        = request.get_json(force=True, silent=True) or {}
    old_pw   = (d.get('old_password') or '').strip()
    new_pw   = (d.get('new_password') or '').strip()
    if not old_pw or not new_pw:
        resp = jsonify({'error': 'Fill in both fields'}); resp.headers['Access-Control-Allow-Origin']='*'; return resp, 400
    if len(new_pw) < 4:
        resp = jsonify({'error': 'New password must be at least 4 characters'}); resp.headers['Access-Control-Allow-Origin']='*'; return resp, 400
    with get_db() as db:
        row = db.execute('SELECT id FROM users WHERE id=? AND password_hash=?',
                         (user['id'], hash_pw(old_pw))).fetchone()
    if not row:
        resp = jsonify({'error': 'Current password is incorrect'}); resp.headers['Access-Control-Allow-Origin']='*'; return resp, 401
    with get_db() as db:
        db.execute('UPDATE users SET password_hash=? WHERE id=?', (hash_pw(new_pw), user['id']))
    resp = jsonify({'ok': True})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp


# ── Leaderboard ────────────────────────────────────────────────────────────────

def calculate_streak(user_id):
    """Count consecutive daily wins/ties ending today or yesterday."""
    with get_db() as db:
        rows = db.execute(
            'SELECT date, outcome FROM game_records WHERE user_id=? ORDER BY date DESC',
            (user_id,)
        ).fetchall()
    if not rows:
        return 0
    today     = date.today()
    yesterday = today - timedelta(days=1)
    most_recent = date.fromisoformat(rows[0]['date'])
    if most_recent < yesterday:
        return 0  # last game too old — streak broken
    streak   = 0
    expected = most_recent
    for row in rows:
        d = date.fromisoformat(row['date'])
        if d > expected:
            continue  # duplicate
        if d < expected:
            break     # gap in days
        if row['outcome'] in ('human_wins', 'tie'):
            streak  += 1
            expected = d - timedelta(days=1)
        else:
            break
    return streak


@app.route('/api/leaderboard')
def leaderboard():
    me_user = auth_user()

    with get_db() as db:
        rows = db.execute('''
            SELECT u.id, u.username,
                   COUNT(g.id) AS total_games,
                   SUM(CASE WHEN g.outcome='human_wins' THEN 1 ELSE 0 END) AS wins,
                   SUM(CASE WHEN g.outcome='ai_wins'    THEN 1 ELSE 0 END) AS losses,
                   SUM(CASE WHEN g.outcome='tie'        THEN 1 ELSE 0 END) AS ties,
                   ROUND(AVG(g.human_distance), 0) AS avg_human_distance
            FROM users u
            JOIN game_records g ON u.id=g.user_id
            GROUP BY u.id
            HAVING total_games >= 1
            ORDER BY wins * 1.0 / total_games DESC, total_games DESC
        ''').fetchall()

    # AI entry — stats from logs/ai_game_log.json (written by precompute.py, one entry per day)
    ai_log_path = os.path.join(LOG_DIR, 'ai_game_log.json')
    ai_n = ai_exact = ai_total_dist = 0
    today_iso = date.today().isoformat()
    if os.path.exists(ai_log_path):
        with open(ai_log_path, encoding='utf-8-sig') as f:
            ai_log = json.load(f)
        for iso, v in ai_log.items():
            if iso > today_iso:
                continue  # only count days that have passed
            ai_n += 1
            d = v.get('ai_distance', 0)
            ai_total_dist += d
            if d == 0:
                ai_exact += 1
    ai_avg_dist = round(ai_total_dist / ai_n, 1) if ai_n else 0
    ai_entry = {
        'id': None, 'username': 'AI Bot', 'is_ai': True,
        'total_games': ai_n,
        'wins': ai_exact,
        'losses': ai_n - ai_exact,
        'ties': 0,
        'win_rate': round(100.0 * ai_exact / ai_n, 1) if ai_n else 0,
        'avg_distance': ai_avg_dist,
        'optimal_rate': None,
        'streak': 0, 'avg_questions': 7, 'rank': None,
    }

    result   = []
    vis_rank = 1
    me_entry = None

    for row in rows:
        r = dict(row)
        r['win_rate']     = round(100.0 * r['wins'] / r['total_games'], 1) if r['total_games'] else 0
        r['win_rate']     = round(100.0 * r['wins'] / r['total_games'], 1) if r['total_games'] else 0
        r['avg_distance'] = r.get('avg_human_distance')
        r['streak']       = calculate_streak(r['id'])
        r['suspicious']   = is_suspicious(r['id'])
        r['is_me']        = bool(me_user and me_user['id'] == r['id'])
        r['is_ai']        = False

        if r['suspicious']:
            r['rank'] = None
        else:
            r['rank'] = vis_rank
            vis_rank += 1

        result.append(r)
        if r['is_me']:
            me_entry = r

    # If logged in but no game records yet, still return me info
    if me_user and not me_entry:
        me_entry = {
            'id': me_user['id'], 'username': me_user['username'],
            'total_games': 0, 'wins': 0, 'losses': 0, 'ties': 0,
            'win_rate': 0.0, 'avg_distance': None, 'streak': 0,
            'rank': None, 'is_me': True, 'is_ai': False, 'suspicious': False,
        }

    # Insert AI entry at correct rank
    if ai_entry:
        result.append(ai_entry)
        result.sort(key=lambda x: (-(x.get('wins') or 0), (x.get('avg_distance') or 9999)))
        for i, r in enumerate(result):
            if not r.get('suspicious') and not r.get('is_ai'):
                r['rank'] = i + 1
        ai_entry['rank'] = next((i+1 for i, r in enumerate(result) if r.get('is_ai')), None)

    resp = jsonify({'leaderboard': result, 'me': me_entry})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

# ── Game log + stats ───────────────────────────────────────────────────────────

def week_start_of(iso_date):
    d = date.fromisoformat(iso_date)
    return (d - timedelta(days=d.weekday())).isoformat()

def update_success_stats(outcome, human_dist, ai_dist):
    path  = os.path.join(LOG_DIR, 'success_stats.json')
    today = date.today().isoformat()

    if os.path.exists(path):
        with open(path, encoding='utf-8-sig') as f:
            s = json.load(f)
    else:
        s = {
            'total_games': 0, 'human_wins': 0, 'ai_wins': 0, 'ties': 0,
            'human_win_rate': 0.0, 'ai_win_rate': 0.0,
            'avg_human_distance': 0.0, 'avg_ai_distance': 0.0,
            'daily': {}
        }

    s['total_games'] += 1
    key_map = {'human_wins': 'human_wins', 'ai_wins': 'ai_wins', 'tie': 'ties'}
    skey    = key_map.get(outcome, 'ties')
    s[skey] += 1
    n = s['total_games']
    s['human_win_rate'] = round(s['human_wins'] / n, 4)
    s['ai_win_rate']    = round(s['ai_wins']    / n, 4)
    if human_dist is not None:
        s['avg_human_distance'] = round((s['avg_human_distance']*(n-1) + human_dist) / n, 1)
    if ai_dist is not None:
        s['avg_ai_distance']    = round((s['avg_ai_distance']   *(n-1) + ai_dist   ) / n, 1)

    day = s['daily'].setdefault(today, {'games':0,'human_wins':0,'ai_wins':0,'ties':0})
    day['games'] += 1
    day[skey]    += 1

    with open(path, 'w') as f:
        json.dump(s, f, indent=2)


@app.route('/log_game', methods=['POST'])
def log_game():
    data = request.get_json(force=True, silent=True)
    if not data or 'date' not in data:
        return jsonify({'error': 'invalid payload'}), 400

    user = auth_user()
    week = data.get('week') or week_start_of(data['date'])
    path = os.path.join(LOG_DIR, f'week_{week}.json')

    if os.path.exists(path):
        with open(path) as f:
            wf = json.load(f)
    else:
        end = (date.fromisoformat(week) + timedelta(days=6)).isoformat()
        wf  = {'week_start': week, 'week_end': end, 'games': []}

    entry = {**data}
    if user:
        entry['username'] = user['username']
    wf['games'].append(entry)
    games = wf['games']
    wf.update({
        'total':  len(games),
        'wins':   sum(1 for g in games if g.get('outcome')=='human_wins'),
        'losses': sum(1 for g in games if g.get('outcome')=='ai_wins'),
        'ties':   sum(1 for g in games if g.get('outcome')=='tie'),
    })

    with open(path, 'w') as f:
        json.dump(wf, f, indent=2)

    already_played = False
    if user:
        with get_db() as db:
            existing = db.execute(
                'SELECT id FROM game_records WHERE user_id=? AND date=?',
                (user['id'], data['date'])
            ).fetchone()
            if not existing:
                db.execute(
                    'INSERT INTO game_records '
                    '(user_id,date,outcome,human_distance,ai_distance,optimal_distance,'
                    'questions_asked,has_unique_qs,played_at) '
                    'VALUES (?,?,?,?,?,?,?,?,?)',
                    (user['id'], data['date'], data.get('outcome'),
                     data.get('human_distance'), data.get('ai_distance'),
                     data.get('optimal_distance'),
                     data.get('questions_asked', 0),
                     1 if data.get('has_unique_questions') else 0,
                     data.get('played_at', datetime.utcnow().isoformat()))
                )
            else:
                already_played = True

    if not already_played:
        update_success_stats(data.get('outcome'), data.get('human_distance'), data.get('ai_distance'))

        # Save full game to player_wins/ when human beats AI
        if data.get('outcome') == 'human_wins':
            username  = user['username'] if user else 'anon'
            ts        = datetime.utcnow().strftime('%H%M%S')
            win_fname = f"{data['date']}_{username}_{ts}.json"
            win_entry = {
                **data,
                'username':   username,
                'logged_at':  datetime.utcnow().isoformat(),
            }
            with open(os.path.join(WINS_DIR, win_fname), 'w') as f:
                json.dump(win_entry, f, indent=2)

    print(f"[log] {data['date']} outcome={data.get('outcome')} "
          f"h_dist={data.get('human_distance')} ai_dist={data.get('ai_distance')} "
          f"user={user['username'] if user else 'anon'}"
          f"{' (duplicate — ignored)' if already_played else ''}")

    resp = jsonify({'ok': True, 'logged_in': bool(user)})
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

# ── Admin (localhost only) ─────────────────────────────────────────────────────

def local_only():
    if request.remote_addr not in ('127.0.0.1', '::1'):
        abort(403)

@app.route('/admin/logs')
def admin_logs():
    local_only()
    files = sorted(f for f in os.listdir(LOG_DIR)
                   if f.endswith('.json') and f != 'success_stats.json')
    rows = []
    for fname in files:
        with open(os.path.join(LOG_DIR, fname)) as f:
            d = json.load(f)
        rows.append({'file': fname, 'total': d.get('total',0),
                     'wins': d.get('wins',0), 'losses': d.get('losses',0),
                     'ties': d.get('ties',0)})
    html_rows = ''.join(
        f"<tr><td>{r['file']}</td><td>{r['total']}</td><td>{r['wins']}</td>"
        f"<td>{r['losses']}</td><td>{r['ties']}</td>"
        f"<td><a href='/admin/logs/{r['file']}'>↓</a></td></tr>"
        for r in rows)
    return (f"""<!doctype html><html><head><title>Numdle Admin</title>
<style>body{{font-family:monospace;background:#111;color:#eee;padding:20px}}
table{{border-collapse:collapse;width:100%}} th,td{{border:1px solid #333;padding:8px}}
th{{background:#222}} a{{color:#6e6ef0}}</style></head><body>
<h2>Game Logs</h2>
<table><tr><th>File</th><th>Total</th><th>W</th><th>L</th><th>T</th><th>DL</th></tr>
{html_rows}</table>
<p style="margin-top:14px">
  <a href="/admin/stats">Success stats JSON →</a> &nbsp;|&nbsp;
  <a href="/admin/charts">Strategy charts →</a>
</p></body></html>""")


@app.route('/admin/logs/<filename>')
def download_log(filename):
    local_only()
    if not filename.endswith('.json') or '/' in filename or '..' in filename:
        abort(400)
    return send_from_directory(LOG_DIR, filename, as_attachment=True)


@app.route('/admin/stats')
def admin_stats():
    local_only()
    path = os.path.join(LOG_DIR, 'success_stats.json')
    if not os.path.exists(path):
        return jsonify({'message': 'No stats logged yet'})
    with open(path, encoding='utf-8-sig') as f:
        return jsonify(json.load(f))


@app.route('/admin/charts')
def admin_charts():
    local_only()
    # Aggregate question-type usage from all week files
    type_humans, type_ai_q = {}, {}
    daily_win_rates = {}

    for fname in sorted(f for f in os.listdir(LOG_DIR)
                        if f.startswith('week_') and f.endswith('.json')):
        with open(os.path.join(LOG_DIR, fname)) as f:
            wf = json.load(f)
        for game in wf.get('games', []):
            day = game.get('date', '')
            outcome = game.get('outcome', '')
            won = 1 if outcome == 'human_wins' else 0
            if day not in daily_win_rates:
                daily_win_rates[day] = {'wins': 0, 'games': 0}
            daily_win_rates[day]['wins']  += won
            daily_win_rates[day]['games'] += 1
            for q in game.get('questions', []):
                qtype = q.get('type') or (q.get('parsed') or {}).get('type', 'unknown')
                type_humans[qtype] = type_humans.get(qtype, 0) + 1

    stats_path = os.path.join(LOG_DIR, 'success_stats.json')
    global_stats = {}
    if os.path.exists(stats_path):
        with open(stats_path) as f:
            global_stats = json.load(f)

    daily_labels = sorted(daily_win_rates.keys())[-30:]
    daily_rates  = [
        round(100 * daily_win_rates[d]['wins'] / daily_win_rates[d]['games'], 1)
        for d in daily_labels
    ]

    type_labels = sorted(type_humans, key=lambda k: -type_humans[k])[:12]
    type_vals   = [type_humans[k] for k in type_labels]

    return f"""<!doctype html><html><head>
<title>Numdle Strategy Charts</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>body{{background:#111;color:#eee;font-family:sans-serif;padding:20px;max-width:900px;margin:0 auto}}
h2{{color:#6e6ef0;margin-top:30px}} .chart-box{{background:#1c1c1e;border-radius:10px;padding:16px;margin-bottom:24px}}</style>
</head><body>
<h1>Numdle &mdash; Strategy Charts</h1>
<p>Global: {global_stats.get('total_games',0)} games &nbsp;·&nbsp;
Human win rate: {round(global_stats.get('human_win_rate',0)*100,1)}% &nbsp;·&nbsp;
AI win rate: {round(global_stats.get('ai_win_rate',0)*100,1)}%</p>

<h2>Human win rate (last 30 days)</h2>
<div class="chart-box"><canvas id="c1"></canvas></div>

<h2>Question types used by humans</h2>
<div class="chart-box"><canvas id="c2"></canvas></div>

<script>
const labels1 = {json.dumps(daily_labels)};
const vals1   = {json.dumps(daily_rates)};
new Chart(document.getElementById('c1'), {{
  type: 'line',
  data: {{ labels: labels1, datasets: [{{
    label: 'Human win %', data: vals1, borderColor:'#30d158', tension:.3, fill:true,
    backgroundColor:'rgba(48,209,88,.15)'
  }}]}},
  options: {{ plugins:{{legend:{{labels:{{color:'#eee'}}}}}}, scales:{{
    x:{{ticks:{{color:'#888'}},grid:{{color:'#333'}}}},
    y:{{ticks:{{color:'#888'}},grid:{{color:'#333'}},min:0,max:100}}
  }}}}
}});

const labels2 = {json.dumps(type_labels)};
const vals2   = {json.dumps(type_vals)};
new Chart(document.getElementById('c2'), {{
  type: 'bar',
  data: {{ labels: labels2, datasets: [{{
    label: 'Times asked', data: vals2, backgroundColor:'#6e6ef0'
  }}]}},
  options: {{ plugins:{{legend:{{labels:{{color:'#eee'}}}}}}, scales:{{
    x:{{ticks:{{color:'#888'}},grid:{{color:'#333'}}}},
    y:{{ticks:{{color:'#888'}},grid:{{color:'#333'}}}}
  }}}}
}});
</script>
<p style="margin-top:20px"><a href="/admin/logs" style="color:#6e6ef0">← Back to logs</a></p>
</body></html>"""

@app.route('/admin/logs/export')
def export_logs():
    """Export all week log JSON files for model re-training (admin-key protected)."""
    key = request.headers.get('X-Admin-Key') or request.args.get('key')
    if key != os.environ.get('NUMDLE_ADMIN_KEY', 'changeme'):
        abort(403)
    all_games = []
    for fname in sorted(f for f in os.listdir(LOG_DIR)
                        if f.startswith('week_') and f.endswith('.json')):
        with open(os.path.join(LOG_DIR, fname)) as f:
            wf = json.load(f)
        all_games.extend(wf.get('games', []))
    return jsonify({'total': len(all_games), 'games': all_games})


@app.route('/dev/reset-today')
def dev_reset_today():
    """Dev-only: wipe today's DB game record and return JS to clear localStorage."""
    today = date.today().isoformat()
    user  = auth_user()
    deleted = 0
    if user:
        with get_db() as db:
            cur = db.execute(
                'DELETE FROM game_records WHERE user_id=? AND date=?',
                (user['id'], today)
            )
            deleted = cur.rowcount
    storage_key = f'numdle_v2_{today}'
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Dev Reset</title>
<style>body{{font-family:system-ui;display:flex;align-items:center;justify-content:center;
min-height:100vh;margin:0;background:#f9fafb;}}
.box{{background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:32px 40px;
text-align:center;max-width:360px;}}
h2{{margin:0 0 8px;font-size:1.1rem;}}p{{color:#6b7280;font-size:.9rem;margin:0 0 20px;}}
button{{background:#4f46e5;color:#fff;border:none;padding:10px 24px;border-radius:8px;
font-size:.95rem;font-weight:700;cursor:pointer;width:100%;}}
button:hover{{background:#4338ca;}}
.note{{margin-top:12px;font-size:.75rem;color:#9ca3af;}}
</style></head><body>
<div class="box">
  <h2>Dev Reset</h2>
  <p>DB records deleted for today ({today}): <strong>{deleted}</strong><br>
  Click below to also clear your browser game state.</p>
  <button onclick="
    localStorage.removeItem('{storage_key}');
    localStorage.removeItem('numdle_v2_all_games');
    window.location='/';
  ">Clear &amp; Go Play</button>
  <p class="note">This page only works in development.</p>
</div>
</body></html>"""
    return html


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    print("=" * 55)
    print("  Numdle  ->  http://localhost:5050")
    print(f"  Logs    ->  {LOG_DIR}")
    print(f"  Admin   ->  http://localhost:5050/admin/logs")
    print(f"  Charts  ->  http://localhost:5050/admin/charts")
    print("=" * 55)
    app.run(host='0.0.0.0', port=5050, debug=False)
