from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import random
import string

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
            # Check if user is a teacher assigned to classes
            classes_count = conn.execute(
                'SELECT COUNT(*) FROM classes WHERE teacher_id = ?', (user_id,)
            ).fetchone()[0]
            
            if classes_count > 0:
                conn.close()
                return False, "Cannot delete user who is assigned as a teacher to classes"
            
            # Check if user has entered results
            results_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE teacher_id = ?', (user_id,)
            ).fetchone()[0]
            
            if results_count > 0:
                conn.close()
                return False, "Cannot delete user who has entered results"
            
            # Delete user
            cursor = conn.cursor()
            cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            conn.close()
            return True, "User deleted successfully"
        except Exception as e:
            conn.close()
            return False, str(e)
    
    @staticmethod
    def get_all_users():
        conn = get_db_connection()
        users = conn.execute('SELECT * FROM users ORDER BY role, name').fetchall()
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

class Student:
    @staticmethod
    def generate_student_id():
        """Generate unique student ID"""
        return 'STU' + ''.join(random.choices(string.digits, k=6))
    
    @staticmethod
    def create_student(full_name, gender, date_of_birth, class_id, roll_number, 
                      fathers_name, mobile_number, mothers_name):
        conn = get_db_connection()
        try:
            # Generate unique student ID
            student_id = Student.generate_student_id()
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO students 
                (student_id, full_name, gender, date_of_birth, class_id, roll_number, 
                 fathers_name, mobile_number, mothers_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, full_name, gender, date_of_birth, class_id, roll_number,
                  fathers_name, mobile_number, mothers_name))
            
            student_db_id = cursor.lastrowid
            conn.commit()
            conn.close()
            return student_db_id, student_id
        except sqlite3.IntegrityError as e:
            conn.close()
            if 'UNIQUE constraint failed: students.student_id' in str(e):
                return None, "Student ID already exists"
            elif 'UNIQUE constraint failed: students.class_id, students.roll_number' in str(e):
                return None, "Roll number already exists in this class"
            else:
                return None, str(e)
    
    @staticmethod
    def get_all_students():
        conn = get_db_connection()
        students = conn.execute('''
            SELECT s.*, c.class_name, c.section 
            FROM students s 
            JOIN classes c ON s.class_id = c.id
            ORDER BY c.class_name, s.roll_number
        ''').fetchall()
        conn.close()
        return students
    
    @staticmethod
    def get_student_by_id(student_id):
        conn = get_db_connection()
        student = conn.execute('''
            SELECT s.*, c.class_name, c.section 
            FROM students s 
            JOIN classes c ON s.class_id = c.id 
            WHERE s.id = ?
        ''', (student_id,)).fetchone()
        conn.close()
        return student
    
    @staticmethod
    def update_student(student_id, full_name, gender, date_of_birth, class_id, 
                      roll_number, fathers_name, mobile_number, mothers_name):
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE students SET 
                full_name=?, gender=?, date_of_birth=?, class_id=?, roll_number=?,
                fathers_name=?, mobile_number=?, mothers_name=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (full_name, gender, date_of_birth, class_id, roll_number,
                  fathers_name, mobile_number, mothers_name, student_id))
            conn.commit()
            conn.close()
            return True, "Student updated successfully"
        except sqlite3.IntegrityError as e:
            conn.close()
            if 'UNIQUE constraint failed: students.class_id, students.roll_number' in str(e):
                return False, "Roll number already exists in this class"
            else:
                return False, str(e)
    
    @staticmethod
    def delete_student(student_id):
        conn = get_db_connection()
        try:
            # Check if student has results
            results_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE student_id = ?', (student_id,)
            ).fetchone()[0]
            
            if results_count > 0:
                conn.close()
                return False, "Cannot delete student who has results. Delete results first."
            
            cursor = conn.cursor()
            cursor.execute('DELETE FROM students WHERE id = ?', (student_id,))
            conn.commit()
            conn.close()
            return True, "Student deleted successfully"
        except Exception as e:
            conn.close()
            return False, str(e)
    
    @staticmethod
    def search_students(query):
        conn = get_db_connection()
        students = conn.execute('''
            SELECT s.*, c.class_name, c.section 
            FROM students s 
            JOIN classes c ON s.class_id = c.id
            WHERE s.full_name LIKE ? OR s.student_id LIKE ? OR s.fathers_name LIKE ?
            ORDER BY c.class_name, s.roll_number
        ''', (f'%{query}%', f'%{query}%', f'%{query}%')).fetchall()
        conn.close()
        return students

