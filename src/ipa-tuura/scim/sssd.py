#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#

import dbus

DBUS_SSSD_NAME = "org.freedesktop.sssd.infopipe"
DBUS_SSSD_PATH = "/org/freedesktop/sssd/infopipe"
DBUS_SSSD_IF = "org.freedesktop.sssd.infopipe"
DBUS_PROPERTY_IF = "org.freedesktop.DBus.Properties"
DBUS_SSSD_USERS_PATH = "/org/freedesktop/sssd/infopipe/Users"
DBUS_SSSD_USERS_IF = "org.freedesktop.sssd.infopipe.Users"
DBUS_SSSD_USER_IF = "org.freedesktop.sssd.infopipe.Users.User"
DBUS_SSSD_GROUPS_PATH = "/org/freedesktop/sssd/infopipe/Groups"
DBUS_SSSD_GROUPS_IF = "org.freedesktop.sssd.infopipe.Groups"
DBUS_SSSD_GROUP_IF = "org.freedesktop.sssd.infopipe.Groups.Group"


class SSSDNotFoundException(Exception):
    """
    Exception returned when an SSSD user or group is not found.
    """

    pass


class SSSDGroup:
    """
    Represents a SSSD Group.

    SSSD groups are defined by an id (gidNumber in LDAP) and a name.
    """

    def __init__(self, id, name):
        self.id = id
        self.name = name
        self.members = []

    def set_members(self, members):
        self.members = members

    def __repr__(self):
        members = ", ".join(self.members)
        msg = "Group {}({}): {}".format(self.id, self.name, members)
        return msg


class SSSDUser:
    """
    Represents a SSSD User.

    SSSD users are defined by an id (uidNumber in LDAP) and a username.
    """

    def __init__(self, id, username, **kwargs):
        self.id = id
        self.username = username
        self.first_name = kwargs.get("givenname")
        self.last_name = kwargs.get("sn")
        self.mail = kwargs.get("mail")
        self.groups = kwargs.get("groups") or []
        self.active = kwargs.get("active")

    def __repr__(self):
        groups = ", ".join(self.groups)
        msg = "User {}({}): {}".format(self.id, self.username, groups)
        return msg


