/**
 * Smart Classroom Timetable Scheduler - Frontend Application
 * Handles all UI interactions, API calls, and dynamic rendering.
 */

const API = {
    async request(url, method = 'GET', body = null) {
        const opts = { method, headers: { 'Content-Type': 'application/json' } };
        if (body) opts.body = JSON.stringify(body);
        const res = await fetch(url, opts);
        const contentType = res.headers.get('content-type') || '';
        const data = contentType.includes('application/json')
            ? await res.json()
            : { error: await res.text() };

        if (res.status === 401 && url !== '/api/login') {
            window.location.href = '/login';
            return null;
        }

        if (!res.ok) {
            return {
                status: 'error',
                error: data?.error || data?.message || `Request failed (${res.status})`,
            };
        }

        return data;
    },
    get: (url) => API.request(url),
    post: (url, body) => API.request(url, 'POST', body),
    put: (url, body) => API.request(url, 'PUT', body),
    del: (url) => API.request(url, 'DELETE'),
};

const DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'];
const DAY_SHORT = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
let ADMIN_SWAP_REQUESTS = [];

// ─── Tab Management ─────────────────────────────────────────

function initTabs() {
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const group = tab.closest('.tabs');
            const panel = tab.dataset.tab;
            group.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            const target = document.getElementById(panel);
            if (target) target.classList.add('active');
            if (typeof tabChanged === 'function') tabChanged(panel);
        });
    });
}

// ─── Modal Management ───────────────────────────────────────

function openModal(id) {
    document.getElementById(id)?.classList.add('active');
}

function closeModal(id) {
    document.getElementById(id)?.classList.remove('active');
}

// ─── Alert Helper ───────────────────────────────────────────

function showAlert(container, message, type = 'info') {
    const el = document.getElementById(container);
    if (!el) return;
    el.innerHTML = `<div class="alert alert-${type}">${message}</div>`;
    setTimeout(() => { el.innerHTML = ''; }, 5000);
}

// ─── Dashboard Module ───────────────────────────────────────

async function loadDashboard() {
    const stats = await API.get('/api/analytics/overview');
    if (!stats || stats.error) return;

    const map = {
        'stat-departments': stats.departments,
        'stat-courses': stats.courses,
        'stat-subjects': stats.subjects,
        'stat-faculty': stats.faculty,
        'stat-classrooms': stats.classrooms,
        'stat-entries': stats.timetable_entries,
    };
    Object.entries(map).forEach(([id, val]) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val || 0;
    });

    loadFacultyWorkload();
    loadRoomUtilization();
    loadAnalyticsPanels();
    loadAdminNotifications();
}

async function loadFacultyWorkload() {
    const data = await API.get('/api/analytics/faculty-workload');
    const tbody = document.getElementById('workload-body');
    if (!tbody || !Array.isArray(data)) return;

    tbody.innerHTML = data.map(f => {
        const pct = f.max_hours_per_week > 0 ? Math.round(f.assigned_hours / f.max_hours_per_week * 100) : 0;
        const color = pct > 90 ? 'var(--danger)' : pct > 70 ? 'var(--warning)' : 'var(--success)';
        return `<tr>
            <td>${f.name}</td>
            <td>${f.assigned_hours} / ${f.max_hours_per_week}</td>
            <td>${f.active_days}</td>
            <td>
                <div class="progress-bar"><div class="fill" style="width:${pct}%;background:${color}"></div></div>
                <span class="text-muted" style="font-size:0.75rem">${pct}%</span>
            </td>
        </tr>`;
    }).join('');
}

async function loadRoomUtilization() {
    const data = await API.get('/api/analytics/room-utilization');
    const tbody = document.getElementById('room-util-body');
    if (!tbody || !Array.isArray(data)) return;

    tbody.innerHTML = data.map(r => {
        const color = r.utilization_pct > 80 ? 'var(--danger)' : r.utilization_pct > 50 ? 'var(--warning)' : 'var(--success)';
        return `<tr>
            <td>${r.name}</td>
            <td><span class="badge badge-info">${r.room_type}</span></td>
            <td>${r.capacity}</td>
            <td>${r.used_slots} / ${r.total_slots}</td>
            <td>
                <div class="progress-bar"><div class="fill" style="width:${r.utilization_pct}%;background:${color}"></div></div>
                <span class="text-muted" style="font-size:0.75rem">${r.utilization_pct}%</span>
            </td>
        </tr>`;
    }).join('');
}

