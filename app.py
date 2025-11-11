import os
import logging
from datetime import datetime
from uuid import uuid4
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import string
import json
from database import *

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")

# Initialize SocketIO with eventlet
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=False)

# Initialize database
init_database()

# In-memory storage for active sessions - using user_id as key for simpler session management
active_rooms = {}
connected_sessions = {}  # Maps session_id to user_info
user_to_session = {}     # Maps user_id to session_id

def generate_meeting_id():
    """Generate a unique meeting ID"""
    return ''.join(secrets.choice(string.digits) for _ in range(10))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        # Validation
        if not name or len(name) < 2:
            flash('Name must be at least 2 characters long', 'error')
            return render_template('register.html')
        
        if not email or '@' not in email:
            flash('Please enter a valid email address', 'error')
            return render_template('register.html')
        
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters long', 'error')
            return render_template('register.html')
        
        # Check if user exists
        if get_user_by_email(email):
            flash('User with this email already exists', 'error')
            return render_template('register.html')
        
        # Create user
        user_id = create_user(name, email, password)
        if user_id:
            session['user_id'] = user_id
            flash('Account created successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Error creating account. Please try again.', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please enter both email and password', 'error')
            return render_template('login.html')

        
        # Find user
        user = get_user_by_email(email)
        
        if not user or not check_password_hash(user['password_hash'], password):
            flash('Invalid email or password', 'error')
            return render_template('login.html')
        
        session['user_id'] = user['id']
        flash('Logged in successfully!', 'success')
        return redirect(url_for('dashboard'))
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = get_user_by_id(session['user_id'])
    if not user:
        session.pop('user_id', None)
        return redirect(url_for('login'))
    
    stats = get_user_meeting_stats(user['id'])
    return render_template('dashboard.html', user=user, stats=stats)

@app.route('/meeting-history')
def meeting_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    history = get_user_meeting_history(session['user_id'])
    return jsonify({'history': history})

@app.route('/start-meeting')
def start_meeting():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meeting_id = generate_meeting_id()
    user = get_user_by_id(session['user_id'])
    
    # Create meeting
    create_meeting(meeting_id, user['id'], user['name'])
    
    # Add to meeting history
    add_meeting_history(user['id'], meeting_id, 'host', f"Meeting {meeting_id}", user['name'])
    
    flash(f'Meeting started! Meeting ID: {meeting_id}', 'success')
    return redirect(url_for('meeting_room', meeting_id=meeting_id))

@app.route('/join-meeting', methods=['POST'])
def join_meeting():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meeting_id = request.form.get('meeting_id', '').strip().replace('-', '')
    
    if not meeting_id:
        flash('Please enter a meeting ID', 'error')
        return redirect(url_for('dashboard'))
    
    if len(meeting_id) != 10 or not meeting_id.isdigit():
        flash('Meeting ID must be 10 digits', 'error')
        return redirect(url_for('dashboard'))
    
    meeting = get_meeting(meeting_id)
    if not meeting:
        flash('Meeting not found or has ended', 'error')
        return redirect(url_for('dashboard'))
    
    user = get_user_by_id(session['user_id'])
    
    # Add to meeting history
    add_meeting_history(user['id'], meeting_id, 'participant', meeting['title'], meeting['host_name'])
    
    flash(f'Joining meeting {meeting_id}...', 'success')
    return redirect(url_for('meeting_room', meeting_id=meeting_id))

@app.route('/meeting/<meeting_id>')
def meeting_room(meeting_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meeting = get_meeting(meeting_id)
    if not meeting:
        flash('Meeting not found', 'error')
        return redirect(url_for('dashboard'))
    
    user = get_user_by_id(session['user_id'])
    
    return render_template('meeting.html', user=user, meeting=meeting)

@app.route('/schedule-meeting', methods=['POST'])
def schedule_meeting():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    meeting_title = request.form.get('title', '').strip()
    meeting_time = request.form.get('datetime', '')
    
    if not meeting_title:
        flash('Please enter a meeting title', 'error')
        return redirect(url_for('dashboard'))
    
    meeting_id = generate_meeting_id()
    user = get_user_by_id(session['user_id'])
    
    # Create scheduled meeting
    create_meeting(meeting_id, user['id'], user['name'], meeting_title, meeting_time, 'scheduled')
    
    flash(f'Meeting scheduled successfully! Meeting ID: {meeting_id}', 'success')
    return redirect(url_for('dashboard'))

# Socket.IO Events
@socketio.on('connect')
def on_connect():
    # Check authentication
    if 'user_id' not in session:
        logging.debug("Connection rejected: no user_id in session")
        return False
    
    user = get_user_by_id(session['user_id'])
    if not user:
        logging.debug("Connection rejected: user not found")
        return False
    
    # Use a simple session mapping approach
    session_id = str(uuid4())
    connected_sessions[session_id] = user
    user_to_session[user['id']] = session_id
    
    # Store session_id in the socket session for later reference
    session['socket_session_id'] = session_id
    
    logging.debug(f"User {user['name']} connected with session {session_id}")
    return True

@socketio.on('disconnect')
def on_disconnect():
    socket_session_id = session.get('socket_session_id')
    
    if socket_session_id and socket_session_id in connected_sessions:
        user = connected_sessions[socket_session_id]
        logging.debug(f"User {user['name']} disconnected")
        
        # Remove from all rooms and notify others
        for room_id in list(active_rooms.keys()):
            if socket_session_id in active_rooms[room_id].get('participants', {}):
                leave_room(room_id)
                del active_rooms[room_id]['participants'][socket_session_id]
                socketio.emit('user_left', {
                    'user_name': user['name'],
                    'message': f"{user['name']} left the meeting",
                    'participants': list(active_rooms[room_id]['participants'].values())
                }, room=room_id)
        
        # Clean up session mappings
        del connected_sessions[socket_session_id]
        if user['id'] in user_to_session:
            del user_to_session[user['id']]

@socketio.on('join_meeting')
def on_join_meeting(data):
    socket_session_id = session.get('socket_session_id')
    
    if not socket_session_id or socket_session_id not in connected_sessions:
        logging.debug(f"Join meeting rejected: invalid session")
        return
    
    user = connected_sessions[socket_session_id]
    meeting_id = data.get('meeting_id')
    
    if not meeting_id:
        logging.debug("Join meeting rejected: no meeting_id")
        return
    
    logging.debug(f"User {user['name']} joining meeting {meeting_id}")
    join_room(meeting_id)
    
    # Initialize room if not exists
    if meeting_id not in active_rooms:
        active_rooms[meeting_id] = {
            'participants': {},
            'messages': []
        }
    
    # Add user to room participants
    active_rooms[meeting_id]['participants'][socket_session_id] = {
        'id': user['id'],
        'name': user['name'],
        'joined_at': datetime.now().isoformat(),
        'camera': True,
        'microphone': True
    }
    
    # Get chat history and send to new user
    chat_history = get_chat_history(meeting_id)
    emit('chat_history', {'messages': chat_history})
    
    # Notify all users in the room (including the new user)
    participants_list = list(active_rooms[meeting_id]['participants'].values())
    socketio.emit('user_joined', {
        'user_name': user['name'],
        'message': f"{user['name']} joined the meeting",
        'participants': participants_list
    }, room=meeting_id)
    
    logging.debug(f"Room {meeting_id} now has {len(participants_list)} participants")

@socketio.on('leave_meeting')
def on_leave_meeting(data):
    socket_session_id = session.get('socket_session_id')
    
    if not socket_session_id or socket_session_id not in connected_sessions:
        return
    
    user = connected_sessions[socket_session_id]
    meeting_id = data.get('meeting_id')
    
    if not meeting_id or meeting_id not in active_rooms:
        return
    
    # Remove from participants
    if socket_session_id in active_rooms[meeting_id]['participants']:
        del active_rooms[meeting_id]['participants'][socket_session_id]
    
    leave_room(meeting_id)
    
    socketio.emit('user_left', {
        'user_name': user['name'],
        'message': f"{user['name']} left the meeting",
        'participants': list(active_rooms[meeting_id]['participants'].values())
    }, room=meeting_id)

@socketio.on('send_message')
def on_send_message(data):
    socket_session_id = session.get('socket_session_id')
    
    if not socket_session_id or socket_session_id not in connected_sessions:
        emit('error', {'message': 'Not authenticated'})
        return
    
    user = connected_sessions[socket_session_id]
    meeting_id = data.get('meeting_id')
    message = data.get('message', '').strip()
    
    if not meeting_id or not message:
        emit('error', {'message': 'Invalid message data'})
        return
    
    logging.debug(f"User {user['name']} sending message to room {meeting_id}: {message}")
    
    # Save message to database
    save_chat_message(meeting_id, user['id'], user['name'], message)
    
    # Create message object
    message_obj = {
        'id': str(uuid4()),
        'user_name': user['name'],
        'message': message,
        'timestamp': datetime.now().strftime('%H:%M:%S')
    }
    
    # Broadcast message to all users in the room
    socketio.emit('new_message', message_obj, room=meeting_id)
    
    # Send confirmation to sender
    emit('message_sent', {'status': 'success', 'message': 'Message sent successfully'})
    
    logging.debug(f"Message broadcasted to room {meeting_id}")

@socketio.on('send_reaction')
def on_send_reaction(data):
    socket_session_id = session.get('socket_session_id')
    
    if not socket_session_id or socket_session_id not in connected_sessions:
        return
    
    user = connected_sessions[socket_session_id]
    meeting_id = data.get('meeting_id')
    emoji = data.get('emoji')
    
    if not meeting_id or not emoji:
        return
    
    # Create reaction object
    reaction_obj = {
        'id': str(uuid4()),
        'user_name': user['name'],
        'emoji': emoji,
        'timestamp': datetime.now().isoformat()
    }
    
    # Broadcast reaction
    socketio.emit('new_reaction', reaction_obj, room=meeting_id)

@socketio.on('toggle_camera')
def on_toggle_camera(data):
    socket_session_id = session.get('socket_session_id')
    
    if not socket_session_id or socket_session_id not in connected_sessions:
        return
    
    user = connected_sessions[socket_session_id]
    meeting_id = data.get('meeting_id')
    camera_on = data.get('camera_on', False)
    
    if not meeting_id or meeting_id not in active_rooms:
        return
    
    # Update participant status
    if socket_session_id in active_rooms[meeting_id]['participants']:
        active_rooms[meeting_id]['participants'][socket_session_id]['camera'] = camera_on
    
    socketio.emit('camera_toggled', {
        'user_id': user['id'],
        'user_name': user['name'],
        'camera_on': camera_on
    }, room=meeting_id)

@socketio.on('toggle_microphone')
def on_toggle_microphone(data):
    socket_session_id = session.get('socket_session_id')
    
    if not socket_session_id or socket_session_id not in connected_sessions:
        return
    
    user = connected_sessions[socket_session_id]
    meeting_id = data.get('meeting_id')
    mic_on = data.get('mic_on', False)
    
    if not meeting_id or meeting_id not in active_rooms:
        return
    
    # Update participant status
    if socket_session_id in active_rooms[meeting_id]['participants']:
        active_rooms[meeting_id]['participants'][socket_session_id]['microphone'] = mic_on
    
    socketio.emit('microphone_toggled', {
        'user_id': user['id'],
        'user_name': user['name'],
        'mic_on': mic_on
    }, room=meeting_id)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)