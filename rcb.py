import os
import time
import shutil
import tempfile
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from seleniumwire import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By

from django.db import transaction
from fins.models import Fin, Sector
from parsers.models import ParseFins
from parsers.fin_updater import update_fin_from_kdfo
from fins.models import IssuedLicense  # замените импорт на ваш


def safe_date(value):
    try:
        return datetime.strptime(value.strip(), "%d.%m.%Y").date()
    except Exception:
        return None


def extract_bank_licenses(driver):
    print("🚀 Открываем страницу РЦБ…")
    driver.get(
        "https://www.gov.kz/memleket/entities/ardfm/permissions-notifications/"
        "section/1/subsection/3/registry/29?lang=ru"
    )
    time.sleep(10)

    headers = driver.find_elements(By.CSS_SELECTOR, ".collapse__header")
    print(f"🖱️ Найдено заголовков карточек: {len(headers)} — пробуем раскрыть")
    for i, btn in enumerate(headers, 1):
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", btn)
            btn.click()
            if i % 10 == 0:
                print(f"  🖱️ Раскрыто {i}/{len(headers)} карточек")
            time.sleep(0.2)
        except Exception as e:
            print(f"  ⚠️ Не смогли кликнуть карточку #{i}: {e}")

    # попытка раскрыть вложенные секции, если они есть
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

    # принудительно активируем все collapse через JS
    driver.execute_script("""
        document.querySelectorAll('.ant-collapse-item').forEach(item => item.classList.add('ant-collapse-item-active'));
        document.querySelectorAll('.ant-collapse-content').forEach(content => {
            content.classList.remove('ant-collapse-content-inactive');
            content.classList.add('ant-collapse-content-active');
            content.style.display = 'block';
            content.style.height = 'auto';
        });
    """)
    time.sleep(1)

    print("🔍 Снимаем HTML…")
    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select(".collapse__content__card")
    print(f"📦 После раскрытия найдено карточек: {len(cards)}")

    records = []
    for idx, card in enumerate(cards, 1):
        collapse_div = card.find_parent("div", class_="collapse")
        if not collapse_div:
            print(f"  [{idx}] ➖ нет parent.div.collapse")
            continue
        header_btn = collapse_div.find("button", class_="collapse__header")
        if not header_btn:
            print(f"  [{idx}] ➖ нет кнопки заголовка")
            continue
        name_el = header_btn.select_one(".collapse__value")
        if not name_el:
            print(f"  [{idx}] ➖ нет .collapse__value")
            continue

        name = name_el.get_text(strip=True)
        data = {"name": name}

        table = card.select_one(".ant-descriptions-view table")
        if not table:
            print(f"  [{idx}] ❌ нет описательной таблицы")
            continue

        for row in table.select("tr"):
            th = row.select_one("th")
            td = row.select_one("td")
            if not th or not td:
                continue
            key = th.get_text(strip=True)
            val = td.get_text(strip=True)

            if "БИН" in key:
                data["bin"] = val
            elif "Номер БД1" in key:
                data["primary_license_number"] = val
            elif "Дата БД1" in key:
                data["primary_license_date"] = safe_date(val)
            elif "Номер лицензии" in key:
                data["current_license_number"] = val
            elif "Дата выдачи лицензии" in key:
                data["current_license_date"] = safe_date(val)

        print(f"  [{idx}] → {data}")
        records.append(data)

    return records


def parse_rcb_from_govkz():
    start_time = datetime.now()
    total, skipped = 0, 0

    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-ipv6")
    tmp_profile = tempfile.mkdtemp(prefix="selenium-")
    options.add_argument(f"--user-data-dir={tmp_profile}")

    service = Service("/usr/bin/chromedriver")
    driver = webdriver.Chrome(
        service=service,
        options=options,
        seleniumwire_options={"verify_ssl": False}
    )

    try:
        records = extract_bank_licenses(driver)
        print(f"🎯 Всего записей после парсинга: {len(records)}")

        with transaction.atomic():
            for rec in records:
                print(f"🔄 Обрабатываем: {rec}")
                bin_code = rec.get("bin", "").strip()
                if not bin_code:
                    print("  ❌ Нет БИН — пропускаем")
                    skipped += 1
                    continue

                fin = Fin.objects.filter(bin=bin_code).first()
                if not fin:
                    print(f"  📡 Fin не найден, вызываем update_fin_from_kdfo({bin_code})")
                    update_fin_from_kdfo(bin_code)
                    fin = Fin.objects.filter(bin=bin_code).first()
                if not fin:
                    print(f"  ❌ Fin всё ещё не найден — пропускаем")
                    skipped += 1
                    continue

                sector = Sector.objects.get(name_sector="Рынок ценных бумаг")
                fin.sector.add(sector)
                print(f"  ➕ Добавлен сектор РЦБ к FIN {bin_code}")

                lic, created = IssuedLicense.objects.update_or_create(
                    fin=fin,
                    current_license_number=rec.get("current_license_number", ""),
                    defaults={
                        "organization_type": "Участник РЦБ",
                        "primary_license_number": rec.get("primary_license_number", ""),
                        "primary_license_date": rec.get("primary_license_date"),
                        "current_license_date": rec.get("current_license_date"),
                        "decision_number": None,
                        "decision_date": None,
                        "currency": "",
                        "operations_count": 0,
                        "operations_description": "Банковские операции",
                        "is_reissued": False,
                    }
                )
                status = "Создана" if created else "Обновлена"
                print(f"  ✅ {status} лицензия: {lic.fin.bin} — {lic.current_license_number}")
                total += 1

        ParseFins.objects.create(
            name="РЦБ",
            total_records=len(records),
            new_records=total,
            skipped_records=skipped,
            duration=datetime.now() - start_time
        )

    except Exception as e:
        print(f"❌ Общая ошибка: {e}")
        ParseFins.objects.create(
            name="РЦБ",
            total_records=0,
            new_records=0,
            skipped_records=0,
            error=str(e),
            duration=datetime.now() - start_time
        )

    finally:
        driver.quit()
        shutil.rmtree(tmp_profile, ignore_errors=True)

    print(f"✅ Итог — добавлено: {total}, пропущено: {skipped}")
    return total, skipped


if __name__ == "__main__":
    parse_rcb_from_govkz()