async function loadAnalyticsPanels() {
    const [workload, rooms] = await Promise.all([
        API.get('/api/analytics/faculty-workload'),
        API.get('/api/analytics/room-utilization'),
    ]);

    renderAnalyticsWorkload(workload);
    renderAnalyticsRooms(rooms);
}

function renderAnalyticsWorkload(data) {
    const el = document.getElementById('analytics-workload');
    if (!el || !Array.isArray(data)) return;

    if (data.length === 0) {
        el.innerHTML = '<p class="text-muted">No faculty workload data available.</p>';
        return;
    }

    const rows = data
        .slice()
        .sort((a, b) => (b.assigned_hours || 0) - (a.assigned_hours || 0))
        .map(f => {
            const pct = f.max_hours_per_week > 0
                ? Math.round((f.assigned_hours || 0) / f.max_hours_per_week * 100)
                : 0;
            return `<tr>
                <td>${f.name}</td>
                <td>${f.assigned_hours} hrs</td>
                <td>${f.active_days} days</td>
                <td>${pct}%</td>
            </tr>`;
        }).join('');

    el.innerHTML = `
        <table class="data-table">
            <thead><tr><th>Faculty</th><th>Assigned</th><th>Days</th><th>Load</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

function renderAnalyticsRooms(data) {
    const el = document.getElementById('analytics-rooms');
    if (!el || !Array.isArray(data)) return;

    if (data.length === 0) {
        el.innerHTML = '<p class="text-muted">No room utilization data available.</p>';
        return;
    }

    const rows = data
        .slice()
        .sort((a, b) => (b.utilization_pct || 0) - (a.utilization_pct || 0))
        .map(r => `<tr>
            <td>${r.name}</td>
            <td>${r.room_type}</td>
            <td>${r.used_slots}/${r.total_slots}</td>
            <td>${r.utilization_pct}%</td>
        </tr>`).join('');

    el.innerHTML = `
        <table class="data-table">
            <thead><tr><th>Room</th><th>Type</th><th>Usage</th><th>Rate</th></tr></thead>
            <tbody>${rows}</tbody>
        </table>
    `;
}

// ─── Data Management (CRUD) ─────────────────────────────────

async function loadDataTable(endpoint, bodyId, columns, actions = '') {
    const data = await API.get(endpoint);
    const tbody = document.getElementById(bodyId);
    if (!tbody || !Array.isArray(data)) return;

    if (data.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${columns.length + (actions ? 1 : 0)}" class="text-center text-muted">No data found</td></tr>`;
        return;
    }

    tbody.innerHTML = data.map(row => {
        const cells = columns.map(col => `<td>${col.render ? col.render(row) : (row[col.key] ?? '')}</td>`).join('');
        const actCell = actions ? `<td>${actions.replace(/\{id\}/g, row.id)}</td>` : '';
        return `<tr>${cells}${actCell}</tr>`;
    }).join('');
}

function loadDepartments() {
    loadDataTable('/api/departments', 'dept-body', [
        { key: 'name' }, { key: 'code' }, { key: 'head_of_department' }
    ], `<button class="btn btn-danger btn-sm" onclick="deleteDept({id})">Delete</button>`);
}

function loadCourses() {
    loadDataTable('/api/courses', 'course-body', [
        { key: 'name' }, { key: 'code' }, { key: 'department_name' },
        { key: 'semester_count' }
    ]);
}

function loadSubjects() {
    loadDataTable('/api/subjects', 'subject-body', [
        { key: 'name' }, { key: 'code' },
        { key: 'course_name', render: r => `${r.course_name} (Sem ${r.semester_number})` },
        { key: 'lectures_per_week' },
        { key: 'is_lab', render: r => r.is_lab ? '<span class="badge badge-success">Lab</span>' : 'Lecture' },
        { key: 'priority' }
    ]);
}

