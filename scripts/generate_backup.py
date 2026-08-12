import urllib.request
import json
import csv
import math
import os
import sys
import time

sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "https://w.junreimap.com"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)

RAW_DIR = os.path.join(REPO_ROOT, "raw")
DATA_DIR = os.path.join(REPO_ROOT, "data")
ANIME_DIR = os.path.join(DATA_DIR, "anime")
GEOJSON_DIR = os.path.join(DATA_DIR, "geojson")

os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(ANIME_DIR, exist_ok=True)
os.makedirs(GEOJSON_DIR, exist_ok=True)

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def fetch_json(url, save_path=None):
    print(f"Fetching: {url}", flush=True)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        content = resp.read()
        if save_path:
            with open(save_path, "wb") as f:
                f.write(content)
        return json.loads(content.decode('utf-8'))

def main():
    start_time = time.time()
    print("=== STARTING JUNREIMAP DATA BACKUP & EXPORT ===", flush=True)
    
    # Remove old backup_summary.json if present
    old_summary = os.path.join(DATA_DIR, "backup_summary.json")
    if os.path.exists(old_summary):
        os.remove(old_summary)
        print("Removed backup_summary.json", flush=True)

    # 1. Fetch g.json
    g_path = os.path.join(RAW_DIR, "g.json")
    g_raw = fetch_json(f"{BASE_URL}/d/g.json", g_path)
    
    bangumi_lite_list = g_raw[0]
    page_size = g_raw[1]
    modified_ts = g_raw[2]
    
    total_bangumi = len(bangumi_lite_list)
    total_pages = math.ceil(total_bangumi / page_size)
    
    print(f"\n[Index] Loaded {total_bangumi} bangumi entries. Page size: {page_size}, Total chunk files: {total_pages}", flush=True)
    
    # 2. Fetch bangumi-icons.json
    icons_path = os.path.join(RAW_DIR, "bangumi-icons.json")
    try:
        icons_data = fetch_json(f"{BASE_URL}/d/bangumi-icons.json", icons_path)
    except Exception as e:
        print(f"Failed to fetch bangumi-icons.json: {e}", flush=True)
        icons_data = {}

    # 3. Fetch all chunk files g0.json ... g{total_pages-1}.json
    detailed_chunks = {}
    for i in range(total_pages):
        chunk_fname = f"g{i}.json"
        chunk_path = os.path.join(RAW_DIR, chunk_fname)
        chunk_url = f"{BASE_URL}/d/{chunk_fname}"
        chunk_json = fetch_json(chunk_url, chunk_path)
        print(f"  Downloaded {chunk_fname}: {len(chunk_json)} detailed bangumi items", flush=True)
        for item in chunk_json:
            b_id = item[0]
            detailed_chunks[b_id] = item

    print(f"\n[Detailed Chunks] Total detailed bangumi entries retrieved: {len(detailed_chunks)}", flush=True)
    
    # 4. Parse & Merge Database
    full_database = []
    all_bangumi_rows = []
    all_points_rows = []
    geojson_features_all = []
    
    total_points_count = 0
    
    for lite_item in bangumi_lite_list:
        b_id = lite_item[0]
        title_cn = lite_item[1] if len(lite_item) > 1 and lite_item[1] else ""
        title_en = lite_item[2] if len(lite_item) > 2 and lite_item[2] else ""
        title_jp = lite_item[3] if len(lite_item) > 3 and lite_item[3] else ""
        region = lite_item[4] if len(lite_item) > 4 and lite_item[4] else ""
        color = lite_item[5] if len(lite_item) > 5 and lite_item[5] else ""
        cover_path = lite_item[6] if len(lite_item) > 6 and lite_item[6] else ""
        rating = lite_item[7] if len(lite_item) > 7 else None
        type_str = lite_item[8] if len(lite_item) > 8 and lite_item[8] else ""
        center_lat = lite_item[9] if len(lite_item) > 9 else None
        center_lng = lite_item[10] if len(lite_item) > 10 else None
        center_zoom = lite_item[11] if len(lite_item) > 11 else None
        points_flat = lite_item[12] if len(lite_item) > 12 and isinstance(lite_item[12], list) else []
        short_name = lite_item[13] if len(lite_item) > 13 and lite_item[13] else ""
        bgm_id = lite_item[15] if len(lite_item) > 15 else None
        icon_path = lite_item[16] if len(lite_item) > 16 and lite_item[16] else ""
        abbreviation = lite_item[17] if len(lite_item) > 17 and lite_item[17] else ""
        
        geo_dict = {}
        if points_flat:
            idx = 0
            while idx < len(points_flat):
                pid = points_flat[idx]
                plat = points_flat[idx+1] if idx+1 < len(points_flat) else None
                plng = points_flat[idx+2] if idx+2 < len(points_flat) else None
                pzoom = points_flat[idx+3] if idx+3 < len(points_flat) else None
                geo_dict[pid] = {'lat': plat, 'lng': plng, 'zoom': pzoom}
                idx += 4
        
        detailed_item = detailed_chunks.get(b_id)
        theme_meta = detailed_item[1] if detailed_item and len(detailed_item) > 1 else None
        raw_pts = detailed_item[2] if detailed_item and len(detailed_item) > 2 else []
        
        merged_points = []
        anime_geojson_features = []
        display_title = title_cn or title_jp or title_en
        
        for pt in raw_pts:
            pid = pt[0]
            pname = pt[1] if len(pt) > 1 and pt[1] else ""
            status_code = pt[5] if len(pt) > 5 else None
            img_rel = pt[6] if len(pt) > 6 and pt[6] else ""
            ep_cut = pt[8] if len(pt) > 8 and pt[8] else ""
            remark = pt[10] if len(pt) > 10 and pt[10] else ""
            location = pt[13] if len(pt) > 13 and pt[13] else ""
            user_id = pt[14] if len(pt) > 14 else None
            
            geo = geo_dict.get(pid, {})
            lat = geo.get('lat')
            lng = geo.get('lng')
            zoom = geo.get('zoom')
            
            img_url = f"{BASE_URL}{img_rel}" if img_rel.startswith('/') else img_rel
            
            pt_obj = {
                'id': pid,
                'name': pname,
                'location': location,
                'ep_cut': ep_cut,
                'remark': remark,
                'lat': lat,
                'lng': lng,
                'zoom': zoom,
                'image_path': img_rel,
                'image_url': img_url,
                'status_code': status_code,
                'user_id': user_id
            }
            merged_points.append(pt_obj)
            total_points_count += 1
            
            all_points_rows.append({
                'bangumi_id': b_id,
                'bangumi_title': display_title,
                'bangumi_title_jp': title_jp,
                'point_id': pid,
                'point_name': pname,
                'location': location,
                'ep_cut': ep_cut,
                'lat': lat,
                'lng': lng,
                'remark': remark,
                'image_url': img_url
            })
            
            if lat is not None and lng is not None:
                feature = {
                    'type': 'Feature',
                    'geometry': {
                        'type': 'Point',
                        'coordinates': [lng, lat]
                    },
                    'properties': {
                        'point_id': pid,
                        'point_name': pname,
                        'bangumi_id': b_id,
                        'bangumi_title': display_title,
                        'location': location,
                        'ep_cut': ep_cut,
                        'remark': remark,
                        'image_url': img_url
                    }
                }
                geojson_features_all.append(feature)
                anime_geojson_features.append(feature)

        cover_url = f"{BASE_URL}{cover_path}" if cover_path.startswith('/') else cover_path
        icon_url = f"{BASE_URL}{icon_path}" if icon_path.startswith('/') else icon_path
        
        bangumi_obj = {
            'id': b_id,
            'title_cn': title_cn,
            'title_jp': title_jp,
            'title_en': title_en,
            'region': region,
            'color': color,
            'cover_path': cover_path,
            'cover_url': cover_url,
            'icon_path': icon_path,
            'icon_url': icon_url,
            'rating': rating,
            'type': type_str,
            'center_lat': center_lat,
            'center_lng': center_lng,
            'center_zoom': center_zoom,
            'bgm_id': bgm_id,
            'short_name': short_name,
            'abbreviation': abbreviation,
            'points_count': len(merged_points),
            'theme_meta': theme_meta,
            'points': merged_points
        }
        
        full_database.append(bangumi_obj)
        
        # Write individual JSON per anime series
        anime_file = os.path.join(ANIME_DIR, f"{b_id}.json")
        with open(anime_file, "w", encoding="utf-8") as f:
            json.dump(bangumi_obj, f, ensure_ascii=False, indent=2, sort_keys=True)
            
        # Write individual GeoJSON per anime series
        anime_geojson_file = os.path.join(GEOJSON_DIR, f"{b_id}.geojson")
        anime_geojson_doc = {
            'type': 'FeatureCollection',
            'features': anime_geojson_features
        }
        with open(anime_geojson_file, "w", encoding="utf-8") as f:
            json.dump(anime_geojson_doc, f, ensure_ascii=False, indent=2, sort_keys=True)
            
        all_bangumi_rows.append({
            'id': b_id,
            'title_cn': title_cn,
            'title_jp': title_jp,
            'title_en': title_en,
            'region': region,
            'type': type_str,
            'rating': rating,
            'points_count': len(merged_points),
            'center_lat': center_lat,
            'center_lng': center_lng,
            'cover_url': cover_url,
            'bgm_id': bgm_id
        })

    print(f"\n[Merge & Split Completed]", flush=True)
    print(f"  Total Bangumi JSON files: {len(full_database)} files in data/anime/", flush=True)
    print(f"  Total Bangumi GeoJSON files: {len(full_database)} files in data/geojson/", flush=True)
    print(f"  Total Anime Pilgrimage Points: {total_points_count}", flush=True)
    print(f"  Total GeoJSON Features: {len(geojson_features_all)}", flush=True)
    
    # 5. Export Datasets
    full_db_path = os.path.join(DATA_DIR, "junreimap_full_database.json")
    print(f"\nSaving {full_db_path}...", flush=True)
    with open(full_db_path, "w", encoding="utf-8") as f:
        json.dump(full_database, f, ensure_ascii=False, indent=2)
        
    bangumi_list_path = os.path.join(DATA_DIR, "bangumi_list.json")
    print(f"Saving {bangumi_list_path}...", flush=True)
    with open(bangumi_list_path, "w", encoding="utf-8") as f:
        json.dump(all_bangumi_rows, f, ensure_ascii=False, indent=2)

    bangumi_csv_path = os.path.join(DATA_DIR, "bangumi_list.csv")
    print(f"Saving {bangumi_csv_path}...", flush=True)
    with open(bangumi_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_bangumi_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_bangumi_rows)

    points_csv_path = os.path.join(DATA_DIR, "points_all.csv")
    print(f"Saving {points_csv_path}...", flush=True)
    with open(points_csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_points_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_points_rows)

    geojson_path = os.path.join(DATA_DIR, "points_all.geojson")
    print(f"Saving {geojson_path}...", flush=True)
    geojson_doc = {
        'type': 'FeatureCollection',
        'features': geojson_features_all
    }
    with open(geojson_path, "w", encoding="utf-8") as f:
        json.dump(geojson_doc, f, ensure_ascii=False, indent=2)
        
    elapsed = time.time() - start_time
    print(f"\nSUCCESS! Backup generated in {elapsed:.2f} seconds.", flush=True)
    print(f"Backup output directory: {REPO_ROOT}", flush=True)

if __name__ == "__main__":
    main()
