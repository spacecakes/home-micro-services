FROM node:22-alpine AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM alpine:latest
RUN apk add --no-cache rsync python3 py3-pip curl openssh-client \
    && pip install --break-system-packages flask
COPY --from=frontend /build/dist /app/dist
WORKDIR /app

EXPOSE 8000
