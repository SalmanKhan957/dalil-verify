import json
import re
from pathlib import Path
from collections import Counter, defaultdict

def run_audits():
    file_path = Path(r"Sahih al-Bukhari.json")
    
    if not file_path.exists():
        print(f"❌ Error: Could not find file at {file_path.resolve()}")
        return

    print(f"📁 Loading dataset: {file_path.name}...")
    try:
        rows = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"❌ Failed to parse JSON: {e}")
        return

    print("✅ Dataset loaded successfully. Starting audits...\n")

    # ==========================================
    # AUDIT 1: True Chapter-Title Cardinality
    # ==========================================
    print("=" * 80)
    print("AUDIT 1: True Chapter-Title Cardinality")
    print("=" * 80)
    
    titles = [str(r.get("Chapter_Title_English", "")).strip() for r in rows]
    nums = [r.get("Chapter_Number") for r in rows]

    print(f"Rows: {len(rows)}")
    print(f"Distinct Chapter_Number: {len(set(nums))}")
    print(f"Distinct Chapter_Title_English: {len(set(t for t in titles if t))}")
    print("\nTop 20 repeated chapter titles:")
    for title, count in Counter(titles).most_common(20):
        print(f"{count:>4} | {title[:120]}")


    # ==========================================
    # AUDIT 2: Chapter-Title Diversity Inside Each In-Book
    # ==========================================
    print("\n" + "=" * 80)
    print("AUDIT 2: Chapter-Title Diversity Inside Each In-Book")
    print("=" * 80)
    
    rx = re.compile(r'Book\s+(\d+),\s*Hadith\s+(\d+)', re.I)
    per_book_titles = defaultdict(set)

    for r in rows:
        ref = str(r.get("In-book reference", ""))
        m = rx.search(ref)
        if not m:
            continue
        book_no = int(m.group(1))
        title = str(r.get("Chapter_Title_English", "")).strip()
        if title:
            per_book_titles[book_no].add(title)

    print("Books with title counts (showing first 20):")
    for book_no in sorted(per_book_titles)[:20]:
        print(f"Book {book_no:>2} -> {len(per_book_titles[book_no])} distinct titles")

    max_titles = max(len(v) for v in per_book_titles.values()) if per_book_titles else 0
    print(f"\nMax distinct titles in a single book: {max_titles}")
    print(f"Total books parsed: {len(per_book_titles)}")


    # ==========================================
    # AUDIT 3: Inspect the 30 Missing-Reference Rows
    # ==========================================
    print("\n" + "=" * 80)
    print("AUDIT 3: Inspect Missing-Reference Rows")
    print("=" * 80)
    
    missing = {
        398, 673, 757, 1100, 1162, 1192, 1343, 1344, 2133, 2158, 2160, 2341, 3413, 
        3444, 3594, 3800, 4724, 4739, 4826, 4832, 4847, 5228, 5258, 5492, 5550, 
        5716, 5844, 5940, 6640, 6652
    }

    found_missing_count = 0
    for r in rows:
        ref = str(r.get("Reference", "")).strip()
        if not ref:
            continue
        try:
            num = int(ref.rstrip('/').split(':')[-1])
        except Exception:
            continue
            
        if num in missing:
            found_missing_count += 1
            print("-" * 80)
            print(f"Reference:            {ref}")
            print(f"In-book reference:    {r.get('In-book reference')}")
            print(f"Chapter_Number:       {r.get('Chapter_Number')}")
            print(f"Chapter_Title_English:{r.get('Chapter_Title_English')}")
            
            # Safely truncate text to keep output readable
            text = str(r.get("English_Text", ""))
            truncated = text[:200] + "..." if len(text) > 200 else text
            text_lines = truncated.replace('\n', ' ').split(' ')
            print(f"English_Text:         {' '.join(text_lines)}")

    print("-" * 80)
    print(f"Total missing records inspected: {found_missing_count} out of {len(missing)}")

if __name__ == "__main__":
    run_audits()