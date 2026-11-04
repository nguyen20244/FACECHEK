"""
test_filter.py - Test bộ lọc với bài thực tế
python test_filter.py
"""
from filters.strict_filter import classify

TEST_CASES = [
    ("✅ KO rõ ràng",        "원룸 양도합니다. 계약 승계 가능합니다.",           True),
    ("✅ VI rõ ràng",        "Mình muốn nhượng nhà, ai cần thì ib mình nhé",    True),
    ("✅ Pass oneroom",      "Pass oneroom gần ga, cọc 3tr, liên hệ mình",      True),
    ("✅ NHƯỢNG PHÒNG hoa", "NHƯỢNG PHÒNG GẤP khu soongsil, giá tốt",          True),
    ("✅ sangto",            "sangto oneroom gần trường, 300man",                True),
    ("✅ 1 key duy nhất",    "Nhượng lại phòng cho ai cần",                     True),
    ("❌ Tìm phòng KO",      "방 구합니다. 2월부터 입주 가능한 원룸 찾아요.",   False),
    ("❌ Tìm phòng VI",      "Mình đang tìm phòng gần trường, ai có không ạ",   False),
    ("❌ Không key nào",     "Hôm nay trời đẹp quá mọi người ơi",               False),
]

def main():
    print("=" * 60)
    print("  STRICT FILTER TEST")
    print("=" * 60)
    passed = 0
    for desc, text, expected in TEST_CASES:
        r = classify(text)
        ok = r["matched"] == expected
        if ok: passed += 1
        icon = "✅ PASS" if ok else "❌ FAIL"
        print(f"\n{icon} | {desc}")
        print(f"   matched={r['matched']} | confidence={r['confidence']}")
        print(f"   transfer={r['matched_transfer']}")
        if r['matched_seek']:
            print(f"   seek={r['matched_seek']}")
    print(f"\n{'='*60}")
    print(f"  KẾT QUẢ: {passed}/{len(TEST_CASES)} passed")
    print("=" * 60)

if __name__ == "__main__":
    main()
