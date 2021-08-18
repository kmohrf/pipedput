FROM git-registry.hack-hro.de:443/kmohrf/docker-recipes/debbuild:buster AS pipedput-builddeps
WORKDIR /usr/src/app
# Create a deb package that contains all the packages from our
# Build-Depends section in the source package. This way we don’t
# have to list our build dependencies multiple times and are
# able to keep them all in the debian/control file.
COPY ./debian debian
RUN mk-build-deps debian/control


FROM git-registry.hack-hro.de:443/kmohrf/docker-recipes/debbuild-python-webdev:buster
# Copy the created Build-Depends package from the last build stage,
# serve it via a local apt repo, and install it so that all build
# dependencies for our build are available.
COPY --from=pipedput-builddeps \
    /usr/src/app/pipedput-build-deps_*.deb \
    /srv/local-apt-repository/pipedput-build-deps.deb
RUN /usr/lib/local-apt-repository/rebuild && \
    apt update -y --allow-releaseinfo-change && \
    apt install -y -t buster-backports pipedput-build-deps && \
    apt-get clean -y
