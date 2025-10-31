from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash, generate_password_hash
from database import init_db, get_db_connection
from models import User, Class, Subject, Result, Enrollment, Student
from auth import LoginUser
import sqlite3
from excel_utils import ExcelImporter
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'uploads'
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
        
        print(f"DEBUG: Login attempt for username: {username}")
        
        user = User.get_by_username(username)
        
        if user:
            print(f"DEBUG: User found - {user.username}")
            print(f"DEBUG: Stored hash - {user.password}")
            print(f"DEBUG: Password check - {check_password_hash(user.password, password)}")
            
            if check_password_hash(user.password, password):
                login_user_obj = LoginUser(user.id, user.username, user.role, user.name)
                login_user(login_user_obj)
                flash('Login successful!', 'success')
                return redirect(url_for('index'))
            else:
                flash('Invalid username or password', 'danger')
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
    
    # Basic statistics
    total_students = cursor.execute('SELECT COUNT(*) FROM users WHERE role = "student"').fetchone()[0]
    total_teachers = cursor.execute('SELECT COUNT(*) FROM users WHERE role = "teacher"').fetchone()[0]
    total_classes = cursor.execute('SELECT COUNT(*) FROM classes').fetchone()[0]
    total_subjects = cursor.execute('SELECT COUNT(*) FROM subjects').fetchone()[0]
    
    # Overall performance stats
    overall_stats_query = '''
        SELECT 
            COUNT(*) as total_results,
            AVG((marks_obtained * 100.0) / total_marks) as average_percentage,
            MAX((marks_obtained * 100.0) / total_marks) as topper_score,
            (SELECT COUNT(*) FROM results WHERE (marks_obtained * 100.0) / total_marks >= 50) * 100.0 / COUNT(*) as pass_percentage
        FROM results
    '''
    overall_stats = cursor.execute(overall_stats_query).fetchone()
    
    # Handle case when no results exist
    if overall_stats['total_results'] == 0:
        overall_stats = {
            'total_results': 0,
            'average_percentage': 0,
            'topper_score': 0,
            'pass_percentage': 0
        }
    else:
        overall_stats = dict(overall_stats)
    
    # Subject-wise performance
    subject_performance_query = '''
        SELECT 
            s.subject_name as name,
            s.subject_code as code,
            AVG((r.marks_obtained * 100.0) / r.total_marks) as average,
            COUNT(DISTINCT r.student_id) as student_count
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        GROUP BY s.id, s.subject_name, s.subject_code
        ORDER BY average DESC
    '''
    subject_performance = cursor.execute(subject_performance_query).fetchall()
    
    # Class-wise performance
    class_performance_query = '''
        SELECT 
            c.class_name,
            c.section,
            AVG((r.marks_obtained * 100.0) / r.total_marks) as average,
            COUNT(DISTINCT r.student_id) as student_count
        FROM results r
        JOIN classes c ON r.class_id = c.id
        GROUP BY c.id, c.class_name, c.section
        ORDER BY average DESC
    '''
    class_performance = cursor.execute(class_performance_query).fetchall()
    
    # Recent results
    recent_results_query = '''
        SELECT 
            r.*,
            s.subject_name,
            u.name as student_name,
            u.username as student_username,
            c.class_name,
            c.section
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        ORDER BY r.created_at DESC
        LIMIT 10
    '''
    recent_results = cursor.execute(recent_results_query).fetchall()
    
    # Top performers - at least 3 subjects
    top_performers_query = '''
        SELECT 
            u.name as student_name,
            c.class_name,
            AVG((r.marks_obtained * 100.0) / r.total_marks) as average_percentage
        FROM results r
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        GROUP BY r.student_id
        HAVING COUNT(*) >= 3
        ORDER BY average_percentage DESC
        LIMIT 5
    '''
    top_performers = cursor.execute(top_performers_query).fetchall()
    
    conn.close()
    
    return render_template('admin_dashboard.html', 
                         total_students=total_students,
                         total_teachers=total_teachers,
                         total_classes=total_classes,
                         total_subjects=total_subjects,
                         overall_stats=overall_stats,
                         subject_performance=subject_performance,
                         class_performance=class_performance,
                         recent_results=recent_results,
                         top_performers=top_performers)

