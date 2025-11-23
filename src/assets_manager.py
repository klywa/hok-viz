import requests
import json
import os
import time

# Base URLs for Tencent's Honor of Kings (PVP) Official Site
HERO_LIST_URL = "https://pvp.qq.com/web201605/js/herolist.json"
ITEM_LIST_URL = "https://pvp.qq.com/web201605/js/item.json"
SUMMONER_URL = "https://pvp.qq.com/web201605/js/summoner.json" # Summoner skills

# Image Base URLs
HERO_ICON_BASE = "https://game.gtimg.cn/images/yxzj/img201606/heroimg/{}/{}.jpg"
ITEM_ICON_BASE = "https://game.gtimg.cn/images/yxzj/img201606/itemimg/{}.jpg"
SUMMONER_ICON_BASE = "https://game.gtimg.cn/images/yxzj/img201606/summoner/{}.jpg"

# Map Image (We might need to find a static URL or use a placeholder if not easily scrapeable)
# A common minimap URL or we can just generate a blank one for now if not found.
# Using a placeholder map URL for standard 5v5 map if available, otherwise we might need to ask user to provide or generate one.
# For now, we will try to download a known map image or generate a grid.

ASSETS_DIR = "assets"

def download_file(url, filepath):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, stream=True)
        if r.status_code == 200:
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(1024):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
    return False

def download_assets():
    print("Downloading metadata...")
    
    # Heroes
    headers = {'User-Agent': 'Mozilla/5.0'}
    r_hero = requests.get(HERO_LIST_URL, headers=headers)
    heroes = r_hero.json()
    
    # Items
    r_item = requests.get(ITEM_LIST_URL, headers=headers)
    items = r_item.json()

    # Save metadata
    with open(os.path.join(ASSETS_DIR, 'heroes.json'), 'w', encoding='utf-8') as f:
        json.dump(heroes, f, ensure_ascii=False, indent=2)
    with open(os.path.join(ASSETS_DIR, 'items.json'), 'w', encoding='utf-8') as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
        
    print(f"Found {len(heroes)} heroes and {len(items)} items.")

    # Download Hero Icons
    print("Downloading Hero icons...")
    for hero in heroes:
        ename = hero['ename']
        # name = hero['cname']
        filepath = os.path.join(ASSETS_DIR, 'heroes', f"{ename}.jpg")
        if not os.path.exists(filepath):
            url = HERO_ICON_BASE.format(ename, ename)
            download_file(url, filepath)
            print(f"Downloaded hero {ename}", end='\r')
    print("\nHero icons downloaded.")

    # Download Item Icons
    print("Downloading Item icons...")
    for item in items:
        item_id = item['item_id']
        filepath = os.path.join(ASSETS_DIR, 'items', f"{item_id}.jpg")
        if not os.path.exists(filepath):
            url = ITEM_ICON_BASE.format(item_id)
            download_file(url, filepath)
            # print(f"Downloaded item {item_id}", end='\r')
    print("Item icons downloaded.")

if __name__ == "__main__":
    download_assets()

