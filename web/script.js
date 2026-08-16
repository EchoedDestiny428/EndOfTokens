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
const stopBtn = document.getElementById('stop-btn');
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
const tglDoubleCheck = document.getElementById('toggle-double-check');
const tglPersistence = document.getElementById('toggle-persistence');

const approvalModal = document.getElementById('approval-modal');
const approvalCommand = document.getElementById('approval-command');
const approvalReason = document.getElementById('approval-reason');
const btnApprove = document.getElementById('btn-approve');
const btnDeny = document.getElementById('btn-deny');

const questionModal = document.getElementById('question-modal');
const questionText = document.getElementById('question-text');
const questionReason = document.getElementById('question-reason');
const questionReasonContainer = document.getElementById('question-reason-container');
const questionOptions = document.getElementById('question-options');
const questionInput = document.getElementById('question-input');
const btnSubmitAnswer = document.getElementById('btn-submit-answer');

const deleteModal = document.getElementById('delete-modal');
const deleteModalText = document.getElementById('delete-modal-text');
const btnCancelDelete = document.getElementById('btn-cancel-delete');
const btnConfirmDelete = document.getElementById('btn-confirm-delete');
let sessionToDelete = null;

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

// Interactive Question Modal exposed to Python
window.showQuestionModal = function(question, reason, options) {
    questionText.innerText = question;
    if (reason && reason.trim()) {
        questionReason.innerText = reason;
        questionReasonContainer.style.display = 'block';
    } else {
        questionReasonContainer.style.display = 'none';
    }
    
    questionOptions.innerHTML = '';
    if (Array.isArray(options) && options.length > 0) {
        options.forEach(opt => {
            const pill = document.createElement('button');
            pill.className = 'option-pill';
            pill.type = 'button';
            pill.innerText = opt;
            pill.onclick = () => {
                questionInput.value = opt;
                submitUserAnswer();
            };
            questionOptions.appendChild(pill);
        });
        questionOptions.style.display = 'flex';
    } else {
        questionOptions.style.display = 'none';
    }
    
    questionInput.value = '';
    questionModal.classList.remove('hidden');
    setTimeout(() => questionInput.focus(), 80);
};

function submitUserAnswer() {
    const answer = questionInput.value.trim();
    if (!answer) return;
    questionModal.classList.add('hidden');
    pywebview.api.resolve_user_input(answer);
}

btnSubmitAnswer.addEventListener('click', submitUserAnswer);
questionInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        submitUserAnswer();
    }
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

document.getElementById('ctx-delete').addEventListener('click', () => {
    if (!contextSession) return;
    sessionToDelete = contextSession;
    deleteModalText.innerText = `Are you sure you want to delete '${contextSession.title}'?`;
    deleteModal.classList.remove('hidden');
});

btnCancelDelete.addEventListener('click', () => {
    deleteModal.classList.add('hidden');
    sessionToDelete = null;
});

btnConfirmDelete.addEventListener('click', async () => {
    if (sessionToDelete) {
        deleteModal.classList.add('hidden');
        await pywebview.api.delete_session(sessionToDelete.id);
        loadTasks();
        sessionToDelete = null;
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
    
    stopBtn.addEventListener('click', async () => {
        await pywebview.api.stop_execution();
        stopBtn.disabled = true;
        stopBtn.querySelector('span').innerText = "Stopping...";
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
            "turbo_mode": tglTurbo.checked,
            "double_check": tglDoubleCheck.checked,
            "persistence_mode": tglPersistence.checked
        });
    };

    tglPro.addEventListener('change', saveSettings);
    tglTurbo.addEventListener('change', saveSettings);
    tglDoubleCheck.addEventListener('change', saveSettings);
    tglPersistence.addEventListener('change', saveSettings);
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
    tglDoubleCheck.checked = session.settings.double_check || false;
    tglPersistence.checked = session.settings.persistence_mode || false;
    updateToggleState();

    chatHistory.innerHTML = '';
    
    // Always render this session's unique train timeline
    renderTimelineFull(session.plan || []);
    
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
    sendBtn.style.display = 'none';
    stopBtn.style.display = 'flex';
    stopBtn.disabled = false;
    stopBtn.querySelector('span').innerText = "Stop";
    chatInput.disabled = true;
    loadingIndicator.classList.remove('hidden');
    
    // Instantly reset the Train Station visualizer for the new request
    renderTimelineFull([]);
    
    // Create the thought box immediately for real-time streaming
    const thoughtBox = document.createElement('div');
    thoughtBox.className = 'thought-process-box';
    chatHistory.appendChild(thoughtBox);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    
    loadingText.innerText = "Agent Active: Planning & Executing...";
    // Start polling for timeline and thought process updates
    pollingInterval = setInterval(async () => {
        const currentSession = await pywebview.api.get_session(sessionId);
        if (currentSession) {
            if (currentSession.plan) renderTimelineFull(currentSession.plan);
            if (currentSession.thought_process) {
                thoughtBox.innerText = currentSession.thought_process;
                thoughtBox.scrollTop = thoughtBox.scrollHeight;
            }
        }
    }, 1000);

    try {
        const response = await pywebview.api.generate_response(
            sessionId, prompt,
            tglPro.checked ? "pro" : "free"
        );
        
        // Before appending the new message, ensure final thought process is captured
        if (response.session && response.session.thought_process) {
            thoughtBox.innerText = response.session.thought_process;
        } else {
            thoughtBox.remove();
        }

        appendMessage('assistant', response.content);
        
        titleDisplay.innerText = response.session.title;
        document.getElementById('current-task-stats').innerHTML = `<span>Reqs: ${response.session.stats.total_requests}</span> | <span>Time: ${response.session.stats.total_time.toFixed(1)}s</span>`;
        renderTimelineFull(response.session.plan);
    } catch (err) {
        appendMessage('assistant', `[Error]: ${err}`);
    } finally {
        if (pollingInterval) clearInterval(pollingInterval);
        stopBtn.style.display = 'none';
        sendBtn.style.display = 'inline-block';
        chatInput.disabled = false;
        loadingIndicator.classList.add('hidden');
        chatInput.focus();
    }
}
