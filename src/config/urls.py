"""
URL configuration for Tele-Backup project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path
from django.http import HttpResponseRedirect


def redirect_to_admin(request):
    """Redirect root URL to admin interface"""
    return HttpResponseRedirect('/admin/')


urlpatterns = [
    path('', redirect_to_admin, name='home'),
    path('admin/', admin.site.urls),
]
