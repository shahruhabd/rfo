import os
import time
import shutil
import tempfile
import requests
import pandas as pd
from io import BytesIO
from datetime import datetime
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from bs4 import BeautifulSoup
import json

import chromedriver_autoinstaller
chromedriver_autoinstaller.install()


def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    try:
        return datetime.strptime(str(val), "%d.%m.%Y").date()
    except Exception:
        return None


from selenium.common.exceptions import TimeoutException, ElementClickInterceptedException

def extract_excel_from_govkz():
    tmp_profile = tempfile.mkdtemp()
    options = Options()
    options.add_argument('--user-agent=Mozilla/5.0')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument(f'--user-data-dir={tmp_profile}')
    options.add_argument('--disable-ipv6')

    # service = Service("/usr/local/bin/chromedriver")  # укажи путь к chromedriver если надо
    seleniumwire_options = {'verify_ssl': False}
    driver = webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)

    try:
        url = "https://www.gov.kz/memleket/entities/ardfm/permissions-notifications/section/1/subsection/5/registry/19?lang=ru"
        driver.get(url)
        time.sleep(10)

        # 1) раскрываем все основные блоки
        main_buttons = driver.find_elements(By.CSS_SELECTOR, ".collapse__header")
        for btn in main_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                btn.click()
                time.sleep(0.2)
            except:
                pass


        content_divs = driver.find_elements(By.CSS_SELECTOR, ".collapse__content")

        for content_div in content_divs:
            # 2) раскрываем все вложенные секции Ant-Design
            inner_arrows = content_div.find_elements(By.CSS_SELECTOR, ".anticon-right.ant-collapse-arrow")
            if inner_arrows:
                print(f"🔍 Найдено {len(inner_arrows)} внутренних секций")
                for j, arrow in enumerate(inner_arrows):
                    try:
                        driver.execute_script("arguments[0].scrollIntoView(true);", arrow)
                        time.sleep(1)

                        driver.execute_script("arguments[0].click();", arrow)
                        time.sleep(2)
                    except:
                        pass


        # 👇 Принудительно раскрываем все внутренние ant-collapse через JS
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


        # 💾 Сохраняем HTML после раскрытия
        html_source = driver.page_source
        html_path = os.path.join(os.path.dirname(__file__), "govkz_issued_page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_source)
        print(f"💾 HTML сохранён: {html_path}")

        # Чтение и парсинг
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()

        soup = BeautifulSoup(html, "html.parser")
        license_blocks = soup.select('.collapse__content__card')
        parsed_data = []

        for block in license_blocks:
            record = {}
            org_name_div = block.find_parent(class_="collapse").select_one(".collapse__value")
            if org_name_div:
                record["name"] = org_name_div.get_text(strip=True)

            for row in block.select("tr.ant-descriptions-row"):
                key_cell = row.select_one("th")
                val_cell = row.select_one("td")
                if key_cell and val_cell:
                    key = key_cell.get_text(strip=True)
                    value = val_cell.get_text(strip=True)

                    if "БИН" in key:
                        record["bin"] = value
                    elif "Тип организации" in key:
                        record["organization_type"] = value
                    elif "Номер первичной лицензии" in key:
                        record["primary_license_number"] = value
                    elif "Дата первичной лицензии" in key:
                        record["primary_license_date"] = value
                    elif "Номер действующей лицензии" in key:
                        record["current_license_number"] = value
                    elif "Дата действующей лицензии" in key:
                        record["current_license_date"] = value
                    elif "Номер решения" in key:
                        record["decision_number"] = value
                    elif "Дата решения" in key:
                        record["decision_date"] = value
                    elif "в тенге" in key:
                        record["currency"] = value
                    elif "Количество" in key:
                        record["operations_count"] = value
                    elif "Банковские заемные операции" in key:
                        record["operations_description"] = key

                # поля переоформления из внутренней ant-table
                table = block.select_one(".ant-table-wrapper table")
                if table:
                    tds = table.select("tbody tr td.ant-table-cell")
                    # 0-й ячейка — всегда "Переоформление лицензии"
                    record["is_reissued"] = True
                    record["reissue_basis"]           = tds[1].get_text(strip=True)
                    record["reissue_reason"]          = tds[2].get_text(strip=True)
                    record["reissue_currency_type"]   = tds[3].get_text(strip=True)
                else:
                    record["is_reissued"] = False
                    record["reissue_basis"] = None
                    record["reissue_reason"] = None
                    record["reissue_currency_type"] = None

            parsed_data.append(record)

        return parsed_data

    finally:
        driver.quit()
        shutil.rmtree(tmp_profile, ignore_errors=True)



def parse_issued_licenses():
    parsed_data = extract_excel_from_govkz()
    if not parsed_data:
        print("❌ Не удалось получить данные.")
        return

    print(f"📄 Найдено записей: {len(parsed_data)}")

    for record in parsed_data:
        print(json.dumps(record, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parse_issued_licenses()
