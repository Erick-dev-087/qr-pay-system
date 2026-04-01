import requests
import json

BASE_URL = 'http://127.0.0.1:5000/api'

def test_vendor_registration():
    """Test vendor registration with multiple vendors"""
    
    # Sample vendor data
    vendors = [
        {
            'name': 'Prestige Restaurant',
            'business_shortcode': 'PREST001',
            'email': 'prestige@restaurant.com',
            'phone': '254745892098',
            'password': 'pass_123',
            'merchant_id': '26873270',
            'mcc': '5812',
            'store_label': 'Nairobi Branch'
        },
        {
            'name': 'Elite Supermarket',
            'business_shortcode': 'ELITE002',
            'email': 'elite@supermarket.com',
            'phone': '254114749086',
            'password': 'elite@09',
            'merchant_id': 'MERCH123',
            'mcc': '5411',
            'store_label': 'Mombasa Branch'
        },
        {
            'name': 'Tech Solutions Ltd',
            'business_shortcode': 'TECH003',
            'email': 'tech@solutions.com',
            'phone': '254789456123',
            'password': 'TechPass789'
        }
    ]
    
    print("=" * 60)
    print("Testing Vendor Registration")
    print("=" * 60)
    
    for idx, vendor in enumerate(vendors, 1):
        print(f"\n[Vendor {idx}] Registering: {vendor['name']}")
        print(f"Email: {vendor['email']}")
        
        try:
            response = requests.post(
                f'{BASE_URL}/auth/register/vendor',
                json=vendor,
                timeout=10
            )
            
            print(f'Status Code: {response.status_code}')
            
            if response.status_code == 201:
                data = response.json()
                print(f'✓ Success!')
                print(f'  Vendor ID: {data["vendor"]["id"]}')
                print(f'  Access Token: {data["access_token"][:50]}...')
                print(f'  Business Shortcode: {data["vendor"]["business_shortcode"]}')
            else:
                print(f'✗ Failed!')
                print(f'Response: {json.dumps(response.json(), indent=2)}')
        
        except requests.exceptions.ConnectionError:
            print(f'✗ Error: Unable to connect to server at {BASE_URL}')
            print(f'   Make sure the Flask app is running (python app.py)')
        except Exception as e:
            print(f'✗ Error: {type(e).__name__}: {e}')
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


def test_duplicate_vendor():
    """Test duplicate vendor registration (should fail with 409)"""
    
    vendor = {
        'name': 'Duplicate Business',
        'business_shortcode': 'DUP001',
        'email': 'duplicate@business.com',
        'phone': '254712111111',
        'password': 'Password123'
    }
    
    print("\n" + "=" * 60)
    print("Testing Duplicate Vendor Registration")
    print("=" * 60)
    
    try:
        # First registration (should succeed)
        print("\n[Attempt 1] Registering first vendor...")
        response1 = requests.post(
            f'{BASE_URL}/auth/register/vendor',
            json=vendor,
            timeout=10
        )
        print(f'Status: {response1.status_code}')
        
        if response1.status_code == 201:
            print('✓ First registration successful')
            
            # Second registration with same email (should fail)
            print("\n[Attempt 2] Attempting to register with same email...")
            response2 = requests.post(
                f'{BASE_URL}/auth/register/vendor',
                json=vendor,
                timeout=10
            )
            print(f'Status: {response2.status_code}')
            
            if response2.status_code == 409:
                print('✓ Correctly rejected duplicate email!')
                print(f'Response: {json.dumps(response2.json(), indent=2)}')
            else:
                print(f'✗ Unexpected response: {response2.json()}')
        else:
            print(f'✗ First registration failed: {response1.json()}')
    
    except Exception as e:
        print(f'✗ Error: {e}')
    
    print("\n" + "=" * 60)


def test_missing_fields():
    """Test registration with missing required fields"""
    
    incomplete_vendors = [
        {
            'name': 'Missing Email',
            'business_shortcode': 'MISS001',
            'phone': '254712222222',
            'password': 'Password123'
        },
        {
            'name': 'Missing Phone',
            'business_shortcode': 'MISS002',
            'email': 'missing@test.com',
            'password': 'Password123'
        },
        {
            'business_shortcode': 'MISS003',
            'email': 'missing@test2.com',
            'phone': '254712333333',
            'password': 'Password123'
        }
    ]
    
    print("\n" + "=" * 60)
    print("Testing Missing Required Fields")
    print("=" * 60)
    
    for idx, vendor_data in enumerate(incomplete_vendors, 1):
        print(f"\n[Test {idx}] Attempting registration with incomplete data...")
        try:
            response = requests.post(
                f'{BASE_URL}/auth/register/vendor',
                json=vendor_data,
                timeout=10
            )
            
            if response.status_code == 400:
                print(f'✓ Correctly rejected: {response.json()["error"]}')
            else:
                print(f'✗ Unexpected status {response.status_code}: {response.json()}')
        
        except Exception as e:
            print(f'✗ Error: {e}')
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    # Run all tests
    test_vendor_registration()
    test_duplicate_vendor()
    test_missing_fields()
