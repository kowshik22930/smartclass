
"""
Smart Classroom Timetable Scheduler - Flask Application
Main application with REST API endpoints and template rendering.
"""
import os
import sqlite3
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, g

from ML.pipeline import SchedulingPipeline

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'smart-scheduler-secret-2025')

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'database', 'scheduler.db')


# ─── Database Helpers ────────────────────────────────────────────────

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def dict_row(row):
    return dict(row) if row else None


def dict_rows(rows):
    return [dict(r) for r in rows]


def get_json_data():
    """Safely parse JSON request bodies."""
    return request.get_json(silent=True) or {}


def init_db():
    """Initialize database from schema and seed files."""
    db = sqlite3.connect(DB_PATH)
    schema_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'schema.sql')
    seed_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'seed_data.sql')

    with open(schema_path) as f:
        db.executescript(f.read())

    check = db.execute("SELECT COUNT(*) FROM departments").fetchone()[0]
    if check == 0:
        with open(seed_path) as f:
            db.executescript(f.read())
        print("[DB] Seed data loaded.")

    _ensure_default_users(db)

    db.close()
    print("[DB] Database initialized.")


def _ensure_default_users(db):
    """Ensure demo logins exist for each portal."""
    demo_users = [
        ('admin', 'admin123', 'admin', None),
        ('faculty1', 'faculty123', 'faculty', 1),
        ('faculty2', 'faculty123', 'faculty', 2),
        ('faculty3', 'faculty123', 'faculty', 3),
        ('faculty4', 'faculty123', 'faculty', 4),
        ('faculty5', 'faculty123', 'faculty', 5),
        ('faculty6', 'faculty123', 'faculty', 6),
        ('faculty7', 'faculty123', 'faculty', 7),
        ('student1', 'student123', 'student', 1),
        ('student2', 'student123', 'student', 2),
        ('student3', 'student123', 'student', 3),
        ('student4', 'student123', 'student', 1),
        ('student5', 'student123', 'student', 1),
        ('student6', 'student123', 'student', 1),
        ('student7', 'student123', 'student', 1),
        ('student8', 'student123', 'student', 1),
        ('student9', 'student123', 'student', 1),
        ('student10', 'student123', 'student', 1),
        ('student11', 'student123', 'student', 1),
        ('student12', 'student123', 'student', 1),
        ('student13', 'student123', 'student', 1),
        ('student14', 'student123', 'student', 1),
        ('student15', 'student123', 'student', 1),
        ('student16', 'student123', 'student', 1),
    ]
    for username, password, role, linked_id in demo_users:
        db.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role, linked_id)
            VALUES (?, ?, ?, ?)
            """,
            (username, password, role, linked_id),
        )
    db.commit()


# ─── Auth Decorator ──────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated


def roles_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                if request.is_json:
                    return jsonify({'error': 'Authentication required'}), 401
                return redirect(url_for('login_page'))

            if session.get('role') not in allowed_roles:
                if request.path.startswith('/api/'):
                    return jsonify({'error': 'Forbidden'}), 403
                if session.get('role') == 'faculty':
                    return redirect(url_for('faculty_page'))
                if session.get('role') == 'student':
                    return redirect(url_for('student_page'))
                return redirect(url_for('dashboard_page'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ─── Page Routes ─────────────────────────────────────────────────────

@app.route('/')
def index():
    if 'user_id' in session:
        role = session.get('role', 'admin')
        if role == 'faculty':
            return redirect(url_for('faculty_page'))
        elif role == 'student':
            return redirect(url_for('student_page'))
        return redirect(url_for('dashboard_page'))
    return redirect(url_for('login_page'))


@app.route('/login')
def login_page():
    return render_template('login.html')


@app.route('/dashboard')
@roles_required('admin')
def dashboard_page():
    return render_template('dashboard.html')


@app.route('/faculty-view')
@roles_required('faculty')
def faculty_page():
    return render_template('faculty.html', current_user={
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'linked_id': session.get('linked_id'),
    })


@app.route('/student-view')
@roles_required('student')
def student_page():
    return render_template('student.html', current_user={
        'id': session.get('user_id'),
        'username': session.get('username'),
        'role': session.get('role'),
        'linked_id': session.get('linked_id'),
    })


# ─── Auth API ────────────────────────────────────────────────────────

@app.route('/api/login', methods=['POST'])
def api_login():
    data = get_json_data()
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username:
        return jsonify({'status': 'error', 'message': 'Username is required'}), 400
    if not password:
        return jsonify({'status': 'error', 'message': 'Password is required'}), 400

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

    if not user:
        return jsonify({'status': 'error', 'message': 'Username not found'}), 401

    if user['password_hash'] != password:
        return jsonify({'status': 'error', 'message': 'Wrong password'}), 401

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['role'] = user['role']
    session['linked_id'] = user['linked_id']
    return jsonify({'status': 'success', 'role': user['role']})


@app.route('/api/logout', methods=['POST'])
def api_logout():
    session.clear()
    return jsonify({'status': 'success'})


# ─── Department API ──────────────────────────────────────────────────

@app.route('/api/departments', methods=['GET'])
@roles_required('admin')
def get_departments():
    db = get_db()
    rows = db.execute("SELECT * FROM departments ORDER BY name").fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/departments', methods=['POST'])
@roles_required('admin')
def add_department():
    data = get_json_data()
    db = get_db()
    try:
        db.execute("INSERT INTO departments (name, code, head_of_department) VALUES (?, ?, ?)",
                   (data['name'], data['code'], data.get('head_of_department', '')))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/departments/<int:dept_id>', methods=['PUT'])
@roles_required('admin')
def update_department(dept_id):
    data = get_json_data()
    db = get_db()
    try:
        db.execute("UPDATE departments SET name=?, code=?, head_of_department=? WHERE id=?",
                   (data['name'], data['code'], data.get('head_of_department', ''), dept_id))
        db.commit()
        return jsonify({'status': 'updated'})
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/departments/<int:dept_id>', methods=['DELETE'])
@roles_required('admin')
def delete_department(dept_id):
    db = get_db()
    try:
        db.execute("DELETE FROM departments WHERE id=?", (dept_id,))
        db.commit()
        return jsonify({'status': 'deleted'})
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


# ─── Course API ──────────────────────────────────────────────────────

@app.route('/api/courses', methods=['GET'])
@roles_required('admin')
def get_courses():
    db = get_db()
    rows = db.execute("""
        SELECT c.*, d.name as department_name
        FROM courses c JOIN departments d ON c.department_id = d.id
        ORDER BY c.name
    """).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/courses', methods=['POST'])
@roles_required('admin')
def add_course():
    data = get_json_data()
    db = get_db()
    try:
        db.execute("INSERT INTO courses (name, code, department_id, semester_count) VALUES (?, ?, ?, ?)",
                   (data['name'], data['code'], data['department_id'], data.get('semester_count', 8)))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


# ─── Semester API ────────────────────────────────────────────────────

@app.route('/api/semesters', methods=['GET'])
@roles_required('admin', 'student')
def get_semesters():
    db = get_db()
    rows = db.execute("""
        SELECT s.*, c.name as course_name, c.code as course_code
        FROM semesters s JOIN courses c ON s.course_id = c.id
        ORDER BY c.name, s.semester_number
    """).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/semesters', methods=['POST'])
@roles_required('admin')
def add_semester():
    data = get_json_data()
    db = get_db()
    try:
        db.execute("INSERT INTO semesters (course_id, semester_number, academic_year, student_count) VALUES (?, ?, ?, ?)",
                   (data['course_id'], data['semester_number'], data['academic_year'], data.get('student_count', 0)))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


# ─── Subject API ─────────────────────────────────────────────────────

@app.route('/api/subjects', methods=['GET'])
@roles_required('admin')
def get_subjects():
    db = get_db()
    rows = db.execute("""
        SELECT sub.*, s.semester_number, c.name as course_name
        FROM subjects sub
        JOIN semesters s ON sub.semester_id = s.id
        JOIN courses c ON s.course_id = c.id
        ORDER BY c.name, s.semester_number, sub.name
    """).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/subjects', methods=['POST'])
@roles_required('admin')
def add_subject():
    data = get_json_data()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO subjects (name, code, semester_id, lectures_per_week, is_lab, priority) VALUES (?, ?, ?, ?, ?, ?)",
            (data['name'], data['code'], data['semester_id'],
             data.get('lectures_per_week', 3), data.get('is_lab', 0), data.get('priority', 5)))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


# ─── Faculty API ─────────────────────────────────────────────────────

@app.route('/api/faculty', methods=['GET'])
@roles_required('admin', 'faculty')
def get_faculty():
    db = get_db()
    query = """
        SELECT f.*, d.name as department_name
        FROM faculty f JOIN departments d ON f.department_id = d.id
    """
    args = []
    if session.get('role') == 'faculty':
        query += " WHERE f.id = ?"
        args.append(session.get('linked_id'))
    query += " ORDER BY f.name"
    rows = db.execute(query, args).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/faculty', methods=['POST'])
@roles_required('admin')
def add_faculty():
    data = get_json_data()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO faculty (name, email, department_id, designation, max_hours_per_day, max_hours_per_week) VALUES (?, ?, ?, ?, ?, ?)",
            (data['name'], data['email'], data['department_id'],
             data.get('designation', ''), data.get('max_hours_per_day', 6), data.get('max_hours_per_week', 25)))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/faculty-subjects', methods=['GET'])
@roles_required('admin', 'faculty')
def get_faculty_subjects():
    db = get_db()
    query = """
        SELECT fs.*, f.name as faculty_name, sub.name as subject_name, sub.code as subject_code
        FROM faculty_subjects fs
        JOIN faculty f ON fs.faculty_id = f.id
        JOIN subjects sub ON fs.subject_id = sub.id
    """
    args = []
    if session.get('role') == 'faculty':
        query += " WHERE fs.faculty_id = ?"
        args.append(session.get('linked_id'))
    rows = db.execute(query, args).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/faculty-subjects', methods=['POST'])
@roles_required('admin')
def add_faculty_subject():
    data = get_json_data()
    db = get_db()
    try:
        db.execute("INSERT INTO faculty_subjects (faculty_id, subject_id, preference_score) VALUES (?, ?, ?)",
                   (data['faculty_id'], data['subject_id'], data.get('preference_score', 5)))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


# ─── Classroom API ───────────────────────────────────────────────────

@app.route('/api/classrooms', methods=['GET'])
@roles_required('admin', 'student')
def get_classrooms():
    db = get_db()
    rows = db.execute("SELECT * FROM classrooms ORDER BY name").fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/classrooms', methods=['POST'])
@roles_required('admin')
def add_classroom():
    data = get_json_data()
    db = get_db()
    try:
        db.execute(
            "INSERT INTO classrooms (name, building, floor, capacity, room_type, has_projector, has_ac) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (data['name'], data.get('building', ''), data.get('floor', 0),
             data['capacity'], data.get('room_type', 'lecture'),
             data.get('has_projector', 1), data.get('has_ac', 0)))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


# ─── Timeslot API ────────────────────────────────────────────────────

@app.route('/api/timeslots', methods=['GET'])
@roles_required('admin', 'faculty', 'student')
def get_timeslots():
    db = get_db()
    rows = db.execute("SELECT * FROM timeslots ORDER BY slot_number").fetchall()
    return jsonify(dict_rows(rows))


# ─── Timetable Generation API ───────────────────────────────────────

@app.route('/api/generate', methods=['POST'])
@roles_required('admin')
def generate_timetable():
    """Main endpoint: triggers the full ML pipeline."""
    db = get_db()
    params = get_json_data()

    data = _load_scheduling_data(db)
    if not data['subjects']:
        return jsonify({'error': 'No subjects found. Add data first.'}), 400
    if not data['faculty_subjects']:
        return jsonify({'error': 'No faculty-subject mappings found.'}), 400

    pipeline = SchedulingPipeline(data)
    result = pipeline.run(
        use_ml=params.get('use_ml', True),
        ga_generations=params.get('ga_generations', 80),
        ga_population=params.get('ga_population', 25),
    )

    if result['status'] == 'success':
        version = _get_next_version(db)
        _save_timetable(db, result['schedule'], version)
        _log_generation(db, version, result)
        _notify_students_timetable_generated(db, version)
        result['timetable_version'] = version

    return jsonify(result)


@app.route('/api/timetable', methods=['GET'])
@roles_required('admin', 'faculty', 'student')
def get_timetable():
    """Get the latest generated timetable, with optional filters."""
    db = get_db()
    version = request.args.get('version')
    semester_id = request.args.get('semester_id')
    faculty_id = request.args.get('faculty_id')

    query = """
        SELECT te.*,
               sub.name as subject_name, sub.code as subject_code, sub.is_lab,
               f.name as faculty_name,
               cr.name as classroom_name, cr.room_type,
               ts.start_time, ts.end_time, ts.label as slot_label,
               s.semester_number, c.name as course_name
        FROM timetable_entries te
        JOIN subjects sub ON te.subject_id = sub.id
        JOIN faculty f ON te.faculty_id = f.id
        JOIN classrooms cr ON te.classroom_id = cr.id
        JOIN timeslots ts ON te.timeslot_id = ts.id
        JOIN semesters s ON te.semester_id = s.id
        JOIN courses c ON s.course_id = c.id
    """
    conditions = []
    args = []

    if version:
        conditions.append("te.timetable_version = ?")
        args.append(int(version))
    else:
        conditions.append("te.timetable_version = (SELECT MAX(timetable_version) FROM timetable_entries)")

    if session.get('role') == 'student':
        conditions.append("te.semester_id = ?")
        args.append(int(session.get('linked_id')))
    elif semester_id:
        conditions.append("te.semester_id = ?")
        args.append(int(semester_id))

    if session.get('role') == 'faculty':
        conditions.append("te.faculty_id = ?")
        args.append(int(session.get('linked_id')))
    elif faculty_id:
        conditions.append("te.faculty_id = ?")
        args.append(int(faculty_id))

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY te.day_of_week, ts.slot_number"

    rows = db.execute(query, args).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/timetable/versions', methods=['GET'])
@roles_required('admin')
def get_versions():
    db = get_db()
    rows = db.execute("""
        SELECT DISTINCT timetable_version, COUNT(*) as entry_count,
               MIN(created_at) as created_at
        FROM timetable_entries GROUP BY timetable_version ORDER BY timetable_version DESC
    """).fetchall()
    return jsonify(dict_rows(rows))


# ─── Swap Requests API ──────────────────────────────────────────────

@app.route('/api/swap-requests', methods=['GET'])
@roles_required('admin', 'faculty')
def get_swap_requests():
    db = get_db()
    query = """
        SELECT sr.*, f.name as faculty_name,
               sub.name as subject_name, ts.label as current_slot
        FROM swap_requests sr
        JOIN faculty f ON sr.faculty_id = f.id
        JOIN timetable_entries te ON sr.entry_id = te.id
        JOIN subjects sub ON te.subject_id = sub.id
        JOIN timeslots ts ON te.timeslot_id = ts.id
    """
    args = []
    if session.get('role') == 'faculty':
        query += " WHERE sr.faculty_id = ?"
        args.append(session.get('linked_id'))
    query += " ORDER BY sr.created_at DESC"
    rows = db.execute(query, args).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/faculty/attendance', methods=['GET'])
@roles_required('faculty')
def get_faculty_attendance():
    entry_id = request.args.get('entry_id', type=int)
    attendance_date = request.args.get('date', '')
    if not entry_id or not attendance_date:
        return jsonify({'error': 'Class and date are required'}), 400
    db = get_db()
    faculty_id = session.get('linked_id')
    entry = db.execute(
        'SELECT id, semester_id FROM timetable_entries WHERE id = ? AND faculty_id = ?',
        (entry_id, faculty_id)
    ).fetchone()
    if not entry:
        return jsonify({'error': 'Class not found in your schedule'}), 404
    rows = db.execute("""
        SELECT u.id AS student_user_id, u.username, a.status
        FROM users u
        LEFT JOIN attendance a ON a.student_user_id = u.id
            AND a.timetable_entry_id = ? AND a.attendance_date = ?
        WHERE u.role = 'student' AND u.linked_id = ?
        ORDER BY u.username
    """, (entry_id, attendance_date, entry['semester_id'])).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/faculty/attendance', methods=['POST'])
@roles_required('faculty')
def save_faculty_attendance():
    data = get_json_data()
    entry_id = data.get('entry_id')
    attendance_date = data.get('date', '')
    records = data.get('records')
    if not entry_id or not attendance_date or not isinstance(records, list):
        return jsonify({'error': 'Class, date, and attendance records are required'}), 400
    db = get_db()
    entry = db.execute(
        'SELECT id, semester_id FROM timetable_entries WHERE id = ? AND faculty_id = ?',
        (entry_id, session.get('linked_id'))
    ).fetchone()
    if not entry:
        return jsonify({'error': 'Class not found in your schedule'}), 404
    valid_students = {row['id'] for row in db.execute(
        "SELECT id FROM users WHERE role = 'student' AND linked_id = ?",
        (entry['semester_id'],)
    ).fetchall()}
    for record in records:
        try:
            student_id = int(record.get('student_user_id'))
        except (TypeError, ValueError, AttributeError):
            return jsonify({'error': 'Invalid student in attendance records'}), 400
        status = record.get('status')
        if student_id not in valid_students or status not in ('present', 'absent'):
            return jsonify({'error': 'Invalid student or attendance status'}), 400
    for record in records:
        db.execute("""
            INSERT INTO attendance (timetable_entry_id, student_user_id, attendance_date, status)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(timetable_entry_id, student_user_id, attendance_date)
            DO UPDATE SET status = excluded.status, recorded_at = CURRENT_TIMESTAMP
        """, (entry_id, int(record['student_user_id']), attendance_date, record['status']))
    db.commit()
    return jsonify({'status': 'saved', 'count': len(records)})


@app.route('/api/swap-requests', methods=['POST'])
@roles_required('faculty')
def create_swap_request():
    data = get_json_data()
    db = get_db()
    try:
        faculty_id = int(session.get('linked_id'))
        entry = db.execute(
            "SELECT id FROM timetable_entries WHERE id = ? AND faculty_id = ?",
            (data['entry_id'], faculty_id)
        ).fetchone()
        if not entry:
            return jsonify({'error': 'You can only request swaps for your own timetable entries'}), 403
        db.execute(
            "INSERT INTO swap_requests (faculty_id, entry_id, requested_day, requested_timeslot_id, reason) VALUES (?, ?, ?, ?, ?)",
            (faculty_id, data['entry_id'], data.get('requested_day'),
             data.get('requested_timeslot_id'), data.get('reason', '')))
        db.commit()
        return jsonify({'status': 'created'}), 201
    except KeyError as e:
        return jsonify({'error': f"Missing field: {e.args[0]}"}), 400
    except sqlite3.IntegrityError as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/swap-requests/<int:req_id>/approve', methods=['POST'])
@roles_required('admin')
def approve_swap(req_id):
    db = get_db()
    req = dict_row(db.execute("SELECT * FROM swap_requests WHERE id=?", (req_id,)).fetchone())
    if not req:
        return jsonify({'error': 'Not found'}), 404

    if req['requested_day'] is not None:
        db.execute("UPDATE timetable_entries SET day_of_week=? WHERE id=?",
                   (req['requested_day'], req['entry_id']))
    if req['requested_timeslot_id']:
        db.execute("UPDATE timetable_entries SET timeslot_id=? WHERE id=?",
                   (req['requested_timeslot_id'], req['entry_id']))

    db.execute("UPDATE swap_requests SET status='approved' WHERE id=?", (req_id,))
    db.commit()
    return jsonify({'status': 'approved'})


@app.route('/api/swap-requests/<int:req_id>/reject', methods=['POST'])
@roles_required('admin')
def reject_swap(req_id):
    db = get_db()
    db.execute("UPDATE swap_requests SET status='rejected' WHERE id=?", (req_id,))
    db.commit()
    return jsonify({'status': 'rejected'})


@app.route('/api/swap-requests/<int:req_id>', methods=['DELETE'])
@roles_required('admin')
def delete_swap_request(req_id):
    db = get_db()
    cursor = db.execute("DELETE FROM swap_requests WHERE id=?", (req_id,))
    db.commit()
    if cursor.rowcount == 0:
        return jsonify({'error': 'Swap request not found'}), 404
    return jsonify({'status': 'deleted'})


@app.route('/api/swap-requests/clear', methods=['DELETE'])
@roles_required('admin')
def clear_swap_requests():
    db = get_db()
    db.execute("DELETE FROM swap_requests")
    db.commit()
    return jsonify({'status': 'deleted'})


# ─── Analytics API ───────────────────────────────────────────────────

@app.route('/api/analytics/overview', methods=['GET'])
@roles_required('admin')
def analytics_overview():
    db = get_db()
    stats = {
        'departments': db.execute("SELECT COUNT(*) FROM departments").fetchone()[0],
        'courses': db.execute("SELECT COUNT(*) FROM courses").fetchone()[0],
        'subjects': db.execute("SELECT COUNT(*) FROM subjects").fetchone()[0],
        'faculty': db.execute("SELECT COUNT(*) FROM faculty").fetchone()[0],
        'classrooms': db.execute("SELECT COUNT(*) FROM classrooms").fetchone()[0],
        'timetable_entries': db.execute("SELECT COUNT(*) FROM timetable_entries").fetchone()[0],
    }

    logs = db.execute("""
        SELECT * FROM generation_logs ORDER BY created_at DESC LIMIT 5
    """).fetchall()
    stats['recent_generations'] = dict_rows(logs)

    return jsonify(stats)


@app.route('/api/analytics/faculty-workload', methods=['GET'])
@roles_required('admin')
def faculty_workload():
    db = get_db()
    rows = db.execute("""
        SELECT f.id, f.name, f.max_hours_per_week,
               COUNT(te.id) as assigned_hours,
               COUNT(DISTINCT te.day_of_week) as active_days
        FROM faculty f
        LEFT JOIN timetable_entries te ON f.id = te.faculty_id
            AND te.timetable_version = (SELECT MAX(timetable_version) FROM timetable_entries)
        GROUP BY f.id
        ORDER BY f.name
    """).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/analytics/room-utilization', methods=['GET'])
@roles_required('admin')
def room_utilization():
    db = get_db()
    rows = db.execute("""
        SELECT cr.id, cr.name, cr.capacity, cr.room_type,
               COUNT(te.id) as used_slots,
               30 as total_slots
        FROM classrooms cr
        LEFT JOIN timetable_entries te ON cr.id = te.classroom_id
            AND te.timetable_version = (SELECT MAX(timetable_version) FROM timetable_entries)
        GROUP BY cr.id
        ORDER BY cr.name
    """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d['utilization_pct'] = round(d['used_slots'] / 30 * 100, 1)
        result.append(d)
    return jsonify(result)


# ─── Notifications API ──────────────────────────────────────────────

@app.route('/api/notifications', methods=['GET'])
@roles_required('student')
def get_notifications():
    db = get_db()
    rows = db.execute("""
        SELECT *
        FROM notifications
        WHERE user_type = 'student' AND (user_id IS NULL OR user_id = ?)
        ORDER BY created_at DESC
        LIMIT 20
    """, (session.get('user_id'),)).fetchall()
    return jsonify(dict_rows(rows))


@app.route('/api/notifications/mark-read', methods=['POST'])
@roles_required('student')
def mark_notifications_read():
    db = get_db()
    db.execute("""
        UPDATE notifications
        SET is_read = 1
        WHERE user_type = 'student' AND user_id = ?
    """, (session.get('user_id'),))
    db.commit()
    return jsonify({'status': 'success'})


@app.route('/api/notifications/<int:notification_id>', methods=['DELETE'])
@roles_required('student')
def delete_notification(notification_id):
    db = get_db()
    cursor = db.execute("""
        DELETE FROM notifications
        WHERE id = ?
          AND user_type = 'student'
          AND (user_id IS NULL OR user_id = ?)
    """, (notification_id, session.get('user_id')))
    db.commit()
    if cursor.rowcount == 0:
        return jsonify({'error': 'Notification not found'}), 404
    return jsonify({'status': 'success'})


@app.route('/api/notifications/clear', methods=['DELETE'])
@roles_required('student')
def clear_notifications():
    db = get_db()
    db.execute("""
        DELETE FROM notifications
        WHERE user_type = 'student'
          AND (user_id IS NULL OR user_id = ?)
    """, (session.get('user_id'),))
    db.commit()
    return jsonify({'status': 'success'})


# ─── Internal Helpers ────────────────────────────────────────────────

def _load_scheduling_data(db):
    return {
        'semesters': dict_rows(db.execute("SELECT * FROM semesters").fetchall()),
        'subjects': dict_rows(db.execute("SELECT * FROM subjects").fetchall()),
        'faculty': dict_rows(db.execute("SELECT * FROM faculty").fetchall()),
        'faculty_subjects': dict_rows(db.execute("SELECT * FROM faculty_subjects").fetchall()),
        'classrooms': dict_rows(db.execute("SELECT * FROM classrooms WHERE is_active=1").fetchall()),
        'timeslots': dict_rows(db.execute("SELECT * FROM timeslots ORDER BY slot_number").fetchall()),
        'faculty_availability': dict_rows(db.execute("SELECT * FROM faculty_availability").fetchall()),
        'history': dict_rows(db.execute("SELECT * FROM timetable_history").fetchall()),
        'days': [0, 1, 2, 3, 4],
    }


def _get_next_version(db):
    row = db.execute("SELECT MAX(timetable_version) FROM timetable_entries").fetchone()
    return (row[0] or 0) + 1


def _save_timetable(db, schedule, version):
    for entry in schedule:
        db.execute("""
            INSERT INTO timetable_entries
            (timetable_version, semester_id, subject_id, faculty_id, classroom_id, day_of_week, timeslot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (version, entry['semester_id'], entry['subject_id'], entry['faculty_id'],
              entry['classroom_id'], entry['day_of_week'], entry['timeslot_id']))
    db.commit()


def _log_generation(db, version, result):
    analytics = result.get('analytics', {})
    steps = result.get('steps', [])
    algo_names = ', '.join(s['name'] for s in steps)
    db.execute("""
        INSERT INTO generation_logs
        (timetable_version, algorithm_used, fitness_score, conflicts_resolved, generation_time_seconds)
        VALUES (?, ?, ?, ?, ?)
    """, (version, algo_names, analytics.get('fitness_score', 0),
          analytics.get('conflicts', 0), analytics.get('generation_time_seconds', 0)))
    db.commit()


def _notify_students_timetable_generated(db, version):
    student_users = db.execute(
        "SELECT id, linked_id FROM users WHERE role = 'student'"
    ).fetchall()
    for user in student_users:
        semester_suffix = f" for semester {user['linked_id']}" if user['linked_id'] else ""
        message = f"New timetable version {version} is available{semester_suffix}. Please check your dashboard."
        db.execute(
            """
            INSERT INTO notifications (user_type, user_id, message, is_read)
            VALUES (?, ?, ?, 0)
            """,
            ('student', user['id'], message),
        )
    db.commit()


# ─── Main ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    init_db()
    app.run(debug=True, port=5000)