class _SSSD:
    _instance = None

    def __init__(self):
        """
        Initialization of the DBus objects and interfaces.
        """
        try:
            self._bus = dbus.SystemBus()
            self._sssd_obj = self._bus.get_object(DBUS_SSSD_NAME, DBUS_SSSD_PATH)
            self._sssd_iface = dbus.Interface(self._sssd_obj, DBUS_SSSD_IF)
            self._users_obj = self._bus.get_object(DBUS_SSSD_NAME, DBUS_SSSD_USERS_PATH)
            self._users_iface = dbus.Interface(self._users_obj, DBUS_SSSD_USERS_IF)
            self._groups_obj = self._bus.get_object(
                DBUS_SSSD_NAME, DBUS_SSSD_GROUPS_PATH
            )
            self._groups_iface = dbus.Interface(self._groups_obj, DBUS_SSSD_GROUPS_IF)
        except dbus.DBusException:
            # TBD: add some logging
            raise SSSDNotFoundException

    def _get_user_name(self, user_path):
        """
        Retrieve the user name for a given DBus user_path.

        :param user_path: the object_path for a Dbus User
        :returns: a str containing the user name
        """
        user_obj = self._bus.get_object(DBUS_SSSD_NAME, user_path)
        user_iface = dbus.Interface(user_obj, DBUS_PROPERTY_IF)
        name = user_iface.Get(DBUS_SSSD_USER_IF, "name")
        return str(name)

    def _get_group_from_path(self, group_path, retrieve_members=False):
        """
        Retrieve the group for a given DBus group_path.

        :param group_path: the object_path for a Dbus Group
        :param retrieve_members: if True, also fill in the members of the group
        :returns: a SSSDGroup object
        """
        group_obj = self._bus.get_object(DBUS_SSSD_NAME, group_path)
        group_props = dbus.Interface(group_obj, DBUS_PROPERTY_IF)
        name = group_props.Get(DBUS_SSSD_GROUP_IF, "name")
        id = group_props.Get(DBUS_SSSD_GROUP_IF, "gidNumber")

        sssdgroup = SSSDGroup(int(id), str(name))

        if retrieve_members:
            group_iface = dbus.Interface(group_obj, DBUS_SSSD_GROUP_IF)
            group_iface.UpdateMemberList(id)
            members = group_props.Get(DBUS_SSSD_GROUP_IF, "users")
            # Transform the users (object path) into names
            users = [self._get_user_name(user) for user in members]
            sssdgroup.set_members(users)
        return sssdgroup

    def find_group_by_name(self, name, retrieve_members=False):
        """
        Find the group with the specified name.

        :param name: a str containing the group name
        :param retrieve_members: if True, also fill in the members of the group
        :returns: a SSSDGroup object
        :raises SSSDNotFoundException: if no group matching the name exists
        """
        try:
            group_path = self._groups_iface.FindByName(name)
            return self._get_group_from_path(group_path, retrieve_members)
        except dbus.exceptions.DBusException:
            raise SSSDNotFoundException("Group {} not found".format(name))

    def find_group_by_id(self, id, retrieve_members=False):
        """
        Find the group with the specified id.

        :param name: an int containing the group id
        :param retrieve_members: if True, also fill in the members of the group
        :returns: a SSSDGroup object
        :raises SSSDNotFoundException: if no group matching the id exists
        """
        try:
            group_path = self._groups_iface.FindByID(id)
            return self._get_group_from_path(group_path, retrieve_members)
        except dbus.exceptions.DBusException:
            raise SSSDNotFoundException("Group {} not found".format(id))

    def _get_user_from_path(self, user_path, retrieve_groups=False):
        """
        Retrieve the user for a given DBus user_path.

        :param user_path: the object_path for a Dbus User
        :param retrieve_groups: if True, also fill in the groups of the user
        :returns: a SSSDUser object
        """
        user_obj = self._bus.get_object(DBUS_SSSD_NAME, user_path)
        user_iface = dbus.Interface(user_obj, DBUS_PROPERTY_IF)
        name = user_iface.Get(DBUS_SSSD_USER_IF, "name")
        id = user_iface.Get(DBUS_SSSD_USER_IF, "uidNumber")

        kwargs = dict()
        extra_attrs = user_iface.Get(DBUS_SSSD_USER_IF, "extraAttributes")

        # Retrieve firstname
        givenname = extra_attrs.get("givenname")
        if givenname:
            kwargs["givenname"] = str(givenname[0])
        # Retrieve lastname
        sn = extra_attrs.get("sn")
        if sn:
            kwargs["sn"] = str(sn[0])
        # Retrieve email
        mail = extra_attrs.get("mail")
        if mail:
            kwargs["mail"] = [str(x) for x in mail]
        # Retrieve active state
        locked = extra_attrs.get("lock")
        if locked and str(locked[0]).lower() == "true":
            kwargs["active"] = False
        else:
            kwargs["active"] = True

        if retrieve_groups:
            groups = self._sssd_iface.GetUserGroups(name)
            if groups:
                kwargs["groups"] = {str(x) for x in groups}

        sssduser = SSSDUser(id, name, **kwargs)
        return sssduser

    def find_user_by_name(self, username, retrieve_groups=False):
        """
        Find the user with the specified name.

        :param name: a str containing the user name
        :param retrieve_groups: if True, also fill in the groups of the user
        :returns: a SSSDUser object
        :raises SSSDNotFoundException: if no user matching the name exists
        """
        try:
            user_path = self._users_iface.FindByName(username)
            return self._get_user_from_path(user_path, retrieve_groups)
        except dbus.exceptions.DBusException:
            raise SSSDNotFoundException("User {} not found".format(username))

    def find_user_by_id(self, id, retrieve_groups=False):
        """
        Find the user with the specified id.

        :param id: an int containing the user id
        :param retrieve_groups: if True, also fill in the groups of the user
        :returns: a SSSDUser object
        :raises SSSDNotFoundException: if no user matching the id exists
        """
        try:
            user_path = self._users_iface.FindByID(id)
            return self._get_user_from_path(user_path, retrieve_groups)
        except dbus.exceptions.DBusException:
            raise SSSDNotFoundException("User {} not found".format(id))

    def find_user_groups(self, username):
        """
        Find the groups for the specified user.

        :param username: a str containing the user name
        :returns: an array of SSSDGroup objects, can be empty
        :raises SSSDNotFoundException: if no user matching the name exists
        """

        try:
            groups = self._sssd_iface.GetUserGroups(username)
            set_of_groups = {str(x) for x in groups}
            sssdgroups = []
            for grp in set_of_groups:
                sssdgroup = self.find_group_by_name(grp)
                sssdgroups.append(sssdgroup)
            return sssdgroups
        except dbus.exceptions.DBusException:
            raise SSSDNotFoundException("User {} not found".format(username))


def SSSD():
    if _SSSD._instance is None:
        _SSSD._instance = _SSSD()
    return _SSSD._instance
