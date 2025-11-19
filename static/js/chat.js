// 전역 변수
let conversationId = null;
const API_BASE_URL = '';

// DOM 요소
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const newConversationBtn = document.getElementById('new-conversation-btn');
const conversationIdDisplay = document.getElementById('conversation-id-display');
const sidebar = document.getElementById('sidebar');
const toggleSidebarBtn = document.getElementById('toggle-sidebar-btn');
const closeSidebarBtn = document.getElementById('close-sidebar-btn');

// 세션 정보 업데이트 인터벌
let sessionUpdateInterval = null;

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 새 대화 시작
    newConversationBtn.addEventListener('click', startNewConversation);
    
    // 전송 버튼 클릭
    sendBtn.addEventListener('click', sendMessage);
    
    // 사이드바 토글
    toggleSidebarBtn.addEventListener('click', () => {
        sidebar.classList.toggle('open');
    });
    
    closeSidebarBtn.addEventListener('click', () => {
        sidebar.classList.remove('open');
    });
    
    // Enter 키로 전송 (Shift+Enter는 줄바꿈)
    messageInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // 텍스트 영역 자동 높이 조절
    messageInput.addEventListener('input', () => {
        messageInput.style.height = 'auto';
        messageInput.style.height = messageInput.scrollHeight + 'px';
    });
    
    // 첫 대화 자동 생성
    startNewConversation();
});

// 새 대화 시작
async function startNewConversation() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/conversations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: 'web_user'
            })
        });
        
        if (!response.ok) {
            throw new Error('대화 생성 실패');
        }
        
        const data = await response.json();
        conversationId = data.conversation_id;
        conversationIdDisplay.textContent = `대화 ID: ${conversationId.substring(0, 8)}...`;
        
        // 채팅 메시지 초기화
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <p>안녕! 나는 CBot이야. 편하게 이야기해줘. 무엇이든 들어줄게. 💙</p>
            </div>
        `;
        
        // 세션 정보 업데이트 시작
        startSessionUpdates();
        
        // 기존 대화 불러오기 (선택사항)
        // loadConversationHistory();
        
    } catch (error) {
        console.error('대화 생성 오류:', error);
        showError('대화를 시작할 수 없습니다. 다시 시도해주세요.');
    }
}

// 메시지 전송
async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) {
        return;
    }
    
    if (!conversationId) {
        await startNewConversation();
    }
    
    // 사용자 메시지 표시
    addMessage('user', message);
    messageInput.value = '';
    messageInput.style.height = 'auto';
    
    // 입력 비활성화
    setInputDisabled(true);
    
    // 타이핑 인디케이터 표시
    const typingIndicator = showTypingIndicator();
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message
            })
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || '메시지 전송 실패');
        }
        
        const data = await response.json();
        
        // 타이핑 인디케이터 제거
        removeTypingIndicator(typingIndicator);
        
        // 대화 기록 가져와서 메시지 인덱스 확인
        try {
            const convResponse = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`);
            if (convResponse.ok) {
                const conversation = await convResponse.json();
                const messages = conversation.messages || [];
                const messageIndex = messages.length - 1; // 방금 추가된 메시지의 인덱스
                addMessage('assistant', data.response, messageIndex);
            } else {
                addMessage('assistant', data.response);
            }
        } catch (error) {
            console.error('대화 기록 가져오기 오류:', error);
            addMessage('assistant', data.response);
        }
        
        // 세션 정보 즉시 업데이트
        updateSessionInfo();
        
    } catch (error) {
        console.error('메시지 전송 오류:', error);
        removeTypingIndicator(typingIndicator);
        showError('메시지를 전송할 수 없습니다. 다시 시도해주세요.');
    } finally {
        setInputDisabled(false);
        messageInput.focus();
    }
}

