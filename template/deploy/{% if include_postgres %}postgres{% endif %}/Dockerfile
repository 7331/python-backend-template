FROM golang:1.25-alpine@sha256:1ae0735f00daffa3aaf1363a5184c0d2dc55c78e3db4ec70241cdac97bf84b59 AS wal_g_build
ARG WAL_G_VERSION=v3.0.9
ARG WAL_G_COMMIT=3e493188db28335fb93a45bd680c6ff8fc3028c1
RUN apk add --no-cache build-base git libsodium-dev
RUN git clone --quiet --depth 1 --branch "$WAL_G_VERSION" https://github.com/wal-g/wal-g /src/wal-g && \
    test "$(git -C /src/wal-g rev-parse HEAD)" = "$WAL_G_COMMIT"
WORKDIR /src/wal-g/main/pg
RUN --mount=type=cache,target=/root/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=1 GOEXPERIMENT=jsonv2 go build -mod=mod -tags libsodium -trimpath \
      -ldflags "-s -w -X github.com/wal-g/wal-g/cmd/pg.walgVersion=$WAL_G_VERSION" -o /usr/local/bin/wal-g .

FROM postgres:18-alpine@sha256:123b17998ccaf47e53b502e8c6a1e79afd8f579c6f3eec83c563da026f957395
RUN apk add --no-cache libsodium
COPY --from=wal_g_build /usr/local/bin/wal-g /usr/local/bin/wal-g