@app.route('/admin/view_all_results')
@login_required
def view_all_results():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    results = conn.execute('''
        SELECT 
            r.*,
            s.subject_name,
            u.name as student_name,
            c.class_name,
            c.section,
            t.name as teacher_name
        FROM results r
        JOIN subjects s ON r.subject_id = s.id
        JOIN users u ON r.student_id = u.id
        JOIN classes c ON r.class_id = c.id
        JOIN users t ON r.teacher_id = t.id
        ORDER BY r.created_at DESC
    ''').fetchall()
    conn.close()
    
    return render_template('view_all_results.html', results=results)

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
    
    return render_template('edit_user.html', user=user)

@app.route('/admin/update_user/<int:user_id>', methods=['POST'])
@login_required
def update_user(user_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    username = request.form['username']
    role = request.form['role']
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

@app.route('/admin/manage_subjects')
@login_required
def manage_subjects():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    subjects = Subject.get_all_subjects()
    return render_template('manage_subjects.html', subjects=subjects)

@app.route('/admin/add_subject', methods=['POST'])
@login_required
def add_subject():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    subject_name = request.form['subject_name']
    subject_code = request.form['subject_code']
    
    subject_id = Subject.create_subject(subject_name, subject_code)
    if subject_id:
        flash('Subject created successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Subject name or code already exists!'})

@app.route('/admin/edit_subject/<int:subject_id>')
@login_required
def edit_subject(subject_id):
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    subject = Subject.get_subject_by_id(subject_id)
    if not subject:
        flash('Subject not found!', 'danger')
        return redirect(url_for('manage_subjects'))
    
    return render_template('edit_subject.html', subject=subject)

@app.route('/admin/update_subject/<int:subject_id>', methods=['POST'])
@login_required
def update_subject(subject_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    subject_name = request.form['subject_name']
    subject_code = request.form['subject_code']
    
    success = Subject.update_subject(subject_id, subject_name, subject_code)
    if success:
        flash('Subject updated successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Subject name or code already exists!'})

@app.route('/admin/delete_subject/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
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
    return render_template('manage_classes.html', classes=classes, teachers=teachers)

@app.route('/admin/add_class', methods=['POST'])
@login_required
def add_class():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    class_name = request.form['class_name']
    section = request.form['section']
    teacher_id = request.form['teacher_id']
    
    class_id = Class.create_class(class_name, section, teacher_id)
    if class_id:
        flash('Class created successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Class name already exists!'})

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
    return render_template('edit_class.html', class_data=class_data, teachers=teachers)

@app.route('/admin/update_class/<int:class_id>', methods=['POST'])
@login_required
def update_class(class_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    class_name = request.form['class_name']
    section = request.form['section']
    teacher_id = request.form['teacher_id']
    
    success = Class.update_class(class_id, class_name, section, teacher_id)
    if success:
        flash('Class updated successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Class name already exists!'})

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