// 메시지 추가
function addMessage(role, content, messageIndex = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    // 메시지 인덱스 저장 (assistant 메시지의 경우 프롬프트 조회용)
    if (messageIndex !== null) {
        messageDiv.dataset.messageIndex = messageIndex;
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
    // assistant 메시지인 경우 클릭 가능하게 표시
    if (role === 'assistant' && messageIndex !== null) {
        contentDiv.style.cursor = 'pointer';
        contentDiv.title = '클릭하여 프롬프트 보기';
        contentDiv.addEventListener('click', () => showPrompt(messageIndex));
    }
    
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(timeDiv);
    
    // 환영 메시지 제거
    const welcomeMessage = chatMessages.querySelector('.welcome-message');
    if (welcomeMessage) {
        welcomeMessage.remove();
    }
    
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// 프롬프트 표시
async function showPrompt(messageIndex) {
    if (!conversationId) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}/messages/${messageIndex}/prompt`);
        
        if (!response.ok) {
            const errorData = await response.json();
            alert(errorData.error || '프롬프트를 가져올 수 없습니다.');
            return;
        }
        
        const data = await response.json();
        const prompt = data.prompt || '프롬프트 정보가 없습니다.';
        
        // 모달 창으로 프롬프트 표시
        showPromptModal(prompt, data.current_task, data.tasks_remaining, data.supervision);
        
    } catch (error) {
        console.error('프롬프트 가져오기 오류:', error);
        alert('프롬프트를 가져오는 중 오류가 발생했습니다.');
    }
}

// 프롬프트 모달 표시
function showPromptModal(prompt, currentTask, tasksRemaining, supervision) {
    // 기존 모달이 있으면 제거
    const existingModal = document.getElementById('prompt-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 모달 생성
    const modal = document.createElement('div');
    modal.id = 'prompt-modal';
    modal.className = 'prompt-modal';
    
    const modalContent = document.createElement('div');
    modalContent.className = 'prompt-modal-content';
    
    const header = document.createElement('div');
    header.className = 'prompt-modal-header';
    header.innerHTML = `
        <h3>프롬프트 전문</h3>
        <button class="prompt-modal-close" onclick="this.closest('.prompt-modal').remove()">×</button>
    `;
    
    const info = document.createElement('div');
    info.className = 'prompt-modal-info';
    let infoHtml = `
        <div>현재 Task: ${currentTask || 'N/A'}</div>
        <div>남은 Tasks: ${tasksRemaining || 0}</div>
    `;
    
    // Supervision 정보 추가
    if (supervision) {
        const score = supervision.score || 0;
        const isGood = score >= 7;
        infoHtml += `<div class="supervision-info ${isGood ? 'good' : 'needs-improvement'}">Supervision 점수: ${score}/10</div>`;
    }
    
    info.innerHTML = infoHtml;
    
    const promptText = document.createElement('pre');
    promptText.className = 'prompt-modal-text';
    promptText.textContent = prompt;
    
    modalContent.appendChild(header);
    modalContent.appendChild(info);
    
    // Supervision 피드백 섹션 추가
    if (supervision) {
        const supervisionSection = document.createElement('div');
        supervisionSection.className = 'prompt-modal-supervision';
        const score = supervision.score || 0;
        const isGood = score >= 7;
        
        let supervisionHtml = `
            <div class="supervision-section-header ${isGood ? 'good' : 'needs-improvement'}">
                <h4>Supervision 피드백</h4>
                <span class="supervision-score-badge ${isGood ? 'good' : 'needs-improvement'}">${score}/10</span>
            </div>
        `;
        
        if (supervision.feedback) {
            supervisionHtml += `<div class="supervision-feedback-text">${supervision.feedback}</div>`;
        }
        
        if (supervision.improvements && supervision.improvements !== '없음') {
            supervisionHtml += `<div class="supervision-improvements-text"><strong>개선점:</strong> ${supervision.improvements}</div>`;
        }
        
        if (supervision.strengths && supervision.strengths !== '없음') {
            supervisionHtml += `<div class="supervision-strengths-text"><strong>잘한 점:</strong> ${supervision.strengths}</div>`;
        }
        
        supervisionSection.innerHTML = supervisionHtml;
        modalContent.appendChild(supervisionSection);
    }
    
    modalContent.appendChild(promptText);
    modal.appendChild(modalContent);
    
    document.body.appendChild(modal);
    
    // 모달 외부 클릭 시 닫기
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });
    
    // ESC 키로 닫기
    const handleEsc = (e) => {
        if (e.key === 'Escape') {
            modal.remove();
            document.removeEventListener('keydown', handleEsc);
        }
    };
    document.addEventListener('keydown', handleEsc);
}

// 타이핑 인디케이터 표시
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.className = 'message assistant';
    typingDiv.id = 'typing-indicator';
    
    const indicatorDiv = document.createElement('div');
    indicatorDiv.className = 'typing-indicator';
    
    for (let i = 0; i < 3; i++) {
        const dot = document.createElement('div');
        dot.className = 'typing-dot';
        indicatorDiv.appendChild(dot);
    }
    
    typingDiv.appendChild(indicatorDiv);
    chatMessages.appendChild(typingDiv);
    scrollToBottom();
    
    return typingDiv;
}

// 타이핑 인디케이터 제거
function removeTypingIndicator(indicator) {
    if (indicator && indicator.parentNode) {
        indicator.parentNode.removeChild(indicator);
    }
}

// 스크롤을 맨 아래로
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 입력 비활성화/활성화
function setInputDisabled(disabled) {
    messageInput.disabled = disabled;
    sendBtn.disabled = disabled;
    
    if (disabled) {
        sendBtn.innerHTML = '<div class="loading"></div>';
    } else {
        sendBtn.innerHTML = '<span>전송</span>';
    }
}

// 에러 메시지 표시
function showError(message) {
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message assistant';
    errorDiv.style.color = '#dc3545';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.style.background = '#fff5f5';
    contentDiv.style.border = '1px solid #feb2b2';
    contentDiv.textContent = `❌ ${message}`;
    
    errorDiv.appendChild(contentDiv);
    chatMessages.appendChild(errorDiv);
    scrollToBottom();
}

// 세션 정보 업데이트 시작
function startSessionUpdates() {
    // 기존 인터벌 정리
    if (sessionUpdateInterval) {
        clearInterval(sessionUpdateInterval);
    }
    
    // 즉시 한 번 실행
    updateSessionInfo();
    
    // 2초마다 업데이트
    sessionUpdateInterval = setInterval(() => {
        if (conversationId) {
            updateSessionInfo();
        }
    }, 2000);
}

// 세션 정보 업데이트
async function updateSessionInfo() {
    if (!conversationId) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/sessions/${conversationId}`);
        
        if (!response.ok) {
            return;
        }
        
        const session = await response.json();
        
        // 현재 task 표시
        updateCurrentTask(session);
        
        // Task 목록 표시
        updateTaskList(session);
        
        // 완료된 task 표시
        updateCompletedTasks(session);
        
        // Supervision 로그 표시
        updateSupervisionLog(session);
        
    } catch (error) {
        console.error('세션 정보 업데이트 오류:', error);
    }
}

