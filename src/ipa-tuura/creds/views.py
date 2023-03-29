#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

import json
import logging

import pam
from creds import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.html import escape
from django.views import View

logger = logging.getLogger(__name__)


class SimplePwdView(LoginRequiredMixin, View):
    """
    View for credentials validation using username and password.
    """

    def get(self, request):
        form = forms.PwdValidationForm()
        ctx = {"form": form}
        return render(request, "creds/simple_pwd.html", ctx)

    def post(self, request):
        """
        Validation of user credentials using PAM stack.
        """
        form = forms.PwdValidationForm(request.POST)
        if form.is_valid():
            username = escape(form.cleaned_data["username"])
            password = escape(form.cleaned_data["password"])
            logger.debug("cred validation: validating user %s", username)
            p = pam.PamAuthenticator()
            res = p.authenticate(username, password)
            answer = {"validated": res, "reason": p.reason, "code": p.code}
            error = None
            logger.debug("cred validation: result %s reason %s", res, p.reason)
        else:
            answer = None
            error = {"message": form.errors}
            logger.debug("cred validation: form error %s", form.errors)
        result = {
            "username": form.cleaned_data.get("username"),
            "error": error,
            "result": answer,
        }
        return HttpResponse(content=json.dumps(result), content_type="application/json")
