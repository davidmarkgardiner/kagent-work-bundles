# Build on a connected, approved build host; no credentials are required.
ARG NODE_IMAGE=node:22-bookworm@sha256:17b7fd60fd812617654c64b95f9b2dde94f103313073b672bc40fdad6dccbaa2
FROM ${NODE_IMAGE} AS installer
RUN apt-get update && apt-get install -y --no-install-recommends libsecret-1-dev python3 make g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY app/package.json app/package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund && npm_config_build_from_source=true npm_config_nodedir=/usr/local npm rebuild keytar

FROM ${NODE_IMAGE} AS dependencies
RUN apt-get update && apt-get install -y --no-install-recommends libsecret-1-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=installer /app/node_modules ./node_modules
COPY app/package.json app/package-lock.json ./
USER 1000:1000
ENV NODE_ENV=production MCP_HOST=0.0.0.0 PORT=8091 ADO_AUTH=pat

FROM dependencies AS runtime
COPY --chown=1000:1000 app/ ./
EXPOSE 8091
CMD ["node", "bridge.mjs"]
