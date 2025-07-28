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

from django.db import transaction
from fins.models import Fin, Sector 
from parsers.models import ParseFins

from parsers.fin_updater import update_fin_from_kdfo

def safe_date(value):
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except Exception:
        return None
    
def safe_int(value):
    try:
        return int(value)
    except Exception:
        return 0

def parse_date(val):
    if pd.isna(val):
        return None
    if isinstance(val, datetime):
        return val.date()
    try:
        return datetime.strptime(str(val), "%d.%m.%Y").date()
    except Exception:
        return None


def parse_rcb_from_govkz():
    start_time = datetime.now()
    try:
        options = Options()
        options.add_argument('--user-agent=Mozilla/5.0')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-ipv6')
        tmp_profile = tempfile.mkdtemp()
        options.add_argument(f"--user-data-dir={tmp_profile}")

        service = Service("/usr/bin/chromedriver")

        seleniumwire_options = {'verify_ssl': False}
        driver = webdriver.Chrome(service=service, options=options, seleniumwire_options=seleniumwire_options)

        try:
            url = "https://www.gov.kz/memleket/entities/ardfm/permissions-notifications/section/1/subsection/3/registry/29?lang=ru"
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

            # 💾 Сохраняем HTML-страницу
            html_source = driver.page_source
            html_path = os.path.join(os.path.dirname(__file__), "govkz_issued_page.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(html_source)
            print(f"💾 HTML сохранён: {html_path}")

            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()

            soup = BeautifulSoup(html, "html.parser")
            license_blocks = soup.select('.collapse__content__card')

            bin_list = []

            for block in license_blocks:
                rows = block.select("tr")
                for row in rows:
                    key_cell = row.select_one("th")
                    val_cell = row.select_one("td")
                    if key_cell and val_cell:
                        key = key_cell.get_text(strip=True)
                        value = val_cell.get_text(strip=True)
                        if "БИН" in key.upper():
                            bin_list.append(value)
                            break

            total = 0
            skipped = 0

            for bin_code in bin_list:
                try:
                    print(f"🔄 Обновление по БИНу: {bin_code}")
                    update_fin_from_kdfo(bin_code)

                    fin = Fin.objects.get(bin=bin_code)
                    sector = Sector.objects.get(name_sector="Рынок ценных бумаг")
                    fin.sector.add(sector)
                    fin.save(update_fields=["sector"])
                except Exception as e:
                    print(f"❌ Ошибка при обновлении {bin_code}: {e}")

            duration = datetime.now() - start_time

            # логирование результата
            ParseFins.objects.create(
                name="РЦБ",
                total_records=len(bin_list),
                new_records=total,
                skipped_records=skipped,
                duration=duration
            )
            return bin_list

        finally:
            driver.quit()
            shutil.rmtree(tmp_profile, ignore_errors=True)

    except Exception as e:
        ParseFins.objects.create(
            name="Реестр выданных, переоформленных лицензий на осуществление деятельности на рынке ценных бумаг",
            total_records=0,
            new_records=0,
            skipped_records=0,
            error=str(e),
            duration=datetime.now() - start_time
        )
        print(f"❌ Ошибка при выполнении парсера: {e}")

if __name__ == "__main__":
    parse_rcb_from_govkz()
