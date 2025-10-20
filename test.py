import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Error
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from threading import Thread
import asyncio
import cloudscraper
import re
from urllib.parse import urljoin
import time
def resolve_bing_redirect(url: str) -> str:
    """
    Nhận vào 1 URL (thường là của Bing redirect), 
    trả về URL thật nếu phát hiện được, 
    còn nếu không thì trả về chính URL gốc.
    """
    scraper = cloudscraper.create_scraper(
        browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False}
    )
    
    try:
        response = scraper.get(url, timeout=10)
        html = response.text
        
        # Tìm đường dẫn thực trong JavaScript: var u = "https://..."
        match = re.search(r'var\s+u\s*=\s*"([^"]+)"', html)
        if match:
            real_url = match.group(1)
            print(f"🔗 Đã phát hiện redirect Bing → {real_url}")
            return real_url
        
        # Nếu không có, thử xem có thẻ meta refresh
        match_meta = re.search(r'<meta[^>]*url=([^">]+)', html, re.IGNORECASE)
        if match_meta:
            real_url = match_meta.group(1)
            print(f"🔗 Đã phát hiện redirect meta → {real_url}")
            return real_url
        
        print("⚠️ Không phát hiện redirect, dùng URL gốc.")
        return url

    except Exception as e:
        print(f"❌ Lỗi khi kiểm tra Bing redirect: {e}")
        return url
    
def bing_search(content, page=3):
    response = requests.get("https://bing.com")
    # print(f"Bing status: {response.status_code}")
    headers = response.headers
    data_response = []
    headers = {
    "Cookie": headers['Set-Cookie']
}

    for i in range(page):
        start = i * 10 + 1
        url = f'https://www.bing.com/search?q="{content}"&first={start}&cc=VN&setlang=vi'
        
        # Gửi request với cloudscraper
        response = requests.get(url,headers=headers)
        raw_text = response.text

        soup = BeautifulSoup(raw_text, 'html.parser')
        ol_element = soup.find("ol", id="b_results")
        if not ol_element:
            continue

        li_elements = ol_element.find_all("li", class_=["b_algo", "b_algo b_vtl_deeplinks qbrs"])
        
        for li in li_elements:
            h2 = li.find("h2")
            if not h2 or not h2.find("a"):
                continue
            title = h2.get_text(strip=True)
            href = h2.find("a")["href"]

            desc_tag = li.find("p", class_="b_lineclamp2")
            description = desc_tag.get_text(strip=True) if desc_tag else ""
            data_ = {
                "title": title,
                "description": description,
                "link": resolve_bing_redirect(href)
            }
            print(data_)
            data_response.append(data_)
    # print(data_response)
    return data_response

async def crawl_page(url: str, timeout_each=5000):
    """Crawl 1 trang web, giới hạn riêng cho page.goto."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            # 1️⃣ Đi đến trang, chờ DOM sẵn sàng
            response = await page.goto(url, timeout=timeout_each, wait_until="load")

            status = response.status if response else None
            print(f"📡 HTTP status: {status}")

            # 2️⃣ Nếu thành công -> lấy HTML
            if status in [200, 201,204]:
                html = await page.content()
                html = BeautifulSoup(html,'html.parser')
                imgs_attr = []
                imgs = html.find_all("img")
                
                for img in imgs:
                    src = img.get("src")
                    alt = img.get("alt")

                    # ✅ Chuyển link tương đối thành tuyệt đối
                    if src:
                        src = urljoin(url, src)

                    imgs_attr.append({"src": src, "alt": alt})
                raw_text = html.text
                html = re.sub(r"\n", "", raw_text)
                return html, imgs_attr
            else:
                return "", []

        except PlaywrightTimeoutError:
            print("⏰ Timeout nội bộ (page.goto) — thử lấy HTML hiện có...")

            try:
                # ⏳ Đợi 0.5s để trang ổn định trước khi lấy content
                await asyncio.sleep(0.5)
                html = await page.content()
            except Error:
                print("⚠️ Trang đang chuyển hướng, đợi thêm rồi thử lại lần 2...")
                await asyncio.sleep(1)
                try:
                    html = await page.content()
                except Error:
                    print("❌ Không thể lấy HTML, bỏ qua trang này.")
                    return "", []

            # ✅ Tiếp tục xử lý HTML nếu lấy được
            html = BeautifulSoup(html, 'html.parser')
            imgs_attr = []
            imgs = html.find_all("img")
            for img in imgs:
                src = img.get("src")
                alt = img.get("alt")
                if src:
                    src = urljoin(url, src)
                imgs_attr.append({"src": src, "alt": alt})
            raw_text = html.text
            html = re.sub(r"\n", "", raw_text)
            return html, imgs_attr
        except:
            print(f"Crawl thất bại")
            return "", []
        finally:
            # Đảm bảo browser luôn được đóng, kể cả khi timeout tổng thể
            await browser.close()


async def crawl_with_total_timeout(url, total_timeout=10):
    print(f"Đang crawl {url}")
    start_time = time.perf_counter()  # ⏱ Bắt đầu đếm
    """Giới hạn tổng thời gian crawl toàn bộ."""
    try:
        # Dùng asyncio.wait_for để giới hạn tổng thời gian
        html, info = await asyncio.wait_for(crawl_page(url), timeout=total_timeout)
        elapsed = time.perf_counter() - start_time  # ⏱ Thời gian đã trôi qua
        print(f"✅ Hoàn tất trong {elapsed:.2f} giây.")
        return html, info

    except asyncio.TimeoutError:
        print("⏰ Timeout tổng thể! Quá 6 giây rồi.")
        elapsed = time.perf_counter() - start_time  # ⏱ Thời gian đã trôi qua
        print(f"✅ Hoàn tất trong {elapsed:.2f} giây .")
        return "", []

# html, imgs = asyncio.run(crawl_with_total_timeout("https://caodang.fpt.edu.vn/"))
# print(html)
# print(imgs)

async def crawl_list_urls(urls):
    results = []
    for u in urls:
        html, imgs = await crawl_with_total_timeout(u["url"], total_timeout=10)
        results.append({"html": html, "imgs_attr": imgs})
    return results

