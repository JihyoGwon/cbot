// 전역 변수
let conversationId = null;
const API_BASE_URL = '';

// DOM 요소
const chatMessages = document.getElementById('chat-messages');
const messageInput = document.getElementById('message-input');
const sendBtn = document.getElementById('send-btn');
const newConversationBtn = document.getElementById('new-conversation-btn');
const conversationIdDisplay = document.getElementById('conversation-id-display');

// 초기화
document.addEventListener('DOMContentLoaded', () => {
    // 새 대화 시작
    newConversationBtn.addEventListener('click', startNewConversation);
    
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
        
        // AI 응답 표시
        addMessage('assistant', data.response);
        
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
function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = content;
    
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

