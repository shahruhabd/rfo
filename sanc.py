import time
import os
import shutil
import tempfile
import json
from datetime import datetime

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# from sanctions.models import RegulatoryDecision, ViolationType, SanctionType, Department
# from fins.models import Fin

def get_text_or_none(parent, class_name):
    tag = parent.select_one(class_name)
    return tag.get_text(strip=True) if tag else None

def parse_sanctions():
    start = time.time()
    tmp_profile = tempfile.mkdtemp()

    options = Options()
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    # options.add_argument('--headless')  # можно вернуть, когда всё отладите
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'--user-data-dir={tmp_profile}')

    service = Service("chromedriver.exe")
    driver = webdriver.Chrome(service=service, options=options)

    try:
        driver.get("https://www.gov.kz/memleket/entities/ardfm/sanctions?lang=ru")
        time.sleep(1)

        # Опционально: закрыть баннер куки
        try:
            btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button#onetrust-accept-btn-handler"))
            )
            btn.click()
        except Exception:
            pass

        current_page = driver.find_element(
            By.CSS_SELECTOR, "li.ant-pagination-item-active"
        ).text
        
        all_results = []
        while True:
            from selenium.common.exceptions import ElementClickInterceptedException, NoSuchElementException

            # Ждём появления хотя бы одного заголовка
            WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, ".collapse-group button.collapse__header"))
            )

            # Раскрываем все блоки
            buttons = driver.find_elements(By.CSS_SELECTOR, ".collapse-group button.collapse__header")
            for btn in buttons:
                driver.execute_script("""
                    const rect = arguments[0].getBoundingClientRect();
                    window.scrollBy(0, rect.top - (window.innerHeight / 2));
                """, btn)
                try:
                    btn.click()
                except ElementClickInterceptedException:
                    driver.execute_script("arguments[0].click();", btn)

                time.sleep(0.1)

            soup = BeautifulSoup(driver.page_source, "html.parser")
            blocks = soup.select(".collapse-group .card.collapse")

            for block in blocks:
                item = {
                    "bin": None,
                    "organization": None,
                    "decision_date": None,
                    "decision_number": None,
                    "violation_type": None,
                    "sanction_type": None,
                    "sanction_amount": None,
                    "responsible_body": None,
                    "execution_deadline": None,
                    "npa_article": None,
                    "note": None,
                    "npa_type": None,
                    "department": None,
                }

                # Заголовок
                rows = block.select(".collapse__header__title--html .row")
                for row in rows:
                    k = get_text_or_none(row, ".col-md-4")
                    v = get_text_or_none(row, ".col-md-8")
                    if not k or not v:
                        continue
                    if "БИН" in k:
                        item["bin"] = v
                    elif "Наименование организации" in k:
                        item["organization"] = v
                    elif "Дата решения" in k:
                        try:
                            item["decision_date"] = datetime.strptime(v, "%d.%m.%Y").date().isoformat()
                        except ValueError:
                            item["decision_date"] = v
                    elif "Номер принятия" in k:
                        item["decision_number"] = v

                # Детали
                details = block.select(".collapse__content__card .row")
                for row in details:
                    label = get_text_or_none(row, ".typography__variant-bodyhl")
                    value = get_text_or_none(row, ".typography__variant-body")
                    if not label:
                        continue
                    if "Вид взыскания" in label:
                        item["violation_type"] = value
                    elif "Тип взыскания" in label:
                        item["sanction_type"] = value
                    elif "Наложенное взыскание" in label:
                        item["sanction_amount"] = value
                    elif "Существо нарушения" in label:
                        item["responsible_body"] = value
                    elif "Срок исполнения" in label:
                        try:
                            item["execution_deadline"] = datetime.strptime(value, "%d.%m.%Y").date().isoformat()
                        except ValueError:
                            item["execution_deadline"] = value
                    elif "Статья" in label:
                        item["npa_article"] = value
                    elif "Примечание" in label:
                        item["note"] = value
                    elif "Тип НПА" in label:
                        item["npa_type"] = value
                    elif "Наименование департамента" in label:
                        item["department"] = value

                all_results.append(item)
            
            next_link = driver.find_element(By.CSS_SELECTOR, "li.ant-pagination-next a")
            # проверяем, не отключена ли кнопка
            parent_li = next_link.find_element(By.XPATH, "..")
            if "ant-pagination-disabled" in parent_li.get_attribute("class"):
                break  # больше нет страниц

            # скроллим в видимую область
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_link)
            time.sleep(0.2)  # даём браузеру отреагировать

            old_page = current_page

            # клик
            try:
                next_link.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", next_link)

            retries = 3
            for attempt in range(retries):
                try:
                    WebDriverWait(driver, 10).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, "li.ant-pagination-item-active").text != old_page
                    )
                    break
                except Exception:
                    if attempt == retries - 1:
                        print(f"⚠️ Не удалось перейти на страницу после {old_page} даже после повторов.")
                        break
                    print("🔁 Повторная попытка перехода страницы...")
                    time.sleep(2)

    finally:
        driver.quit()
        shutil.rmtree(tmp_profile, ignore_errors=True)

    # Сохраняем JSON
    output_path = os.path.join(os.path.dirname(__file__), "sanctions.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # Вывод инфо
    duration = round(time.time() - start, 1)
    print(f"✅ Спарсено: {len(all_results)} записей")
    print(f"💾 JSON сохранён в: {output_path}")
    print(f"⏱️ Время выполнения: {duration} сек")

if __name__ == "__main__":
    parse_sanctions()
