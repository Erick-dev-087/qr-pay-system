"""
M-Pesa/Daraja Integration Service
Handles both CustomerPayBillOnline and CustomerBuyGoodsOnline transaction types
"""

import os
import requests
import base64
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Optional


class TransactionType(Enum):
    """M-Pesa Transaction Types"""
    BILL_PAYMENT = "CustomerPayBillOnline"      # Bill Payment
    BUY_GOODS = "CustomerBuyGoodsOnline"        # Goods/Services


class DarajaConfig:
    """Configuration for Daraja API"""
    
    def __init__(self):
        self.consumer_key = os.getenv('DARAJA_CONSUMER_KEY')
        self.consumer_secret = os.getenv('DARAJA_CONSUMER_SECRET')
        self.base_url = os.getenv('DARAJA_BASE_URL', 'https://sandbox.safaricom.co.ke')
        self.shortcode = os.getenv('DARAJA_SHORTCODE')
        self.passkey = os.getenv('DARAJA_PASSKEY')
        self.callback_url = os.getenv('DARAJA_CALLBACK_URL')
        
        # Optional: Goods till number (if different from bill payment till)
        self.goods_till = os.getenv('DARAJA_GOODS_TILL', self.shortcode)
        
        self.validate()
    
    def validate(self):
        """Validate all required credentials are present"""
        required = ['consumer_key', 'consumer_secret', 'shortcode', 'passkey', 'callback_url']
        missing = [attr for attr in required if not getattr(self, attr)]
        
        if missing:
            raise ValueError(f"Missing Daraja credentials: {', '.join(missing)}")


class DarajaService:
    """
    Handles M-Pesa/Daraja API interactions
    
    Supports both transaction types:
    - CustomerPayBillOnline: For bill payments
    - CustomerBuyGoodsOnline: For goods/services sales
    """
    
    def __init__(self):
        self.config = DarajaConfig()
        self.access_token = None
        self.token_expires_at = None
    
    def _get_access_token(self) -> str:
        """
        Get OAuth2 access token from Daraja.
        
        LEARNING: Tokens expire, so we cache and reuse them.
        
        Returns:
            str: Access token
            
        Raises:
            Exception: If token generation fails
        """
        # Return cached token if still valid
        if self.access_token and datetime.now(timezone.utc) < self.token_expires_at:
            return self.access_token
        
        url = f'{self.config.base_url}/oauth/v1/generate?grant_type=client_credentials'
        
        try:
            response = requests.get(
                url,
                auth=(self.config.consumer_key, self.config.consumer_secret),
                timeout=10
            )
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data['access_token']
            
            
            expires_in = int(data.get('expires_in', 3600))
            self.token_expires_at = datetime.now(timezone.utc)
           
            self.token_expires_at += timedelta(seconds=expires_in - 300)
            
            return self.access_token
            
        except Exception as e:
            raise Exception(f"Failed to get access token: {str(e)}")
    
    def _get_password(self, timestamp: str) -> str:
        """
        Generate M-Pesa password.
        
            
        Returns:
            str: Base64 encoded password
        """
        data = f'{self.config.shortcode}{self.config.passkey}{timestamp}'
        return base64.b64encode(data.encode()).decode()
    
    def initiate_stk_push(
        self,
        phone_number: str,
        amount: int,
        account_reference: str,
        transaction_desc: str,
        transaction_type: TransactionType = TransactionType.BILL_PAYMENT,
        custom_till: Optional[str] = None
    ) -> Dict:
        """
        Initiate STK Push (M-Pesa prompt on customer's phone).
        
        
            }
        """
        try:
            
            if not isinstance(phone_number, str) or not phone_number.startswith('254'):
                return {
                    'success': False,
                    'message': 'Phone number must start with 254'
                }
            
            if amount <= 0 or amount > 500000:
                return {
                    'success': False,
                    'message': 'Amount must be between 1 and 500,000 KES'
                }
            
          
            token = self._get_access_token()
            
            
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            password = self._get_password(timestamp)
            
            
            if transaction_type == TransactionType.BUY_GOODS:
               
                party_b = custom_till or self.config.goods_till
            else:
                
                party_b = self.config.shortcode
            
            
            payload = {
                'BusinessShortCode': self.config.shortcode,
                'Password': password,
                'Timestamp': timestamp,
                'TransactionType': transaction_type.value,  # "CustomerPayBillOnline" or "CustomerBuyGoodsOnline"
                'Amount': amount,
                'PartyA': phone_number,  # Customer's phone
                'PartyB': party_b,  # Recipient (till/merchant code)
                'PhoneNumber': phone_number,  # Where to send prompt
                'CallBackURL': self.config.callback_url,
                'AccountReference': account_reference[:12],  # Max 12 chars
                'TransactionDesc': transaction_desc[:13]  # Max 13 chars
            }
            
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f'{self.config.base_url}/mpesa/stkpush/v1/processrequest'
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            data = response.json()
            
            
            if response.status_code == 200:
                return {
                    'success': True,
                    'checkout_request_id': data.get('CheckoutRequestID'),
                    'request_id': data.get('RequestID'),
                    'message': 'STK push initiated successfully',
                    'response_code': data.get('ResponseCode'),
                    'response_description': data.get('ResponseDescription'),
                    'customer_message': data.get('CustomerMessage')
                }
            else:
               
                return {
                    'success': False,
                    'message': data.get('errorMessage', 'Failed to initiate STK push'),
                    'response_code': data.get('ResponseCode', response.status_code),
                    'error_details': data
                }
        
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'message': 'Request timeout - Daraja service not responding'
            }
        except requests.exceptions.ConnectionError:
            return {
                'success': False,
                'message': 'Connection error - Failed to reach Daraja service'
            }
        except Exception as e:
            return {
                'success': False,
                'message': f'Error initiating STK push: {str(e)}'
            }
    
    def query_transaction_status(self, checkout_request_id: str) -> Dict:
        """
        Query the status of an STK push transaction.
        
        
        """
        try:
            token = self._get_access_token()
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
            password = self._get_password(timestamp)
            
            payload = {
                'BusinessShortCode': self.config.shortcode,
                'CheckoutRequestID': checkout_request_id,
                'Password': password,
                'Timestamp': timestamp
            }
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            url = f'{self.config.base_url}/mpesa/stkpushquery/v1/query'
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            
            return {
                'success': response.status_code == 200,
                'response_code': data.get('ResponseCode'),
                'result_code': data.get('ResultCode'),
                'result_desc': data.get('ResultDesc'),
                'checkout_request_id': data.get('CheckoutRequestID'),
                'data': data
            }
        
        except Exception as e:
            return {
                'success': False,
                'message': f'Error querying transaction status: {str(e)}'
            }



def initiate_payment(
    phone_number: str,
    amount: int,
    account_reference: str,
    description: str,
    transaction_type: TransactionType = TransactionType.BILL_PAYMENT
) -> Dict:
    """
    Convenience function to initiate STK push.
    
    Usage:
        result = initiate_payment(
            phone_number='254712345678',
            amount=500,
            account_reference='ORD-001',
            description='Purchase',
            transaction_type=TransactionType.BILL_PAYMENT
        )
    """
    service = DarajaService()
    return service.initiate_stk_push(
        phone_number=phone_number,
        amount=amount,
        account_reference=account_reference,
        transaction_desc=description,
        transaction_type=transaction_type
    )
