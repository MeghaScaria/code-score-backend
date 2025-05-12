from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

@app.route('/score', methods=['POST'])
def score_code():
    data = request.get_json()
    code = data.get('code')
    language = data.get('language')

    if not code or not language:
        return jsonify({'error': 'Both code and language are required.'}), 400

    # Construct the prompt for Gemini API
    prompt = f'''
Evaluate the following {language} code based on these criteria:
- Syntax (30 points)
- Logic (30 points)
- Methods Used (20 points)
- Objective Fulfillment (20 points)

Provide a score out of 100, a breakdown of the scores, suggestions for improvement, and a brief summary of the code's purpose.

Code:
```{language}
{code}
'''

    # Send the prompt to Gemini API
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return jsonify({'error': 'Gemini API key not found.'}), 500

    headers = {
        'Content-Type': 'application/json'
    }

    payload = {
        'contents': [
            {
                'parts': [
                    {'text': prompt}
                ]
            }
        ]
    }

    url = f'https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}'

    # Send the request to Gemini API
    response = requests.post(
        url,
        headers=headers,
        json=payload
    )

    if response.status_code != 200:
        return jsonify({'error': 'Failed to get response from Gemini API.'}), 500

        result = response.json()
    full_text = result['candidates'][0]['content']['parts'][0]['text']

    import re

    # Extract individual scores using regex
    def extract_score(label, text):
        match = re.search(fr'\*\*{label} \((\d+)/30\)\*\*' if label in ['Syntax', 'Logic']
                          else fr'\*\*{label} \((\d+)/20\)\*\*', text)
        return int(match.group(1)) if match else None

    syntax = extract_score('Syntax', full_text)
    logic = extract_score('Logic', full_text)
    methods = extract_score('Methods Used', full_text)
    objective = extract_score('Objective Fulfillment', full_text)

    # Extract total score
    total_score_match = re.search(r'\*\*Total Score: (\d+)/100\*\*', full_text)
    total_score = int(total_score_match.group(1)) if total_score_match else None

    # Extract suggestions
    suggestions_match = re.search(r'\*\*Suggestions for Improvement:\*\*\n\n((?:\* .+\n?)+)', full_text)
    suggestions = [s.strip("* ").strip() for s in suggestions_match.group(1).splitlines()] if suggestions_match else []

    # Extract summary
    summary_match = re.search(r'\*\*Summary:\*\*\n\n(.+)', full_text, re.DOTALL)
    summary = summary_match.group(1).strip() if summary_match else ""

    # Extract improved code
    code_match = re.search(r'```python\n(.+?)\n```', full_text, re.DOTALL)
    improved_code = code_match.group(1).strip() if code_match else ""

    return jsonify({
        "total_score": total_score,
        "breakdown": {
            "syntax": syntax,
            "logic": logic,
            "methods_used": methods,
            "objective_fulfillment": objective
        },
        "suggestions": suggestions,
        "summary": summary,
        "improved_code": improved_code,
        "raw_text": full_text
    })


if __name__ == '__main__':
    app.run(debug=True)
