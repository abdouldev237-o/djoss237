from datetime import timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.utils import timezone

from .models import City, Listing, Neighborhood, Report, User
from .validators import normalize_cameroon_phone, validate_cameroon_phone, validate_image_upload


INPUT_CLASS = (
    "w-full min-w-0 rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3.5 "
    "text-base font-semibold text-slate-900 outline-none transition "
    "placeholder:text-slate-400 focus:border-slate-400 focus:bg-white "
    "focus:ring-4 focus:ring-slate-950/5 sm:text-sm"
)


class LoginForm(forms.Form):
    identifier = forms.CharField(max_length=150, label="Nom d’utilisateur ou téléphone")
    password = forms.CharField(widget=forms.PasswordInput, label="Mot de passe")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS


class SignupForm(UserCreationForm):
    username = forms.CharField(max_length=150, label="Nom d’utilisateur")
    phone_number = forms.CharField(max_length=20, label="Téléphone")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASS

    class Meta:
        model = User
        fields = ["username", "phone_number", "password1", "password2"]

    def clean_username(self):
        value = self.cleaned_data["username"].strip()
        if len(value) < 3:
            raise ValidationError("Le nom d'utilisateur doit contenir au moins 3 caractères.")
        if not value.replace("_", "").isalnum():
            raise ValidationError("Utilisez uniquement des lettres, chiffres et underscore.")
        return value

    def clean_phone_number(self):
        value = validate_cameroon_phone(self.cleaned_data["phone_number"])
        return value


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        single = super().clean
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [single(item, initial) for item in data]
        return [single(data, initial)]


