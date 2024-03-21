#
# Copyright (C) 2024  FreeIPA Contributors see COPYING for license
#

import socket

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

try:
    from ipalib.install.kinit import kinit_password
except ImportError:
    from ipapython.ipautil import kinit_password

import logging
import os
import tempfile

import requests
import SSSDConfig
from scim.utils import NegotiateAuth

logger = logging.getLogger(__name__)


class BridgeViewSet(GenericViewSet):
    @action(detail=False, methods=["post"])
    def login_password(self, request):
        if "user" not in request.POST:
            return Response("User not specified", status=status.HTTP_400_BAD_REQUEST)
        if "password" not in request.POST:
            return Response(
                "Password not specified", status=status.HTTP_400_BAD_REQUEST
            )

        try:
            sssdconfig = SSSDConfig.SSSDConfig()
            sssdconfig.import_config()
        except Exception as e:
            logger.info("Unable to read SSSD config")
            raise e

        ccache_dir = tempfile.mkdtemp(prefix="krbcc")
        ccache_name = os.path.join(ccache_dir, "ccache")

        user = request.POST["user"]
        passwd = request.POST["password"]

        try:
            kinit_password(user, passwd, ccache_name)
        except RuntimeError as e:
            raise RuntimeError("Kerberos authentication failed: {}".format(e))

        # We now have a valid ticket, request a session cookie
        server_hostname = socket.gethostname()
        r = requests.get(
            f"https://{server_hostname}/bridge/login_kerberos/",
            auth=NegotiateAuth(server_hostname, ccache_name),
            verify=False,  # TODO: proper certificates instead of self-signed
        )
        session_cookie = r.cookies.get("session")

        return Response({"session": session_cookie})
