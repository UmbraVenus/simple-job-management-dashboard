# Stage 1: build the static bundle. Node is needed only here.
FROM node:22-bookworm-slim AS build

WORKDIR /app

# Lockfile first: `npm ci` is re-run only when dependencies change.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Runs `tsc --noEmit` first, so a type error fails the image build.
RUN npm run build

# Stage 2: the image that ships contains nginx and the built files, no Node.
FROM nginx:1.28-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
