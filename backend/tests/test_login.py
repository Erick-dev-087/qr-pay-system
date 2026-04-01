import requests
import json


def test_user_login():
    url = 'http://127.0.0.1:5000/api'
    print("Testing User LogIn")
    try:
        response = requests.post(f'{url}/auth/login',
        json = {'email': 'dan@njoroge.com', 'password':'Daniel01'},
        )
        data = response.json()
        print(f"Response: {data}")
    except Exception as e:
        print(f'Error: {e}')


if __name__ == "__main__":
    test_user_login()