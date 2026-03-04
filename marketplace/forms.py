from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone

from .models import CustomerProfile


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
