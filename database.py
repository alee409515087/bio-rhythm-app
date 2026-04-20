import sqlite3

DATABASE = 'bio_rhythm.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS branches (
            branch_id   INTEGER PRIMARY KEY,
            branch_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS teams (
            team_id     INTEGER PRIMARY KEY,
            team_name   TEXT NOT NULL,
            branch_id   INTEGER REFERENCES branches(branch_id)
        );

        CREATE TABLE IF NOT EXISTS agent_profiles (
            agent_id                INTEGER PRIMARY KEY,
            agent_name              TEXT NOT NULL,
            branch_id               INTEGER REFERENCES branches(branch_id),
            team_id                 INTEGER REFERENCES teams(team_id),
            calculated_peak_hour    INTEGER,
            calculated_peak_day     INTEGER,
            total_modules_completed INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS module_difficulty_baseline (
            module_id               INTEGER PRIMARY KEY,
            module_name             TEXT NOT NULL,
            topic                   TEXT NOT NULL,
            average_completion_time REAL,
            average_pass_rate       REAL
        );

        CREATE TABLE IF NOT EXISTS quiz_attempts (
            attempt_id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id                INTEGER REFERENCES agent_profiles(agent_id),
            module_id               INTEGER REFERENCES module_difficulty_baseline(module_id),
            attempted_at            DATETIME NOT NULL,
            completion_time_seconds INTEGER NOT NULL,
            quiz_score              INTEGER NOT NULL,
            tab_switches            INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS hourly_bio_aggregates (
            aggregate_id        INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id            INTEGER REFERENCES agent_profiles(agent_id),
            day_of_week         INTEGER NOT NULL,
            hour_of_day         INTEGER NOT NULL,
            composite_bio_score REAL,
            data_points_count   INTEGER DEFAULT 0,
            UNIQUE(agent_id, day_of_week, hour_of_day)
        );

        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL CHECK(role IN ('manager','agent')),
            agent_id      INTEGER REFERENCES agent_profiles(agent_id)
        );
    """)
    conn.commit()
    conn.close()

# ── Helpers ───────────────────────────────────────────────────────────────────

def _cold_start_ids(conn):
    rows = conn.execute(
        "SELECT agent_id FROM agent_profiles WHERE total_modules_completed < 10"
    ).fetchall()
    return [r['agent_id'] for r in rows]

def _ph(n):
    return ','.join('?' * n) if n else '0'

def _heatmap_rows(conn, where, params, cold_ids):
    sql = f"""
        SELECT h.day_of_week, h.hour_of_day,
               AVG(h.composite_bio_score) AS score,
               SUM(h.data_points_count)   AS cnt
        FROM hourly_bio_aggregates h
        JOIN agent_profiles a ON h.agent_id = a.agent_id
        WHERE {where} AND h.agent_id NOT IN ({_ph(len(cold_ids))})
        GROUP BY h.day_of_week, h.hour_of_day
    """
    return conn.execute(sql, (*params, *cold_ids)).fetchall()

# ── Heatmap ───────────────────────────────────────────────────────────────────

def get_heatmap_data(filter_type='all', filter_id=None):
    conn = get_db()
    cold_ids = _cold_start_ids(conn)

    if filter_type == 'agent' and filter_id:
        aid = int(filter_id)
        if aid in cold_ids:
            agent = conn.execute(
                "SELECT branch_id FROM agent_profiles WHERE agent_id=?", (aid,)
            ).fetchone()
            rows = _heatmap_rows(conn, "a.branch_id=?", (agent['branch_id'],), cold_ids)
        else:
            rows = conn.execute("""
                SELECT day_of_week, hour_of_day,
                       composite_bio_score AS score,
                       data_points_count   AS cnt
                FROM hourly_bio_aggregates WHERE agent_id=?
            """, (aid,)).fetchall()
    elif filter_type == 'team' and filter_id:
        rows = _heatmap_rows(conn, "a.team_id=?", (filter_id,), cold_ids)
    elif filter_type == 'branch' and filter_id:
        rows = _heatmap_rows(conn, "a.branch_id=?", (filter_id,), cold_ids)
    else:
        rows = _heatmap_rows(conn, "1=1", (), cold_ids)

    conn.close()
    result = {}
    for r in rows:
        result[(r['day_of_week'], r['hour_of_day'])] = {
            'score': round(r['score'], 1) if r['score'] is not None else None,
            'count': r['cnt'] or 0
        }
    return result

# ── Insights ──────────────────────────────────────────────────────────────────

def get_insights(filter_type='all', filter_id=None):
    conn = get_db()
    cold_ids = _cold_start_ids(conn)
    ph = _ph(len(cold_ids))
    insights = []
    DAYS = ['週一','週二','週三','週四','週五','週六','週日']

    if filter_type == 'agent' and filter_id:
        aid   = int(filter_id)
        agent = conn.execute("SELECT * FROM agent_profiles WHERE agent_id=?", (aid,)).fetchone()

        if aid in cold_ids:
            done = agent['total_modules_completed']
            insights.append({
                'type': 'cold_start', 'icon': '❄',
                'title': f'{agent["agent_name"]} — 冷啟動模式',
                'body': (f'已完成 {done}/10 個模組。目前套用分行平均節律，'
                         f'完成 {10-done} 個後將建立個人基線。')
            })
        else:
            ph_val = agent['calculated_peak_hour']
            pd_val = agent['calculated_peak_day']
            if ph_val is not None:
                insights.append({
                    'type': 'peak', 'icon': '⚡',
                    'title': f'{agent["agent_name"]} 認知高峰',
                    'body': (f'統計顯示高峰時段為 {DAYS[pd_val]} '
                             f'{ph_val:02d}:00–{ph_val+1:02d}:00，'
                             f'建議在此時段安排複雜法規培訓。')
                })
            low = conn.execute("""
                SELECT day_of_week, hour_of_day, composite_bio_score
                FROM hourly_bio_aggregates
                WHERE agent_id=? AND data_points_count>=2
                ORDER BY composite_bio_score ASC LIMIT 1
            """, (aid,)).fetchone()
            if low:
                insights.append({
                    'type': 'warning', 'icon': '⚠',
                    'title': '低效能時段提示',
                    'body': (f'{DAYS[low["day_of_week"]]} {low["hour_of_day"]:02d}:00 '
                             f'Bio-Score 最低（{low["composite_bio_score"]:.1f}），'
                             f'建議避免安排高難度模組。')
                })
        insights.append({
            'type': 'stat', 'icon': '📊',
            'title': '模組完成統計',
            'body': f'累計完成 {agent["total_modules_completed"]} 個微學習模組。'
        })

    else:
        if   filter_type == 'team'   and filter_id: scope = f"a.team_id={filter_id} AND"
        elif filter_type == 'branch' and filter_id: scope = f"a.branch_id={filter_id} AND"
        else:                                        scope = ""

        top = conn.execute(f"""
            SELECT a.agent_name, AVG(h.composite_bio_score) AS s
            FROM hourly_bio_aggregates h
            JOIN agent_profiles a ON h.agent_id=a.agent_id
            WHERE {scope} h.agent_id NOT IN ({ph})
            GROUP BY h.agent_id ORDER BY s DESC LIMIT 1
        """, cold_ids).fetchone()
        if top:
            insights.append({
                'type': 'peak', 'icon': '🏆',
                'title': '本期最高效能業務員',
                'body': f'{top["agent_name"]} 平均 Bio-Score {top["s"]:.1f}，建議作為團隊學習標竿。'
            })

        best = conn.execute(f"""
            SELECT h.day_of_week, h.hour_of_day, AVG(h.composite_bio_score) AS s
            FROM hourly_bio_aggregates h
            JOIN agent_profiles a ON h.agent_id=a.agent_id
            WHERE {scope} h.agent_id NOT IN ({ph}) AND h.data_points_count>=2
            GROUP BY h.day_of_week, h.hour_of_day
            ORDER BY s DESC LIMIT 1
        """, cold_ids).fetchone()
        if best:
            insights.append({
                'type': 'peak', 'icon': '⚡',
                'title': '最佳培訓時段',
                'body': (f'{DAYS[best["day_of_week"]]} {best["hour_of_day"]:02d}:00–'
                         f'{best["hour_of_day"]+1:02d}:00 '
                         f'平均 Bio-Score 最高（{best["s"]:.1f}），適合安排培訓活動。')
            })

        cs = len(cold_ids)
        if cs:
            insights.append({
                'type': 'cold_start', 'icon': '❄',
                'title': f'{cs} 名業務員冷啟動中',
                'body': '尚未完成 10 個模組，目前套用分行平均節律。'
            })

    conn.close()
    return insights

# ── List helpers ──────────────────────────────────────────────────────────────

def get_branches_list():
    conn = get_db()
    rows = conn.execute("SELECT * FROM branches ORDER BY branch_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_teams_list(branch_id=None):
    conn = get_db()
    if branch_id:
        rows = conn.execute(
            "SELECT * FROM teams WHERE branch_id=? ORDER BY team_name", (branch_id,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM teams ORDER BY team_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_agents_list(branch_id=None, team_id=None):
    conn = get_db()
    base = """
        SELECT a.agent_id, a.agent_name, a.total_modules_completed,
               a.branch_id, a.team_id, b.branch_name, t.team_name,
               CASE WHEN a.total_modules_completed < 10 THEN 1 ELSE 0 END AS cold_start
        FROM agent_profiles a
        JOIN branches b ON a.branch_id=b.branch_id
        LEFT JOIN teams t ON a.team_id=t.team_id
    """
    if team_id:
        rows = conn.execute(base + "WHERE a.team_id=? ORDER BY a.agent_name", (team_id,)).fetchall()
    elif branch_id:
        rows = conn.execute(base + "WHERE a.branch_id=? ORDER BY a.agent_name", (branch_id,)).fetchall()
    else:
        rows = conn.execute(base + "ORDER BY b.branch_name, t.team_name, a.agent_name").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_agent_profile(agent_id):
    conn = get_db()
    row = conn.execute("""
        SELECT a.*, b.branch_name, t.team_name,
               CASE WHEN a.total_modules_completed < 10 THEN 1 ELSE 0 END AS cold_start
        FROM agent_profiles a
        JOIN branches b ON a.branch_id=b.branch_id
        LEFT JOIN teams t ON a.team_id=t.team_id
        WHERE a.agent_id=?
    """, (agent_id,)).fetchone()
    conn.close()
    return dict(row) if row else None