class Class:
    @staticmethod
    def create_class(class_name, section, teacher_id):
        """Create a new class with validation"""
        if not class_name or not section:
            return None, "Class name and section are required"
        
        if not teacher_id:
            return None, "Teacher ID is required"
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Check if class with same name and section already exists
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
        """Update class information with validation"""
        if not class_name or not section:
            return False, "Class name and section are required"
        
        if not teacher_id:
            return False, "Teacher ID is required"
            
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Check if another class with same name and section already exists
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
        """Delete a class with comprehensive checks"""
        conn = get_db_connection()
        try:
            # Check if class exists
            class_data = conn.execute(
                'SELECT id FROM classes WHERE id = ?', (class_id,)
            ).fetchone()
            
            if not class_data:
                conn.close()
                return False, "Class not found"
            
            # Check if class has students enrolled
            enrollment_count = conn.execute(
                'SELECT COUNT(*) FROM student_enrollment WHERE class_id = ?', (class_id,)
            ).fetchone()[0]
            
            if enrollment_count > 0:
                conn.close()
                return False, "Cannot delete class that has students enrolled"
            
            # Check if class has results
            results_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE class_id = ?', (class_id,)
            ).fetchone()[0]
            
            if results_count > 0:
                conn.close()
                return False, "Cannot delete class that has results"
            
            # Delete class subjects first
            cursor = conn.cursor()
            cursor.execute('DELETE FROM class_subjects WHERE class_id = ?', (class_id,))
            
            # Then delete class
            cursor.execute('DELETE FROM classes WHERE id = ?', (class_id,))
            
            if cursor.rowcount == 0:
                conn.close()
                return False, "Class not found"
                
            conn.commit()
            conn.close()
            return True, "Class deleted successfully"
        except Exception as e:
            conn.close()
            return False, f"Error deleting class: {str(e)}"
    
    @staticmethod
    def get_all_classes():
        """Get all classes with teacher information"""
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
        """Get class by ID with teacher information"""
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
        """Get all classes taught by a specific teacher"""
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
        """Get all subjects assigned to a class"""
        conn = get_db_connection()
        try:
            subjects = conn.execute('''
                SELECT s.*, cs.is_compulsory,
                       (SELECT COUNT(*) FROM results 
                        WHERE class_id = ? AND subject_id = s.id) as has_results
                FROM subjects s
                JOIN class_subjects cs ON s.id = cs.subject_id
                WHERE cs.class_id = ?
                ORDER BY cs.is_compulsory DESC, s.subject_name
            ''', (class_id, class_id)).fetchall()
            conn.close()
            return subjects
        except Exception as e:
            conn.close()
            return []
    
    @staticmethod
    def add_subject_to_class(class_id, subject_id, is_compulsory=True):
        """Add a subject to a class with validation"""
        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            
            # Check if subject is already assigned to class
            existing = cursor.execute('''
                SELECT 1 FROM class_subjects 
                WHERE class_id = ? AND subject_id = ?
            ''', (class_id, subject_id)).fetchone()
            
            if existing:
                conn.close()
                return False, "Subject is already assigned to this class"
            
            cursor.execute('''
                INSERT INTO class_subjects (class_id, subject_id, is_compulsory)
                VALUES (?, ?, ?)
            ''', (class_id, subject_id, is_compulsory))
            
            conn.commit()
            conn.close()
            return True, "Subject added to class successfully"
        except sqlite3.IntegrityError as e:
            conn.close()
            return False, f"Database integrity error: {str(e)}"
        except Exception as e:
            conn.close()
            return False, f"Error adding subject to class: {str(e)}"
    
    @staticmethod
    def remove_subject_from_class(class_id, subject_id):
        """Remove a subject from a class with validation"""
        conn = get_db_connection()
        try:
            # Check if any results exist for this class-subject combination
            results_count = conn.execute('''
                SELECT COUNT(*) FROM results r
                WHERE r.class_id = ? AND r.subject_id = ?
            ''', (class_id, subject_id)).fetchone()[0]
            
            if results_count > 0:
                conn.close()
                return False, "Cannot remove subject. Results already exist for this subject in the class."
            
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
        """Get subjects not yet assigned to a class"""
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
    def get_class_statistics(class_id):
        """Get statistics for a class"""
        conn = get_db_connection()
        try:
            stats = conn.execute('''
                SELECT 
                    (SELECT COUNT(*) FROM student_enrollment WHERE class_id = ?) as student_count,
                    (SELECT COUNT(*) FROM class_subjects WHERE class_id = ?) as subject_count,
                    (SELECT COUNT(*) FROM results WHERE class_id = ?) as result_count
            ''', (class_id, class_id, class_id)).fetchone()
            conn.close()
            return stats
        except Exception as e:
            conn.close()
            return None
            
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
            # Check if subject has results
            results_count = conn.execute(
                'SELECT COUNT(*) FROM results WHERE subject_id = ?', (subject_id,)
            ).fetchone()[0]
            
            if results_count > 0:
                conn.close()
                return False, "Cannot delete subject that has results"
            
            # Check if subject is assigned to classes
            class_subjects_count = conn.execute(
                'SELECT COUNT(*) FROM class_subjects WHERE subject_id = ?', (subject_id,)
            ).fetchone()[0]
            
            if class_subjects_count > 0:
                conn.close()
                return False, "Cannot delete subject that is assigned to classes"
            
            # Delete subject
            cursor = conn.cursor()
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

