import json
import pathlib

def inspect_dataset_deep(file_path):
    p = pathlib.Path(file_path)
    if not p.exists():
        print(f"❌ Error: File not found at {p.resolve()}")
        return

    # Print basic file stats
    print(f"📁 Analyzing: {p.name} ({p.stat().st_size / 1024 / 1024:.2f} MB)")
    
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Error reading JSON: {e}")
        return

    print(f"🧱 Root Data Type: {type(data).__name__}")

    # Unpack dictionary if the data is nested under a key
    if isinstance(data, dict):
        print(f"🔑 Top-level keys: {list(data.keys())}")
        for k, v in data.items():
            if isinstance(v, list) and len(v) > 0:
                print(f"👉 Found likely data array in key '{k}' with {len(v)} items.")
                data = v
                break
        else:
            print("⚠️ Could not find a primary data array inside the dictionary.")
            return

    # Analyze the array
    if isinstance(data, list):
        total_rows = len(data)
        print(f"📊 Total Records: {total_rows}")
        
        if total_rows == 0:
            return

        # 1. Aggregate unique keys across a sample to see the true schema
        sample_size = min(total_rows, 1000)
        all_keys = set()
        for item in data[:sample_size]:
            if isinstance(item, dict):
                all_keys.update(item.keys())
        
        print(f"\n🔍 Detected Schema Keys (based on first {sample_size} records):")
        for key in sorted(all_keys):
            print(f"  - {key}")

        # 2. DALIL-Specific Architectural Sanity Check
        print("\n🏛️ DALIL Architecture Check:")
        
        # Look for common variations of the required fields
        has_book = sum(1 for x in data if any(k in x.keys() for k in ['book', 'book_en', 'book_name', 'bookId', 'book_no']))
        has_chapter = sum(1 for x in data if any(k in x.keys() for k in ['chapter', 'chapter_en', 'chapter_name', 'baab', 'chapterId', 'chapter_no']))
        has_text = sum(1 for x in data if any(k in x.keys() for k in ['text', 'text_en', 'hadith_en', 'english', 'matn_en']))

        print(f"  - Records with Book (Kitab) info:    {has_book}/{total_rows} ({(has_book/total_rows)*100:.1f}%)")
        print(f"  - Records with Chapter (Baab) info:  {has_chapter}/{total_rows} ({(has_chapter/total_rows)*100:.1f}%)")
        print(f"  - Records with Hadith (Matn) text:   {has_text}/{total_rows} ({(has_text/total_rows)*100:.1f}%)")

        if has_chapter == 0:
            print("\n❌ CRITICAL: This dataset lacks Chapter/Baab metadata. It is UNFIT for Dalil's Baab-Enriched Retrieval.")
        else:
            print("\n✅ SUCCESS: This dataset appears to contain the hierarchical metadata we need.")

        # 3. Print a clean, formatted sample record
        print("\n👀 Sample Record (Record #0):")
        sample_str = json.dumps(data[0], indent=2, ensure_ascii=False)
        if len(sample_str) > 1500:
            print(sample_str[:1500] + "\n... [truncated for readability]")
        else:
            print(sample_str)

if __name__ == "__main__":
    # Point this to your new JSON file
    target_file = r"Sahih al-Bukhari.json"
    inspect_dataset_deep(target_file)