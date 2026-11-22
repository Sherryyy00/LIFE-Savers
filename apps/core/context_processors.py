from django.conf import settings


def site(request):
    """Makes the site name and tagline available in every template."""
    return {"SITE_NAME": settings.SITE_NAME, "SITE_TAGLINE": settings.SITE_TAGLINE}