class Result:
    @staticmethod
    def enter_marks(student_id, subject_id, marks_obtained, total_marks, exam_type, academic_year):
        """Enter marks for a student - automatically gets class from student"""
        conn = get_db_connection()
        try:
            # Get student's class and verify subject belongs to that class
            student = conn.execute('''
                SELECT s.class_id, c.teacher_id 
                FROM students s 
                JOIN classes c ON s.class_id = c.id 
                WHERE s.id = ?
            ''', (student_id,)).fetchone()
            
            if not student:
                conn.close()
                return None, "Student not found"
            
            # Verify subject is assigned to student's class
            valid_subject = conn.execute('''
                SELECT 1 FROM class_subjects 
                WHERE class_id = ? AND subject_id = ?
            ''', (student['class_id'], subject_id)).fetchone()
            
            if not valid_subject:
                conn.close()
                return None, "Subject not assigned to student's class"
            
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results 
                (student_id, subject_id, class_id, teacher_id, marks_obtained, total_marks, exam_type, academic_year)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (student_id, subject_id, student['class_id'], student['teacher_id'],
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
            JOIN students st ON r.student_id = st.id
            JOIN users u ON st.id = r.student_id
            JOIN users u2 ON r.teacher_id = u2.id
            WHERE r.class_id = ?
            ORDER BY u.name, s.subject_name
        ''', (class_id,)).fetchall()
        conn.close()
        return results

class Enrollment:
    @staticmethod
    def enroll_student(student_id, class_id, academic_year):
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
    def get_student_classes(student_id):
        conn = get_db_connection()
        classes = conn.execute('''
            SELECT c.*, se.academic_year
            FROM classes c
            JOIN student_enrollment se ON c.id = se.class_id
            WHERE se.student_id = ?
        ''', (student_id,)).fetchall()
        conn.close()
        return classes