"""Flask 메인 애플리케이션"""
import logging
from flask import Flask, request, jsonify, render_template
from flask_session import Session
from services.counselor_service import CounselorService
from services.firestore_service import FirestoreService
from services.persona_service import PersonaService
from config import Config

# Flask 앱 로깅 설정
logging.basicConfig(level=logging.INFO)
app_logger = logging.getLogger('werkzeug')
app_logger.setLevel(logging.INFO)

app = Flask(__name__)
app.config.from_object(Config)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# 서비스 인스턴스 생성
counselor_service = CounselorService()
firestore_service = FirestoreService()
persona_service = PersonaService()
from services.module_service import ModuleService
module_service = ModuleService()


@app.route('/')
def index():
    """메인 채팅 페이지"""
    return render_template('index.html')


@app.route('/health', methods=['GET'])
def health_check():
    """헬스 체크 엔드포인트"""
    return jsonify({'status': 'ok'}), 200


@app.route('/api/conversations', methods=['POST'])
def create_conversation():
    """새 대화 생성"""
    try:
        data = request.get_json()
        user_id = data.get('user_id', 'anonymous')
        initial_message = data.get('message', None)
        persona = data.get('persona', None)  # 페르소나 정보
        
        conversation_id = firestore_service.create_conversation(user_id, initial_message)
        
        # 세션 생성 및 페르소나 정보 저장
        from services.session_service import SessionService
        from services.task_planner_service import TaskPlannerService
        session_service = SessionService()
        task_planner = TaskPlannerService()
        
        session = session_service.create_session(conversation_id)
        
        # Part 1 초기 Task 생성
        initial_tasks = task_planner.create_initial_tasks("first_session")
        if initial_tasks:
            session_service.update_tasks(conversation_id, initial_tasks)
        
        # 페르소나 정보가 있으면 세션에 저장
        if persona:
            session_service.update_user_persona(conversation_id, persona)
        
        return jsonify({
            'conversation_id': conversation_id,
            'message': '대화가 생성되었습니다.'
        }), 201
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/conversations/<conversation_id>/chat', methods=['POST'])
def chat(conversation_id):
    """고도화된 상담 에이전트와 대화하기"""
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        
        if not user_message:
            return jsonify({'error': '메시지가 필요합니다.'}), 400
        
        # 사용자 메시지를 Firestore에 저장
        firestore_service.add_message(conversation_id, 'user', user_message)
        
        # 대화 기록 가져오기
        conversation_history = firestore_service.get_conversation_history(conversation_id)
        
        # 통합 상담 서비스 호출 (Task Planner, Selector, Supervisor 포함)
        result = counselor_service.chat(conversation_id, user_message, conversation_history)
        
        # 상담사 응답을 Firestore에 저장 (프롬프트 메타데이터 포함)
        prompt_metadata = {
            'prompt': result.get('prompt', ''),
            'current_task': result.get('current_task'),
            'current_part': result.get('current_part', 1),
            'current_module': result.get('current_module'),
            'task_selector_output': result.get('task_selector_output')  # Task Selector 출력 추가
        }
        
        # Supervision 결과가 있으면 메타데이터에 포함
        if result.get('supervision'):
            prompt_metadata['supervision'] = {
                'score': result['supervision'].get('score', 0),
                'feedback': result['supervision'].get('feedback', ''),
                'improvements': result['supervision'].get('improvements', ''),
                'strengths': result['supervision'].get('strengths', ''),
                'needs_improvement': result['supervision'].get('needs_improvement', False)
            }
        
        firestore_service.add_message(
            conversation_id, 
            'assistant', 
            result['response'],
            metadata=prompt_metadata
        )
        
        # 응답에 메타데이터 포함
        response_data = {
            'conversation_id': conversation_id,
            'response': result['response'],
            'current_task': result.get('current_task'),
            'current_part': result.get('current_part', 1),
            'current_module': result.get('current_module')
        }
        
        # Supervision 결과가 있으면 포함 (디버깅용)
        if result.get('supervision'):
            response_data['supervision'] = {
                'score': result['supervision']['score'],
                'needs_improvement': result['supervision']['needs_improvement']
            }
        
        return jsonify(response_data), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/conversations/<conversation_id>', methods=['GET'])
