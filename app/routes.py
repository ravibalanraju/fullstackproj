from flask import Blueprint, request, jsonify
from app.services import get_prompt_template, call_chatgpt, save_to_history, process_bulk, render_prompt

api_bp = Blueprint('api', __name__)
TEMPLATE_ID = "Education_Prompt"
MAX_BULK_SIZE = 50

@api_bp.route('/ask', methods=['POST'])
def single_request():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("userInput"), str) or not data["userInput"].strip():
        return jsonify({"error": "Request body must be JSON with a non-empty 'userInput' string"}), 400
    user_input = data["userInput"]
    template = get_prompt_template(TEMPLATE_ID)
    if not template:
        return jsonify({"error": "Prompt template not found"}), 404
    try:
        response_text = call_chatgpt(user_input, template)
    except Exception as exc:
        return jsonify({"error": f"AI request failed: {exc}"}), 502
    save_to_history(user_input, render_prompt(user_input, template), response_text)
    return jsonify({"response": response_text})

@api_bp.route('/ask/bulk', methods=['POST'])
async def batch_request():
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or not isinstance(data.get("userInput"), list) or not data["userInput"]:
        return jsonify({"error": "Request body must be JSON with a non-empty 'userInput' list of strings"}), 400
    user_inputs = data["userInput"]
    if not all(isinstance(item, str) and item.strip() for item in user_inputs):
        return jsonify({"error": "Every item in 'userInput' must be a non-empty string"}), 400
    if len(user_inputs) > MAX_BULK_SIZE:
        return jsonify({"error": f"Bulk requests are limited to {MAX_BULK_SIZE} inputs"}), 400
    template = get_prompt_template(TEMPLATE_ID)
    if not template:
        return jsonify({"error": "Prompt template not found"}), 404
    results = await process_bulk(user_inputs, template)
    responses = [
        {"error": f"AI request failed: {r}"} if isinstance(r, Exception) else r
        for r in results
    ]
    return jsonify({"responses": responses})
