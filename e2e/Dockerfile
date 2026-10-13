# Built from a Docker Hub image on purpose: the official Playwright image is
# hosted on mcr.microsoft.com, which the brief does not promise is reachable.
FROM node:22-bookworm-slim

WORKDIR /e2e

COPY package.json package-lock.json ./
RUN npm ci

# Installs the headless Chromium build plus the system libraries it needs.
# The browser version is tied to the pinned @playwright/test version.
RUN npx playwright install --with-deps --only-shell chromium

COPY . .

# Playwright runs TypeScript without checking the types, so the check is a
# build step: a type error in a test fails the image build. It comes after the
# browser install so that editing a test does not download Chromium again.
RUN npm run typecheck

CMD ["npx", "playwright", "test"]
