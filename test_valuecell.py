from playwright.sync_api import sync_playwright

BASE_URL = "https://valuecell.ai"
PROFILE_DIR = "./sessions/valuecell_profile"

with sync_playwright() as p:
    context = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE_DIR,
        headless=False,
    )
    page = context.new_page()
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    print("当前页面标题：", page.title())
    print("当前页面 URL：", page.url)
    page.screenshot(path="./screenshots/valuecell_homepage_test.png", full_page=True)
    input("浏览器已打开，按回车退出...")
    context.close()
