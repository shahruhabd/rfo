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

    service = Service("chromedriver.exe")  # укажи путь к chromedriver если надо
    seleniumwire_options = {'verify_ssl': False}
    driver = webdriver.Chrome(service=service, options=options, seleniumwire_options=seleniumwire_options)

    try:
        url = "https://www.gov.kz/memleket/entities/ardfm/permissions-notifications/section/1/subsection/5/registry/19?lang=ru"
        driver.get(url)
        time.sleep(10)

        # 🔽 Раскрываем все блоки collapse, чтобы появились ant-table
        expand_buttons = driver.find_elements(By.CSS_SELECTOR, ".collapse__header")
        for btn in expand_buttons:
            try:
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn)
                time.sleep(0.3)
                btn.click()
                # ждём появления вложенной таблицы (если есть)
                WebDriverWait(driver, 3).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".ant-table-content"))
                )
            except (TimeoutException, ElementClickInterceptedException):
                print("⚠️ Не удалось раскрыть блок (возможно уже раскрыт или отсутствует таблица)")
            except Exception as e:
                print(f"❌ Ошибка при раскрытии: {e}")

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
