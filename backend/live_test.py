import asyncio
import json
import uuid
import httpx
from redis.asyncio import Redis

BASE_URL = "http://localhost:8000/api/v1"
PHONE = "+919876543210"
DEVICE_INFO = "Live Test Script"

async def main():
    print("--- LIVE TEST SCRIPT ---")
    
    # 1. Connect to Redis to intercept OTP
    redis = Redis.from_url("redis://localhost:6379/0")
    
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        # Request OTP
        print("\n1. Requesting OTP...")
        resp = await client.post("/auth/send-otp", json={"phone": PHONE})
        print(resp.status_code, resp.text)
        if resp.status_code != 200: return
        
        # Read OTP from Redis
        otp_code = "000000"
        print(f"Intercepted OTP: {otp_code}")
        
        # Verify OTP
        print("\n2. Verifying OTP...")
        resp = await client.post("/auth/verify-otp", json={
            "phone": PHONE,
            "otp": str(otp_code),
            "device_info": DEVICE_INFO
        })
        print(resp.status_code, resp.text)
        if resp.status_code != 200: return
        
        data = resp.json()["data"]
        token = data["tokens"]["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Create profile if not exists
        print("\n3. Checking Profile...")
        resp = await client.get("/profiles/me", headers=headers)
        if resp.status_code == 404:
            print("Creating profile...")
            resp = await client.post("/profiles", headers=headers, json={
                "first_name": "Live",
                "last_name": "User",
                "gender": "MALE",
                "date_of_birth": "1990-01-01",
                "marital_status": "NEVER_MARRIED",
                "country": "India",
                "disability_type": "VISUAL",
                "disability_onset": "SINCE_BIRTH"
            })
            print(resp.status_code, resp.text)
        elif resp.status_code == 200:
            print("Profile exists.")
        
        # Edit Basic Details
        print("\n4. Editing Basic Details...")
        resp = await client.patch("/profiles/me", headers=headers, json={
            "bio": "This is a live test."
        })
        print(resp.status_code, resp.text)
        
        # Edit Disability & Health
        print("\n5. Editing Disability & Health...")
        resp = await client.put("/profiles/me/sensitive", headers=headers, json={
            "disability_percentage": 50,
            "health_conditions": "None"
        })
        print(resp.status_code, resp.text)
        
        # Edit Partner Preferences
        print("\n6. Editing Partner Preferences...")
        resp = await client.put("/profiles/me/preferences", headers=headers, json={
            "preferred_gender": "FEMALE",
            "age_min": 25,
            "age_max": 35
        })
        print(resp.status_code, resp.text)
        
        # Photo Upload Session
        print("\n7. Requesting Photo Upload Session...")
        resp = await client.post("/profiles/me/photos/upload-sessions", headers=headers)
        print(resp.status_code, resp.text)

if __name__ == "__main__":
    asyncio.run(main())
