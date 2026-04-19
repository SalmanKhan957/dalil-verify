import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

from domains.ask.dispatcher import dispatch_ask_query

def main():
    print("=== FIRST REQUEST ===")
    res1 = dispatch_ask_query("Tafsir of surah baqarah", request_context={"conversation_id": "test_conv_3"})
    
    import json
    with open("tmp/test_v2_res1.json", "w", encoding="utf-8") as f:
        json.dump(res1, f, indent=2)
        
    quran1 = res1.get('quran_support') or {}
    print(f"Quran Support 1: Ayah Start={quran1.get('ayah_start')} Ayah End={quran1.get('ayah_end')}")
    
    turn_id = res1.get('conversation', {}).get('turn_id')
    print(f"Turn ID: {turn_id}")
    
    print("\n=== SECOND REQUEST (CONTINUE) ===")
    res2 = dispatch_ask_query("continue", request_context={"conversation_id": "test_conv_3", "parent_turn_id": turn_id})
    
    # Save the output to a utf-8 file to easily view the whole payload
    import json
    with open("tmp/test_v2_res2.json", "w", encoding="utf-8") as f:
        json.dump(res2, f, indent=2)
        
    print(f"R2 Route Type: {res2.get('route_type')}")
    print(f"R2 Reason: {res2.get('orchestration', {}).get('interpretation', {}).get('route_reason')}")
    quran2 = res2.get('quran_support') or {}
    print(f"Quran Support 2: Ayah Start={quran2.get('ayah_start')} Ayah End={quran2.get('ayah_end')}")

if __name__ == "__main__":
    main()
