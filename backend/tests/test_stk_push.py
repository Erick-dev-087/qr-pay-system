#!/usr/bin/env python
"""
Test STK Push through Payment Routes (Integration Test)

This tests the complete flow:
1. Login as user
2. Get access token
3. Get a QR code ID (from seed_data - ID should be 1-5)
4. Initiate payment via API route
5. Route handles STK push internally
"""

import os
import json
import requests
from dotenv import load_dotenv
import time

load_dotenv()

# API Configuration
API_BASE = 'https://qr-pay-system.onrender.com/api'

# Test credentials from seed_data.py
TEST_USER = {
    'email': 'dan@njoroge.com',
    'password': 'Daniel01'
}

# QR Code IDs should be 1-5 if seed_data.py was run
TEST_QR_CODE_ID = 3

print('='*70)
print('TEST: STK PUSH INTEGRATION TEST - Via Payment Routes')
print('='*70)

def test_payment_flow():
    """Test the complete payment flow through API routes"""
    
    try:
        print('\nSTEP 1: Login as user')
        print('-' * 70)
        
        # Login as user
        login_response = requests.post(
            f'{API_BASE}/auth/login',
            json=TEST_USER,
            timeout=30
        )
        
        if login_response.status_code != 200:
            print(f'FAILED: Login failed: {login_response.status_code}')
            print(login_response.text)
            return False
        
        user_data = login_response.json()
        user_token = user_data['access_token']
        user_info = user_data.get('user', {})
        user_id = user_info.get('id', 'N/A')  # Extract user ID
        user_phone = user_info.get('phone', 'N/A')  # Extract phone from user object
        print(f'SUCCESS: User logged in: {TEST_USER["email"]}')
        print(f'   User ID: {user_id}')
        print(f'   Phone: {user_phone}')
        print(f'   Token: {user_token[:50]}...')
        
        
        print('\nSTEP 2: Get QR Code')
        print('-' * 70)
        
        # Use QR Code ID from seed data (1-5)
        qr_code_id = TEST_QR_CODE_ID
        print(f'Using QR Code ID: {qr_code_id} (from seed_data.py)')
        
        
        print('\nSTEP 3: Initiate STK Push Payment')
        print('-' * 70)
        
        # Initiate payment
        payment_payload = {
            'qr_code_id': qr_code_id,
            'amount': 1  # 100 KES
        }
        
        print(f'Payload: {json.dumps(payment_payload, indent=2)}')
        
        payment_response = requests.post(
            f'{API_BASE}/payment/initiate',
            headers={
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            },
            json=payment_payload,
            timeout=30
        )
        
        print(f'\nResponse Status: {payment_response.status_code}')
        
        # Pretty print response
        try:
            response_data = payment_response.json()
            print(f'Response:\n{json.dumps(response_data, indent=2)}')
        except:
            print(f'Response:\n{payment_response.text}')
        
        
        if payment_response.status_code == 201:
            print('\nSUCCESS: Payment initiated!')
            response_data = payment_response.json()
            print(f'   Transaction ID: {response_data.get("transaction_id")}')
            print(f'   Checkout Request ID: {response_data.get("checkout_request_id")}')
            print(f'   Amount: {response_data.get("amount")} KES')
            print(f'   Vendor: {response_data.get("vendor", {}).get("name")}')
            print(f'   Status: {response_data.get("status")}')
            print(f'   Phone Prompted: {user_phone}')
            print('\nInstructions: Please check your phone and enter your M-Pesa PIN')

            time.sleep(3)

            max_wait = 30
            poll_interval = 1
            elapsed = 0

            while elapsed < max_wait:
                print(f"\r Waiting ... {elapsed}s / {max_wait}s", end='', flush=True)
                status_response =  requests.get(
                    f'{API_BASE}/payment/{response_data.get("transaction_id")}/status',
                    headers={
                        'Authorization': f'Bearer {user_token}'
                    },
                    timeout= 10
                )

                if status_response.status_code == 200:
                    transaction = status_response.json()
                    status = transaction['status']

                    if status != 'pending':
                        print(f'\n\n STEP 4: CALLBACK RECEIVED!')
                        print('-' * 70)

                        if status == 'success':
                            print('✅ Payment SUCCESSFUL!')
                        print(f'   Transaction ID: {transaction["id"]}')
                        print(f'   Amount: {transaction["amount"]} KES')
                        print(f'   M-Pesa Receipt: {transaction["mpesa_receipt"]}')
                        print(f'   Completed at: {transaction["completed_at"]}')
                        return True
            
                # Wait before next poll
                time.sleep(poll_interval)
                elapsed += poll_interval
            
            # Timeout
            print(f'\n\n TIMEOUT: No callback received after {max_wait} seconds')
            print('   User may not have entered PIN or payment timed out')
            return False
            
        elif payment_response.status_code == 400:
            print('\nFAILED: 400 Bad Request')
            data = payment_response.json()
            print(f'   Error: {data.get("error")}')
            print(f'   Message: {data.get("message")}')
            return False
            
        elif payment_response.status_code == 401:
            print('\nFAILED: 401 Unauthorized')
            print('   Check your token or credentials')
            return False
            
        elif payment_response.status_code == 404:
            print('\nFAILED: 404 Not Found')
            print('   QR code or vendor not found')
            return False
            
        else:
            print(f'\nFAILED: Unexpected status {payment_response.status_code}')
            return False
    
    except requests.exceptions.ConnectionError:
        print('\nFAILED: Connection Error')
        print('   Make sure Flask is running on http://localhost:5000')
        return False
        
    except requests.exceptions.Timeout:
        print('\nFAILED: Request Timeout')
        return False
        
    except Exception as e:
        print(f'\nFAILED: Error: {str(e)}')
        return False


def main():
    """Main test runner"""
    
    print('\nChecking Flask server...')
    try:
        health = requests.get(f'{API_BASE}/health', timeout=5)
        if health.status_code == 200:
            print('SUCCESS: Flask server is running!\n')
        else:
            print(f'WARNING: Flask returned {health.status_code}\n')
    except:
        print('FAILED: Flask server is NOT running!')
        print('   Start it with: python app.py\n')
        return False
    
    # Run the test
    success = test_payment_flow()
    
    print('\n' + '='*70)
    if success:
        print('SUCCESS: TEST PASSED - Payment flow works!')
    else:
        print('FAILED: TEST FAILED - Check the errors above')
    print('='*70 + '\n')
    
    return success


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)

   