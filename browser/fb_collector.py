"""
fb_collector.py — v3 Batch Mode

Luồng hoạt động:
  1. Đọc groups.json, chia groups theo "batch" (1 hoặc 2)
  2. Quét Batch 1 (Group 1-3) → trả về posts ngay
  3. Main loop gửi Telegram cho Batch 1
  4. Nghỉ BATCH_PAUSE_SECONDS (60s)
  5. Quét Batch 2 (Group 4-6) → trả về posts
  6. Main loop gửi Telegram cho Batch 2
  7. Nghỉ hết INTERVAL rồi lặp lại

collect_from_facebook() vẫn trả về list[dict] như cũ.
collect_by_batch() trả về {batch_num: list[dict]} để main_auto dùng batch mode.
"""

import re
import time
import random
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
import cloakbrowser

# ===================== CẤU HÌNH =====================
PROFILE_DIR        = Path("data/cloak_profile").resolve()
GROUP_CONFIG       = json.loads(Path("config/groups.json").read_text(encoding="utf-8"))
GROUPS             = [g for g in GROUP_CONFIG["groups"] if g.get("enabled")]
BATCH_PAUSE        = int(GROUP_CONFIG.get("batch_pause_seconds", 60))

SCROLL_TIMES       = 5
SCROLL_PAUSE       = 2.8
PAGE_TIMEOUT       = 45_000
HEADLESS           = False
NAV_RETRIES        = 3
GROUP_DELAY_MIN    = 8
GROUP_DELAY_MAX    = 15
HOME_URL           = "https://www.facebook.com"
# ====================================================


def _safe_text(el) -> str:
    try:
        return el.inner_text(timeout=2500).strip()
    except Exception:
        return ""


def _extract_post_id(url: str) -> str:
    for pattern in [r'/posts/(\d+)', r'story_fbid=(\d+)', r'/permalink/(\d+)', r'multi_permalinks=(\d+)']:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return hashlib.md5(url.encode()).hexdigest()[:16]


def _is_on_group_page(page, expected_url: str) -> bool:
    current = page.url
    m = re.search(r'/groups/([^/?#]+)', expected_url)
    if not m:
        return False
    group_id = m.group(1)
    if group_id not in current:
        print(f"  ⚠️ URL sai! Mong đợi group/{group_id}, đang ở: {current[:80]}")
        return False
    return True


def _recover_to_group(page, url: str) -> bool:
    print(f"  🔄 Đang recover về group: {url}")
    try:
        page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        time.sleep(4)
        if _is_on_group_page(page, url):
            print("  ✅ Recover thành công")
            return True
        print(f"  ❌ Recover thất bại, vẫn ở: {page.url[:80]}")
        return False
    except Exception as e:
        print(f"  ❌ Lỗi recover: {e}")
        return False


