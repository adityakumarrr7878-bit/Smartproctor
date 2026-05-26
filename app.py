from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector, json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'smartproctor5_secret_key_2025'

from proctor import proctor_bp
app.register_blueprint(proctor_bp)


def get_db():
    return mysql.connector.connect(
        host='localhost', user='root',
        password='singhisking@02.01.2008',
        database='smartproctor5'
    )


def get_exam_status(exam):
    now = datetime.now()
    if now < exam['start_time']:  return 'upcoming'
    if now > exam['end_time']:    return 'completed'
    return 'ongoing'


# ── HOME ───────────────────────────────────────────────────
@app.route('/')
def index():
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams ORDER BY start_time DESC")
    exams = cur.fetchall(); db.close()
    ongoing, upcoming, completed = [], [], []
    for e in exams:
        e['description'] = e.get('description') or ''
        e['status'] = get_exam_status(e)
        if e['status'] == 'ongoing':    ongoing.append(e)
        elif e['status'] == 'upcoming': upcoming.append(e)
        else:                           completed.append(e)
    return render_template('index.html', ongoing=ongoing, upcoming=upcoming, completed=completed)


# ── ADMIN AUTH ─────────────────────────────────────────────
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        db  = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT * FROM admins WHERE email=%s AND password=%s",
                    (request.form['email'], request.form['password']))
        admin = cur.fetchone(); db.close()
        if admin:
            session['admin'] = True
            return redirect(url_for('admin_dashboard'))
        error = 'Wrong Credentials'
    return render_template('admin_login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect(url_for('index'))


# ── ADMIN DASHBOARD ────────────────────────────────────────
@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams ORDER BY created_at DESC")
    exams = cur.fetchall(); db.close()
    for e in exams:
        e['status'] = get_exam_status(e)
    return render_template('admin_dashboard.html', exams=exams)


# ── DELETE EXAM ────────────────────────────────────────────
@app.route('/admin/exam/<int:exam_id>/delete', methods=['POST'])
def delete_exam(exam_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    db  = get_db(); cur = db.cursor()
    # ON DELETE CASCADE handles questions, submissions, live_violations
    cur.execute("DELETE FROM exams WHERE id=%s", (exam_id,))
    db.commit(); db.close()
    return redirect(url_for('admin_dashboard'))


# ── CREATE EXAM ────────────────────────────────────────────
@app.route('/admin/create_exam', methods=['GET', 'POST'])
def create_exam():
    if not session.get('admin'): return redirect(url_for('admin_login'))
    if request.method == 'POST':
        title       = request.form['title']
        description = request.form.get('description', '')
        duration    = int(request.form['duration'])
        start_time  = request.form['start_time']
        end_time    = request.form['end_time']
        rolls       = request.form['allowed_rolls']
        q_texts     = request.form.getlist('question[]')
        q_types     = request.form.getlist('question_type[]')
        opt_a       = request.form.getlist('option_a[]')
        opt_b       = request.form.getlist('option_b[]')
        opt_c       = request.form.getlist('option_c[]')
        opt_d       = request.form.getlist('option_d[]')
        correct     = request.form.getlist('correct[]')

        db  = get_db(); cur = db.cursor()
        cur.execute(
            "INSERT INTO exams (title,description,duration,start_time,end_time,allowed_rolls) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (title, description, duration, start_time, end_time, rolls)
        )
        exam_id = cur.lastrowid
        mcq_i = 0
        for i, q in enumerate(q_texts):
            if not q.strip(): continue
            qt = q_types[i] if i < len(q_types) else 'mcq'
            if qt == 'mcq':
                a = opt_a[mcq_i] if mcq_i < len(opt_a) else ''
                b = opt_b[mcq_i] if mcq_i < len(opt_b) else ''
                c = opt_c[mcq_i] if mcq_i < len(opt_c) else ''
                d = opt_d[mcq_i] if mcq_i < len(opt_d) else ''
                ans = correct[mcq_i] if mcq_i < len(correct) else ''
                mcq_i += 1
            else:
                a = b = c = d = ans = ''
            cur.execute(
                "INSERT INTO questions (exam_id,question_text,question_type,option_a,option_b,option_c,option_d,correct_answer) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (exam_id, q, qt, a, b, c, d, ans)
            )
        db.commit(); db.close()
        return redirect(url_for('admin_dashboard'))
    return render_template('create_exam.html')


# ── EXAM DETAIL ────────────────────────────────────────────
@app.route('/exam/<int:exam_id>')
def exam_detail(exam_id):
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
    exam = cur.fetchone()
    if not exam: db.close(); return redirect(url_for('index'))
    cur.execute("SELECT COUNT(*) as cnt FROM questions WHERE exam_id=%s", (exam_id,))
    q_count = cur.fetchone()['cnt']; db.close()
    exam['status']      = get_exam_status(exam)
    exam['description'] = exam.get('description') or ''
    return render_template('exam_detail.html', exam=exam, q_count=q_count)


# ── VERIFY ROLL ────────────────────────────────────────────
@app.route('/exam/<int:exam_id>/verify', methods=['GET', 'POST'])
def verify_roll(exam_id):
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
    exam = cur.fetchone(); db.close()
    if not exam: return redirect(url_for('index'))
    error = None
    if request.method == 'POST':
        roll    = request.form['roll_number'].strip()
        allowed = [r.strip() for r in (exam['allowed_rolls'] or '').split(',')]
        if roll not in allowed:
            error = 'Invalid Roll Number. You are not allowed to take this exam.'
        else:
            # Check if already submitted
            db2 = get_db(); cur2 = db2.cursor(dictionary=True)
            cur2.execute("SELECT id FROM submissions WHERE exam_id=%s AND roll_number=%s",
                         (exam_id, roll))
            already = cur2.fetchone(); db2.close()
            if already:
                error = 'You have already submitted this exam. Each roll number can attempt only once.'
            else:
                session[f'roll_{exam_id}'] = roll
                return redirect(url_for('instructions', exam_id=exam_id))
    return render_template('verify_roll.html', exam=exam, error=error)


# ── INSTRUCTIONS ───────────────────────────────────────────
@app.route('/exam/<int:exam_id>/instructions')
def instructions(exam_id):
    if not session.get(f'roll_{exam_id}'): return redirect(url_for('verify_roll', exam_id=exam_id))
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT COUNT(*) as cnt FROM questions WHERE exam_id=%s", (exam_id,))
    q_count = cur.fetchone()['cnt']
    cur.execute("SELECT question_type, COUNT(*) as cnt FROM questions WHERE exam_id=%s GROUP BY question_type", (exam_id,))
    type_counts = {r['question_type']: r['cnt'] for r in cur.fetchall()}
    db.close()
    return render_template('instructions.html', exam=exam, q_count=q_count, type_counts=type_counts)


# ── EXAM PAGE ──────────────────────────────────────────────
@app.route('/exam/<int:exam_id>/start')
def exam_page(exam_id):
    if not session.get(f'roll_{exam_id}'): return redirect(url_for('verify_roll', exam_id=exam_id))
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT * FROM questions WHERE exam_id=%s ORDER BY FIELD(question_type,'mcq','short_answer','long_answer'), id", (exam_id,))
    questions = cur.fetchall(); db.close()
    roll = session[f'roll_{exam_id}']
    return render_template('exam_page.html', exam=exam, questions=questions, roll=roll)


# ── SUBMIT EXAM ────────────────────────────────────────────
@app.route('/exam/<int:exam_id>/submit', methods=['POST'])
def submit_exam(exam_id):
    data     = request.get_json()
    roll     = data.get('roll_number')
    answers  = data.get('answers', {})
    attempted = sum(1 for v in answers.values() if v)

    db  = get_db(); cur = db.cursor(dictionary=True)

    # Prevent duplicate submissions
    cur.execute("SELECT id FROM submissions WHERE exam_id=%s AND roll_number=%s", (exam_id, roll))
    if cur.fetchone():
        db.close()
        session.pop(f'roll_{exam_id}', None)
        return jsonify({'status': 'already_submitted', 'attempted': attempted})

    # Read violations from live_violations table
    cur.execute("SELECT counts FROM live_violations WHERE exam_id=%s AND roll_number=%s", (exam_id, roll))
    row = cur.fetchone()
    violations = {}
    if row:
        c = row['counts']
        violations = json.loads(c) if isinstance(c, str) else (c or {})

    final_v = {
        'no_face':         violations.get('no_face', 0),
        'multi_face':      violations.get('multi_face', 0),
        'object_detected': violations.get('object_detected', 0),
        'tab_switch':      violations.get('tab_switch', 0),
    }

    cur2 = db.cursor()
    cur2.execute(
        "INSERT INTO submissions (exam_id,roll_number,answers,attempted,violations) VALUES (%s,%s,%s,%s,%s)",
        (exam_id, roll, json.dumps(answers), attempted, json.dumps(final_v))
    )
    db.commit(); db.close()
    session.pop(f'roll_{exam_id}', None)
    return jsonify({'status': 'ok', 'attempted': attempted})


# ── RESULT PAGE ────────────────────────────────────────────
@app.route('/exam/<int:exam_id>/result')
def result_page(exam_id):
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT COUNT(*) as cnt FROM questions WHERE exam_id=%s", (exam_id,))
    q_count = cur.fetchone()['cnt']; db.close()
    attempted = request.args.get('attempted', 0)
    return render_template('result.html', exam_id=exam_id, q_count=q_count, attempted=attempted)


# ── VIEW SUBMISSIONS ───────────────────────────────────────
@app.route('/admin/exam/<int:exam_id>/submissions')
def view_submissions(exam_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT * FROM submissions WHERE exam_id=%s ORDER BY submitted_at DESC", (exam_id,))
    submitted = cur.fetchall()
    for s in submitted:
        v = s['violations']
        s['violations'] = json.loads(v) if isinstance(v, str) else (v or {})
    submitted_rolls = {s['roll_number'] for s in submitted}
    allowed_rolls   = [r.strip() for r in (exam['allowed_rolls'] or '').split(',')]
    not_submitted   = [r for r in allowed_rolls if r not in submitted_rolls]
    db.close()
    return render_template('view_submissions.html', exam=exam, submitted=submitted, not_submitted=not_submitted)


# ── VIEW ANSWERS ───────────────────────────────────────────
@app.route('/admin/exam/<int:exam_id>/answers/<int:submission_id>')
def view_answers(exam_id, submission_id):
    if not session.get('admin'): return redirect(url_for('admin_login'))
    db  = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM exams WHERE id=%s", (exam_id,))
    exam = cur.fetchone()
    cur.execute("SELECT * FROM submissions WHERE id=%s AND exam_id=%s", (submission_id, exam_id))
    submission = cur.fetchone()
    if not submission:
        db.close()
        return redirect(url_for('view_submissions', exam_id=exam_id))
    a = submission['answers']
    v = submission['violations']
    submission['answers']    = json.loads(a) if isinstance(a, str) else (a or {})
    submission['violations'] = json.loads(v) if isinstance(v, str) else (v or {})
    cur.execute("SELECT * FROM questions WHERE exam_id=%s ORDER BY FIELD(question_type,'mcq','short_answer','long_answer'), id", (exam_id,))
    questions = cur.fetchall(); db.close()
    return render_template('view_answers.html', exam=exam, submission=submission, questions=questions)


if __name__ == '__main__':
    app.run(debug=True)
