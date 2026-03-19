# Multi-stage build: the Astro site is built inside Docker so that no
# prebuilt dist/ directory needs to be committed to git.  If dist/ exists
# in the repo it is for local preview only and is NOT used by this image.
# Build: install deps + build static site
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install --no-package-lock
COPY . .
RUN npx astro build

# Serve: nginx with static files
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
