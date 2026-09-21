from .models import Notification, PlatformSettings


def marketplace_context(request):
    config = PlatformSettings.load()
    unread = 0
    if request.user.is_authenticated:
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return {
        "platform_settings": config,
        "unread_notifications": unread,
    }
