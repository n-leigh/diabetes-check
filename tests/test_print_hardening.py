import pytest
import re
from app import app, _IN_MEMORY_ASSESSMENTS, PRINT_TOKEN_TTL_SECONDS

data_template = {
    "BMI": "25.0", "Age": "5", "PhysHlth": "0", "MentHlth": "0",
    "HighChol": "0", "HighBP": "0", "Smoker": "0", "Stroke": "0",
    "HeartDiseaseorAttack": "0", "GenHlth": "1", "DiffWalk": "0",
    "DiabetesDuration": "1", "Sex": "1", "Ethnicity": "1",
    "HeavyAlcohol": "0", "AnyHealthcare": "1", "NoDocbcCost": "0",
    "BlurryVision": "0", "Tiredness": "0", "FrequentUrination": "0",
    "FamilyHistory": "0", "Veggies": "1", "Fruits": "1", "PhysActivity": "1"
}

@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as c:
        yield c

def get_csrf(client):
    res = client.get("/assessment")
    html = res.data.decode('utf-8')
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""

def generate_assessment(client):
    csrf = get_csrf(client)
    data = data_template.copy()
    data["csrf_token"] = csrf
    res = client.post("/predict", data=data)
    html = res.data.decode('utf-8')
    match = re.search(r'/print/([^?"]+)\?auto=1', html)
    return match.group(1) if match else None

def test_url_works_when_cookie_is_present(client):
    print_id = generate_assessment(client)
    assert print_id is not None
    
    # Get with cookie (should be 200)
    res_1 = client.get(f"/print/{print_id}?auto=1")
    assert res_1.status_code == 200
    
    # Token should be consumed, subsequent request should redirect (302)
    res_2 = client.get(f"/print/{print_id}?auto=1")
    assert res_2.status_code == 302
    assert b"/assessment" in res_2.data

def test_url_works_when_cookie_is_absent():
    # Simulate a cross-tab/cookie-loss bug by using two separate clients.
    with app.test_client() as c1:
        print_id = generate_assessment(c1)
        assert print_id is not None
        
    with app.test_client() as c2:
        # c2 has no cookies initially, triggering fallback mechanism.
        res_1 = c2.get(f"/print/{print_id}?auto=1")
        assert res_1.status_code == 200
        
        # Token consumed
        res_2 = c2.get(f"/print/{print_id}?auto=1")
        assert res_2.status_code == 302
        assert b"/assessment" in res_2.data

def test_ttl_expiry(client):
    print_id = generate_assessment(client)
    
    # Backdate the token timestamp to simulate TTL expiry
    record = _IN_MEMORY_ASSESSMENTS.get(print_id)
    record['timestamp'] -= (PRINT_TOKEN_TTL_SECONDS + 10)
    
    res = client.get(f"/print/{print_id}?auto=1")
    assert res.status_code == 302
    assert b"/assessment" in res.data

def test_clear_history_invalidates_token(client):
    print_id = generate_assessment(client)
    
    csrf = get_csrf(client)
    res_clear = client.post("/history/clear", data={"csrf_token": csrf})
    assert res_clear.status_code == 302
    
    res_print = client.get(f"/print/{print_id}?auto=1")
    assert res_print.status_code == 302
    assert b"/assessment" in res_print.data

def test_403_on_mismatched_session():
    # client1 generates the token
    with app.test_client() as client1:
        print_id = generate_assessment(client1)

    # client2 gets its own session
    with app.test_client() as client2:
        client2.get("/assessment")
        
        # client2 attempts to access client1's token.
        # Since it HAS a cookie (a different one), it should be explicitly denied.
        res = client2.get(f"/print/{print_id}?auto=1")
        assert res.status_code == 403
