build:
	podman build -t ipa-tuura/base .

run:
	podman run --name bridge -d -p 8000:8000 ipa-tuura/base && \
	podman start bridge

start:
	podman start bridge

exec:
	podman exec -it bridge bash

clean:
	podman rm -f bridge && \
	podman image rm ipa-tuura/base
