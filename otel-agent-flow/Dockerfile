FROM golang:1.27-bookworm@sha256:5c3e9b43cfd3bb95c7937462e29d87ada57b481a96fa23ad0eb61778d7a00110 AS native-agent
RUN git init /upstream && git -C /upstream remote add origin https://github.com/kagent-dev/kagent.git && git -C /upstream fetch --depth 1 origin b8d8b5ca7dd2cc4fba9ab1cc5c2b4b40536d0bf2 && git -C /upstream checkout --detach FETCH_HEAD
WORKDIR /upstream/go
RUN go mod download
COPY standalone/main.go ./flowdemo/main.go
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -ldflags="-s -w" -o /flow-standalone-agent ./flowdemo

FROM python:3.12-slim-bookworm@sha256:34386ef0cb081344d7ec1c103ba398e6e9f64e9ab3a1509accc92a4e24a07258
WORKDIR /app
COPY .build/grpcurl /usr/local/bin/grpcurl
COPY --from=native-agent /flow-standalone-agent /usr/local/bin/flow-standalone-agent
COPY backend.py telemetry.py onboarding.py onboarding_ordinary.py substrate_call.py standalone_call.py workflow_demo.py isolation_demo.py live_gitlab.py /app/
COPY ui /app/ui
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 BIND_ADDRESS=0.0.0.0
USER 10001:10001
EXPOSE 8787 8084
CMD ["python", "/app/backend.py"]
