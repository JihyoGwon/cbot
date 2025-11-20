// Admin 페이지 JavaScript

let editingPersonaId = null;

// 페이지 로드 시 초기화
document.addEventListener('DOMContentLoaded', () => {
    loadPersonas();
    loadCommonKeywords();
    
    // 이벤트 리스너 등록
    document.getElementById('add-persona-btn').addEventListener('click', () => {
        openPersonaModal();
    });
    
    document.getElementById('init-default-btn').addEventListener('click', () => {
        initializeDefaultPersonas();
    });
    
    document.getElementById('save-common-keywords-btn').addEventListener('click', () => {
        saveCommonKeywords();
    });
    
    document.getElementById('close-modal-btn').addEventListener('click', () => {
        closePersonaModal();
    });
    
    document.getElementById('cancel-btn').addEventListener('click', () => {
        closePersonaModal();
    });
    
    document.getElementById('persona-form').addEventListener('submit', (e) => {
        e.preventDefault();
        savePersona();
    });
    
    // 모달 외부 클릭 시 닫기
    document.getElementById('persona-modal').addEventListener('click', (e) => {
        if (e.target.id === 'persona-modal') {
            closePersonaModal();
        }
    });
});

// 페르소나 목록 로드
async function loadPersonas() {
    try {
        const response = await fetch('/admin/api/personas');
        const data = await response.json();
        
        if (response.ok) {
            // data.personas가 배열인지 확인
            if (data.personas && Array.isArray(data.personas)) {
                renderPersonas(data.personas);
            } else {
                console.error('Invalid personas data:', data);
                showError('페르소나 데이터 형식이 올바르지 않습니다.');
                document.getElementById('personas-list').innerHTML = '<div class="loading">데이터 형식 오류</div>';
            }
        } else {
            showError('페르소나 목록을 불러오는데 실패했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Error loading personas:', error);
        showError('페르소나 목록을 불러오는데 실패했습니다: ' + error.message);
    }
}

// 페르소나 목록 렌더링
function renderPersonas(personas) {
    const container = document.getElementById('personas-list');
    
    // personas가 배열이 아닌 경우 처리
    if (!Array.isArray(personas)) {
        container.innerHTML = '<div class="loading">페르소나 데이터 형식이 올바르지 않습니다.</div>';
        return;
    }
    
    if (personas.length === 0) {
        container.innerHTML = '<div class="loading">페르소나가 없습니다. 기본 페르소나를 초기화하거나 새로 추가하세요.</div>';
        return;
    }
    
    container.innerHTML = personas.map(persona => `
        <div class="persona-card">
            <div class="persona-card-header">
                <div>
                    <div class="persona-card-title">${escapeHtml(persona.name)}</div>
                    <div class="persona-card-id">${escapeHtml(persona.id)}</div>
                </div>
            </div>
            ${persona.description ? `<div class="persona-card-description">${escapeHtml(persona.description)}</div>` : ''}
            <div class="persona-card-keywords">
                <h4>타입별 특화 키워드</h4>
                <div class="keywords-list">
                    ${persona.type_specific_keywords.map(kw => `<span class="keyword-tag">${escapeHtml(kw)}</span>`).join('')}
                </div>
            </div>
            <div class="persona-card-keywords">
                <h4>공통 키워드</h4>
                <div class="keywords-list">
                    ${persona.common_keywords.map(kw => `<span class="keyword-tag common">${escapeHtml(kw)}</span>`).join('')}
                </div>
            </div>
            <div class="persona-card-actions">
                <button class="btn btn-secondary btn-small" onclick="editPersona('${persona.id}')">수정</button>
                <button class="btn btn-danger btn-small" onclick="deletePersona('${persona.id}')">삭제</button>
            </div>
        </div>
    `).join('');
}

// 공통 키워드 로드
async function loadCommonKeywords() {
    try {
        const response = await fetch('/admin/api/personas/common-keywords');
        const data = await response.json();
        
        if (response.ok) {
            const keywords = data.keywords;
            document.getElementById('common-keyword-1').value = keywords[0] || '';
            document.getElementById('common-keyword-2').value = keywords[1] || '';
            document.getElementById('common-keyword-3').value = keywords[2] || '';
            document.getElementById('common-keyword-4').value = keywords[3] || '';
        }
    } catch (error) {
        console.error('공통 키워드를 불러오는데 실패했습니다:', error);
    }
}

// 공통 키워드 저장
async function saveCommonKeywords() {
    const keywords = [
        document.getElementById('common-keyword-1').value.trim(),
        document.getElementById('common-keyword-2').value.trim(),
        document.getElementById('common-keyword-3').value.trim(),
        document.getElementById('common-keyword-4').value.trim()
    ];
    
    if (keywords.some(kw => !kw)) {
        showError('모든 공통 키워드를 입력해주세요.');
        return;
    }
    
    try {
        const response = await fetch('/admin/api/personas/common-keywords', {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ keywords })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('공통 키워드가 저장되었습니다.');
            loadPersonas(); // 목록 새로고침
        } else {
            showError('공통 키워드 저장에 실패했습니다: ' + data.error);
        }
    } catch (error) {
        showError('공통 키워드 저장에 실패했습니다: ' + error.message);
    }
}

