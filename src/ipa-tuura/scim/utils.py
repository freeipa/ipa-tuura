#
# Copyright (C) 2024  FreeIPA Contributors see COPYING for license
#

from base64 import b64decode, b64encode

import gssapi
from django.db import NotSupportedError
from django_scim.filters import GroupFilterQuery, UserFilterQuery
from requests.auth import AuthBase
from scim.models import SSSDGroupToGroupModel, SSSDUserToUserModel
from scim.sssd import SSSD, SSSDNotFoundException


class SCIMUserFilterQuery(UserFilterQuery):
    """
    Custom UserFilterQuery allowing to search using SSSD DBus interface.
    """

    attr_map = {
        # attr, sub attr, uri
        ("userName", None, None): "scim_username",
        ("name", "familyName", None): "last_name",
        ("familyName", None, None): "last_name",
        ("name", "givenName", None): "first_name",
        ("givenName", None, None): "first_name",
        ("active", None, None): "is_active",
    }

    @classmethod
    def search(cls, filter_query, request=None):
        localresult = super(SCIMUserFilterQuery, cls).search(filter_query, request)
        if len(localresult) > 0:
            return localresult

        # The only supported search filters are equality filters
        items = filter_query.split(" ")
        if len(items) != 3:
            raise NotSupportedError("Support only exact search by username")

        (attr, op, value) = (items[0], items[1], items[2].strip('"'))
        if attr.lower() != "username":
            raise NotSupportedError("Support only search by username")
        if op.lower() != "eq":
            raise NotSupportedError("Support only exact search")

        try:
            sssd_if = SSSD()
            sssduser = sssd_if.find_user_by_name(value, retrieve_groups=True)
        except SSSDNotFoundException:
            return localresult

        user = SSSDUserToUserModel(sssd_if, sssduser)
        return [user]


class SCIMGroupFilterQuery(GroupFilterQuery):
    """
    Custom GroupFilterQuery allowing to search using SSSD DBus interface.
    """

    attr_map = {("displayName", None, None): "scim_display_name"}

    @classmethod
    def search(cls, filter_query, request=None):
        localresult = super(SCIMGroupFilterQuery, cls).search(filter_query, request)
        if len(localresult) > 0:
            return localresult

        # The only supported search filters are equality filters
        items = filter_query.split(" ")
        if len(items) != 3:
            raise NotSupportedError("Support only exact search by displayname")

        (attr, op, value) = (items[0], items[1], items[2].strip('"'))
        if attr.lower() != "displayname":
            raise NotSupportedError("Support only search by displayname")
        if op.lower() != "eq":
            raise NotSupportedError("Support only exact search")

        try:
            sssd_if = SSSD()
            sssdgroup = sssd_if.find_group_by_name(value, retrieve_members=True)
        except SSSDNotFoundException:
            return localresult

        group = SSSDGroupToGroupModel(sssd_if, sssdgroup)
        return [group]


class NegotiateAuth(AuthBase):
    """Negotiate Auth using python GSSAPI"""

    def __init__(self, target_host, ccache_name=None):
        self.context = None
        self.target_host = target_host
        self.ccache_name = ccache_name

    def __call__(self, request):
        self.initial_step(request)
        request.register_hook("response", self.handle_response)
        return request

    def deregister(self, response):
        response.request.deregister_hook("response", self.handle_response)

    def _get_negotiate_token(self, response):
        token = None
        if response is not None:
            h = response.headers.get("www-authenticate", "")
            if h.startswith("Negotiate"):
                val = h[h.find("Negotiate") + len("Negotiate") :].strip()
                if len(val) > 0:
                    token = b64decode(val)
        return token

    def _set_authz_header(self, request, token):
        request.headers["Authorization"] = "Negotiate {}".format(
            b64encode(token).decode("utf-8")
        )

    def initial_step(self, request, response=None):
        if self.context is None:
            store = {"ccache": self.ccache_name}
            creds = gssapi.Credentials(usage="initiate", store=store)
            name = gssapi.Name(
                "HTTP@{0}".format(self.target_host),
                name_type=gssapi.NameType.hostbased_service,
            )
            self.context = gssapi.SecurityContext(
                creds=creds, name=name, usage="initiate"
            )

        in_token = self._get_negotiate_token(response)
        out_token = self.context.step(in_token)
        self._set_authz_header(request, out_token)

    def handle_response(self, response, **kwargs):
        status = response.status_code
        if status >= 400 and status != 401:
            return response

        in_token = self._get_negotiate_token(response)
        if in_token is not None:
            out_token = self.context.step(in_token)
            if self.context.complete:
                return response
            elif not out_token:
                return response

            self._set_authz_header(response.request, out_token)
            # use response so we can make another request
            _ = response.content  # pylint: disable=unused-variable
            response.raw.release_conn()
            newresp = response.connection.send(response.request, **kwargs)
            newresp.history.append(response)
            return self.handle_response(newresp, **kwargs)

        return response
