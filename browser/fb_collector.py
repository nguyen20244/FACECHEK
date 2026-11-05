"""
fb_collector.py
CloakBrowser tự động chuyển sang "Bài viết mới" rồi cuộn lấy bài.

FIX mới (rate limit):
  #A - Delay ngẫu nhiên 8-15s giữa các group để tránh bị block
  #B - Khi bị redirect về home, navigate thẳng lại vào group (không bỏ qua)
  #C - Nếu "Bài viết mới" trigger redirect home, navigate lại trước khi cuộn
  #D - Tăng delay sau click filter lên 4s
"""

import re
import time
import random
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
import cloakbrowser

# ===================== CẤU HÌNH =====================
PROFILE_DIR   = Path("data/cloak_profile").resolve()
GROUP_CONFIG  = json.loads(Path("config/groups.json").read_text(encoding="utf-8"))
GROUPS        = [g for g in GROUP_CONFIG["groups"] if g.get("enabled")]

SCROLL_TIMES      = 8
SCROLL_PAUSE      = 2.8
PAGE_TIMEOUT      = 45_000
HEADLESS          = False
NAV_RETRIES       = 3        # số lần retry navigate
GROUP_DELAY_MIN   = 8        # FIX #A: delay tối thiểu giữa group (giây)
GROUP_DELAY_MAX   = 15       # FIX #A: delay tối đa giữa group (giây)
HOME_URL          = "https://www.facebook.com"
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
    """
    FIX #B: Khi bị redirect về home, navigate thẳng lại vào group.
    Trả về True nếu recover thành công.
    """
    print(f"  🔄 Đang recover về group: {url}")
    try:
        page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        time.sleep(4)
        if _is_on_group_page(page, url):
            print(f"  ✅ Recover thành công")
            return True
        print(f"  ❌ Recover thất bại, vẫn ở: {page.url[:80]}")
        return False
    except Exception as e:
        print(f"  ❌ Lỗi recover: {e}")
        return False


def _navigate_to_group(page, url: str, name: str) -> bool:
    """Navigate đến group, retry nếu bị redirect."""
    for attempt in range(1, NAV_RETRIES + 1):
        try:
            print(f"  → Navigate lần {attempt}: {url}")
            page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(3.5)

            if _is_on_group_page(page, url):
                print(f"  ✅ Đang đúng trang group: {name}")
                return True

            print(f"  ⚠️ Bị redirect (lần {attempt}), đang ở: {page.url[:80]}")
            if attempt < NAV_RETRIES:
                delay = 5 * attempt  # tăng dần: 5s, 10s
                print(f"  → Thử lại sau {delay}s...")
                time.sleep(delay)

        except Exception as e:
            print(f"  ⚠️ Lỗi navigate lần {attempt}: {e}")
            if attempt < NAV_RETRIES:
                time.sleep(5)

    print(f"  ❌ Không vào được group {name} sau {NAV_RETRIES} lần thử — bỏ qua")
    return False


def _click_newest_filter(page, group_url: str) -> bool:
    """
    Chuyển sang Bài viết mới.
    FIX #C: Nếu click filter gây redirect home → recover lại trước khi return.
    """
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

        # Chọn "Bài viết mới"
        selected = False
        for text in TARGET_TEXTS:
            try:
                option = page.get_by_text(text, exact=False).first
                if option and option.is_visible():
                    option.click(timeout=2000)
                    print(f"  ✅ Đã chọn: {text}")
                    time.sleep(4)  # FIX #D: tăng từ 2.8s lên 4s
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
                        time.sleep(4)  # FIX #D
                        selected = True
                        break
            except Exception:
                pass

        if not selected:
            print("  ⚠️ Không tìm thấy option 'Bài viết mới'")
            return False

        # FIX #C: Sau khi click filter, kiểm tra có bị redirect không
        if not _is_on_group_page(page, group_url):
            print("  ⚠️ Click filter bị redirect về home — đang recover...")
            recovered = _recover_to_group(page, group_url)
            if not recovered:
                return False
            print("  ℹ️ Đã recover — tiếp tục cuộn (không có filter Bài viết mới)")

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

            if len(clean) < 30:
                print(f"       → Bỏ vì nội dung quá ngắn")
                continue

            is_likely_comment = (
                len(clean) < 45 and
                any(w in clean.lower() for w in ["ib", "check tin", "rep ", "còn ko", "xin gia"])
            )
            if is_likely_comment:
                print(f"       → Bỏ vì nghi là comment ngắn")
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


