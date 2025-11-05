import sqlite3
import os
from werkzeug.security import generate_password_hash

def init_db():
    """Initialize the database with empty tables - no sample data"""
    conn = sqlite3.connect('school_results.db')
    cursor = conn.cursor()
    
    # ... (users, classes, subjects tables are the same) ...
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_name TEXT NOT NULL,
            section TEXT,
            teacher_id INTEGER,
            FOREIGN KEY (teacher_id) REFERENCES users (id),
            UNIQUE(class_name, section)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_name TEXT NOT NULL UNIQUE,
            subject_code TEXT UNIQUE
        )
    ''')
    
    # ... (class_subjects, student_enrollment, results, students tables are the same) ...
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
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
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE(class_id, roll_number)
        )
    ''')
    
    #
    # >>> NEW TABLE: Teacher Subject Assignments <<<
    # This table links teachers to the subjects they are allowed to teach.
    #
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS teacher_subject_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            subject_id INTEGER NOT NULL,
            FOREIGN KEY (teacher_id) REFERENCES users (id),
            FOREIGN KEY (subject_id) REFERENCES subjects (id),
            UNIQUE(teacher_id, subject_id)
        )
    ''')
    
    # ... (admin user creation is the same) ...
    hashed_password = generate_password_hash('admin123')
    cursor.execute('''
        INSERT OR IGNORE INTO users (username, password, role, name, email)
        VALUES (?, ?, ?, ?, ?)
    ''', ('admin', hashed_password, 'admin', 'System Administrator', 'admin@school.com'))
    
    conn.commit()
    conn.close()
    print("Database initialized with empty tables")

def get_db_connection():
    """Get a database connection"""
    conn = sqlite3.connect('school_results.db')
    conn.row_factory = sqlite3.Row
    return conn