let currentSessionId = null;

const viewHome = document.getElementById('view-home');
const viewChat = document.getElementById('view-chat');
const navHome = document.getElementById('nav-home');
const navNewTask = document.getElementById('nav-new-task');
const navDashboard = document.getElementById('nav-dashboard');
const tasksContainer = document.getElementById('tasks-container');
const chatHistory = document.getElementById('chat-history');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');
const loadingIndicator = document.getElementById('loading-indicator');
const loadingText = document.getElementById('loading-text');
const taskSettingsSection = document.getElementById('task-settings-section');
const planTimeline = document.getElementById('plan-timeline');

// Rename Logic
const titleDisplay = document.getElementById('current-task-title');
const renameInput = document.getElementById('rename-input');
const renameBtn = document.getElementById('rename-btn');

// Toggles
const tglPro = document.getElementById('toggle-pro');
const tglTurbo = document.getElementById('toggle-turbo');

const approvalModal = document.getElementById('approval-modal');
const approvalCommand = document.getElementById('approval-command');
const approvalReason = document.getElementById('approval-reason');
const btnApprove = document.getElementById('btn-approve');
const btnDeny = document.getElementById('btn-deny');

// Exposed to Python via evaluate_js
window.showApprovalModal = function(command, reason) {
    approvalCommand.innerText = command;
    approvalReason.innerText = reason;
    approvalModal.classList.remove('hidden');
};

btnApprove.addEventListener('click', () => {
    approvalModal.classList.add('hidden');
    pywebview.api.resolve_approval(true);
});

btnDeny.addEventListener('click', () => {
    approvalModal.classList.add('hidden');
    pywebview.api.resolve_approval(false);
});

window.addEventListener('pywebviewready', () => {
    initApp();
});

// Context Menu
const contextMenu = document.getElementById('context-menu');
let contextSession = null;

document.addEventListener('click', () => {
    if (contextMenu) contextMenu.classList.add('hidden');
});

document.getElementById('ctx-rename').addEventListener('click', async () => {
    if (!contextSession) return;
    const newName = prompt("Enter new task name:", contextSession.title);
    if (newName && newName.trim() !== "" && newName !== contextSession.title) {
        await pywebview.api.rename_session(contextSession.id, newName.trim());
        loadTasks();
    }
});

document.getElementById('ctx-delete').addEventListener('click', async () => {
    if (!contextSession) return;
    if (confirm(`Are you sure you want to delete '${contextSession.title}'?`)) {
        await pywebview.api.delete_session(contextSession.id);
        loadTasks();
    }
});

function initApp() {
    setupToggles();
    setupRouting();
    setupRenaming();
    loadTasks();
    
    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const prompt = chatInput.value.trim();
        if (!prompt || !currentSessionId) return;
        
        chatInput.value = '';
        appendMessage('user', prompt);
        
        await sendPromptToBackend(currentSessionId, prompt);
    });
}

function setupRenaming() {
    renameBtn.addEventListener('click', () => {
        titleDisplay.style.display = 'none';
        renameInput.style.display = 'inline-block';
        renameInput.value = titleDisplay.innerText;
        renameInput.focus();
    });

    const saveRename = async () => {
        const newTitle = renameInput.value.trim();
        if (newTitle && newTitle !== titleDisplay.innerText) {
            titleDisplay.innerText = newTitle;
            await pywebview.api.rename_session(currentSessionId, newTitle);
        }
        renameInput.style.display = 'none';
        titleDisplay.style.display = 'inline-block';
    };

    renameInput.addEventListener('blur', saveRename);
    renameInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') saveRename();
    });
}

function updateToggleState() {
    // Only handling Pro vs Auto now, others were removed
}

function setupToggles() {
    const saveSettings = async () => {
        if (!currentSessionId) return;
        updateToggleState();
        await pywebview.api.update_session_settings(currentSessionId, {
            "pro_mode": tglPro.checked,
            "turbo_mode": tglTurbo.checked
        });
    };

    tglPro.addEventListener('change', saveSettings);
    tglTurbo.addEventListener('change', saveSettings);
}

function setupRouting() {
    navHome.addEventListener('click', () => {
        viewChat.classList.remove('active-view');
        viewHome.classList.add('active-view');
        navHome.classList.add('active');
        taskSettingsSection.style.display = 'none';
        currentSessionId = null;
        loadTasks();
    });

    navNewTask.addEventListener('click', async () => {
        const session = await pywebview.api.create_session("New Task");
        openSession(session);
    });

    navDashboard.addEventListener('click', () => {
        pywebview.api.open_dashboard();
    });
}

function renderTimelineMini(plan) {
    if (!plan || plan.length === 0) return '';
    let html = '<div class="timeline-mini">';
    plan.forEach((step, index) => {
        html += `<div class="timeline-node" style="opacity: 1;"><div class="dot ${step.status}"></div> ${step.name}</div>`;
        if (index < plan.length - 1) {
            html += `<div class="timeline-line"></div>`;
        }
    });
    html += '</div>';
    return html;
}