function loadFaculty() {
    loadDataTable('/api/faculty', 'faculty-body', [
        { key: 'name' }, { key: 'email' }, { key: 'department_name' },
        { key: 'designation' },
        { key: 'max_hours_per_week', render: r => `${r.max_hours_per_day}h/day, ${r.max_hours_per_week}h/week` }
    ]);
}

function loadClassrooms() {
    loadDataTable('/api/classrooms', 'classroom-body', [
        { key: 'name' }, { key: 'building' },
        { key: 'capacity' },
        { key: 'room_type', render: r => `<span class="badge badge-info">${r.room_type}</span>` },
        { key: 'has_projector', render: r => r.has_projector ? 'Yes' : 'No' },
        { key: 'has_ac', render: r => r.has_ac ? 'Yes' : 'No' }
    ]);
}

async function deleteDept(id) {
    if (!confirm('Delete this department?')) return;
    const result = await API.del(`/api/departments/${id}`);
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    loadDepartments();
}

// ─── Form Submissions ───────────────────────────────────────

async function submitDepartment(e) {
    e.preventDefault();
    const form = e.target;
    const result = await API.post('/api/departments', {
        name: form.name.value, code: form.code.value,
        head_of_department: form.head.value
    });
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    closeModal('modal-dept');
    form.reset();
    loadDepartments();
    showAlert('alert-area', 'Department added successfully', 'success');
}

async function submitCourse(e) {
    e.preventDefault();
    const form = e.target;
    const result = await API.post('/api/courses', {
        name: form.name.value, code: form.code.value,
        department_id: parseInt(form.department_id.value),
        semester_count: parseInt(form.semester_count.value)
    });
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    closeModal('modal-course');
    form.reset();
    loadCourses();
    showAlert('alert-area', 'Course added successfully', 'success');
}

async function submitSubject(e) {
    e.preventDefault();
    const form = e.target;
    const result = await API.post('/api/subjects', {
        name: form.name.value, code: form.code.value,
        semester_id: parseInt(form.semester_id.value),
        lectures_per_week: parseInt(form.lectures_per_week.value),
        is_lab: form.is_lab.checked ? 1 : 0,
        priority: parseInt(form.priority.value)
    });
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    closeModal('modal-subject');
    form.reset();
    loadSubjects();
}

async function submitFaculty(e) {
    e.preventDefault();
    const form = e.target;
    const result = await API.post('/api/faculty', {
        name: form.name.value, email: form.email.value,
        department_id: parseInt(form.department_id.value),
        designation: form.designation.value,
        max_hours_per_day: parseInt(form.max_day.value),
        max_hours_per_week: parseInt(form.max_week.value)
    });
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    closeModal('modal-faculty');
    form.reset();
    loadFaculty();
}

async function submitClassroom(e) {
    e.preventDefault();
    const form = e.target;
    const result = await API.post('/api/classrooms', {
        name: form.name.value, building: form.building.value,
        floor: parseInt(form.floor.value), capacity: parseInt(form.capacity.value),
        room_type: form.room_type.value,
        has_projector: form.has_projector.checked ? 1 : 0,
        has_ac: form.has_ac.checked ? 1 : 0
    });
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    closeModal('modal-classroom');
    form.reset();
    loadClassrooms();
}

// ─── Timetable Generation ───────────────────────────────────