// 현재 task 업데이트
function updateCurrentTask(session) {
    const currentTaskEl = document.getElementById('current-task');
    const currentTaskId = session.current_task;
    const tasks = session.tasks || [];
    
    const currentTask = tasks.find(t => t.id === currentTaskId);
    
    if (currentTask) {
        const moduleInfo = currentTask.module ? 
            `<div class="task-module">🔧 Module: ${currentTask.module.name || currentTask.module.id}</div>` : 
            (currentTask.module_id ? `<div class="task-module">🔧 Module: ${currentTask.module_id}</div>` : '');
        
        currentTaskEl.innerHTML = `
            <div class="task-title">${currentTask.title || currentTask.id}</div>
            <div class="task-description">${currentTask.description || ''}</div>
            ${moduleInfo}
            <div class="task-meta">
                <span class="task-priority ${currentTask.priority || 'medium'}">${currentTask.priority || 'medium'}</span>
                ${currentTask.target ? `<div class="task-target">목표: ${currentTask.target}</div>` : ''}
            </div>
        `;
    } else {
        currentTaskEl.innerHTML = '<p class="no-task">아직 task가 없습니다.</p>';
    }
}

// Task 목록 업데이트
function updateTaskList(session) {
    const taskListEl = document.getElementById('task-list');
    const tasks = session.tasks || [];
    const currentTaskId = session.current_task;
    
    if (tasks.length === 0) {
        taskListEl.innerHTML = '<p class="no-task">task가 없습니다.</p>';
        return;
    }
    
    taskListEl.innerHTML = tasks.map(task => {
        const isCurrent = task.id === currentTaskId;
        const moduleInfo = task.module ? 
            `<div class="task-module">🔧 ${task.module.name || task.module.id}</div>` : 
            (task.module_id ? `<div class="task-module">🔧 ${task.module_id}</div>` : '');
        
        return `
            <div class="task-item ${isCurrent ? 'current' : ''}">
                <div class="task-title">${task.title || task.id}</div>
                <div class="task-description">${task.description || ''}</div>
                ${moduleInfo}
                <div class="task-meta">
                    <span class="task-priority ${task.priority || 'medium'}">${task.priority || 'medium'}</span>
                    ${isCurrent ? '<span style="color: #667eea; font-weight: 600;">진행 중</span>' : ''}
                </div>
            </div>
        `;
    }).join('');
}

