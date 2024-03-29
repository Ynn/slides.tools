FROM node:20-slim


USER root
RUN apt update && apt install -y ghostscript && rm -rf /var/lib/apt/lists/*

WORKDIR /slidev
RUN npx playwright@1.41.2 install-deps chromium  \
    && rm -fr /root/.cache/ms-playwright/chromium*/chrome-linux/locales \
    && rm -fr /root/.npm \
    && rm -rf /usr/lib/x86_64-linux-gnu/dri \
    && chown -R node:node /slidev

USER node

RUN npm i -D playwright-chromium@1.41.2 --with-deps
RUN npm install --production @slidev/cli@0.48.1 \ 
                            @slidev/theme-seriph@0.25.0 \
                            @slidev/theme-default@0.25.0 \
                            @slidev/theme-apple-basic@0.25.0 \
                            @slidev/theme-bricks@0.25.0 \
                            @slidev/theme-shibainu@0.25.0 \
                            slidev-theme-light-icons@1.0.2\
                            slidev-theme-academic@1.2.0 \
                            slidev-theme-mokkapps@1.3.2 \
                            slidev-theme-dracula@0.2.0

COPY theme-nnynn/slidev-theme-nnynn-0.25.0.tgz .
RUN npm install --production slidev-theme-nnynn-0.25.0.tgz
WORKDIR /slidev/slides
