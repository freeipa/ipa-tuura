<!---
#
# Copyright (C) 2022  FreeIPA Contributors see COPYING for license
#
-->

# ipa-tuura

This is a bridge providing SCIM 2.0 REST API, that can be deployed on a SSSD client and queries the user identities from the SSSD id provider.

## Installation

### SSSD preparation

Enroll the host as an IPA client:

```bash
$ ipa-client-install --domain ipa.test --realm IPA.TEST --principal admin --password Secret123 -U
```

The previous step creates a [domain/ipa.test] section in /etc/sssd/sssd.conf
but sssd.conf needs to be customized in order to return additional attributes.

The following script modifies sssd.conf:

```bash
$ cd $IPA_TUURA/src/install
$ python prepare_sssd.py
```

### Django preparation

Create and activate a python virtual env

```bash
$ python3 -m venv --system-site-packages ipatuura-env
$ source ipatuura-env/bin/activate
```

Install the requirements

```bash
$ pip install -r $IPA_TUURA/src/install/requirements.txt
```

Create the djangoadmin user and start the ipa-tuura server

Note: do not use "admin" name as it conflicts with IPA "admin" user

```bash
$ python manage.py createsuperuser
$ python manage.py runserver
```

If connecting from another system, update the ALLOWED_HOSTS line `root/settings.py`

```bash
ALLOWED_HOSTS = ['192.168.122.221', 'localhost', '127.0.0.1']
```

And run the following to have django listen on all interfaces:

```bash
$ python manage.py runserver 0.0.0.0:8000
```

### Documentation

This project uses Sphinx as a documentation generator. Follow these steps to build
the documentation:

```bash
$ cd $IPA_TUURA/doc/
$ make venv
$ make html
```

The generated documentation will be available at `$IPA_TUURA/doc/_build/html/` folder.