// 기본 페르소나 초기화
async function initializeDefaultPersonas() {
    if (!confirm('기본 페르소나 16개를 초기화하시겠습니까? 기존 페르소나와 중복되지 않는 것만 생성됩니다.')) {
        return;
    }
    
    try {
        const response = await fetch('/admin/api/personas/initialize', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(`${data.result.created}개의 페르소나가 생성되었습니다.`);
            loadPersonas();
            loadCommonKeywords();
        } else {
            showError('페르소나 초기화에 실패했습니다: ' + data.error);
        }
    } catch (error) {
        showError('페르소나 초기화에 실패했습니다: ' + error.message);
    }
}

// 페르소나 모달 열기
function openPersonaModal(personaId = null) {
    editingPersonaId = personaId;
    const modal = document.getElementById('persona-modal');
    const form = document.getElementById('persona-form');
    const title = document.getElementById('modal-title');
    
    if (personaId) {
        title.textContent = '페르소나 수정';
        loadPersonaForEdit(personaId);
    } else {
        title.textContent = '새 페르소나 추가';
        form.reset();
        document.getElementById('persona-id').disabled = false;
    }
    
    modal.classList.add('show');
}

// 페르소나 모달 닫기
function closePersonaModal() {
    const modal = document.getElementById('persona-modal');
    modal.classList.remove('show');
    editingPersonaId = null;
    document.getElementById('persona-form').reset();
}

// 페르소나 수정을 위해 로드
async function loadPersonaForEdit(personaId) {
    try {
        const response = await fetch(`/admin/api/personas/${personaId}`);
        const persona = await response.json();
        
        if (response.ok) {
            document.getElementById('persona-id').value = persona.id;
            document.getElementById('persona-id').disabled = true;
            document.getElementById('persona-name').value = persona.name || '';
            document.getElementById('persona-description').value = persona.description || '';
            document.getElementById('keyword-1').value = persona.type_specific_keywords[0] || '';
            document.getElementById('keyword-2').value = persona.type_specific_keywords[1] || '';
            document.getElementById('keyword-3').value = persona.type_specific_keywords[2] || '';
            document.getElementById('keyword-4').value = persona.type_specific_keywords[3] || '';
        } else {
            showError('페르소나를 불러오는데 실패했습니다: ' + persona.error);
        }
    } catch (error) {
        showError('페르소나를 불러오는데 실패했습니다: ' + error.message);
    }
}

// 페르소나 저장
async function savePersona() {
    const formData = {
        id: document.getElementById('persona-id').value.trim(),
        name: document.getElementById('persona-name').value.trim(),
        description: document.getElementById('persona-description').value.trim(),
        type_specific_keywords: [
            document.getElementById('keyword-1').value.trim(),
            document.getElementById('keyword-2').value.trim(),
            document.getElementById('keyword-3').value.trim(),
            document.getElementById('keyword-4').value.trim()
        ]
    };
    
    // 유효성 검사
    if (!formData.id || !formData.name) {
        showError('페르소나 ID와 이름은 필수입니다.');
        return;
    }
    
    if (formData.type_specific_keywords.some(kw => !kw)) {
        showError('모든 타입별 특화 키워드를 입력해주세요.');
        return;
    }
    
    try {
        const url = editingPersonaId 
            ? `/admin/api/personas/${editingPersonaId}`
            : '/admin/api/personas';
        
        const method = editingPersonaId ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(formData)
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess(editingPersonaId ? '페르소나가 수정되었습니다.' : '페르소나가 생성되었습니다.');
            closePersonaModal();
            loadPersonas();
        } else {
            showError('페르소나 저장에 실패했습니다: ' + data.error);
        }
    } catch (error) {
        showError('페르소나 저장에 실패했습니다: ' + error.message);
    }
}

// 페르소나 수정
function editPersona(personaId) {
    openPersonaModal(personaId);
}

// 페르소나 삭제
async function deletePersona(personaId) {
    if (!confirm('이 페르소나를 삭제하시겠습니까?')) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/api/personas/${personaId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showSuccess('페르소나가 삭제되었습니다.');
            loadPersonas();
        } else {
            showError('페르소나 삭제에 실패했습니다: ' + data.error);
        }
    } catch (error) {
        showError('페르소나 삭제에 실패했습니다: ' + error.message);
    }
}

// 에러 메시지 표시
function showError(message) {
    const container = document.querySelector('.admin-content');
    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.textContent = message;
    container.insertBefore(errorDiv, container.firstChild);
    
    setTimeout(() => {
        errorDiv.remove();
    }, 5000);
}

// 성공 메시지 표시
function showSuccess(message) {
    const container = document.querySelector('.admin-content');
    const successDiv = document.createElement('div');
    successDiv.className = 'success-message';
    successDiv.textContent = message;
    container.insertBefore(successDiv, container.firstChild);
    
    setTimeout(() => {
        successDiv.remove();
    }, 3000);
}

// HTML 이스케이프
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

