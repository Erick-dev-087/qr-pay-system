# In a new file: utils/mpesa_mock.py

class MockMpesaService:
    """
    Mock M-Pesa service for testing payment flow
    Replace this with real Daraja integration later
    
    When implementing real Daraja, this class should:
    1. Get OAuth access token
    2. Generate password (base64 of shortcode+passkey+timestamp)
    3. Format timestamp as YYYYMMDDHHmmss
    4. Call actual STK Push API endpoint
    """
    
    @staticmethod
    def initiate_stk_push(business_shortcode, amount, phone_number, transaction_id, 
                         account_reference, transaction_desc, callback_url):
        """
        Simulates M-Pesa STK Push
        
        In production, this will call:
        POST https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest
        
        With payload:
        {
            "BusinessShortCode": business_shortcode,
            "Password": base64(shortcode + passkey + timestamp),
            "Timestamp": "20251105120000",
            "TransactionType": "CustomerBuyGoodsOnline",  # or "CustomerPayBillOnline"
            "Amount": amount,
            "PartyA": phone_number,
            "PartyB": business_shortcode,
            "PhoneNumber": phone_number,
            "CallBackURL": callback_url,
            "AccountReference": account_reference,
            "TransactionDesc": transaction_desc
        }
        
        Args:
            business_shortcode: Vendor's Till/Paybill number
            amount: Payment amount (integer)
            phone_number: Payer's phone (format: 254712345678)
            transaction_id: Database transaction ID
            account_reference: Transaction reference (e.g., "TXN-123")
            transaction_desc: Payment description
            callback_url: URL for M-Pesa to send payment confirmation
        
        Returns:
            dict: Mock response mimicking Daraja API response
        """
        # Simulate validation that would happen in production
        if not phone_number.startswith('254'):
            return {
                'success': False,
                'message': 'Invalid phone number format. Must start with 254',
                'response_code': '400'
            }
        
        if amount < 1:
            return {
                'success': False,
                'message': 'Amount must be at least 1 KES',
                'response_code': '400'
            }
        
        # Mock success response (what Daraja returns)
        return {
            'success': True,
            'message': 'STK Push sent successfully',
            'checkout_request_id': f'ws_CO_{transaction_id}_{business_shortcode}',
            'merchant_request_id': f'MR_{transaction_id}',
            'response_code': '0',
            'response_description': 'Success. Request accepted for processing',
            'customer_message': 'Success. Request accepted for processing'
        }
    
    @staticmethod
    def simulate_callback(transaction_id, success=True):
        """
        Simulates M-Pesa callback
        Use this for testing the /api/payment/stk_callback endpoint
        
        In production, M-Pesa will POST to your callback_url with this structure
        """
        if success:
            return {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': f'MR_{transaction_id}',
                        'CheckoutRequestID': f'ws_CO_{transaction_id}',
                        'ResultCode': 0,
                        'ResultDesc': 'The service request is processed successfully.',
                        'CallbackMetadata': {
                            'Item': [
                                {'Name': 'Amount', 'Value': 500},
                                {'Name': 'MpesaReceiptNumber', 'Value': f'QGK{transaction_id}ABC'},
                                {'Name': 'TransactionDate', 'Value': 20251105120000},
                                {'Name': 'PhoneNumber', 'Value': 254712345678}
                            ]
                        }
                    }
                }
            }
        else:
            return {
                'Body': {
                    'stkCallback': {
                        'MerchantRequestID': f'MR_{transaction_id}',
                        'CheckoutRequestID': f'ws_CO_{transaction_id}',
                        'ResultCode': 1032,
                        'ResultDesc': 'Request cancelled by user'
                    }
                }
            }
