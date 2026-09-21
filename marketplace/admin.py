from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Boost,
    BoostPlan,
    Category,
    City,
    ContactEvent,
    EnterpriseAd,
    EnterpriseAdPlan,
    Favorite,
    Listing,
    ListingEvent,
    ListingImage,
    Neighborhood,
    Notification,
    Payment,
    PlatformSettings,
    ProfileShareEvent,
    Report,
    ShareEvent,
    SupportMessage,
    User,
    UserReport,
)


@admin.register(User)
class MarketplaceUserAdmin(UserAdmin):
    list_display = ("username", "phone_number", "display_name", "city", "is_blocked", "date_joined", "last_login")
    search_fields = ("username", "phone_number", "display_name", "email")
    list_filter = ("is_active", "is_staff", "is_blocked", "city")
    fieldsets = UserAdmin.fieldsets + (("Marché Local", {"fields": ("phone_number", "display_name", "bio", "avatar", "city", "show_phone", "is_blocked", "blocked_reason", "last_seen_at")} ),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Marché Local", {"fields": ("phone_number",)}),)


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    list_display = ("site_name", "monetization_enabled", "enterprise_ads_enabled", "listing_days", "renewal_notice_days")
    def has_add_permission(self, request):
        return not PlatformSettings.objects.exists()


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "category", "city", "status", "promo_type", "views_count", "whatsapp_clicks", "call_clicks", "expires_at")
    list_filter = ("status", "promo_type", "category", "city", "created_at")
    search_fields = ("title", "description", "slug", "user__username", "user__phone_number")
    readonly_fields = ("public_id", "created_at", "updated_at", "views_count", "whatsapp_clicks", "call_clicks", "share_count", "report_count", "last_viewed_at")
    list_select_related = ("user", "category", "city", "neighborhood")


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "listing", "created_at")
    list_filter = ("created_at",)
    search_fields = ("user__username", "user__phone_number", "listing__title")


@admin.register(ListingImage)
class ListingImageAdmin(admin.ModelAdmin):
    list_display = ("listing", "position", "is_cover", "created_at")
    list_filter = ("is_cover",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "position", "is_active")
    list_filter = ("is_active",)
    prepopulated_fields = {"slug": ("name",)}


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "is_active")
    list_filter = ("region", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Neighborhood)
class NeighborhoodAdmin(admin.ModelAdmin):
    list_display = ("name", "city", "is_active")
    list_filter = ("city", "is_active")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "reason", "status", "created_at")
    list_filter = ("reason", "status", "created_at")
    search_fields = ("listing__title", "message", "reporter_phone")


@admin.register(UserReport)
class UserReportAdmin(admin.ModelAdmin):
    list_display = ("id", "target_user", "reporter_user", "reason", "status", "created_at")
    list_filter = ("status", "reason")
    search_fields = ("target_user__username", "reporter_phone", "message")


@admin.register(ListingEvent)
class ListingEventAdmin(admin.ModelAdmin):
    list_display = ("listing", "event_type", "platform", "user", "created_at")
    list_filter = ("event_type", "platform", "created_at")
    search_fields = ("listing__title", "user__username", "ip_hash")


@admin.register(ContactEvent)
class ContactEventAdmin(admin.ModelAdmin):
    list_display = ("listing", "event_type", "user", "created_at")
    list_filter = ("event_type", "created_at")


@admin.register(ShareEvent)
class ShareEventAdmin(admin.ModelAdmin):
    list_display = ("listing", "platform", "created_at")
    list_filter = ("platform", "created_at")


@admin.register(ProfileShareEvent)
class ProfileShareEventAdmin(admin.ModelAdmin):
    list_display = ("profile", "platform", "created_at")
    list_filter = ("platform", "created_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "title", "is_read", "created_at")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("user__username", "title", "message")


@admin.register(BoostPlan)
class BoostPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_days", "price", "currency", "promotion_type", "is_active", "position")
    list_filter = ("is_active",)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("reference", "provider", "user", "amount", "currency", "status", "paid_at", "created_at")
    list_filter = ("provider", "status", "currency")
    search_fields = ("reference", "user__username", "user__phone_number")


@admin.register(Boost)
class BoostAdmin(admin.ModelAdmin):
    list_display = ("listing", "plan", "status", "starts_at", "ends_at")
    list_filter = ("status",)


@admin.register(EnterpriseAdPlan)
class EnterpriseAdPlanAdmin(admin.ModelAdmin):
    list_display = ("name", "duration_days", "price", "is_active", "position")
    list_filter = ("is_active",)


@admin.register(EnterpriseAd)
class EnterpriseAdAdmin(admin.ModelAdmin):
    list_display = ("business_name", "title", "status", "starts_at", "ends_at", "position")
    list_filter = ("status",)
    search_fields = ("business_name", "title", "description")


@admin.register(SupportMessage)
class SupportMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "phone_number", "is_resolved", "created_at")
    list_filter = ("is_resolved",)
    search_fields = ("name", "phone_number", "message")
