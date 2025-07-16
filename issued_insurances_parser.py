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

from django.db import transaction
from fins.models import Fin, IssuedLicense, LicenseReissue, LicenseType, OperationType, OrganizationTypeLicense, License

# from parsers.fin_updater import update_fin_from_kdfo

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


def extract_excel_from_govkz():
    options = Options()
    options.add_argument('--user-agent=Mozilla/5.0')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-ipv6')

    # service = Service("/usr/bin/chromedriver")

    seleniumwire_options = {'verify_ssl': False}
    driver = webdriver.Chrome(options=options, seleniumwire_options=seleniumwire_options)

    try:
        url = "https://www.gov.kz/memleket/entities/ardfm/permissions-notifications/section/1/subsection/8/registry/22?lang=ru"
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

        # 💾 Сохраняем HTML-страницу
        html_source = driver.page_source
        html_path = os.path.join(os.path.dirname(__file__), "govkz_issued_insurances_page.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_source)
        print(f"💾 HTML сохранён: {html_path}")

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

            for row in block.select("tr"):
                cells = row.select("td")
                if len(cells) == 2:
                    key = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)

                    if "БИН" in key:
                        record["bin"] = value
                    elif "Номер лицензии" in key:
                        record["primary_license_number"] = value
                    elif "Дата выдачи лицензии" in key:
                        record["primary_license_date"] = value
                    elif "Всего классов" in key:
                        record["current_license_number"] = value
                    
                        
                # поля переоформления из внутренней ant-table
                table = block.select_one(".ant-table-wrapper table")

                reissues = []

                if table:
                    rows = table.select("tbody tr")
                    for row in rows:
                        cells = row.select("td.ant-table-cell")
                        if len(cells) >= 4:
                            reissue = {
                                "date": parse_date(cells[0].get_text(strip=True)),
                                "basis": cells[1].get_text(strip=True),
                                "reason": cells[2].get_text(strip=True),
                                "currency_type": cells[3].get_text(strip=True),
                            }
                            reissues.append(reissue)

                record["is_reissued"] = bool(reissues)
                record["reissues"] = reissues if reissues else None

            parsed_data.append(record)

            organization_type_name = record.get("organization_type", "").strip().lower()
            org_type, _ = OrganizationTypeLicense.objects.get_or_create(name=organization_type_name)

            # Поиск секций формы (bold теги)
            form_headers = block.select("b")

            operation_data = []

            for form_header in form_headers:
                form_name = form_header.get_text(strip=True).replace(":", "")
                form_table = form_header.find_next("table")

                if not form_table:
                    continue

                lic_type, _ = LicenseType.objects.get_or_create(
                    type=org_type,
                    name=form_name
                )

                rows = form_table.select("tr")
                for row in rows:
                    cells = row.select("td")
                    if len(cells) != 2:
                        continue
                    name = cells[0].get_text(strip=True)
                    value = cells[1].get_text(strip=True)

                    # если стоит галочка
                    if "✓" in value or "✔" in value:
                        op_type, _ = OperationType.objects.get_or_create(
                            licensetype=lic_type,
                            name=name
                        )
                        operation_data.append({
                            "license_type": lic_type,
                            "operation_type": op_type,
                            "license_name": record.get("current_license_number", "")
                        })

            record["operations"] = operation_data

        return parsed_data

    finally:
        driver.quit()


