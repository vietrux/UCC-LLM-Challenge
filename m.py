import requests

# === CONFIGURATION ===
API_KEY = "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"
BASE_URL = "https://openrouter.ai/api/v1"

# === HEADERS ===
headers = {
    "Authorization": f"Bearer {API_KEY}"
}

# === FUNCTION TO GET CREDIT BALANCE ===
def get_credits():
    response = requests.get(f"{BASE_URL}/credits", headers=headers)
    if response.status_code == 200:
        return response.json()['data']
    else:
        print("[!] Failed to fetch credits.")
        return None

# === FUNCTION TO GET API KEY INFO ===
def get_key_info():
    response = requests.get(f"{BASE_URL}/auth/key", headers=headers)
    if response.status_code == 200:
        return response.json()['data']
    else:
        print("[!] Failed to fetch API key info.")
        return None

# === MAIN EXECUTION ===
def main():
    print("=== OpenRouter API Key Information ===\n")

    # Fetch credits
    credits = get_credits()
    if credits:
        print(f"Total Credits Available: {credits['total_credits']}")
        print(f"Total Credits Used:      {credits['total_usage']}\n")

    # Fetch API Key info
    key_info = get_key_info()
    if key_info:
        print(f"Label:                   {key_info['label']}")
        print(f"Usage (Credits Used):    {key_info['usage']}")
        print(f"Credit Limit:            {key_info['limit']}")
        print(f"Free Tier:               {key_info['is_free_tier']}")
        print(f"Rate Limit (Requests):   {key_info['rate_limit']['requests']}")
        print(f"Rate Limit Interval:     {key_info['rate_limit']['interval']}\n")

if __name__ == "__main__":
    main()
