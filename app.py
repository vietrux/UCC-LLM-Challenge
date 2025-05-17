from flask import Flask, render_template, request, jsonify, session, Response, stream_with_context
import uuid
import re
from openai import OpenAI
from typing import Dict, List, Tuple, Optional
import os
import json
import time

# Import the challenge data
from chall import CHALLENGES

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Constants
API_KEY = "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"
BASE_URL = "https://openrouter.ai/api/v1"
MODEL = "openai/gpt-4o-mini"

# Initialize OpenAI client
def get_llm_response(messages: List[Dict[str, str]], system_prompt: str) -> str:
    """Get response from LLM using conversation history"""
    try:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        
        # Prepend the system message to the conversation history
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        completion = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            temperature=0.7,
            max_tokens=1024
        )
        
        return completion.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"

def get_streaming_llm_response(messages: List[Dict[str, str]], system_prompt: str):
    """Get streaming response from LLM"""
    try:
        client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
        
        # Prepend the system message to the conversation history
        full_messages = [{"role": "system", "content": system_prompt}] + messages
        
        stream = client.chat.completions.create(
            model=MODEL,
            messages=full_messages,
            temperature=0.7,
            max_tokens=1024,
            stream=True
        )
        
        return stream
    except Exception as e:
        return f"Error: {str(e)}"

def check_success(response: str, secret_info: str) -> bool:
    """Check if response contains the secret information"""
    return secret_info.lower() in response.lower()

def validate_input(user_input: str) -> Tuple[bool, str]:
    """Validate user input for safety"""
    if len(user_input) > 512:
        return False, "Input too long (max 512 characters)."
    return True, ""

@app.route('/')
def index():
    """Render the main page with challenge selection"""
    # Initialize or reset session
    session['user_id'] = str(uuid.uuid4())
    session['completed_levels'] = []
    return render_template('index.html', challenges=CHALLENGES)

@app.route('/challenge/<int:level>', methods=['GET'])
def challenge(level):
    """Render the challenge page for a specific level"""
    # Find the challenge with matching level
    challenge = None
    for c in CHALLENGES:
        if c['level'] == level:
            challenge = c
            break
    
    if not challenge:
        return "Challenge not found", 404
        
    # Initialize conversation for this challenge if needed

    session_key = f"conversation_{level}"
    if session_key not in session:
        session[session_key] = []
    # Remove all previous conversation history for this challenge
    
    return render_template('challenge.html', challenge=challenge, 
                           completed_levels=session.get('completed_levels', []))

@app.route('/api/submit', methods=['POST'])
def submit():
    """API endpoint to handle user submission and get AI response"""
    data = request.json
    level = data.get('level')
    user_message = '/no-think ' + data.get('message')
    
    # Find the challenge
    challenge = None
    for c in CHALLENGES:
        if c['level'] == level:
            challenge = c
            break
    
    if not challenge:
        return jsonify({'error': 'Challenge not found'}), 404
        
    # Validate input
    valid, error_msg = validate_input(user_message)
    if not valid:
        return jsonify({'error': error_msg}), 400
        
    # Get conversation history for this challenge
    session_key = f"conversation_{level}"
    if session_key not in session:
        session[session_key] = []
    
    conversation = session[session_key]
    
    # Add user message to conversation
    conversation.append({"role": "user", "content": user_message})
    
    # Get response from AI
    response = get_llm_response(conversation, challenge["system_prompt"])
    
    # Add AI response to conversation
    conversation.append({"role": "assistant", "content": response})
    
    # Update session
    session[session_key] = conversation
    
    # Check if challenge is solved
    success = check_success(response, challenge["information_to_hide"])
    if success and level not in session.get('completed_levels', []):
        if 'completed_levels' not in session:
            session['completed_levels'] = []
        session['completed_levels'].append(level)
    
    return jsonify({
        'response': response,
        'success': success,
        'conversation_turns': len(conversation) // 2,
        'completed_levels': session.get('completed_levels', [])
    })

@app.route('/api/submit-stream', methods=['POST'])
def submit_stream():
    """API endpoint to handle user submission and get streaming AI response"""
    data = request.json
    level = data.get('level')
    user_message = '/no-think ' + data.get('message')
    
    # Find the challenge
    challenge = None
    for c in CHALLENGES:
        if c['level'] == level:
            challenge = c
            break
    
    if not challenge:
        return jsonify({'error': 'Challenge not found'}), 404
        
    # Validate input
    valid, error_msg = validate_input(user_message)
    if not valid:
        return jsonify({'error': error_msg}), 400
        
    # Get conversation history for this challenge
    session_key = f"conversation_{level}"
    if session_key not in session:
        session[session_key] = []
    
    conversation = session[session_key]
    
    # Add user message to conversation
    conversation.append({"role": "user", "content": user_message})
    
    # Update session - important to save immediately to keep track of conversation
    session[session_key] = conversation
    
    def generate():
        full_response = ""
        try:
            # Important: Add proper SSE headers
            yield "retry: 1000\n\n"
            
            stream = get_streaming_llm_response(conversation, challenge["system_prompt"])
            
            for chunk in stream:
                if hasattr(chunk.choices[0].delta, "content"):
                    content = chunk.choices[0].delta.content or ""
                    if content:
                        full_response += content
                        data_to_send = {
                            "content": content,
                            "done": False
                        }
                        yield f"data: {json.dumps(data_to_send)}\n\n"
                        # Don't sleep - it can cause buffering issues
            
            # After streaming is done, add to conversation history and check success
            conversation.append({"role": "assistant", "content": full_response})
            session[session_key] = conversation
            
            success = check_success(full_response, challenge["information_to_hide"])
            if success and level not in session.get('completed_levels', []):
                if 'completed_levels' not in session:
                    session['completed_levels'] = []
                session['completed_levels'].append(level)
            
            # Final data with completion status
            final_data = {
                "content": "",
                "done": True,
                "success": success,
                "conversation_turns": len(conversation) // 2,
                "completed_levels": session.get('completed_levels', [])
            }
            yield f"data: {json.dumps(final_data)}\n\n"
            
        except Exception as e:
            error_data = {
                "content": f"Error: {str(e)}",
                "error": True,
                "done": True
            }
            yield f"data: {json.dumps(error_data)}\n\n"
    
    # Set the correct headers for SSE
    response = Response(stream_with_context(generate()), 
                       mimetype="text/event-stream")
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'  # Important for nginx
    response.headers['Connection'] = 'keep-alive'
    return response

@app.route('/api/check-answer', methods=['POST'])
def check_answer():
    """API endpoint to check a user-submitted answer"""
    data = request.json
    level = data.get('level')
    answer = data.get('answer')
    
    # Find the challenge
    challenge = None
    for c in CHALLENGES:
        if c['level'] == level:
            challenge = c
            break
    
    if not challenge:
        return jsonify({'error': 'Challenge not found'}), 404
    
    # Check if the answer is correct
    success = check_success(answer, challenge["information_to_hide"])
    
    # If correct, add to completed levels
    if success and level not in session.get('completed_levels', []):
        if 'completed_levels' not in session:
            session['completed_levels'] = []
        session['completed_levels'].append(level)
    
    return jsonify({
        'success': success,
        'completed_levels': session.get('completed_levels', [])
    })

@app.route('/api/clear', methods=['POST'])
def clear():
    """Clear the conversation history for a challenge"""
    data = request.json
    level = data.get('level')
    
    session_key = f"conversation_{level}"
    session[session_key] = []
    
    return jsonify({'status': 'success', 'message': 'Conversation cleared'})

if __name__ == '__main__':
    app.run(debug=True, port=5007)
