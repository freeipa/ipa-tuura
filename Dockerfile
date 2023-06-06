FROM fedora:38
# set TZ to ensure the test using timestamp
ENV TZ=Europe/Madrid

LABEL org.opencontainers.image.source=https://github.com/freeipa/ipa-tuura
LABEL org.opencontainers.image.description="IPA-tuura Container"

RUN INSTALL_PKGS="\
python3-sssdconfig maven unzip python3-pip git \
python3-netifaces python3-devel krb5-devel gcc \
sssd-dbus dbus-devel glibc glib2-devel dbus-daemon \
python-devel openldap-devel python-ipalib \
" && dnf install -y $INSTALL_PKGS && dnf clean all

COPY . ipa-tuura

WORKDIR /ipa-tuura

RUN pip install -r src/install/requirements.txt

RUN pip install dbus-python python-ldap

RUN python3 src/ipa-tuura/manage.py test

RUN python3 src/ipa-tuura/manage.py createsuperuser

ENTRYPOINT [ "python3 src/ipa-tuura/manage.py runserver" ]
