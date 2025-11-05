from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import init_db, get_db_connection
from models import User, Class, Subject, Result, Enrollment, Student
from auth import LoginUser
import sqlite3
from excel_utils import ExcelImporter
import os
import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
#
# >>> FIX: Removed the hidden invalid character from this line
#
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return LoginUser.get(user_id)

# Initialize database
init_db()

# Routes
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif current_user.role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        elif current_user.role == 'student':
            return redirect(url_for('student_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.get_by_username(username)
        
        if user and check_password_hash(user.password, password):
            login_user_obj = LoginUser(user.id, user.username, user.role, user.name)
            login_user(login_user_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

# Admin Routes
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total_students = cursor.execute('SELECT COUNT(*) FROM users WHERE role = "student"').fetchone()[0]
    total_teachers = cursor.execute('SELECT COUNT(*) FROM users WHERE role = "teacher"').fetchone()[0]
    total_classes = cursor.execute('SELECT COUNT(*) FROM classes').fetchone()[0]
    total_subjects = cursor.execute('SELECT COUNT(*) FROM subjects').fetchone()[0]
    
    overall_stats_query = '''
        SELECT 
            COUNT(*) as total_results,
            AVG((marks_obtained * 100.0) / total_marks) as average_percentage,
            MAX((marks_obtained * 100.0) / total_marks) as topper_score
        FROM results
    '''
    overall_stats_raw = cursor.execute(overall_stats_query).fetchone()
    
    if overall_stats_raw['total_results'] == 0:
        overall_stats = {
            'total_results': 0, 'average_percentage': 0, 'pass_percentage': 0, 'topper_score': 0
        }
    else:
        pass_percentage_raw = cursor.execute(
            'SELECT (SELECT COUNT(*) FROM results WHERE (marks_obtained * 100.0) / total_marks >= 50) * 100.0 / COUNT(*) FROM results'
        ).fetchone()[0]
        overall_stats = dict(overall_stats_raw)
        overall_stats['pass_percentage'] = pass_percentage_raw or 0
    
    subject_performance = cursor.execute('''
        SELECT 
            s.subject_name as name, s.subject_code as code,
            AVG((r.marks_obtained * 100.0) / r.total_marks) as average,
            COUNT(DISTINCT r.student_id) as student_count
        FROM results r JOIN subjects s ON r.subject_id = s.id
        GROUP BY s.id, s.subject_name, s.subject_code ORDER BY average DESC
    ''').fetchall()
    
    class_performance = cursor.execute('''
        SELECT 
            c.class_name, c.section,
            AVG((r.marks_obtained * 100.0) / r.total_marks) as average,
            COUNT(DISTINCT r.student_id) as student_count
        FROM results r JOIN classes c ON r.class_id = c.id
        GROUP BY c.id, c.class_name, c.section ORDER BY average DESC
    ''').fetchall()
    
    recent_results = cursor.execute('''
        SELECT 
            r.*, s.subject_name, u.name as student_name,
            u.username as student_username, c.class_name, c.section
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        ORDER BY r.created_at DESC LIMIT 10
    ''').fetchall()
    
    top_performers = cursor.execute('''
        SELECT 
            u.name as student_name, c.class_name, c.section,
            AVG((r.marks_obtained * 100.0) / r.total_marks) as average_percentage
        FROM results r
        JOIN users u ON r.student_id = u.id
        JOIN student_enrollment se ON u.id = se.student_id
        JOIN classes c ON se.class_id = c.id
        GROUP BY r.student_id, u.name, c.class_name, c.section
        HAVING COUNT(DISTINCT r.subject_id) >= 3
        ORDER BY average_percentage DESC LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         total_students=total_students, total_teachers=total_teachers,
                         total_classes=total_classes, total_subjects=total_subjects,
                         overall_stats=overall_stats, subject_performance=subject_performance,
                         class_performance=class_performance, recent_results=recent_results,
                         top_performers=top_performers)

@app.route('/admin/manage_all_results')
@login_required
def manage_all_results():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    results = Result.get_all_results()
    
    return render_template('manage_results.html', 
                         results=results,
                         title="Manage All Results",
                         user_role='admin')

@app.route('/admin/manage_users')
@login_required
def manage_users():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    users = User.get_all_users()
    return render_template('manage_users.html', users=users)

@app.route('/admin/add_user', methods=['POST'])
@login_required
def add_user():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    username = request.form['username']
    password = request.form['password']
    role = request.form['role']
    name = request.form['name']
    email = request.form['email']
    
    if role == 'student':
        return jsonify({
            'success': False, 
            'message': 'Cannot add student from here. Please use the "Manage Students" page.'
        })

    user_id = User.create_user(username, password, role, name, email)
    if user_id:
        flash('User created successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Username already exists!'})

@app.route('/admin/edit_user/<int:user_id>')
@login_required
def edit_user(user_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    user = User.get_by_id(user_id)
    if not user:
        flash('User not found!', 'danger')
        return redirect(url_for('manage_users'))
    
    if user.role == 'student':
        student_profile = Student.get_student_by_user_id(user_id)
        if student_profile:
            return redirect(url_for('edit_student', student_id=student_profile['id']))
        else:
            flash('This student has no profile. Editing basic user info.', 'warning')
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/update_user/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    user = User.get_by_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': 'User not found!'})

    role = request.form['role']
    if user.role == 'student' and role != 'student':
        return jsonify({'success': False, 'message': 'Cannot change role from student. Delete and recreate as new user.'})
    if user.role != 'student' and role == 'student':
         return jsonify({'success': False, 'message': 'Cannot change role to student. Use "Manage Students" to create new students.'})

    username = request.form['username']
    name = request.form['name']
    email = request.form['email']
    password = request.form.get('password', '')
    
    success = User.update_user(user_id, username, role, name, email, password if password else None)
    if success:
        flash('User updated successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Username already exists!'})

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    success, message = User.delete_user(user_id)
    if success:
        flash('User deleted successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/admin/manage_subjects_master')
@login_required
def manage_subjects_master():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    subjects = Subject.get_all_subjects()
    return render_template('manage_subjects.html', subjects=subjects)


@app.route('/admin/add_subject_master', methods=['POST'])
@login_required
def add_subject_master():
    subject_name = request.form['subject_name']
    subject_code = request.form['subject_code']
    
    subject_id = Subject.create_subject(subject_name, subject_code)
    if subject_id:
        flash('Subject created successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Subject name or code already exists!'})


@app.route('/admin/edit_subject_master/<int:subject_id>')
@login_required
def edit_subject_master(subject_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    subject = Subject.get_subject_by_id(subject_id)
    if not subject:
        flash('Subject not found!', 'danger')
        return redirect(url_for('manage_subjects_master'))
    
    all_teachers = User.get_teachers()
    assigned_teachers_raw = Subject.get_teachers_for_subject(subject_id)
    assigned_teacher_ids = {t['id'] for t in assigned_teachers_raw}
    
    return render_template('edit_subject.html', 
                         subject=subject,
                         all_teachers=all_teachers,
                         assigned_teacher_ids=assigned_teacher_ids)


@app.route('/admin/update_subject_master/<int:subject_id>', methods=['POST'])
@login_required
def update_subject_master(subject_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    subject_name = request.form['subject_name']
    subject_code = request.form['subject_code']
    success = Subject.update_subject(subject_id, subject_name, subject_code)
    
    if not success:
        return jsonify({'success': False, 'message': 'Subject name or code already exists!'})

    new_teacher_ids = set(request.form.getlist('teachers'))
    old_teachers_raw = Subject.get_teachers_for_subject(subject_id)
    old_teacher_ids = {str(t['id']) for t in old_teachers_raw}
    
    teachers_to_add = new_teacher_ids - old_teacher_ids
    teachers_to_remove = old_teacher_ids - new_teacher_ids
    
    for teacher_id in teachers_to_add:
        Subject.assign_teacher_to_subject(subject_id, int(teacher_id))
        
    for teacher_id in teachers_to_remove:
        Subject.remove_teacher_from_subject(subject_id, int(teacher_id))

    flash('Subject and teacher assignments updated successfully!', 'success')
    return jsonify({'success': True})


@app.route('/admin/delete_subject_master/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject_master(subject_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    success, message = Subject.delete_subject(subject_id)
    if success:
        flash('Subject deleted successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/admin/manage_classes')
@login_required
def manage_classes():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    classes = Class.get_all_classes()
    teachers = User.get_teachers()
    subjects = Subject.get_all_subjects() 
    
    return render_template('manage_classes.html', 
                         classes=classes, 
                         teachers=teachers, 
                         subjects=subjects)

@app.route('/admin/add_class', methods=['POST'])
@login_required
def add_class():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    class_name = request.form['class_name']
    section = request.form['section']
    teacher_id = request.form['teacher_id']
    subject_ids = request.form.getlist('subjects') 
    
    class_id, message = Class.create_class(class_name, section, teacher_id)
    
    if class_id:
        for subject_id in subject_ids:
            Class.add_subject_to_class(class_id, subject_id)
            
        flash('Class and assigned subjects created successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/admin/edit_class/<int:class_id>')
@login_required
def edit_class(class_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    class_data = Class.get_class_by_id(class_id)
    if not class_data:
        flash('Class not found!', 'danger')
        return redirect(url_for('manage_classes'))
    
    teachers = User.get_teachers()
    
    subjects_in_class_raw = Class.get_subjects_for_class(class_id)
    subjects_in_class_ids = {s['id'] for s in subjects_in_class_raw}
    
    all_subjects = Subject.get_all_subjects()
    
    return render_template('edit_class.html', 
                         class_data=class_data, 
                         teachers=teachers,
                         all_subjects=all_subjects,
                         subjects_in_class_ids=subjects_in_class_ids)

@app.route('/admin/update_class/<int:class_id>', methods=['POST'])
@login_required
def update_class(class_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    class_name = request.form['class_name']
    section = request.form['section']
    teacher_id = request.form['teacher_id']
    
    success, message = Class.update_class(class_id, class_name, section, teacher_id)
    
    if success:
        new_subject_ids = set(request.form.getlist('subjects'))
        old_subjects_raw = Class.get_subjects_for_class(class_id)
        old_subject_ids = {str(s['id']) for s in old_subjects_raw}
        
        subjects_to_add = new_subject_ids - old_subject_ids
        subjects_to_remove = old_subject_ids - new_subject_ids
        
        for sub_id in subjects_to_add:
            Class.add_subject_to_class(class_id, int(sub_id))
            
        for sub_id in subjects_to_remove:
            Class.remove_subject_from_class(class_id, int(sub_id))

        flash('Class updated successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/admin/delete_class/<int:class_id>', methods=['POST'])
@login_required
def delete_class(class_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    success, message = Class.delete_class(class_id)
    if success:
        flash('Class deleted successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})


@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    #
    # >>> FIX: This logic was mixed up. This is the correct logic.
    #
    if current_user.role == 'admin':
        return redirect(url_for('admin_dashboard'))
    elif current_user.role == 'student':
        return redirect(url_for('student_dashboard'))
    elif current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()

    subjects_taught = User.get_subjects_taught(current_user.id)
    
    total_students_query = '''
        SELECT COUNT(DISTINCT se.student_id)
        FROM student_enrollment se
        JOIN class_subjects cs ON se.class_id = cs.class_id
        JOIN teacher_subject_assignments tsa ON cs.subject_id = tsa.subject_id
        WHERE tsa.teacher_id = ?
    '''
    total_students = cursor.execute(total_students_query, (current_user.id,)).fetchone()[0] or 0
    
    total_results = cursor.execute('SELECT COUNT(*) FROM results WHERE teacher_id = ?', (current_user.id,)).fetchone()[0] or 0
    
    recent_results = cursor.execute('''
        SELECT r.*, s.subject_name, u.name as student_name, c.class_name, c.section
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        WHERE r.teacher_id = ?
        ORDER BY r.created_at DESC
        LIMIT 5
    ''', (current_user.id,)).fetchall()
    
    conn.close()
    
    return render_template('teacher_dashboard.html', 
                         subjects_taught=subjects_taught,
                         total_students=total_students,
                         total_results=total_results,
                         recent_results=recent_results)

#
# >>> FIX: This route was accidentally deleted. It's re-added now.
#
@app.route('/teacher/class_stats/<int:class_id>')
@login_required
def class_stats(class_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # A teacher might not be the class_teacher, so we check this
    class_info = cursor.execute(
        'SELECT * FROM classes WHERE id = ?', (class_id,)
    ).fetchone()

    # We also check if the teacher teaches *any* subject in this class
    subjects_taught_in_class = User.get_teachable_subjects_for_class(current_user.id, class_id)
    
    if not class_info or not subjects_taught_in_class:
        conn.close()
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    total_students = cursor.execute(
        'SELECT COUNT(*) FROM student_enrollment WHERE class_id = ?', (class_id,)
    ).fetchone()[0] or 0
    
    total_results = cursor.execute(
        'SELECT COUNT(*) FROM results WHERE class_id = ?', (class_id,)
    ).fetchone()[0] or 0
    
    average_result = cursor.execute('''
        SELECT AVG((marks_obtained * 100.0) / total_marks) as avg_percentage
        FROM results WHERE class_id = ?
    ''', (class_id,)).fetchone()
    average_percentage = round(average_result['avg_percentage'] or 0, 2)
    
    top_subjects = cursor.execute('''
        SELECT s.subject_name as name, 
               AVG((r.marks_obtained * 100.0) / r.total_marks) as average
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        WHERE r.class_id = ?
        GROUP BY s.subject_name
        ORDER BY average DESC
        LIMIT 3
    ''', (class_id,)).fetchall()
    
    conn.close()
    
    return jsonify({
        'success': True,
        'class_name': class_info['class_name'],
        'section': class_info['section'],
        'total_students': total_students,
        'total_results': total_results,
        'average_percentage': average_percentage,
        'top_subjects': [
            {'name': subject['name'], 'average': round(subject['average'], 2)}
            for subject in top_subjects
        ]
    })

@app.route('/teacher/manage_results_by_subject/<int:subject_id>')
@login_required
def teacher_manage_results_by_subject(subject_id):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
        
    subjects_taught_raw = User.get_subjects_taught(current_user.id)
    if subject_id not in {s['id'] for s in subjects_taught_raw}:
        flash('Access denied! You do not teach this subject.', 'danger')
        return redirect(url_for('teacher_dashboard'))
        
    subject = Subject.get_subject_by_id(subject_id)
    
    conn = get_db_connection()
    results = conn.execute('''
        SELECT r.*, s.subject_name, u.name as student_name, c.class_name, c.section,
               (r.marks_obtained * 100.0 / r.total_marks) as percentage
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        WHERE r.subject_id = ? AND r.teacher_id = ?
        ORDER BY c.class_name, c.section, u.name
    ''', (subject_id, current_user.id)).fetchall()
    conn.close()

    return render_template('manage_results.html',
                         results=results,
                         title=f"Manage Results for {subject['subject_name']}",
                         user_role='teacher')

@app.route('/edit_result/<int:result_id>', methods=['GET'])
@login_required
def edit_result(result_id):
    result = Result.get_result_by_id(result_id)

    if not result:
        flash('Result not found!', 'danger')
        return redirect(url_for('index'))

    if current_user.role == 'admin':
        pass 
    elif current_user.role == 'teacher' and result['teacher_id'] == current_user.id:
        pass 
    else:
        flash('Access denied! You can only edit results you entered.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    return render_template('edit_result.html', result=result)

@app.route('/update_result/<int:result_id>', methods=['POST'])
@login_required
def update_result(result_id):
    result = Result.get_result_by_id(result_id)

    if not result:
        flash('Result not found!', 'danger')
        return redirect(url_for('index'))

    if current_user.role != 'admin' and (current_user.role != 'teacher' or result['teacher_id'] != current_user.id):
        flash('Access denied! You can only edit results you entered.', 'danger')
        return redirect(url_for('teacher_dashboard'))

    marks_obtained = request.form.get('marks_obtained')
    total_marks = request.form.get('total_marks')
    exam_type = request.form.get('exam_type')
    academic_year = request.form.get('academic_year')
    
    success, message = Result.update_marks(
        result_id, marks_obtained, total_marks, exam_type, academic_year
    )
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'danger')

    if current_user.role == 'admin':
        return redirect(url_for('manage_all_results'))
    else:
        return redirect(url_for('teacher_manage_results_by_subject', subject_id=result['subject_id']))

@app.route('/delete_result/<int:result_id>', methods=['POST'])
@login_required
def delete_result(result_id):
    result = Result.get_result_by_id(result_id)

    if not result:
        return jsonify({'success': False, 'message': 'Result not found!'})

    if current_user.role != 'admin' and (current_user.role != 'teacher' or result['teacher_id'] != current_user.id):
        return jsonify({'success': False, 'message': 'Access denied!'})

    success, message = Result.delete_result(result_id)
    
    if success:
        flash(message, 'success')
    
    return jsonify({'success': success, 'message': message})

@app.route('/teacher/enter_marks_by_subject/<int:subject_id>')
@login_required
def enter_marks_by_subject(subject_id):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))

    subjects_taught_raw = User.get_subjects_taught(current_user.id)
    subjects_taught_ids = {s['id'] for s in subjects_taught_raw}
    
    if subject_id not in subjects_taught_ids:
        flash('Access denied! You are not assigned to teach this subject.', 'danger')
        return redirect(url_for('teacher_dashboard'))
        
    subject = Subject.get_subject_by_id(subject_id)

    classes_with_subject = Class.get_classes_for_subject(subject_id)
    
    students_by_class = []
    for c in classes_with_subject:
        students = User.get_students_in_class(c['id'])
        if students:
            students_by_class.append({
                'id': c['id'],
                'name': c['class_name'],
                'section': c['section'],
                'students': students
            })

    current_year = datetime.date.today().year
    academic_year = f"{current_year}-{current_year + 1}"
    
    return render_template('enter_marks_by_subject.html',
                         subject=subject,
                         students_by_class=students_by_class,
                         academic_year=academic_year)


@app.route('/teacher/submit_marks_by_subject/<int:subject_id>', methods=['POST'])
@login_required
def submit_marks_by_subject(subject_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Access denied!'})

    subjects_taught_raw = User.get_subjects_taught(current_user.id)
    if subject_id not in {s['id'] for s in subjects_taught_raw}:
        return jsonify({'success': False, 'message': 'Access denied! You do not teach this subject.'})

    try:
        exam_type = request.form.get('exam_type')
        academic_year = request.form.get('academic_year')
        
        if not exam_type or not academic_year:
            return jsonify({'success': False, 'message': 'Exam Type and Academic Year are required.'})
        
        student_ids = request.form.getlist('student_id')
        
        success_count = 0
        fail_count = 0
        
        for student_id_str in student_ids:
            student_id = int(student_id_str)
            marks = request.form.get(f'marks_{student_id}')
            total = request.form.get(f'total_{student_id}')
            class_id = request.form.get(f'class_{student_id}')
            
            if marks and total:
                try:
                    marks_obtained = float(marks)
                    total_marks = float(total)
                    class_id_int = int(class_id)
                    
                    result_id, message = Result.enter_marks(
                        student_id,
                        subject_id,
                        class_id_int,
                        current_user.id, 
                        marks_obtained,
                        total_marks,
                        exam_type,
                        academic_year
                    )
                    if result_id:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    fail_count += 1
        
        flash(f'Successfully submitted {success_count} results. Failed or skipped {fail_count} entries.', 'success')
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'message': f'An error occurred: {str(e)}'})

@app.route('/teacher/view_results_by_subject/<int:subject_id>')
@login_required
def view_results_by_subject(subject_id):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
        
    subjects_taught_raw = User.get_subjects_taught(current_user.id)
    if subject_id not in {s['id'] for s in subjects_taught_raw}:
        flash('Access denied! You do not teach this subject.', 'danger')
        return redirect(url_for('teacher_dashboard'))
        
    subject = Subject.get_subject_by_id(subject_id)
    
    conn = get_db_connection()
    results = conn.execute('''
        SELECT r.*, s.subject_name, u.name as student_name, c.class_name, c.section,
               (r.marks_obtained * 100.0 / r.total_marks) as percentage
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        WHERE r.subject_id = ? AND r.teacher_id = ?
        ORDER BY c.class_name, c.section, u.name
    ''', (subject_id, current_user.id)).fetchall()
    conn.close()

    #
    # >>> FIX: This was rendering the wrong template in your file
    #
    return render_template('manage_results.html',
                         results=results,
                         title=f"Manage Results for {subject['subject_name']}",
                         user_role='teacher')

# Student Routes
@app.route('/student_dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        return redirect(url_for('login'))
    
    student_user = User.get_by_id(current_user.id)
    student_details = Student.get_student_by_user_id(current_user.id)
    results = Result.get_student_results(current_user.id)
    
    student_data = {
        'full_name': student_user.name,
        'roll_number': student_details['roll_number'] if student_details else 'N/A',
        'class_name': student_details['class_name'] if student_details else 'N/A',
        'section': student_details['section'] if student_details else 'N/A'
    }
    
    results_data = []
    for result in results:
        percentage = 0
        if result['total_marks'] > 0:
            percentage = round((result['marks_obtained'] / result['total_marks']) * 100, 2)
            
        results_data.append({
            'code': result['subject_name'],
            'name': result['subject_name'],
            'marks': f"{result['marks_obtained']}/{result['total_marks']}",
            'percentage': percentage,
            'exam_type': result['exam_type'],
            'exam_date': result['exam_date']
        })
    
    return render_template('student_dashboard.html', 
                         student=student_data, 
                         results=results_data)

@app.route('/student/my_results')
@login_required
def my_results():
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    results = Result.get_student_results(current_user.id)
    
    total_marks_obtained = 0
    total_max_marks = 0
    
    for result in results:
        total_marks_obtained += result['marks_obtained']
        total_max_marks += result['total_marks']
    
    overall_percentage = (total_marks_obtained / total_max_marks * 100) if total_max_marks > 0 else 0
    
    return render_template('view_my_results.html', 
                         results=results, 
                         overall_percentage=round(overall_percentage, 2))


@app.route('/admin/upload_data')
@login_required
def upload_data():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    return render_template('upload_data.html')

@app.route('/admin/download_template/<template_type>')
@login_required
def download_template(template_type):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    file_data, filename = ExcelImporter.download_template(template_type)
    if file_data:
        from flask import send_file
        return send_file(
            file_data,
            download_name=filename,
            as_attachment=True,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
    else:
        flash('Error generating template', 'danger')
        return redirect(url_for('upload_data'))

@app.route('/admin/upload_users', methods=['POST'])
@login_required
def upload_users():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'})
    
    try:
        success, message = ExcelImporter.import_users(file)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

@app.route('/admin/upload_subjects', methods=['POST'])
@login_required
def upload_subjects():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'})
    
    try:
        success, message = ExcelImporter.import_subjects(file)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

@app.route('/admin/upload_students', methods=['POST'])
@login_required
def upload_students():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'})
    
    try:
        success, message = ExcelImporter.import_students(file)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

@app.route('/admin/upload_classes', methods=['POST'])
@login_required
def upload_classes():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'})
    
    try:
        success, message = ExcelImporter.import_classes(file)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

@app.route('/admin/upload_results', methods=['POST'])
@login_required
def upload_results():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
    
    if not file.filename.endswith(('.xlsx', '.xls')):
        return jsonify({'success': False, 'message': 'Please upload an Excel file (.xlsx or .xls)'})
    
    try:
        success, message = ExcelImporter.import_results(file)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing file: {str(e)}'})

@app.route('/teacher/upload_results', methods=['GET', 'POST'])
@login_required
def teacher_upload_results():
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'danger')
            return redirect(url_for('teacher_upload_results'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('teacher_upload_results'))
        
        if not file.filename.endswith(('.xlsx', '.xls')):
            flash('Please upload an Excel file (.xlsx or .xls)', 'danger')
            return redirect(url_for('teacher_upload_results'))
        
        try:
            success, message = ExcelImporter.import_results(file)
            if success:
                flash(message, 'success')
            else:
                flash(message, 'danger')
        except Exception as e:
            flash(f'Error processing file: {str(e)}', 'danger')
        
        return redirect(url_for('teacher_upload_results'))
    
    subjects_taught = User.get_subjects_taught(current_user.id)
    
    return render_template('teacher_upload_results.html', subjects=subjects_taught)


@app.route('/admin/manage_students')
@login_required
def manage_students():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    students = Student.get_all_students()
    classes = Class.get_all_classes()
    
    current_year = datetime.date.today().year
    academic_year = f"{current_year}-{current_year + 1}"
    
    return render_template('manage_students.html', 
                         students=students, 
                         classes=classes,
                         academic_year=academic_year)

@app.route('/admin/add_student', methods=['POST'])
@login_required
def add_student():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    full_name = request.form['full_name']
    gender = request.form['gender']
    date_of_birth = request.form['date_of_birth']
    class_id = request.form['class_id']
    roll_number = request.form['roll_number']
    fathers_name = request.form['fathers_name']
    mobile_number = request.form['mobile_number']
    mothers_name = request.form['mothers_name']
    email = request.form['email']
    academic_year = request.form['academic_year']
    
    student_id, message = Student.create_student(
        full_name, gender, date_of_birth, class_id, roll_number,
        fathers_name, mobile_number, mothers_name, email, academic_year
    )
    
    if student_id:
        flash(message, 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/admin/edit_student/<int:student_id>')
@login_required
def edit_student(student_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    student = Student.get_student_by_id(student_id)
    if not student:
        flash('Student not found!', 'danger')
        return redirect(url_for('manage_students'))
    
    classes = Class.get_all_classes()
    return render_template('edit_student.html', student=student, classes=classes)

@app.route('/admin/update_student/<int:student_id>', methods=['POST'])
@login_required
def update_student(student_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    full_name = request.form['full_name']
    gender = request.form['gender']
    date_of_birth = request.form['date_of_birth']
    class_id = request.form['class_id']
    roll_number = request.form['roll_number']
    fathers_name = request.form['fathers_name']
    mobile_number = request.form['mobile_number']
    mothers_name = request.form['mothers_name']
    email = request.form['email']
    
    success, message = Student.update_student(
        student_id, full_name, gender, date_of_birth, class_id, roll_number,
        fathers_name, mobile_number, mothers_name, email
    )
    
    if success:
        flash('Student updated successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/admin/delete_student/<int:student_id>', methods=['POST'])
@login_required
def delete_student_route(student_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    success, message = Student.delete_student(student_id)
    if success:
        flash('Student deleted successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/admin/search_students', methods=['POST'])
@login_required
def search_students():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    query = request.form.get('query', '')
    students = Student.search_students(query)
    
    students_list = [dict(student) for student in students]
    
    return jsonify({'success': True, 'students': students_list})

# Debug routes (optional - remove in production)
@app.route('/debug_users')
def debug_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])

@app.route('/reset_admin')
def reset_admin():
    conn = get_db_connection()
    hashed_password = generate_password_hash('admin123')
    conn.execute(
        'UPDATE users SET password = ? WHERE username = ?',
        (hashed_password, 'admin')
    )
    conn.commit()
    conn.close()
    return "Admin password reset successfully!"

if __name__ == '__main__':
    app.run(debug=True)