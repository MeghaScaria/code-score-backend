from flask import Flask, request, jsonify, render_template
import requests
import os
from dotenv import load_dotenv
import re

load_dotenv()
app = Flask(__name__)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/score', methods=['POST'])
def score_code():
    # Get input with validation
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No JSON data provided'}), 400
        
    code = data.get('code', '').strip()
    language = data.get('language', '').strip()

    if not code or not language:
        return jsonify({'error': 'Both code and language are required'}), 400

    # Strictly formatted prompt
    prompt = f"""
    **Code Evaluation Request**
    Language: {language}
    
    Evaluate this code based on:
    1. Syntax (0-30): Proper structure and formatting
    2. Logic (0-30): Correctness and edge case handling
    3. Methods (0-20): Efficient use of functions/libraries
    4. Objective (0-20): Fulfills stated purpose
    
    Code:
    ```{language}
    {code}
    ```
    
    **Required Response Format:**
    
    SCORES:
    - Syntax: [score]/30
    - Logic: [score]/30
    - Methods: [score]/20
    - Objective: [score]/20
    - TOTAL: [total]/100
    
    SUMMARY:
    [Brief description of code's purpose]
    
    SUGGESTIONS:
    • [Suggestion 1]
    • [Suggestion 2]
    • [Suggestion 3]
    
    IMPROVED CODE:
    ```{language}
    [Only if improvements exist]
    ```
    """

    # API Configuration
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'Missing Gemini API key'}), 500

    try:
        # Using latest Gemini 1.5 Flash model
        response = requests.post(
            f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}',
            json={
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": 0.2,  # More deterministic scoring
                    "response_mime_type": "text/plain"
                }
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        full_text = result['candidates'][0]['content']['parts'][0]['text']
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'API request failed: {str(e)}'}), 500
    except (KeyError, IndexError):
        return jsonify({'error': 'Invalid API response format'}), 500

    # Robust parsing with fallbacks
    def extract_score(category):
        # Multiple patterns to catch different formats
        patterns = [
            rf"{category}:\s*(\d+)/\d+",
            rf"{category}\s*\((\d+)/\d+\)",
            rf"{category}.*?(\d+)\s*out of \d+"
        ]
        for pattern in patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match:
                return int(match.group(1))
        return 0  # Default to 0 if missing

    scores = {
        "syntax": extract_score("Syntax"),
        "logic": extract_score("Logic"),
        "methods": extract_score("Methods"),
        "objective": extract_score("Objective")
    }
    scores["total"] = sum(scores.values())

    # Extract summary
    summary_match = re.search(
        r"SUMMARY:\s*(.*?)(?:\n\s*\n|SUGGESTIONS|$)", 
        full_text, 
        re.DOTALL | re.IGNORECASE
    )
    summary = summary_match.group(1).strip() if summary_match else "No summary provided"

    # Extract suggestions (multiple formats)
    suggestions = []
    suggestions_section = re.search(
        r"SUGGESTIONS:(.*?)(?:IMPROVED CODE|$)", 
        full_text, 
        re.DOTALL | re.IGNORECASE
    )
    if suggestions_section:
        suggestions = [
            s.strip() 
            for s in re.split(r'\n\s*[\-•*]', suggestions_section.group(1)) 
            if s.strip()
        ]
    
    if not suggestions:
        suggestions = ["No specific suggestions provided"]

    # Extract improved code
    improved_code = ""
    code_match = re.search(
        rf"```(?:{language})?\n(.*?)```", 
        full_text, 
        re.DOTALL
    )
    if code_match:
        improved_code = code_match.group(1).strip()
        if improved_code == code.strip():
            improved_code = "No significant improvements suggested"

    return jsonify({
        "total_score": scores["total"],
        "breakdown": {
            "syntax": scores["syntax"],
            "logic": scores["logic"],
            "methods": scores["methods"],
            "objective": scores["objective"]
        },
        "summary": summary,
        "suggestions": suggestions[:5],  # Limit to 5 suggestions
        "improved_code": improved_code
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)