async function generateTimetable() {
    const btn = document.getElementById('btn-generate');
    const stepsEl = document.getElementById('pipeline-steps');
    const resultEl = document.getElementById('gen-result');

    btn.disabled = true;
    btn.textContent = 'Generating...';
    stepsEl.innerHTML = `
        <div class="step running"><div class="step-icon">1</div><div class="step-info"><div class="step-name">Pattern Learning (Decision Tree)</div><div class="step-detail">Analyzing historical data...</div></div></div>
        <div class="step"><div class="step-icon">2</div><div class="step-info"><div class="step-name">Room Clustering (K-Means)</div><div class="step-detail">Waiting...</div></div></div>
        <div class="step"><div class="step-icon">3</div><div class="step-info"><div class="step-name">CSP Solver</div><div class="step-detail">Waiting...</div></div></div>
        <div class="step"><div class="step-icon">4</div><div class="step-info"><div class="step-name">Genetic Algorithm</div><div class="step-detail">Waiting...</div></div></div>
    `;

    const useML = document.getElementById('cfg-ml')?.checked ?? true;
    const gens = parseInt(document.getElementById('cfg-gens')?.value || 80);
    const pop = parseInt(document.getElementById('cfg-pop')?.value || 25);

    try {
        const result = await API.post('/api/generate', {
            use_ml: useML, ga_generations: gens, ga_population: pop
        });

        if (result && result.status === 'success') {
            const steps = result.steps || [];
            stepsEl.innerHTML = steps.map((s, i) => {
                const cls = s.result === 'success' ? 'done' : s.result.includes('error') ? 'error' : 'done';
                return `<div class="step ${cls}">
                    <div class="step-icon">${i + 1}</div>
                    <div class="step-info">
                        <div class="step-name">${s.name}</div>
                        <div class="step-detail">${s.result} - ${s.duration}s</div>
                    </div>
                </div>`;
            }).join('');

            const a = result.analytics;
            resultEl.innerHTML = `
                <div class="alert alert-success">
                    Timetable v${result.timetable_version} generated successfully!
                </div>
                <div class="stats-grid" style="grid-template-columns: repeat(4, 1fr);">
                    <div class="stat-card"><div class="stat-value">${a.total_entries}</div><div class="stat-label">Total Classes</div></div>
                    <div class="stat-card"><div class="stat-value">${a.fitness_score}</div><div class="stat-label">Fitness Score</div></div>
                    <div class="stat-card"><div class="stat-value">${a.conflicts}</div><div class="stat-label">Conflicts</div></div>
                    <div class="stat-card"><div class="stat-value">${a.generation_time_seconds}s</div><div class="stat-label">Generation Time</div></div>
                </div>`;

            if (result.ml_insights) {
                const fi = result.ml_insights.feature_importance;
                if (fi && Object.keys(fi).length > 0) {
                    resultEl.innerHTML += `<div class="panel mt-2"><div class="panel-header"><h3>ML Feature Importance</h3></div><div class="panel-body">
                        <table class="data-table"><thead><tr><th>Feature</th><th>Importance</th></tr></thead><tbody>
                        ${Object.entries(fi).sort((a, b) => b[1] - a[1]).map(([k, v]) =>
                            `<tr><td>${k}</td><td><div class="progress-bar" style="width:200px;display:inline-block"><div class="fill" style="width:${v * 100}%"></div></div> ${(v * 100).toFixed(1)}%</td></tr>`
                        ).join('')}
                        </tbody></table></div></div>`;
                }
            }
        } else {
            resultEl.innerHTML = `<div class="alert alert-danger">Generation failed: ${result?.error || 'Unknown error'}</div>`;
        }
    } catch (err) {
        resultEl.innerHTML = `<div class="alert alert-danger">Error: ${err.message}</div>`;
    }

    btn.disabled = false;
    btn.textContent = 'Generate Timetable';
}

// ─── Timetable Display ──────────────────────────────────────

async function loadTimetable(semesterId, facultyId) {
    let url = '/api/timetable?';
    if (semesterId) url += `semester_id=${semesterId}&`;
    if (facultyId) url += `faculty_id=${facultyId}&`;

    const entries = await API.get(url);
    const timeslots = await API.get('/api/timeslots');

    return {
        entries: Array.isArray(entries) ? entries : [],
        timeslots: Array.isArray(timeslots) ? timeslots : [],
    };
}

