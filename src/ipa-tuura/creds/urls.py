#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

from creds import views
from django.urls import path

urlpatterns = [
    path("simple_pwd", views.SimplePwdView.as_view(), name="simple_pwd"),
]
