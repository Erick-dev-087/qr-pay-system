import requests
import json

def test_user_registration():
    BASE_URL = 'http://127.0.0.1:5000/api'
    print("Testing User Registration")
    payload = {
        'name': 'Arnold Kimani',
        'phone_number': '254726489145',
        'email': 'kimani876@gmail.com',
        'password': 'secure_pass123'
    }
    try:
        response = requests.post(f'{BASE_URL}/auth/register/user', json=payload,timeout=10)
        print(f'Status: {response.status_code}')
        print(f'Response: {json.dumps(response.json(), indent=2)}')
    except Exception as e:
        print(f'Error: {e}')


if __name__ == "__main__":
    test_user_registration()