def get_conversation(conversation_id):
    """대화 가져오기"""
    try:
        conversation = firestore_service.get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({'error': '대화를 찾을 수 없습니다.'}), 404
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        if 'created_at' in conversation and isinstance(conversation['created_at'], datetime):
            conversation['created_at'] = conversation['created_at'].isoformat()
        if 'updated_at' in conversation and isinstance(conversation['updated_at'], datetime):
            conversation['updated_at'] = conversation['updated_at'].isoformat()
        # messages 내부의 timestamp도 변환
        if 'messages' in conversation:
            for msg in conversation['messages']:
                if 'timestamp' in msg and isinstance(msg['timestamp'], datetime):
                    msg['timestamp'] = msg['timestamp'].isoformat()
        
        return jsonify(conversation), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sessions/<conversation_id>', methods=['GET'])
def get_session(conversation_id):
    """상담 세션 정보 가져오기"""
    try:
        from services.session_service import SessionService
        from services.module_service import ModuleService
        
        session_service = SessionService()
        module_service = ModuleService()
        
        session = session_service.get_session(conversation_id)
        
        if not session:
            return jsonify({'error': '세션을 찾을 수 없습니다.'}), 404
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for key in ['created_at', 'updated_at']:
            if key in session and isinstance(session[key], datetime):
                session[key] = session[key].isoformat()
        
        # Task에 module 정보 추가
        tasks = session.get('tasks', [])
        for task in tasks:
            module_id = task.get('module_id')
            if module_id:
                module = module_service.get_module(module_id)
                if module:
                    task['module'] = {
                        'id': module.get('id'),
                        'name': module.get('name'),
                        'description': module.get('description')
                    }
        
        return jsonify(session), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/conversations/<conversation_id>/messages/<int:message_index>/prompt', methods=['GET'])
