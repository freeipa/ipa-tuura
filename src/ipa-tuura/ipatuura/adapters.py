#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

import logging

from django.contrib.auth.models import BaseUserManager
from django.db import transaction
from django_scim import exceptions
from django_scim.adapters import SCIMGroup, SCIMUser
from ipatuura.ipa import IPA

logger = logging.getLogger(__name__)


class SCIMUser(SCIMUser):
    @property
    def meta(self):
        """
        Return the meta object of the user per the SCIM spec.
        """
        d = {
            "resourceType": self.resource_type,
            "location": self.location,
        }
        return d

    def to_dict(self):
        """
        Return a ``dict`` conforming to the SCIM User Schema,
        ready for conversion to a JSON object.
        """
        d = super().to_dict()
        d.update(
            {
                "userName": self.obj.scim_username,
            }
        )

        return d

    def from_dict(self, d):
        """
        Consume a ``dict`` conforming to the SCIM User Schema, updating the
        internal user object with data from the ``dict``.
        Please note, the user object is not saved within this method. To
        persist the changes made by this method, please call ``.save()`` on the
        adapter. Eg::
            scim_user.from_dict(d)
            scim_user.save()
        """
        self.parse_active(d.get("active"))

        self.obj.first_name = d.get("name", {}).get("givenName") or ""
        self.obj.last_name = d.get("name", {}).get("familyName") or ""
        self.parse_email(d.get("emails"))
        if self.is_new_user and not self.obj.email:
            raise exceptions.BadRequestError("Empty email value")
        self.obj.scim_username = d.get("userName")
        self.obj.scim_external_id = d.get("externalId") or ""
        cleartext_password = d.get("password")
        if cleartext_password:
            self.obj.set_password(cleartext_password)
            self.obj._scim_cleartext_password = cleartext_password
            self.password_changed = True

    def parse_active(self, active):
        if active is not None:
            if active != self.obj.is_active:
                self.activity_changed = True
            self.obj.is_active = active

    def parse_email(self, emails_value):
        if emails_value:
            email = None
            if isinstance(emails_value, list):
                primary_emails = [e["value"] for e in emails_value if e.get("primary")]
                other_emails = [
                    e["value"] for e in emails_value if not e.get("primary")
                ]
                # Make primary emails the first in the list
                sorted_emails = list(map(str.strip, primary_emails + other_emails))
                email = sorted_emails[0] if sorted_emails else None
            elif isinstance(emails_value, dict):
                # if value is a dict, let's assume it contains the primary
                # email.
                # OneLogin sends a dict despite the spec:
                #   https://tools.ietf.org/html/rfc7643#section-4.1.2
                #   https://tools.ietf.org/html/rfc7643#section-8.2
                email = (emails_value.get("value") or "").strip()

            self.validate_email(email)

            self.obj.email = email

    @property
    def emails(self):
        """
        Return the email of the user per the SCIM spec.
        """
        if isinstance(self.obj.email, list):
            emails = []
            primary = True
            for onemail in self.obj.email:
                emails.append({"value": onemail, "primary": primary})
                primary = False
            return emails
        elif self.obj.email:
            return [{"value": self.obj.email, "primary": True}]
        else:
            return []

    @property
    def is_new_user(self):
        return not bool(self.obj.id)

    def save(self):
        ipa_if = IPA()
        temp_password = None
        if self.is_new_user:
            password = getattr(self.obj, "_scim_cleartext_password", None)
            # If temp password was not passed, create one.
            if password is None:
                self.obj.require_password_change = True
                manager = BaseUserManager()
                temp_password = manager.make_random_password()
                password = temp_password
            self.obj.set_password(password)
            ipa_if.user_add(self)

        is_new_user = self.is_new_user
        if not is_new_user:
            ipa_if.user_mod(self)
        try:
            with transaction.atomic():
                super().save()
                # if is_new_user:
                #    # Set SCIM ID to be equal to database ID.
                #    # Because users are uniquely identified with this value
                #    # its critical that changes to this line are well
                #    # considered before executed.
                #    self.obj.__class__.objects.update(scim_id=str(self.obj.id))
                logger.info(f"User saved. User id {self.obj.id}")
        except Exception as e:
            raise e

    def delete(self):
        self.obj.is_active = False
        ipa_if = IPA()
        ipa_if.user_del(self)
        self.obj.__class__.objects.filter(id=self.id).delete()


class SCIMGroup(SCIMGroup):
    @property
    def display_name(self):
        """
        Return the displayName of the group per the SCIM spec.
        """
        return self.obj.scim_display_name
