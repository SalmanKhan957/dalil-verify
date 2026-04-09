import json

def analyze_json_structure(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print("=== 1. Top-Level Keys ===")
        if isinstance(data, dict):
            print(list(data.keys()))
        elif isinstance(data, list):
            print(f"File is a root-level list containing {len(data)} items.")
            data = {'items': data} # Wrap it to parse the first item safely
        else:
            print("Unknown root structure.")
            return

        if 'metadata' in data:
            print("\n=== 2. Metadata Keys ===")
            print(list(data['metadata'].keys()))
            
        if 'chapters' in data and len(data['chapters']) > 0:
            print("\n=== 3. Sample 'Chapter' Record (Likely the Kitab/Book) ===")
            print(json.dumps(data['chapters'][0], indent=2, ensure_ascii=False))
            
        if 'hadiths' in data and len(data['hadiths']) > 0:
            print("\n=== 4. Sample 'Hadith' Record ===")
            print(json.dumps(data['hadiths'][0], indent=2, ensure_ascii=False))
            
        # If the structure is an array of books (another common format)
        if 'items' in data and len(data['items']) > 0:
             print("\n=== Sample Root Record ===")
             print(json.dumps(data['items'][0], indent=2, ensure_ascii=False)[:1000] + "\n... [truncated]")

    except FileNotFoundError:
        print(f"Error: Could not find '{filepath}'. Make sure it's in the same folder as this script.")
    except json.JSONDecodeError:
        print("Error: The file is not valid JSON.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    analyze_json_structure('bukhari.json')