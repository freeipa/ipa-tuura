#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.models import UserManager
from django.contrib.auth.models import GroupManager
from django.db import models
from django.db.utils import NotSupportedError
from django.utils.translation import gettext_lazy as _

from django_scim.models import AbstractSCIMGroupMixin, AbstractSCIMUserMixin

from ipatuura.sssd import SSSD, SSSDNotFoundException


def SSSDUserToUserModel(sssd_if, sssduser):
    """
    Create a User from an SSSDUser object.

    If the SSSDUser contains groups (basically group names), the User
    is updated with the group list as an array of Group.
    This requires access to DBus through the provided SSSD interface
    in order to fill the group gidNumber.

    :param sssd_if: SSSD interface obtained with sssd_if = SSSD()
    :param sssduser: SSSDUser object
    :returns: a User object
    """
    usermodel = User()
    usermodel.scim_username = sssduser.username
    usermodel.id = sssduser.id
    usermodel.scim_id = str(usermodel.id)
    usermodel.first_name = sssduser.first_name
    usermodel.last_name = sssduser.last_name
    usermodel.email = sssduser.mail
    usermodel.is_active = sssduser.active
    groups = []
    for groupname in sssduser.groups:
        try:
            sssdgroup = sssd_if.find_group_by_name(groupname)
            groupmodel = SSSDGroupToGroupModel(sssd_if, sssdgroup)
            groups.append(groupmodel)
        except SSSDNotFoundException:
            # TBD add logging
            pass
    usermodel.scim_groups.set(groups)
    return usermodel


def SSSDGroupToGroupModel(sssd_if, sssdgroup):
    """
    Create a Group from an SSSDGroup object.

    If the SSSDGroup contains members (basically user names), the Group
    is updated with the user list as an array of User.
    This requires access to DBus through the provided SSSD interface
    in order to fill the user uidNumber.

    :param sssd_if: SSSD interface obtained with sssd_if = SSSD()
    :param sssdgroup: SSSDGroup object
    :returns: a Group object
    """
    groupmodel = Group()
    groupmodel.scim_display_name = sssdgroup.name
    groupmodel.id = sssdgroup.id
    groupmodel.scim_id = str(groupmodel.id)
    users = []
    for username in sssdgroup.members:
        try:
            sssduser = sssd_if.find_user_by_name(username)
            usermodel = SSSDUserToUserModel(sssd_if, sssduser)
            users.append(usermodel)
        except SSSDNotFoundException:
            # TBD add logging
            pass
    groupmodel.user_set.set(users)
    return groupmodel


class CustomUserGroupRelationManager():
    """
    Manager allowing to access Groups linked to a User object.
    """
    groups = []

    def all(self):
        return self.groups

    def set(self, grouplist):
        self.groups = grouplist


class CustomUserManager(UserManager):
    """
    Manager specific to the User objects.
    """
    def create_user(self, scim_username, email, password=None):
        """
        Create and save a User with the scim_username, email and password.

        :param scim_username: user name
        :param email: user email
        :param password: user password
        :returns: a User object
        """
        if not scim_username:
            raise ValueError(_('The scim_username must be set'))
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(scim_username=scim_username,
                          email=self.normalize_email(email))
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, scim_username, email, password=None):
        """
        Create and save a SuperUser with the given email and password.

        :param scim_username: user name
        :param email: user email
        :param password: user password
        :returns: a User object
        """
        user = self.create_user(scim_username, email, password)
        user.is_staff = True
        user.is_superuser = True
        user.save()
        return user

    def get(self, *args, **kwargs):
        """
        Returns the User object matching the given lookup parameters.

        Look first in the local database, then look using SSSD interface.
        SSSD supports only simple searches (no AND / OR / NOT combination),
        and searches based on either the scim_id (mapped to uidNumber) or
        the scim_username (mapped to name).

        :returns: a User object
        :raises User.DoesNotExist: when no User matching the criteria is found
        :raises NotSupportedError: when the criteria are too complex
        """
        # Look for a user in the local DB first
        # This is needed for logging in as the django admin
        try:
            localuser = super().get(*args, **kwargs)
            return localuser
        except User.DoesNotExist:
            # Look in SSSD
            pass

        # Support only search by scim_id
        if 'scim_id' in kwargs.keys():
            try:
                sssd_if = SSSD()
                sssduser = sssd_if.find_user_by_id(
                    kwargs['scim_id'], retrieve_groups=True)
            except SSSDNotFoundException:
                raise User.DoesNotExist
            return SSSDUserToUserModel(sssd_if, sssduser)
        elif 'scim_username' in kwargs.keys():
            try:
                sssd_if = SSSD()
                sssduser = sssd_if.find_user_by_name(
                    kwargs['scim_username'], retrieve_groups=True)
            except SSSDNotFoundException:
                raise User.DoesNotExist
            return SSSDUserToUserModel(sssd_if, sssduser)
        else:
            raise NotSupportedError(
                'Support only exact search by scim_id or scim_username')


