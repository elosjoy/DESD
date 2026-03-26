from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import CustomerProfile, ProducerProfile, Product, OrderItem


class CustomerRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30)
    delivery_address = forms.CharField(widget=forms.Textarea)
    postcode = forms.CharField(max_length=20)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")
    accept_terms = forms.BooleanField()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Email already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")
        if p1:
            validate_password(p1)
        return cleaned

    def save(self):
        email = self.cleaned_data["email"].strip().lower()
        password = self.cleaned_data["password1"]

        user = User.objects.create_user(username=email, email=email, password=password)

        CustomerProfile.objects.create(
            user=user,
            full_name=self.cleaned_data["full_name"],
            phone=self.cleaned_data["phone"],
            delivery_address=self.cleaned_data["delivery_address"],
            postcode=self.cleaned_data["postcode"],
            terms_accepted=True,
            terms_accepted_at=timezone.now(),
        )
        return user


class ProducerRegistrationForm(forms.Form):
    producer_name = forms.CharField(max_length=200)
    contact_name = forms.CharField(max_length=200)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30)
    address = forms.CharField(widget=forms.Textarea)
    postcode = forms.CharField(max_length=20)
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username=email).exists():
            raise forms.ValidationError("Email already registered.")
        return email

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get("password1")
        p2 = cleaned.get("password2")

        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords do not match.")

        if p1:
            validate_password(p1)

        return cleaned

    def save(self):
        email = self.cleaned_data["email"].strip().lower()
        password = self.cleaned_data["password1"]

        user = User.objects.create_user(username=email, email=email, password=password)

        ProducerProfile.objects.create(
            user=user,
            producer_name=self.cleaned_data["producer_name"],
            contact_name=self.cleaned_data["contact_name"],
            phone=self.cleaned_data["phone"],
            address=self.cleaned_data["address"],
            postcode=self.cleaned_data["postcode"],
        )
        return user


class ProducerProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            "name",
            "price",
            "category",
            "description",
            "allergen_info",
            "harvest_date",
            "stock_quantity",
            "availability_status",
            "seasonal_availability",
        ]


class ProductAvailabilityUpdateForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["availability_status", "stock_quantity"]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['availability_status'].required = False
        self.fields['stock_quantity'].required = False


class ProducerOrderStatusUpdateForm(forms.Form):
    new_status = forms.ChoiceField(choices=[])
    producer_note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        allowed_statuses = kwargs.pop("allowed_statuses", [])
        super().__init__(*args, **kwargs)
        self.fields["new_status"].choices = [
            (status, label)
            for status, label in OrderItem.STATUS_CHOICES
            if status in allowed_statuses
        ]
