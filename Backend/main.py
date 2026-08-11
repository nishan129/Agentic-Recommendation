import pandas as pd
import requests

BASE_URL = "http://localhost:8000/api/v1"
LOGIN_URL = f"{BASE_URL}/auth/login"
CREATE_URL = f"{BASE_URL}/admin/products"

# 1. Authenticate first
login_payload = {
    "email": "nishant@gmail.com",
    "password": "12345678"
}

login_resp = requests.post(LOGIN_URL, json=login_payload)
login_resp.raise_for_status()
token = login_resp.json()["access_token"]

HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

# 2. Read Dataset
df = pd.read_csv("course_recommendation_dataset.csv")

# 3. Process and Upload Products
success_count = 0
failed_count = 0

for index, row in df.iterrows():
    tags_list = [t.strip() for t in str(row["tags"]).split(",") if t.strip()]

    payload = {
        "title": str(row["course_name"]).strip(),
        "description": str(row["description"]).strip() if pd.notna(row["description"]) else None,
        "category": str(row["category"]).strip(),
        "product_type": "course",
        "price": int(row["price_inr"]),
        "image_url": str(row["image_url"]).strip() if pd.notna(row["image_url"]) else None,
        "rating": float(row["rating"]) if pd.notna(row["rating"]) else None,
        "stock": 26,
        "tags": tags_list if len(tags_list) > 0 else None,
        "is_active": True
    }

    try:
        response = requests.post(CREATE_URL, json=payload, headers=HEADERS)

        if response.status_code in (200, 201):
            success_count += 1
            print(f"[{index + 1}/40] Added: {payload['title']}")
        else:
            failed_count += 1
            print(f"[{index + 1}/40] Failed ({response.status_code}): {payload['title']}")
            print(f"     Response: {response.text}")

    except requests.exceptions.RequestException as e:
        print(f"Connection error on item {index + 1}: {e}")
        break

print(f"\nUpload complete! Successfully added: {success_count}, Failed: {failed_count}")