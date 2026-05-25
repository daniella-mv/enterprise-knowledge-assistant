# Frontend dev image. For Phase 6 we'll add a multi-stage prod build
# (vite build -> nginx). For now this serves the Vite dev server with HMR.
FROM node:20-alpine

WORKDIR /app

# Install deps first for layer caching.
COPY package.json ./
RUN npm install

# Copy the rest. docker-compose mounts src/, vite.config.ts etc. on top
# at runtime so edits hot-reload.
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]
