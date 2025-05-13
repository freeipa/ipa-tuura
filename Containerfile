# Containerfile to build a RHEL/CentOS based image in production mode using Apache and WSGI
# This image is used by GitHub Actions to run Django unit tests
#
# You can build the image by running:
# podman build -f Containerfile .

ARG BASE_IMAGE=quay.io/centos/centos:stream9

FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.source=https://github.com/freeipa/ipa-tuura \
      org.opencontainers.image.description="ipa-tuura bridge service image"

ENV TZ=Europe/Madrid \
    DJANGO_SUPERUSER_PASSWORD=Secret123 \
    DJANGO_SUPERUSER_USERNAME=scim \
    DJANGO_SUPERUSER_EMAIL=scim@ipa.test

# Install system dependencies
RUN dnf -y update && dnf -y install \
    dbus-daemon \
    dbus-devel \
    gcc \
    glib2-devel \
    git \
    glibc \
    httpd \
    krb5-devel \
    mod_ssl \
    mod_wsgi \
    openldap-devel \
    openssl \
    python3-devel \
    python3-netifaces \
    python3-pip \
    python3-sssdconfig \
    python-devel \
    python-ipalib \
    sssd-dbus \
    unzip \
    && dnf clean all

# Copy the source code
WORKDIR /www
RUN git clone https://github.com/freeipa/ipa-tuura ipa-tuura

# Install ipa-tuura dependencies
RUN dnf -y update && dnf -y install \
    openldap-clients \
    sssd \
    sssd-ldap \
    sssd-ipa \
    realmd \
    freeipa-client \
    oddjob-mkhomedir \
    mod_auth_gssapi \
    mod_session \
    gssproxy \
    openssh-clients \
    sshpass \
    && dnf clean all \
    && pip install -r /www/ipa-tuura/src/install/requirements.txt

RUN ls /www
RUN ls /www/ipa-tuura

# Django setup
WORKDIR /www/ipa-tuura/src/ipa-tuura/
RUN python3 manage.py makemigrations \
    && python3 manage.py migrate \
    && python3 manage.py createsuperuser --scim_username scim --noinput \
    && echo 'LoadModule wsgi_module modules/mod_wsgi.so' >> /etc/httpd/conf/httpd.conf \
    && sed -i 's/ALLOWED_HOSTS = \[\]/ALLOWED_HOSTS = \['"'*'"'\]/g' /www/ipa-tuura/src/ipa-tuura/root/settings.py

# Generate and configure self-signed certificate
RUN cp /www/ipa-tuura/conf/ipa.conf /root
RUN openssl req -config /root/ipa.conf -newkey rsa -x509 -days 365 -out /etc/pki/tls/certs/apache-selfsigned.crt \
    && sed -i 's\localhost.crt\apache-selfsigned.crt\g' /etc/httpd/conf.d/ssl.conf \
    && sed -i 's\localhost.key\apache-selfsigned.key\g' /etc/httpd/conf.d/ssl.conf

# Deploy Apache virtual host
RUN cp /www/ipa-tuura/conf/ipatuura.conf /etc/httpd/conf.d/ipatuura.conf

# Setup permissions for apache user
RUN echo 'apache ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/apache \
    && usermod -a -G sssd,root apache \
    && chmod -R 770 /etc/sssd \
    && chmod 740 /www/ipa-tuura/src/ipa-tuura/ \
    && chown apache:apache /www/ipa-tuura/src/ipa-tuura/ \
    && chown apache:apache /www/ipa-tuura/src/ipa-tuura/db.sqlite3

# Setup gssproxy
RUN mkdir -m 0755 -p /etc/gssproxy \
    && cp /www/ipa-tuura/conf/gssproxy.conf /etc/gssproxy/80-httpd.conf
RUN mkdir -m 0755 -p /etc/systemd/system/httpd.service.d \
    && cp /www/ipa-tuura/conf/httpd_env.conf /etc/systemd/system/httpd.service.d/env.conf
RUN mkdir /var/lib/ipatuura \
    && chmod 770 /var/lib/ipatuura \
    && systemctl enable gssproxy

# Enable httpd service
RUN systemctl enable httpd

CMD [ "/sbin/init" ]