function renderTimetableGrid(container, entries, timeslots, emptyMessage = 'No timetable generated yet. Go to Generate tab to create one.') {
    const el = document.getElementById(container);
    if (!el) return;

    if (!entries || entries.length === 0) {
        el.innerHTML = `<div class="empty-state"><div class="icon">&#128197;</div><p>${emptyMessage}</p></div>`;
        return;
    }

    let html = '<div class="timetable-grid">';
    html += '<div class="header-cell">Time</div>';
    DAYS.forEach(d => { html += `<div class="header-cell">${d}</div>`; });

    const lookup = {};
    entries.forEach(e => {
        const key = `${e.day_of_week}-${e.timeslot_id}`;
        if (!lookup[key]) lookup[key] = [];
        lookup[key].push(e);
    });

    timeslots.forEach(slot => {
        if (slot.is_break) {
            html += `<div class="time-cell">${slot.start_time}-${slot.end_time}</div>`;
            for (let d = 0; d < 5; d++) {
                html += `<div class="break-cell">${slot.label || 'Break'}</div>`;
            }
        } else {
            html += `<div class="time-cell">${slot.start_time}<br>${slot.end_time}</div>`;
            for (let d = 0; d < 5; d++) {
                const classes = lookup[`${d}-${slot.id}`] || [];
                html += '<div class="cell">';
                classes.forEach(c => {
                    const cls = c.is_lab ? 'lab' : '';
                    html += `<div class="class-block ${cls}">
                        <div class="subject">${c.subject_code}</div>
                        <div class="details">${c.faculty_name}<br>${c.classroom_name}</div>
                    </div>`;
                });
                html += '</div>';
            }
        }
    });

    html += '</div>';
    el.innerHTML = html;
}

// ─── Semester/Faculty dropdowns ─────────────────────────────

async function populateFilters() {
    const semesters = await API.get('/api/semesters');
    const faculty = await API.get('/api/faculty');
    const semesterList = Array.isArray(semesters) ? semesters : [];
    const facultyList = Array.isArray(faculty) ? faculty : [];

    document.querySelectorAll('.semester-select').forEach(sel => {
        const current = sel.value;
        sel.innerHTML = '<option value="">All Semesters</option>' +
            semesterList.map(s => `<option value="${s.id}">${s.course_name} - Sem ${s.semester_number}</option>`).join('');
        if (current) sel.value = current;
    });

    document.querySelectorAll('.faculty-select').forEach(sel => {
        const current = sel.value;
        sel.innerHTML = '<option value="">All Faculty</option>' +
            facultyList.map(f => `<option value="${f.id}">${f.name}</option>`).join('');
        if (current) sel.value = current;
    });

    const depts = await API.get('/api/departments');
    const departmentList = Array.isArray(depts) ? depts : [];
    document.querySelectorAll('.dept-select').forEach(sel => {
        sel.innerHTML = '<option value="">Select Department</option>' +
            departmentList.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
    });

    document.querySelectorAll('.semester-id-select').forEach(sel => {
        sel.innerHTML = '<option value="">Select Semester</option>' +
            semesterList.map(s => `<option value="${s.id}">${s.course_name} - Sem ${s.semester_number} (${s.academic_year})</option>`).join('');
    });
}

// ─── View Timetable with Filters ────────────────────────────

async function viewFilteredTimetable() {
    const semId = document.getElementById('filter-semester')?.value;
    const facId = document.getElementById('filter-faculty')?.value;
    const { entries, timeslots } = await loadTimetable(semId || null, facId || null);
    let emptyMessage = 'No timetable generated yet. Go to Generate tab to create one.';
    if (semId && facId) {
        emptyMessage = 'No classes match this semester and faculty combination. Try changing one of the filters.';
    } else if (semId) {
        emptyMessage = 'No classes found for the selected semester.';
    } else if (facId) {
        emptyMessage = 'No classes found for the selected faculty.';
    }
    renderTimetableGrid('timetable-display', entries, timeslots, emptyMessage);
}

// ─── Login ──────────────────────────────────────────────────

async function handleLogin(e) {
    e.preventDefault();
    const form = e.target;
    const result = await API.post('/api/login', {
        username: form.username.value.trim(),
        password: form.password.value
    });

    if (result && result.status === 'success') {
        if (result.role === 'faculty') window.location.href = '/faculty-view';
        else if (result.role === 'student') window.location.href = '/student-view';
        else window.location.href = '/dashboard';
    } else {
        showAlert('login-alert', result?.message || 'Invalid credentials', 'danger');
    }
}

function toggleLoginPassword(checkbox) {
    const form = checkbox?.closest('form');
    const passwordInput = form?.querySelector('input[name="password"]');
    if (!passwordInput) return;
    passwordInput.type = checkbox.checked ? 'text' : 'password';
}

async function logout() {
    await API.post('/api/logout');
    window.location.href = '/login';
}

// ─── Swap Requests ──────────────────────────────────────────

