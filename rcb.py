import os
import time
import json
from datetime import datetime
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
def parse_rcb_from_govkz():
    start_time = datetime.now()
    try:
        print("🚀 Инициализация Chrome...")
        options = Options()
        # options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')

        import chromedriver_autoinstaller
        chromedriver_autoinstaller.install()
        driver = webdriver.Chrome(options=options)

        try:
            url = "https://www.gov.kz/memleket/entities/ardfm/permissions-notifications/section/1/subsection/3/registry/29?lang=ru"
            print(f"🌐 Переход по ссылке: {url}")
            driver.get(url)
            time.sleep(20)

            print("🔘 Пробуем нажать кнопку cookies...")
            try:
                btn = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "button#onetrust-accept-btn-handler"))
                )
                btn.click()
                print("✅ Cookie-кнопка нажата")
            except Exception:
                print("⚠️ Cookie-кнопка не найдена или уже скрыта")

            print("🔽 Раскрытие основных блоков...")
            main_buttons = driver.find_elements(By.CSS_SELECTOR, ".collapse__header")
            print(f"🔹 Найдено {len(main_buttons)} верхних блоков")
            for btn in main_buttons:
                try:
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                    btn.click()
                    time.sleep(0.2)
                except:
                    print("⚠️ Ошибка при клике на основной блок")

            content_divs = driver.find_elements(By.CSS_SELECTOR, ".collapse__content")
            print(f"🔍 Проверка внутренних секций в {len(content_divs)} блоках")
            for content_div in content_divs:
                inner_arrows = content_div.find_elements(By.CSS_SELECTOR, ".anticon-right.ant-collapse-arrow")
                if inner_arrows:
                    print(f"🔸 Найдено {len(inner_arrows)} внутренних стрелок")
                    for j, arrow in enumerate(inner_arrows):
                        try:
                            driver.execute_script("arguments[0].scrollIntoView(true);", arrow)
                            time.sleep(1)
                            driver.execute_script("arguments[0].click();", arrow)
                            time.sleep(2)
                        except:
                            print(f"⚠️ Ошибка при раскрытии вложенного блока {j}")

            print("🧩 Принудительное раскрытие через JS")
            driver.execute_script("""
            document.querySelectorAll('.ant-collapse-item').forEach(item => {
                item.classList.add('ant-collapse-item-active');
            });
            document.querySelectorAll('.ant-collapse-content').forEach(content => {
                content.classList.remove('ant-collapse-content-inactive');
                content.classList.add('ant-collapse-content-active');
                content.style.display = 'block';
                content.style.height = 'auto';
            });
            """)
            time.sleep(1)

            html_source = driver.page_source
            html_path = os.path.join(os.path.dirname(__file__), "govkz_issued_page.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_source)
            print(f"💾 HTML сохранён: {html_path}")

            print("📄 Парсинг HTML через BeautifulSoup")
            soup = BeautifulSoup(html_source, "html.parser")
            license_blocks = soup.select('.collapse__content__card')
            print(f"📦 Найдено блоков лицензий: {len(license_blocks)}")

            all_licenses = []

            for i, block in enumerate(license_blocks):
                license_data = {}
                rows = block.select("tr")
                print(f"  └ Блок {i + 1}: {len(rows)} строк")
                for row in rows:
                    key_cell = row.select_one("th")
                    val_cell = row.select_one("td")
                    if key_cell and val_cell:
                        key = key_cell.get_text(strip=True)
                        val = val_cell.get_text(strip=True)
                        license_data[key] = val
                if license_data:
                    all_licenses.append(license_data)

            print(f"✅ Всего лицензий собрано: {len(all_licenses)}")
            print(json.dumps(all_licenses, ensure_ascii=False, indent=2))
            return all_licenses

        finally:
            driver.quit()
            print("🧹 Chrome закрыт")

    except Exception as e:
        print(f"❌ Ошибка при выполнении парсера: {e}")

if __name__ == "__main__":
    parse_rcb_from_govkz()
