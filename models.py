from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string
import datetime

class Enrollment:
    @staticmethod
    def enroll_student(student_id, class_id, academic_year):
        # student_id is users.id
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO student_enrollment (student_id, class_id, academic_year)
                VALUES (?, ?, ?)
            ''', (student_id, class_id, academic_year))
            enrollment_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return enrollment_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
            
    @staticmethod
    def update_student_enrollment(student_id, class_id, academic_year):
        # student_id is users.id
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            # Check if enrollment exists
            exists = cursor.execute(
                'SELECT id FROM student_enrollment WHERE student_id = ?', (student_id,)
            ).fetchone()
            
            if exists:
                cursor.execute('''
                    UPDATE student_enrollment 
                    SET class_id = ?, academic_year = ?
                    WHERE student_id = ?
                ''', (class_id, academic_year, student_id))
            else:
                cursor.execute('''
                    INSERT INTO student_enrollment (student_id, class_id, academic_year)
                    VALUES (?, ?, ?)
                ''', (student_id, class_id, academic_year))
            
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    @staticmethod
    def get_student_classes(student_id):
        # student_id is users.id
        conn = get_db_connection()
        classes = conn.execute('''
            SELECT c.*, se.academic_year
            FROM classes c
            JOIN student_enrollment se ON c.id = se.class_id
            WHERE se.student_id = ?
        ''', (student_id,)).fetchall()
        conn.close()
        return classes

class User:
    def __init__(self, id, username, password, role, name, email):
        self.id = id
        self.username = username
        self.password = password
        self.role = role
        self.name = name
        self.email = email
    
    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        
        if user:
            return User(
                id=user['id'],
                username=user['username'],
                password=user['password'],
                role=user['role'],
                name=user['name'],
                email=user['email']
            )
        return None
    
    @staticmethod
    def get_by_id(user_id):
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE id = ?', (user_id,)
        ).fetchone()
        conn.close()
        
        if user:
            return User(
                id=user['id'],
                username=user['username'],
                password=user['password'],
                role=user['role'],
                name=user['name'],
                email=user['email']
            )
        return None
    
    def verify_password(self, password):
        return check_password_hash(self.password, password)
    
    @staticmethod
    def create_user(username, password, role, name, email):
        conn = get_db_connection()
        hashed_password = generate_password_hash(password)
        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, password, role, name, email) VALUES (?, ?, ?, ?, ?)',
                (username, hashed_password, role, name, email)
            )
            user_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return user_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    @staticmethod
    def update_user(user_id, username, role, name, email, password=None):
        conn = get_db_connection()
        try:
            if password:
                hashed_password = generate_password_hash(password)
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET username=?, role=?, name=?, email=?, password=? WHERE id=?',
                    (username, role, name, email, hashed_password, user_id)
                )
            else:
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE users SET username=?, role=?, name=?, email=? WHERE id=?',
                    (username, role, name, email, user_id)
                )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    @staticmethod
    def delete_user(user_id):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            user = conn.execute('SELECT role FROM users WHERE id = ?', (user_id,)).fetchone()
            if not user:
                conn.close()
                return False, "User not found"
            
            if user['role'] == 'student':
                cursor.execute('DELETE FROM results WHERE student_id = ?', (user_id,))
                cursor.execute('DELETE FROM student_enrollment WHERE student_id = ?', (user_id,))
                cursor.execute('DELETE FROM students WHERE user_id = ?', (user_id,))
            
            if user['role'] == 'teacher':
                classes_count = conn.execute(
                    'SELECT COUNT(*) FROM classes WHERE teacher_id = ?', (user_id,)
                ).fetchone()[0]
                if classes_count > 0:
                    conn.close()
                    return False, "Cannot delete. Teacher is assigned to one or more classes."
                
                results_count = conn.execute(
                    'SELECT COUNT(*) FROM results WHERE teacher_id = ?', (user_id,)
                ).fetchone()[0]
                if results_count > 0:
                    conn.close()
                    return False, "Cannot delete. Teacher has entered results."
                
                cursor.execute('DELETE FROM teacher_subject_assignments WHERE teacher_id = ?', (user_id,))

            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True, "User deleted successfully"
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, str(e)
    
    @staticmethod
    def get_all_users():
        conn = get_db_connection()
        users = conn.execute('SELECT * FROM users ORDER BY role, name').fetchall()
        conn.close()
        return users
    
    @staticmethod
    def get_all_users_with_details():
        conn = get_db_connection()
        users = conn.execute('''
            SELECT 
                u.id, u.username, u.name, u.email, u.role, u.created_at,
                s.roll_number,
                c.class_name, c.section
            FROM users u
            LEFT JOIN students s ON u.id = s.user_id
            LEFT JOIN classes c ON s.class_id = c.id
            ORDER BY u.role, u.name
        ''').fetchall()
        conn.close()
        return users
    
    @staticmethod
    def get_students():
        conn = get_db_connection()
        students = conn.execute(
            'SELECT * FROM users WHERE role = "student" ORDER BY name'
        ).fetchall()
        conn.close()
        return students
    
    @staticmethod
    def get_teachers():
        conn = get_db_connection()
        teachers = conn.execute(
            'SELECT * FROM users WHERE role = "teacher" ORDER BY name'
        ).fetchall()
        conn.close()
        return teachers

    @staticmethod
    def get_subjects_taught(teacher_id):
        """Get all subjects taught by a specific teacher"""
        conn = get_db_connection()
        subjects = conn.execute('''
            SELECT s.* FROM subjects s
            JOIN teacher_subject_assignments tsa ON s.id = tsa.subject_id
            WHERE tsa.teacher_id = ?
            ORDER BY s.subject_name
        ''', (teacher_id,)).fetchall()
        conn.close()
        return subjects

    @staticmethod
    def get_teachable_subjects_for_class(teacher_id, class_id):
        """
        Get subjects that a specific teacher teaches AND are part of a specific class.
        """
        conn = get_db_connection()
        subjects = conn.execute('''
            SELECT s.* FROM subjects s
            JOIN class_subjects cs ON s.id = cs.subject_id
            JOIN teacher_subject_assignments tsa ON s.id = tsa.subject_id
            WHERE cs.class_id = ? AND tsa.teacher_id = ?
            ORDER BY s.subject_name
        ''', (class_id, teacher_id)).fetchall()
        conn.close()
        return subjects

    @staticmethod
    def get_students_in_class(class_id):
        """Get all students (as users) enrolled in a specific class"""
        conn = get_db_connection()
        students = conn.execute('''
            SELECT u.id, u.name, s.roll_number
            FROM users u
            JOIN student_enrollment se ON u.id = se.student_id
            JOIN students s ON u.id = s.user_id
            WHERE se.class_id = ? AND u.role = 'student'
            ORDER BY s.roll_number, u.name
        ''', (class_id,)).fetchall()
        conn.close()
        return students

class Student:
    @staticmethod
    def create_student(full_name, gender, date_of_birth, class_id, roll_number, 
                      fathers_name, mobile_number, mothers_name, email, academic_year):
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        try:
            username = f"{full_name.split(' ')[0].lower().strip()}{roll_number}"
            password = str(date_of_birth).replace('-', '')
        except Exception as e:
            return None, f"Error generating username/password: {str(e)}"

        try:
            hashed_password = generate_password_hash(password)
            cursor.execute(
                'INSERT INTO users (username, password, role, name, email) VALUES (?, ?, ?, ?, ?)',
                (username, hashed_password, 'student', full_name, email)
            )
            user_id = cursor.lastrowid
            
            if not user_id:
                conn.rollback()
                conn.close()
                return None, "Failed to create user account"

            student_id_str = f"S{user_id:04d}"

            cursor.execute('''
                INSERT INTO students 
                (user_id, student_id, full_name, gender, date_of_birth, class_id, roll_number, 
                 fathers_name, mobile_number, mothers_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, student_id_str, full_name, gender, date_of_birth, class_id, roll_number,
                  fathers_name, mobile_number, mothers_name))
            
            student_db_id = cursor.lastrowid

            cursor.execute('''
                INSERT INTO student_enrollment (student_id, class_id, academic_year)
                VALUES (?, ?, ?)
            ''', (user_id, class_id, academic_year))

            conn.commit()
            conn.close()
            
            return student_db_id, (f"Student created successfully! "
                                   f"Username: {username}, "
                                   f"Password: {password}")

        except sqlite3.IntegrityError as e:
            conn.rollback()
            conn.close()
            if 'UNIQUE constraint failed: users.username' in str(e):
                return None, f"Username '{username}' already exists. Student not created."
            if 'UNIQUE constraint failed: users.email' in str(e):
                return None, f"Email '{email}' already exists. Student not created."
            elif 'UNIQUE constraint failed: students.class_id, students.roll_number' in str(e):
                return None, "Roll number already exists in this class. Student not created."
            elif 'UNIQUE constraint failed: students.user_id' in str(e):
                return None, "This user already has a student profile. Student not created."
            else:
                return None, f"Database error: {str(e)}"
        except Exception as e:
            conn.rollback()
            conn.close()
            return None, f"An unexpected error occurred: {str(e)}"

    
    @staticmethod
    def get_all_students():
        conn = get_db_connection()
        students = conn.execute('''
            SELECT s.*, c.class_name, c.section, u.username, u.email
            FROM students s 
            JOIN classes c ON s.class_id = c.id
            JOIN users u ON s.user_id = u.id
            ORDER BY c.class_name, s.roll_number
        ''').fetchall()
        conn.close()
        return students
    
    @staticmethod
    def get_student_by_id(student_id):
        conn = get_db_connection()
        student = conn.execute('''
            SELECT s.*, c.class_name, c.section, u.username, u.email 
            FROM students s 
            JOIN classes c ON s.class_id = c.id 
            JOIN users u ON s.user_id = u.id
            WHERE s.id = ?
        ''', (student_id,)).fetchone()
        conn.close()
        return student

    @staticmethod
    def get_student_by_user_id(user_id):
        conn = get_db_connection()
        student = conn.execute('''
            SELECT s.*, c.class_name, c.section 
            FROM students s 
            JOIN classes c ON s.class_id = c.id 
            WHERE s.user_id = ?
        ''', (user_id,)).fetchone()
        conn.close()
        return student
    
    @staticmethod
    def update_student(student_id, full_name, gender, date_of_birth, class_id, 
                      roll_number, fathers_name, mobile_number, mothers_name, email):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            student_data = cursor.execute('SELECT user_id FROM students WHERE id = ?', (student_id,)).fetchone()
            if not student_data:
                conn.close()
                return False, "Student profile not found"
            
            user_id = student_data['user_id']
            
            cursor.execute('''
                UPDATE students SET 
                full_name=?, gender=?, date_of_birth=?, class_id=?, roll_number=?,
                fathers_name=?, mobile_number=?, mothers_name=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (full_name, gender, date_of_birth, class_id, roll_number,
                  fathers_name, mobile_number, mothers_name, student_id))
            
            cursor.execute('''
                UPDATE users SET name = ?, email = ?
                WHERE id = ?
            ''', (full_name, email, user_id))
            
            academic_year = datetime.date.today().strftime("%Y-%Y")
            
            Enrollment.update_student_enrollment(user_id, class_id, academic_year)

            conn.commit()
            conn.close()
            return True, "Student updated successfully"
            
        except sqlite3.IntegrityError as e:
            conn.rollback()
            conn.close()
            if 'UNIQUE constraint failed: students.class_id, students.roll_number' in str(e):
                return False, "Roll number already exists in this class"
            if 'UNIQUE constraint failed: users.email' in str(e):
                return False, f"Email '{email}' already exists for another user."
            else:
                return False, str(e)
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f"An unexpected error occurred: {str(e)}"
    
    @staticmethod
    def delete_student(student_id):
        conn = get_db_connection()
        try:
            user = conn.execute(
                'SELECT user_id FROM students WHERE id = ?', (student_id,)
            ).fetchone()
            
            if not user:
                conn.close()
                return False, "Student profile not found"
            
            user_id_to_delete = user['user_id']
            conn.close() 
            return User.delete_user(user_id_to_delete)

        except Exception as e:
            conn.close()
            return False, str(e)

    
    @staticmethod
    def search_students(query):
        conn = get_db_connection()
        students = conn.execute('''
            SELECT s.*, c.class_name, c.section, u.username
            FROM students s 
            JOIN classes c ON s.class_id = c.id
            JOIN users u ON s.user_id = u.id
            WHERE s.full_name LIKE ? OR u.username LIKE ? OR s.fathers_name LIKE ? OR s.student_id LIKE ?
            ORDER BY c.class_name, s.roll_number
        ''', (f'%{query}%', f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
        conn.close()
        return students

class Class:
    @staticmethod
    def create_class(class_name, section, teacher_id):
        if not class_name or not section:
            return None, "Class name and section are required"
        if not teacher_id:
            return None, "Teacher ID is required"
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            existing_class = cursor.execute(
                'SELECT id FROM classes WHERE class_name = ? AND section = ?',
                (class_name, section)
            ).fetchone()
            
            if existing_class:
                conn.close()
                return None, "Class with this name and section already exists"
            
            cursor.execute(
                'INSERT INTO classes (class_name, section, teacher_id) VALUES (?, ?, ?)',
                (class_name, section, teacher_id)
            )
            class_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return class_id, "Class created successfully"
        except sqlite3.IntegrityError as e:
            conn.close()
            return None, f"Database integrity error: {str(e)}"
        except Exception as e:
            conn.close()
            return None, f"Error creating class: {str(e)}"
    
    @staticmethod
    def update_class(class_id, class_name, section, teacher_id):
        if not class_name or not section:
            return False, "Class name and section are required"
        if not teacher_id:
            return False, "Teacher ID is required"
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            existing_class = cursor.execute(
                'SELECT id FROM classes WHERE class_name = ? AND section = ? AND id != ?',
                (class_name, section, class_id)
            ).fetchone()
            
            if existing_class:
                conn.close()
                return False, "Another class with this name and section already exists"
            
            cursor.execute(
                'UPDATE classes SET class_name=?, section=?, teacher_id=? WHERE id=?',
                (class_name, section, teacher_id, class_id)
            )
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Class not found"
                
            conn.commit()
            conn.close()
            return True, "Class updated successfully"
        except sqlite3.IntegrityError as e:
            conn.close()
            return False, f"Database integrity error: {str(e)}"
        except Exception as e:
            conn.close()
            return False, f"Error updating class: {str(e)}"
    
    @staticmethod
    def delete_class(class_id):
        conn = get_db_connection()
        try:
            enrollment_count = conn.execute(
                'SELECT COUNT(*) FROM student_enrollment WHERE class_id = ?', (class_id,)
            ).fetchone()[0]
            if enrollment_count > 0:
                conn.close()
                return False, "Cannot delete class. Students are enrolled in it."
            
            results_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE class_id = ?', (class_id,)
            ).fetchone()[0]
            if results_count > 0:
                conn.close()
                return False, "Cannot delete class. Results are associated with it."
            
            cursor = conn.cursor()
            cursor.execute('DELETE FROM class_subjects WHERE class_id = ?', (class_id,))
            cursor.execute('DELETE FROM classes WHERE id = ?', (class_id,))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Class not found"
                
            conn.commit()
            conn.close()
            return True, "Class deleted successfully"
        except Exception as e:
            conn.rollback()
            conn.close()
            return False, f"Error deleting class: {str(e)}"
    
    @staticmethod
    def get_all_classes():
        conn = get_db_connection()
        try:
            classes = conn.execute('''
                SELECT c.*, u.name as teacher_name,
                       (SELECT COUNT(*) FROM student_enrollment WHERE class_id = c.id) as student_count
                FROM classes c 
                LEFT JOIN users u ON c.teacher_id = u.id
                ORDER BY c.class_name, c.section
            ''').fetchall()
            conn.close()
            return classes
        except Exception as e:
            conn.close()
            return []
    
    @staticmethod
    def get_class_by_id(class_id):
        conn = get_db_connection()
        try:
            class_data = conn.execute('''
                SELECT c.*, u.name as teacher_name,
                       (SELECT COUNT(*) FROM student_enrollment WHERE class_id = c.id) as student_count
                FROM classes c 
                LEFT JOIN users u ON c.teacher_id = u.id 
                WHERE c.id = ?
            ''', (class_id,)).fetchone()
            conn.close()
            return class_data
        except Exception as e:
            conn.close()
            return None
    
    @staticmethod
    def get_classes_by_teacher(teacher_id):
        conn = get_db_connection()
        try:
            classes = conn.execute('''
                SELECT c.*, 
                       (SELECT COUNT(*) FROM student_enrollment WHERE class_id = c.id) as student_count
                FROM classes c 
                WHERE c.teacher_id = ?
                ORDER BY c.class_name, c.section
            ''', (teacher_id,)).fetchall()
            conn.close()
            return classes
        except Exception as e:
            conn.close()
            return []
    
    @staticmethod
    def get_subjects_for_class(class_id):
        conn = get_db_connection()
        try:
            subjects = conn.execute('''
                SELECT s.*
                FROM subjects s
                JOIN class_subjects cs ON s.id = cs.subject_id
                WHERE cs.class_id = ?
                ORDER BY s.subject_name
            ''', (class_id,)).fetchall()
            conn.close()
            return subjects
        except Exception as e:
            conn.close()
            return []
    
    @staticmethod
    def add_subject_to_class(class_id, subject_id, is_compulsory=True):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO class_subjects (class_id, subject_id, is_compulsory)
                VALUES (?, ?, ?)
            ''', (class_id, subject_id, is_compulsory))
            conn.commit()
            conn.close()
            return True, "Subject added to class successfully"
        except sqlite3.IntegrityError as e:
            conn.close()
            return False, "Subject is already assigned to this class"
        except Exception as e:
            conn.close()
            return False, f"Error adding subject to class: {str(e)}"
    
    @staticmethod
    def remove_subject_from_class(class_id, subject_id):
        conn = get_db_connection()
        try:
            results_count = conn.execute('''
                SELECT COUNT(*) FROM results r
                WHERE r.class_id = ? AND r.subject_id = ?
            ''', (class_id, subject_id)).fetchone()[0]
            
            if results_count > 0:
                conn.close()
                return False, "Cannot remove subject. Results already exist for this subject."
            
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM class_subjects 
                WHERE class_id = ? AND subject_id = ?
            ''', (class_id, subject_id))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Subject not found in class"
                
            conn.commit()
            conn.close()
            return True, "Subject removed from class successfully"
        except Exception as e:
            conn.close()
            return False, f"Error removing subject from class: {str(e)}"
    
    @staticmethod
    def get_available_subjects_for_class(class_id):
        conn = get_db_connection()
        try:
            subjects = conn.execute('''
                SELECT s.* FROM subjects s
                WHERE s.id NOT IN (
                    SELECT subject_id FROM class_subjects WHERE class_id = ?
                )
                ORDER BY s.subject_name
            ''', (class_id,)).fetchall()
            conn.close()
            return subjects
        except Exception as e:
            conn.close()
            return []
    
    @staticmethod
    def get_classes_for_subject(subject_id):
        """Get all classes that have a specific subject assigned"""
        conn = get_db_connection()
        classes = conn.execute('''
            SELECT c.*
            FROM classes c
            JOIN class_subjects cs ON c.id = cs.class_id
            WHERE cs.subject_id = ?
            ORDER BY c.class_name, c.section
        ''', (subject_id,)).fetchall()
        conn.close()
        return classes
            
class Subject:
    @staticmethod
    def create_subject(subject_name, subject_code):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO subjects (subject_name, subject_code) VALUES (?, ?)',
                (subject_name, subject_code)
            )
            subject_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return subject_id
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    @staticmethod
    def update_subject(subject_id, subject_name, subject_code):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE subjects SET subject_name=?, subject_code=? WHERE id=?',
                (subject_name, subject_code, subject_id)
            )
            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            conn.close()
            return False
    
    @staticmethod
    def delete_subject(subject_id):
        conn = get_db_connection()
        try:
            results_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE subject_id = ?', (subject_id,)
            ).fetchone()[0]
            if results_count > 0:
                conn.close()
                return False, "Cannot delete subject that has results"
            
            class_subjects_count = conn.execute(
                'SELECT COUNT(*) FROM class_subjects WHERE subject_id = ?', (subject_id,)
            ).fetchone()[0]
            if class_subjects_count > 0:
                conn.close()
                return False, "Cannot delete. Subject is assigned to classes. Remove it from classes first."

            cursor = conn.cursor()
            cursor.execute('DELETE FROM teacher_subject_assignments WHERE subject_id = ?', (subject_id,))
            cursor.execute('DELETE FROM subjects WHERE id = ?', (subject_id,))
            conn.commit()
            conn.close()
            return True, "Subject deleted successfully"
        except Exception as e:
            conn.close()
            return False, str(e)
    
    @staticmethod
    def get_all_subjects():
        conn = get_db_connection()
        subjects = conn.execute('SELECT * FROM subjects ORDER BY subject_name').fetchall()
        conn.close()
        return subjects
    
    @staticmethod
    def get_subject_by_id(subject_id):
        conn = get_db_connection()
        subject = conn.execute(
            'SELECT * FROM subjects WHERE id = ?', (subject_id,)
        ).fetchone()
        conn.close()
        return subject

    @staticmethod
    def assign_teacher_to_subject(subject_id, teacher_id):
        """Assigns a teacher to a subject."""
        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT OR IGNORE INTO teacher_subject_assignments (subject_id, teacher_id) VALUES (?, ?)',
                (subject_id, teacher_id)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            return False

    @staticmethod
    def remove_teacher_from_subject(subject_id, teacher_id):
        """Removes a teacher's assignment from a subject."""
        conn = get_db_connection()
        try:
            conn.execute(
                'DELETE FROM teacher_subject_assignments WHERE subject_id = ? AND teacher_id = ?',
                (subject_id, teacher_id)
            )
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            return False

    @staticmethod
    def get_teachers_for_subject(subject_id):
        """Get all teachers assigned to a specific subject."""
        conn = get_db_connection()
        teachers = conn.execute('''
            SELECT u.id, u.name, u.username 
            FROM users u
            JOIN teacher_subject_assignments tsa ON u.id = tsa.teacher_id
            WHERE tsa.subject_id = ? AND u.role = 'teacher'
            ORDER BY u.name
        ''', (subject_id,)).fetchall()
        conn.close()
        return teachers

class Result:
    @staticmethod
    def enter_marks(student_id, subject_id, class_id, teacher_id, marks_obtained, total_marks, exam_type, academic_year):
        """Enter marks for a student - student_id is users.id"""
        conn = get_db_connection()
        try:
            valid_subject = conn.execute('''
                SELECT 1 FROM class_subjects 
                WHERE class_id = ? AND subject_id = ?
            ''', (class_id, subject_id)).fetchone()
            
            if not valid_subject:
                conn.close()
                return None, "Subject not assigned to student's class"
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results 
                (student_id, subject_id, class_id, teacher_id, marks_obtained, total_marks, exam_type, academic_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, subject_id, class_id, teacher_id,
                  marks_obtained, total_marks, exam_type, academic_year))
            
            result_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return result_id, "Marks entered successfully"
        except sqlite3.IntegrityError as e:
            conn.close()
            return None, f"Error entering marks: {str(e)}"
    
    @staticmethod
    def get_student_results(student_id):
        conn = get_db_connection()
        results = conn.execute('''
            SELECT r.*, s.subject_name, c.class_name, u.name as teacher_name
            FROM results r
            JOIN subjects s ON r.subject_id = s.id
            JOIN classes c ON r.class_id = c.id
            JOIN users u ON r.teacher_id = u.id
            WHERE r.student_id = ?
            ORDER BY r.created_at DESC
        ''', (student_id,)).fetchall()
        conn.close()
        return results
    
    @staticmethod
    def get_class_results(class_id):
        conn = get_db_connection()
        results = conn.execute('''
            SELECT r.*, s.subject_name, u.name as student_name, u2.name as teacher_name
            FROM results r
            JOIN subjects s ON r.subject_id = s.id
            JOIN users u ON r.student_id = u.id
            JOIN users u2 ON r.teacher_id = u2.id
            WHERE r.class_id = ?
            ORDER BY u.name, s.subject_name
        ''', (class_id,)).fetchall()
        conn.close()
        return results

    @staticmethod
    def get_all_results():
        """Gets all results from all students and teachers for the admin."""
        conn = get_db_connection()
        results = conn.execute('''
            SELECT 
                r.*,
                s.subject_name,
                u.name as student_name,
                c.class_name,
                c.section,
                t.name as teacher_name,
                (r.marks_obtained * 100.0 / r.total_marks) as percentage
            FROM results r
            JOIN subjects s ON r.subject_id = s.id
            JOIN users u ON r.student_id = u.id
            JOIN classes c ON r.class_id = c.id
            JOIN users t ON r.teacher_id = t.id
            ORDER BY r.created_at DESC
        ''').fetchall()
        conn.close()
        return results

    @staticmethod
    def get_result_by_id(result_id):
        """Gets a single result by its ID, with all related info."""
        conn = get_db_connection()
        result = conn.execute('''
            SELECT 
                r.*,
                s.subject_name,
                s.id as subject_id,
                u.name as student_name,
                c.class_name,
                c.section
            FROM results r
            JOIN subjects s ON r.subject_id = s.id
            JOIN users u ON r.student_id = u.id
            JOIN classes c ON r.class_id = c.id
            WHERE r.id = ?
        ''', (result_id,)).fetchone()
        conn.close()
        return result

    @staticmethod
    def update_marks(result_id, marks_obtained, total_marks, exam_type, academic_year):
        """Updates an existing result."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE results SET
                marks_obtained = ?,
                total_marks = ?,
                exam_type = ?,
                academic_year = ?
                WHERE id = ?
            ''', (marks_obtained, total_marks, exam_type, academic_year, result_id))
            conn.commit()
            conn.close()
            return True, "Result updated successfully"
        except Exception as e:
            conn.close()
            return False, f"Error updating result: {str(e)}"

    @staticmethod
    def delete_result(result_id):
        """Deletes a single result by its ID."""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM results WHERE id = ?', (result_id,))
            conn.commit()
            conn.close()
            return True, "Result deleted successfully"
        except Exception as e:
            conn.close()
            return False, f"Error deleting result: {str(e)}"