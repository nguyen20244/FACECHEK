from pathlib import Path
import ast
import re
import shutil
import sys

TARGET = Path("browser/fb_collector.py")

CLICK_FUNCTION = r'''
def _click_newest_filter(page):
    # Avoid clicking broad Facebook controls automatically.
    # Scan the feed in its current order instead.
    print("  [DEBUG] Skip automatic newest-filter click.")
    return False
'''

PARSE_FUNCTION = r'''
def _parse_posts(page, group_name: str) -> list[dict]:
    # Requires the existing _safe_text() and _extract_post_id() helpers.
    from urllib.parse import urljoin
    import hashlib
    from datetime import datetime, timezone

    posts = []
    candidates = []
    selectors = (
        'div[role="article"]',
        'div[data-pagelet^="FeedUnit"]',
    )

    print(f"  [DEBUG] URL: {page.url}")
    try:
        print(f"  [DEBUG] Title: {page.title()}")
    except Exception:
        pass

    for selector in selectors:
        try:
            found = page.query_selector_all(selector)
            print(f"  [DEBUG] {selector}: {len(found)} elements")
            candidates.extend(found)
        except Exception as exc:
            print(f"  [DEBUG] Selector error ({selector}): {exc}")

    unique_candidates = []
    seen_text = set()

    for element in candidates:
        try:
            text = _safe_text(element)
            normalized = " ".join((text or "").split())
            if len(normalized) < 10 or normalized in seen_text:
                continue
            seen_text.add(normalized)
            unique_candidates.append((element, text))
        except Exception as exc:
            print(f"  [DEBUG] Candidate read error: {exc}")

    print(f"  [DEBUG] Unique candidate elements: {len(unique_candidates)}")

    for element, text in unique_candidates:
        try:
            post_url = ""
            try:
                links = element.query_selector_all(
                    'a[href*="/posts/"], '
                    'a[href*="story_fbid="], '
                    'a[href*="permalink.php"]'
                )
                for link in links:
                    href = link.get_attribute("href") or ""
                    if any(token in href for token in (
                        "/posts/", "story_fbid=", "permalink.php"
                    )):
                        post_url = urljoin(
                            "https://www.facebook.com/", href
                        ).split("?")[0]
                        break
            except Exception as exc:
                print(f"  [DEBUG] Permalink lookup error: {exc}")

            # Never use the group page URL as a unique post ID.
            if post_url:
                post_id = _extract_post_id(post_url)
            else:
                digest_input = f"{group_name}|{' '.join(text.split())}"
                post_id = hashlib.sha256(
                    digest_input.encode("utf-8")
                ).hexdigest()[:24]
                post_url = page.url

            created_at = datetime.now(timezone.utc).isoformat()
            posts.append({
                "post_id": post_id,
                "group": group_name,
                "text": text[:5000],
                "url": post_url,
                "created_at": created_at,
            })
            print(f"  [POST] {text[:120].replace(chr(10), ' ')}")
        except Exception as exc:
            print(f"  [DEBUG] Parse error: {exc}")

    result = []
    seen_ids = set()
    for post in posts:
        if post["post_id"] not in seen_ids:
            seen_ids.add(post["post_id"])
            result.append(post)

    print(f"  [DEBUG] Parsed posts: {len(result)}")
    return result
'''

def replace_function(source: str, name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ms)^def {re.escape(name)}\s*\(.*?(?=^def |\Z)"
    )
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise RuntimeError(
            f"Không tìm thấy duy nhất hàm {name}() trong {TARGET}. "
            f"Số kết quả: {len(matches)}"
        )
    match = matches[0]
    return source[:match.start()] + replacement.strip("\n") + "\n\n" + source[match.end():]

def main():
    if not TARGET.exists():
        print(f"Không tìm thấy {TARGET}.")
        print("Hãy chạy file này tại thư mục gốc FACECHEK.")
        sys.exit(1)

    source = TARGET.read_text(encoding="utf-8")
    source = replace_function(source, "_click_newest_filter", CLICK_FUNCTION)
    source = replace_function(source, "_parse_posts", PARSE_FUNCTION)

    ast.parse(source)  # Validate syntax before writing.

    backup = TARGET.with_suffix(".py.before_fix.bak")
    if not backup.exists():
        shutil.copy2(TARGET, backup)

    TARGET.write_text(source, encoding="utf-8")
    print("Đã cập nhật browser/fb_collector.py")
    print(f"Đã tạo bản sao lưu: {backup}")
    print("Đã kiểm tra cú pháp Python: OK")
    print()
    print("Chạy tiếp: python main_auto.py")

if __name__ == "__main__":
    main()
