from django.db import models
from django.conf import settings
from django.contrib.postgres.indexes import GinIndex

class Establishment(models.Model):
    name = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=20, unique=True, null=True, blank=True)
    address = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class Product(models.Model):
    name = models.CharField(max_length=255)
    barcode = models.CharField(max_length=50, null=True, blank=True)
    category = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        indexes = [
            GinIndex(name='product_name_trgm_idx', fields=['name'], opclasses=['gin_trgm_ops'])
        ]

    def __str__(self):
        return self.name

class Receipt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    establishment = models.ForeignKey(Establishment, on_delete=models.CASCADE)
    issue_date = models.DateTimeField(help_text="Data da compra na nota")
    created_at = models.DateTimeField(auto_now_add=True, help_text="Data em que foi escaneada")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    access_key = models.CharField(max_length=44, unique=True)

    def __str__(self):
        return f"Nota {self.access_key} - {self.establishment.name}"

class ReceiptItem(models.Model):
    receipt = models.ForeignKey(Receipt, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=3)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"