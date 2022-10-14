#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

from django.db import NotSupportedError
from django_scim.filters import UserFilterQuery, GroupFilterQuery
from ipatuura.models import SSSDUserToUserModel
from ipatuura.models import SSSDGroupToGroupModel
from ipatuura.sssd import SSSD, SSSDNotFoundException


class SCIMUserFilterQuery(UserFilterQuery):
    """
    Custom UserFilterQuery allowing to search using SSSD DBus interface.
    """
    attr_map = {
        # attr, sub attr, uri
        ('userName', None, None): 'scim_username',
        ('name', 'familyName', None): 'last_name',
        ('familyName', None, None): 'last_name',
        ('name', 'givenName', None): 'first_name',
        ('givenName', None, None): 'first_name',
        ('active', None, None): 'is_active',
    }

    @classmethod
    def search(cls, filter_query, request=None):
        localresult = super(SCIMUserFilterQuery, cls).search(
            filter_query, request)
        if len(localresult) > 0:
            return localresult

        # The only supported search filters are equality filters
        items = filter_query.split(" ")
        if len(items) != 3:
            raise NotSupportedError('Support only exact search by username')

        (attr, op, value) = (items[0], items[1], items[2].strip('"'))
        if attr.lower() != "username":
            raise NotSupportedError('Support only search by username')
        if op.lower() != 'eq':
            raise NotSupportedError('Support only exact search')

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
    attr_map = {
        ('displayName', None, None): 'scim_display_name'
    }

    @classmethod
    def search(cls, filter_query, request=None):
        localresult = super(SCIMGroupFilterQuery, cls).search(
            filter_query, request)
        if len(localresult) > 0:
            return localresult

        # The only supported search filters are equality filters
        items = filter_query.split(" ")
        if len(items) != 3:
            raise NotSupportedError('Support only exact search by displayname')

        (attr, op, value) = (items[0], items[1], items[2].strip('"'))
        if attr.lower() != "displayname":
            raise NotSupportedError('Support only search by displayname')
        if op.lower() != 'eq':
            raise NotSupportedError('Support only exact search')

        try:
            sssd_if = SSSD()
            sssdgroup = sssd_if.find_group_by_name(
                value, retrieve_members=True)
        except SSSDNotFoundException:
            return localresult

        group = SSSDGroupToGroupModel(sssd_if, sssdgroup)
        return [group]