class PublicListingForm(forms.ModelForm):
    neighborhood = forms.ModelChoiceField(
        queryset=Neighborhood.objects.none(),
        required=False,
        empty_label="Choisir un quartier",
        to_field_name="slug",
    )
    images = MultipleFileField(
        required=False,
        widget=MultipleFileInput(
            attrs={
                "accept": "image/jpeg,image/png,image/webp",
            }
        ),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput())

    duration_mode = forms.ChoiceField(
        label="Durée de publication",
        error_messages={"required": "Choisissez une durée de publication."},
        choices=[
            ("days", "Choisir un nombre de jours"),
            ("date", "Choisir une date précise"),
        ],
        initial="days",
    )
    duration_days = forms.IntegerField(
        label="Nombre de jours",
        error_messages={"required": "Choisissez le nombre de jours."},
        min_value=1,
        max_value=30,
        initial=30,
    )
    expires_at_input = forms.DateTimeField(
        label="Date d’expiration",
        required=False,
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S"],
        widget=forms.DateTimeInput(
            format="%Y-%m-%dT%H:%M",
            attrs={
                "type": "datetime-local",
                "class": INPUT_CLASS,
            },
        ),
    )

    class Meta:
        model = Listing
        fields = [
            "category",
            "city",
            "neighborhood",
            "title",
            "description",
            "price",
            "price_type",
            "condition",
            "images",
        ]
        widgets = {
            "category": forms.Select(),
            "city": forms.Select(),
            "neighborhood": forms.Select(),
            "title": forms.TextInput(
                attrs={
                    "maxlength": 180,
                    "placeholder": "Ex. Appartement 2 chambres à Bonapriso",
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "rows": 7,
                    "maxlength": 5000,
                    "placeholder": "Décrivez l’article, le service, le logement, le quartier, ce qui est inclus…",
                }
            ),
            "price": forms.NumberInput(
                attrs={
                    "min": 0,
                    "step": 1,
                    "placeholder": "Ex. 350000",
                    "inputmode": "numeric",
                }
            ),
            "price_type": forms.Select(),
            "condition": forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Show the whole active hierarchy. The label is indented for children.
        categories = self.fields["category"].queryset.filter(is_active=True).select_related("parent")
        self.fields["category"].queryset = categories
        self.fields["category"].label_from_instance = self.category_label

        self.fields["city"].queryset = City.objects.filter(is_active=True).order_by("name")
        self.fields["city"].widget.attrs.update({
            "hx-get": "/htmx/quartiers/",
            "hx-trigger": "change",
            "hx-target": "#id_neighborhood",
            "hx-swap": "innerHTML",
            "hx-include": "this",
            "hx-indicator": "#neighborhoodIndicator",
        })
        self.fields["neighborhood"].queryset = Neighborhood.objects.none()

        if self.is_bound:
            city_value = self.data.get("city")
            city = None
            try:
                city = City.objects.filter(pk=int(city_value), is_active=True).first()
            except (TypeError, ValueError):
                city = City.objects.filter(slug=str(city_value or ""), is_active=True).first()
            if city:
                self.fields["neighborhood"].queryset = city.neighborhoods.filter(is_active=True).order_by("name")
        elif self.instance and self.instance.pk and self.instance.city_id:
            self.fields["neighborhood"].queryset = self.instance.city.neighborhoods.filter(is_active=True).order_by("name")

        for name in [
            "category",
            "city",
            "neighborhood",
            "condition",
            "price_type",
            "price",
            "title",
            "description",
            "duration_mode",
            "duration_days",
        ]:
            self.fields[name].widget.attrs["class"] = INPUT_CLASS

        self.fields["duration_days"].widget.attrs.update({"min": "1", "max": "30", "inputmode": "numeric"})
        self.fields["category"].error_messages["required"] = "Choisissez une catégorie."
        self.fields["city"].error_messages["required"] = "Choisissez une ville."
        self.fields["title"].error_messages["required"] = "Saisissez un titre pour votre annonce."
        self.fields["description"].error_messages["required"] = "Décrivez votre annonce."
        self.fields["price_type"].error_messages["required"] = "Choisissez le type de prix."
        self.fields["condition"].error_messages["required"] = "Choisissez l’état de l’annonce."

        # When editing an existing listing, keep its current expiry visible.
        if self.instance and self.instance.pk:
            current_days = max(1, min(30, int(self.instance.duration_days or 30)))
            self.fields["duration_days"].initial = current_days
            if self.instance.expires_at:
                local_expiry = timezone.localtime(self.instance.expires_at)
                self.fields["expires_at_input"].initial = local_expiry.strftime("%Y-%m-%dT%H:%M")
                self.fields["duration_mode"].initial = (
                    "date" if self.instance.expires_at > timezone.now() else "days"
                )

    @staticmethod
    def category_label(category):
        if category.parent_id:
            return f"{category.parent.name}  ›  {category.name}"
        return category.name

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Requête non autorisée.")
        return ""

    def clean_title(self):
        value = self.cleaned_data["title"].strip()
        if len(value) < 5:
            raise ValidationError("Le titre doit contenir au moins 5 caractères.")
        return value

    def clean_description(self):
        value = self.cleaned_data["description"].strip()
        if len(value) < 10:
            raise ValidationError("La description est trop courte.")
        return value

    def clean_images(self):
        files = self.files.getlist("images")
        for file in files:
            validate_image_upload(file)
        return files

    def clean(self):
        cleaned = super().clean()
        city = cleaned.get("city")
        neighborhood = cleaned.get("neighborhood")
        if city and neighborhood and neighborhood.city_id != city.pk:
            self.add_error("neighborhood", "Le quartier ne correspond pas à la ville sélectionnée.")

        mode = cleaned.get("duration_mode") or "days"
        days = cleaned.get("duration_days") or 30
        exact = cleaned.get("expires_at_input")
        now = timezone.now()
        max_expiry = now + timedelta(days=30)
        min_expiry = now + timedelta(hours=1)

        if mode == "date":
            if not exact:
                self.add_error("expires_at_input", "Choisissez une date d’expiration.")
            else:
                if timezone.is_naive(exact):
                    exact = timezone.make_aware(exact, timezone.get_current_timezone())
                if exact <= min_expiry:
                    self.add_error("expires_at_input", "L’expiration doit être dans au moins 1 heure.")
                elif exact > max_expiry:
                    self.add_error("expires_at_input", "Une annonce ne peut pas dépasser 30 jours de publication.")
                else:
                    cleaned["expires_at"] = exact
                    cleaned["duration_days"] = max(1, min(30, int((exact - now).total_seconds() // 86400 + (1 if (exact - now).total_seconds() % 86400 else 0))))
        else:
            if days < 1 or days > 30:
                self.add_error("duration_days", "Choisissez une durée comprise entre 1 et 30 jours.")
            else:
                cleaned["duration_days"] = days
                cleaned["expires_at"] = now + timedelta(days=days)

        return cleaned


class ProfileForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ["display_name", "bio", "city", "avatar"]:
            self.fields[name].widget.attrs["class"] = INPUT_CLASS
        self.fields["show_phone"].widget.attrs["class"] = "h-5 w-5 rounded border-slate-300 text-slate-950 focus:ring-slate-900"

    class Meta:
        model = User
        fields = ["display_name", "bio", "city", "avatar", "show_phone"]
        widgets = {
            "display_name": forms.TextInput(attrs={"maxlength": 120}),
            "bio": forms.Textarea(attrs={"rows": 5, "maxlength": 1200}),
            "city": forms.Select(),
        }


class ReportForm(forms.ModelForm):
    class Meta:
        model = Report
        fields = ["reason", "message", "reporter_phone"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4, "maxlength": 2000, "placeholder": "Expliquez brièvement le problème."}),
            "reporter_phone": forms.TextInput(attrs={"placeholder": "Optionnel", "inputmode": "tel"}),
        }

    def clean_reporter_phone(self):
        value = self.cleaned_data.get("reporter_phone")
        return validate_cameroon_phone(value) if value else ""
