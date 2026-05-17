import { InsightsData } from './types';

export const INSIGHTS_DATA: InsightsData = {
  "overall": {
    "total_events": 85,
    "total_events_with_analysis": 50,
    "total_events_without_analysis": 35,
    "total_links": 668,
    "total_links_website": 446,
    "total_links_facebook": 222,
    "total_comments": {
      "raw": 36078,
      "clean": 29622,
      "trash": 6456,
      "trash_rate": "17.9%"
    },
    "by_category": {
      "education": {
        "events": 40,
        "comments_clean": 5370
      },
      "showbiz": {
        "events": 45,
        "comments_clean": 24252
      }
    }
  },
  "education": {
    "category": "education",
    "total_events": 40,
    "events_with_analysis": 20,
    "total_links": 82,
    "comment_stats": {
      "total_raw": 7815,
      "total_clean": 5370,
      "total_trash": 2445,
      "trash_rate": "31.3%"
    },
    "stance_distribution": {
      "tích cực": {
        "count": 644,
        "percent": "12.0%"
      },
      "tiêu cực": {
        "count": 2645,
        "percent": "49.3%"
      },
      "trung lập": {
        "count": 1729,
        "percent": "32.2%"
      },
      "ý kiến riêng": {
        "count": 352,
        "percent": "6.6%"
      }
    },
    "top_events_by_comments": [
      {
        "id_content": "education_007",
        "ten_su_kien": "Tranh luận việc xếp bác sĩ nội trú, chuyên khoa I tương đương thạc sĩ",
        "time_event": "",
        "total": 879,
        "clean": 771,
        "trash": 108
      },
      {
        "id_content": "education_011",
        "ten_su_kien": "Sở GD-ĐT Ninh Bình xác minh clip lãnh đạo trường THPT thân mật với nhiều phụ nữ",
        "time_event": "2025-11-10",
        "total": 1128,
        "clean": 717,
        "trash": 411
      },
      {
        "id_content": "education_017",
        "ten_su_kien": "thí điểm thi trung học phổ thông trên máy tính",
        "time_event": "2025-07-09",
        "total": 1212,
        "clean": 707,
        "trash": 505
      },
      {
        "id_content": "education_020",
        "ten_su_kien": "Đề thi THPT 2025 được đánh giá khó hơn dự kiến",
        "time_event": "2025-06-29",
        "total": 783,
        "clean": 633,
        "trash": 150
      },
      {
        "id_content": "education_018",
        "ten_su_kien": "hà nội dự kiến di dời đại học về phía Tây",
        "time_event": "2026-03-15",
        "total": 631,
        "clean": 500,
        "trash": 131
      },
      {
        "id_content": "education_037",
        "ten_su_kien": "Bộ Giáo dục lấy ý kiến về việc BỎ hình thức tuyển sinh bằng xét tuyển học bạ",
        "time_event": "2024-12-02",
        "total": 579,
        "clean": 426,
        "trash": 153
      },
      {
        "id_content": "education_009",
        "ten_su_kien": "Cô giáo phạt tát học sinh 231 cái",
        "time_event": "2018-11-25",
        "total": 510,
        "clean": 384,
        "trash": 126
      },
      {
        "id_content": "education_005",
        "ten_su_kien": "Tạm đình chỉ giáo viên tiếng Anh bị tố sửa bài thi học sinh",
        "time_event": "2026-01-24",
        "total": 431,
        "clean": 326,
        "trash": 105
      },
      {
        "id_content": "education_015",
        "ten_su_kien": "Trường Quốc tế Mỹ bị giải thể do Chủ trường bị điều tra vì huy động vốn từ phụ huynh lên tới hàng nghìn tỷ đồng.",
        "time_event": "2026-01-12",
        "total": 304,
        "clean": 187,
        "trash": 117
      },
      {
        "id_content": "education_004",
        "ten_su_kien": "Khởi tố hiệu trưởng Trường Cao đẳng Du lịch Hà Nội",
        "time_event": "",
        "total": 282,
        "clean": 186,
        "trash": 96
      }
    ],
    "events_by_year": {
      "2018": 1,
      "2022": 1,
      "2023": 3,
      "2024": 3,
      "2025": 21,
      "2026": 6,
      "unknown": 5
    },
    "events_without_analysis": 20
  },
  "showbiz": {
    "category": "showbiz",
    "total_events": 45,
    "events_with_analysis": 30,
    "total_links": 139,
    "events_without_analysis": 15,
    "comment_stats": {
      "total_raw": 28263,
      "total_clean": 24252,
      "total_trash": 4011,
      "trash_rate": "14.2%"
    },
    "emotion_distribution": {
      "Phẫn nộ": {
        "count": 299,
        "percent": "1.2%"
      },
      "Cà khịa": {
        "count": 814,
        "percent": "3.4%"
      },
      "Đồng cảm": {
        "count": 58,
        "percent": "0.2%"
      },
      "Ủng hộ": {
        "count": 33,
        "percent": "0.1%"
      },
      "Trung lập": {
        "count": 23048,
        "percent": "95.0%"
      }
    },
    "top_events_by_comments": [
      {
        "id_content": "showbiz_001",
        "ten_su_kien": "Ồn ào phát ngôn của nghệ sĩ trong talkshow",
        "time_event": "2025-05-01",
        "total": 1500,
        "clean": 1200,
        "trash": 300
      },
      {
        "id_content": "showbiz_002",
        "ten_su_kien": "Nghi vấn đạo nhạc trong MV mới phát hành",
        "time_event": "2025-04-28",
        "total": 980,
        "clean": 750,
        "trash": 230
      }
    ],
    "events_by_year": {
      "2024": 5,
      "2025": 40
    }
  }
};
