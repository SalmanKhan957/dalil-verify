import urllib.request
import sqlite3
from pathlib import Path

def fetch_and_audit_android_db():
    db_path = Path("data/raw/open_source/tafseer_en_maududi.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Official database mirror for Quran for Android
    url = "https://mirror.quran.com/android/databases/tafseer/en/tafseer_en_maududi.db"
    
    if not db_path.exists():
        print(f"1. Downloading Android SQLite Database...")
        print(f"   URL: {url}")
        print("   (This might take a few seconds, it's a real database file...)")
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req) as response, open(db_path, 'wb') as out_file:
                out_file.write(response.read())
            print("✅ Download complete!\n")
        except Exception as e:
            print(f"❌ Auto-download failed: {e}")
            return
    else:
        print(f"✅ Database already exists at {db_path}\n")

    print("2. Connecting to SQLite Database...")
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check the tables inside the database
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   Found tables: {tables}")
        
        target_table = "tafseer" if "tafseer" in tables else tables[0]

        # Query 2:30
        print(f"\n📦 Inspecting Record Shape (Surah 2, Ayah 30) from table '{target_table}':")
        cursor.execute(f"SELECT text FROM {target_table} WHERE sura = 2 AND ayah = 30")
        result = cursor.fetchone()
        
        if result:
            text_data = result[0]
            print("=========================================")
            # Printing just the first 1000 characters so it doesn't flood your terminal
            print(text_data[:1000] + ("...\n[TEXT TRUNCATED FOR READABILITY]" if len(text_data) > 1000 else ""))
            print("=========================================")
            print("\n🔍 ARCHITECTURAL AUDIT:")
            print(f"   Total character length of this Tafsir entry: {len(text_data)}")
            print("\n   If the text above contains paragraphs explaining the concept of a")
            print("   'Vicegerent' or 'Khalifah' instead of just a 2-line translation,")
            print("   we have officially found our gold mine. 🚨")
        else:
            print("❌ Ayah not found.")
            
        conn.close()
    except Exception as e:
        print(f"❌ SQLite Error: {e}")

if __name__ == "__main__":
    fetch_and_audit_android_db()