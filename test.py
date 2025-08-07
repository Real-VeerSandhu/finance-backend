import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

def test_api():
    print("Testing Finance Portfolio API...")
    
    # Test 1: Register a new user
    print("\n1. Registering new user...")
    # register_data = {
    #     "username": "testuser",
    #     "email": "test@example.com",
    #     "password": "testpassword123"
    # }
    register_data = {
        "username": "testuser2",
        "email": "test2@example.com",
        "password": "testpassword123"
    }
    
    response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        print(f"✓ Registration successful! Token: {access_token[:20]}...")
    else:
        print(f"✗ Registration failed: {response.text}")
        return
    
    # Headers for authenticated requests
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Test 2: Research a stock
    print("\n2. Researching AAPL stock...")
    response = requests.get(f"{BASE_URL}/research/AAPL", headers=headers)
    if response.status_code == 200:
        stock_data = response.json()
        print(f"✓ Stock research successful!")
        print(f"   {stock_data['name']}: ${stock_data['price']}")
    else:
        print(f"✗ Stock research failed: {response.text}")
    
    # Test 3: Add position to portfolio
    print("\n3. Adding AAPL position to portfolio...")
    position_data = {"ticker": "AAPL", "shares": 10}
    response = requests.post(f"{BASE_URL}/portfolio/add", json=position_data, headers=headers)
    if response.status_code == 200:
        print(f"✓ Position added successfully!")
    else:
        print(f"✗ Failed to add position: {response.text}")
    
    # Test 4: Get portfolio
    print("\n4. Getting portfolio...")
    response = requests.get(f"{BASE_URL}/portfolio", headers=headers)
    if response.status_code == 200:
        portfolio = response.json()
        print(f"✓ Portfolio retrieved successfully!")
        print(f"   Portfolio has {len(portfolio['positions'])} positions")
        for pos in portfolio['positions']:
            print(f"   - {pos['ticker']}: {pos['shares']} shares")
    else:
        print(f"✗ Failed to get portfolio: {response.text}")
    
    # Test 5: Add to watchlist
    print("\n5. Adding MSFT to watchlist...")
    ticker_data = {"ticker": "MSFT"}
    response = requests.post(f"{BASE_URL}/watchlist/add", json=ticker_data, headers=headers)
    if response.status_code == 200:
        print(f"✓ Added to watchlist successfully!")
    else:
        print(f"✗ Failed to add to watchlist: {response.text}")
    
    # Test 6: Get watchlist
    print("\n6. Getting watchlist...")
    response = requests.get(f"{BASE_URL}/watchlist", headers=headers)
    if response.status_code == 200:
        watchlist = response.json()
        print(f"✓ Watchlist retrieved successfully!")
        print(f"   Watchlist contains: {', '.join(watchlist['tickers'])}")
    else:
        print(f"✗ Failed to get watchlist: {response.text}")
    
    print("\n✓ All tests completed!")

if __name__ == "__main__":
    test_api()