def _navigate_to_group(page, url: str, name: str) -> bool:
    # Ưu tiên mở thẳng chronological để tránh click filter bị redirect
    chrono_url = url.rstrip("/")
    if "sorting_setting=" not in chrono_url:
        sep = "&" if "?" in chrono_url else "?"
        chrono_url = f"{chrono_url}{sep}sorting_setting=CHRONOLOGICAL"

    for attempt in range(1, NAV_RETRIES + 1):
        try:
            target = chrono_url if attempt == 1 else url
            print(f"  → Navigate lần {attempt}: {target}")
            page.goto(target, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(3.5)
            if _is_on_group_page(page, url):
                print(f"  ✅ Đang đúng trang group: {name}")
                return True
            print(f"  ⚠️ Bị redirect (lần {attempt}), đang ở: {page.url[:80]}")
            if attempt < NAV_RETRIES:
                delay = 5 * attempt
                print(f"  → Thử lại sau {delay}s...")
                time.sleep(delay)
        except Exception as e:
            print(f"  ⚠️ Lỗi navigate lần {attempt}: {e}")
            if attempt < NAV_RETRIES:
                time.sleep(5)
    print(f"  ❌ Không vào được group {name} sau {NAV_RETRIES} lần thử — bỏ qua")
    return False


def _click_newest_filter(page, group_url: str) -> bool:
    if not _is_on_group_page(page, group_url):
        print("  ⚠️ Không click filter vì đang sai trang")
        return False

    TARGET_TEXTS = ["Bài viết mới", "Hiển thị bài viết gần đây đầu tiên"]

    try:
        opened = False
        for sel in [
            'div[role="button"]:has-text("Phù hợp nhất")',
            'h2:has-text("Phù hợp nhất")',
            'span:has-text("Phù hợp nhất")',
            'div[aria-haspopup="dialog"]',
        ]:
            try:
                btn = page.query_selector(sel)
                if btn and btn.is_visible():
                    btn.click(timeout=2500)
                    time.sleep(1.5)
                    opened = True
                    print("  → Đã mở menu sắp xếp")
                    break
            except Exception:
                continue

        if not opened:
            try:
                page.get_by_text("Phù hợp nhất", exact=False).first.click(timeout=2000)
                time.sleep(1.5)
                print("  → Đã mở menu (fallback)")
            except Exception:
                print("  ⚠️ Không mở được menu sắp xếp")
                return False

        selected = False
        for text in TARGET_TEXTS:
            try:
                option = page.get_by_text(text, exact=False).first
                if option and option.is_visible():
                    option.click(timeout=2000)
                    print(f"  ✅ Đã chọn: {text}")
                    time.sleep(4)
                    selected = True
                    break
            except Exception:
                pass

        if not selected:
            try:
                items = page.query_selector_all('div[role="menuitemradio"]')
                for item in items:
                    t = _safe_text(item)
                    if "Bài viết mới" in t:
                        item.click()
                        print("  ✅ Đã chọn (menuitemradio): Bài viết mới")
                        time.sleep(4)
                        selected = True
                        break
            except Exception:
                pass

        if not selected:
            print("  ⚠️ Không tìm thấy option 'Bài viết mới'")
            return False

        if not _is_on_group_page(page, group_url):
            print("  ⚠️ Click filter bị redirect — đang recover...")
            recovered = _recover_to_group(page, group_url)
            if not recovered:
                return False
            print("  ℹ️ Đã recover — tiếp tục không có filter")

        return True

    except Exception as e:
        print(f"  ⚠️ Lỗi click newest: {e}")
        return False


def _parse_posts(page, group_name: str) -> list[dict]:
    posts = []

    try:
        page.evaluate("""
            () => {
                document.querySelectorAll('div[role="article"]').forEach(el => {
                    el.scrollIntoView({behavior: 'instant', block: 'center'});
                });
                document.querySelectorAll('div[role="button"]').forEach(btn => {
                    const t = (btn.innerText || '').trim();
                    if (t === 'Xem thêm' || t === 'See more') {
                        try { btn.click(); } catch(e) {}
                    }
                });
            }
        """)
        time.sleep(1.8)
    except Exception:
        pass

    elements = page.query_selector_all('div[role="article"]')
    print(f"  [DEBUG] div[role=\"article\"]: {len(elements)} elements")

    for idx, el in enumerate(elements):
        try:
            text = page.evaluate("(el) => el.innerText || el.textContent || ''", el)
            text = (text or "").strip()

            if len(text) < 20:
                try:
                    text = page.evaluate("""
                        (el) => {
                            const nodes = el.querySelectorAll('div[dir="auto"], span[dir="auto"]');
                            let best = '';
                            nodes.forEach(n => {
                                const t = (n.innerText || n.textContent || '').trim();
                                if (t.length > best.length) best = t;
                            });
                            return best;
                        }
                    """, el)
                    text = (text or "").strip()
                except Exception:
                    pass

            ui_noise = [
                "Theo dõi", "Bày tỏ cảm xúc", "Thích", "Bình luận",
                "Trả lời", "Chia sẻ", "Xem thêm", "See more",
                "Phù hợp nhất", "Facebook", "Tác giả"
            ]
            clean = text
            for n in ui_noise:
                clean = clean.replace(n, " ")
            clean = re.sub(r"\s+", " ", clean).strip()

            print(f"  [DEBUG] Article {idx+1}: raw_len={len(text)} | clean_len={len(clean)} | preview: {clean[:90]!r}")

            if len(clean) < 25:
                print("       → Bỏ vì nội dung quá ngắn")
                continue

            # Chỉ bỏ comment rất ngắn; bài >=40 ký tự giữ lại để filter score quyết định
            is_likely_comment = (
                len(clean) < 40 and
                any(w in clean.lower() for w in ["ib", "check tin", "rep ", "còn ko", "xin gia", "inb mik", "liên hệ mình"])
            )
            if is_likely_comment:
                print("       → Bỏ vì nghi là comment ngắn")
                continue

            post_url = page.url
            post_id = None
            try:
                href = page.evaluate("""
                    (el) => {
                        const links = el.querySelectorAll(
                            'a[href*="/posts/"], a[href*="story_fbid"], a[href*="/permalink/"], a[href*="multi_permalinks"]'
                        );
                        for (const a of links) {
                            const h = a.href || '';
                            if (h.includes('/posts/') || h.includes('story_fbid') || h.includes('/permalink/'))
                                return h;
                        }
                        return '';
                    }
                """, el)
                if href:
                    post_url = href.split("?")[0]
                    post_id = _extract_post_id(post_url)
            except Exception:
                pass

            if not post_id:
                post_id = hashlib.md5((group_name + clean[:180]).encode()).hexdigest()[:16]

            posts.append({
                "post_id":    post_id,
                "group":      group_name,
                "text":       clean[:2500],
                "url":        post_url,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            print(f"       → ✅ Giữ lại (post_id={post_id})")

        except Exception as e:
            print(f"  [DEBUG] Lỗi parse element {idx}: {e}")
            continue

    seen, unique = set(), []
    for p in posts:
        if p["post_id"] not in seen:
            seen.add(p["post_id"])
            unique.append(p)

    print(f"  [DEBUG] Parsed posts: {len(unique)}")
    return unique


def _context_alive(context) -> bool:
    """True nếu browser context vẫn mở."""
    try:
        _ = context.pages  # truy cập thuộc tính — sẽ lỗi nếu đã đóng
        return True
    except Exception:
        return False


def _scrape_groups(context, groups: list[dict]) -> list[dict]:
    """
    Scrape một danh sách group, trả về tất cả posts thu được.
    Dùng 1 page dùng chung trong batch để tránh TargetClosedError
    khi mở quá nhiều tab / context bị đóng giữa chừng.
    """
    all_posts = []
    page = None

    try:
        if not _context_alive(context):
            print("[ERROR] Browser context đã đóng trước khi scrape batch")
            return all_posts
        page = context.new_page()
    except Exception as e:
        print(f"[ERROR] Không tạo được page: {e}")
        return all_posts

    try:
        for idx, group in enumerate(groups):
            name = group["name"]
            url  = group["url"]
            print(f"\n[INFO] Quét group: {name}")

            if idx > 0:
                delay = random.uniform(GROUP_DELAY_MIN, GROUP_DELAY_MAX)
                print(f"  ⏳ Nghỉ {delay:.1f}s trước khi sang group tiếp...")
                time.sleep(delay)

            # Context chết giữa chừng → dừng batch, không crash cycle
            if not _context_alive(context):
                print(f"[ERROR] Context đã đóng trước group {name} — dừng batch")
                break

            # Page chết → mở lại trên cùng context
            try:
                _ = page.url
            except Exception:
                print("  ⚠️ Page đã đóng — tạo page mới...")
                try:
                    page = context.new_page()
                except Exception as e:
                    print(f"  ❌ Không tạo lại được page: {e}")
                    break

            try:
                ok = _navigate_to_group(page, url, name)
                if not ok:
                    continue

                # Chỉ click filter UI nếu chưa ở chế độ chronological (tránh redirect)
                if "sorting_setting=CHRONOLOGICAL" not in page.url:
                    _click_newest_filter(page, url)
                else:
                    print("  ℹ️ Đã ở CHRONOLOGICAL — bỏ qua click filter UI")

                for i in range(SCROLL_TIMES):
                    if i > 0 and i % 3 == 0:
                        if not _is_on_group_page(page, url):
                            print(f"  ⚠️ Bị redirect giữa chừng lúc cuộn {i+1} — thử recover...")
                            recovered = _recover_to_group(page, url)
                            if not recovered:
                                print("  ❌ Không recover được — dừng cuộn group này")
                                break
                            print(f"  ✅ Đã recover, tiếp tục cuộn từ {i+1}")
                    try:
                        page.evaluate("window.scrollBy(0, window.innerHeight * 2.2)")
                    except Exception as e:
                        print(f"  ⚠️ Lỗi scroll: {e}")
                        break
                    time.sleep(SCROLL_PAUSE)
                    print(f"  Cuộn {i+1}/{SCROLL_TIMES}...")

                try:
                    print(f"  [DEBUG] URL cuối: {page.url}")
                    print(f"  [DEBUG] Title: {page.title()}")
                except Exception:
                    print("  ⚠️ Không đọc được URL/Title (page/context đóng?)")
                    continue

                if not _is_on_group_page(page, url):
                    print(f"  ❌ URL sai sau cuộn — bỏ qua parse group {name}")
                    continue

                posts = _parse_posts(page, name)
                print(f"  → Thu được {len(posts)} bài từ {name}")
                all_posts.extend(posts)

            except Exception as e:
                print(f"[WARN] Lỗi group {name}: {e}")
                # Nếu context chết thì dừng luôn
                if not _context_alive(context):
                    print("[ERROR] Context đã đóng sau lỗi — dừng batch")
                    break
                continue
    finally:
        if page is not None:
            try:
                page.close()
            except Exception:
                pass

    return all_posts


def _launch_context():
    """Mở persistent browser context (cloak)."""
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return cloakbrowser.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=HEADLESS,
        args=["--disable-notifications"],
    )


def _ensure_logged_in(context) -> bool:
    """True nếu đã login Facebook."""
    try:
        page = context.new_page()
        page.goto(HOME_URL, timeout=PAGE_TIMEOUT)
        time.sleep(3)
        url = page.url or ""
        page.close()
        if "login" in url or "checkpoint" in url:
            print("[ERROR] Chưa đăng nhập. Chạy browser/cloak_session.py trước.")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] Không kiểm tra được login: {e}")
        return False


def collect_by_batch() -> dict[int, list[dict]]:
    """
    Scrape theo batch:
      - Mỗi batch mở context riêng (tránh context chết sau pause 60s)
      - Batch 1 → nghỉ → Batch 2
    Trả về {1: [...], 2: [...]}
    """
    batches: dict[int, list] = defaultdict(list)
    for g in GROUPS:
        batch_num = int(g.get("batch", 1))
        batches[batch_num].append(g)

    result: dict[int, list[dict]] = {}
    sorted_batches = sorted(batches.keys())

    for batch_num in sorted_batches:
        groups_in_batch = batches[batch_num]
        print(f"\n{'='*60}")
        print(f"[BATCH {batch_num}] Bắt đầu — {len(groups_in_batch)} group: "
              f"{[g['name'] for g in groups_in_batch]}")
        print(f"{'='*60}")

        context = None
        try:
            context = _launch_context()
            if not _ensure_logged_in(context):
                result[batch_num] = []
                try:
                    context.close()
                except Exception:
                    pass
                continue

            posts = _scrape_groups(context, groups_in_batch)
            result[batch_num] = posts
            print(f"\n[BATCH {batch_num}] Xong — thu được {len(posts)} bài")
        except Exception as e:
            print(f"[ERROR] Batch {batch_num} failed: {e}")
            result[batch_num] = result.get(batch_num, [])
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception:
                    pass

        # Nghỉ giữa batch (trừ batch cuối) — context đã đóng, không sợ chết giữa chừng
        if batch_num != sorted_batches[-1]:
            print(f"\n⏸️  Nghỉ {BATCH_PAUSE}s giữa batch {batch_num} và batch {batch_num + 1}...")
            time.sleep(BATCH_PAUSE)

    total = sum(len(v) for v in result.values())
    print(f"\n[INFO] Tổng: {total} bài từ {len(GROUPS)} group ({len(sorted_batches)} batch)")
    return result


def collect_from_facebook() -> list[dict]:
    """Wrapper tương thích ngược — gộp tất cả batch thành 1 list."""
    batched = collect_by_batch()
    all_posts = []
    for posts in batched.values():
        all_posts.extend(posts)
    return all_posts


if __name__ == "__main__":
    batched = collect_by_batch()
    for batch_num, posts in batched.items():
        print(f"\n=== BATCH {batch_num}: {len(posts)} bài ===")
        for p in posts[:3]:
            print(f"  ID  : {p['post_id']}")
            print(f"  Text: {p['text'][:150]}")
            print(f"  URL : {p['url']}")
