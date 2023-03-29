#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

from django import forms


class PwdValidationForm(forms.Form):
    """
    Form for credentials validation using username and password.
    """

    username = forms.CharField(max_length=63)
    password = forms.CharField(max_length=63, widget=forms.PasswordInput)