# Teacher Routes
@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get teacher's classes with additional statistics
    classes_taught = cursor.execute('''
        SELECT c.*, u.name as teacher_name,
               (SELECT COUNT(*) FROM student_enrollment WHERE class_id = c.id) as student_count,
               (SELECT COUNT(*) FROM results WHERE class_id = c.id) as result_count
        FROM classes c 
        LEFT JOIN users u ON c.teacher_id = u.id
        WHERE c.teacher_id = ?
    ''', (current_user.id,)).fetchall()
    
    # Convert to list of dictionaries
    classes_list = []
    for class_item in classes_taught:
        classes_list.append({
            'id': class_item['id'],
            'class_name': class_item['class_name'],
            'section': class_item['section'],
            'teacher_name': class_item['teacher_name'],
            'student_count': class_item['student_count'] or 0,
            'result_count': class_item['result_count'] or 0
        })
    
    # Get total students across all classes
    total_students = cursor.execute('''
        SELECT COUNT(DISTINCT se.student_id) 
        FROM student_enrollment se 
        JOIN classes c ON se.class_id = c.id 
        WHERE c.teacher_id = ?
    ''', (current_user.id,)).fetchone()[0] or 0
    
    # Get total results entered by this teacher
    total_results = cursor.execute('''
        SELECT COUNT(*) FROM results WHERE teacher_id = ?
    ''', (current_user.id,)).fetchone()[0] or 0
    
    # Get recent results (last 5)
    recent_results = cursor.execute('''
        SELECT r.*, s.subject_name, u.name as student_name, c.class_name
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
                         classes=classes_list,
                         total_students=total_students,
                         total_results=total_results,
                         recent_activity=len(recent_results),
                         recent_results=recent_results)

@app.route('/teacher/class_stats/<int:class_id>')
@login_required
def class_stats(class_id):
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    # Verify the teacher teaches this class
    conn = get_db_connection()
    cursor = conn.cursor()
    
    class_info = cursor.execute('''
        SELECT * FROM classes WHERE id = ? AND teacher_id = ?
    ''', (class_id, current_user.id)).fetchone()
    
    if not class_info:
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    # Get class statistics
    total_students = cursor.execute('''
        SELECT COUNT(*) FROM student_enrollment WHERE class_id = ?
    ''', (class_id,)).fetchone()[0] or 0
    
    total_results = cursor.execute('''
        SELECT COUNT(*) FROM results WHERE class_id = ?
    ''', (class_id,)).fetchone()[0] or 0
    
    # Calculate average percentage
    average_result = cursor.execute('''
        SELECT AVG((marks_obtained * 100.0) / total_marks) as avg_percentage
        FROM results WHERE class_id = ?
    ''', (class_id,)).fetchone()
    average_percentage = round(average_result['avg_percentage'] or 0, 2)
    
    # Get top subjects by average
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

@app.route('/teacher/enter_marks/<int:class_id>')
@login_required
def enter_marks(class_id):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    # Verify the teacher teaches this class
    conn = get_db_connection()
    cursor = conn.cursor()
    
    class_info = cursor.execute('''
        SELECT * FROM classes WHERE id = ? AND teacher_id = ?
    ''', (class_id, current_user.id)).fetchone()
    
    if not class_info:
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    # Convert to dictionary for easier template access
    class_dict = {
        'id': class_info['id'],
        'class_name': class_info['class_name'],
        'section': class_info['section']
    }
    
    # Get students in this class
    students = cursor.execute('''
        SELECT u.id, u.name 
        FROM users u 
        JOIN student_enrollment se ON u.id = se.student_id 
        WHERE se.class_id = ?
    ''', (class_id,)).fetchall()
    
    # Convert students to list of dictionaries
    students_list = []
    for student in students:
        students_list.append({
            'id': student['id'],
            'name': student['name']
        })
    
    # Get subjects assigned to this class (not all subjects)
    subjects = Class.get_subjects_for_class(class_id)
    
    conn.close()
    
    return render_template('enter_marks.html', 
                         class_info=class_dict, 
                         students=students_list, 
                         subjects=subjects)

@app.route('/teacher/submit_marks', methods=['POST'])
@login_required
def submit_marks():
    if current_user.role != 'teacher':
        return jsonify({'success': False, 'message': 'Access denied!'})
    
    student_id = request.form['student_id']
    subject_id = request.form['subject_id']
    class_id = request.form['class_id']
    marks_obtained = float(request.form['marks_obtained'])
    total_marks = float(request.form['total_marks'])
    exam_type = request.form['exam_type']
    academic_year = request.form['academic_year']
    
    result_id, message = Result.enter_marks(
        student_id, subject_id, marks_obtained, total_marks, exam_type, academic_year
    )
    
    if result_id:
        flash('Marks entered successfully!', 'success')
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': message})

@app.route('/teacher/view_results/<int:class_id>')
@login_required
def view_results(class_id):
    if current_user.role != 'teacher':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    # Verify the teacher teaches this class
    conn = get_db_connection()
    cursor = conn.cursor()
    
    class_info = cursor.execute('''
        SELECT * FROM classes WHERE id = ? AND teacher_id = ?
    ''', (class_id, current_user.id)).fetchone()
    
    if not class_info:
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    # Convert to dictionary
    class_dict = {
        'id': class_info['id'],
        'class_name': class_info['class_name'],
        'section': class_info['section']
    }
    
    results = Result.get_class_results(class_id)
    
    conn.close()
    
    return render_template('view_results.html', 
                         class_info=class_dict, 
                         results=results)

# Student Routes
@app.route('/student/dashboard')
@login_required
def student_dashboard():
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    # Get student's classes
    classes = Enrollment.get_student_classes(current_user.id)
    
    return render_template('student_dashboard.html', classes=classes)

@app.route('/student/my_results')
@login_required
def my_results():
    if current_user.role != 'student':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    results = Result.get_student_results(current_user.id)
    
    # Calculate overall performance
    total_marks_obtained = 0
    total_max_marks = 0
    
    for result in results:
        total_marks_obtained += result['marks_obtained']
        total_max_marks += result['total_marks']
    
    overall_percentage = (total_marks_obtained / total_max_marks * 100) if total_max_marks > 0 else 0
    
    return render_template('view_my_results.html', 
                         results=results, 
                         overall_percentage=round(overall_percentage, 2))

# Upload Section

# Create upload folder if it doesn't exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Excel Upload Routes
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

# Teacher upload_results Section 
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
    
    # Get teacher's classes for reference
    conn = get_db_connection()
    classes = conn.execute(
        'SELECT * FROM classes WHERE teacher_id = ?', (current_user.id,)
    ).fetchall()
    conn.close()
    
    return render_template('teacher_upload_results.html', classes=classes)

# Student Management Routes
@app.route('/admin/manage_students')
@login_required
def manage_students():
    if current_user.role != 'admin':
        flash('Access denied!', 'danger')
        return redirect(url_for('index'))
    
    students = Student.get_all_students()
    classes = Class.get_all_classes()
    return render_template('manage_students.html', students=students, classes=classes)

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
    
    student_id, message = Student.create_student(
        full_name, gender, date_of_birth, class_id, roll_number,
        fathers_name, mobile_number, mothers_name
    )
    
    if student_id:
        flash(f'Student created successfully! Student ID: {message}', 'success')
        return jsonify({'success': True, 'student_id': message})
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
    
    success, message = Student.update_student(
        student_id, full_name, gender, date_of_birth, class_id, roll_number,
        fathers_name, mobile_number, mothers_name
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
    
    students_list = []
    for student in students:
        students_list.append({
            'id': student['id'],
            'student_id': student['student_id'],
            'full_name': student['full_name'],
            'gender': student['gender'],
            'date_of_birth': student['date_of_birth'],
            'class_name': student['class_name'],
            'section': student['section'],
            'roll_number': student['roll_number'],
            'fathers_name': student['fathers_name'],
            'mobile_number': student['mobile_number'],
            'mothers_name': student['mothers_name']
        })
    
    return jsonify({'success': True, 'students': students_list})

# Debug routes (optional - remove in production)
@app.route('/debug_users')
def debug_users():
    """Debug route to see all users and their passwords"""
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    conn.close()
    
    user_info = []
    for user in users:
        user_info.append({
            'id': user['id'],
            'username': user['username'],
            'password': user['password'],
            'role': user['role'],
            'name': user['name']
        })
    
    return jsonify(user_info)

@app.route('/reset_admin')
def reset_admin():
    """Reset admin password"""
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