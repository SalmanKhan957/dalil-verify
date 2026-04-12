import json
from pathlib import Path

def display_maududi_structure():
    maududi_file = Path("data/raw/open_source/en-al-maududi-inline-footnotes.json")
    
    if not maududi_file.exists():
        print(f"❌ File not found: {maududi_file}")
        return
    
    print("📖 Loading Maududi Tafsir Data...\n")
    
    with open(maududi_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 80)
    print("COMPLETE STRUCTURE OF SURAH FATIHA (CHAPTER 1)")
    print("=" * 80)
    print("\n📋 All Ayahs of Surah Fatiha with Complete Fields:\n")
    
    # Extract all ayahs from Surah Fatiha (1:1 to 1:7)
    surah_fatiha_ayahs = {k: v for k, v in data.items() if k.startswith("1:")}
    
    for ayah_key in sorted(surah_fatiha_ayahs.keys(), key=lambda x: int(x.split(":")[1])):
        ayah_data = surah_fatiha_ayahs[ayah_key]
        print(f"📌 {ayah_key}:")
        print(f"   Fields: {list(ayah_data.keys())}")
        print(f"   Full Content:")
        print(json.dumps(ayah_data, indent=6, ensure_ascii=False))
        print()
    
    print("=" * 80)
    print("📊 DATA STRUCTURE SUMMARY")
    print("=" * 80)
    
    # Show structure of one ayah to understand all fields
    first_ayah = surah_fatiha_ayahs.get("1:1", {})
    print(f"\nExample Ayah (1:1) Structure:")
    print(f"  Key Format: 'surah:ayah' (e.g., '1:1', '1:2', etc.)")
    print(f"  Value Type: Dictionary with field(s): {list(first_ayah.keys())}")
    print(f"  Field 't': Contains the complete tafsir/explanation text with footnotes")
    print(f"\nTotal Ayahs in Surah Fatiha: {len(surah_fatiha_ayahs)}")
    print(f"Total Size of all Fatiha data: ~{sum(len(str(v)) for v in surah_fatiha_ayahs.values())} characters")

if __name__ == "__main__":
    display_maududi_structure()
