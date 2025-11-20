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

// 세션 정보 업데이트 인터벌
let sessionUpdateInterval = null;

// 페르소나 선택 관련 변수
let selectedPersonaType = null;
let selectedCounselingLevel = null;

// 아코디언 섹션 토글 함수
function toggleSection(header) {
    const section = header.parentElement;
    const content = section.querySelector('.info-section-content');
    const icon = header.querySelector('.toggle-icon');
    
    const isCollapsed = section.classList.contains('collapsed');
    
    if (isCollapsed) {
        section.classList.remove('collapsed');
        content.style.display = 'block';
        icon.textContent = '▼';
    } else {
        section.classList.add('collapsed');
        content.style.display = 'none';
        icon.textContent = '▶';
    }
}

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 페르소나 선택 모달 초기화
    initPersonaSelection();
    
    // 새 대화 시작 버튼 (페르소나 선택 모달에서)
    document.getElementById('start-conversation-btn').addEventListener('click', startNewConversationWithPersona);
    
    // 페르소나 타입 선택 변경
    document.getElementById('persona-type-select').addEventListener('change', (e) => {
        selectedPersonaType = e.target.value;
        updatePersonaDescription(e.target.value);
        checkCanStartConversation();
    });
    
    // 상담 레벨 선택 변경
    document.getElementById('counseling-level-select').addEventListener('change', (e) => {
        selectedCounselingLevel = parseInt(e.target.value);
        checkCanStartConversation();
    });
    
    // 새 대화 시작 버튼 (헤더)
    newConversationBtn.addEventListener('click', () => {
        showPersonaSelectionModal();
    });
    
    // 전송 버튼 클릭
    sendBtn.addEventListener('click', sendMessage);
    
    
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
    
    // 페르소나 선택 모달 표시
    showPersonaSelectionModal();
});

// 새 대화 시작 (페르소나 선택 없이 - 호환성 유지)
async function startNewConversation() {
    // 페르소나 선택 모달 표시
    showPersonaSelectionModal();
}

