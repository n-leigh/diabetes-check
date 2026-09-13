import os
import pytest
from app import app

def test_compiled_css_exists():
    css_path = os.path.join('static', 'css', 'tailwind.min.css')
    assert os.path.exists(css_path), f"{css_path} not found. Did you run 'npm run build:css'?"

def test_csp_headers():
    client = app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    csp = response.headers.get('Content-Security-Policy')
    assert csp is not None, "CSP header missing"
    assert "script-src 'self'" in csp
    assert "style-src 'self'" in csp
    assert "font-src 'self'" in csp
    assert "img-src 'self'" in csp

def test_no_external_images_in_templates():
    import re
    templates_dir = 'templates'
    # Catches src= or srcset= containing http://, https://, or // (protocol-relative)
    external_img_pattern = re.compile(r'<img[^>]+(?:src|srcset)=["\'][^"\']*(?:https?://|//)[^"\']*["\']', re.IGNORECASE)
    violations = []
    
    for root, _, files in os.walk(templates_dir):
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = external_img_pattern.findall(content)
                    for match in matches:
                        violations.append(f"{file_path}: {match}")
                        
    assert not violations, f"External images found in templates: {violations}"

