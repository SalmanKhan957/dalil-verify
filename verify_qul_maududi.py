import json
from pathlib import Path

def audit_qul_data():
    file_path = Path("data/raw/open_source/en-al-maududi-inline-footnotes.json")
    
    if not file_path.exists():
        print(f"❌ File not found at {file_path}. Please check your download.")
        return

    print("📁 Loading Tarteel QUL Dataset...")
    data = json.loads(file_path.read_text(encoding="utf-8"))
    
    # In QUL's format, keys are usually "Surah:Ayah" (e.g., "2:30")
    target_ayah = "2:255"
    
    if target_ayah in data:
        record = data[target_ayah]
        print("\n✅ Ayah Found! Inspecting the Dictionary Shape...\n")
        print("=========================================")
        
        # Pretty-print the dictionary to see its exact keys and structure
        print(json.dumps(record, indent=2, ensure_ascii=False))
        
        print("=========================================")
        print("🔍 ARCHITECTURAL AUDIT:")
        print("Look at the output above. Does it have a key like 'text', ")
        print("'footnotes', or 'translation'? Paste the output here so we ")
        print("can write the final PostgreSQL ingestion mapping.")
    else:
        print(f"❌ Ayah {target_ayah} not found in the JSON keys.")

if __name__ == "__main__":
    audit_qul_data()