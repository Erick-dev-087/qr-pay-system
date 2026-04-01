"""
Manual Callback Test - Simulate M-Pesa sending a callback

This script simulates M-Pesa sending a callback for a successful payment.
Useful for testing the callback endpoint without waiting for real M-Pesa.

Usage:
    python test_callback_manual.py
    
This will:
1. Login user
2. Initiate payment
3. Simulate M-Pesa callback with success result
4. Verify transaction status changed to SUCCESS
"""

import requests
import json
from dotenv import load_dotenv

load_dotenv()

API_BASE = 'http://localhost:5000/api'

def test_callback_flow():
    """Test manual callback"""
    
    print('='*70)
    print('MANUAL CALLBACK TEST - Simulating M-Pesa Callback')
    print('='*70)
    
    try:
        # STEP 1: Login
        print('\nSTEP 1: Login and initiate payment...')
        print('-' * 70)
        
        login_response = requests.post(
            f'{API_BASE}/auth/login',
            json={'email': 'john.kamau@email.com', 'password': 'password123'},
            timeout=30
        )
        
        if login_response.status_code != 200:
            print(f'FAILED: Login failed')
            return False
        
        user_data = login_response.json()
        user_token = user_data['access_token']
        user_phone = user_data.get('user', {}).get('phone')
        print(f'SUCCESS: Logged in as john.kamau@email.com')
        print(f'   Phone: {user_phone}')
        
        # STEP 2: Initiate payment
        print('\nSTEP 2: Initiating payment...')
        print('-' * 70)
        
        payment_response = requests.post(
            f'{API_BASE}/payment/initiate',
            headers={
                'Authorization': f'Bearer {user_token}',
                'Content-Type': 'application/json'
            },
            json={'qr_code_id': 1, 'amount': 1},
            timeout=30
        )
        
        if payment_response.status_code != 201:
            print(f'FAILED: Payment initiation failed')
            print(payment_response.json())
            return False
        
        payment_data = payment_response.json()
        transaction_id = payment_data['transaction_id']
        checkout_request_id = payment_data['checkout_request_id']
        
        print(f'SUCCESS: Payment initiated')
        print(f'   Transaction ID: {transaction_id}')
        print(f'   Checkout Request ID: {checkout_request_id}')
        
        # STEP 3: Simulate M-Pesa callback
        print('\nSTEP 3: Simulating M-Pesa callback (success)...')
        print('-' * 70)
        
        # Build callback payload (mimics real M-Pesa format)
        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "29115-34620561-1",
                    "CheckoutRequestID": checkout_request_id,
                    "ResultCode": 0,  # 0 = Success
                    "ResultDesc": "The service request has been initiated successfully",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 100},
                            {"Name": "MpesaReceiptNumber", "Value": "LHG31H500G5"},
                            {"Name": "PhoneNumber", "Value": user_phone},
                            {"Name": "TransactionDate", "Value": 20240124153100},
                            {"Name": "TransactionID", "Value": "12234534"}
                        ]
                    }
                }
            }
        }
        
        print(f'Sending callback to: {API_BASE}/payment/confirm')
        print(f'Payload: {json.dumps(callback_payload, indent=2)}')
        
        callback_response = requests.post(
            f'{API_BASE}/payment/confirm',
            json=callback_payload,
            timeout=30
        )
        
        print(f'\nCallback Response Status: {callback_response.status_code}')
        print(f'Response: {callback_response.json()}')
        
        if callback_response.status_code == 200:
            print('SUCCESS: Callback received and processed')
        else:
            print(f'WARNING: Unexpected status {callback_response.status_code}')
        
        # STEP 4: Check transaction status
        print('\nSTEP 4: Checking transaction status...')
        print('-' * 70)
        
        status_response = requests.get(
            f'{API_BASE}/payment/{transaction_id}/status',
            headers={'Authorization': f'Bearer {user_token}'},
            timeout=30
        )
        
        if status_response.status_code == 200:
            status_data = status_response.json()
            transaction_status = status_data.get('status')
            mpesa_receipt = status_data.get('mpesa_receipt')
            
            print(f'SUCCESS: Got transaction status')
            print(f'   Status: {transaction_status}')
            print(f'   M-Pesa Receipt: {mpesa_receipt}')
            
            if transaction_status == 'success':
                print('\n✅ TEST PASSED - Callback processed and transaction marked SUCCESS!')
                return True
            else:
                print(f'\n⚠️ Transaction status is {transaction_status}, expected success')
                return False
        else:
            print(f'FAILED: Could not get transaction status')
            print(status_response.json())
            return False
        
    except requests.exceptions.ConnectionError:
        print('FAILED: Could not connect to Flask server')
        print('   Make sure Flask is running: python app.py')
        return False
    except Exception as e:
        print(f'FAILED: Error: {str(e)}')
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    import sys
    success = test_callback_flow()
    
    print('\n' + '='*70)
    if success:
        print('SUCCESS: Manual callback test passed!')
    else:
        print('FAILED: Manual callback test failed')
    print('='*70 + '\n')
    
    sys.exit(0 if success else 1)
