"""
Response cleaning utilities for LLM outputs
"""
import re


def clean_llm_response(response: str) -> str:
    """Clean and normalize LLM response content"""
    if not response:
        return ""
    
    # Remove thinking tags (various formats)
    response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE)
    response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL | re.IGNORECASE)
    response = re.sub(r'\*\*Thinking\*\*:.*?(?=\n\n|\n[A-Z]|$)', '', response, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove common LLM artifacts
    response = re.sub(r'```thinking.*?```', '', response, flags=re.DOTALL | re.IGNORECASE)
    response = re.sub(r'Internal thoughts:.*?(?=\n\n|\n[A-Z]|$)', '', response, flags=re.DOTALL | re.IGNORECASE)
    response = re.sub(r'\[thinking\].*?\[/thinking\]', '', response, flags=re.DOTALL | re.IGNORECASE)
    
    # Remove excessive whitespace
    response = re.sub(r'\n\s*\n\s*\n+', '\n\n', response)  # Multiple blank lines
    response = re.sub(r'[ \t]+$', '', response, flags=re.MULTILINE)  # Trailing spaces
    
    # Strip leading/trailing whitespace
    response = response.strip()
    
    return response


def clean_json_response(response: str) -> str:
    """Clean LLM response specifically for JSON parsing"""
    cleaned = clean_llm_response(response)
    
    # Remove any text before the first {
    if '{' in cleaned:
        first_brace = cleaned.find('{')
        cleaned = cleaned[first_brace:]
    
    # Remove any text after the last }
    if '}' in cleaned:
        last_brace = cleaned.rfind('}')
        cleaned = cleaned[:last_brace + 1]
    
    return cleaned


def extract_content_from_markdown(response: str) -> str:
    """Extract content from markdown code blocks if present"""
    cleaned = clean_llm_response(response)
    
    # Check for markdown code blocks
    code_block_pattern = r'```(?:\w+)?\s*(.*?)\s*```'
    matches = re.findall(code_block_pattern, cleaned, re.DOTALL)
    
    if matches:
        # Return the content of the first code block
        return matches[0].strip()
    
    return cleaned


def sanitize_for_display(response: str) -> str:
    """Sanitize response for clean display output"""
    cleaned = clean_llm_response(response)
    
    # Remove common prefixes that add no value
    prefixes_to_remove = [
        "Based on my analysis:",
        "Here's what I found:",
        "According to the information:",
        "The answer is:",
        "Here is the result:",
        "Let me provide:",
    ]
    
    for prefix in prefixes_to_remove:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix):].strip()
    
    return cleaned