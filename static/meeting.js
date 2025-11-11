// Meeting Room JavaScript with WebRTC Implementation
class MeetingRoom {
    constructor(config) {
        this.config = config;
        this.socket = null;
        this.startTime = Date.now();
        this.timerInterval = null;
        this.participants = new Map();
        this.isCameraOn = true;
        this.isMicrophoneOn = true;
        this.isChatVisible = true;
        this.localStream = null;
        this.screenStream = null;
        this.isScreenSharing = false;
        
        this.init();
    }

    init() {
        this.initSocket();
        this.startTimer();
        this.bindEvents();
        this.initCamera();
        this.joinMeeting();
    }

    async initCamera() {
        try {
            this.localStream = await navigator.mediaDevices.getUserMedia({
                video: true,
                audio: true
            });
            
            // Display local video
            const localVideo = document.createElement('video');
            localVideo.srcObject = this.localStream;
            localVideo.autoplay = true;
            localVideo.muted = true;
            localVideo.style.width = '100%';
            localVideo.style.height = '100%';
            localVideo.style.objectFit = 'cover';
            
            const videoPlaceholder = document.querySelector('.main-video .video-placeholder');
            if (videoPlaceholder) {
                videoPlaceholder.innerHTML = '';
                videoPlaceholder.appendChild(localVideo);
            }
            
            this.showNotification('Camera and microphone access granted', 'success');
        } catch (error) {
            console.error('Error accessing camera/microphone:', error);
            this.showNotification('Camera/microphone access denied. Please allow access and refresh.', 'warning');
            this.isCameraOn = false;
            this.isMicrophoneOn = false;
            this.updateControlButtons();
        }
    }