class User(AbstractSCIMUserMixin, AbstractBaseUser):
    """
    User model
    """
    # Why override this? Can't we just use what the AbstractSCIMUser mixin
    # gives us? The USERNAME_FIELD needs to be "unique" and for flexibility,
    # AbstractSCIMUser.scim_username is not unique by default.
    scim_username = models.CharField(
        _('SCIM Username'),
        max_length=254,
        null=True,
        blank=True,
        default=None,
        unique=True,
        help_text=_("A service provider's unique identifier for the user"),
    )

    first_name = models.CharField(
        _('First Name'),
        max_length=100,
    )

    last_name = models.CharField(
        _('Last Name'),
        max_length=100,
    )

    email = models.EmailField(
        _('Email'),
    )

    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_('Whether the user can log into this admin site'),
    )

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'scim_username'
    REQUIRED_FIELDS = ['email']

    # Override the object manager
    objects = CustomUserManager()

    def get_full_name(self):
        return self.first_name + ' ' + self.last_name

    def get_short_name(self):
        return self.first_name + (
            ' ' + self.last_name[0] if self.last_name else ''
        )

    @property
    def username(self):
        return self.scim_username

    @property
    def scim_groups(self):
        """
        Return a custom Relation Manager used to handle group membership.
        """
        if getattr(self, '_scim_groups', None):
            return self._scim_groups
        else:
            self._scim_groups = CustomUserGroupRelationManager()
            return self._scim_groups


class CustomGroupUserRelationManager():
    """
    Manager allowing to access Users linked to a Group object.
    """
    users = []

    def all(self):
        return self.users

    def set(self, userlist):
        self.users = userlist


class CustomGroupManager(GroupManager):
    """
    Manager specific to the Group objects.
    """
    def get(self, *args, **kwargs):
        """
        Returns the Group object matching the given lookup parameters.

        Look first in the local database, then look using SSSD interface.
        SSSD supports only simple searches (no AND / OR / NOT combination),
        and searches based on either the scim_id (mapped to gidNumber) or
        the scim_display_name (mapped to name).

        :returns: a Group object
        :raises Group.DoesNotExist: when no Group matching the criteria is
        found
        :raises NotSupportedError: when the criteria are too complex
        """

        # Look for a group in the local DB first
        try:
            localgroup = super().get(*args, **kwargs)
            return localgroup
        except Group.DoesNotExist:
            # Look in SSSD
            pass

        # Support only search by scim_id or scim_display_name
        if 'scim_id' in kwargs.keys():
            try:
                sssd_if = SSSD()
                sssdgroup = sssd_if.find_group_by_id(
                    kwargs['scim_id'], retrieve_members=True)
            except SSSDNotFoundException:
                raise Group.DoesNotExist

            return SSSDGroupToGroupModel(sssd_if, sssdgroup)
        elif 'scim_display_name' in kwargs.keys():
            try:
                sssd_if = SSSD()
                sssdgroup = sssd_if.find_group_by_name(
                    kwargs['scim_display_name'], retrieve_members=True)
            except SSSDNotFoundException:
                raise Group.DoesNotExist
            return SSSDGroupToGroupModel(sssd_if, sssdgroup)
        else:
            raise NotSupportedError(
                'Support only exact search by scim_id or scim_display_name')


class Group(AbstractSCIMGroupMixin):
    """
    Group model
    """
    # Override the object manager
    objects = CustomGroupManager()

    @property
    def user_set(self):
        """
        Return a custom Relation Manager used to handle the list of users.
        """
        if getattr(self, '_user_set', None):
            return self._user_set
        else:
            self._user_set = CustomGroupUserRelationManager()
            return self._user_set
