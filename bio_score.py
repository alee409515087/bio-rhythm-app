import sqlite3
import math

def calculate_bio_score(quiz_score, completion_time, avg_time, tab_switches):
    """
    Weighted Bio-Score (0-100):
      accuracy  50% — raw quiz score
      speed     35% — how fast vs. module average (capped at 1.5x faster)
      focus     15% — penalty for tab switches (8+ switches → 0)

    "A 100% score in 3 min > 100% score in 6 min with 4 tab-switches"
    """
    accuracy = quiz_score / 100.0

    if avg_time and avg_time > 0:
        speed_ratio = avg_time / max(completion_time, 1)
        speed = min(speed_ratio, 1.5) / 1.5  # normalize: 1.5x faster → 1.0
    else:
        speed = 0.5  # neutral if no baseline

    focus = max(0.0, 1.0 - tab_switches / 8.0)

    raw = (accuracy * 0.50) + (speed * 0.35) + (focus * 0.15)
    return round(raw * 100, 2)


def recalculate_aggregates(db_path='bio_rhythm.db'):
    """
    Batch job: reads all QuizAttempts, recalculates HourlyBioAggregates,
    then updates AgentProfiles peak hour/day.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")

    # Load module difficulty baselines
    baselines = {}
    for row in conn.execute("SELECT module_id, average_completion_time FROM module_difficulty_baseline"):
        baselines[row['module_id']] = row['average_completion_time']

    # Load all attempts
    attempts = conn.execute("""
        SELECT agent_id, module_id, attempted_at,
               completion_time_seconds, quiz_score, tab_switches,
               CAST(strftime('%w', attempted_at) AS INTEGER) as dow_sun,
               CAST(strftime('%H', attempted_at) AS INTEGER) as hod
        FROM quiz_attempts
    """).fetchall()

    # Aggregate: (agent_id, day_of_week, hour) → [scores]
    buckets = {}
    for a in attempts:
        # Convert Sunday=0 → Monday=0 (ISO week)
        dow = (a['dow_sun'] + 6) % 7
        hod = a['hod']
        key = (a['agent_id'], dow, hod)
        avg_time = baselines.get(a['module_id'], a['completion_time_seconds'])
        score = calculate_bio_score(
            a['quiz_score'], a['completion_time_seconds'], avg_time, a['tab_switches']
        )
        buckets.setdefault(key, []).append(score)

    # Upsert into hourly_bio_aggregates
    conn.execute("DELETE FROM hourly_bio_aggregates")
    for (agent_id, dow, hod), scores in buckets.items():
        avg_score = sum(scores) / len(scores)
        conn.execute("""
            INSERT INTO hourly_bio_aggregates
                (agent_id, day_of_week, hour_of_day, composite_bio_score, data_points_count)
            VALUES (?, ?, ?, ?, ?)
        """, (agent_id, dow, hod, round(avg_score, 2), len(scores)))

    # Update AgentProfiles peak hour/day and module count
    agents = conn.execute("SELECT agent_id FROM agent_profiles").fetchall()
    for ag in agents:
        aid = ag['agent_id']
        best = conn.execute("""
            SELECT day_of_week, hour_of_day
            FROM hourly_bio_aggregates
            WHERE agent_id=? AND data_points_count >= 2
            ORDER BY composite_bio_score DESC LIMIT 1
        """, (aid,)).fetchone()

        count = conn.execute(
            "SELECT COUNT(*) FROM quiz_attempts WHERE agent_id=?", (aid,)
        ).fetchone()[0]

        conn.execute("""
            UPDATE agent_profiles
            SET calculated_peak_hour=?,
                calculated_peak_day=?,
                total_modules_completed=?
            WHERE agent_id=?
        """, (
            best['hour_of_day'] if best else None,
            best['day_of_week'] if best else None,
            count,
            aid
        ))

    conn.commit()
    conn.close()
    print("[Bio-Rhythm] Aggregates recalculated.")
