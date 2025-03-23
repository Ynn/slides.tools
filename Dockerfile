FROM node:23-slim


USER root
RUN apt update && apt install -y ghostscript && rm -rf /var/lib/apt/lists/*

WORKDIR /slidev
RUN npx playwright@1.49 install-deps chromium  \
    && rm -fr /root/.cache/ms-playwright/chromium*/chrome-linux/locales \
    && rm -fr /root/.npm \
    && rm -rf /usr/lib/x86_64-linux-gnu/dri \
    && chown -R node:node /slidev

USER node
RUN npm i -D playwright-chromium@1.49 --with-deps
COPY --chown=node:node package.json .
RUN npm install --production
WORKDIR /slidev/slides
EXPOSE 3030/tcp
