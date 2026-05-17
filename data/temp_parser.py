import re
import json

import os

def parse_txt():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    input_file = os.path.join(base_dir, "keyword_analysis_v4.txt")
    output_file = os.path.join(base_dir, "keyword_analysis_v4.json")
    
    with open(input_file, "r", encoding="utf-8") as f:
        text = f.read()

    categories = {}
    current_category = None

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "TOP 10 TỪ/CỤM TỪ —" in line:
            current_category = line.split("—")[1].split("(")[0].strip()
            categories[current_category] = []
        
        match = re.match(r'\d+\.\s+"([^"]+)"\s+\[(.*?)\]', line)
        if match and current_category:
            keyword = match.group(1)
            ngram_type = match.group(2)
            
            i += 1
            stats_line = lines[i].strip()
            stats_match = re.search(r'Tổng: (\d+) lần \| (\d+) bài \| PMI: ([\d.]+) \| Score: ([\d.]+)', stats_line)
            if stats_match:
                total_freq = int(stats_match.group(1))
                total_articles = int(stats_match.group(2))
                pmi = float(stats_match.group(3))
                score = float(stats_match.group(4))
                
                i += 1
                details_line = lines[i].strip()
                details = {}
                if "Chi tiết: [" in details_line:
                    details_str = details_line.replace("Chi tiết: [", "").replace("]", "")
                    for part in details_str.split(", "):
                        if ":" in part:
                            article_id, count = part.split(":")
                            details[article_id.strip()] = int(count.strip())
                
                categories[current_category].append({
                    "keyword": keyword,
                    "ngram_type": ngram_type,
                    "total_frequency": total_freq,
                    "total_articles": total_articles,
                    "pmi_score": pmi,
                    "score": score,
                    "details": details
                })
        i += 1

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=4)

if __name__ == "__main__":
    parse_txt()