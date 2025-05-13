from flask import Flask, request, jsonify, render_template
import requests
import os
from dotenv import load_dotenv
import re

load_dotenv()
app = Flask(__name__)

def build_prompt(code, language):
    return f"""
    **Code Evaluation - Strict Format Required**

    Evaluate this {language} code:
    ```{language}
    {code}
    ```

    RESPONSE MUST CONTAIN:

    1. SCORES (ALL REQUIRED):
    - Syntax: [0-30]/30 (structure/formatting)
    - Logic: [0-30]/30 (correctness/edge cases)
    - Methods: [0-20]/20 (function design/efficiency)
    - Objective: [0-20]/20 (problem solved)
    - TOTAL: [sum]/100

    2. SUMMARY:
    [1-2 sentence description]

    3. EXACTLY 3 SUGGESTIONS:
    • [Specific improvement 1]
    • [Specific improvement 2]
    • [Specific improvement 3]

    4. IMPROVED CODE (REQUIRED):
    ```{language}
    [MUST provide optimized version]
    ```

    Rules:
    - If code is perfect, return original in code block
    - Never omit improved code section
    - Deduct points for each flaw
    """

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/score', methods=['POST'])
def score_code():
    try:
        data = request.get_json()
        code = data.get('code', '').strip()
        language = data.get('language', 'Python').strip()

        if not code or not language:
            return jsonify({'error': 'Both code and language are required'}), 400

        # Get API response
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'error': 'API key not configured'}), 500

        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}',
            json={
                "contents": [{"parts": [{"text": build_prompt(code, language)}]}],
                "generationConfig": {
                    "temperature": 0.1,
                    "response_mime_type": "text/plain"
                }
            },
            timeout=30
        )
        response.raise_for_status()
        full_text = response.json()['candidates'][0]['content']['parts'][0]['text']

        # Parse scores with fallbacks
        def extract_score(category):
            match = re.search(rf"{category}:\s*(\d+)/\d+", full_text, re.IGNORECASE)
            return int(match.group(1)) if match else 0

        scores = {
            "syntax": extract_score("Syntax"),
            "logic": extract_score("Logic"),
            "methods": extract_score("Methods"),
            "objective": extract_score("Objective")
        }
        scores["total"] = sum(scores.values())

        # Extract other sections
        summary = re.search(r"SUMMARY:\s*(.*?)(?:\n|$)", full_text, re.IGNORECASE)
        summary = summary.group(1).strip() if summary else "Code evaluation completed"

        suggestions = re.findall(r"•\s*(.*?)(?=\n•|\n```|$)", full_text) or [
            "Add type checking",
            "Include error handling",
            "Add documentation"
        ]

        # Improved code extraction (more robust)
        code_blocks = re.findall(r'```(?:[a-z]*\n)?(.*?)```', full_text, re.DOTALL)
        if len(code_blocks) > 1:  # First is original, second is improved
            improved_code = code_blocks[1].strip()
        elif code_blocks:  # If only one, use it
            improved_code = code_blocks[0].strip()
        else:
            improved_code = code  # Fallback to original

        return jsonify({
            "total_score": scores["total"],
            "breakdown": scores,
            "summary": summary,
            "suggestions": suggestions[:3],
            "improved_code": improved_code
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)