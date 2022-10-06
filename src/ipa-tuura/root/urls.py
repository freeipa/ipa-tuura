#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

"""root URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path, re_path
from rest_framework_swagger.views import get_swagger_view

schema_view = get_swagger_view(title='Domains API')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('scim/v2/', include('django_scim.urls')),
    path('creds/', include('creds.urls')),
    path('domains/v1/', include('domains.urls')),
    re_path('domains/doc', schema_view)
]