def parse_issued_assurances_licenses():
    print("🚀 Начало парсинга лицензий страховых компаний...")
    
    parsed_data = extract_excel_from_govkz()
    if not parsed_data:
        print("❌ Не удалось получить данные.")
        return

    print(f"📄 Найдено записей: {len(parsed_data)}")

    for i, record in enumerate(parsed_data, start=1):
        print(f"\n🔎 Запись {i}:")
        print(f"  ▶️ Название: {record.get('name')}")
        print(f"  ▶️ БИН: {record.get('bin')}")
        print(f"  ▶️ Организация: {record.get('organization_type')}")
        print(f"  ▶️ Текущая лицензия: {record.get('current_license_number')}")
        print(f"  ▶️ Переоформлений: {len(record.get('reissues') or [])}")
        print(f"  ▶️ Операций: {len(record.get('operations') or [])}")

    print("\n🧾 Полный JSON:")
    print(json.dumps(parsed_data, indent=2, ensure_ascii=False))

    print("\n✅ Парсинг завершён.")



    # with transaction.atomic():
    #     for record in parsed_data:
    #         bin_code = record.get("bin", "").strip()
    #         name = record.get("name", "").strip()

    #         if not bin_code or not name:
    #             print(f"⛔ Пропущено: bin='{bin_code}', name='{name}'")
    #             skipped += 1
    #             continue

    #         if not bin_code or not name:
    #             skipped += 1
    #             continue

    #         fin = Fin.objects.filter(bin=bin_code).first()
    #         if not fin:
    #             update_fin_from_kdfo(bin_code)
    #             fin = Fin.objects.filter(bin=bin_code).first()
    #             if not fin:
    #                 skipped += 1
    #                 continue

            # IssuedLicense.objects.update_or_create(
            #     fin=fin,
            #     current_license_number=record.get("current_license_number", "").strip(),
            #     defaults={
            #         "organization_type": record.get("organization_type", ""),
            #         "primary_license_number": record.get("primary_license_number", ""),
            #         "primary_license_date": safe_date(record.get("primary_license_date")),
            #         "current_license_date": safe_date(record.get("current_license_date")),
            #         "decision_number": record.get("decision_number", ""),
            #         "decision_date": safe_date(record.get("decision_date")),
            #         "currency": record.get("currency", ""),
            #         "operations_count": safe_int(record.get("operations_count")),
            #         "operations_description": record.get("operations_description", ""),
            #         "is_reissued": record.get("is_reissued", False),
            #         "reissue_basis": record.get("reissue_basis"),
            #         "reissue_reason": record.get("reissue_reason"),
            #         "reissue_currency_type": record.get("reissue_currency_type"),
            #     }
            # )

    #         issued_license, _ = IssuedLicense.objects.update_or_create(
    #             fin=fin,
    #             current_license_number=record.get("current_license_number", "").strip(),
    #             defaults={
    #                 "organization_type": record.get("organization_type", ""),
    #                 "primary_license_number": record.get("primary_license_number", ""),
    #                 "primary_license_date": safe_date(record.get("primary_license_date")),
    #                 "current_license_date": safe_date(record.get("current_license_date")),
    #                 "decision_number": record.get("decision_number", ""),
    #                 "decision_date": safe_date(record.get("decision_date")),
    #                 "currency": record.get("currency", ""),
    #                 "operations_count": safe_int(record.get("operations_count")),
    #                 "operations_description": record.get("operations_description", ""),
    #                 "is_reissued": record.get("is_reissued", False),
    #             }
    #         )

    #         # Удаляем старые переоформления (если перезаписываем)
    #         issued_license.reissues.all().delete()

    #         # Добавляем новые, если есть
    #         reissues = record.get("reissues") or []
    #         for reissue in reissues:
    #             LicenseReissue.objects.create(
    #                 license=issued_license,
    #                 basis=reissue.get("basis", ""),
    #                 reason=reissue.get("reason", ""),
    #                 currency_type=reissue.get("currency_type", "")
    #             )

    #         # Удалить старые операции по этой лицензии
    #         issued_license.licenses.all().delete()

    #         # Сохраняем новые операции
    #         for op in record.get("operations", []):
    #             License.objects.create(
    #                 license_type=op["license_type"],
    #                 operation_type=op["operation_type"],
    #                 license_name=op["license_name"],
    #             )

    #         total += 1

    # print(f"✅ Загружено в БД: {total}, пропущено: {skipped}")


if __name__ == "__main__":
    parse_issued_assurances_licenses()
