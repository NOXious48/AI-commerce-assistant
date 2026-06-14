import json
import urllib.request
from urllib.error import URLError, HTTPError

def check_images():
    try:
        with open("data/products_metadata/products_metadata.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading dataset: {e}")
        return

    print("Checking dataset image URLs...\n")
    valid = 0
    total = 0
    broken = 0
    
    products = data.get("products", [])
    
    # Just check the first 20 products
    for p in products[:20]:
        meta = p.get("metadata", {})
        images = meta.get("images", [])
        for img in images:
            url = img.get("large") or img.get("hi_res") or img.get("thumb")
            if url:
                total += 1
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    resp = urllib.request.urlopen(req, timeout=5)
                    if resp.getcode() == 200:
                        print(f"[OK] {url}")
                        valid += 1
                except HTTPError as e:
                    print(f"[FAIL {e.code}] {url}")
                    broken += 1
                except URLError as e:
                    print(f"[FAIL {e.reason}] {url}")
                    broken += 1
                except Exception as e:
                    print(f"[FAIL {e}] {url}")
                    broken += 1
                
                # Check only the main image
                break

    print(f"\nSummary: {valid}/{total} images are available (Broken: {broken})")

if __name__ == "__main__":
    check_images()
