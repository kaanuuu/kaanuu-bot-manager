function showToast(message, type = 'info') {
    let container = document.getElementById('toastContainer');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toastContainer';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }
    
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function openModal(modalId) {
    document.getElementById(modalId).classList.add('active');
}

function closeModal(modalId) {
    document.getElementById(modalId).classList.remove('active');
}

document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal-overlay')) {
        e.target.classList.remove('active');
    }
});

async function createBot(event) {
    event.preventDefault();
    const form = event.target;
    const data = Object.fromEntries(new FormData(form));
    
    try {
        const response = await fetch('/api/create_bot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        const result = await response.json();
        if (result.success) {
            showToast('Bot created successfully!', 'success');
            setTimeout(() => location.reload(), 1000);
        } else {
            showToast(result.message || 'Failed to create bot', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function startBot(botId) {
    try {
        const response = await fetch(`/api/start_bot/${botId}`);
        const result = await response.json();
        if (result.success) {
            showToast('Bot started!', 'success');
            location.reload();
        } else {
            showToast('Failed to start bot', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function stopBot(botId) {
    try {
        const response = await fetch(`/api/stop_bot/${botId}`);
        const result = await response.json();
        if (result.success) {
            showToast('Bot stopped', 'info');
            location.reload();
        } else {
            showToast('Failed to stop bot', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function restartBot(botId) {
    try {
        const response = await fetch(`/api/restart_bot/${botId}`);
        const result = await response.json();
        if (result.success) {
            showToast('Bot restarted!', 'success');
            location.reload();
        } else {
            showToast('Failed to restart bot', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function deleteBot(botId) {
    if (!confirm('Are you sure you want to delete this bot?')) return;
    
    try {
        const response = await fetch(`/api/delete_bot/${botId}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        if (result.success) {
            showToast('Bot deleted', 'info');
            location.reload();
        } else {
            showToast('Failed to delete bot', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function addMessage(botId) {
    const input = document.getElementById(`messageInput_${botId}`);
    if (!input) return;
    
    const text = input.value.trim();
    if (!text) {
        showToast('Please enter a message', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/add_message/${botId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text })
        });
        const result = await response.json();
        if (result.success) {
            showToast('Message added!', 'success');
            input.value = '';
            loadMessages(botId);
        } else {
            showToast('Failed to add message', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function loadMessages(botId) {
    try {
        const response = await fetch(`/api/get_messages/${botId}`);
        const result = await response.json();
        if (result.success) {
            const container = document.getElementById(`messagesList_${botId}`);
            if (container) {
                container.innerHTML = result.messages.map(msg => `
                    <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 12px;background:var(--bg);border-radius:8px;margin-bottom:5px;">
                        <span>${msg.message_text}</span>
                        <button onclick="deleteMessage(${msg.id})" class="btn btn-danger btn-sm">Delete</button>
                    </div>
                `).join('');
            }
        }
    } catch (error) {
        console.error('Error loading messages:', error);
    }
}

async function deleteMessage(msgId) {
    if (!confirm('Delete this message?')) return;
    
    try {
        const response = await fetch(`/api/delete_message/${msgId}`, {
            method: 'DELETE'
        });
        const result = await response.json();
        if (result.success) {
            showToast('Message deleted', 'info');
            location.reload();
        } else {
            showToast('Failed to delete message', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function addTarget(botId) {
    const input = document.getElementById(`targetInput_${botId}`);
    if (!input) return;
    
    const targetId = input.value.trim();
    if (!targetId) {
        showToast('Please enter target user ID', 'error');
        return;
    }
    
    try {
        const response = await fetch(`/api/add_target/${botId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                target_id: targetId,
                target_username: targetId,
                chat_id: 'private'
            })
        });
        const result = await response.json();
        if (result.success) {
            showToast('Target added!', 'success');
            input.value = '';
        } else {
            showToast('Failed to add target', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function updateSetting(botId, key, value) {
    try {
        const response = await fetch(`/api/update_settings/${botId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ [key]: value })
        });
        const result = await response.json();
        if (result.success) {
            showToast('Settings updated!', 'success');
        } else {
            showToast('Failed to update settings', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

function copyCommand(text) {
    navigator.clipboard.writeText(text).then(() => {
        showToast('Command copied!', 'success');
    }).catch(() => {
        const textarea = document.createElement('textarea');
        textarea.value = text;
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
        showToast('Command copied!', 'success');
    });
}

function searchCommands() {
    const query = document.getElementById('commandSearch').value.toLowerCase();
    document.querySelectorAll('.command-item').forEach(item => {
        item.style.display = item.textContent.toLowerCase().includes(query) ? 'flex' : 'none';
    });
}

function toggleSection(sectionId) {
    const section = document.getElementById(sectionId);
    if (section) {
        section.style.display = section.style.display === 'none' ? 'block' : 'none';
    }
}

function toggleSidebar() {
    document.querySelector('.sidebar').classList.toggle('mobile-open');
}

async function logout() {
    if (!confirm('Are you sure you want to logout?')) return;
    
    try {
        const response = await fetch('/api/logout');
        const result = await response.json();
        if (result.success) {
            window.location.href = '/';
        } else {
            showToast('Logout failed', 'error');
        }
    } catch (error) {
        showToast('Network error', 'error');
    }
}

async function loadDashboardStats() {
    try {
        const response = await fetch('/api/dashboard_stats');
        const result = await response.json();
        if (result.success) {
            const stats = result.stats;
            document.querySelectorAll('.stat-number').forEach(el => {
                const key = el.dataset.stat;
                if (key && stats[key] !== undefined) {
                    el.textContent = stats[key];
                }
            });
        }
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function toggleBotTypeFields() {
    const type = document.getElementById('botTypeSelect').value;
    document.getElementById('botTokenFields').style.display = type === 'bot_token' ? 'block' : 'none';
    document.getElementById('userAPIFields').style.display = type === 'user_api' ? 'block' : 'none';
}

document.addEventListener('DOMContentLoaded', function() {
    if (document.querySelector('.stat-number')) {
        loadDashboardStats();
    }
    
    document.querySelectorAll('[data-bot-id]').forEach(el => {
        const botId = el.dataset.botId;
        if (el.id === `messagesList_${botId}`) {
            loadMessages(botId);
        }
    });
    
    document.querySelectorAll('.switch input').forEach(input => {
        input.addEventListener('change', function() {
            const botId = this.dataset.botId;
            const key = this.dataset.key;
            const value = this.checked ? 1 : 0;
            if (botId && key) {
                updateSetting(botId, key, value);
            }
        });
    });
});