def collect_from_facebook() -> list[dict]:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    all_posts = []

    context = cloakbrowser.launch_persistent_context(
        user_data_dir=str(PROFILE_DIR),
        headless=HEADLESS,
        args=["--disable-notifications"],
    )

    try:
        # Kiểm tra login
        check_page = context.new_page()
        check_page.goto(HOME_URL, timeout=PAGE_TIMEOUT)
        time.sleep(3)
        if "login" in check_page.url or "checkpoint" in check_page.url:
            print("[ERROR] Chưa đăng nhập. Chạy browser/cloak_session.py trước.")
            check_page.close()
            context.close()
            return []
        check_page.close()

        for idx, group in enumerate(GROUPS):
            name = group["name"]
            url  = group["url"]
            print(f"\n[INFO] Quét group: {name}")

            # FIX #A: Delay ngẫu nhiên giữa các group (trừ group đầu)
            if idx > 0:
                delay = random.uniform(GROUP_DELAY_MIN, GROUP_DELAY_MAX)
                print(f"  ⏳ Nghỉ {delay:.1f}s trước khi sang group tiếp theo...")
                time.sleep(delay)

            page = context.new_page()
            try:
                ok = _navigate_to_group(page, url, name)
                if not ok:
                    page.close()
                    continue

                _click_newest_filter(page, url)

                # Cuộn — recover nếu bị redirect giữa chừng
                for i in range(SCROLL_TIMES):
                    if i > 0 and i % 3 == 0:
                        if not _is_on_group_page(page, url):
                            print(f"  ⚠️ Bị redirect giữa chừng lúc cuộn {i+1} — thử recover...")
                            # FIX #B: Thử recover thay vì bỏ qua ngay
                            recovered = _recover_to_group(page, url)
                            if not recovered:
                                print(f"  ❌ Không recover được — dừng cuộn group này")
                                break
                            print(f"  ✅ Đã recover, tiếp tục cuộn từ vị trí {i+1}")

                    page.evaluate("window.scrollBy(0, window.innerHeight * 2.2)")
                    time.sleep(SCROLL_PAUSE)
                    print(f"  Cuộn {i+1}/{SCROLL_TIMES}...")

                print(f"  [DEBUG] URL cuối: {page.url}")
                print(f"  [DEBUG] Title: {page.title()}")

                if not _is_on_group_page(page, url):
                    print(f"  ❌ URL sai sau cuộn — bỏ qua parse group {name}")
                    page.close()
                    continue

                posts = _parse_posts(page, name)
                print(f"  → Thu được {len(posts)} bài từ {name}")
                all_posts.extend(posts)

            except Exception as e:
                print(f"[WARN] Lỗi group {name}: {e}")
            finally:
                try:
                    page.close()
                except Exception:
                    pass

    finally:
        try:
            context.close()
        except Exception:
            pass

    print(f"\n[INFO] Tổng: {len(all_posts)} bài từ {len(GROUPS)} group")
    return all_posts


if __name__ == "__main__":
    posts = collect_from_facebook()
    print("\n=== 5 BÀI ĐẦU ===")
    for p in posts[:5]:
        print(f"\nID  : {p['post_id']}")
        print(f"Text: {p['text'][:200]}")
        print(f"URL : {p['url']}")
