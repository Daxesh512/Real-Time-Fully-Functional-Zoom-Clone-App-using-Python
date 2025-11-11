import sqlite3
import os
from datetime import datetime
from uuid import uuid4
from werkzeug.security import generate_password_hash, check_password_hash

DATABASE_PATH = 'zoomclone.db'

def init_database():
    """Initialize the SQLite database with required tables"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Meetings table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meetings (
            id TEXT PRIMARY KEY,
            title TEXT,
            host_id TEXT NOT NULL,
            host_name TEXT NOT NULL,
            scheduled_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            FOREIGN KEY (host_id) REFERENCES users (id)
        )
    ''')
    
    # Meeting history table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS meeting_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            meeting_id TEXT NOT NULL,
            role TEXT NOT NULL,
            meeting_title TEXT,
            host_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (meeting_id) REFERENCES meetings (id)
        )
    ''')
    
    # Chat messages table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            message TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (meeting_id) REFERENCES meetings (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def create_user(name, email, password):
    """Create a new user"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        user_id = str(uuid4())
        password_hash = generate_password_hash(password)
        
        cursor.execute('''
            INSERT INTO users (id, name, email, password_hash)
            VALUES (?, ?, ?, ?)
        ''', (user_id, name, email, password_hash))
        
        conn.commit()
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def get_user_by_email(email):
    """Get user by email"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'password_hash': user[3],
            'created_at': user[4]
        }
    return None

def get_user_by_id(user_id):
    """Get user by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'name': user[1],
            'email': user[2],
            'password_hash': user[3],
            'created_at': user[4]
        }
    return None

def create_meeting(meeting_id, host_id, host_name, title=None, scheduled_time=None, status='active'):
    """Create a new meeting"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO meetings (id, title, host_id, host_name, scheduled_time, status)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (meeting_id, title or f"Meeting {meeting_id}", host_id, host_name, scheduled_time, status))
    
    conn.commit()
    conn.close()

def get_meeting(meeting_id):
    """Get meeting by ID"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM meetings WHERE id = ?', (meeting_id,))
    meeting = cursor.fetchone()
    
    conn.close()
    
    if meeting:
        return {
            'id': meeting[0],
            'title': meeting[1],
            'host_id': meeting[2],
            'host_name': meeting[3],
            'scheduled_time': meeting[4],
            'created_at': meeting[5],
            'status': meeting[6]
        }
    return None

def add_meeting_history(user_id, meeting_id, role, meeting_title, host_name):
    """Add meeting to user's history"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO meeting_history (user_id, meeting_id, role, meeting_title, host_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, meeting_id, role, meeting_title, host_name))
    
    conn.commit()
    conn.close()

def get_user_meeting_stats(user_id):
    """Get meeting statistics for a user"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Created meetings
    cursor.execute('SELECT COUNT(*) FROM meeting_history WHERE user_id = ? AND role = "host"', (user_id,))
    created = cursor.fetchone()[0]
    
    # Joined meetings
    cursor.execute('SELECT COUNT(*) FROM meeting_history WHERE user_id = ? AND role = "participant"', (user_id,))
    joined = cursor.fetchone()[0]
    
    # Scheduled meetings
    cursor.execute('SELECT COUNT(*) FROM meetings WHERE host_id = ? AND status = "scheduled"', (user_id,))
    scheduled = cursor.fetchone()[0]
    
    conn.close()
    
    return {'created': created, 'joined': joined, 'scheduled': scheduled}

def get_user_meeting_history(user_id):
    """Get user's meeting history"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT meeting_id, role, meeting_title, host_name, joined_at
        FROM meeting_history 
        WHERE user_id = ? 
        ORDER BY joined_at DESC
        LIMIT 10
    ''', (user_id,))
    
    history = cursor.fetchall()
    conn.close()
    
    return [
        {
            'meeting_id': row[0],
            'role': row[1],
            'meeting_title': row[2],
            'host_name': row[3],
            'joined_at': row[4]
        }
        for row in history
    ]

def save_chat_message(meeting_id, user_id, user_name, message):
    """Save chat message to database"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO chat_messages (meeting_id, user_id, user_name, message)
        VALUES (?, ?, ?, ?)
    ''', (meeting_id, user_id, user_name, message))
    
    conn.commit()
    conn.close()

def get_chat_history(meeting_id):
    """Get chat history for a meeting"""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT user_name, message, timestamp
        FROM chat_messages 
        WHERE meeting_id = ? 
        ORDER BY timestamp ASC
    ''', (meeting_id,))
    
    messages = cursor.fetchall()
    conn.close()
    
    return [
        {
            'user_name': row[0],
            'message': row[1],
            'timestamp': row[2]
        }
        for row in messages
    ]