    initSocket() {
        this.socket = io();
        
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.showNotification('Connected to meeting server', 'success');
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.showNotification('Connection lost. Trying to reconnect...', 'warning');
        });

        this.socket.on('user_joined', (data) => {
            this.handleUserJoined(data);
        });

        this.socket.on('user_left', (data) => {
            this.handleUserLeft(data);
        });

        this.socket.on('new_message', (data) => {
            this.displayMessage(data);
        });

        this.socket.on('message_sent', (data) => {
            if (data.status === 'success') {
                this.showNotification('Message sent', 'success');
            }
        });

        this.socket.on('new_reaction', (data) => {
            this.showFloatingReaction(data);
        });

        this.socket.on('camera_toggled', (data) => {
            this.handleCameraToggled(data);
        });

        this.socket.on('microphone_toggled', (data) => {
            this.handleMicrophoneToggled(data);
        });

        this.socket.on('chat_history', (data) => {
            this.loadChatHistory(data.messages);
        });
    }

    joinMeeting() {
        this.socket.emit('join_meeting', {
            meeting_id: this.config.meetingId
        });
    }

    startTimer() {
        this.timerInterval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
            document.getElementById('timer').textContent = this.formatTime(elapsed);
        }, 1000);
    }

    formatTime(seconds) {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = seconds % 60;
        
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }

    bindEvents() {
        // Message input enter key
        const messageInput = document.getElementById('messageInput');
        messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Click outside emoji picker to close
        document.addEventListener('click', (e) => {
            const emojiContainer = document.getElementById('emojiPickerContainer');
            const emojiButton = e.target.closest('[onclick*="toggleEmojiPicker"]');
            if (!emojiContainer.contains(e.target) && !emojiButton) {
                emojiContainer.style.display = 'none';
            }
        });

        // Window before unload
        window.addEventListener('beforeunload', () => {
            this.leaveMeeting();
        });
    }

    handleUserJoined(data) {
        this.showSystemNotification(data.message);
        this.updateParticipantsList(data.participants);
        this.showNotification(`${data.user_name} joined the meeting`, 'success');
    }

    handleUserLeft(data) {
        this.showSystemNotification(data.message);
        this.updateParticipantsList(data.participants);
        this.showNotification(`${data.user_name} left the meeting`, 'info');
    }

    updateParticipantsList(participants) {
        const participantsList = document.getElementById('participantsList');
        const participantCount = document.getElementById('participantCount');
        
        // Clear existing participants (except self)
        const selfParticipant = participantsList.querySelector('.participant-item');
        participantsList.innerHTML = '';
        if (selfParticipant) {
            participantsList.appendChild(selfParticipant);
        }

        // Add other participants
        participants.forEach(participant => {
            if (participant.id !== this.config.userId) {
                this.addParticipantToList(participant);
                this.addParticipantVideo(participant);
            }
        });

        // Update count
        participantCount.textContent = participants.length;
    }

    addParticipantToList(participant) {
        const participantsList = document.getElementById('participantsList');
        const participantDiv = document.createElement('div');
        participantDiv.className = 'participant-item fade-in';
        participantDiv.id = `participant-${participant.id}`;
        
        participantDiv.innerHTML = `
            <div class="participant-avatar">
                <i class="fas fa-user"></i>
            </div>
            <div class="participant-info">
                <span class="participant-name">${participant.name}</span>
                <div class="participant-status">
                    <i class="fas fa-microphone ${participant.microphone ? 'text-success' : 'text-danger'}"></i>
                    <i class="fas fa-video ${participant.camera ? 'text-success' : 'text-danger'}"></i>
                </div>
            </div>
        `;
        
        participantsList.appendChild(participantDiv);
    }

    addParticipantVideo(participant) {
        const participantVideos = document.getElementById('participantVideos');
        const videoDiv = document.createElement('div');
        videoDiv.className = 'participant-video fade-in';
        videoDiv.id = `video-${participant.id}`;
        
        videoDiv.innerHTML = `
            <div class="video-placeholder">
                <i class="fas fa-user fa-2x text-muted"></i>
            </div>
            <div class="video-overlay">
                <span class="participant-name">${participant.name}</span>
            </div>
        `;
        
        participantVideos.appendChild(videoDiv);
    }

    sendMessage() {
        const messageInput = document.getElementById('messageInput');
        const message = messageInput.value.trim();
        
        if (!message) return;

        this.socket.emit('send_message', {
            meeting_id: this.config.meetingId,
            message: message
        });

        messageInput.value = '';
    }

    displayMessage(data) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'chat-message slide-up';
        
        const isOwnMessage = data.user_name === this.config.userName;
        
        messageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-sender" style="${isOwnMessage ? 'color: var(--success-color);' : ''}">${data.user_name}${isOwnMessage ? ' (You)' : ''}</span>
                <span class="message-time">${data.timestamp}</span>
            </div>
            <div class="message-content">${this.formatMessageContent(data.message)}</div>
        `;
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    formatMessageContent(content) {
        // Simple emoji rendering and link detection
        return content
            .replace(/:\)/g, '😊')
            .replace(/:\(/g, '😞')
            .replace(/:D/g, '😃')
            .replace(/:\|/g, '😐')
            .replace(/<3/g, '❤️')
            .replace(/(https?:\/\/[^\s]+)/g, '<a href="$1" target="_blank" class="text-primary">$1</a>');
    }

    loadChatHistory(messages) {
        const chatMessages = document.getElementById('chatMessages');
        chatMessages.innerHTML = '';
        
        messages.forEach(message => {
            this.displayMessage({
                user_name: message.user_name,
                message: message.message,
                timestamp: new Date(message.timestamp).toLocaleTimeString()
            });
        });
    }

    showSystemNotification(message) {
        const chatMessages = document.getElementById('chatMessages');
        const notificationDiv = document.createElement('div');
        notificationDiv.className = 'system-notification slide-up';
        notificationDiv.textContent = message;
        
        chatMessages.appendChild(notificationDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    sendReaction(emoji) {
        this.socket.emit('send_reaction', {
            meeting_id: this.config.meetingId,
            emoji: emoji
        });
    }

    showFloatingReaction(data) {
        const floatingReactions = document.getElementById('floatingReactions');
        const reaction = document.createElement('div');
        reaction.className = 'floating-reaction';
        reaction.textContent = data.emoji;
        
        // Random position
        reaction.style.left = Math.random() * (window.innerWidth - 100) + 'px';
        reaction.style.top = window.innerHeight - 100 + 'px';
        
        floatingReactions.appendChild(reaction);
        
        // Remove after animation
        setTimeout(() => {
            reaction.remove();
        }, 3000);
    }

    toggleCamera() {
        if (!this.localStream) {
            this.showNotification('Camera not available', 'error');
            return;
        }

        this.isCameraOn = !this.isCameraOn;
        
        const videoTrack = this.localStream.getVideoTracks()[0];
        if (videoTrack) {
            videoTrack.enabled = this.isCameraOn;
        }

        this.updateControlButtons();

        this.socket.emit('toggle_camera', {
            meeting_id: this.config.meetingId,
            camera_on: this.isCameraOn
        });

        this.showNotification(`Camera ${this.isCameraOn ? 'enabled' : 'disabled'}`, 'info');
    }

    toggleMicrophone() {
        if (!this.localStream) {
            this.showNotification('Microphone not available', 'error');
            return;
        }

        this.isMicrophoneOn = !this.isMicrophoneOn;
        
        const audioTrack = this.localStream.getAudioTracks()[0];
        if (audioTrack) {
            audioTrack.enabled = this.isMicrophoneOn;
        }

        this.updateControlButtons();

        this.socket.emit('toggle_microphone', {
            meeting_id: this.config.meetingId,
            mic_on: this.isMicrophoneOn
        });

        this.showNotification(`Microphone ${this.isMicrophoneOn ? 'enabled' : 'disabled'}`, 'info');
    }

    updateControlButtons() {
        const cameraBtn = document.getElementById('cameraBtn');
        const micBtn = document.getElementById('micBtn');
        
        if (cameraBtn) {
            if (this.isCameraOn) {
                cameraBtn.classList.remove('muted');
                cameraBtn.classList.add('active');
                cameraBtn.innerHTML = '<i class="fas fa-video"></i>';
            } else {
                cameraBtn.classList.remove('active');
                cameraBtn.classList.add('muted');
                cameraBtn.innerHTML = '<i class="fas fa-video-slash"></i>';
            }
        }

        if (micBtn) {
            if (this.isMicrophoneOn) {
                micBtn.classList.remove('muted');
                micBtn.classList.add('active');
                micBtn.innerHTML = '<i class="fas fa-microphone"></i>';
            } else {
                micBtn.classList.remove('active');
                micBtn.classList.add('muted');
                micBtn.innerHTML = '<i class="fas fa-microphone-slash"></i>';
            }
        }
    }

    async shareScreen() {
        try {
            if (this.isScreenSharing) {
                // Stop screen sharing
                if (this.screenStream) {
                    this.screenStream.getTracks().forEach(track => track.stop());
                    this.screenStream = null;
                }
                
                // Resume camera
                if (this.localStream) {
                    const localVideo = document.querySelector('.main-video video');
                    if (localVideo) {
                        localVideo.srcObject = this.localStream;
                    }
                }
                
                this.isScreenSharing = false;
                this.showNotification('Screen sharing stopped', 'info');
            } else {
                // Start screen sharing
                this.screenStream = await navigator.mediaDevices.getDisplayMedia({
                    video: true,
                    audio: true
                });
                
                // Display screen in main video area
                const localVideo = document.querySelector('.main-video video');
                if (localVideo) {
                    localVideo.srcObject = this.screenStream;
                }
                
                // Handle screen share end
                this.screenStream.getVideoTracks()[0].addEventListener('ended', () => {
                    this.shareScreen(); // Stop sharing when user ends it
                });
                
                this.isScreenSharing = true;
                this.showNotification('Screen sharing started', 'success');
            }
        } catch (error) {
            console.error('Error sharing screen:', error);
            this.showNotification('Screen sharing not supported or permission denied', 'error');
        }
    }

    toggleChat() {
        const chatSection = document.getElementById('chatSection');
        const participantsSection = document.getElementById('participantsSection');
        
        if (this.isChatVisible) {
            chatSection.style.display = 'none';
            participantsSection.style.flex = '1';
        } else {
            chatSection.style.display = 'flex';
            participantsSection.style.flex = 'none';
        }
        
        this.isChatVisible = !this.isChatVisible;
    }

    showParticipants() {
        const participantsSection = document.getElementById('participantsSection');
        participantsSection.scrollIntoView({ behavior: 'smooth' });
    }

    showReactionPicker() {
        // Quick reactions
        const reactions = ['👍', '👎', '❤️', '😂', '😮', '😢', '👏', '🔥'];
        const reaction = reactions[Math.floor(Math.random() * reactions.length)];
        this.sendReaction(reaction);
    }

    handleCameraToggled(data) {
        const participantElement = document.getElementById(`participant-${data.user_id}`);
        if (participantElement) {
            const cameraIcon = participantElement.querySelector('.fa-video, .fa-video-slash');
            if (cameraIcon) {
                cameraIcon.className = `fas fa-video${data.camera_on ? '' : '-slash'} ${data.camera_on ? 'text-success' : 'text-danger'}`;
            }
        }
    }

    handleMicrophoneToggled(data) {
        const participantElement = document.getElementById(`participant-${data.user_id}`);
        if (participantElement) {
            const micIcon = participantElement.querySelector('.fa-microphone, .fa-microphone-slash');
            if (micIcon) {
                micIcon.className = `fas fa-microphone${data.mic_on ? '' : '-slash'} ${data.mic_on ? 'text-success' : 'text-danger'}`;
            }
        }
    }

    leaveMeeting() {
        if (this.socket) {
            this.socket.emit('leave_meeting', {
                meeting_id: this.config.meetingId
            });
        }

        if (this.timerInterval) {
            clearInterval(this.timerInterval);
        }

        // Stop all streams
        if (this.localStream) {
            this.localStream.getTracks().forEach(track => track.stop());
        }
        if (this.screenStream) {
            this.screenStream.getTracks().forEach(track => track.stop());
        }
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 80px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                const bsAlert = new bootstrap.Alert(notification);
                bsAlert.close();
            }
        }, 3000);
    }
}

// Global functions for meeting controls
function toggleCamera() {
    if (window.meetingRoom) {
        window.meetingRoom.toggleCamera();
    }
}

function toggleMicrophone() {
    if (window.meetingRoom) {
        window.meetingRoom.toggleMicrophone();
    }
}

function shareScreen() {
    if (window.meetingRoom) {
        window.meetingRoom.shareScreen();
    }
}

function toggleChat() {
    if (window.meetingRoom) {
        window.meetingRoom.toggleChat();
    }
}

function showParticipants() {
    if (window.meetingRoom) {
        window.meetingRoom.showParticipants();
    }
}

function sendMessage() {
    if (window.meetingRoom) {
        window.meetingRoom.sendMessage();
    }
}

function showReactionPicker() {
    if (window.meetingRoom) {
        window.meetingRoom.showReactionPicker();
    }
}

function toggleEmojiPicker() {
    const emojiPickerContainer = document.getElementById('emojiPickerContainer');
    emojiPickerContainer.style.display = emojiPickerContainer.style.display === 'none' ? 'block' : 'none';
}

function insertEmoji(emoji) {
    const messageInput = document.getElementById('messageInput');
    messageInput.value += emoji;
    messageInput.focus();
    document.getElementById('emojiPickerContainer').style.display = 'none';
}

function leaveMeeting() {
    const modal = new bootstrap.Modal(document.getElementById('leaveMeetingModal'));
    modal.show();
}

function confirmLeaveMeeting() {
    if (window.meetingRoom) {
        window.meetingRoom.leaveMeeting();
    }
    window.location.href = '/dashboard';
}

// Initialize meeting room when page loads
document.addEventListener('DOMContentLoaded', function() {
    if (typeof MEETING_CONFIG !== 'undefined') {
        window.meetingRoom = new MeetingRoom(MEETING_CONFIG);
    }
});