def get_message_prompt(conversation_id, message_index):
    """특정 메시지의 프롬프트 가져오기"""
    try:
        conversation = firestore_service.get_conversation(conversation_id)
        
        if not conversation:
            return jsonify({'error': '대화를 찾을 수 없습니다.'}), 404
        
        messages = conversation.get('messages', [])
        
        if message_index < 0 or message_index >= len(messages):
            return jsonify({'error': '메시지를 찾을 수 없습니다.'}), 404
        
        message = messages[message_index]
        
        # assistant 메시지이고 metadata가 있는 경우만 프롬프트 반환
        if message.get('role') == 'assistant' and message.get('metadata'):
            metadata = message.get('metadata', {})
            prompt = metadata.get('prompt', '')
            supervision = metadata.get('supervision')
            
            response_data = {
                'prompt': prompt,
                'current_task': metadata.get('current_task'),
                'current_part': metadata.get('current_part', 1),
                'current_module': metadata.get('current_module'),
                'task_selector_output': metadata.get('task_selector_output')  # Task Selector 출력 추가
            }
            
            # Supervision 정보가 있으면 포함
            if supervision:
                response_data['supervision'] = supervision
            
            return jsonify(response_data), 200
        else:
            return jsonify({'error': '이 메시지에는 프롬프트 정보가 없습니다.'}), 404
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/api/conversations', methods=['GET'])
def list_conversations():
    """사용자의 대화 목록 가져오기"""
    try:
        user_id = request.args.get('user_id', 'anonymous')
        limit = int(request.args.get('limit', 10))
        
        conversations = firestore_service.list_conversations(user_id, limit)
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for conv in conversations:
            if 'created_at' in conv and isinstance(conv['created_at'], datetime):
                conv['created_at'] = conv['created_at'].isoformat()
            if 'updated_at' in conv and isinstance(conv['updated_at'], datetime):
                conv['updated_at'] = conv['updated_at'].isoformat()
            # messages 내부의 timestamp도 변환
            if 'messages' in conv:
                for msg in conv['messages']:
                    if 'timestamp' in msg and isinstance(msg['timestamp'], datetime):
                        msg['timestamp'] = msg['timestamp'].isoformat()
        
        return jsonify({
            'conversations': conversations,
            'count': len(conversations)
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ==================== Admin API ====================

@app.route('/admin', methods=['GET'])
def admin_page():
    """페르소나 관리 Admin 페이지"""
    return render_template('admin.html')


@app.route('/admin/api/personas', methods=['GET'])
def list_personas():
    """모든 페르소나 타입 목록 가져오기"""
    try:
        personas = persona_service.list_personas()
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for persona in personas:
            for key in ['created_at', 'updated_at']:
                if key in persona and isinstance(persona[key], datetime):
                    persona[key] = persona[key].isoformat()
        
        return jsonify({
            'personas': personas,
            'count': len(personas)
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas', methods=['POST'])
def create_persona():
    """새 페르소나 타입 생성"""
    try:
        data = request.get_json()
        
        if not data.get('id'):
            return jsonify({'error': '페르소나 ID가 필요합니다.'}), 400
        
        persona = persona_service.create_persona(data)
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for key in ['created_at', 'updated_at']:
            if key in persona and isinstance(persona[key], datetime):
                persona[key] = persona[key].isoformat()
        
        return jsonify({
            'message': '페르소나가 생성되었습니다.',
            'persona': persona
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas/<persona_id>', methods=['GET'])
def get_persona(persona_id):
    """페르소나 타입 가져오기"""
    try:
        persona = persona_service.get_persona(persona_id)
        
        if not persona:
            return jsonify({'error': '페르소나를 찾을 수 없습니다.'}), 404
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for key in ['created_at', 'updated_at']:
            if key in persona and isinstance(persona[key], datetime):
                persona[key] = persona[key].isoformat()
        
        return jsonify(persona), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas/<persona_id>', methods=['PUT'])
def update_persona(persona_id):
    """페르소나 타입 수정"""
    try:
        data = request.get_json()
        
        persona = persona_service.update_persona(persona_id, data)
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for key in ['created_at', 'updated_at']:
            if key in persona and isinstance(persona[key], datetime):
                persona[key] = persona[key].isoformat()
        
        return jsonify({
            'message': '페르소나가 수정되었습니다.',
            'persona': persona
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas/<persona_id>', methods=['DELETE'])
def delete_persona(persona_id):
    """페르소나 타입 삭제"""
    try:
        persona_service.delete_persona(persona_id)
        
        return jsonify({
            'message': '페르소나가 삭제되었습니다.'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas/common-keywords', methods=['GET'])
def get_common_keywords():
    """공통 키워드 가져오기"""
    try:
        keywords = persona_service.get_common_keywords()
        return jsonify({'keywords': keywords}), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas/common-keywords', methods=['PUT'])
def update_common_keywords():
    """공통 키워드 업데이트"""
    try:
        data = request.get_json()
        keywords = data.get('keywords', [])
        
        if len(keywords) != 4:
            return jsonify({'error': '공통 키워드는 정확히 4개여야 합니다.'}), 400
        
        updated_keywords = persona_service.update_common_keywords(keywords)
        
        return jsonify({
            'message': '공통 키워드가 업데이트되었습니다.',
            'keywords': updated_keywords
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/personas/initialize', methods=['POST'])
def initialize_personas():
    """기본 페르소나 타입 초기화 (16개)"""
    try:
        result = persona_service.initialize_default_personas()
        
        return jsonify({
            'message': f'{result["created"]}개의 페르소나가 생성되었습니다.',
            'result': result
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/counseling-levels', methods=['GET'])
def get_counseling_levels():
    """상담 레벨 목록 가져오기"""
    try:
        levels = persona_service.get_counseling_levels()
        
        return jsonify({
            'levels': levels,
            'count': len(levels)
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/counseling-levels', methods=['PUT'])
def update_counseling_levels():
    """상담 레벨 업데이트"""
    try:
        data = request.get_json()
        levels = data.get('levels', [])
        
        if len(levels) != 5:
            return jsonify({'error': '상담 레벨은 정확히 5개여야 합니다.'}), 400
        
        updated_levels = persona_service.update_counseling_levels(levels)
        
        return jsonify({
            'message': '상담 레벨이 업데이트되었습니다.',
            'levels': updated_levels
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


# ==================== Module API ====================

@app.route('/admin/api/modules', methods=['GET'])
def list_modules():
    """모든 Module 목록 가져오기"""
    try:
        modules = module_service.get_all_modules()
        return jsonify({
            'modules': modules,
            'count': len(modules)
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/modules', methods=['POST'])
def create_module():
    """새 Module 생성"""
    try:
        data = request.get_json()
        
        if not data.get('id'):
            return jsonify({'error': 'Module ID가 필요합니다.'}), 400
        
        module = module_service.create_module(data)
        
        return jsonify({
            'message': 'Module이 생성되었습니다.',
            'module': module
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/modules/<module_id>', methods=['GET'])
def get_module(module_id):
    """Module 가져오기"""
    try:
        module = module_service.get_module(module_id)
        
        if not module:
            return jsonify({'error': 'Module을 찾을 수 없습니다.'}), 404
        
        return jsonify(module), 200
        
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/modules/<module_id>', methods=['PUT'])
def update_module(module_id):
    """Module 수정"""
    try:
        data = request.get_json()
        
        module = module_service.update_module(module_id, data)
        
        return jsonify({
            'message': 'Module이 수정되었습니다.',
            'module': module
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


@app.route('/admin/api/modules/<module_id>', methods=['DELETE'])
def delete_module(module_id):
    """Module 삭제"""
    try:
        module_service.delete_module(module_id)
        
        return jsonify({
            'message': 'Module이 삭제되었습니다.'
        }), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()}), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

