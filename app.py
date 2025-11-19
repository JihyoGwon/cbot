"""Flask 메인 애플리케이션"""
from flask import Flask, request, jsonify, render_template
from flask_session import Session
from services.counselor_service import CounselorService
from services.firestore_service import FirestoreService
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

# 서비스 인스턴스 생성
counselor_service = CounselorService()
firestore_service = FirestoreService()


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
        
        conversation_id = firestore_service.create_conversation(user_id, initial_message)
        
        return jsonify({
            'conversation_id': conversation_id,
            'message': '대화가 생성되었습니다.'
        }), 201
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


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
        
        # 상담사 응답을 Firestore에 저장
        firestore_service.add_message(conversation_id, 'assistant', result['response'])
        
        # 응답에 메타데이터 포함
        response_data = {
            'conversation_id': conversation_id,
            'response': result['response'],
            'current_task': result.get('current_task'),
            'tasks_remaining': result.get('tasks_remaining', 0)
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
        session_service = SessionService()
        
        session = session_service.get_session(conversation_id)
        
        if not session:
            return jsonify({'error': '세션을 찾을 수 없습니다.'}), 404
        
        # datetime 객체를 문자열로 변환
        from datetime import datetime
        for key in ['created_at', 'updated_at']:
            if key in session and isinstance(session[key], datetime):
                session[key] = session[key].isoformat()
        
        return jsonify(session), 200
        
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

