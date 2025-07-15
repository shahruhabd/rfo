from django.db import models

class Sector(models.Model):
    name_sector = models.CharField(max_length=200)

    def __str__(self):
        return self.name_sector

    class Meta:
        verbose_name = 'Сектор'
        verbose_name_plural = 'Секторы'

class Fin(models.Model):
    bin = models.CharField(max_length=12, unique=True, verbose_name="БИН")
    sector = models.ManyToManyField(Sector, null=True, blank=True, related_name='fin_sectors',  verbose_name='Сектор')
    full_name_ru = models.CharField(max_length=500, null=True, blank=True, verbose_name="Полное название (рус)")
    full_name_kz = models.CharField(max_length=500, null=True, blank=True, verbose_name="Полное название (каз)")
    full_name_en = models.CharField(max_length=500, null=True, blank=True, verbose_name="Полное название (англ)")
    short_name_ru = models.CharField(max_length=500, null=True, blank=True, verbose_name="Краткое название (рус)")
    short_name_kz = models.CharField(max_length=500, null=True, blank=True, verbose_name="Краткое название (каз)")
    short_name_en = models.CharField(max_length=500, null=True, blank=True, verbose_name="Краткое название (англ)")

    registration_date = models.DateField(null=True, blank=True, verbose_name="Дата регистрации")
    registration_last_date = models.DateField(null=True, blank=True, verbose_name="Дата последнего изменения")
    liquidation_date = models.DateField(null=True, blank=True, verbose_name="Дата ликвидации")

    org_status = models.CharField(max_length=100, null=True, blank=True, verbose_name="Статус")
    form_of_law = models.CharField(max_length=255, null=True, blank=True, verbose_name="Форма собственности")
    private_enterprise_type = models.CharField(max_length=255, null=True, blank=True, verbose_name="Тип предприятия")
    property_type = models.CharField(max_length=255, null=True, blank=True, verbose_name="Тип собственности")

    activity_code = models.CharField(max_length=10, null=True, blank=True, verbose_name="ОКЭД")
    activity_name_ru = models.CharField(max_length=500, null=True, blank=True, verbose_name="Вид деятельности (рус)")
    activity_name_kz = models.CharField(max_length=500, null=True, blank=True, verbose_name="Вид деятельности (каз)")

    address = models.TextField(null=True, blank=True, verbose_name="Адрес регистрации")
    zip_code = models.CharField(max_length=20, null=True, blank=True, verbose_name="Почтовый индекс")

    class Meta:
        verbose_name = "Финансовая организация"
        verbose_name_plural = "Финансовые организации"

    def __str__(self):
        return f"{self.short_name_ru or 'Без названия'}"
    

class FinLeader(models.Model):
    fin = models.OneToOneField(Fin, on_delete=models.CASCADE, related_name='leader')

    surname = models.CharField(max_length=100, verbose_name="Фамилия")
    name = models.CharField(max_length=100, verbose_name="Имя")
    middle_name = models.CharField(max_length=100, null=True, blank=True, verbose_name="Отчество")
    iin = models.CharField(max_length=12, verbose_name="ИИН")

    nationality = models.CharField(max_length=100, null=True, blank=True, verbose_name="Гражданство")
    country = models.CharField(max_length=100, null=True, blank=True, verbose_name="Страна")

    position_name = models.CharField(max_length=255, null=True, blank=True, verbose_name="Должность")
    issue_date = models.DateField(null=True, blank=True, verbose_name="Дата назначения")

    def full_name(self):
        return f'{self.surname} {self.name} {self.middle_name}'

    class Meta:
        verbose_name = "Руководитель"
        verbose_name_plural = "Руководители"

class FinFounderUL(models.Model):
    fin = models.ForeignKey(Fin, on_delete=models.CASCADE, related_name='founders_ul')

    bin = models.CharField(max_length=12, verbose_name="БИН")
    name_ru = models.CharField(max_length=500, null=True, blank=True, verbose_name="Название организации (рус)")
    name_kz = models.CharField(max_length=500, null=True, blank=True, verbose_name="Название организации (каз)")
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Доля (%)")
    value = models.BigIntegerField(null=True, blank=True, verbose_name="Взнос")

    class Meta:
        verbose_name = "Учредитель (ЮЛ)"
        verbose_name_plural = "Учредители (ЮЛ)"


class FinFounderFL(models.Model):
    fin = models.ForeignKey(Fin, on_delete=models.CASCADE, related_name='founders_fl')

    surname = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, null=True, blank=True)
    iin = models.CharField(max_length=12)
    country = models.CharField(max_length=100, null=True, blank=True)
    nationality = models.CharField(max_length=100, null=True, blank=True)
    percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    value = models.BigIntegerField(null=True, blank=True)
    
    def full_name(self):
        return f'{self.surname} {self.name} {self.middle_name}'

    class Meta:
        verbose_name = "Учредитель (ФЛ)"
        verbose_name_plural = "Учредители (ФЛ)"
    

from django.db import models


