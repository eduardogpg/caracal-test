from django.db import models
from caracal.models import LifeCycleModel
from caracal.callbacks import before_save, after_save, before_delete, after_delete


class Category(LifeCycleModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Product(LifeCycleModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE,
                                 related_name='products',
                                 default=None, null=True, blank=True)

    def __str__(self):
        return self.name

    @before_save(skip=True)
    def send_email(self, *args, **kwargs):
        print(f"Sending email for product {self.name}")

    @before_save
    def calculate_total(self, *args, **kwargs):
        print(f"Calculating total for product {self.name}")

    @before_save
    def update_category(self, *args, **kwargs):
        print(f"Updating category for product {self.name}")

    @before_delete
    def send_email_before_delete(self, *args, **kwargs):
        print(f"Sending email for product {self.name} before delete")

    @after_delete
    def send_email_after_delete(self, *args, **kwargs):
        print(f"Sending email for product {self.name} after delete")
