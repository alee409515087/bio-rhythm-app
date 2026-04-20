#!/usr/bin/env python3
"""
Bio-Rhythm Analytics Engine — Startup Script
One-command launch: python run.py
"""
import os
import sys

def main():
    # Ensure we're in the project directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    from database import init_db
    from seed_data import seed
    from bio_score import recalculate_aggregates

    print("=" * 50)
    print("  BIO-RHYTHM Analytics Engine")
    print("=" * 50)

    print("\n[1/3] Initializing database...")
    init_db()

    import sqlite3
    conn = sqlite3.connect('bio_rhythm.db')
    count = conn.execute("SELECT COUNT(*) FROM quiz_attempts").fetchone()[0]
    conn.close()

    if count == 0:
        print("[2/3] Seeding demo data...")
        seed()
        print("[3/3] Calculating Bio-Score aggregates...")
        recalculate_aggregates()
    else:
        print(f"[2/3] Found {count} existing quiz attempts, skipping seed.")
        print("[3/3] Recalculating aggregates...")
        recalculate_aggregates()

    print("\n✓ Ready!")
    print("\n  URL     : http://localhost:5000")
    print("  Manager : manager / manager123")
    print("  Agents  : agent01–agent08 / agent123")
    print("\n  Press Ctrl+C to stop.\n")
    print("=" * 50 + "\n")

    from app import app
    app.run(debug=False, port=5000, use_reloader=False)

if __name__ == '__main__':
    main()