class IssuedLicense(models.Model):
    fin = models.ForeignKey(
        'Fin', on_delete=models.CASCADE,
        related_name="issued_licenses",
        verbose_name="Финансовая организация"
    )
    organization_type = models.CharField(max_length=255, verbose_name="Тип организации")

    primary_license_number = models.CharField(max_length=50, verbose_name="Номер первичной лицензии")
    primary_license_date = models.DateField(verbose_name="Дата первичной лицензии")

    current_license_number = models.CharField(max_length=50, verbose_name="Номер действующей лицензии")
    current_license_date = models.DateField(verbose_name="Дата действующей лицензии")

    decision_number = models.CharField(max_length=1000, null=True, blank=True, verbose_name="Номер решения уполномоченного органа")
    decision_date = models.DateField(null=True, blank=True, verbose_name="Дата решения уполномоченного органа")

    currency = models.CharField(max_length=100, verbose_name="Валюта операций")
    operations_count = models.PositiveIntegerField(verbose_name="Количество операций")
    operations_description = models.TextField(verbose_name="Банковские операции")

    is_reissued = models.BooleanField(default=False, verbose_name="Лицензия переоформлена")

    # Для страховых организаций
    total_insurances = models.CharField(max_length=100, null=True, blank=True, verbose_name="Количество страховых классов")

    class Meta:
        verbose_name = "Выданная лицензия"
        verbose_name_plural = "Реестр выданных лицензий"

    def __str__(self):
        return f"{self.fin} — {self.current_license_number}"
    

class LicenseReissue(models.Model):
    license = models.ForeignKey(
        IssuedLicense, on_delete=models.CASCADE,
        related_name='reissues',
        verbose_name='Лицензия'
    )
    basis = models.TextField(verbose_name="Основание переоформления")
    reason = models.TextField(verbose_name="Причина переоформления")
    currency_type = models.CharField(max_length=100, blank=True, null=True, verbose_name="Валюта при переоформлении")

    class Meta:
        verbose_name = "Переоформление лицензии"
        verbose_name_plural = "Переоформления лицензии"

    def __str__(self):
        return f"{self.date} — {self.reason}"


class SuspendedLicense(models.Model):
    fin = models.ForeignKey(
        'Fin', on_delete=models.CASCADE,
        related_name="suspended_licenses",
        verbose_name="Финансовая организация"
    )

    license_number = models.CharField(max_length=50, verbose_name="Номер лицензии")
    license_issue_date = models.DateField(verbose_name="Дата выдачи лицензии")
    currency = models.CharField(max_length=255, verbose_name="Валюта операций")

    suspension_type = models.CharField(max_length=255, verbose_name="Тип приостановления/лишения")
    decision_number = models.CharField(max_length=255, verbose_name="Номер решения уполномоченного органа")
    decision_date = models.DateField(verbose_name="Дата решения уполномоченного органа")
    suspension_reason = models.TextField(verbose_name="Основание приостановления / лишения")

    class Meta:
        verbose_name = "Приостановленная/лишённая лицензия"
        verbose_name_plural = "Реестр приостановленных/лишённых лицензий"

    def __str__(self):
        return f"{self.fin} — {self.license_number}"


class RevokedLicense(models.Model):
    fin = models.ForeignKey(
        'Fin', on_delete=models.CASCADE,
        related_name="revoked_licenses",
        verbose_name="Финансовая организация"
    )

    decision_number = models.CharField(max_length=100, verbose_name="Номер решения уполномоченного органа")
    decision_date = models.DateField(verbose_name="Дата решения уполномоченного органа")

    license_number = models.CharField(max_length=50, verbose_name="Номер лицензии")
    license_issue_date = models.DateField(verbose_name="Дата выдачи лицензии")

    activity_type = models.TextField(verbose_name="Вид деятельности")

    class Meta:
        verbose_name = "Прекратившая действие лицензия"
        verbose_name_plural = "Реестр прекращённых лицензий"

    def __str__(self):
        return f"{self.fin} — {self.license_number}"

class OrganizationTypeLicense(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Вид организации'
        verbose_name_plural = 'Виды организации'

# Модель для типа лицензии
class LicenseType(models.Model):
    type = models.ForeignKey(OrganizationTypeLicense, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Тип операций для лицензирования'
        verbose_name_plural = 'Тип операций для лицензирования'

# Модель для типа операции
class OperationType(models.Model):
    licensetype = models.ForeignKey(LicenseType, on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = 'Вид операции для лицензирования'
        verbose_name_plural = 'Вид операции для лицензирования'

class License(models.Model):
    license_type = models.ForeignKey(LicenseType, on_delete=models.CASCADE, related_name='licenses', null=True, blank=True)
    operation_type = models.ForeignKey(OperationType, on_delete=models.SET_NULL, related_name='licenses', null=True, blank=True)
    license_name = models.CharField(max_length=200)

    def __str__(self):
        return self.license_name

    class Meta:
        verbose_name = 'Лицензия'
        verbose_name_plural = 'Лицензии'
