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
    
    // 시간 표시 (말풍선 바깥)
    const timeDiv = document.createElement('div');
    timeDiv.className = 'message-time';
    timeDiv.textContent = new Date().toLocaleTimeString('ko-KR', { 
        hour: '2-digit', 
        minute: '2-digit' 
    });
    
    // 말풍선과 시간을 메시지 컨테이너에 추가
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
            let errorData;
            try {
                errorData = await response.json();
            } catch (e) {
                errorData = { error: '프롬프트를 가져올 수 없습니다.' };
            }
            alert(errorData.error || '프롬프트를 가져올 수 없습니다.');
            return;
        }
        
        const data = await response.json();
        const prompt = data.prompt || '프롬프트 정보가 없습니다.';
        const taskSelectorOutput = data.task_selector_output || null;
        
        // 모달 창으로 프롬프트 표시
        showPromptModal(prompt, data.current_task, data.current_part, data.current_module, data.supervision, taskSelectorOutput);
        
    } catch (error) {
        console.error('프롬프트 가져오기 오류:', error);
        alert('프롬프트를 가져오는 중 오류가 발생했습니다: ' + (error.message || String(error)));
    }
}

// 프롬프트 모달 표시
function showPromptModal(prompt, currentTask, currentPart, currentModule, supervision, taskSelectorOutput) {
    // 기존 모달이 있으면 제거
    const existingModal = document.getElementById('prompt-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    // 모달 생성
    const modal = document.createElement('div');
    modal.id = 'prompt-modal';
    modal.className = 'prompt-modal show';
    
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
        <div>Part: ${currentPart || 'N/A'}</div>
        <div>Task: ${currentTask || 'N/A'}</div>
        <div>Module: ${currentModule || 'N/A'}</div>
    `;
    
    // Supervision 정보 추가
    if (supervision) {
        const score = supervision.score || 0;
        const isGood = score >= 7;
        infoHtml += `<div class="supervision-info ${isGood ? 'good' : 'needs-improvement'}">Supervision 점수: ${score}/10</div>`;
    }
    
    info.innerHTML = infoHtml;
    
    const body = document.createElement('div');
    body.className = 'prompt-modal-body';
    
    body.appendChild(info);
    
    // Task Selector 출력 섹션 추가
    if (taskSelectorOutput && typeof taskSelectorOutput === 'string' && taskSelectorOutput.trim()) {
        const taskSelectorSection = document.createElement('div');
        taskSelectorSection.className = 'prompt-modal-section';
        taskSelectorSection.innerHTML = `
            <div class="supervision-section-header">
                <h4>Task Selector 출력</h4>
            </div>
            <div class="prompt-text" style="margin-top: 12px; font-family: 'Courier New', monospace;">
                ${String(taskSelectorOutput).replace(/\n/g, '<br>')}
            </div>
        `;
        body.appendChild(taskSelectorSection);
    }
    
    // 메인 상담사 프롬프트 섹션
    const promptSection = document.createElement('div');
    promptSection.className = 'prompt-modal-section';
    promptSection.innerHTML = `
        <div class="supervision-section-header">
            <h4>메인 상담사 프롬프트</h4>
        </div>
        <div class="prompt-text" style="margin-top: 12px;">
            ${String(prompt).replace(/\n/g, '<br>')}
        </div>
    `;
    body.appendChild(promptSection);
    
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
        body.appendChild(supervisionSection);
    }
    
    modalContent.appendChild(header);
    modalContent.appendChild(body);
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
        
        // Part 진행 상태 표시
        updatePartProgress(session);
        
        // 현재 상태 표시 (Part, Task, Module)
        updateCurrentStatus(session);
        
        // Task 목록 표시 (Part별 구분)
        updateTaskList(session);
        
        // Supervision 로그 표시
        updateSupervisionLog(session);
        
    } catch (error) {
        console.error('세션 정보 업데이트 오류:', error);
    }
}

// Part 진행 상태 업데이트
function updatePartProgress(session) {
    const partProgressEl = document.getElementById('part-progress');
    const currentPart = session.current_part || 1;
    
    // 모든 Part 스텝 초기화
    const partSteps = partProgressEl.querySelectorAll('.part-step');
    const connectors = partProgressEl.querySelectorAll('.part-step-connector');
    
    partSteps.forEach((step, index) => {
        const partNum = index + 1;
        step.classList.remove('active', 'completed');
        
        if (partNum < currentPart) {
            step.classList.add('completed');
            if (connectors[index]) {
                connectors[index].classList.add('completed');
            }
        } else if (partNum === currentPart) {
            step.classList.add('active');
        }
    });
}

// 현재 상태 업데이트 (Part, Task, Module)
function updateCurrentStatus(session) {
    const currentPartEl = document.getElementById('current-part');
    const currentTaskTitleEl = document.getElementById('current-task-title');
    const currentModuleEl = document.getElementById('current-module');
    
    const currentPart = session.current_part || 1;
    const currentTaskId = session.current_task;
    const currentModuleId = session.current_module;
    const tasks = session.tasks || [];
    
    // Part 표시
    currentPartEl.textContent = `Part ${currentPart}`;
    
    // Task 표시
    const currentTask = tasks.find(t => t.id === currentTaskId);
    if (currentTask) {
        currentTaskTitleEl.textContent = currentTask.title || currentTask.id;
    } else {
        currentTaskTitleEl.textContent = '-';
    }
    
    // Module 표시
    if (currentModuleId) {
        currentModuleEl.textContent = currentModuleId;
    } else {
        currentModuleEl.textContent = '-';
    }
}


// Task 목록 업데이트 (Part별 구분)
function updateTaskList(session) {
    const taskListEl = document.getElementById('task-list');
    const tasks = session.tasks || [];
    const currentTaskId = session.current_task;
    
    if (tasks.length === 0) {
        taskListEl.innerHTML = '<p class="no-data">task가 없습니다.</p>';
        return;
    }
    
    // Part별로 Task 분류
    const tasksByPart = {
        1: tasks.filter(t => t.part === 1),
        2: tasks.filter(t => t.part === 2),
        3: tasks.filter(t => t.part === 3)
    };
    
    let html = '';
    
    // Part 1 Task
    if (tasksByPart[1].length > 0) {
        html += '<div class="task-group part-1">';
        html += '<div class="task-group-header">Part 1: 시작</div>';
        html += tasksByPart[1].map(task => renderTaskItem(task, currentTaskId)).join('');
        html += '</div>';
    }
    
    // Part 2 Task
    if (tasksByPart[2].length > 0) {
        html += '<div class="task-group part-2">';
        html += '<div class="task-group-header">Part 2: 탐색</div>';
        html += tasksByPart[2].map(task => renderTaskItem(task, currentTaskId)).join('');
        html += '</div>';
    }
    
    // Part 3 Task
    if (tasksByPart[3].length > 0) {
        html += '<div class="task-group part-3">';
        html += '<div class="task-group-header">Part 3: 마무리</div>';
        html += tasksByPart[3].map(task => renderTaskItem(task, currentTaskId)).join('');
        html += '</div>';
    }
    
    // Part 정보가 없는 Task (기존 데이터 호환성)
    const tasksWithoutPart = tasks.filter(t => !t.part || ![1, 2, 3].includes(t.part));
    if (tasksWithoutPart.length > 0) {
        html += '<div class="task-group">';
        html += '<div class="task-group-header">기타</div>';
        html += tasksWithoutPart.map(task => renderTaskItem(task, currentTaskId)).join('');
        html += '</div>';
    }
    
    taskListEl.innerHTML = html || '<p class="no-data">task가 없습니다.</p>';
}

// Task 아이템 렌더링 헬퍼 함수
function renderTaskItem(task, currentTaskId) {
    const isCurrent = task.id === currentTaskId;
    const taskStatus = task.status || 'pending';
    const statusBadge = getStatusBadge(taskStatus);
    
    return `
        <div class="task-item ${isCurrent ? 'current' : ''}">
            <div class="task-item-header">
                <div class="task-title">${task.title || task.id}</div>
                <span class="task-status-badge ${taskStatus}">${getStatusText(taskStatus)}</span>
            </div>
            ${task.description ? `<div class="task-description">${task.description}</div>` : ''}
        </div>
    `;
}

// 상태 텍스트 변환
function getStatusText(status) {
    const statusMap = {
        'pending': '대기',
        'in_progress': '진행',
        'sufficient': '충분',
        'completed': '완료'
    };
    return statusMap[status] || status;
}

// 상태 배지 생성 헬퍼 함수
function getStatusBadge(status) {
    const badges = {
        'pending': '<span class="task-status-badge status-pending">대기 중</span>',
        'in_progress': '<span class="task-status-badge status-in-progress">진행 중</span>',
        'sufficient': '<span class="task-status-badge status-sufficient">충분히 다뤘음</span>',
        'completed': '<span class="task-status-badge status-completed">완료됨</span>'
    };
    return badges[status] || '';
}


// Supervision 로그 업데이트
function updateSupervisionLog(session) {
    const supervisionLogEl = document.getElementById('supervision-log');
    const supervisionLog = session.supervision_log || [];
    
    if (supervisionLog.length === 0) {
        supervisionLogEl.innerHTML = '<p class="no-data">아직 supervision이 없습니다.</p>';
        return;
    }
    
    // 최근 5개만 표시
    const recentLogs = supervisionLog.slice(-5).reverse();
    
    supervisionLogEl.innerHTML = recentLogs.map(log => {
        const score = log.score || 7;
        const scoreClass = score >= 8 ? 'high' : score >= 6 ? 'medium' : 'low';
        const feedback = log.feedback || '';
        const improvements = log.improvements || '';
        const strengths = log.strengths || '';
        
        return `
            <div class="supervision-item ${score < 7 ? 'has-improvement' : 'good'}">
                <div class="supervision-header">
                    <span class="supervision-score ${scoreClass}">${score}/10</span>
                </div>
                ${feedback ? `<div class="supervision-feedback">${feedback}</div>` : ''}
                ${improvements && improvements !== '없음' ? `
                    <div class="supervision-improvements">
                        <div class="supervision-improvements-text">${improvements}</div>
                    </div>
                ` : ''}
                ${strengths && strengths !== '없음' ? `
                    <div class="supervision-strengths">
                        <div class="supervision-strengths-text">${strengths}</div>
                    </div>
                ` : ''}
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