// 완료된 task 업데이트
function updateCompletedTasks(session) {
    const completedTasksEl = document.getElementById('completed-tasks');
    const completedTasks = session.completed_tasks || [];
    
    if (completedTasks.length === 0) {
        completedTasksEl.innerHTML = '<p class="no-task">완료된 task가 없습니다.</p>';
        return;
    }
    
    completedTasksEl.innerHTML = completedTasks.map(task => {
        const moduleInfo = task.module ? 
            `<div class="task-module">🔧 ${task.module.name || task.module.id}</div>` : 
            (task.module_id ? `<div class="task-module">🔧 ${task.module_id}</div>` : '');
        
        return `
            <div class="task-item completed">
                <div class="task-title">${task.title || task.id}</div>
                <div class="task-description">${task.description || ''}</div>
                ${moduleInfo}
                <div class="task-meta">
                    <span class="task-priority ${task.priority || 'medium'}">${task.priority || 'medium'}</span>
                    <span>완료됨</span>
                </div>
            </div>
        `;
    }).join('');
}

// Supervision 로그 업데이트
function updateSupervisionLog(session) {
    const supervisionLogEl = document.getElementById('supervision-log');
    const supervisionLog = session.supervision_log || [];
    
    if (supervisionLog.length === 0) {
        supervisionLogEl.innerHTML = '<p class="no-task">아직 supervision이 없습니다.</p>';
        return;
    }
    
    // 최근 5개만 표시
    const recentLogs = supervisionLog.slice(-5).reverse();
    
    supervisionLogEl.innerHTML = recentLogs.map(log => {
        const score = log.score || 7;
        const isGood = score >= 7;
        const feedback = log.feedback || '';
        const improvements = log.improvements || '';
        const strengths = log.strengths || '';
        
        return `
            <div class="supervision-item ${isGood ? 'good' : 'needs-improvement'}">
                <div class="supervision-score ${isGood ? 'good' : 'needs-improvement'}">
                    점수: ${score}/10
                </div>
                <div class="supervision-feedback">
                    ${feedback}
                </div>
                ${improvements && improvements !== '없음' ? `<div class="supervision-improvements">개선점: ${improvements}</div>` : ''}
                ${strengths && strengths !== '없음' ? `<div class="supervision-strengths">잘한 점: ${strengths}</div>` : ''}
            </div>
        `;
    }).join('');
}

// 대화 기록 불러오기 (선택사항)
async function loadConversationHistory() {
    if (!conversationId) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/conversations/${conversationId}`);
        
        if (!response.ok) {
            return;
        }
        
        const conversation = await response.json();
        const messages = conversation.messages || [];
        
        // 환영 메시지 제거
        const welcomeMessage = chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        // 메시지 표시
        messages.forEach(msg => {
            addMessage(msg.role, msg.content);
        });
        
    } catch (error) {
        console.error('대화 기록 불러오기 오류:', error);
    }
}