async function loadSwapRequests() {
    const data = await API.get('/api/swap-requests');
    const tbody = document.getElementById('swap-body');
    if (!tbody || !Array.isArray(data)) return;
    ADMIN_SWAP_REQUESTS = data;
    updateAdminNotificationBadge();
    renderAdminNotifications();

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No swap requests</td></tr>';
        return;
    }

    tbody.innerHTML = data.map(r => `<tr>
        <td>${r.faculty_name}</td>
        <td>${r.subject_name}</td>
        <td>${r.reason || '-'}</td>
        <td><span class="badge badge-${r.status === 'approved' ? 'success' : r.status === 'rejected' ? 'danger' : 'warning'}">${r.status}</span></td>
        <td>${r.status === 'pending' ? `
            <button class="btn btn-success btn-sm" onclick="approveSwap(${r.id})">Approve</button>
            <button class="btn btn-danger btn-sm" onclick="rejectSwap(${r.id})">Reject</button>
        ` : ''}
            <button class="btn btn-secondary btn-sm" onclick="deleteSwapRequest(${r.id})">Clear</button>
        </td>
    </tr>`).join('');
}

async function approveSwap(id) {
    await API.post(`/api/swap-requests/${id}/approve`);
    loadSwapRequests();
}

async function rejectSwap(id) {
    await API.post(`/api/swap-requests/${id}/reject`);
    loadSwapRequests();
}

async function loadAdminNotifications() {
    if (!document.getElementById('admin-notif-list')) return;
    await loadSwapRequests();
}

function updateAdminNotificationBadge() {
    const badge = document.getElementById('admin-notif-badge');
    if (!badge) return;
    const pendingCount = ADMIN_SWAP_REQUESTS.filter(r => r.status === 'pending').length;
    badge.textContent = pendingCount;
    badge.style.display = pendingCount > 0 ? 'inline-flex' : 'none';
}

function renderAdminNotifications() {
    const el = document.getElementById('admin-notif-list');
    if (!el) return;
    const pendingRequests = ADMIN_SWAP_REQUESTS.filter(r => r.status === 'pending');

    if (pendingRequests.length === 0) {
        el.innerHTML = `<div class="empty-state"><div class="icon">&#128276;</div><p>No new swap request notifications.</p></div>`;
        return;
    }

    el.innerHTML = pendingRequests.map(r => `
        <div class="alert alert-warning notification-card admin-notification-card" style="margin-bottom:0.75rem;">
            <div style="display:flex; justify-content:space-between; gap:1rem; align-items:flex-start;">
                <div>
                    <strong>New swap request from ${r.faculty_name}</strong>
                    <div style="margin-top:0.35rem;">${r.subject_name}: ${r.reason || 'No reason provided.'}</div>
                </div>
                <div class="notification-card-actions">
                    <span class="badge badge-warning">Pending</span>
                    <div class="admin-notification-buttons">
                        <button class="btn btn-success btn-sm" onclick="approveSwap(${r.id})">Approve</button>
                        <button class="btn btn-danger btn-sm" onclick="rejectSwap(${r.id})">Reject</button>
                        <button class="btn btn-secondary btn-sm" onclick="deleteSwapRequest(${r.id})">Clear</button>
                    </div>
                </div>
            </div>
        </div>
    `).join('');
}

async function deleteSwapRequest(id) {
    if (!confirm('Clear this swap request from the dashboard?')) return;
    const result = await API.del(`/api/swap-requests/${id}`);
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    showAlert('alert-area', 'Swap request cleared successfully', 'success');
    loadSwapRequests();
}

async function clearAllSwapRequests() {
    if (ADMIN_SWAP_REQUESTS.length === 0) return;
    if (!confirm('Clear the full swap request list from the dashboard?')) return;
    const result = await API.del('/api/swap-requests/clear');
    if (result?.error) {
        showAlert('alert-area', result.error, 'danger');
        return;
    }
    ADMIN_SWAP_REQUESTS = [];
    updateAdminNotificationBadge();
    renderAdminNotifications();
    showAlert('alert-area', 'Swap request list cleared successfully', 'success');
    loadSwapRequests();
}

// ─── Init ───────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
    initTabs();
});

