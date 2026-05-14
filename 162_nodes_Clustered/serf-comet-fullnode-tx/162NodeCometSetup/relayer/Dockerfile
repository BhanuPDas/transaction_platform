FROM golang:1.25-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN go mod tidy
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o relayer ./client
FROM alpine:3.20
WORKDIR /app
RUN apk add --no-cache bash curl
COPY --from=builder /app/relayer .
COPY config.yaml /app/config.yaml
ENTRYPOINT ["/app/relayer"]