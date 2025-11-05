import requests

if __name__ == "__main__":
    base = "https://scholar.google.com/scholar?"
    language = "en"
    start = 0
    num = 10
    query = "machine learning"
    url = f"{base}hl={language}&num={num}&start={start}&q={query}"

    headers_to_use = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.google.com/",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document"
        }

    session = requests.Session()
    session.headers = headers_to_use
    response = session.get(url)
    print(f"Status code: {response.status_code}")