import os
import sqlite3
from werkzeug.security import generate_password_hash

def reset_database():
    """Completely reset the database with no sample data"""
    
    # Remove existing database
    if os.path.exists('school_results.db'):
        os.remove('school_results.db')
        print("Old database removed")
    
    # Create new database
    conn = sqlite3.connect('school_results.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'teacher', 'student')),
            name TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Classes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL UNIQUE,
            section TEXT,
            teacher_id INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    # Subjects table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL UNIQUE,
            subject_code TEXT UNIQUE
        )
    ''')
    
    # Class-Subjects relationship table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS class_subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            is_compulsory BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            UNIQUE(class_id, subject_id)
        )
    ''')
    
    # Student enrollment table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS student_enrollment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            academic_year TEXT,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (class_id) REFERENCES classes (id),
            UNIQUE(student_id, class_id, academic_year)
        )
    ''')
    
    # Results table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            class_id INTEGER NOT NULL,
            teacher_id INTEGER NOT NULL,
            marks_obtained REAL NOT NULL,
            total_marks REAL NOT NULL,
            exam_type TEXT,
            exam_date DATE DEFAULT CURRENT_DATE,
            academic_year TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES users (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            FOREIGN KEY (class_id) REFERENCES classes (id),
            FOREIGN KEY (teacher_id) REFERENCES users (id)
        )
    ''')
    
    # Students table with detailed information
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT UNIQUE NOT NULL,
            full_name TEXT NOT NULL,
            gender TEXT NOT NULL CHECK(gender IN ('Male', 'Female', 'Other')),
            date_of_birth DATE NOT NULL,
            class_id INTEGER NOT NULL,
            roll_number INTEGER NOT NULL,
            fathers_name TEXT NOT NULL,
            mobile_number TEXT,
            mothers_name TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes (id),
            UNIQUE(class_id, roll_number)
        )
    ''')
    
    # Insert ONLY the admin user - no other sample data
    hashed_password = generate_password_hash('admin123')
    cursor.execute('''
        INSERT INTO users (username, password, role, name, email)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', hashed_password, 'admin', 'System Administrator', 'admin@school.com'))
    
    conn.commit()
    conn.close()
    print("Database reset successfully!")
    print("Only admin user created:")
    print("Username: admin")
    print("Password: admin123")

if __name__ == '__main__':
    reset_database()