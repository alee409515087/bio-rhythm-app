import os
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, session, jsonify)
from werkzeug.security import check_password_hash
from apscheduler.schedulers.background import BackgroundScheduler

from database import (init_db, get_db, get_heatmap_data, get_insights,
                      get_agents_list, get_branches_list, get_teams_list,
                      get_agent_profile)
from bio_score import recalculate_aggregates
from seed_data import seed

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'bio-rhythm-2024-secret')

def init_app():
    init_db()
    conn = get_db()
    count = conn.execute("SELECT COUNT(*) FROM quiz_attempts").fetchone()[0]
    conn.close()
    if count == 0:
        seed()
        recalculate_aggregates()

scheduler = BackgroundScheduler()
scheduler.add_job(recalculate_aggregates, 'interval', minutes=2, id='bio_batch')
scheduler.start()

# ── Auth ──────────────────────────────────────────────────────────────────────
def require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def require_manager(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'manager':
            return redirect(url_for('agent_view'))
        return f(*args, **kwargs)
    return decorated

# ── Pages ─────────────────────────────────────────────────────────────────────
@app.route('/', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id']  = user['user_id']
            session['username'] = user['username']
            session['role']     = user['role']
            session['agent_id'] = user['agent_id']
            return redirect(url_for('dashboard') if user['role'] == 'manager' else url_for('agent_view'))
        error = '帳號或密碼錯誤，請重試。'
    return render_template('login.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@require_login
@require_manager
def dashboard():
    return render_template('dashboard.html',
                           branches=get_branches_list(),
                           teams=get_teams_list(),
                           agents=get_agents_list(),
                           username=session.get('username'))

@app.route('/agent')
@require_login
def agent_view():
    agent_id = session.get('agent_id')
    profile  = get_agent_profile(agent_id) if agent_id else None
    return render_template('agent.html', profile=profile, username=session.get('username'))

# ── APIs ──────────────────────────────────────────────────────────────────────
@app.route('/api/heatmap')
@require_login
def api_heatmap():
    if session.get('role') == 'agent':
        data = get_heatmap_data('agent', str(session.get('agent_id')))
    else:
        ft = request.args.get('type', 'all')
        fid = request.args.get('id')
        data = get_heatmap_data(ft, fid)
    return jsonify([
        {'day': k[0], 'hour': k[1], 'score': v['score'], 'count': v['count']}
        for k, v in data.items()
    ])

@app.route('/api/insights')
@require_login
def api_insights():
    if session.get('role') == 'agent':
        return jsonify(get_insights('agent', str(session.get('agent_id'))))
    return jsonify(get_insights(
        request.args.get('type', 'all'),
        request.args.get('id')
    ))

@app.route('/api/teams')
@require_login
@require_manager
def api_teams():
    branch_id = request.args.get('branch_id')
    return jsonify(get_teams_list(branch_id))

@app.route('/api/agents')
@require_login
@require_manager
def api_agents():
    return jsonify(get_agents_list(
        request.args.get('branch_id'),
        request.args.get('team_id')
    ))

if __name__ == '__main__':
    with app.app_context():
        init_app()
    app.run(debug=False, port=5000, use_reloader=False)