// 메시지 전송
async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message) {
        return;
    }
    
    if (!conversationId) {
        showPersonaSelectionModal();
        return;
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
        
        // Part별 콘텐츠 동적 표시
        updatePartContent(session);
        
        // Task Completion Checker 로그 표시 (우측 패널)
        updateCompletionLog(session);
        
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

// Part별 콘텐츠 동적 업데이트
function updatePartContent(session) {
    const currentPart = session.current_part || 1;
    const currentTaskId = session.current_task;
    const currentModuleId = session.current_module;
    const tasks = session.tasks || [];
    const part2Goal = session.part2_goal;
    const selectedKeywords = session.part2_selected_keywords || [];
    
    // 현재 Task 찾기
    const currentTask = tasks.find(t => t.id === currentTaskId);
    const currentTaskTitle = currentTask ? (currentTask.title || currentTask.id) : '-';
    const currentModule = currentModuleId || '-';
    
    // Part별 콘텐츠 표시/숨김
    document.getElementById('part1-content').style.display = currentPart === 1 ? 'block' : 'none';
    document.getElementById('part2-content').style.display = currentPart === 2 ? 'block' : 'none';
    document.getElementById('part3-content').style.display = currentPart === 3 ? 'block' : 'none';
    
    // Part 1 콘텐츠 업데이트
    if (currentPart === 1) {
        document.getElementById('current-task-title').textContent = currentTaskTitle;
        document.getElementById('current-module').textContent = currentModule;
        
        const part1Tasks = tasks.filter(t => t.part === 1);
        const taskListPart1 = document.getElementById('task-list-part1');
        if (part1Tasks.length > 0) {
            taskListPart1.innerHTML = part1Tasks.map(task => renderTaskItem(task, currentTaskId)).join('');
        } else {
            taskListPart1.innerHTML = '<p class="no-data">task가 없습니다.</p>';
        }
    }
    
    // Part 2 콘텐츠 업데이트
    if (currentPart === 2) {
        // Part 2 목표 업데이트
        const part2GoalText = document.getElementById('part2-goal-text');
        const part2Keywords = document.getElementById('part2-keywords');
        const keywordsList = document.getElementById('keywords-list');
        
        if (part2Goal) {
            part2GoalText.innerHTML = `<span class="goal-text">${part2Goal}</span>`;
            
            if (selectedKeywords.length > 0) {
                keywordsList.innerHTML = selectedKeywords.map(keyword => 
                    `<span class="keyword-badge">${keyword}</span>`
                ).join('');
                part2Keywords.style.display = 'flex';
            } else {
                part2Keywords.style.display = 'none';
            }
        } else {
            part2GoalText.innerHTML = '<span class="placeholder-text">목표가 설정되면 표시됩니다.</span>';
            part2Keywords.style.display = 'none';
        }
        
        // 현재 작업 업데이트
        document.getElementById('current-task-title-part2').textContent = currentTaskTitle;
        document.getElementById('current-module-part2').textContent = currentModule;
        
        // Part 2 Task 목록 업데이트
        const part2Tasks = tasks.filter(t => t.part === 2);
        const taskListPart2 = document.getElementById('task-list-part2');
        if (part2Tasks.length > 0) {
            taskListPart2.innerHTML = part2Tasks.map(task => renderTaskItem(task, currentTaskId)).join('');
        } else {
            taskListPart2.innerHTML = '<p class="no-data">task가 없습니다.</p>';
        }
    }
    
    // Part 3 콘텐츠 업데이트
    if (currentPart === 3) {
        document.getElementById('current-task-title-part3').textContent = currentTaskTitle;
        document.getElementById('current-module-part3').textContent = currentModule;
        
        const part3Tasks = tasks.filter(t => t.part === 3);
        const taskListPart3 = document.getElementById('task-list-part3');
        if (part3Tasks.length > 0) {
            taskListPart3.innerHTML = part3Tasks.map(task => renderTaskItem(task, currentTaskId)).join('');
        } else {
            taskListPart3.innerHTML = '<p class="no-data">task가 없습니다.</p>';
        }
    }
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

function updateCompletionLog(session) {
    const completionLogEl = document.getElementById('completion-log');
    const completionLog = session.completion_log || [];
    
    if (completionLog.length === 0) {
        completionLogEl.innerHTML = '<p class="no-data">아직 완료 체크가 없습니다.</p>';
        return;
    }
    
    // 최근 5개만 표시
    const recentLogs = completionLog.slice(-5).reverse();
    
    completionLogEl.innerHTML = recentLogs.map(log => {
        const newStatus = log.new_status || null;
        const completionReason = log.completion_reason || '';
        const taskId = log.task_id || 'N/A';
        
        // new_status가 있으면 완료된 것으로 간주 (sufficient 또는 completed)
        const isCompleted = newStatus !== null && newStatus !== 'None';
        
        // 현재 Task 목록에서 Task 제목 찾기
        const tasks = session.tasks || [];
        const task = tasks.find(t => t.id === taskId);
        const taskTitle = task ? task.title : taskId;
        
        // 상태 표시 텍스트 결정
        let statusText = '✗ 미완료';
        let statusClass = 'no';
        if (isCompleted) {
            if (newStatus === 'completed') {
                statusText = '✓ 완료';
                statusClass = 'yes';
            } else if (newStatus === 'sufficient') {
                statusText = '○ 충분';
                statusClass = 'sufficient';
            }
        }
        
        return `
            <div class="completion-item ${isCompleted ? 'completed' : 'not-completed'}">
                <div class="completion-header">
                    <span class="completion-status ${statusClass}">
                        ${statusText}
                    </span>
                    <span class="completion-task">${taskTitle}</span>
                </div>
                ${completionReason ? `
                    <div class="completion-reason">${completionReason}</div>
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

// 페르소나 선택 모달 초기화
async function initPersonaSelection() {
    try {
        console.log('페르소나 목록 로드 시작...');
        const response = await fetch(`${API_BASE_URL}/admin/api/personas`);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('페르소나 목록 로드 실패:', response.status, errorData);
            showPersonaLoadError();
            return;
        }
        
        const data = await response.json();
        console.log('페르소나 목록 응답:', data);
        
        if (data.personas && Array.isArray(data.personas) && data.personas.length > 0) {
            const select = document.getElementById('persona-type-select');
            select.innerHTML = '<option value="">타입을 선택하세요</option>';
            
            data.personas.forEach(persona => {
                const option = document.createElement('option');
                option.value = persona.id;
                option.textContent = `${persona.name} (${persona.id})`;
                select.appendChild(option);
            });
            
            console.log(`${data.personas.length}개의 페르소나 타입이 로드되었습니다.`);
        } else {
            console.warn('페르소나 목록이 비어있습니다.');
            showPersonaLoadError('페르소나 타입이 없습니다. Admin 페이지에서 페르소나를 생성해주세요.');
        }
    } catch (error) {
        console.error('페르소나 목록 로드 오류:', error);
        showPersonaLoadError('페르소나 목록을 불러오는데 실패했습니다.');
    }
}

// 페르소나 로드 오류 표시
function showPersonaLoadError(message = '페르소나 목록을 불러올 수 없습니다.') {
    const select = document.getElementById('persona-type-select');
    if (select) {
        select.innerHTML = `<option value="">${message}</option>`;
        select.disabled = true;
    }
}

// 페르소나 설명 업데이트
async function updatePersonaDescription(personaId) {
    if (!personaId) {
        const descEl = document.getElementById('persona-type-description');
        if (descEl) descEl.textContent = '';
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/admin/api/personas/${personaId}`);
        const data = await response.json();
        
        const descEl = document.getElementById('persona-type-description');
        if (descEl) {
            if (response.ok && data.description) {
                descEl.textContent = data.description;
            } else {
                descEl.textContent = '';
            }
        }
    } catch (error) {
        console.error('페르소나 정보 로드 오류:', error);
        const descEl = document.getElementById('persona-type-description');
        if (descEl) descEl.textContent = '';
    }
}

// 대화 시작 가능 여부 확인
function checkCanStartConversation() {
    const startBtn = document.getElementById('start-conversation-btn');
    if (startBtn) {
        if (selectedPersonaType && selectedCounselingLevel) {
            startBtn.disabled = false;
        } else {
            startBtn.disabled = true;
        }
    }
}

// 페르소나 선택 모달 표시
function showPersonaSelectionModal() {
    const modal = document.getElementById('persona-selection-modal');
    if (modal) {
        modal.classList.remove('hidden');
        
        // 선택 초기화
        selectedPersonaType = null;
        selectedCounselingLevel = null;
        const typeSelect = document.getElementById('persona-type-select');
        const levelSelect = document.getElementById('counseling-level-select');
        const descEl = document.getElementById('persona-type-description');
        const startBtn = document.getElementById('start-conversation-btn');
        
        if (typeSelect) typeSelect.value = '';
        if (levelSelect) levelSelect.value = '';
        if (descEl) descEl.textContent = '';
        if (startBtn) startBtn.disabled = true;
    }
}

// 페르소나 선택 모달 숨기기
function hidePersonaSelectionModal() {
    const modal = document.getElementById('persona-selection-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
}

// 페르소나 선택 후 새 대화 시작
async function startNewConversationWithPersona() {
    if (!selectedPersonaType || !selectedCounselingLevel) {
        alert('페르소나 타입과 상담 레벨을 선택해주세요.');
        return;
    }
    
    try {
        // 페르소나 정보 가져오기
        const personaResponse = await fetch(`${API_BASE_URL}/admin/api/personas/${selectedPersonaType}`);
        const personaData = await personaResponse.json();
        
        if (!personaResponse.ok) {
            throw new Error('페르소나 정보를 가져오는데 실패했습니다.');
        }
        
        // 대화 생성 (페르소나 정보 포함)
        const response = await fetch(`${API_BASE_URL}/api/conversations`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                user_id: 'web_user',
                persona: {
                    type: selectedPersonaType,
                    type_specific_keywords: personaData.type_specific_keywords || [],
                    common_keywords: personaData.common_keywords || [],
                    counseling_level: selectedCounselingLevel
                }
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
        
        // 페르소나 선택 모달 숨기기
        hidePersonaSelectionModal();
        
        // 세션 정보 업데이트 시작
        startSessionUpdates();
    } catch (error) {
        console.error('대화 생성 오류:', error);
        alert('대화를 시작하는데 실패했습니다. 다시 시도해주세요.');
    }
}

