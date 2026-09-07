from django.db import models


class ComponentType(models.TextChoices):
    PREBUILT_PC = "prebuilt_pc", "PC Armado"
    NOTEBOOK = "notebook", "Notebook"
    CPU = "cpu", "Procesador"
    MOTHERBOARD = "motherboard", "Placa Madre"
    RAM = "ram", "Memoria RAM"
    GPU = "gpu", "Tarjeta de Video"
    PSU = "psu", "Fuente de Poder"
    CASE = "case", "Gabinete"
    COOLER = "cooler", "Refrigeracion"
    STORAGE = "storage", "Almacenamiento"
    MONITOR = "monitor", "Monitor"
    PERIPHERAL = "peripheral", "Accesorio/Periferico"
    SERVICE = "service", "Servicio"
    OTHER = "other", "Otro"


class Product(models.Model):
    # --- datos crudos, tal como vienen del catalogo real ---
    source_url = models.URLField(unique=True)
    name = models.CharField(max_length=500)
    brand = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True)
    breadcrumb = models.JSONField(default=list, blank=True)
    raw_category = models.CharField(max_length=200, blank=True)

    price_low = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_high = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=10, default="CLP")
    in_stock = models.BooleanField(default=True)

    rating_value = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    rating_count = models.PositiveIntegerField(null=True, blank=True)

    extraction_method = models.CharField(max_length=30, blank=True)
    scraped_at = models.DateTimeField(auto_now=True)

    # --- datos derivados por el motor de reglas (sin IA) ---
    component_type = models.CharField(
        max_length=20, choices=ComponentType.choices, default=ComponentType.OTHER, db_index=True
    )
    specs = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def discount_pct(self):
        if self.price_low and self.price_high and self.price_high > self.price_low:
            return round((1 - float(self.price_low) / float(self.price_high)) * 100)
        return 0