function renderTimelineFull(plan) {
    if (!plan || plan.length === 0) {
        planTimeline.style.display = 'none';
        return;
    }
    planTimeline.style.display = 'flex';
    planTimeline.innerHTML = '';
    
    let activeNode = null;

    plan.forEach((step, index) => {
        const node = document.createElement('div');
        node.className = 'timeline-node';
        node.innerHTML = `<div class="dot ${step.status}"></div> ${step.name}`;
        
        if (step.status === 'yellow' || step.status === 'red') {
            activeNode = node;
        } else if (step.status === 'green' && !activeNode) {
            // Keep tracking the last green one if no yellow is found yet
            activeNode = node;
        }

        planTimeline.appendChild(node);
        if (index < plan.length - 1) {
            const line = document.createElement('div');
            line.className = 'timeline-line';
            planTimeline.appendChild(line);
        }
    });

    if (activeNode) {
        // Allow the DOM to paint before scrolling
        setTimeout(() => {
            activeNode.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }, 50);
    }
}

async function loadTasks() {
    const sessions = await pywebview.api.get_all_sessions();
    tasksContainer.innerHTML = '';
    
    sessions.forEach(s => {
        const card = document.createElement('div');
        card.className = 'task-card';
        card.innerHTML = `
            <h4>${s.title}</h4>
            <div class="task-metrics">
                <span>Requests: <strong>${s.stats.total_requests}</strong></span>
                <span>Time spent: <strong>${s.stats.total_time.toFixed(1)}s</strong></span>
                <span>Pro: <strong>${s.stats.pro_uses}</strong> | Auto: <strong>${s.stats.openclaw_uses}</strong></span>
            </div>
            ${renderTimelineMini(s.plan)}
        `;
        card.addEventListener('click', () => openSession(s));
        card.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            contextSession = s;
            contextMenu.style.left = `${e.pageX}px`;
            contextMenu.style.top = `${e.pageY}px`;
            contextMenu.classList.remove('hidden');
        });
        tasksContainer.appendChild(card);
    });
}

async function openSession(session) {
    currentSessionId = session.id;
    titleDisplay.innerText = session.title;
    document.getElementById('current-task-stats').innerHTML = `<span>Reqs: ${session.stats.total_requests}</span> | <span>Time: ${session.stats.total_time.toFixed(1)}s</span>`;
    
    viewHome.classList.remove('active-view');
    navHome.classList.remove('active');
    viewChat.classList.add('active-view');
    taskSettingsSection.style.display = 'block';
    
    tglPro.checked = session.settings.pro_mode || false;
    tglTurbo.checked = session.settings.turbo_mode || false;
    updateToggleState();

    chatHistory.innerHTML = '';
    
    // Add thought process box if it exists
    if (session.thought_process && session.thought_process.trim() !== "") {
        const thoughtDiv = document.createElement('div');
        thoughtDiv.className = 'thought-process-box';
        thoughtDiv.innerText = session.thought_process;
        chatHistory.appendChild(thoughtDiv);
    }
    
    session.history.forEach(msg => appendMessage(msg.role, msg.content));
}

function appendMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role === 'user' ? 'msg-user' : 'msg-bot'}`;
    
    const label = document.createElement('div');
    label.className = 'msg-label';
    label.innerText = role === 'user' ? 'You' : 'Agent';
    
    const text = document.createElement('div');
    text.innerText = content;
    
    div.appendChild(label);
    div.appendChild(text);
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

// Polling interval for timeline updates during End Of Tokens execution
let pollingInterval = null;

async function sendPromptToBackend(sessionId, prompt) {
    sendBtn.disabled = true;
    chatInput.disabled = true;
    loadingIndicator.classList.remove('hidden');
    
    // Instantly reset the Train Station visualizer for the new request
    renderTimelineFull([]);
    
    loadingText.innerText = "Agent Active: Planning & Executing...";
    // Start polling for timeline updates unconditionally since End Of Tokens is default
    pollingInterval = setInterval(async () => {
        const currentSession = await pywebview.api.get_session(sessionId);
        if (currentSession && currentSession.plan) {
            renderTimelineFull(currentSession.plan);
        }
    }, 1000);

    try {
        const response = await pywebview.api.generate_response(
            sessionId, prompt,
            tglPro.checked ? "pro" : "free"
        );
        
        // Before appending the new message, check if there's a new thought process to append
        if (response.session && response.session.thought_process) {
            const thoughtDiv = document.createElement('div');
            thoughtDiv.className = 'thought-process-box';
            thoughtDiv.innerText = response.session.thought_process;
            chatHistory.appendChild(thoughtDiv);
        }

        appendMessage('assistant', response.content);
        
        titleDisplay.innerText = response.session.title;
        document.getElementById('current-task-stats').innerHTML = `<span>Reqs: ${response.session.stats.total_requests}</span> | <span>Time: ${response.session.stats.total_time.toFixed(1)}s</span>`;
        renderTimelineFull(response.session.plan);
    } catch (err) {
        appendMessage('assistant', `[Error]: ${err}`);
    } finally {
        if (pollingInterval) clearInterval(pollingInterval);
        sendBtn.disabled = false;
        chatInput.disabled = false;
        loadingIndicator.classList.add('hidden');
        chatInput.focus();
    }
}
