"""
test_trash_rule.py
------------------
Test is_trash_rule() với các case thực tế từ data.

Cách dùng:
    python3 test_trash_rule.py
"""

import re
from analyze_education_async import is_trash_rule

# Format: (text, expected, ghi_chu)
TEST_CASES = [
    # ── Phải là RÁC (True) ──────────────────────────
    ("Hhh",                                                         True,  "lặp ký tự"),
    ("Đoàn Đức Thành",                                              True,  "tên người thuần túy"),
    ("Huỳnh Phương Ngọc",                                           True,  "tên người thuần túy"),
    ("Phuong Nguyen Minh",                                          True,  "tên người không dấu"),
    ("Minh Dương",                                                  True,  "tên 2 từ"),
    ("Nguyễn Vanh",                                                 True,  "tên 2 từ"),
    ("Yen Nhii",                                                    True,  "tên 2 từ không dấu"),
    ("Trúc Phương bạn hiểu ý mình trứ 😌",                          True,  "tên + câu ngắn vô nghĩa"),
    ("Lê Thành Đạt =)) buồn không anh",                             True,  "tên + reaction ngắn"),
    ("Trần Gia Phú buồn cười :))",                                  True,  "tên + reaction"),
    ("Nguồn: https://moet.gov.vn/abc",                               True,  "link URL"),
    ("Hocmai.vn THPT Thảo Su",                                      True,  "tên tổ chức + trường"),
    ("Lụm về share",                                                True,  "spam share"),
    ("😂😂😂",                                                       True,  "chỉ emoji"),
    ("ok",                                                          True,  "quá ngắn"),

    # ── KHÔNG phải rác (False) ──────────────────────
    ("Trần Quang Đại vâng anh! Ủng hộ quan điểm của anh 100%",
     False, "tên + nội dung dài có ý kiến"),
    ("Nguyễn Phú Thịnh Bà Phương Hằng lên mạng chửi bới lung tung, công an cũng vào cuộc xác minh nghệ sĩ làm từ thiện đó thôi.",
     False, "tên + câu dài có nội dung"),
    ("Theo tôi đây chỉ là 1 biểu hiện lộ ra của việc thiếu tôn chỉ nhân bản của triết lý giáo dục vn mà thôi. Từ khi quyết thương mại hóa giáo dục tới khi GD trở thành thương trường và họ kiếm lợi nhuận bằng mọi giá thì ta có thể thấy các đề xuất của họ đầy mùi tiền nên nhiều lúc họ chỉ thở thôi ta đã thấy thối rồi đâu cần điều tra., tìm hiểu",
     False, "ý kiến dài"),
    ("Sự việc sẽ chỉ kết thúc khi có người bị 'Ủ TỜ' :3\nCòn ko thì sẽ tiếp tục",
     False, "trung lập có nội dung"),
    ("Truy cứu trách nhiệm những người liên quan giải nhất này",
     False, "tiêu cực ngắn nhưng có nội dung"),
    ("Hay quá, ủng hộ mạnh mẽ!",                                   False, "tích cực rõ ràng"),
    ("Đúng rồi",                                                    False, "tích cực ngắn"),
    ("Sai hoàn toàn",                                               False, "tiêu cực ngắn"),
    ("Kệ đi, không ảnh hưởng gì đến mình",                         False, "trung lập"),
    ("Có điểm hay nhưng nên sửa phần thi thực hành để công bằng hơn",
     False, "ý kiến riêng"),
]


def run_tests():
    passed = 0
    failed = 0

    print(f"{'─'*70}")
    print(f"{'TEXT':<45} {'EXPECT':<8} {'GOT':<8} {'STATUS'}")
    print(f"{'─'*70}")

    for text, expected, note in TEST_CASES:
        got    = is_trash_rule(text)
        ok     = got == expected
        status = "✅" if ok else "❌"
        label  = lambda b: "RÁC   " if b else "KHÔNG "

        if ok:
            passed += 1
        else:
            failed += 1

        display = text[:42] + "..." if len(text) > 45 else text
        print(f"{display:<45} {label(expected):<8} {label(got):<8} {status}  {note}")

    print(f"{'─'*70}")
    print(f"Kết quả: {passed}/{len(TEST_CASES)} passed | {failed} failed")

    if failed > 0:
        print(f"\n❌ FAILED cases:")
        for text, expected, note in TEST_CASES:
            got = is_trash_rule(text)
            if got != expected:
                print(f"  [{note}] \"{text[:80]}\"")
                print(f"    Expected: {'RÁC' if expected else 'KHÔNG RÁC'} | Got: {'RÁC' if got else 'KHÔNG RÁC'}")


if __name__ == "__main__":
    run_tests()

print(debug_trash("Theo tôi đây chỉ là 1 biểu hiện lộ ra của việc thiếu tôn chỉ nhân bản của triết lý giáo dục vn mà thôi. Từ khi quyết thương mại hóa giáo dục tới khi GD trở thành thương trường và họ kiếm lợi nhuận bằng mọi giá thì ta có thể thấy các đề xuất của họ đầy mùi tiền nên nhiều lúc họ chỉ thở thôi ta đã thấy thối rồi đâu cần điều tra., tìm hiểu"))