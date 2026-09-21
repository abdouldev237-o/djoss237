from django.urls import path

from . import views

app_name = "marketplace"

urlpatterns = [
    path("health/", views.health_check, name="health"),
    path("", views.home, name="home"),
    path("annonces/", views.listing_list, name="listing_list"),
    path("annonces/publier/", views.create_listing, name="create_listing"),
    path("annonces/<slug:slug>/", views.listing_detail, name="listing_detail"),
    path("annonces/<slug:slug>/modifier/", views.edit_listing, name="edit_listing"),
    path("annonces/<slug:slug>/whatsapp/", views.listing_whatsapp, name="listing_whatsapp"),
    path("annonces/<slug:slug>/appel/", views.listing_call, name="listing_call"),
    path("annonces/<slug:slug>/partager/", views.event_share, name="event_share"),
    path("annonces/<slug:slug>/favori/", views.toggle_favorite, name="toggle_favorite"),
    path("annonces/<slug:slug>/signaler/", views.report_form, name="report_form"),
    path("annonces/<slug:slug>/signaler/envoyer/", views.report_listing, name="report_listing"),
    path("htmx/quartiers/", views.neighborhoods_htmx, name="neighborhoods_htmx"),

    path("connexion/", views.public_user_form, name="login_form_page"),
    path("inscription/", views.public_signup_form, name="signup_form_page"),
    path("htmx/connexion/", views.login_htmx, name="login_htmx"),
    path("htmx/inscription/", views.signup_htmx, name="signup_htmx"),
    path("deconnexion/", views.logout_view, name="logout"),

    path("mes-annonces/", views.my_listings, name="my_listings"),
    path("favoris/", views.favorites, name="favorites"),
    path("mes-annonces/<slug:slug>/", views.owner_listing_detail, name="owner_listing_detail"),
    path("mes-annonces/<slug:slug>/pause/", views.owner_toggle_pause, name="owner_toggle_pause"),
    path("mes-annonces/<slug:slug>/vendue/", views.owner_mark_sold, name="owner_mark_sold"),
    path("mes-annonces/<slug:slug>/renouveler/", views.owner_renew, name="owner_renew"),
    path("mes-annonces/<slug:slug>/boost/", views.start_boost_checkout, name="start_boost_checkout"),
    path("mes-annonces/<slug:slug>/statistiques/", views.owner_listing_stats, name="owner_listing_stats"),
    path("mes-annonces/<slug:slug>/supprimer/", views.owner_delete, name="owner_delete"),

    path("profil/modifier/", views.profile_edit, name="profile_edit"),
    path("profil/<str:username>/", views.profile, name="profile"),
    path("profil/<str:username>/partager/", views.profile_share_event, name="profile_share_event"),
    path("profil/<str:username>/signaler/", views.report_user_form, name="report_user_form"),
    path("profil/<str:username>/signaler/envoyer/", views.report_user, name="report_user"),

    path("notifications/", views.notification_list, name="notifications"),
    path("notifications/<int:pk>/lue/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/toutes-lues/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
]
