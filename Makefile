include .env

up: datadir plugin
	docker-compose up --detach --no-recreate

up-gating:
	docker-compose -f docker-compose.gating.yaml up --no-recreate --detach

stop:
	docker-compose stop

down: stop
	docker-compose -f docker-compose.gating.yaml \
	-f docker-compose.yml down

datadir:
ifeq (,$(wildcard data/keycloak))
	mkdir -p data/keycloak
endif

container:
	$(MAKE) -C src

plugin: datadir
ifeq (,$(wildcard data/keycloak/$(PLUGIN_JAR)))
	cd data/keycloak && \
	wget https://github.com/justin-stephenson/scim-keycloak-user-storage-spi/${PLUGIN_ARCHIVE}/$(PLUGIN_TAG).tar.gz && \
	tar zxvf $(PLUGIN_TAG).tar.gz && \
	pushd $(PLUGIN_DIR) && \
	mvn clean package && \
	mv target/$(PLUGIN_JAR) ../ && \
	chown 994:994 ../${PLUGIN_JAR}
endif

bridge:
	source ./env.containers && \
	bash -c "src/install/setup_bridge.sh"

clean:
	rm -rf data/keycloak/*
