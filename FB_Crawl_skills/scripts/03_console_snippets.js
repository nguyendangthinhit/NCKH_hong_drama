/**
 * Facebook Scrape — JS Snippets cho DevTools Console
 *
 * Cách dùng:
 *   1. Mở post Facebook muốn scrape
 *   2. F12 → tab Console
 *   3. Paste snippet bên dưới vào console
 *   4. Nhấn Enter
 *   5. Kết quả sẽ in ra JSON trong console + tự download file
 *
 * ĐÃ TEST với cấu trúc DOM Facebook 2024-2026.
 * FB thay đổi DOM thường xuyên → có thể cần adjust selector nếu không work.
 */

// ============================================================
// SNIPPET 1: Extract comments từ post hiện tại
// ============================================================
(function extractComments() {
    console.log("🔍 Bắt đầu extract comments...");

    const results = [];
    const seen = new Set();

    // FB dùng [role="article"] cho mỗi comment block
    const articles = document.querySelectorAll('[role="article"]');

    console.log(`📦 Tìm thấy ${articles.length} articles`);

    articles.forEach((article, idx) => {
        try {
            // 1. Author — link đầu tiên trong article (thường là tên người comment)
            const authorLinks = article.querySelectorAll('a[href*="facebook.com/"], a[role="link"]');
            let author = null;
            let profileUrl = null;
            for (const link of authorLinks) {
                const txt = link.textContent.trim();
                // Skip empty, navigation links, "Xem thêm"
                if (txt && txt.length < 60 && !/^(Xem|View|Thêm|More|Reply|Trả lời)/i.test(txt)) {
                    author = txt;
                    profileUrl = link.href;
                    break;
                }
            }

            // 2. Comment text — div[dir="auto"] chứa text comment
            const textDivs = article.querySelectorAll('div[dir="auto"]');
            const textParts = [];
            textDivs.forEach(div => {
                const t = div.textContent.trim();
                if (t && t.length > 0 && t.length < 5000) {
                    textParts.push(t);
                }
            });
            // Comment text thường ở div[dir="auto"] đầu tiên hoặc thứ 2
            const text = textParts[0] || null;

            // 3. Timestamp — abbr hoặc link có href chứa "comment_id"
            const timeEl = article.querySelector('abbr, time, a[href*="comment_id"], a[href*="permalink"]');
            const timestamp = timeEl ? (timeEl.getAttribute('title') || timeEl.textContent.trim()) : null;

            // 4. Reactions count
            const reactEl = article.querySelector('[aria-label*="reaction"], [aria-label*="Reactions"]');
            const reactions = reactEl ? reactEl.getAttribute('aria-label') : null;

            // 5. Reply count
            const replyEl = Array.from(article.querySelectorAll('span, div'))
                .find(el => /\b(\d+)\s*(repl|trả lời|reply)/i.test(el.textContent));
            const replies = replyEl ? replyEl.textContent.trim() : null;

            // Skip nếu không có text hoặc author rõ ràng
            if (!text || text.length < 2) return;
            if (!author) return;

            // Dedupe
            const key = author + '|' + text.substring(0, 100);
            if (seen.has(key)) return;
            seen.add(key);

            results.push({
                idx: idx,
                author: author,
                profile_url: profileUrl,
                text: text.substring(0, 5000),
                timestamp: timestamp,
                reactions: reactions,
                replies: replies,
                scraped_at: new Date().toISOString(),
                post_url: window.location.href,
            });
        } catch (e) {
            console.warn(`Skip article ${idx}: ${e.message}`);
        }
    });

    console.log(`✅ Extracted ${results.length} comments`);

    // In JSON ra console
    console.log(JSON.stringify(results, null, 2));

    // Auto-download file
    const blob = new Blob([JSON.stringify(results, null, 2)], {type: 'application/json'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `fb_comments_${Date.now()}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    console.log(`💾 Downloaded: fb_comments_${Date.now()}.json`);
    console.log(`📋 Copy từ console output nếu download fail. Tổng: ${results.length} comments.`);

    return results;
})();


// ============================================================
// SNIPPET 2: Scroll xuống để load thêm comments (chạy trước snippet 1)
// ============================================================
// Paste riêng, đợi 5-10s rồi paste snippet 1
//
// (async function autoScroll() {
//     let prevHeight = 0;
//     let sameCount = 0;
//     for (let i = 0; i < 30; i++) {
//         window.scrollTo(0, document.body.scrollHeight);
//         await new Promise(r => setTimeout(r, 2000));
//         const newHeight = document.body.scrollHeight;
//         if (newHeight === prevHeight) {
//             sameCount++;
//             if (sameCount >= 3) break;  // 3 lần không đổi = hết
//         } else {
//             sameCount = 0;
//         }
//         prevHeight = newHeight;
//         console.log(`Scroll ${i+1}: ${newHeight}px`);
//     }
//     console.log("✓ Scroll done");
// })();


// ============================================================
// SNIPPET 3: Extract post content + comments (gộp cả post + comments)
// ============================================================
// (function extractPostAndComments() {
//     // Post content
//     const postContent = document.querySelector('[data-ad-preview="message"]') ||
//                         document.querySelector('div[dir="auto"][style*="text-align"]');
//
//     return {
//         post: {
//             text: postContent ? postContent.textContent.trim() : null,
//             url: window.location.href,
//             scraped_at: new Date().toISOString(),
//         },
//         comments: extractComments(),
//     };
// })();