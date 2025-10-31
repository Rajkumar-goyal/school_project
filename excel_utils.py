import pandas as pd
import sqlite3
from werkzeug.security import generate_password_hash
from database import get_db_connection
import io

class ExcelImporter:
    @staticmethod
    def import_users(excel_file):
        """Import users from Excel file"""
        try:
            # Read Excel file
            df = pd.read_excel(excel_file)
            
            # Validate required columns
            required_columns = ['username', 'password', 'role', 'name']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}"
            
            # Validate roles
            valid_roles = ['admin', 'teacher', 'student']
            invalid_roles = df[~df['role'].isin(valid_roles)]['role'].tolist()
            if invalid_roles:
                return False, f"Invalid roles found: {', '.join(invalid_roles)}. Valid roles are: {', '.join(valid_roles)}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            success_count = 0
            error_messages = []
            
            for index, row in df.iterrows():
                try:
                    # Check if username already exists
                    existing_user = cursor.execute(
                        'SELECT id FROM users WHERE username = ?', (row['username'],)
                    ).fetchone()
                    
                    if existing_user:
                        error_messages.append(f"Row {index + 2}: Username '{row['username']}' already exists")
                        continue
                    
                    # Hash password
                    hashed_password = generate_password_hash(str(row['password']))
                    
                    # Insert user
                    cursor.execute(
                        'INSERT INTO users (username, password, role, name, email) VALUES (?, ?, ?, ?, ?)',
                        (row['username'], hashed_password, row['role'], row['name'], row.get('email', ''))
                    )
                    success_count += 1
                    
                except Exception as e:
                    error_messages.append(f"Row {index + 2}: {str(e)}")
                    continue
            
            conn.commit()
            conn.close()
            
            message = f"Successfully imported {success_count} users."
            if error_messages:
                message += f" Errors: {'; '.join(error_messages)}"
            
            return True, message
            
        except Exception as e:
            return False, f"Error reading Excel file: {str(e)}"
    
    @staticmethod
    def import_subjects(excel_file):
        """Import subjects from Excel file"""
        try:
            df = pd.read_excel(excel_file)
            
            required_columns = ['subject_name', 'subject_code']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            success_count = 0
            error_messages = []
            
            for index, row in df.iterrows():
                try:
                    # Check if subject name or code already exists
                    existing_subject = cursor.execute(
                        'SELECT id FROM subjects WHERE subject_name = ? OR subject_code = ?',
                        (row['subject_name'], row['subject_code'])
                    ).fetchone()
                    
                    if existing_subject:
                        error_messages.append(f"Row {index + 2}: Subject '{row['subject_name']}' or code '{row['subject_code']}' already exists")
                        continue
                    
                    cursor.execute(
                        'INSERT INTO subjects (subject_name, subject_code) VALUES (?, ?)',
                        (row['subject_name'], row['subject_code'])
                    )
                    success_count += 1
                    
                except Exception as e:
                    error_messages.append(f"Row {index + 2}: {str(e)}")
                    continue
            
            conn.commit()
            conn.close()
            
            message = f"Successfully imported {success_count} subjects."
            if error_messages:
                message += f" Errors: {'; '.join(error_messages)}"
            
            return True, message
            
        except Exception as e:
            return False, f"Error reading Excel file: {str(e)}"
    
    @staticmethod
    def import_classes(excel_file):
        """Import classes from Excel file"""
        try:
            df = pd.read_excel(excel_file)
            
            required_columns = ['class_name', 'section']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            success_count = 0
            error_messages = []
            
            for index, row in df.iterrows():
                try:
                    # Check if class already exists
                    existing_class = cursor.execute(
                        'SELECT id FROM classes WHERE class_name = ? AND section = ?',
                        (row['class_name'], row['section'])
                    ).fetchone()
                    
                    if existing_class:
                        error_messages.append(f"Row {index + 2}: Class '{row['class_name']} - {row['section']}' already exists")
                        continue
                    
                    # Handle teacher assignment if provided
                    teacher_id = None
                    if 'teacher_username' in df.columns and pd.notna(row.get('teacher_username')):
                        teacher = cursor.execute(
                            'SELECT id FROM users WHERE username = ? AND role = "teacher"',
                            (row['teacher_username'],)
                        ).fetchone()
                        if teacher:
                            teacher_id = teacher['id']
                        else:
                            error_messages.append(f"Row {index + 2}: Teacher '{row['teacher_username']}' not found")
                            continue
                    
                    cursor.execute(
                        'INSERT INTO classes (class_name, section, teacher_id) VALUES (?, ?, ?)',
                        (row['class_name'], row['section'], teacher_id)
                    )
                    success_count += 1
                    
                except Exception as e:
                    error_messages.append(f"Row {index + 2}: {str(e)}")
                    continue
            
            conn.commit()
            conn.close()
            
            message = f"Successfully imported {success_count} classes."
            if error_messages:
                message += f" Errors: {'; '.join(error_messages)}"
            
            return True, message
            
        except Exception as e:
            return False, f"Error reading Excel file: {str(e)}"
    
    @staticmethod
    def import_results(excel_file):
        """Import results from Excel file"""
        try:
            df = pd.read_excel(excel_file)
            
            required_columns = ['student_username', 'subject_code', 'class_name', 'section', 'marks_obtained', 'total_marks', 'exam_type']
            missing_columns = [col for col in required_columns if col not in df.columns]
            if missing_columns:
                return False, f"Missing required columns: {', '.join(missing_columns)}"
            
            conn = get_db_connection()
            cursor = conn.cursor()
            
            success_count = 0
            error_messages = []
            
            for index, row in df.iterrows():
                try:
                    # Get student ID
                    student = cursor.execute(
                        'SELECT id FROM users WHERE username = ? AND role = "student"',
                        (row['student_username'],)
                    ).fetchone()
                    if not student:
                        error_messages.append(f"Row {index + 2}: Student '{row['student_username']}' not found")
                        continue
                    
                    # Get subject ID
                    subject = cursor.execute(
                        'SELECT id FROM subjects WHERE subject_code = ?',
                        (row['subject_code'],)
                    ).fetchone()
                    if not subject:
                        error_messages.append(f"Row {index + 2}: Subject with code '{row['subject_code']}' not found")
                        continue
                    
                    # Get class ID
                    class_data = cursor.execute(
                        'SELECT id FROM classes WHERE class_name = ? AND section = ?',
                        (row['class_name'], row['section'])
                    ).fetchone()
                    if not class_data:
                        error_messages.append(f"Row {index + 2}: Class '{row['class_name']} - {row['section']}' not found")
                        continue
                    
                    # Get teacher ID (use current user or class teacher)
                    teacher_id = class_data['teacher_id']
                    if not teacher_id:
                        error_messages.append(f"Row {index + 2}: No teacher assigned to class '{row['class_name']} - {row['section']}'")
                        continue
                    
                    # Check if result already exists
                    existing_result = cursor.execute(
                        '''SELECT id FROM results 
                         WHERE student_id = ? AND subject_id = ? AND class_id = ? AND exam_type = ?''',
                        (student['id'], subject['id'], class_data['id'], row['exam_type'])
                    ).fetchone()
                    
                    if existing_result:
                        # Update existing result
                        cursor.execute(
                            '''UPDATE results SET marks_obtained = ?, total_marks = ?, academic_year = ?
                             WHERE id = ?''',
                            (float(row['marks_obtained']), float(row['total_marks']), 
                             row.get('academic_year', '2024-2025'), existing_result['id'])
                        )
                    else:
                        # Insert new result
                        cursor.execute(
                            '''INSERT INTO results 
                            (student_id, subject_id, class_id, teacher_id, marks_obtained, total_marks, exam_type, academic_year)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                            (student['id'], subject['id'], class_data['id'], teacher_id,
                             float(row['marks_obtained']), float(row['total_marks']), 
                             row['exam_type'], row.get('academic_year', '2024-2025'))
                        )
                    
                    success_count += 1
                    
                except Exception as e:
                    error_messages.append(f"Row {index + 2}: {str(e)}")
                    continue
            
            conn.commit()
            conn.close()
            
            message = f"Successfully imported/updated {success_count} results."
            if error_messages:
                message += f" Errors: {'; '.join(error_messages)}"
            
            return True, message
            
        except Exception as e:
            return False, f"Error reading Excel file: {str(e)}"
    
    @staticmethod
    def download_template(template_type):
        """Generate template Excel files for download"""
        try:
            if template_type == 'users':
                data = {
                    'username': ['john_doe', 'jane_smith', 'bob_wilson'],
                    'password': ['password123', 'password123', 'password123'],
                    'role': ['student', 'teacher', 'admin'],
                    'name': ['John Doe', 'Jane Smith', 'Bob Wilson'],
                    'email': ['john@school.com', 'jane@school.com', 'bob@school.com']
                }
                filename = 'users_template.xlsx'
                
            elif template_type == 'subjects':
                data = {
                    'subject_name': ['Mathematics', 'Science', 'English'],
                    'subject_code': ['MATH101', 'SCI101', 'ENG101']
                }
                filename = 'subjects_template.xlsx'
                
            elif template_type == 'classes':
                data = {
                    'class_name': ['10th Grade', '11th Grade', '12th Grade'],
                    'section': ['A', 'B', 'A'],
                    'teacher_username': ['teacher1', 'teacher2', 'teacher1']
                }
                filename = 'classes_template.xlsx'
                
            elif template_type == 'results':
                data = {
                    'student_username': ['student1', 'student2', 'student1'],
                    'subject_code': ['MATH101', 'SCI101', 'ENG101'],
                    'class_name': ['10th Grade', '10th Grade', '10th Grade'],
                    'section': ['A', 'A', 'A'],
                    'marks_obtained': [85, 92, 78],
                    'total_marks': [100, 100, 100],
                    'exam_type': ['Midterm', 'Midterm', 'Midterm'],
                    'academic_year': ['2024-2025', '2024-2025', '2024-2025']
                }
                filename = 'results_template.xlsx'
            else:
                return None, "Invalid template type"
            
            df = pd.DataFrame(data)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Template')
            
            output.seek(0)
            return output, filename
            
        except Exception as e:
            return None, f"Error generating template: {str(e)}"
@classmethod
def import_students(cls, file):
    """Import students from Excel file"""
    try:
        df = pd.read_excel(file)
        
        # Validate required columns
        required_columns = ['Full Name', 'Gender', 'Date of Birth', 'Class ID', 'Roll Number', 'Father\'s Name', 'Mother\'s Name']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            return False, f"Missing required columns: {', '.join(missing_columns)}"
        
        success_count = 0
        error_count = 0
        errors = []
        
        for index, row in df.iterrows():
            try:
                full_name = str(row['Full Name']).strip()
                gender = str(row['Gender']).strip()
                date_of_birth = str(row['Date of Birth']).strip()
                class_id = int(row['Class ID'])
                roll_number = int(row['Roll Number'])
                fathers_name = str(row['Father\'s Name']).strip()
                mothers_name = str(row['Mother\'s Name']).strip()
                mobile_number = str(row['Mobile Number']).strip() if 'Mobile Number' in df.columns and pd.notna(row['Mobile Number']) else None
                
                # Validate data
                if not all([full_name, gender, date_of_birth, fathers_name, mothers_name]):
                    error_count += 1
                    errors.append(f"Row {index+2}: Missing required fields")
                    continue
                
                if gender not in ['Male', 'Female', 'Other']:
                    error_count += 1
                    errors.append(f"Row {index+2}: Invalid gender '{gender}'")
                    continue
                
                # Create student
                student_id, message = Student.create_student(
                    full_name, gender, date_of_birth, class_id, roll_number,
                    fathers_name, mobile_number, mothers_name
                )
                
                if student_id:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append(f"Row {index+2}: {message}")
                    
            except Exception as e:
                error_count += 1
                errors.append(f"Row {index+2}: Error - {str(e)}")
                continue
        
        message = f"Successfully imported {success_count} students"
        if error_count > 0:
            message += f", {error_count} failed. First few errors: {'; '.join(errors[:3])}"
        
        return True, message
        
    except Exception as e:
        return False, f"Error reading Excel file: {str(e)}"