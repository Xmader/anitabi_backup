import json
import os
import urllib.request
from urllib.parse import urlparse
import concurrent.futures
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DB = os.path.join(REPO_ROOT, "data", "junreimap_full_database.json")
MEDIA_DIR = os.path.join(REPO_ROOT, "media_assets")

os.makedirs(MEDIA_DIR, exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
BASE_URL = "https://w.junreimap.com"

def download_file(url, target_path):
    if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
        return True, "EXISTS"
    
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp, open(target_path, "wb") as f:
            f.write(resp.read())
        return True, "DOWNLOADED"
    except Exception as e:
        return False, str(e)

def url_to_local_path(url):
    parsed = urlparse(url)
    rel_path = parsed.path.lstrip('/')
    local_rel = os.path.normpath(rel_path)
    return os.path.join(MEDIA_DIR, local_rel)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--all-points":
        mode = "ALL"
    else:
        mode = "COVERS_ONLY"
        
    print(f"=== JUNREIMAP MEDIA DOWNLOADER (Mode: {mode}) ===", flush=True)
    
    if not os.path.exists(DATA_DB):
        print(f"Error: Database file not found at {DATA_DB}. Please run generate_backup.py first.", flush=True)
        sys.exit(1)
        
    with open(DATA_DB, "r", encoding="utf-8") as f:
        database = json.load(f)
        
    tasks = []
    seen_paths = set()
    
    # 1. Collect covers
    for b in database:
        cover_url = b.get('cover_url')
        if cover_url:
            local_path = url_to_local_path(cover_url)
            if local_path not in seen_paths:
                seen_paths.add(local_path)
                tasks.append((cover_url, local_path))

    # 2. Collect point images if mode == ALL
    if mode == "ALL":
        for b in database:
            for pt in b.get('points', []):
                img_url = pt.get('image_url')
                if img_url:
                    local_path = url_to_local_path(img_url)
                    if local_path not in seen_paths:
                        seen_paths.add(local_path)
                        tasks.append((img_url, local_path))
                    
    total_files = len(tasks)
    print(f"Total media files queued for download: {total_files}", flush=True)
    
    completed = 0
    skipped = 0
    errors = 0
    
    start_t = time.time()
    max_workers = 16
    print(f"Starting downloader with {max_workers} worker threads...\n", flush=True)
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {executor.submit(download_file, url, path): (url, path) for url, path in tasks}
        for future in concurrent.futures.as_completed(future_to_url):
            try:
                success, status = future.result()
                completed += 1
                if status == "EXISTS":
                    skipped += 1
                elif not success:
                    errors += 1
            except Exception as exc:
                completed += 1
                errors += 1
                
            if completed % 100 == 0 or completed == total_files:
                elapsed = time.time() - start_t
                rate = completed / elapsed if elapsed > 0 else 0
                print(f"Progress: [{completed}/{total_files}] ({completed*100/total_files:.1f}%) | Speed: {rate:.1f} files/s | Errors: {errors}", flush=True)

    print(f"\nDone! Downloaded: {completed - skipped - errors}, Skipped (Already existed): {skipped}, Errors: {errors}", flush=True)
    print(f"Media folder location: {MEDIA_DIR}", flush=True)

if __name__ == "__main__":
    main()
