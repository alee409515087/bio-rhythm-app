import sqlite3
import math
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

DATABASE = 'bio_rhythm.db'

BRANCHES = [
    (1, '信義分行'),
    (2, '大安分行'),
]

# (team_id, name, branch_id)
TEAMS = [
    (1, '壽險銷售組', 1),
    (2, '法遵合規組', 1),
    (3, '財富管理組', 2),
    (4, '數位通路組', 2),
]

# (agent_id, name, branch_id, team_id, peak_hour, peak_sigma, n_attempts)
AGENTS = [
    (1, '林志豪', 1, 1,  8,  1.5, 140),   # 晨峰型
    (2, '陳美君', 1, 1, 14,  2.0,  88),   # 午後型
    (3, '王建國', 1, 2, 10,  3.0,  72),   # 寬鬆晨型
    (4, '張雅婷', 1, 2, 16,  2.0,   8),   # ❄ 冷啟動
    (5, '劉志明', 2, 3,  9,  2.5, 155),   # 早上型
    (6, '黃淑芬', 2, 3, 15,  2.0, 100),   # 下午型
    (7, '吳俊傑', 2, 4, 11,  3.5,  76),   # 彈性中午型
    (8, '蔡麗玲', 2, 4, 13,  2.0,   4),   # ❄ 冷啟動
]

MODULES = [
    (1, '定期壽險基礎',         '壽險', 240, 0.88),
    (2, '投資型保單法規 (ULIP)', '法遵', 420, 0.62),
    (3, '金融商品交叉銷售框架',  '銷售', 360, 0.74),
    (4, '金管會最新法規更新',    '法遵', 300, 0.70),
    (5, '數位工具操作與實務',    '系統', 200, 0.91),
]

USERS = [
    ('manager', 'manager123', 'manager', None),
    ('agent01', 'agent123',   'agent',   1),
    ('agent02', 'agent123',   'agent',   2),
    ('agent03', 'agent123',   'agent',   3),
    ('agent04', 'agent123',   'agent',   4),
    ('agent05', 'agent123',   'agent',   5),
    ('agent06', 'agent123',   'agent',   6),
    ('agent07', 'agent123',   'agent',   7),
    ('agent08', 'agent123',   'agent',   8),
]

def _perf(peak_hour, sigma, hour):
    base = math.exp(-0.5 * ((hour - peak_hour) / sigma) ** 2)
    return 0.35 + 0.65 * base

def seed(db_path=DATABASE):
    random.seed(42)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    for bid, bname in BRANCHES:
        conn.execute("INSERT OR IGNORE INTO branches VALUES (?,?)", (bid, bname))

    for tid, tname, bid in TEAMS:
        conn.execute("INSERT OR IGNORE INTO teams VALUES (?,?,?)", (tid, tname, bid))

    for aid, name, bid, tid, *_ in AGENTS:
        conn.execute(
            "INSERT OR IGNORE INTO agent_profiles (agent_id,agent_name,branch_id,team_id) VALUES (?,?,?,?)",
            (aid, name, bid, tid)
        )

    for mid, mname, topic, avg_t, avg_p in MODULES:
        conn.execute("""
            INSERT OR IGNORE INTO module_difficulty_baseline
            VALUES (?,?,?,?,?)
        """, (mid, mname, topic, avg_t, avg_p))

    now = datetime.now()
    ACTIVE_HOURS = list(range(7, 21))
    attempts = []

    for aid, _, _, _, peak_hour, sigma, n_attempts in AGENTS:
        for _ in range(n_attempts):
            offset = random.randint(0, 59)
            dt = now - timedelta(days=offset)
            while dt.weekday() > 4:
                dt -= timedelta(days=1)
            hour = random.choice(ACTIVE_HOURS)
            dt = dt.replace(hour=hour, minute=random.randint(0, 59), second=0)

            mod = random.choice(MODULES)
            mid, _, _, avg_time, avg_pass = mod
            perf = _perf(peak_hour, sigma, hour)

            score    = int(max(0, min(100, avg_pass * perf * 100 + random.gauss(0, 8))))
            speed_f  = 1.0 / max(perf, 0.3)
            comp_t   = int(avg_time * speed_f * random.uniform(0.85, 1.20))
            distract = max(0, 1.0 - perf)
            tab_sw   = max(0, min(12, int(random.gauss(distract * 6, 1.5))))

            attempts.append((aid, mid, dt.strftime('%Y-%m-%d %H:%M:%S'), comp_t, score, tab_sw))

    conn.executemany("""
        INSERT INTO quiz_attempts
            (agent_id,module_id,attempted_at,completion_time_seconds,quiz_score,tab_switches)
        VALUES (?,?,?,?,?,?)
    """, attempts)

    for username, password, role, agent_id in USERS:
        ph = generate_password_hash(password, method='pbkdf2:sha256')
        conn.execute(
            "INSERT OR IGNORE INTO users (username,password_hash,role,agent_id) VALUES (?,?,?,?)",
            (username, ph, role, agent_id)
        )

    conn.commit()
    conn.close()
    print(f"[Seed] Inserted {len(attempts)} quiz attempts, 4 teams.")

if __name__ == '__main__':
    from database import init_db
    init_db()
    seed()
    from bio_score import recalculate_aggregates
    recalculate_aggregates()
